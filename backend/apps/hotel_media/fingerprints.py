from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError


HASH_SIZE = 8
PHASH_HIGHFREQ_FACTOR = 4


class FingerprintError(Exception):
    """Raised when an image cannot be fingerprinted."""


def _bits_to_hex(bits: Iterable[bool]) -> tuple[str, int]:
    bit_list = [1 if bit else 0 for bit in bits]
    if not bit_list:
        return '', 0

    value = 0
    for bit in bit_list:
        value = (value << 1) | bit

    bit_length = len(bit_list)
    width = (bit_length + 3) // 4
    return f'{value:0{width}x}', bit_length


def _grayscale(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.exif_transpose(image).convert('L').resize(size, Image.Resampling.LANCZOS)


def _center_crop(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image)
    width, height = image.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    return image.crop((left, top, left + side, top + side))


def _relative_crop(image: Image.Image, box: tuple[float, float, float, float]) -> Image.Image | None:
    width, height = image.size
    left = max(0, min(width - 1, round(width * box[0])))
    top = max(0, min(height - 1, round(height * box[1])))
    right = max(left + 1, min(width, round(width * box[2])))
    bottom = max(top + 1, min(height, round(height * box[3])))
    if right - left < 48 or bottom - top < 48:
        return None
    return image.crop((left, top, right, bottom))


def _candidate_screenshot_crops(image: Image.Image) -> list[tuple[str, Image.Image]]:
    """Regions that usually isolate reposted Instagram/story media inside screenshots."""
    image = ImageOps.exif_transpose(image)
    width, height = image.size
    crops: list[tuple[str, Image.Image]] = []
    seen: set[tuple[int, int, int, int]] = set()

    regions = [
        ('center_80', (0.10, 0.10, 0.90, 0.90)),
        ('story_body', (0.03, 0.10, 0.97, 0.88)),
        ('story_body_tight', (0.07, 0.13, 0.93, 0.84)),
        ('post_media', (0.00, 0.12, 1.00, 0.78)),
        ('post_media_tight', (0.04, 0.16, 0.96, 0.72)),
        ('upper_media', (0.00, 0.08, 1.00, 0.68)),
        ('middle_media', (0.00, 0.20, 1.00, 0.82)),
    ]
    if height > width * 1.45:
        regions.extend([
            ('portrait_content', (0.00, 0.08, 1.00, 0.84)),
            ('portrait_content_lower', (0.00, 0.15, 1.00, 0.91)),
        ])
    if width > height * 1.25:
        regions.extend([
            ('landscape_left', (0.00, 0.06, 0.72, 0.94)),
            ('landscape_center', (0.14, 0.06, 0.86, 0.94)),
            ('landscape_right', (0.28, 0.06, 1.00, 0.94)),
        ])

    for label, box in regions:
        crop = _relative_crop(image, box)
        if crop is None:
            continue
        key = crop.getbbox() or (0, 0, crop.size[0], crop.size[1])
        signature = (crop.size[0], crop.size[1], *key)
        if signature in seen:
            continue
        seen.add(signature)
        crops.append((label, crop))

    center = _center_crop(image)
    crops.append(('center_square', center))
    return crops


@lru_cache(maxsize=8)
def _dct_matrix(size: int) -> np.ndarray:
    n = np.arange(size)
    k = n.reshape((size, 1))
    return np.cos(np.pi * (n + 0.5) * k / size)


def average_hash(image: Image.Image, hash_size: int = HASH_SIZE) -> tuple[str, int]:
    pixels = np.asarray(_grayscale(image, (hash_size, hash_size)), dtype=np.float32)
    avg = pixels.mean()
    return _bits_to_hex(pixels.flatten() > avg)


def difference_hash(image: Image.Image, hash_size: int = HASH_SIZE) -> tuple[str, int]:
    pixels = np.asarray(_grayscale(image, (hash_size + 1, hash_size)), dtype=np.float32)
    diff = pixels[:, 1:] > pixels[:, :-1]
    return _bits_to_hex(diff.flatten())


def perceptual_hash(
    image: Image.Image,
    hash_size: int = HASH_SIZE,
    highfreq_factor: int = PHASH_HIGHFREQ_FACTOR,
) -> tuple[str, int]:
    size = hash_size * highfreq_factor
    pixels = np.asarray(_grayscale(image, (size, size)), dtype=np.float32)

    matrix = _dct_matrix(size)
    dct = matrix @ pixels @ matrix.T
    low_freq = dct[:hash_size, :hash_size]

    # Ignore the DC term when computing the median so overall brightness changes
    # do not dominate the hash.
    flattened = low_freq.flatten()
    median = np.median(flattened[1:]) if flattened.size > 1 else np.median(flattened)
    return _bits_to_hex(flattened > median)


def color_hash(image: Image.Image, hash_size: int = HASH_SIZE) -> tuple[str, int]:
    rgb = ImageOps.exif_transpose(image).convert('RGB').resize((hash_size, hash_size), Image.Resampling.LANCZOS)
    pixels = np.asarray(rgb, dtype=np.float32)
    channel_means = pixels.reshape((-1, 3)).mean(axis=0)
    bits = []
    for pixel in pixels.reshape((-1, 3)):
        bits.extend(pixel > channel_means)
    return _bits_to_hex(bits)


def compute_image_fingerprints(image_path: str | Path, *, include_screenshot_regions: bool = False) -> list[dict]:
    try:
        with Image.open(image_path) as image:
            image = ImageOps.exif_transpose(image)
            width, height = image.size
            center = _center_crop(image)

            fingerprints = []
            for kind, func, source_image, crop_label in [
                ('phash', perceptual_hash, image, ''),
                ('dhash', difference_hash, image, ''),
                ('ahash', average_hash, image, ''),
                ('center_phash', perceptual_hash, center, 'center'),
                ('colorhash', color_hash, image, ''),
            ]:
                hash_value, bit_length = func(source_image)
                fingerprints.append({
                    'hash_kind': kind,
                    'hash_value': hash_value,
                    'bit_length': bit_length,
                    'width': width,
                    'height': height,
                    'crop_label': crop_label,
                })
            if include_screenshot_regions:
                for crop_label, crop in _candidate_screenshot_crops(image):
                    for kind, func in [
                        ('phash', perceptual_hash),
                        ('dhash', difference_hash),
                        ('ahash', average_hash),
                    ]:
                        hash_value, bit_length = func(crop)
                        fingerprints.append({
                            'hash_kind': kind,
                            'hash_value': hash_value,
                            'bit_length': bit_length,
                            'width': crop.size[0],
                            'height': crop.size[1],
                            'crop_label': crop_label,
                        })
            return fingerprints
    except (FileNotFoundError, OSError, UnidentifiedImageError) as exc:
        raise FingerprintError(str(exc)) from exc


def hamming_distance(left_hex: str, right_hex: str) -> int:
    if not left_hex or not right_hex:
        return 10**9
    left = int(left_hex, 16)
    right = int(right_hex, 16)
    return (left ^ right).bit_count()
