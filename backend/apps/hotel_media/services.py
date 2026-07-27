from __future__ import annotations

import logging
import os
import json
import tempfile
from datetime import timezone as datetime_timezone, timedelta
from urllib.parse import urlparse

import requests
from django.db.models import Q
from django.core.files.storage import default_storage
from django.utils.dateparse import parse_datetime
from django.utils import timezone

from .fingerprints import FingerprintError, compute_image_fingerprints
from .models import HotelMediaItem, HotelMediaPhoto, MediaFingerprint, SocialContentItem

logger = logging.getLogger(__name__)


def _normalize_social_labels(parsed: dict) -> dict:
    allowed_categories = {value for value, _ in HotelMediaItem.CATEGORY_CHOICES}
    allowed_rooms = {value for value, _ in HotelMediaItem.ROOM_CATEGORY_CHOICES}
    category = str(parsed.get('category') or '').strip()
    room_category = str(parsed.get('room_category') or '').strip()
    confidence = float(parsed.get('confidence') or 0)
    if confidence < 0.78:
        return {}
    if category not in allowed_categories:
        category = ''
    if room_category not in allowed_rooms:
        room_category = ''
    if room_category and category != HotelMediaItem.CATEGORY_ROOMS:
        room_category = ''
    tags = [
        str(tag).strip()[:40]
        for tag in (parsed.get('auto_tags') or [])
        if str(tag).strip()
    ][:5]
    return {
        'category': category,
        'room_category': room_category or None,
        'auto_tags': tags,
    }


def _classify_social_content_with_ai(title: str = '', caption: str = '') -> dict:
    """Classify Instagram text by meaning with a constrained model prompt."""
    text = f'{title}\n{caption}'.strip()
    if not text:
        return {}
    try:
        from apps.leads.ai_service import ai_service

        if not ai_service.is_configured():
            return {}
        prompt = (
            'Classify this hotel Instagram content by meaning, not keyword matching. '
            'Return JSON only with keys category, room_category, auto_tags, confidence. '
            'category must be one of rooms, cafeteria, pool, spa, conference, exterior, lobby, other. '
            'room_category must be one of standard_queen, standard_twin, comfort, family, or empty. '
            'Set an exact room_category only when the text itself clearly identifies it; '
            'a generic room/interior is not enough. Use an empty category when uncertain. '
            'auto_tags must be a short array. confidence is 0..1.'
        )
        kwargs = {
            'model': ai_service._model,
            'messages': [
                {'role': 'system', 'content': prompt},
                {'role': 'user', 'content': text[:2000]},
            ],
            'temperature': 0,
            'max_tokens': 300,
            'timeout': 20,
        }
        if getattr(ai_service, 'provider', None) != 'gemini':
            kwargs['response_format'] = {'type': 'json_object'}
        response = ai_service.client.chat.completions.create(**kwargs)
        raw = (response.choices[0].message.content or '').strip()
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
        parsed = json.loads(raw)
        return _normalize_social_labels(parsed)
    except Exception as exc:
        logger.warning('Could not classify Instagram content semantically: %s', exc)
        return {}


def _classify_social_content_batch(records: list[dict]) -> dict[str, dict]:
    """Classify a sync page in one semantic model request."""
    inputs = [
        {
            'id': str(record.get('id') or ''),
            'caption': str(record.get('caption') or '')[:2000],
        }
        for record in records
        if record.get('id') and str(record.get('caption') or '').strip()
    ]
    if not inputs:
        return {}
    try:
        from apps.leads.ai_service import ai_service

        if not ai_service.is_configured():
            return {}
        prompt = (
            'Classify each hotel Instagram item by its full meaning, never by a keyword rule. '
            'Return JSON only: {"items":[{"id":"input id","category":"","room_category":"",'
            '"auto_tags":[],"confidence":0.0}]}. '
            'category: rooms, cafeteria, pool, spa, conference, exterior, lobby, other, or empty. '
            'room_category: standard_queen, standard_twin, comfort, family, or empty. '
            'Use an exact room_category only when the caption itself clearly identifies it. '
            'A generic room or interior is insufficient. Preserve every input id exactly.'
        )
        kwargs = {
            'model': ai_service._model,
            'messages': [
                {'role': 'system', 'content': prompt},
                {'role': 'user', 'content': json.dumps(inputs, ensure_ascii=False)},
            ],
            'temperature': 0,
            'max_tokens': min(3500, 200 + len(inputs) * 130),
            'timeout': 30,
        }
        if getattr(ai_service, 'provider', None) != 'gemini':
            kwargs['response_format'] = {'type': 'json_object'}
        response = ai_service.client.chat.completions.create(**kwargs)
        raw = (response.choices[0].message.content or '').strip()
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
        parsed = json.loads(raw)
        allowed_ids = {item['id'] for item in inputs}
        return {
            item_id: labels
            for item in (parsed.get('items') or [])
            if (item_id := str(item.get('id') or '')) in allowed_ids
            and (labels := _normalize_social_labels(item))
        }
    except Exception as exc:
        logger.warning('Could not batch-classify Instagram content semantically: %s', exc)
        return {}


