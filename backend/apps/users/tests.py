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
