from django.db import migrations

TRANSFER_TOOL = {
    'name': 'transfer_to_manager',
    'display_name': 'Transfer to Manager',
    'description': (
        "Call this tool to notify the hotel manager about a completed or escalated lead. "
        "\n\nCall when ANY of these happen:\n"
        "1. Guest has confirmed room + meal plan + provided contacts → booking complete\n"
        "2. Guest is a legal entity (юрлицо), requests invoice or contract\n"
        "3. Corporate event, conference, teambuilding, banquet request\n"
        "4. Sports camp or group training request\n"
        "5. Complaint, conflict, or refund request\n"
        "6. Guest count exceeds 10 (transfer_to_manager returned by get_room_options)\n"
        "7. Guest asks a question you cannot answer from the knowledge base\n\n"
        "This tool sends a notification to the manager with a structured summary. "
        "Always call this after collecting guest data — never ask the guest to wait."
    ),
    'is_enabled': True,
}


def seed_tool(apps, schema_editor):
    AITool = apps.get_model('flows', 'AITool')
    AITool.objects.get_or_create(name=TRANSFER_TOOL['name'], defaults=TRANSFER_TOOL)


def remove_tool(apps, schema_editor):
    AITool = apps.get_model('flows', 'AITool')
    AITool.objects.filter(name=TRANSFER_TOOL['name']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('flows', '0007_managertransferconfig'),
    ]

    operations = [
        migrations.RunPython(seed_tool, remove_tool),
    ]
