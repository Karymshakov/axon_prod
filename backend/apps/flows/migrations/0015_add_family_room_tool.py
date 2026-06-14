from django.db import migrations


GET_ROOM_OPTIONS_DESCRIPTION = (
    "Use for standard groups — couples, friends, colleagues, solo travelers. "
    "Never call this when the guest mentions children, kids, baby, toddler, son, daughter, or family."
)

GET_FAMILY_ROOM_DESCRIPTION = (
    "Use ONLY when guest mentions children, kids, baby, toddler, son, daughter, family, "
    "or any indication they are travelling with minors. "
    "Returns family room options only. "
    "guest_count should be adults only — do not count children under 6."
)


def add_family_room_tool(apps, schema_editor):
    AITool = apps.get_model('flows', 'AITool')

    # Update get_room_options description
    AITool.objects.filter(name='get_room_options').update(
        description=GET_ROOM_OPTIONS_DESCRIPTION
    )

    # Create get_family_room tool (skip if already exists)
    AITool.objects.get_or_create(
        name='get_family_room',
        defaults={
            'display_name': 'Get Family Room',
            'description': GET_FAMILY_ROOM_DESCRIPTION,
            'is_enabled': True,
        },
    )


def remove_family_room_tool(apps, schema_editor):
    AITool = apps.get_model('flows', 'AITool')
    AITool.objects.filter(name='get_family_room').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('flows', '0014_remove_send_media_tool'),
    ]

    operations = [
        migrations.RunPython(add_family_room_tool, remove_family_room_tool),
    ]