def _file_path(file_field) -> str | None:
    if not file_field:
        return None
    try:
        return file_field.path
    except (NotImplementedError, ValueError):
        if default_storage.exists(file_field.name):
            try:
                return default_storage.path(file_field.name)
            except NotImplementedError:
                return None
    return None


def _create_fingerprints(records: list[dict], *, organization, hotel_media_item=None, hotel_media_photo=None, social_content_item=None) -> int:
    created = 0
    for record in records:
        MediaFingerprint.objects.create(
            organization=organization,
            hotel_media_item=hotel_media_item,
            hotel_media_photo=hotel_media_photo,
            social_content_item=social_content_item,
            hash_kind=record['hash_kind'],
            hash_value=record['hash_value'],
            bit_length=record.get('bit_length') or 64,
            width=record.get('width'),
            height=record.get('height'),
            crop_label=record.get('crop_label', ''),
        )
        created += 1
    return created


def _fingerprints_from_remote_image_url(url: str) -> list[dict]:
    if not url:
        return []

    temp_path = ''
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        content_type = (response.headers.get('Content-Type') or '').split(';', 1)[0].lower()
        if content_type and not content_type.startswith('image/'):
            return []

        suffix = '.jpg'
        parsed_suffix = os.path.splitext(urlparse(url).path or '')[1]
        if parsed_suffix and len(parsed_suffix) <= 8:
            suffix = parsed_suffix

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(response.content)
            temp_path = tmp.name

        return compute_image_fingerprints(temp_path)
    except (requests.RequestException, FingerprintError, OSError) as exc:
        logger.info('Could not fingerprint remote social image %s: %s', url[:120], exc)
        return []
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                pass


def rebuild_hotel_media_item_fingerprints(item: HotelMediaItem) -> int:
    """Rebuild fingerprints for a curated hotel media item and its photo album."""
    MediaFingerprint.objects.filter(hotel_media_item=item, social_content_item__isnull=True).delete()
    MediaFingerprint.objects.filter(hotel_media_photo__item=item, social_content_item__isnull=True).delete()

    created = 0
    if item.media_type == HotelMediaItem.MEDIA_TYPE_PHOTO and item.file:
        path = _file_path(item.file)
        if path:
            try:
                created += _create_fingerprints(
                    compute_image_fingerprints(path),
                    organization=item.organization,
                    hotel_media_item=item,
                )
            except FingerprintError as exc:
                logger.warning('Could not fingerprint hotel media item %s: %s', item.id, exc)

    for photo in item.photos.all():
        created += rebuild_hotel_media_photo_fingerprints(photo)

    return created


def rebuild_hotel_media_photo_fingerprints(photo: HotelMediaPhoto) -> int:
    MediaFingerprint.objects.filter(hotel_media_photo=photo, social_content_item__isnull=True).delete()

    path = _file_path(photo.file)
    if not path:
        return 0

    try:
        return _create_fingerprints(
            compute_image_fingerprints(path),
            organization=photo.item.organization,
            hotel_media_item=photo.item,
            hotel_media_photo=photo,
        )
    except FingerprintError as exc:
        logger.warning('Could not fingerprint hotel media photo %s: %s', photo.id, exc)
        return 0


