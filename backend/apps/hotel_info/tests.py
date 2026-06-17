from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

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

    def test_manager_cannot_access_ai_flows_api(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(reverse('flows-list'))

        self.assertEqual(response.status_code, 403)

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
