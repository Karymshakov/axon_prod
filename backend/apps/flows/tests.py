from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.flows.models import AIFlowMode, ConversationFlow, FlowCard, FlowConnection, LeadFlowState
from apps.flows.serializers import FlowCardSerializer
from apps.flows.views import FlowCardViewSet
from apps.leads.models import Lead
from apps.leads.services.booking_tools import (
    build_flow_card_instruction,
    get_flow_guided_response,
    normalize_booking_tool_args,
)
from apps.leads.services.stage_resolver import sync_stage_state
from apps.organizations.models import Organization, OrganizationMember


class FlowCardPolicyTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email='sales@example.com', password='pass')
        self.org = Organization.objects.create(name='Policy Org', slug='policy-org', owner=self.user)
        self.user.current_organization = self.org
        self.user.save(update_fields=['current_organization'])
        OrganizationMember.objects.create(organization=self.org, user=self.user, role='admin')
        self.flow = ConversationFlow.objects.create(organization=self.org, name='Booking Flow', is_active=True)

    def test_flow_card_policy_is_exposed_to_api_and_prompt_builder(self):
        card = FlowCard.objects.create(
            flow=self.flow,
            title='Collect dates',
            message_template='Ask for {check_in_date} and checkout.',
            goal='Collect stay dates before showing final prices.',
            required_fields=['check_in_date', 'check_out_date'],
            success_conditions={'all_fields_present': True},
            allowed_tools=['get_room_options'],
            response_policy={'side_questions': 'answer_then_return'},
            return_to_funnel_instruction='After answering side questions, ask for missing stay dates.',
        )

        serializer_data = FlowCardSerializer(card).data
        self.assertEqual(serializer_data['goal'], 'Collect stay dates before showing final prices.')
        self.assertEqual(serializer_data['required_fields'], ['check_in_date', 'check_out_date'])
        self.assertEqual(serializer_data['allowed_tools'], ['get_room_options'])

        instruction = build_flow_card_instruction(
            card,
            {'check_in_date': '2026-07-01'},
            self.flow,
        )
        self.assertIn('Current flow stage: Collect dates', instruction)
        self.assertIn('Stage goal: Collect stay dates before showing final prices.', instruction)
        self.assertIn('Required fields to collect before progressing: check_in_date, check_out_date', instruction)
        self.assertIn('Allowed tools on this stage: get_room_options', instruction)
        self.assertIn('Return-to-funnel instruction', instruction)

    def test_flow_card_nested_view_is_scoped_through_flow_organization(self):
        own_card = FlowCard.objects.create(flow=self.flow, title='Own card')
        other_owner = get_user_model().objects.create_user(email='other@example.com', password='pass')
        other_org = Organization.objects.create(name='Other Org', slug='other-org', owner=other_owner)
        other_flow = ConversationFlow.objects.create(organization=other_org, name='Other Flow')
        FlowCard.objects.create(flow=other_flow, title='Other card')

        factory = APIRequestFactory()
        request = factory.get(f'/flows/{self.flow.pk}/cards/')
        force_authenticate(request, user=self.user)
        response = FlowCardViewSet.as_view({'get': 'list'})(request, flow_pk=self.flow.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['id'] for row in response.data], [own_card.pk])

    def test_active_flow_is_unique_per_organization_not_global(self):
        other_owner = get_user_model().objects.create_user(email='flow-owner@example.com', password='pass')
        other_org = Organization.objects.create(name='Second Org', slug='second-org', owner=other_owner)
        other_flow = ConversationFlow.objects.create(organization=other_org, name='Other Active', is_active=True)

        new_own_flow = ConversationFlow.objects.create(organization=self.org, name='Own Active', is_active=True)

        other_flow.refresh_from_db()
        self.flow.refresh_from_db()
        new_own_flow.refresh_from_db()

        self.assertTrue(other_flow.is_active)
        self.assertFalse(self.flow.is_active)
        self.assertTrue(new_own_flow.is_active)

    def test_stage_resolver_syncs_required_data_from_message_and_lead_data(self):
        card = FlowCard.objects.create(
            flow=self.flow,
            title='Qualify stay',
            required_fields=['guest_count', 'check_in_date'],
        )
        lead = Lead.objects.create(organization=self.org, contact_person='Aida')
        state = LeadFlowState.objects.create(lead=lead, flow=self.flow, current_card=card)

        resolution = sync_stage_state(
            state,
            lead,
            {'check_in_date': '2026-07-10'},
            'Нас будет 3 человека',
        )

        self.assertTrue(resolution.is_complete)
        self.assertTrue(resolution.changed)
        self.assertEqual(resolution.collected_data['guest_count'], 3)
        self.assertEqual(resolution.collected_data['check_in_date'], '2026-07-10')

    def test_stage_resolver_understands_current_month_day_phrase(self):
        card = FlowCard.objects.create(
            flow=self.flow,
            title='Qualify stay',
            required_fields=['guest_count', 'check_in_date'],
        )
        lead = Lead.objects.create(organization=self.org, contact_person='Aida')
        state = LeadFlowState.objects.create(lead=lead, flow=self.flow, current_card=card)

        resolution = sync_stage_state(
            state,
            lead,
            {},
            '5 человек, планируем 5го числа этого месяца',
        )

        today = date.today()
        expected = date(today.year, today.month, 5)
        if expected < today:
            next_month = today.month + 1
            year = today.year
            if next_month > 12:
                next_month = 1
                year += 1
            expected = date(year, next_month, 5)

        self.assertTrue(resolution.is_complete)
        self.assertEqual(resolution.collected_data['guest_count'], 5)
        self.assertEqual(resolution.collected_data['check_in_date'], expected.isoformat())

    def test_booking_tool_args_use_flow_state_and_nights(self):
        card = FlowCard.objects.create(flow=self.flow, title='Room Selection')
        lead = Lead.objects.create(organization=self.org, contact_person='Aida')
        LeadFlowState.objects.create(
            lead=lead,
            flow=self.flow,
            current_card=card,
            collected_data={'guest_count': 5},
        )

        args = normalize_booking_tool_args(
            'get_room_options',
            {},
            'с 5 июня на 4 ночи',
            [],
            {},
            lead,
        )

        checkin = date(date.today().year, 6, 5)
        self.assertEqual(args['guest_count'], 5)
        self.assertEqual(args['checkin_date'], checkin.isoformat())
        self.assertEqual(args['checkout_date'], (checkin + timedelta(days=4)).isoformat())

    def test_flow_guided_response_stays_on_stage_until_required_fields_collected(self):
        AIFlowMode.objects.create(organization=self.org, mode=AIFlowMode.MODE_FLOW_GUIDED)
        entry = FlowCard.objects.create(
            flow=self.flow,
            card_type=FlowCard.CARD_TYPE_ENTRY,
            title='Collect booking basics',
            message_template='Need guest count and dates.',
            required_fields=['guest_count', 'check_in_date'],
        )
        next_card = FlowCard.objects.create(
            flow=self.flow,
            title='Offer room',
            message_template='Offer room now.',
        )
        FlowConnection.objects.create(flow=self.flow, source_card=entry, target_card=next_card)
        lead = Lead.objects.create(organization=self.org, contact_person='Aida')
        LeadFlowState.objects.create(lead=lead, flow=self.flow, current_card=entry)

        instruction = get_flow_guided_response('Нас будет 3 человека', lead, {}, None)

        lead.flow_state.refresh_from_db()
        self.assertEqual(lead.flow_state.current_card, entry)
        self.assertIn('Stage status: stay on this stage', instruction)
        self.assertEqual(lead.flow_state.collected_data['guest_count'], 3)

    def test_flow_guided_response_advances_after_required_fields_collected(self):
        AIFlowMode.objects.create(organization=self.org, mode=AIFlowMode.MODE_FLOW_GUIDED)
        entry = FlowCard.objects.create(
            flow=self.flow,
            card_type=FlowCard.CARD_TYPE_ENTRY,
            title='Collect booking basics',
            message_template='Need guest count and dates.',
            required_fields=['guest_count', 'check_in_date'],
        )
        next_card = FlowCard.objects.create(
            flow=self.flow,
            title='Offer room',
            message_template='Offer room now.',
        )
        FlowConnection.objects.create(flow=self.flow, source_card=entry, target_card=next_card)
        lead = Lead.objects.create(organization=self.org, contact_person='Aida')
        LeadFlowState.objects.create(lead=lead, flow=self.flow, current_card=entry)

        instruction = get_flow_guided_response(
            'готовы смотреть варианты',
            lead,
            {'guest_count': 3, 'check_in_date': '2026-07-10'},
            None,
        )

        lead.flow_state.refresh_from_db()
        self.assertEqual(lead.flow_state.current_card, next_card)
        self.assertEqual(instruction, 'Offer room now.')

    def test_flow_guided_response_auto_advances_completed_required_stage_without_keyword(self):
        AIFlowMode.objects.create(organization=self.org, mode=AIFlowMode.MODE_FLOW_GUIDED)
        meal_card = FlowCard.objects.create(
            flow=self.flow,
            card_type=FlowCard.CARD_TYPE_ENTRY,
            title='Meal Plan Selection',
            message_template='Choose meal plan.',
            required_fields=['meal_plan'],
        )
        contact_card = FlowCard.objects.create(
            flow=self.flow,
            title='Collect Contacts',
            message_template='Please share phone or email.',
            required_fields=['phone'],
        )
        FlowConnection.objects.create(
            flow=self.flow,
            source_card=meal_card,
            target_card=contact_card,
            condition_keywords='готово',
        )
        lead = Lead.objects.create(organization=self.org, contact_person='Aida')
        LeadFlowState.objects.create(
            lead=lead,
            flow=self.flow,
            current_card=meal_card,
            collected_data={'meal_plan': 'breakfast'},
        )

        instruction = get_flow_guided_response('dnccira@gmail.com', lead, {}, None)

        lead.flow_state.refresh_from_db()
        self.assertEqual(lead.flow_state.current_card, contact_card)
        self.assertIn('Current flow stage: Collect Contacts', instruction)
        self.assertIn('Please share phone or email.', instruction)

    def test_contact_stage_requires_real_name_and_phone_but_not_email(self):
        from apps.leads.services.stage_resolver import sync_stage_state

        contact_card = FlowCard.objects.create(
            flow=self.flow,
            title='Collect Contacts',
            message_template='Ask for contacts.',
            required_fields=['phone', 'email'],
        )
        lead = Lead.objects.create(
            organization=self.org,
            contact_person='Dan12',
            telegram_username='dan12dan_12',
            phone='0777889933',
        )
        state = LeadFlowState.objects.create(lead=lead, flow=self.flow, current_card=contact_card)

        resolution = sync_stage_state(state, lead, {}, '')

        self.assertFalse(resolution.is_complete)
        self.assertEqual(resolution.required_fields, ['phone', 'contact_person'])
        self.assertEqual(resolution.missing_fields, ['contact_person'])

        lead.contact_person = 'Даниил'
        lead.save(update_fields=['contact_person'])
        resolution = sync_stage_state(state, lead, {}, '')

        self.assertTrue(resolution.is_complete)
        self.assertNotIn('email', resolution.required_fields)
