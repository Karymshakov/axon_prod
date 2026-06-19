from __future__ import annotations

import logging
import os
from urllib.parse import unquote, urlparse

from django.conf import settings

from apps.hotel_media.fingerprints import FingerprintError, compute_image_fingerprints, hamming_distance
from apps.hotel_media.models import HotelMediaItem, MediaFingerprint, SocialContentItem

logger = logging.getLogger(__name__)


HASH_THRESHOLDS = {
    'phash': 8,
    'center_phash': 8,
    'dhash': 8,
    'ahash': 7,
    'colorhash': 36,
}

HIGH_CONFIDENCE_SCORE = 0.88
MIN_ACCEPTED_SCORE = 0.82


def _metadata_text(metadata: dict) -> str:
    return str(metadata.get('text') or metadata.get('message') or '').strip()


def _file_url_to_path(file_url: str) -> str | None:
    if not file_url:
        return None

    parsed = urlparse(file_url)
    path = unquote(parsed.path if parsed.scheme else file_url)
    media_url = settings.MEDIA_URL or '/media/'
    if path.startswith(media_url):
        relative = path[len(media_url):].lstrip('/\\')
        local_path = os.path.join(settings.MEDIA_ROOT, relative)
        if os.path.exists(local_path):
            return local_path

    if os.path.exists(path):
        return path
    return None


def _social_content_from_metadata(metadata: dict, organization) -> SocialContentItem | None:
    candidates = []
    for key in (
        'instagram_story_id',
        'instagram_media_id',
        'instagram_share_id',
        'instagram_reel_id',
        'instagram_post_id',
    ):
        value = str(metadata.get(key) or '').strip()
        if value:
            candidates.append(value)

    social_context = metadata.get('instagram_context') or {}
    if isinstance(social_context, dict):
        for key in ('story_id', 'media_id', 'share_id', 'reel_id', 'post_id'):
            value = str(social_context.get(key) or '').strip()
            if value:
                candidates.append(value)

    if not candidates:
        return None

    queryset = SocialContentItem.objects.filter(
        platform=SocialContentItem.PLATFORM_INSTAGRAM,
        external_id__in=candidates,
        is_active=True,
    )
    if organization is not None:
        queryset = queryset.filter(organization=organization)
    item = queryset.order_by('-updated_at').first()
    if not item:
        return None

    has_semantic_context = bool(
        item.effective_category
        or item.effective_room_category
        or item.linked_media_item_id
        or item.reply_guidance
        or item.playbook_keys
    )
    if not has_semantic_context:
        logger.info(
            'Social content %s matched by platform ID but has no manager labels yet; treating media as unresolved',
            item.id,
        )
        return None

    return item


def _context_from_social_content(item: SocialContentItem, *, match_method: str, confidence: float) -> dict:
    category = item.effective_category
    room_category = item.effective_room_category
    linked = item.linked_media_item
    title = item.title or (linked.title if linked else '') or item.caption[:80]

    return {
        'source': 'social_content',
        'match_method': match_method,
        'confidence': round(confidence, 3),
        'needs_clarification': confidence < HIGH_CONFIDENCE_SCORE,
        'social_content_id': item.id,
        'platform': item.platform,
        'content_type': item.content_type,
        'external_id': item.external_id,
        'title': title,
        'caption': item.caption[:500],
        'category': category,
        'room_category': room_category or '',
        'playbook_keys': item.playbook_keys if isinstance(item.playbook_keys, list) else [],
        'reply_guidance': item.reply_guidance,
    }


