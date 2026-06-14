from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0059_alter_instagramappconfig_app_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='aiconfig',
            name='instagram_ai_paused',
            field=models.BooleanField(default=False, help_text='Pause AI replies and AI automation for Instagram across all leads'),
        ),
        migrations.AddField(
            model_name='aiconfig',
            name='telegram_ai_paused',
            field=models.BooleanField(default=False, help_text='Pause AI replies and AI automation for Telegram across all leads'),
        ),
        migrations.AddField(
            model_name='aiconfig',
            name='whatsapp_ai_paused',
            field=models.BooleanField(default=False, help_text='Pause AI replies and AI automation for WhatsApp across all leads'),
        ),
    ]
