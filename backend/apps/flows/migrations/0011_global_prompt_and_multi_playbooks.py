from django.db import migrations, models


def copy_playbook_to_m2m(apps, schema_editor):
    FlowCard = apps.get_model('flows', 'FlowCard')
    for card in FlowCard.objects.filter(playbook__isnull=False):
        card.playbooks.add(card.playbook)


class Migration(migrations.Migration):

    dependencies = [
        ('flows', '0010_managertransferconfig_notification_template'),
        ('hotel_info', '0001_initial'),
    ]

    operations = [
        # 1. Add global_prompt to ConversationFlow
        migrations.AddField(
            model_name='conversationflow',
            name='global_prompt',
            field=models.TextField(
                blank=True,
                help_text='Global instructions injected into every flow-guided AI response for this flow.',
            ),
        ),
        # 2. Add playbooks M2M to FlowCard
        migrations.AddField(
            model_name='flowcard',
            name='playbooks',
            field=models.ManyToManyField(
                blank=True,
                help_text='Playbooks to inject into AI context when this card is active',
                related_name='flow_card_set',
                to='hotel_info.playbook',
            ),
        ),
        # 3. Data migration: copy existing FK → M2M
        migrations.RunPython(copy_playbook_to_m2m, migrations.RunPython.noop),
        # 4. Remove old playbook FK
        migrations.RemoveField(
            model_name='flowcard',
            name='playbook',
        ),
    ]
