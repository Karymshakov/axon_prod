from django.db import migrations


def backfill_leadactivity_organization(apps, schema_editor):
    LeadActivity = apps.get_model('leads', 'LeadActivity')

    qs = (
        LeadActivity.objects
        .filter(organization__isnull=True, lead__organization__isnull=False)
        .select_related('lead')
        .only('id', 'organization_id', 'lead__organization_id')
    )

    updates = []
    for activity in qs.iterator(chunk_size=1000):
        activity.organization_id = activity.lead.organization_id
        updates.append(activity)
        if len(updates) >= 1000:
            LeadActivity.objects.bulk_update(updates, ['organization'])
            updates = []

    if updates:
        LeadActivity.objects.bulk_update(updates, ['organization'])


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0062_lead_next_follow_up'),
    ]

    operations = [
        migrations.RunPython(backfill_leadactivity_organization, migrations.RunPython.noop),
    ]
