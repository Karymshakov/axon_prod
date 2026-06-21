from tempfile import TemporaryDirectory
from io import BytesIO
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from PIL import Image, ImageDraw

from apps.organizations.models import Organization

from .fingerprints import compute_image_fingerprints
from .models import HotelMediaItem, MediaFingerprint, SocialContentItem


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

    def test_unrelated_market_photo_does_not_match_room_media(self):
        from apps.leads.services.media_context import find_best_fingerprint_context

        with TemporaryDirectory() as temp_dir:
            room_path = f'{temp_dir}/comfort.jpg'
            market_path = f'{temp_dir}/market.jpg'

            room = Image.new('RGB', (470, 702), '#d8c3a2')
            draw = ImageDraw.Draw(room)
            draw.rectangle((40, 80, 430, 430), fill='#f7f1e8')
            draw.rectangle((90, 420, 450, 610), fill='#7d9b78')
            draw.ellipse((110, 250, 270, 410), fill='#b9825f')
            room.save(room_path)

            item = HotelMediaItem.objects.create(
                organization=self.org,
                title='Comfort',
                category=HotelMediaItem.CATEGORY_ROOMS,
                room_category=HotelMediaItem.ROOM_CATEGORY_COMFORT,
                media_type=HotelMediaItem.MEDIA_TYPE_PHOTO,
            )
            for record in compute_image_fingerprints(room_path):
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

            market = Image.new('RGB', (640, 900), '#9aa0a4')
            draw = ImageDraw.Draw(market)
            draw.polygon([(0, 180), (640, 80), (640, 210), (0, 300)], fill='#2f3338')
            draw.rectangle((0, 420, 640, 900), fill='#777d82')
            for x in range(20, 640, 90):
                draw.rectangle((x, 250, x + 55, 370), fill='#3d454b')
                draw.rectangle((x + 8, 375, x + 48, 430), fill='#d0b46d')
            draw.line((80, 410, 260, 900), fill='#3b3b3b', width=20)
            draw.rectangle((380, 250, 420, 350), fill='#1b1b1b')
            market.save(market_path)

            context = find_best_fingerprint_context(market_path, organization=self.org)

        self.assertIsNone(context)


class SocialContentFingerprintTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            email='social_hash@example.com',
            password='password123',
            name='Social Hash Owner',
            role='admin',
        )
        self.org = Organization.objects.create(name='Social Hash Org', slug='social-hash-org', owner=self.owner)

    @patch('apps.hotel_media.services.requests.get')
    def test_rebuild_social_content_fingerprints_downloads_remote_image(self, get_mock):
        from apps.hotel_media.services import rebuild_social_content_fingerprints

        image = Image.new('RGB', (480, 720), '#1f7cb8')
        draw = ImageDraw.Draw(image)
        draw.rectangle((40, 260, 440, 620), fill='#33a8d8')
        draw.rectangle((0, 0, 480, 160), fill='#222222')
        buffer = BytesIO()
        image.save(buffer, format='JPEG')

        response = Mock()
        response.headers = {'Content-Type': 'image/jpeg'}
        response.content = buffer.getvalue()
        response.raise_for_status.return_value = None
        get_mock.return_value = response

        item = SocialContentItem.objects.create(
            organization=self.org,
            platform=SocialContentItem.PLATFORM_INSTAGRAM,
            external_id='pool-story',
            content_type=SocialContentItem.TYPE_STORY,
            status=SocialContentItem.STATUS_ACTIVE,
            review_status=SocialContentItem.REVIEW_REVIEWED,
            title='Pool story',
            category=HotelMediaItem.CATEGORY_POOL,
            media_url='https://cdn.example.test/pool.jpg',
        )

        created = rebuild_social_content_fingerprints(item)

        self.assertGreater(created, 0)
        self.assertTrue(MediaFingerprint.objects.filter(social_content_item=item).exists())