def rebuild_social_content_fingerprints(item: SocialContentItem) -> int:
    """Rebuild fingerprints for linked media or downloaded Instagram image previews."""
    created = 0
    if item.linked_media_item_id:
        MediaFingerprint.objects.filter(social_content_item=item).delete()
        source_item = item.linked_media_item
        if source_item.file:
            path = _file_path(source_item.file)
            if path:
                try:
                    created += _create_fingerprints(
                        compute_image_fingerprints(path),
                        organization=item.organization,
                        hotel_media_item=source_item,
                        social_content_item=item,
                    )
                except FingerprintError as exc:
                    logger.warning('Could not fingerprint linked social content %s: %s', item.id, exc)
        for photo in source_item.photos.all():
            path = _file_path(photo.file)
            if not path:
                continue
            try:
                created += _create_fingerprints(
                    compute_image_fingerprints(path),
                    organization=item.organization,
                    hotel_media_item=source_item,
                    hotel_media_photo=photo,
                    social_content_item=item,
                )
            except FingerprintError as exc:
                logger.warning('Could not fingerprint linked social photo %s: %s', photo.id, exc)
        return created

    records = []
    for url in (item.thumbnail_url, item.media_url):
        records = _fingerprints_from_remote_image_url(url)
        if records:
            break

    if records:
        MediaFingerprint.objects.filter(social_content_item=item).delete()
        created = _create_fingerprints(
            records,
            organization=item.organization,
            social_content_item=item,
        )
    else:
        existing_count = MediaFingerprint.objects.filter(social_content_item=item).count()
        if existing_count > 0:
            logger.info('Instagram URLs expired for SocialContentItem %s, but keeping %s existing fingerprints.', item.id, existing_count)
            created = existing_count
        else:
            logger.warning('Could not fetch fingerprints for SocialContentItem %s and no existing fingerprints found.', item.id)

    return created


def upsert_social_content_from_instagram_payload(
    *,
    organization,
    external_id: str,
    content_type: str = SocialContentItem.TYPE_UNKNOWN,
    title: str = '',
    caption: str = '',
    media_url: str = '',
    thumbnail_url: str = '',
    permalink: str = '',
    posted_at=None,
    expires_at=None,
    metadata: dict | None = None,
    semantic_labels: dict | None = None,
    source: str = SocialContentItem.SOURCE_AUTO_SYNC,
) -> SocialContentItem:
    """Create/update social content from sync or webhook data without manager labels."""
    inferred = semantic_labels or {}
    item = SocialContentItem.objects.filter(
        organization=organization,
        platform=SocialContentItem.PLATFORM_INSTAGRAM,
        external_id=external_id,
    ).first()

    if item:
        if item.status == SocialContentItem.STATUS_DELETED:
            return item

        update_fields = ['last_synced_at']
        item.last_synced_at = timezone.now()

        if content_type and content_type != SocialContentItem.TYPE_UNKNOWN and item.content_type != content_type:
            item.content_type = content_type
            update_fields.append('content_type')

        if title and item.title != title[:255]:
            item.title = title[:255]
            update_fields.append('title')

        if caption and item.caption != caption:
            item.caption = caption
            update_fields.append('caption')

        if media_url and item.media_url != media_url:
            item.media_url = media_url
            update_fields.append('media_url')

        if thumbnail_url and item.thumbnail_url != thumbnail_url:
            item.thumbnail_url = thumbnail_url
            update_fields.append('thumbnail_url')

        if permalink and item.permalink != permalink:
            item.permalink = permalink
            update_fields.append('permalink')

        if expires_at and item.expires_at != expires_at:
            item.expires_at = expires_at
            update_fields.append('expires_at')

        if posted_at and item.posted_at != posted_at:
            item.posted_at = posted_at
            update_fields.append('posted_at')

        if metadata:
            item.metadata = metadata
            update_fields.append('metadata')

        if not item.category and inferred.get('category'):
            item.category = inferred['category']
            update_fields.append('category')
        if not item.room_category and inferred.get('room_category'):
            item.room_category = inferred['room_category']
            update_fields.append('room_category')
        if not item.auto_tags and inferred.get('auto_tags'):
            item.auto_tags = inferred['auto_tags']
            update_fields.append('auto_tags')

        should_reactivate = (
            item.status == SocialContentItem.STATUS_EXPIRED
            and (
                (expires_at and expires_at > timezone.now())
                or content_type == SocialContentItem.TYPE_HIGHLIGHT
                or source == SocialContentItem.SOURCE_WEBHOOK
            )
        )
        if should_reactivate:
            item.status = SocialContentItem.STATUS_ACTIVE
            item.is_active = True
            update_fields.extend(['status', 'is_active'])

        item.save(update_fields=update_fields)
        return item
    else:
        item = SocialContentItem.objects.create(
            organization=organization,
            platform=SocialContentItem.PLATFORM_INSTAGRAM,
            external_id=external_id,
            content_type=content_type or SocialContentItem.TYPE_UNKNOWN,
            title=title[:255] if title else '',
            caption=caption or '',
            media_url=media_url or '',
            thumbnail_url=thumbnail_url or '',
            permalink=permalink or '',
            posted_at=posted_at,
            expires_at=expires_at,
            last_synced_at=timezone.now(),
            metadata=metadata or {},
            category=inferred.get('category') or '',
            room_category=inferred.get('room_category'),
            auto_tags=inferred.get('auto_tags') or [],
            source=source,
            status=SocialContentItem.STATUS_ACTIVE,
            is_active=True,
            review_status=SocialContentItem.REVIEW_NEEDS_REVIEW,
        )
        return item


