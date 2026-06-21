from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import TestCase
from PIL import Image, ImageDraw

from apps.organizations.models import Organization

from .fingerprints import compute_image_fingerprints
from .models import HotelMediaItem, MediaFingerprint


class ScreenshotFingerprintTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            email='hotel_media_hash@example.com',
            password='password123',
            name='Hash Owner',
            role='admin',
        )
        self.org = Organization.objects.create(name='Hash Org', slug='hash-org', owner=self.owner)

    def test_incoming_instagram_story_screenshot_matches_curated_photo_region(self):
        from apps.leads.services.media_context import find_best_fingerprint_context

        with TemporaryDirectory() as temp_dir:
            base_path = f'{temp_dir}/comfort.jpg'
            screenshot_path = f'{temp_dir}/story_screenshot.jpg'

            base = Image.new('RGB', (470, 702), '#d8c3a2')
            draw = ImageDraw.Draw(base)
            draw.rectangle((40, 80, 430, 430), fill='#f7f1e8')
            draw.rectangle((90, 420, 450, 610), fill='#7d9b78')
            draw.ellipse((110, 250, 270, 410), fill='#b9825f')
            draw.line((20, 660, 450, 610), fill='#5f5349', width=10)
            base.save(base_path)

            item = HotelMediaItem.objects.create(
                organization=self.org,
                title='Comfort',
                category=HotelMediaItem.CATEGORY_ROOMS,
                room_category=HotelMediaItem.ROOM_CATEGORY_COMFORT,
                media_type=HotelMediaItem.MEDIA_TYPE_PHOTO,
            )
            for record in compute_image_fingerprints(base_path):
                MediaFingerprint.objects.create(
                    organization=self.org,
                    hotel_media_item=item,
                    hash_kind=record['hash_kind'],
                    hash_value=record['hash_value'],
                    bit_length=record['bit_length'],
                    width=record['width'],
                    height=record['height'],
                    crop_label=record.get('crop_label', ''),
                )

            screenshot = Image.new('RGB', (500, 900), '#111111')
            screenshot.paste(base, (15, 90))
            draw = ImageDraw.Draw(screenshot)
            draw.rectangle((0, 0, 500, 80), fill='#050505')
            draw.rectangle((0, 810, 500, 900), fill='#050505')
            draw.text((24, 28), 'nomadcamp', fill='#ffffff')
            screenshot.save(screenshot_path)

            context = find_best_fingerprint_context(screenshot_path, organization=self.org)

        self.assertIsNotNone(context)
        self.assertEqual(context['source'], 'hotel_media')
        self.assertEqual(context['room_category'], HotelMediaItem.ROOM_CATEGORY_COMFORT)
        self.assertTrue(context.get('incoming_crop_label'))
