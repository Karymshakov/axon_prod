"""
Data migration: set current_organization for users who have an OrganizationMember
record but whose current_organization field is NULL.

This fixes accounts created via invite_member (which previously didn't set
current_organization), causing integration API endpoints to fall back to the
wrong org's config (the first record in the database).
"""
from django.db import migrations


def fix_users_missing_current_org(apps, schema_editor):
    OrganizationMember = apps.get_model('organizations', 'OrganizationMember')
    User = apps.get_model('users', 'User')

    # Find all active members whose user has no current_organization
    members_without_org = OrganizationMember.objects.filter(
        is_active=True,
        user__current_organization__isnull=True,
    ).select_related('user', 'organization').order_by('joined_at')

    updated = set()
    for member in members_without_org:
        user = member.user
        if user.pk in updated:
            continue
        user.current_organization = member.organization
        user.save(update_fields=['current_organization'])
        updated.add(user.pk)

    if updated:
        print(f'  Set current_organization for {len(updated)} user(s).')


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0002_populate_default_org'),
    ]

    operations = [
        migrations.RunPython(
            fix_users_missing_current_org,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