def external_id_from_url(value: str) -> str:
    """Best-effort stable key for external media URLs when Meta does not provide an ID."""
    parsed = urlparse(value or '')
    return (parsed.path or value or '').strip('/')[:128]


def _parse_instagram_datetime(value: str | None):
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed and timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone=datetime_timezone.utc)
    return parsed


def _instagram_content_type(record: dict, *, default: str = SocialContentItem.TYPE_POST) -> str:
    product_type = str(record.get('media_product_type') or '').upper()
    media_type = str(record.get('media_type') or '').upper()
    if product_type == 'REELS':
        return SocialContentItem.TYPE_REEL
    if default == SocialContentItem.TYPE_STORY:
        return SocialContentItem.TYPE_STORY
    if media_type == 'VIDEO' and product_type == 'REELS':
        return SocialContentItem.TYPE_REEL
    return default


def _instagram_get(url: str, *, token: str, params: dict | None = None) -> dict:
    query = dict(params or {})
    query['access_token'] = token
    response = requests.get(url, params=query, timeout=20)
    response.raise_for_status()
    return response.json()


def _instagram_records(url: str, *, token: str, params: dict, max_pages: int = 10):
    """Yield paginated Graph API records instead of silently stopping at 50."""
    payload = _instagram_get(url, token=token, params=params)
    pages = 0
    while payload and pages < max_pages:
        pages += 1
        yield from payload.get('data', [])
        next_url = ((payload.get('paging') or {}).get('next') or '').strip()
        if not next_url:
            break
        response = requests.get(next_url, timeout=20)
        response.raise_for_status()
        payload = response.json()


