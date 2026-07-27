from django.db import migrations


ROOM_OPTIONS_PROPERTIES = {
    'guest_count': {
        'type': 'integer',
        'description': 'Total people in the party, including children.',
    },
    'adult_count': {
        'type': 'integer',
        'description': 'Number of adults when children are present.',
    },
    'children_ages': {
        'type': 'array',
        'items': {'type': 'number', 'minimum': 0, 'maximum': 17},
        'description': 'Ages of all children in years; use a decimal for an infant.',
    },
    'one_room_required': {
        'type': 'boolean',
        'description': 'True only when the guest explicitly requires everyone to stay in one room.',
    },
}


def update_booking_tools(apps, schema_editor):
    AITool = apps.get_model('flows', 'AITool')
    AgentConfig = apps.get_model('flows', 'AgentConfig')

    for tool in AITool.objects.filter(name='get_family_room').iterator():
        tool.is_enabled = False
        tool.description = (
            'Family-room self-service is disabled. Explicit family-room requests '
            'must be transferred to a manager.'
        )
        tool.save(update_fields=['is_enabled', 'description'])

    for tool in AITool.objects.filter(name='get_room_options').iterator():
        schema = dict(tool.parameters_schema or {})
        schema['type'] = 'object'
        properties = dict(schema.get('properties') or {})
        properties.update(ROOM_OPTIONS_PROPERTIES)
        schema['properties'] = properties
        tool.parameters_schema = schema
        tool.description = (
            'Use for every automated room search, including families. Pass total '
            'guest_count plus adult_count and children_ages when children are present. '
            'A young child staying free without a separate bed must not cause an '
            'unnecessary extra room or family-room recommendation.'
        )
        tool.save(update_fields=['parameters_schema', 'description'])

    for agent in AgentConfig.objects.all().iterator():
        tools = [name for name in (agent.tools or []) if name != 'get_family_room']
        if tools != (agent.tools or []):
            agent.tools = tools
            agent.save(update_fields=['tools'])


class Migration(migrations.Migration):
    dependencies = [
        ('flows', '0028_require_dates_for_room_pricing_tools'),
    ]

    operations = [
        migrations.RunPython(update_booking_tools, migrations.RunPython.noop),
    ]
