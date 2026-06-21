from __future__ import annotations

import logging
import os
from urllib.parse import parse_qs, unquote, urlparse

from django.conf import settings
from django.db import models

from apps.hotel_media.fingerprints import FingerprintError, compute_image_fingerprints, hamming_distance
from apps.hotel_media.models import HotelMediaItem, MediaFingerprint, SocialContentItem

logger = logging.getLogger(__name__)


HIGH_CONFIDENCE_SCORE = 0.88

# A single perceptual hash is deliberately insufficient. With hundreds of
# candidates, unrelated images regularly have one accidental 80-86% match.
STRUCTURAL_HASH_WEIGHTS = {
    'phash': 0.45,
    'dhash': 0.35,
    'ahash': 0.20,
}
STRUCTURAL_HASH_MIN_SCORES = {
    'phash': 0.78,
    'dhash': 0.78,
    'ahash': 0.82,
}
MIN_DIRECT_CONSENSUS_SCORE = 0.86
MIN_SCREENSHOT_CONSENSUS_SCORE = 0.82
MIN_WINNER_MARGIN = 0.025

INSTAGRAM_ID_KEYS = {
    'id',
    'media_id',
    'story_id',
    'share_id',
    'reel_id',
    'post_id',
    'attachment_id',
    'asset_id',
}
INSTAGRAM_URL_KEYS = {
    'url',
    'media_url',
    'thumbnail_url',
    'permalink',
    'story_url',
    'share_url',
}


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


def _append_unique(values: list[str], value: str | int | None) -> None:
    cleaned = str(value or '').strip()
    if cleaned and cleaned not in values:
        values.append(cleaned)


