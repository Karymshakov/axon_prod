from django.db import migrations, models

def map_legacy_sources(apps, schema_editor):
    Lead = apps.get_model('leads', 'Lead')
    for lead in Lead.objects.all():
        src = (lead.source or '').strip()
        src_lower = src.lower()

        # Map channel
        channel = ''
        disc_source = ''
        disc_detail = ''

        if src_lower == 'telegram':
            channel = 'Telegram'
            disc_source = 'other'
            disc_detail = 'Telegram contact'
        elif src_lower == 'whatsapp':
            channel = 'WhatsApp'
            disc_source = 'other'
            disc_detail = 'WhatsApp contact'
        elif src_lower == 'instagram':
            channel = 'Instagram'
            disc_source = 'instagram'
        elif src_lower in ['referral', 'friends', 'friend', 'recommendation']:
            disc_source = 'friends'
        elif src_lower in ['advertisement', 'ad', 'ads', 'facebook', 'google ads']:
            disc_source = 'advertisement'
        elif src_lower in ['search', 'google', 'yandex', 'поиск']:
            disc_source = 'search'
        elif src_lower in ['website', 'site', 'сайт']:
            disc_source = 'website'
        elif src_lower == 'partner':
            disc_source = 'partner'
        elif src_lower in ['returning', 'returning_guest', 'returning guest']:
            disc_source = 'returning_guest'
        elif src:
            disc_source = 'other'
            disc_detail = src

        # If a channel was detected, set it. Otherwise, if it was created manually or source is other, check if they used a known channel username/chat ID.
        if not channel:
            if lead.telegram_chat_id or lead.telegram_username:
                channel = 'Telegram'
            elif lead.instagram_user_id or lead.instagram_username:
                channel = 'Instagram'
            elif lead.whatsapp_phone:
                channel = 'WhatsApp'
            else:
                channel = 'manual'

        lead.contact_channel = channel
        lead.discovery_source = disc_source
        lead.discovery_source_detail = disc_detail
        lead.save(update_fields=['contact_channel', 'discovery_source', 'discovery_source_detail'])

class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0063_backfill_leadactivity_organization'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='contact_channel',
            field=models.CharField(
                blank=True,
                help_text='Preferred communication channel, e.g. Telegram, WhatsApp, Instagram, manual',
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name='lead',
            name='discovery_source',
            field=models.CharField(
                blank=True,
                help_text='How the guest found out about the hotel',
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name='lead',
            name='discovery_source_detail',
            field=models.CharField(
                blank=True,
                help_text='Detailed information about discovery source',
                max_length=255,
            ),
        ),
        migrations.RunPython(map_legacy_sources, migrations.RunPython.noop),
    ]
