from __future__ import annotations

import logging
import os
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
    source: str = SocialContentItem.SOURCE_AUTO_SYNC,
) -> SocialContentItem:
    """Create/update social content from sync or webhook data without manager labels."""
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

        if posted_at and not item.posted_at:
            item.posted_at = posted_at
            update_fields.append('posted_at')

        if metadata:
            item.metadata = metadata
            update_fields.append('metadata')

        if item.status == SocialContentItem.STATUS_EXPIRED and expires_at and expires_at > timezone.now():
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
            media_payload = _instagram_get(f'{base}/media', token=token, params={'fields': fields, 'limit': 50})
            for record in media_payload.get('data', []):
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
                    source=SocialContentItem.SOURCE_AUTO_SYNC,
                )
                result['items_synced'] += 1
        except Exception as exc:
            result['errors'].append(f'posts/reels sync failed for @{conn.instagram_username or user_id}: {exc}')

        active_story_ids = set()
        try:
            stories_payload = _instagram_get(f'{base}/stories', token=token, params={'fields': fields, 'limit': 50})
            for record in stories_payload.get('data', []):
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
