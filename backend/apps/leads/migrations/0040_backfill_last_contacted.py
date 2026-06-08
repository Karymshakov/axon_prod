from django.db import migrations


def backfill_last_contacted(apps, schema_editor):
    Lead = apps.get_model('leads', 'Lead')
    LeadActivity = apps.get_model('leads', 'LeadActivity')

    updated = 0
    skipped = 0

    for lead in Lead.objects.filter(last_contacted__isnull=True).iterator():
        latest_activity = (
            LeadActivity.objects.filter(lead=lead)
            .order_by('-created_at')
            .values_list('created_at', flat=True)
            .first()
        )
        if latest_activity:
            Lead.objects.filter(id=lead.id).update(last_contacted=latest_activity.date())
            updated += 1
        else:
            skipped += 1

    print(f'  Backfilled last_contacted: {updated} leads updated, {skipped} skipped (no activity)')


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0039_lead_instagram_intent_tier'),
    ]

    operations = [
        migrations.RunPython(backfill_last_contacted, migrations.RunPython.noop),
    ]
