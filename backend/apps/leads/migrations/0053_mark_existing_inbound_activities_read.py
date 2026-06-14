from django.db import migrations

INBOUND_TYPES = [
    'instagram_received',
    'telegram_received',
    'whatsapp_received',
    'ringcentral_sms_received',
    'ringcentral_call_inbound',
]


def mark_existing_as_read(apps, schema_editor):
    LeadActivity = apps.get_model('leads', 'LeadActivity')
    LeadActivity.objects.filter(activity_type__in=INBOUND_TYPES).update(is_read=True)


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0052_leadactivity_is_read'),
    ]

    operations = [
        migrations.RunPython(mark_existing_as_read, migrations.RunPython.noop),
    ]
