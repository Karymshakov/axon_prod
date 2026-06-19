import mimetypes
import os
import re
from urllib.parse import urlparse

from django.conf import settings


MEDIA_PLACEHOLDERS = {
    'photo': '[Изображение получено]',
    'video': '[Видео получено]',
    'audio': '[Аудио получено]',
    'document': '[Файл получен]',
}


def sanitize_media_id(value: str | int | None, fallback: str = 'media') -> str:
    raw = str(value or fallback)
    cleaned = re.sub(r'[^a-zA-Z0-9_\-]', '_', raw).strip('_')
    return cleaned or fallback


def extension_from_mime(mime_type: str | None, default: str) -> str:
    if not mime_type:
        return default

    ext = mimetypes.guess_extension(mime_type.split(';', 1)[0].strip())
    if ext == '.jpe':
        return '.jpg'
    return ext or default


def extension_from_filename(filename: str | None, mime_type: str | None, default: str) -> str:
    if filename:
        parsed_path = urlparse(filename).path
        ext = os.path.splitext(parsed_path)[1]
        if ext:
            return ext[:16]
    return extension_from_mime(mime_type, default)


def incoming_media_path(prefix: str, media_id: str | int | None, extension: str) -> tuple[str, str]:
    media_dir = os.path.join(settings.MEDIA_ROOT, 'incoming_media')
    os.makedirs(media_dir, exist_ok=True)

    safe_id = sanitize_media_id(media_id)
    safe_ext = extension if extension.startswith('.') else f'.{extension}'
    filename = f'{prefix}_{safe_id}{safe_ext}'
    return os.path.join(media_dir, filename), f'{settings.MEDIA_URL}incoming_media/{filename}'


def media_metadata(media_type: str, file_url: str, mime_type: str | None = None, filename: str | None = None) -> dict:
    metadata = {
        'media_type': media_type,
        'file_url': file_url,
    }
    if mime_type:
        metadata['mime_type'] = mime_type
    if filename:
        metadata['file_name'] = filename
    return metadata


def infer_media_type(mime_type: str | None = None, filename: str | None = None, fallback: str = 'photo') -> str:
    guessed_mime = mime_type
    if not guessed_mime and filename:
        guessed_mime, _ = mimetypes.guess_type(filename)

    if guessed_mime:
        if guessed_mime.startswith('image/'):
            return 'photo'
        if guessed_mime.startswith('video/'):
            return 'video'
        if guessed_mime.startswith('audio/'):
            return 'audio'

    return fallback


def is_media_only_activity_metadata(metadata: dict | None) -> bool:
    if not metadata or not metadata.get('media_type'):
        return False

    if metadata.get('ai_text') or metadata.get('visual_summary') or metadata.get('media_context'):
        return False

    text = str(metadata.get('text') or metadata.get('message') or '').strip()
    if not text:
        return True

    normalized_placeholders = {value.casefold() for value in MEDIA_PLACEHOLDERS.values()}
    return text.casefold() in normalized_placeholders


def activity_text_for_ai(metadata: dict | None, fallback: str = '') -> str:
    metadata = metadata or {}
    return str(
        metadata.get('ai_text')
        or metadata.get('visual_summary')
        or metadata.get('text')
        or metadata.get('message')
        or fallback
        or ''
    )
