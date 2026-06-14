from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Organization, OrganizationMember


class OrganizationSettingsVisibilityTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            email='owner@example.com',
            password='password123',
            name='Owner',
            role='admin',
        )
        self.admin = user_model.objects.create_user(
            email='admin@example.com',
            password='password123',
            name='Admin',
            role='admin',
        )
        self.member = user_model.objects.create_user(
            email='member@example.com',
            password='password123',
            name='Member',
            role='support',
        )
        self.platform_admin_member = user_model.objects.create_user(
            email='platform-admin-member@example.com',
            password='password123',
            name='Platform Admin Member',
            role='admin',
        )

        self.organization = Organization.objects.create(
            name='Nomad Camp',
            slug='nomad-camp',
            owner=self.owner,
        )
        OrganizationMember.objects.create(
            organization=self.organization,
            user=self.owner,
            role=OrganizationMember.Role.OWNER,
        )
        OrganizationMember.objects.create(
            organization=self.organization,
            user=self.admin,
            role=OrganizationMember.Role.ADMIN,
        )
        OrganizationMember.objects.create(
            organization=self.organization,
            user=self.member,
            role=OrganizationMember.Role.MEMBER,
        )
        OrganizationMember.objects.create(
            organization=self.organization,
            user=self.platform_admin_member,
            role=OrganizationMember.Role.MEMBER,
        )

        self.url = reverse('organization-detail', kwargs={'slug': self.organization.slug})
        self.payload = {
            'org_settings': {
                'internal_tools_visibility': {
                    'show_ai_diagnostics': False,
                    'show_dev_database_export': False,
                    'show_reset_ai_memory': False,
                }
            }
        }

    def test_owner_can_update_internal_tools_visibility(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.patch(self.url, self.payload, format='json')

        self.assertEqual(response.status_code, 200)
        self.organization.refresh_from_db()
        self.assertFalse(self.organization.org_settings['internal_tools_visibility']['show_ai_diagnostics'])

    def test_admin_can_update_internal_tools_visibility(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(self.url, self.payload, format='json')

        self.assertEqual(response.status_code, 200)
        self.organization.refresh_from_db()
        self.assertFalse(self.organization.org_settings['internal_tools_visibility']['show_dev_database_export'])
        self.assertFalse(self.organization.org_settings['internal_tools_visibility']['show_reset_ai_memory'])

    def test_admin_can_update_lead_discovery_sources(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            self.url,
            {
                'org_settings': {
                    'lead_discovery_sources': [
                        {'value': 'partner_nomad_sport', 'label': 'Партнер Nomad Sport'},
                        {'value': 'other', 'label': 'Другое'},
                    ],
                },
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.organization.refresh_from_db()
        self.assertEqual(
            self.organization.org_settings['lead_discovery_sources'][0]['value'],
            'partner_nomad_sport',
        )

    def test_member_cannot_update_internal_tools_visibility(self):
        self.client.force_authenticate(user=self.member)

        response = self.client.patch(self.url, self.payload, format='json')

        self.assertEqual(response.status_code, 403)

    def test_platform_admin_can_update_even_with_member_org_role(self):
        self.client.force_authenticate(user=self.platform_admin_member)

        response = self.client.patch(self.url, self.payload, format='json')

        self.assertEqual(response.status_code, 200)
        self.organization.refresh_from_db()
        self.assertFalse(self.organization.org_settings['internal_tools_visibility']['show_ai_diagnostics'])
