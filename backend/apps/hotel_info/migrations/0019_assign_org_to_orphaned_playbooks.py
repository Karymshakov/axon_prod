"""
Data migration: assign the Nomad Camp organization to any Playbook rows
that have organization=NULL.

Playbooks with no org were created before the multi-tenant migration or
via a code path that skipped the org assignment. The safest fallback is
to assign them to the first organization in the database (Nomad Camp,
created in the Phase 1 migration).
"""
from django.db import migrations


def assign_org_to_orphaned_playbooks(apps, schema_editor):
    Playbook = apps.get_model('hotel_info', 'Playbook')
    Organization = apps.get_model('organizations', 'Organization')

    orphans = Playbook.objects.filter(organization__isnull=True)
    if not orphans.exists():
        return

    # Use Nomad Camp (the bootstrapped org from Phase 1 migration).
    # Fall back to whichever org was created first if name differs.
    org = (
        Organization.objects.filter(slug='nomad-camp').first()
        or Organization.objects.order_by('id').first()
    )
    if org is None:
        return  # No orgs exist — nothing to assign

    count = orphans.update(organization=org)
    print(f'  Assigned org "{org.name}" to {count} orphaned Playbook(s).')


class Migration(migrations.Migration):

    dependencies = [
        ('hotel_info', '0018_handovercontact_organization_hotelfaq_organization_and_more'),
        ('organizations', '0003_fix_users_missing_current_org'),
    ]

    operations = [
        migrations.RunPython(
            assign_org_to_orphaned_playbooks,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
