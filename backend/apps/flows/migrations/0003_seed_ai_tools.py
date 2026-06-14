from django.db import migrations


TOOLS = [
    {
        'name': 'get_room_options',
        'display_name': 'Get Room Options',
        'description': (
            "Look up available room options for a given number of guests. "
            "Call this as soon as the guest mentions their group size — total_guests is the ONLY required parameter, dates are optional. "
            "Returns room configurations with the BASE (standard, no meals) price only. "
            "Present these options to the guest and ask them to choose. "
            "Do NOT mention meal plan prices at this stage — that comes after they pick a room. "
            "You MUST call this tool — do not use prices from memory."
        ),
        'is_enabled': True,
    },
    {
        'name': 'get_meal_plan_pricing',
        'display_name': 'Get Meal Plan Pricing',
        'description': (
            "Look up meal plan prices for a specific room type. "
            "Call this after room selection AND whenever the guest asks ANY question about "
            "food, meals, питание, dining, or что включено в стоимость. "
            "This is the ONLY authoritative source for meal pricing — "
            "never answer food questions from memory. "
            "Returns price_per_night for each meal plan — this is the TOTAL all-in nightly rate "
            "(room + meals combined in one price). It is NOT an add-on fee. "
            "Present it as: 'с полупансионом — X сом/ночь'. "
            "NEVER subtract the room base price to find a delta. Use price_per_night as-is."
        ),
        'is_enabled': True,
    },
]


def seed_tools(apps, schema_editor):
    AITool = apps.get_model('flows', 'AITool')
    for tool in TOOLS:
        AITool.objects.get_or_create(name=tool['name'], defaults=tool)


def remove_tools(apps, schema_editor):
    AITool = apps.get_model('flows', 'AITool')
    AITool.objects.filter(name__in=[t['name'] for t in TOOLS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('flows', '0002_add_aitool_model'),
    ]

    operations = [
        migrations.RunPython(seed_tools, remove_tools),
    ]
