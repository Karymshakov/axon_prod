from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0061_lead_custom_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='next_follow_up_at',
            field=models.DateTimeField(
                blank=True,
                help_text='AI-scheduled datetime for the next proactive outreach',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='lead',
            name='next_follow_up_hint',
            field=models.TextField(
                blank=True,
                help_text="AI's reasoning for the scheduled follow-up",
            ),
        ),
    ]