def _context_from_fingerprint(fingerprint: MediaFingerprint, *, match_kind: str, distance: int, score: float) -> dict:
    social_item = fingerprint.social_content_item
    if social_item:
        context = _context_from_social_content(
            social_item,
            match_method=f'{match_kind}_hash',
            confidence=score,
        )
    else:
        media_item = fingerprint.hotel_media_item
        context = {
            'source': 'hotel_media',
            'match_method': f'{match_kind}_hash',
            'confidence': round(score, 3),
            'needs_clarification': score < HIGH_CONFIDENCE_SCORE,
            'hotel_media_item_id': media_item.id if media_item else None,
            'hotel_media_photo_id': fingerprint.hotel_media_photo_id,
            'title': media_item.title if media_item else '',
            'description': media_item.description[:500] if media_item else '',
            'category': media_item.category if media_item else '',
            'room_category': media_item.room_category or '' if media_item else '',
            'tags': media_item.tags if media_item and isinstance(media_item.tags, list) else [],
            'playbook_keys': [],
            'reply_guidance': '',
        }

    context['hash_distance'] = distance
    context['hash_kind'] = match_kind
    return context


def find_best_fingerprint_context(image_path: str, *, organization=None) -> dict | None:
    try:
        incoming_fingerprints = compute_image_fingerprints(image_path)
    except FingerprintError as exc:
        logger.warning('Could not fingerprint incoming media %s: %s', image_path, exc)
        return None

    best = None
    best_seen = None
    queryset = MediaFingerprint.objects.select_related(
        'hotel_media_item',
        'hotel_media_photo',
        'social_content_item',
    )
    if organization is not None:
        queryset = queryset.filter(organization=organization)

    candidate_count = queryset.count()
    if candidate_count == 0:
        logger.info(
            'Media fingerprint match skipped for %s: no fingerprints found for organization=%s. '
            'Run rebuild_media_fingerprints in this environment.',
            image_path,
            getattr(organization, 'id', organization),
        )
        return None

    by_kind = {record['hash_kind']: record for record in incoming_fingerprints}
    for hash_kind, incoming in by_kind.items():
        threshold = HASH_THRESHOLDS.get(hash_kind)
        if threshold is None:
            continue

        for candidate in queryset.filter(hash_kind=hash_kind).iterator():
            if candidate.bit_length != incoming.get('bit_length'):
                continue
            distance = hamming_distance(incoming['hash_value'], candidate.hash_value)
            if best_seen is None or distance < best_seen['distance']:
                best_seen = {
                    'distance': distance,
                    'hash_kind': hash_kind,
                    'fingerprint_id': candidate.id,
                    'hotel_media_item_id': candidate.hotel_media_item_id,
                    'social_content_item_id': candidate.social_content_item_id,
                    'threshold': threshold,
                    'bit_length': candidate.bit_length,
                }
            if distance > threshold:
                continue
            score = 1 - (distance / max(1, candidate.bit_length))
            if score < MIN_ACCEPTED_SCORE:
                continue
            if best is None or score > best['score']:
                best = {
                    'score': score,
                    'distance': distance,
                    'hash_kind': hash_kind,
                    'fingerprint': candidate,
                }

    if not best:
        logger.info(
            'Media fingerprint match unresolved for %s: candidates=%s best_seen=%s',
            image_path,
            candidate_count,
            best_seen,
        )
        return None

    context = _context_from_fingerprint(
        best['fingerprint'],
        match_kind=best['hash_kind'],
        distance=best['distance'],
        score=best['score'],
    )
    logger.info(
        'Media fingerprint matched for %s: context=%s',
        image_path,
        {
            'source': context.get('source'),
            'hotel_media_item_id': context.get('hotel_media_item_id'),
            'social_content_id': context.get('social_content_id'),
            'category': context.get('category'),
            'room_category': context.get('room_category'),
            'hash_kind': context.get('hash_kind'),
            'hash_distance': context.get('hash_distance'),
            'confidence': context.get('confidence'),
            'needs_clarification': context.get('needs_clarification'),
        },
    )
    return context


