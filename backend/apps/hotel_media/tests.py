from tempfile import TemporaryDirectory
from io import BytesIO
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from PIL import Image, ImageDraw

from apps.organizations.models import Organization

from .fingerprints import compute_image_fingerprints
from .models import (
    HotelMediaItem,
    MediaFingerprint,
    SocialAutomationDelivery,
    SocialContentItem,
)


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

    def test_single_strong_hash_collision_is_not_treated_as_a_match(self):
        from apps.leads.services.media_context import find_best_fingerprint_context

        with TemporaryDirectory() as temp_dir:
            trash_path = f'{temp_dir}/trash.jpg'
            trash = Image.new('RGB', (640, 480), '#707070')
            draw = ImageDraw.Draw(trash)
            for index in range(16):
                x = (index % 4) * 160
                y = (index // 4) * 120
                draw.rectangle((x + 8, y + 8, x + 145, y + 105), fill=(40 + index * 9, 80, 120))
            trash.save(trash_path)

            item = HotelMediaItem.objects.create(
                organization=self.org,
                title='Events',
                category=HotelMediaItem.CATEGORY_CONFERENCE,
                media_type=HotelMediaItem.MEDIA_TYPE_PHOTO,
            )
            exact_phash = next(
                record for record in compute_image_fingerprints(trash_path)
                if record['hash_kind'] == 'phash'
            )
            MediaFingerprint.objects.create(
                organization=self.org,
                hotel_media_item=item,
                hash_kind='phash',
                hash_value=exact_phash['hash_value'],
                bit_length=exact_phash['bit_length'],
                width=exact_phash['width'],
                height=exact_phash['height'],
            )

            context = find_best_fingerprint_context(trash_path, organization=self.org)

        self.assertIsNone(context)

    def test_story_screenshot_matches_social_content_with_hash_consensus(self):
        from apps.leads.services.media_context import find_best_fingerprint_context

        with TemporaryDirectory() as temp_dir:
            pool_path = f'{temp_dir}/pool_story.jpg'
            screenshot_path = f'{temp_dir}/pool_story_screenshot.jpg'

            pool = Image.new('RGB', (470, 702), '#17232d')
            draw = ImageDraw.Draw(pool)
            draw.rectangle((0, 260, 470, 702), fill='#168ec0')
            for x in range(30, 470, 90):
                draw.line((x, 270, x - 40, 700), fill='#f4f4f4', width=5)
            for x in range(70, 430, 60):
                draw.ellipse((x, 400, x + 42, 470), fill='#b8835f')
            draw.text((95, 80), 'nomadcamp pool', fill='#ffffff')
            pool.save(pool_path)

            social = SocialContentItem.objects.create(
                organization=self.org,
                platform=SocialContentItem.PLATFORM_INSTAGRAM,
                external_id='pool-story-consensus',
                content_type=SocialContentItem.TYPE_STORY,
                status=SocialContentItem.STATUS_ACTIVE,
                review_status=SocialContentItem.REVIEW_REVIEWED,
                title='Pool',
                category=HotelMediaItem.CATEGORY_POOL,
            )
            for record in compute_image_fingerprints(pool_path):
                MediaFingerprint.objects.create(
                    organization=self.org,
                    social_content_item=social,
                    hash_kind=record['hash_kind'],
                    hash_value=record['hash_value'],
                    bit_length=record['bit_length'],
                    width=record['width'],
                    height=record['height'],
                    crop_label=record.get('crop_label', ''),
                )

            screenshot = Image.new('RGB', (500, 900), '#080b0f')
            screenshot.paste(pool, (15, 90))
            draw = ImageDraw.Draw(screenshot)
            draw.rectangle((0, 0, 500, 80), fill='#080b0f')
            draw.rectangle((0, 810, 500, 900), fill='#080b0f')
            screenshot.save(screenshot_path)

            context = find_best_fingerprint_context(screenshot_path, organization=self.org)

        self.assertIsNotNone(context)
        self.assertEqual(context['source'], 'social_content')
        self.assertEqual(context['category'], HotelMediaItem.CATEGORY_POOL)
        self.assertGreaterEqual(len(context['match_evidence']), 2)
        self.assertFalse(context['needs_clarification'])


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

    def test_webhook_upsert_reactivates_expired_story_for_highlight_matching(self):
        from apps.hotel_media.services import upsert_social_content_from_instagram_payload

        item = SocialContentItem.objects.create(
            organization=self.org,
            platform=SocialContentItem.PLATFORM_INSTAGRAM,
            external_id='expired-story-now-highlight',
            content_type=SocialContentItem.TYPE_STORY,
            status=SocialContentItem.STATUS_EXPIRED,
            is_active=False,
            review_status=SocialContentItem.REVIEW_REVIEWED,
            title='Pool story',
            category=HotelMediaItem.CATEGORY_POOL,
        )

        saved = upsert_social_content_from_instagram_payload(
            organization=self.org,
            external_id='expired-story-now-highlight',
            content_type=SocialContentItem.TYPE_HIGHLIGHT,
            media_url='https://cdn.example.test/pool-highlight.jpg',
            source=SocialContentItem.SOURCE_WEBHOOK,
        )
        item.refresh_from_db()

        self.assertEqual(saved.id, item.id)
        self.assertTrue(item.is_active)
        self.assertEqual(item.status, SocialContentItem.STATUS_ACTIVE)
        self.assertEqual(item.content_type, SocialContentItem.TYPE_HIGHLIGHT)

    @patch('apps.hotel_media.services.upsert_social_content_from_instagram_payload')
    @patch('apps.hotel_media.services._instagram_records')
    def test_story_sync_retries_with_core_fields(self, records_mock, upsert_mock):
        from apps.hotel_media.services import sync_instagram_social_content
        from apps.leads.models import InstagramConnection

        InstagramConnection.objects.create(
            organization=self.org,
            instagram_user_id='ig-business-1',
            instagram_username='hotel',
            access_token='token',
        )

        def records_side_effect(url, *, token, params):
            if url.endswith('/media'):
                return iter([])
            if 'thumbnail_url' in params['fields']:
                raise RuntimeError('Unsupported field')
            return iter([{
                'id': 'story-1',
                'media_type': 'IMAGE',
                'media_url': 'https://cdn.example.test/story.jpg',
                'timestamp': '2026-07-27T10:00:00+0000',
            }])

        records_mock.side_effect = records_side_effect

        result = sync_instagram_social_content(organization=self.org)

        self.assertEqual(result['stories_synced'], 1)
        self.assertEqual(result['errors'], [])
        self.assertEqual(upsert_mock.call_args.kwargs['external_id'], 'story-1')


class InstagramCommentAutomationTests(TransactionTestCase):
    def setUp(self):
        task_patcher = patch(
            'apps.hotel_media.tasks.rebuild_social_content_fingerprints_task.apply_async'
        )
        task_patcher.start()
        self.addCleanup(task_patcher.stop)
        owner = get_user_model().objects.create_user(
            email='campaign-automation@example.com',
            password='password123',
            name='Campaign Owner',
            role='admin',
        )
        self.org = Organization.objects.create(
            name='Campaign Hotel',
            slug='campaign-hotel',
            owner=owner,
        )
        self.item = SocialContentItem.objects.create(
            organization=self.org,
            platform=SocialContentItem.PLATFORM_INSTAGRAM,
            external_id='media-123',
            content_type=SocialContentItem.TYPE_POST,
            status=SocialContentItem.STATUS_ACTIVE,
            automation_enabled=True,
            automation_trigger=SocialContentItem.AUTOMATION_COMMENT_EXACT,
            automation_trigger_values=['Хочу'],
            automation_reply_ru='Отправили подробности в директ.',
        )

    @patch('apps.leads.instagram_views.instagram_service.send_private_reply_to_comment')
    def test_exact_comment_sends_one_private_reply_without_creating_lead(self, send_mock):
        from apps.leads.instagram_views import _process_instagram_comment_change
        from apps.leads.models import Lead

        send_mock.return_value = {
            'message_id': 'reply-mid-1',
            'recipient_id': 'ig-user-1',
        }
        payload = {
            'field': 'comments',
            'value': {
                'id': 'comment-1',
                'text': '  ХОЧУ  ',
                'from': {'id': 'ig-user-1'},
                'media': {'id': 'media-123'},
            },
        }

        _process_instagram_comment_change(payload, self.org.id)
        _process_instagram_comment_change(payload, self.org.id)

        self.assertEqual(send_mock.call_count, 1)
        self.assertEqual(SocialAutomationDelivery.objects.count(), 1)
        self.assertEqual(SocialAutomationDelivery.objects.get().status, 'sent')
        self.assertEqual(Lead.objects.filter(organization=self.org).count(), 0)

    def test_instagram_entry_changes_accepts_nested_and_direct_meta_shapes(self):
        from apps.leads.instagram_views import _instagram_entry_changes

        nested = {'changes': [{'field': 'comments', 'value': {'id': 'nested'}}]}
        direct = {'field': 'comments', 'value': {'id': 'direct'}}

        self.assertEqual(_instagram_entry_changes(nested), nested['changes'])
        self.assertEqual(
            _instagram_entry_changes(direct),
            [{'field': 'comments', 'value': {'id': 'direct'}}],
        )

    @patch('apps.leads.instagram_views.instagram_service.send_private_reply_to_comment')
    def test_failed_private_reply_can_retry_on_repeated_webhook(self, send_mock):
        from apps.leads.instagram_views import _process_instagram_comment_change

        payload = {
            'field': 'comments',
            'value': {
                'id': 'comment-retry',
                'text': 'Хочу',
                'from': {'id': 'ig-user-2'},
                'media': {'id': 'media-123'},
            },
        }
        send_mock.side_effect = [
            None,
            {'message_id': 'reply-mid-2', 'recipient_id': 'ig-user-2'},
        ]

        _process_instagram_comment_change(payload, self.org.id)
        _process_instagram_comment_change(payload, self.org.id)

        self.assertEqual(send_mock.call_count, 2)
        delivery = SocialAutomationDelivery.objects.get(external_event_id='comment-retry')
        self.assertEqual(delivery.status, SocialAutomationDelivery.STATUS_SENT)
