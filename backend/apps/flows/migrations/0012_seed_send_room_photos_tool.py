from django.db import migrations

TOOL = {
    'name': 'get_room_images',
    'display_name': 'Send Room Photos',
    'description': (
        "Send photos of hotel rooms to the guest. "
        "Call this when a guest asks to see a room, asks what a room looks like, or requests photos. "
        "Infer the room category from context: 1-2 guests → standard_queen or standard_twin; "
        "3-4 guests or guest mentions 'комфорт'/'comfort' → comfort; "
        "family with confirmed children → family. "
        "Pass multiple categories when the guest asks to see all rooms. "
        "Photos are sent directly to the guest — compose a natural reply referencing them."
    ),
    'is_enabled': True,
}


def seed_tool(apps, schema_editor):
    AITool = apps.get_model('flows', 'AITool')
    AITool.objects.get_or_create(name=TOOL['name'], defaults=TOOL)


def remove_tool(apps, schema_editor):
    AITool = apps.get_model('flows', 'AITool')
    AITool.objects.filter(name=TOOL['name']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('flows', '0011_global_prompt_and_multi_playbooks'),
    ]

    operations = [
        migrations.RunPython(seed_tool, remove_tool),
    ]
