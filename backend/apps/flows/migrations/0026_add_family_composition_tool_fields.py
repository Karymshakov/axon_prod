from django.db import migrations


def add_family_composition_fields(apps, schema_editor):
    AITool = apps.get_model('flows', 'AITool')
    for tool in AITool.objects.filter(name='get_family_room'):
        schema = dict(tool.parameters_schema or {})
        properties = dict(schema.get('properties') or {})
        properties.update({
            'children_ages': {
                'type': 'array',
                'items': {'type': 'number', 'minimum': 0, 'maximum': 17},
                'description': (
                    'Ages of children in years. Use a decimal for an infant '
                    'under one year, for example 2 months = 0.17.'
                ),
            },
            'single_room_required': {
                'type': 'boolean',
                'description': (
                    'True when the family explicitly requires everyone to stay '
                    'together in one room. Never return multiple rooms when true.'
                ),
            },
        })
        schema['type'] = 'object'
        schema['properties'] = properties
        required = list(schema.get('required') or [])
        if 'guest_count' not in required:
            required.append('guest_count')
        schema['required'] = required
        tool.parameters_schema = schema
        tool.save(update_fields=['parameters_schema', 'updated_at'])


def remove_family_composition_fields(apps, schema_editor):
    AITool = apps.get_model('flows', 'AITool')
    for tool in AITool.objects.filter(name='get_family_room'):
        schema = dict(tool.parameters_schema or {})
        properties = dict(schema.get('properties') or {})
        properties.pop('children_ages', None)
        properties.pop('single_room_required', None)
        schema['properties'] = properties
        tool.parameters_schema = schema
        tool.save(update_fields=['parameters_schema', 'updated_at'])


class Migration(migrations.Migration):
    dependencies = [
        ('flows', '0025_update_booking_tool_descriptions'),
    ]

    operations = [
        migrations.RunPython(add_family_composition_fields, remove_family_composition_fields),
    ]
