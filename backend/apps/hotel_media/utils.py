import io
import logging

from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)

# Telegram Bot API photo limits
_TELEGRAM_TARGET_BYTES = 4 * 1024 * 1024  # 4 MB target after compression
_TELEGRAM_MAX_DIMENSION = 2560            # max side length in pixels


def compress_image_for_telegram(file_obj, filename: str = 'photo.jpg') -> ContentFile:
    """
    Compress an uploaded image so it is ready for Telegram delivery.

    Resizes to max 2560 px on any side, then JPEG-compresses to ≤ 4 MB
    at progressively lower quality (85 → 40). Returns a Django ContentFile
    suitable for passing directly to a FileField on save.

    Falls back to the original file content if Pillow is unavailable or the
    file cannot be opened as an image.

    Args:
        file_obj: Any file-like object (UploadedFile, open file, BytesIO).
        filename:  Desired output filename (extension changed to .jpg).

    Returns:
        ContentFile with compressed JPEG bytes.
    """
    try:
        from PIL import Image

        file_obj.seek(0)
        with Image.open(file_obj) as img:
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')

            max_dim = max(img.width, img.height)
            if max_dim > _TELEGRAM_MAX_DIMENSION:
                scale = _TELEGRAM_MAX_DIMENSION / max_dim
                new_size = (int(img.width * scale), int(img.height * scale))
                img = img.resize(new_size, Image.LANCZOS)

            quality = 85
            while quality >= 40:
                buf = io.BytesIO()
                img.save(buf, format='JPEG', quality=quality, optimize=True)
                if buf.tell() <= _TELEGRAM_TARGET_BYTES:
                    break
                quality -= 10

            buf.seek(0)
            base_name = filename.rsplit('.', 1)[0]
            return ContentFile(buf.read(), name=f"{base_name}.jpg")

    except Exception as exc:
        logger.warning(f"Could not compress image '{filename}': {exc}. Storing original.")
        file_obj.seek(0)
        return ContentFile(file_obj.read(), name=filename)