def _walk_nested(value):
    if isinstance(value, dict):
        for nested in value.values():
            yield from _walk_nested(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_nested(nested)
    else:
        yield value


def _collect_keyed_values(value, keys: set[str]) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in keys:
                if isinstance(nested, list):
                    for item in nested:
                        _append_unique(found, item)
                elif not isinstance(nested, dict):
                    _append_unique(found, nested)
            found.extend(v for v in _collect_keyed_values(nested, keys) if v not in found)
    elif isinstance(value, list):
        for nested in value:
            found.extend(v for v in _collect_keyed_values(nested, keys) if v not in found)
    return found


def _collect_urls(value) -> list[str]:
    urls: list[str] = []
    for nested in _walk_nested(value):
        text = str(nested or '').strip()
        if text.startswith(('http://', 'https://')):
            _append_unique(urls, text)
    return urls


def _normalize_url(value: str) -> str:
    parsed = urlparse(str(value or '').strip())
    if not parsed.netloc:
        return ''
    host = parsed.netloc.lower()
    if host.startswith('www.'):
        host = host[4:]
    path = unquote(parsed.path or '').rstrip('/')
    return f'{host}{path}'


def _ids_from_url(value: str) -> list[str]:
    parsed = urlparse(str(value or '').strip())
    params = parse_qs(parsed.query)
    ids: list[str] = []
    for key in ('id', 'media_id', 'story_id', 'share_id', 'reel_id', 'post_id', 'asset_id'):
        for item in params.get(key, []):
            _append_unique(ids, item)
    return ids


def _has_social_semantic_context(item: SocialContentItem) -> bool:
    return bool(
        item.effective_category
        or item.effective_room_category
        or item.linked_media_item_id
        or item.reply_guidance
        or item.playbook_keys
    )


def _base_social_queryset(organization):
    queryset = SocialContentItem.objects.filter(
        platform=SocialContentItem.PLATFORM_INSTAGRAM,
        is_active=True,
    )
    if organization is not None:
        queryset = queryset.filter(organization=organization)
    return queryset


def _social_content_types_for_context(content_type: str) -> tuple[str, ...]:
    normalized = str(content_type or '').strip().lower()
    if normalized in {SocialContentItem.TYPE_STORY, SocialContentItem.TYPE_HIGHLIGHT}:
        return (SocialContentItem.TYPE_STORY, SocialContentItem.TYPE_HIGHLIGHT)
    if normalized == SocialContentItem.TYPE_POST:
        return (SocialContentItem.TYPE_POST,)
    if normalized == SocialContentItem.TYPE_REEL:
        return (SocialContentItem.TYPE_REEL,)
    if normalized == SocialContentItem.TYPE_EVENT:
        return (SocialContentItem.TYPE_EVENT,)
    return ()


def _first_semantic_social_item(queryset, *, match_reason: str) -> SocialContentItem | None:
    items = list(queryset.order_by('-updated_at')[:100])
    items.sort(
        key=lambda item: (
            1 if item.review_status == SocialContentItem.REVIEW_REVIEWED else 0,
            1 if _has_social_semantic_context(item) else 0,
            item.updated_at,
        ),
        reverse=True,
    )
    for item in items:
        if _has_social_semantic_context(item):
            return item

    if items:
        logger.info(
            'Social content matched by %s but has no manager labels yet; treating media as unresolved. item_ids=%s',
            match_reason,
            [item.id for item in items[:5]],
        )
    return None


def _social_content_match_from_metadata(metadata: dict, organization) -> tuple[SocialContentItem | None, str]:
    social_context = metadata.get('instagram_context') or {}
    if not isinstance(social_context, dict):
        social_context = {}

    content_type = str(social_context.get('content_type') or '').strip().lower()
    if content_type in {SocialContentItem.TYPE_STORY, SocialContentItem.TYPE_HIGHLIGHT}:
        id_keys = ('instagram_story_id',)
        context_id_keys = ('story_id',)
    elif content_type == SocialContentItem.TYPE_REEL:
        id_keys = ('instagram_reel_id', 'instagram_share_id', 'instagram_media_id')
        context_id_keys = ('reel_id', 'share_id', 'media_id')
    elif content_type == SocialContentItem.TYPE_POST:
        id_keys = ('instagram_post_id', 'instagram_share_id', 'instagram_media_id')
        context_id_keys = ('post_id', 'share_id', 'media_id')
    else:
        id_keys = (
            'instagram_story_id',
            'instagram_reel_id',
            'instagram_post_id',
            'instagram_share_id',
            'instagram_media_id',
        )
        context_id_keys = ('story_id', 'reel_id', 'post_id', 'share_id', 'media_id')

    candidates: list[str] = []
    for key in id_keys:
        _append_unique(candidates, metadata.get(key))
    for key in context_id_keys:
        _append_unique(candidates, social_context.get(key))

    urls: list[str] = []
    for key in INSTAGRAM_URL_KEYS:
        _append_unique(urls, social_context.get(key))
    context_urls = social_context.get('urls')
    if isinstance(context_urls, list):
        for value in context_urls:
            _append_unique(urls, value)
    for key in INSTAGRAM_URL_KEYS:
        _append_unique(urls, metadata.get(key))
    for url in urls:
        for candidate in _ids_from_url(url):
            _append_unique(candidates, candidate)

    queryset = _base_social_queryset(organization)
    compatible_types = _social_content_types_for_context(content_type)
    if compatible_types:
        queryset = queryset.filter(content_type__in=compatible_types)
    if candidates:
        item = _first_semantic_social_item(
            queryset.filter(
                models.Q(external_id__in=candidates)
                | models.Q(parent_external_id__in=candidates)
            ),
            match_reason='platform ID',
        )
        if item:
            return item, 'platform_external_id'

    normalized_urls = {normalized for normalized in (_normalize_url(url) for url in urls) if normalized}
    if normalized_urls:
        exact_url_item = _first_semantic_social_item(
            queryset.filter(
                models.Q(media_url__in=urls)
                | models.Q(thumbnail_url__in=urls)
                | models.Q(permalink__in=urls)
            ),
            match_reason='exact URL',
        )
        if exact_url_item:
            return exact_url_item, 'platform_url'

        possible_items = list(queryset.order_by('-updated_at')[:300])
        possible_items.sort(
            key=lambda item: (
                1 if item.review_status == SocialContentItem.REVIEW_REVIEWED else 0,
                item.updated_at,
            ),
            reverse=True,
        )
        for item in possible_items:
            item_urls = [item.media_url, item.thumbnail_url, item.permalink]
            if isinstance(item.metadata, dict):
                item_urls.extend(_collect_urls(item.metadata))
                item_urls.extend(_collect_keyed_values(item.metadata, INSTAGRAM_URL_KEYS))
            item_normalized = {
                normalized
                for normalized in (_normalize_url(url) for url in item_urls)
                if normalized
            }
            if normalized_urls.intersection(item_normalized) and _has_social_semantic_context(item):
                return item, 'platform_url'

    return None, ''


def _context_from_social_content(item: SocialContentItem, *, match_method: str, confidence: float) -> dict:
    category = item.effective_category
    room_category = item.effective_room_category
    linked = item.linked_media_item
    title = item.title or (linked.title if linked else '') or item.caption[:80]
    linked_media_url = ''
    if linked and linked.file:
        try:
            linked_media_url = linked.file.url
        except ValueError:
            linked_media_url = ''
    preview_url = item.thumbnail_url or item.media_url or linked_media_url

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
        'media_url': item.media_url,
        'thumbnail_url': item.thumbnail_url,
        'permalink': item.permalink,
        'preview_url': preview_url,
        'linked_media_url': linked_media_url,
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
        media_url = ''
        photo_url = ''
        if media_item and media_item.file:
            try:
                media_url = media_item.file.url
            except ValueError:
                media_url = ''
        if fingerprint.hotel_media_photo and fingerprint.hotel_media_photo.file:
            try:
                photo_url = fingerprint.hotel_media_photo.file.url
            except ValueError:
                photo_url = ''
        context = {
            'source': 'hotel_media',
            'match_method': f'{match_kind}_hash',
            'confidence': round(score, 3),
            'needs_clarification': score < HIGH_CONFIDENCE_SCORE,
            'hotel_media_item_id': media_item.id if media_item else None,
            'hotel_media_photo_id': fingerprint.hotel_media_photo_id,
            'title': media_item.title if media_item else '',
            'description': media_item.description[:500] if media_item else '',
            'media_url': media_url,
            'photo_url': photo_url,
            'preview_url': photo_url or media_url,
            'category': media_item.category if media_item else '',
            'room_category': media_item.room_category or '' if media_item else '',
            'tags': media_item.tags if media_item and isinstance(media_item.tags, list) else [],
            'playbook_keys': [],
            'reply_guidance': '',
        }

    context['hash_distance'] = distance
    context['hash_kind'] = match_kind
    return context


def _fingerprint_owner_key(fingerprint: MediaFingerprint) -> tuple:
    if fingerprint.social_content_item_id:
        return ('social', fingerprint.social_content_item_id)
    if fingerprint.hotel_media_photo_id:
        return ('hotel_photo', fingerprint.hotel_media_photo_id)
    return ('hotel_item', fingerprint.hotel_media_item_id)


def _fingerprint_variant_key(fingerprint: MediaFingerprint) -> tuple:
    """Keep album photos separate while grouping hash kinds of one source image."""
    owner = _fingerprint_owner_key(fingerprint)
    if fingerprint.hotel_media_photo_id:
        return (*owner, 'photo', fingerprint.hotel_media_photo_id)
    if fingerprint.hotel_media_item_id:
        return (*owner, 'item', fingerprint.hotel_media_item_id)
    return (*owner, 'remote')


def _consensus_score(evidence: dict[str, dict]) -> float:
    total_weight = sum(STRUCTURAL_HASH_WEIGHTS[kind] for kind in evidence)
    if not total_weight:
        return 0.0
    return sum(
        item['score'] * STRUCTURAL_HASH_WEIGHTS[kind]
        for kind, item in evidence.items()
    ) / total_weight


def _is_consensus_match(evidence: dict[str, dict], *, is_screenshot_region: bool) -> bool:
    kinds = set(evidence)
    if len(kinds) < 2:
        return False
    # Two weak brightness/edge hashes are not enough without pHash. All three
    # algorithms may agree when pHash is mildly affected by text overlays.
    if 'phash' not in kinds and len(kinds) < 3:
        return False
    minimum = MIN_SCREENSHOT_CONSENSUS_SCORE if is_screenshot_region else MIN_DIRECT_CONSENSUS_SCORE
    return _consensus_score(evidence) >= minimum


def find_best_fingerprint_context(image_path: str, *, organization=None) -> dict | None:
    try:
        incoming_fingerprints = compute_image_fingerprints(image_path, include_screenshot_regions=True)
    except FingerprintError as exc:
        logger.warning('Could not fingerprint incoming media %s: %s', image_path, exc)
        return None

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

    by_kind: dict[str, list[dict]] = {}
    for record in incoming_fingerprints:
        if record['hash_kind'] in STRUCTURAL_HASH_WEIGHTS:
            by_kind.setdefault(record['hash_kind'], []).append(record)

    grouped_evidence: dict[tuple, dict[str, dict]] = {}
    for hash_kind, incoming_records in by_kind.items():
        for candidate in queryset.filter(hash_kind=hash_kind).iterator():
            for incoming in incoming_records:
                if candidate.bit_length != incoming.get('bit_length'):
                    continue
                crop_label = str(incoming.get('crop_label') or '')
                distance = hamming_distance(incoming['hash_value'], candidate.hash_value)
                score = 1 - (distance / max(1, candidate.bit_length))
                if best_seen is None or distance < best_seen['distance']:
                    best_seen = {
                        'distance': distance,
                        'score': round(score, 3),
                        'hash_kind': hash_kind,
                        'fingerprint_id': candidate.id,
                        'hotel_media_item_id': candidate.hotel_media_item_id,
                        'social_content_item_id': candidate.social_content_item_id,
                        'bit_length': candidate.bit_length,
                        'incoming_crop_label': crop_label,
                    }
                if score < STRUCTURAL_HASH_MIN_SCORES[hash_kind]:
                    continue

                group_key = (_fingerprint_variant_key(candidate), crop_label)
                evidence = grouped_evidence.setdefault(group_key, {})
                record_data = {
                    'score': score,
                    'distance': distance,
                    'hash_kind': hash_kind,
                    'fingerprint': candidate,
                    'incoming_crop_label': crop_label,
                }
                previous = evidence.get(hash_kind)
                if previous is None or score > previous['score']:
                    evidence[hash_kind] = record_data

    ranked = []
    for (variant_key, crop_label), evidence in grouped_evidence.items():
        if not _is_consensus_match(evidence, is_screenshot_region=bool(crop_label)):
            continue
        raw_score = _consensus_score(evidence)
        evidence_count = len(evidence)
        # Convert raw visual similarity into calibrated identification confidence.
        # Agreement of independent hashes is substantially stronger than one score.
        confidence = min(0.99, raw_score + (0.08 if evidence_count >= 3 else 0.05))
        strongest = max(evidence.values(), key=lambda item: item['score'])
        ranked.append({
            **strongest,
            'owner_key': _fingerprint_owner_key(strongest['fingerprint']),
            'variant_key': variant_key,
            'raw_score': raw_score,
            'score': confidence,
            'evidence': evidence,
            'incoming_crop_label': crop_label,
        })

    ranked.sort(key=lambda item: (item['score'], item['raw_score'], len(item['evidence'])), reverse=True)
    best = ranked[0] if ranked else None

    if not best:
        logger.info(
            'Media fingerprint consensus unresolved for %s: candidates=%s best_seen=%s groups=%s',
            image_path,
            candidate_count,
            best_seen,
            len(grouped_evidence),
        )
        return None

    runner_up = next(
        (item for item in ranked[1:] if item['owner_key'] != best['owner_key']),
        None,
    )
    margin = best['score'] - runner_up['score'] if runner_up else 1.0
    if runner_up and margin < MIN_WINNER_MARGIN and best['score'] < 0.95:
        logger.info(
            'Media fingerprint consensus ambiguous for %s: best=%s runner_up=%s margin=%.3f',
            image_path,
            {
                'owner': best['owner_key'],
                'score': round(best['score'], 3),
                'raw_score': round(best['raw_score'], 3),
                'hashes': sorted(best['evidence']),
                'crop': best['incoming_crop_label'],
            },
            {
                'owner': runner_up['owner_key'],
                'score': round(runner_up['score'], 3),
                'raw_score': round(runner_up['raw_score'], 3),
                'hashes': sorted(runner_up['evidence']),
                'crop': runner_up['incoming_crop_label'],
            },
            margin,
        )
        return None

    context = _context_from_fingerprint(
        best['fingerprint'],
        match_kind='consensus',
        distance=best['distance'],
        score=best['score'],
    )
    context['raw_similarity'] = round(best['raw_score'], 3)
    context['match_evidence'] = sorted(best['evidence'])
    context['match_margin'] = round(margin, 3)
    if best.get('incoming_crop_label'):
        context['incoming_crop_label'] = best['incoming_crop_label']
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
            'raw_similarity': context.get('raw_similarity'),
            'match_evidence': context.get('match_evidence'),
            'match_margin': context.get('match_margin'),
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
        '- current_media_rule: это контекст ТЕКУЩЕГО сообщения; не подменяй его предыдущими фото/постами/сторис из истории',
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
    social_item, social_match_method = _social_content_match_from_metadata(metadata, organization)
    if social_item:
        social_confidence = 1.0 if social_item.review_status == SocialContentItem.REVIEW_REVIEWED else 0.86
        context = _context_from_social_content(
            social_item,
            match_method=social_match_method or 'platform_external_id',
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
