from django.db import migrations


FAMILY_PROPERTIES = {
    'guest_count': {
        'type': 'integer',
        'description': 'Number of adult guests. Do not count children under 6.',
    },
    'children_ages': {
        'type': 'array',
        'items': {'type': 'number', 'minimum': 0, 'maximum': 17},
        'description': (
            'Ages of children in years. Use a decimal for an infant under one year, '
            'for example 2 months = 0.17.'
        ),
    },
    'single_room_required': {
        'type': 'boolean',
        'description': (
            'True when the family explicitly requires everyone to stay together '
            'in one room. Never return multiple rooms when true.'
        ),
    },
    'checkin_date': {
        'type': 'string',
        'description': 'Check-in date in YYYY-MM-DD format.',
    },
    'checkout_date': {
        'type': 'string',
        'description': 'Check-out date in YYYY-MM-DD format.',
    },
}


def repair_family_room_schema(apps, schema_editor):
    AITool = apps.get_model('flows', 'AITool')
    for tool in AITool.objects.filter(name='get_family_room').iterator():
        schema = dict(tool.parameters_schema or {})
        schema['type'] = 'object'
        properties = dict(schema.get('properties') or {})
        for name, definition in FAMILY_PROPERTIES.items():
            properties.setdefault(name, definition)
        schema['properties'] = properties
        required = list(schema.get('required') or [])
        if 'guest_count' not in required:
            required.append('guest_count')
        schema['required'] = required
        tool.parameters_schema = schema
        tool.save(update_fields=['parameters_schema'])


class Migration(migrations.Migration):
    dependencies = [
        ('flows', '0026_add_family_composition_tool_fields'),
    ]

    operations = [
        migrations.RunPython(repair_family_room_schema, migrations.RunPython.noop),
    ]
