from datetime import date
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.hotel_media.models import HotelMediaItem
from apps.organizations.models import Organization

from .models import AIConfig, Lead, LeadActivity, OutboundActionClaim


class DialogGuardTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(
            email='dialog-guards@example.com',
            password='password123',
            name='Dialog Guard Owner',
            role='admin',
        )
        self.org = Organization.objects.create(
            name='Dialog Guard Hotel',
            slug='dialog-guard-hotel',
            owner=owner,
        )
        AIConfig.objects.create(
            organization=self.org,
            proactive_outreach_enabled=True,
        )

    def test_relative_dates_use_bishkek_today_and_keep_checkout_after_checkin(self):
        from apps.leads.services.booking_tools import _infer_relative_booking_dates

        checkin, checkout = _infer_relative_booking_dates(
            'с завтра до пятницы',
            today=date(2026, 7, 27),
        )
        self.assertEqual(checkin, '2026-07-28')
        self.assertEqual(checkout, '2026-07-31')

        checkin, checkout = _infer_relative_booking_dates(
            'с завтра до понедельника',
            today=date(2026, 7, 27),
        )
        self.assertEqual(checkin, '2026-07-28')
        self.assertEqual(checkout, '2026-08-03')

    def test_family_context_uses_structured_extraction_not_message_keywords(self):
        from apps.leads.services.booking_tools import detect_family_context

        lead = Lead.objects.create(organization=self.org)
        LeadActivity.objects.create(
            organization=self.org,
            lead=lead,
            activity_type=LeadActivity.TYPE_TELEGRAM_RECEIVED,
            description='У нас маленький ребенок',
            metadata={'text': 'У нас маленький ребенок'},
        )
        self.assertFalse(detect_family_context(lead))

        lead.children_ages = [0.02]
        lead.infant_count = 1
        lead.save(update_fields=['children_ages', 'infant_count'])
        self.assertTrue(detect_family_context(lead))

    def test_non_sales_conversation_never_gets_followup(self):
        from apps.leads.agent_service import agent_service

        lead = Lead.objects.create(
            organization=self.org,
            source='instagram',
            instagram_user_id='story-guest',
            is_sales_lead=False,
            conversation_kind=Lead.CONVERSATION_COURTESY,
            origin_event_type='story_mention',
            followup_allowed=False,
            next_follow_up_at=timezone.now() + timezone.timedelta(minutes=10),
            next_follow_up_hint='stale',
        )

        agent_service.schedule_idle_or_promise_followup(
            lead,
            'Спасибо за отметку',
            [],
            0,
        )

        lead.refresh_from_db()
        self.assertIsNone(lead.next_follow_up_at)
        self.assertEqual(lead.next_follow_up_hint, '')

    def test_story_mention_is_a_distinct_event(self):
        from apps.leads.instagram_views import (
            _extract_instagram_content_context,
            _instagram_event_type,
        )

        message = {
            'attachments': [
                {
                    'type': 'story_mention',
                    'payload': {'id': 'story-123', 'url': 'https://example.test/story'},
                },
            ],
        }
        context = _extract_instagram_content_context({}, message, message['attachments'])

        self.assertEqual(context['story_id'], 'story-123')
        self.assertEqual(_instagram_event_type(message, context), 'story_mention')


class PhotoIdempotencyTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(
            email='photo-guards@example.com',
            password='password123',
            name='Photo Guard Owner',
            role='admin',
        )
        self.org = Organization.objects.create(
            name='Photo Guard Hotel',
            slug='photo-guard-hotel',
            owner=owner,
        )
        self.lead = Lead.objects.create(
            organization=self.org,
            source='instagram',
            instagram_user_id='ig-guest-1',
        )
        LeadActivity.objects.create(
            organization=self.org,
            lead=self.lead,
            activity_type=LeadActivity.TYPE_INSTAGRAM_RECEIVED,
            description='Есть фото стандарта?',
            metadata={'text': 'Есть фото стандарта?'},
        )

    @patch('apps.leads.instagram_service.instagram_service.send_image_url')
    def test_same_tool_call_sends_photos_only_once_for_one_guest_message(self, send_mock):
        from apps.leads.services.booking_tools import execute_get_room_images

        send_mock.return_value = {'message_id': 'mid-1'}
        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root, MEDIA_URL='/media/'):
                HotelMediaItem.objects.create(
                    organization=self.org,
                    title='Standard Twin',
                    description='Twin room',
                    category=HotelMediaItem.CATEGORY_ROOMS,
                    room_category=HotelMediaItem.ROOM_CATEGORY_STANDARD_TWIN,
                    media_type=HotelMediaItem.MEDIA_TYPE_PHOTO,
                    file=SimpleUploadedFile('standard.jpg', b'fake-jpeg-data', content_type='image/jpeg'),
                )

                first = execute_get_room_images({'categories': ['standard_twin']}, self.lead)
                second = execute_get_room_images({'categories': ['standard_twin']}, self.lead)

        self.assertTrue(first['sent'])
        self.assertTrue(second['already_sent_for_message'])
        self.assertEqual(send_mock.call_count, 1)
        self.assertEqual(
            OutboundActionClaim.objects.filter(lead=self.lead, action_type='room_images').count(),
            1,
        )
        self.assertEqual(
            LeadActivity.objects.filter(
                lead=self.lead,
                activity_type=LeadActivity.TYPE_INSTAGRAM_SENT,
                metadata__room_category='standard_twin',
            ).count(),
            1,
        )
