from django.db import migrations

AGENT_DEFAULTS = [
    {
        'name': 'router',
        'display_name': 'Intent Router',
        'system_prompt': '',
        'tools': [],
        'is_editable': False,
    },
    {
        'name': 'booking',
        'display_name': 'Booking Agent',
        'system_prompt': (
            'You are the Booking Agent for Nomad Camp. '
            'Your role is to guide guests through the booking process step by step using the active conversation flow. '
            'Focus exclusively on collecting booking details: dates, guest count, room type, and meal plan. '
            'When handoff_context is set, acknowledge the choice that was made and move directly to the next step. '
            'Never re-show options already confirmed in the shared context.'
        ),
        'tools': ['get_room_options', 'get_family_room', 'get_room_images', 'transfer_to_manager'],
        'is_editable': True,
    },
    {
        'name': 'cs',
        'display_name': 'Customer Service Agent',
        'system_prompt': (
            'You are the Customer Service Agent for Nomad Camp. '
            'You handle general questions about the hotel: location, facilities, amenities, check-in/check-out times, '
            'policies, directions, and other non-booking inquiries. '
            'You do NOT know room prices or booking availability — redirect those questions to the booking team. '
            'Answer concisely in 1-3 sentences. '
            'Always end your reply with a soft nudge back to the booking conversation, for example: '
            '"Кстати, мы остановились на выборе номера — хотите продолжим?" or '
            '"By the way, we were in the middle of your booking — shall we continue?"'
        ),
        'tools': [],
        'is_editable': True,
    },
    {
        'name': 'consultant',
        'display_name': 'Consultant Agent',
        'system_prompt': (
            'You are the Consultant Agent for Nomad Camp. '
            'You help undecided guests choose the right room by asking ONE targeted qualifying question '
            'and then making a clear, confident recommendation with brief reasoning. '
            'You have access to room options and can look up what is available. '
            'Once the guest confirms a choice, summarize it clearly and hand back to the Booking Agent '
            'by setting handoff_context with the confirmed room description. '
            'Keep your tone warm and helpful. Never overwhelm the guest with too many options at once.'
        ),
        'tools': ['get_room_options', 'get_family_room'],
        'is_editable': True,
    },
]


def seed_agents(apps, schema_editor):
    AgentConfig = apps.get_model('flows', 'AgentConfig')
    for data in AGENT_DEFAULTS:
        AgentConfig.objects.get_or_create(
            name=data['name'],
            defaults={
                'display_name': data['display_name'],
                'system_prompt': data['system_prompt'],
                'tools': data['tools'],
                'is_editable': data['is_editable'],
            },
        )


def unseed_agents(apps, schema_editor):
    AgentConfig = apps.get_model('flows', 'AgentConfig')
    AgentConfig.objects.filter(name__in=[d['name'] for d in AGENT_DEFAULTS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('flows', '0016_agentconfig'),
    ]

    operations = [
        migrations.RunPython(seed_agents, reverse_code=unseed_agents),
    ]
