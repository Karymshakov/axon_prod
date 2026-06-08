from django.db import migrations

TOOL = {
    'name': 'send_media',
    'display_name': 'Send Media',
    'description': (
        "Look up the hotel media library and send the most relevant photo, video, or document to the guest. "
        "Call this when the guest asks about a specific area or feature of the hotel (rooms, pool, dining, spa, exterior, etc.). "
        "Send at most one media item per response."
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
        ('flows', '0012_seed_send_room_photos_tool'),
    ]

    operations = [
        migrations.RunPython(seed_tool, remove_tool),
    ]
