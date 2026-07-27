from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('hotel_media', '0005_socialcontentitem_mediafingerprint_and_more'),
    ]

    operations = [
        migrations.AddField(model_name='socialcontentitem', name='automation_enabled', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='socialcontentitem', name='automation_ends_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='socialcontentitem', name='automation_followup_allowed', field=models.BooleanField(default=False, help_text='Follow-ups remain disabled until the guest shows sales intent.')),
        migrations.AddField(model_name='socialcontentitem', name='automation_promotes_to_lead', field=models.BooleanField(default=False, help_text='If false, campaign delivery itself does not create a sales lead.')),
        migrations.AddField(model_name='socialcontentitem', name='automation_reply_en', field=models.TextField(blank=True)),
        migrations.AddField(model_name='socialcontentitem', name='automation_reply_ky', field=models.TextField(blank=True)),
        migrations.AddField(model_name='socialcontentitem', name='automation_reply_ru', field=models.TextField(blank=True)),
        migrations.AddField(model_name='socialcontentitem', name='automation_starts_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='socialcontentitem', name='automation_trigger', field=models.CharField(choices=[('none', 'Disabled'), ('comment_any', 'Any comment'), ('comment_exact', 'Comment matches configured phrases')], default='none', max_length=30)),
        migrations.AddField(model_name='socialcontentitem', name='automation_trigger_values', field=models.JSONField(blank=True, default=list, help_text='Exact phrases for comment_exact; matching is normalized and case-insensitive.')),
        migrations.CreateModel(
            name='SocialAutomationDelivery',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('external_event_id', models.CharField(max_length=255)),
                ('recipient_id', models.CharField(blank=True, max_length=128)),
                ('trigger_text', models.TextField(blank=True)),
                ('reply_text', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('sent', 'Sent'), ('failed', 'Failed')], default='pending', max_length=20)),
                ('response_message_id', models.CharField(blank=True, max_length=255)),
                ('error', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('organization', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='organizations.organization')),
                ('social_content_item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='automation_deliveries', to='hotel_media.socialcontentitem')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddConstraint(
            model_name='socialautomationdelivery',
            constraint=models.UniqueConstraint(fields=('organization', 'external_event_id'), name='uniq_social_automation_event_per_org'),
        ),
    ]