def build_agent_media_summary(context: dict, original_text: str = '') -> str:
    topic = context.get('category') or 'unknown'
    room_category = context.get('room_category') or ''
    title = context.get('title') or ''
    confidence = context.get('confidence')
    guidance = context.get('reply_guidance') or ''
    playbooks = context.get('playbook_keys') or []

    parts = [
        'Гость отправил медиа. Система распознала контекст медиа:',
        f'- тема/категория: {topic}',
    ]
    if room_category:
        parts.append(f'- room_category: {room_category}')
    if title:
        parts.append(f'- найденный_контент: {title}')
    if confidence is not None:
        parts.append(f'- уверенность: {confidence}')
    if playbooks:
        parts.append(f'- preferred_playbook_keys: {", ".join(str(p) for p in playbooks)}')
    if guidance:
        parts.append(f'- подсказка_менеджера_для_ответа: {guidance}')
    if context.get('needs_clarification'):
        parts.append('- confidence_policy: ask one concise clarification before naming the exact room/content as a fact')
        parts.append('- правило: не называй точную категорию номера как факт, пока гость не подтвердит')
    else:
        parts.append('- confidence_policy: you may use this context as verified')
        parts.append('- правило: этот контекст можно использовать как проверенный')

    if original_text and original_text not in {'[Изображение получено]', '[Видео получено]', '[Файл получен]'}:
        parts.append(f'Текст/подпись гостя: {original_text}')
        parts.append('Ответь на языке текста гостя. Если текст гостя на русском, ответь строго на русском.')
    else:
        parts.append('Гость не добавил полезную текстовую подпись.')
        parts.append('Ответь на русском по умолчанию, если история диалога явно не указывает другой язык.')
    return '\n'.join(parts)


def build_unresolved_media_summary(metadata: dict | None) -> str:
    metadata = metadata or {}
    media_type = metadata.get('media_type') or 'media'
    original_text = _metadata_text(metadata)
    parts = [
        f'Гость отправил {media_type}, но система не смогла уверенно сопоставить медиа с известным контентом отеля или Instagram.',
        'Не угадывай номер, категорию, помещение или контент как факт.',
        'Игнорируй любые прежние догадки по нераспознанным медиа; не продолжай бронирование конкретной категории номера, если ее не подтвердил гость или проверенный media_context.',
        'Задай один короткий уточняющий вопрос о том, что именно гость хочет узнать или какой это объект/номер.',
    ]
    if original_text and original_text not in {'[Изображение получено]', '[Видео получено]', '[Файл получен]'}:
        parts.append(f'Текст/подпись гостя: {original_text}')
        parts.append('Ответь на языке текста гостя. Если текст гостя на русском, ответь строго на русском.')
    else:
        parts.append('Гость не добавил полезную текстовую подпись.')
        parts.append('Ответь на русском по умолчанию, если история диалога явно не указывает другой язык.')
    return '\n'.join(parts)


def resolve_activity_media_context(activity, *, save: bool = True) -> dict | None:
    metadata = activity.metadata or {}
    organization = getattr(activity, 'organization', None) or getattr(activity.lead, 'organization', None)

    context = None
    social_item = _social_content_from_metadata(metadata, organization)
    if social_item:
        social_confidence = 1.0 if social_item.review_status == SocialContentItem.REVIEW_REVIEWED else 0.86
        context = _context_from_social_content(
            social_item,
            match_method='platform_external_id',
            confidence=social_confidence,
        )

    if context is None and metadata.get('media_type') in {'photo', 'image'}:
        image_path = _file_url_to_path(str(metadata.get('file_url') or ''))
        if image_path:
            context = find_best_fingerprint_context(image_path, organization=organization)

    if context is None:
        return None

    original_text = _metadata_text(metadata)
    context['agent_summary'] = build_agent_media_summary(context, original_text)

    if save:
        metadata['media_context'] = context
        metadata['visual_summary'] = context['agent_summary']
        metadata['ai_text'] = context['agent_summary']
        activity.metadata = metadata
        activity.save(update_fields=['metadata'])

    return context
