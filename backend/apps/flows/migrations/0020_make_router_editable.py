from django.db import migrations


def make_router_editable(apps, schema_editor):
    AgentConfig = apps.get_model('flows', 'AgentConfig')
    AgentConfig.objects.filter(name='router').update(is_editable=True)


def revert_router_editable(apps, schema_editor):
    AgentConfig = apps.get_model('flows', 'AgentConfig')
    AgentConfig.objects.filter(name='router').update(is_editable=False)


class Migration(migrations.Migration):

    dependencies = [
        ('flows', '0019_fix_agent_prompts'),
    ]

    operations = [
        migrations.RunPython(make_router_editable, reverse_code=revert_router_editable),
    ]
