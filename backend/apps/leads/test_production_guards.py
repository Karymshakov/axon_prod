from unittest.mock import patch
from datetime import date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from django.test import TestCase

from apps.leads.instagram_views import _split_into_messages as split_instagram
from apps.leads.services.booking_tools import execute_pricing_tool
from apps.leads.services.llm_client import _room_price_claim_matches_cached_offer


class ProductionConversationGuardTests(TestCase):
    def test_short_structured_instagram_reply_stays_in_one_message(self):
        reply = (
            'Для вас подойдёт один номер Комфорт.\n\n'
            'Стоимость — 9 500 сом/ночь.\n\n'
            'Подтвердить этот вариант?'
        )
        self.assertEqual(split_instagram(reply), [reply])

    @patch('apps.hotel_info.pricing_utils.generate_room_combinations')
    def test_infant_and_one_room_constraint_returns_compact_room_only(self, combinations_mock):
        combinations_mock.return_value = [{
            'guest_count': 2,
            'combinations': [
                {
                    'index': 0,
                    'rooms': ['комфорт двухместный'],
                    'room_count': 1,
                    'type': 'Основной',
                    'available': True,
                    'prices': {'standard': 9500},
                },
                {
                    'index': 1,
                    'rooms': ['семейный один номер'],
                    'room_count': 1,
                    'type': 'Семейный',
                    'available': True,
                    'prices': {'standard': 11500},
                },
                {
                    'index': 2,
                    'rooms': ['семейный два номера'],
                    'room_count': 2,
                    'type': 'Семейный',
                    'available': True,
                    'prices': {'standard': 17000},
                },
            ],
        }]

        result = execute_pricing_tool('get_room_options', {
            'guest_count': 2,
            'children_ages': [0.17],
            'one_room_required': True,
            'checkin_date': '2026-07-28',
            'checkout_date': '2026-07-31',
        })

        self.assertNotIn('error', result)
        self.assertEqual(
            [option['description'] for option in result['combinations']],
            ['комфорт двухместный'],
        )
        self.assertTrue(all(option['room_count'] == 1 for option in result['combinations']))

    @patch('apps.hotel_info.pricing_utils.generate_room_combinations')
    def test_missing_current_tariff_is_explicit_error(self, combinations_mock):
        combinations_mock.return_value = [{
            'guest_count': 2,
            'combinations': [
                {
                    'index': 0,
                    'rooms': ['комфорт двухместный'],
                    'room_count': 1,
                    'type': 'Основной',
                    'available': False,
                    'prices': None,
                },
            ],
        }]

        result = execute_pricing_tool('get_room_options', {
            'guest_count': 2,
            'checkin_date': '2026-07-28',
            'checkout_date': '2026-07-31',
        })

        self.assertEqual(result['error'], 'pricing_unavailable')
        self.assertEqual(result['combinations'], [])

    def test_room_pricing_requires_both_exact_dates(self):
        result = execute_pricing_tool('get_room_options', {
            'guest_count': 2,
            'children_ages': [0.02],
            'one_room_required': True,
            'checkin_date': '2026-07-28',
        })

        self.assertEqual(result['error'], 'dates_required')

    def test_verified_cached_offer_can_be_reused_in_followup(self):
        lead = SimpleNamespace(
            check_in_date=date(2026, 7, 28),
            check_out_date=date(2026, 8, 2),
            agent_context={
                'last_room_offer': {
                    'checkin_date': '2026-07-28',
                    'checkout_date': '2026-08-02',
                    'created_at': datetime.now(ZoneInfo('UTC')).isoformat(),
                    'combinations': [{
                        'standard_price_per_night': 9500,
                        'meal_plans': {
                            'with_breakfast': {'per_night': 10900},
                        },
                    }],
                },
            },
        )

        self.assertTrue(_room_price_claim_matches_cached_offer(
            'Вы выбрали Комфорт — 9 500 сом/ночь.',
            lead,
        ))
        self.assertFalse(_room_price_claim_matches_cached_offer(
            'Вы выбрали Комфорт — 7 000 сом/ночь.',
            lead,
        ))
