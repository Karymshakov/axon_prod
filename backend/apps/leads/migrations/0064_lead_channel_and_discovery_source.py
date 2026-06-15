from django.db import migrations, models


CHANNEL_SOURCES = {
    'telegram': 'telegram',
    'tg': 'telegram',
    'instagram': 'instagram',
    'insta': 'instagram',
    'whatsapp': 'whatsapp',
    'wa': 'whatsapp',
}

DISCOVERY_SOURCES = {
    'website': 'website',
    'сайт': 'website',
    'referral': 'friends',
    'recommendation': 'friends',
    'рекомендация': 'friends',
    'сарафанное радио': 'friends',
    'social media': 'social',
    'социальные сети': 'social',
    'email campaign': 'email',
    'email-кампания': 'email',
    'cold call': 'cold_call',
    'холодный звонок': 'cold_call',
    'trade show': 'event',
    'выставка': 'event',
    'advertisement': 'ads',
    'реклама': 'ads',
    'ads': 'ads',
    'partner': 'partner',
    'партнёр': 'partner',
    'booking': 'booking',
    'booking.com': 'booking',
    'букинг': 'booking',
    'other': 'other',
    'другое': 'other',
}


def backfill_channel_and_discovery(apps, schema_editor):
    Lead = apps.get_model('leads', 'Lead')
    for lead in Lead.objects.all().only('id', 'source', 'contact_channel', 'discovery_source', 'discovery_source_detail'):
        raw = (lead.source or '').strip()
        if not raw:
            continue

        lowered = raw.lower()
        update_fields = []

        channel = CHANNEL_SOURCES.get(lowered)
        if channel and not lead.contact_channel:
            lead.contact_channel = channel
            update_fields.append('contact_channel')

        discovery = DISCOVERY_SOURCES.get(lowered)
        if discovery and not lead.discovery_source:
            lead.discovery_source = discovery
            update_fields.append('discovery_source')
            if discovery in {'friends', 'other'} and not lead.discovery_source_detail:
                lead.discovery_source_detail = raw
                update_fields.append('discovery_source_detail')

        if update_fields:
            lead.save(update_fields=update_fields)


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0063_backfill_leadactivity_organization'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='contact_channel',
            field=models.CharField(blank=True, help_text='Primary channel where the guest contacted us', max_length=30),
        ),
        migrations.AddField(
            model_name='lead',
            name='discovery_source',
            field=models.CharField(blank=True, help_text='How the guest learned about us', max_length=50),
        ),
        migrations.AddField(
            model_name='lead',
            name='discovery_source_detail',
            field=models.CharField(blank=True, help_text='Free-form detail for the discovery source', max_length=255),
        ),
        migrations.RunPython(backfill_channel_and_discovery, migrations.RunPython.noop),
    ]