def sync_instagram_social_content(*, organization=None) -> dict:
    """Best-effort sync of posts/reels and currently active stories into SocialContentItem."""
    from apps.leads.models import InstagramConnection

    connections = InstagramConnection.objects.filter(access_token__gt='')
    if organization is not None:
        connections = connections.filter(organization=organization)

    result = {
        'connections': 0,
        'items_synced': 0,
        'stories_synced': 0,
        'stories_expired': 0,
        'errors': [],
        'highlights_supported': False,
        'sync_scope': 'posts_reels_and_active_stories',
    }

    fields = ','.join([
        'id',
        'caption',
        'media_type',
        'media_product_type',
        'media_url',
        'thumbnail_url',
        'permalink',
        'timestamp',
    ])

    for conn in connections.select_related('organization').iterator():
        result['connections'] += 1
        token = conn.access_token
        user_id = conn.instagram_user_id
        if not token or not user_id:
            continue

        base = f'https://graph.instagram.com/v25.0/{user_id}'
        try:
            media_records = list(_instagram_records(
                f'{base}/media',
                token=token,
                params={'fields': fields, 'limit': 50},
            ))
            unlabeled_records = []
            for record in media_records:
                external_id = str(record.get('id') or '').strip()
                existing = SocialContentItem.objects.filter(
                    organization=conn.organization,
                    platform=SocialContentItem.PLATFORM_INSTAGRAM,
                    external_id=external_id,
                ).only('category', 'room_category').first()
                if external_id and (
                    not existing or (not existing.category and not existing.room_category)
                ):
                    unlabeled_records.append(record)
            semantic_by_id = _classify_social_content_batch(unlabeled_records)

            for record in media_records:
                external_id = str(record.get('id') or '').strip()
                if not external_id:
                    continue
                upsert_social_content_from_instagram_payload(
                    organization=conn.organization,
                    external_id=external_id,
                    content_type=_instagram_content_type(record),
                    caption=record.get('caption') or '',
                    media_url=record.get('media_url') or '',
                    thumbnail_url=record.get('thumbnail_url') or '',
                    permalink=record.get('permalink') or '',
                    posted_at=_parse_instagram_datetime(record.get('timestamp')),
                    metadata=record,
                    semantic_labels=semantic_by_id.get(external_id, {}),
                    source=SocialContentItem.SOURCE_AUTO_SYNC,
                )
                result['items_synced'] += 1
        except Exception as exc:
            result['errors'].append(f'posts/reels sync failed for @{conn.instagram_username or user_id}: {exc}')

        active_story_ids = set()
        try:
            story_fields = ','.join([
                'id',
                'media_type',
                'media_url',
                'thumbnail_url',
                'timestamp',
            ])
            try:
                story_records = list(_instagram_records(
                    f'{base}/stories',
                    token=token,
                    params={'fields': story_fields, 'limit': 50},
                ))
            except Exception:
                # Some account/media combinations reject optional thumbnail data.
                # Retry with the stable core fields instead of failing the whole sync.
                story_records = list(_instagram_records(
                    f'{base}/stories',
                    token=token,
                    params={
                        'fields': 'id,media_type,media_url,timestamp',
                        'limit': 50,
                    },
                ))
            for record in story_records:
                external_id = str(record.get('id') or '').strip()
                if not external_id:
                    continue
                active_story_ids.add(external_id)
                posted_at = _parse_instagram_datetime(record.get('timestamp'))
                expires_at = posted_at + timedelta(hours=24) if posted_at else None
                upsert_social_content_from_instagram_payload(
                    organization=conn.organization,
                    external_id=external_id,
                    content_type=SocialContentItem.TYPE_STORY,
                    caption=record.get('caption') or '',
                    media_url=record.get('media_url') or '',
                    thumbnail_url=record.get('thumbnail_url') or '',
                    permalink=record.get('permalink') or '',
                    posted_at=posted_at,
                    expires_at=expires_at,
                    metadata=record,
                    semantic_labels=_classify_social_content_with_ai(
                        caption=record.get('caption') or '',
                    ),
                    source=SocialContentItem.SOURCE_AUTO_SYNC,
                )
                result['stories_synced'] += 1
        except Exception as exc:
            result['errors'].append(f'stories sync failed for @{conn.instagram_username or user_id}: {exc}')

        story_qs = SocialContentItem.objects.filter(
            organization=conn.organization,
            platform=SocialContentItem.PLATFORM_INSTAGRAM,
            content_type=SocialContentItem.TYPE_STORY,
            status=SocialContentItem.STATUS_ACTIVE,
        )
        if active_story_ids:
            story_qs = story_qs.exclude(external_id__in=active_story_ids)
        now = timezone.now()
        expired_count = story_qs.filter(
            Q(expires_at__lt=now)
            | Q(expires_at__isnull=True, last_synced_at__lt=now - timedelta(hours=25))
        ).update(
            status=SocialContentItem.STATUS_EXPIRED,
            is_active=False,
            last_synced_at=now,
        )
        result['stories_expired'] += expired_count

    return result
