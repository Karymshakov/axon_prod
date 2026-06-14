import io
import json
import zipfile

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.organizations.models import Organization, OrganizationMember


class DevDatabaseExportTests(APITestCase):
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
            name='Admin User',
            role='admin',
        )
        self.member = user_model.objects.create_user(
            email='member@example.com',
            password='password123',
            name='Member User',
            role='support',
        )
        self.org = Organization.objects.create(name='Nomad Camp', slug='nomad-camp', owner=self.owner)
        OrganizationMember.objects.create(
            organization=self.org,
            user=self.owner,
            role=OrganizationMember.Role.OWNER,
        )
        OrganizationMember.objects.create(
            organization=self.org,
            user=self.admin,
            role=OrganizationMember.Role.ADMIN,
        )
        OrganizationMember.objects.create(
            organization=self.org,
            user=self.member,
            role=OrganizationMember.Role.MEMBER,
        )
        self.owner.current_organization = self.org
        self.owner.save(update_fields=['current_organization'])
        self.admin.current_organization = self.org
        self.admin.save(update_fields=['current_organization'])
        self.member.current_organization = self.org
        self.member.save(update_fields=['current_organization'])

    def test_owner_can_download_full_dev_snapshot_archive(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(reverse('auth-dev-database-export'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')
        self.assertIn('attachment; filename="omnios-dev-snapshot-', response['Content-Disposition'])

        archive = zipfile.ZipFile(io.BytesIO(response.content))
        archive_names = set(archive.namelist())
        fixture_name = next(name for name in archive_names if name.endswith('.json') and name.startswith('omnios-dev-snapshot-'))

        fixture_data = json.loads(archive.read(fixture_name).decode('utf-8'))
        metadata = json.loads(archive.read('metadata.json').decode('utf-8'))
        restore_readme = archive.read('RESTORE.md').decode('utf-8')

        exported_models = {entry['model'] for entry in fixture_data}
        self.assertIn('users.user', exported_models)
        self.assertIn('organizations.organization', exported_models)
        self.assertIn('Restore locally:', restore_readme)
        self.assertEqual(metadata['exported_by'], 'owner@example.com')
        self.assertIn('Environment variables, API keys, and other runtime secrets are not included', ' '.join(metadata['notes']))

    def test_admin_can_export_dev_database(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(reverse('auth-dev-database-export'))

        self.assertEqual(response.status_code, 200)

    def test_regular_user_cannot_export_dev_database(self):
        self.client.force_authenticate(user=self.member)

        response = self.client.post(reverse('auth-dev-database-export'))

        self.assertEqual(response.status_code, 403)


class OrganizationScopedUserAdminTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            email='org-owner@example.com',
            password='password123',
            name='Org Owner',
            role='support',
        )
        self.org = Organization.objects.create(name='Nomad Camp', slug='org-admin-users', owner=self.owner)
        OrganizationMember.objects.create(
            organization=self.org,
            user=self.owner,
            role=OrganizationMember.Role.OWNER,
        )
        self.owner.current_organization = self.org
        self.owner.save(update_fields=['current_organization'])

        self.other_owner = user_model.objects.create_user(
            email='other-owner@example.com',
            password='password123',
            name='Other Owner',
            role='support',
        )
        self.other_org = Organization.objects.create(name='Other Hotel', slug='other-admin-users', owner=self.other_owner)
        OrganizationMember.objects.create(
            organization=self.other_org,
            user=self.other_owner,
            role=OrganizationMember.Role.OWNER,
        )

    def test_create_admin_user_adds_member_to_current_org_without_global_admin_role(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            reverse('admin-users-list'),
            {
                'email': 'sales-admin@example.com',
                'name': 'Sales Admin',
                'role': 'admin',
                'is_active': True,
                'password': 'password123',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        user = get_user_model().objects.get(email='sales-admin@example.com')
        self.assertEqual(user.role, 'support')
        self.assertFalse(user.is_admin)
        member = OrganizationMember.objects.get(organization=self.org, user=user)
        self.assertEqual(member.role, OrganizationMember.Role.ADMIN)
        self.assertEqual(response.data['role'], 'admin')
        self.assertEqual(response.data['organization_slug'], self.org.slug)

    def test_create_existing_user_switches_current_org_to_org_where_created(self):
        user_model = get_user_model()
        existing_user = user_model.objects.create_user(
            email='existing-manager@example.com',
            password='password123',
            name='Existing Manager',
            role='support',
        )
        OrganizationMember.objects.create(
            organization=self.other_org,
            user=existing_user,
            role=OrganizationMember.Role.MEMBER,
        )
        existing_user.current_organization = self.other_org
        existing_user.save(update_fields=['current_organization'])
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            reverse('admin-users-list'),
            {
                'email': 'existing-manager@example.com',
                'name': 'Existing Manager',
                'role': 'manager',
                'is_active': True,
                'password': 'password123',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['role'], 'manager')
        self.assertEqual(response.data['role_display'], 'Менеджер')
        self.assertEqual(response.data['organization_slug'], self.org.slug)
        existing_user.refresh_from_db()
        self.assertEqual(existing_user.current_organization, self.org)
        self.assertTrue(
            OrganizationMember.objects.filter(
                organization=self.org,
                user=existing_user,
                role=OrganizationMember.Role.MEMBER,
                is_active=True,
            ).exists()
        )

    def test_user_list_is_scoped_to_current_organization(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(reverse('admin-users-list'))

        self.assertEqual(response.status_code, 200)
        emails = {item['email'] for item in response.data}
        self.assertIn('org-owner@example.com', emails)
        self.assertNotIn('other-owner@example.com', emails)

    def test_delete_removes_org_membership_not_user_account(self):
        user_model = get_user_model()
        manager = user_model.objects.create_user(
            email='manager-to-remove@example.com',
            password='password123',
            name='Manager To Remove',
            role='support',
        )
        OrganizationMember.objects.create(
            organization=self.org,
            user=manager,
            role=OrganizationMember.Role.MEMBER,
        )
        self.client.force_authenticate(user=self.owner)

        response = self.client.delete(reverse('admin-user-detail', args=[manager.id]))

        self.assertEqual(response.status_code, 204)
        self.assertTrue(user_model.objects.filter(id=manager.id).exists())
        self.assertFalse(OrganizationMember.objects.filter(organization=self.org, user=manager).exists())

    def test_login_repairs_invalid_current_organization(self):
        user_model = get_user_model()
        manager = user_model.objects.create_user(
            email='login-repair@example.com',
            password='password123',
            name='Login Repair',
            role='support',
        )
        OrganizationMember.objects.create(
            organization=self.org,
            user=manager,
            role=OrganizationMember.Role.MEMBER,
        )
        manager.current_organization = self.other_org
        manager.save(update_fields=['current_organization'])

        response = self.client.post(
            reverse('auth-login'),
            {'email': 'login-repair@example.com', 'password': 'password123'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['user']['current_organization_slug'], self.org.slug)
        self.assertEqual(response.data['user']['role'], 'manager')
        self.assertEqual(response.data['user']['role_display'], 'Менеджер')
        manager.refresh_from_db()
        self.assertEqual(manager.current_organization, self.org)
