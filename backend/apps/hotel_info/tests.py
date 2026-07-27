from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.hotel_info.models import RoomPricing
from apps.organizations.models import Organization, OrganizationMember


class HotelWorkspaceAccessTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_user(
            email='admin-hotel@example.com',
            password='password123',
            name='Admin Hotel',
            role='admin',
        )
        self.manager = user_model.objects.create_user(
            email='manager-hotel@example.com',
            password='password123',
            name='Manager Hotel',
            role='support',
        )
        self.org = Organization.objects.create(
            name='Nomad Camp',
            slug='nomad-camp-access',
            owner=self.admin,
        )
        OrganizationMember.objects.create(
            organization=self.org,
            user=self.admin,
            role=OrganizationMember.Role.ADMIN,
        )
        OrganizationMember.objects.create(
            organization=self.org,
            user=self.manager,
            role=OrganizationMember.Role.MEMBER,
        )
        self.admin.current_organization = self.org
        self.admin.save(update_fields=['current_organization'])
        self.manager.current_organization = self.org
        self.manager.save(update_fields=['current_organization'])

    def test_manager_can_read_hotel_profile(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(reverse('hotel-profile'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('hotel_name', response.data)

    def test_manager_cannot_update_hotel_profile(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.patch(
            reverse('hotel-profile'),
            {'hotel_name': 'Updated by manager'},
            format='json',
        )

        self.assertEqual(response.status_code, 403)

    def test_is_admin_user_can_update_hotel_profile_even_with_member_org_role(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            reverse('hotel-profile'),
            {'hotel_name': 'Updated by admin'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['hotel_name'], 'Updated by admin')

    def test_manager_can_read_but_cannot_change_ai_flows(self):
        self.client.force_authenticate(user=self.manager)

        read_response = self.client.get(reverse('flows-list'))
        write_response = self.client.post(
            reverse('flows-list'),
            {'name': 'Manager flow', 'description': 'Must be forbidden'},
            format='json',
        )

        self.assertEqual(read_response.status_code, 200)
        self.assertEqual(write_response.status_code, 403)

    def test_is_admin_user_can_access_ai_flows_api_even_with_member_org_role(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(reverse('flows-list'))

        self.assertEqual(response.status_code, 200)

    def test_manager_cannot_create_reply_template_category(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            reverse('reply-template-category-list'),
            {'name': 'Бронирование'},
            format='json',
        )

        self.assertEqual(response.status_code, 403)

    def test_admin_can_create_reply_template_category(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            reverse('reply-template-category-list'),
            {'name': 'Бронирование'},
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['name'], 'Бронирование')

    def test_admin_can_create_reply_template_in_new_category(self):
        self.client.force_authenticate(user=self.admin)

        category_response = self.client.post(
            reverse('reply-template-category-list'),
            {'name': 'Бронирование'},
            format='json',
        )
        template_response = self.client.post(
            reverse('reply-template-list'),
            {
                'category': category_response.data['id'],
                'title': 'Уточнить даты',
                'text': 'Подскажите, пожалуйста, даты заезда и выезда.',
                'channel': 'all',
                'tags': ['даты'],
                'is_active': True,
            },
            format='json',
        )

        self.assertEqual(category_response.status_code, 201)
        self.assertEqual(template_response.status_code, 201)

        self.client.force_authenticate(user=self.manager)
        categories_response = self.client.get(reverse('reply-template-category-list'))
        self.assertEqual(categories_response.status_code, 200)
        self.assertEqual(categories_response.data[0]['templates'][0]['title'], 'Уточнить даты')

    def test_channel_filter_includes_universal_reply_templates(self):
        self.client.force_authenticate(user=self.admin)

        category_response = self.client.post(
            reverse('reply-template-category-list'),
            {'name': 'Бронирование'},
            format='json',
        )
        category_id = category_response.data['id']
        self.client.post(
            reverse('reply-template-list'),
            {
                'category': category_id,
                'title': 'Общий ответ',
                'text': 'Универсальный шаблон для любого канала.',
                'channel': 'all',
                'is_active': True,
            },
            format='json',
        )
        self.client.post(
            reverse('reply-template-list'),
            {
                'category': category_id,
                'title': 'Только Instagram',
                'text': 'Этот шаблон нужен только для Instagram.',
                'channel': 'instagram',
                'is_active': True,
            },
            format='json',
        )

        self.client.force_authenticate(user=self.manager)
        response = self.client.get(reverse('reply-template-list'), {'channel': 'telegram'})

        self.assertEqual(response.status_code, 200)
        titles = {template['title'] for template in response.data}
        self.assertIn('Общий ответ', titles)
        self.assertNotIn('Только Instagram', titles)

    def test_automation_defaults_are_editable_by_admin_only(self):
        self.client.force_authenticate(user=self.manager)
        list_response = self.client.get(reverse('automation-message-template-list'))
        self.assertEqual(list_response.status_code, 200)
        self.assertGreaterEqual(len(list_response.data), 7)

        template_id = list_response.data[0]['id']
        forbidden_response = self.client.patch(
            reverse('automation-message-template-detail', args=[template_id]),
            {'text': 'Manager overwrite'},
            format='json',
        )
        self.assertEqual(forbidden_response.status_code, 403)

        self.client.force_authenticate(user=self.admin)
        update_response = self.client.patch(
            reverse('automation-message-template-detail', args=[template_id]),
            {'text': 'Администраторский шаблон'},
            format='json',
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.data['text'], 'Администраторский шаблон')

    def test_booking_rules_are_readable_by_manager_and_writable_by_admin(self):
        self.client.force_authenticate(user=self.manager)
        read_response = self.client.get(reverse('booking-rules'))
        forbidden_response = self.client.patch(
            reverse('booking-rules'),
            {'followup_delay_minutes': 25},
            format='json',
        )
        self.assertEqual(read_response.status_code, 200)
        self.assertEqual(forbidden_response.status_code, 403)

        self.client.force_authenticate(user=self.admin)
        update_response = self.client.patch(
            reverse('booking-rules'),
            {'followup_delay_minutes': 15},
            format='json',
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.data['followup_delay_minutes'], 15)

    def test_family_pricing_is_hidden_and_cannot_be_added(self):
        RoomPricing.objects.create(
            organization=self.org,
            kategoria_nomera='Семейный номер',
            kolichestvo_chelovek=4,
            guest_type='family',
            standartny_tarif=12000,
        )
        self.client.force_authenticate(user=self.admin)

        list_response = self.client.get(reverse('room-pricing-list'))
        create_response = self.client.post(
            reverse('room-pricing-list'),
            {
                'kategoria_nomera': 'Семейный номер',
                'kolichestvo_chelovek': 4,
                'guest_type': 'family',
                'dni_nedeli': [],
                'standartny_tarif': '12000',
            },
            format='json',
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data, [])
        self.assertEqual(create_response.status_code, 400)
