from django.db import migrations


ROOM_OPTIONS_DESCRIPTION = (
    "Use for standard groups — couples, friends, colleagues, solo travelers. "
    "Never call this when the guest mentions children, kids, baby, toddler, son, daughter, or family."
)

MEAL_PLAN_DESCRIPTION = (
    "Look up meal plan prices for a specific room type. "
    "Call this after room selection AND whenever the guest asks ANY question about "
    "food, meals, питание, dining, or что включено в стоимость. "
    "This is the ONLY authoritative source for meal pricing — never answer food questions from memory. "
    "Returns total_price_per_night for each meal plan — this is the COMPLETE all-in nightly rate "
    "(room + meals combined). It is NOT an add-on fee. Do NOT subtract the room base price. "
    "Quote total_price_per_night directly as the new rate: 'с полупансионом — 8 800 сом/ночь'. "
    "Never do arithmetic with the room price. Never present a delta. Just quote total_price_per_night."
)

TRANSFER_DESCRIPTION = (
    "Call this tool to notify the hotel manager about a completed or escalated lead.\n\n"
    "Call when ANY of these happen:\n"
    "1. Guest has confirmed room + meal plan + provided contacts → booking complete\n"
    "2. Guest is a legal entity (юрлицо), requests invoice or contract\n"
    "3. Corporate event, conference, teambuilding, banquet request\n"
    "4. Sports camp or group training request\n"
    "5. Complaint, conflict, or refund request\n"
    "6. get_room_options returns {\"error\": \"transfer_to_manager\"} for groups > 10 → "
    "YOU MUST CALL THIS TOOL IMMEDIATELY. Do not just tell the guest you are transferring — "
    "actually call this tool first, then tell the guest.\n"
    "7. Guest asks a question you cannot answer from the knowledge base\n\n"
    "IMPORTANT: Whenever you say \"I will transfer you to the manager\" or \"передам менеджеру\" "
    "or any equivalent phrase — you MUST call this tool in the same turn. Never say those words "
    "without calling the tool. Saying the words without calling the tool is not a transfer.\n\n"
    "This tool sends a Telegram notification to the manager with a structured summary.\n"
    "Always call this tool before or immediately after telling the guest the transfer is happening — "
    "never ask the guest to wait."
)

ROOM_IMAGES_DESCRIPTION = (
    "Send photos of hotel rooms to the guest. "
    "Call this when a guest asks to see a room, asks what a room looks like, or requests photos. "
    "Infer the room category from context: 1-2 guests → standard_queen or standard_twin; "
    "3-4 guests or guest mentions 'комфорт'/'comfort' → comfort; "
    "family with confirmed children → family. "
    "Pass multiple categories when the guest asks to see all rooms. "
    "Photos are sent directly to the guest — compose a natural reply referencing them."
)

FAMILY_ROOM_DESCRIPTION = (
    "Use ONLY when guest mentions children, kids, baby, toddler, son, daughter, family, "
    "or any indication they are travelling with minors. "
    "Returns family room options only. "
    "guest_count should be adults only — do not count children under 6."
)

MEAL_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "room_type": {
            "type": "string",
            "description": "Exact selected room type from get_room_options/get_family_room, usually room_type_key.",
        },
        "guest_count": {
            "type": "integer",
            "description": "Number of adult guests used for the selected room pricing.",
        },
        "checkin_date": {
            "type": "string",
            "description": "Check-in date in YYYY-MM-DD format.",
        },
    },
    "required": ["room_type", "guest_count"],
}


def update_tool_descriptions(apps, schema_editor):
    AITool = apps.get_model('flows', 'AITool')
    AgentConfig = apps.get_model('flows', 'AgentConfig')
    FlowCard = apps.get_model('flows', 'FlowCard')

    tool_updates = {
        'get_room_options': {
            'display_name': 'Get Room Options',
            'description': ROOM_OPTIONS_DESCRIPTION,
        },
        'get_meal_plan_pricing': {
            'display_name': 'Get Meal Plan Pricing',
            'description': MEAL_PLAN_DESCRIPTION,
            'parameters_schema': MEAL_PLAN_SCHEMA,
        },
        'transfer_to_manager': {
            'display_name': 'Transfer to Manager',
            'description': TRANSFER_DESCRIPTION,
        },
        'get_room_images': {
            'display_name': 'Send Room Photos',
            'description': ROOM_IMAGES_DESCRIPTION,
        },
        'get_family_room': {
            'display_name': 'Get Family Room',
            'description': FAMILY_ROOM_DESCRIPTION,
        },
    }

    for name, defaults in tool_updates.items():
        AITool.objects.update_or_create(
            organization=None,
            name=name,
            defaults={**defaults, 'is_enabled': True},
        )

    for agent_name in ('booking', 'consultant'):
        for agent in AgentConfig.objects.filter(name=agent_name):
            tools = list(agent.tools or [])
            if 'get_meal_plan_pricing' not in tools:
                insert_at = tools.index('get_family_room') + 1 if 'get_family_room' in tools else len(tools)
                tools.insert(insert_at, 'get_meal_plan_pricing')
                agent.tools = tools
                agent.save(update_fields=['tools', 'updated_at'])

    meal_markers = ('meal', 'питан', 'рацион', 'завтрак', 'ужин')
    for card in FlowCard.objects.all():
        title = f"{card.title or ''} {card.goal or ''}".lower()
        tools = list(card.allowed_tools or [])
        if tools and any(marker in title for marker in meal_markers) and 'get_meal_plan_pricing' not in tools:
            insert_at = tools.index('get_family_room') + 1 if 'get_family_room' in tools else len(tools)
            tools.insert(insert_at, 'get_meal_plan_pricing')
            card.allowed_tools = tools
            card.save(update_fields=['allowed_tools'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('flows', '0024_alter_managertransferconfig_notification_template'),
    ]

    operations = [
        migrations.RunPython(update_tool_descriptions, noop),
    ]
