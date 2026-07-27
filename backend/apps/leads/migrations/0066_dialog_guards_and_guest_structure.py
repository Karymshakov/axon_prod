from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('leads', '0065_alter_aiconfig_system_prompt_and_more'),
        ('organizations', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='adult_count',
            field=models.PositiveSmallIntegerField(blank=True, help_text='Number of adult guests', null=True),
        ),
        migrations.AddField(
            model_name='lead',
            name='children_ages',
            field=models.JSONField(blank=True, default=list, help_text='Child ages in years; fractions are allowed for infants'),
        ),
        migrations.AddField(
            model_name='lead',
            name='conversation_kind',
            field=models.CharField(
                choices=[
                    ('sales', 'Sales'),
                    ('courtesy', 'Courtesy / social interaction'),
                    ('faq', 'FAQ only'),
                    ('service', 'Service / support'),
                ],
                db_index=True,
                default='sales',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='lead',
            name='followup_allowed',
            field=models.BooleanField(default=True, help_text='Whether automated proactive follow-ups are allowed for this conversation.'),
        ),
        migrations.AddField(
            model_name='lead',
            name='infant_count',
            field=models.PositiveSmallIntegerField(default=0, help_text='Number of guests under one year old'),
        ),
        migrations.AddField(
            model_name='lead',
            name='is_sales_lead',
            field=models.BooleanField(db_index=True, default=True, help_text='False for courtesy/story/FAQ conversations that must not enter the sales funnel.'),
        ),
        migrations.AddField(
            model_name='lead',
            name='one_room_required',
            field=models.BooleanField(blank=True, help_text='Guest explicitly requires one room', null=True),
        ),
        migrations.AddField(
            model_name='lead',
            name='origin_event_type',
            field=models.CharField(blank=True, db_index=True, help_text='Normalized event that opened the conversation, e.g. story_mention.', max_length=50),
        ),
        migrations.CreateModel(
            name='OutboundActionClaim',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('channel', models.CharField(max_length=30)),
                ('action_type', models.CharField(max_length=50)),
                ('idempotency_key', models.CharField(max_length=255, unique=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('sent', 'Sent'), ('failed', 'Failed')], default='pending', max_length=20)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('lead', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='outbound_action_claims', to='leads.lead')),
                ('organization', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='organizations.organization')),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['lead', 'channel', 'action_type', 'created_at'], name='leads_outbo_lead_id_030257_idx')],
            },
        ),
    ]
