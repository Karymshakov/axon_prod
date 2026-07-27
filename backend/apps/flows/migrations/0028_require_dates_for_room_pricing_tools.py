from django.db import migrations


REQUIRED_PROPERTIES = {
    'guest_count': {
        'type': 'integer',
        'description': (
            'Number of chargeable adult guests. Do not count children under 6.'
        ),
    },
    'checkin_date': {
        'type': 'string',
        'description': 'Exact check-in date in YYYY-MM-DD format.',
    },
    'checkout_date': {
        'type': 'string',
        'description': 'Exact check-out date in YYYY-MM-DD format.',
    },
}


def require_room_pricing_dates(apps, schema_editor):
    AITool = apps.get_model('flows', 'AITool')
    for tool in AITool.objects.filter(
        name__in=('get_room_options', 'get_family_room')
    ).iterator():
        schema = dict(tool.parameters_schema or {})
        schema['type'] = 'object'
        properties = dict(schema.get('properties') or {})
        for name, definition in REQUIRED_PROPERTIES.items():
            properties.setdefault(name, definition)
        schema['properties'] = properties
        required = list(schema.get('required') or [])
        for name in ('guest_count', 'checkin_date', 'checkout_date'):
            if name not in required:
                required.append(name)
        schema['required'] = required
        tool.parameters_schema = schema
        tool.save(update_fields=['parameters_schema'])


class Migration(migrations.Migration):
    dependencies = [
        ('flows', '0027_repair_family_room_tool_schema'),
    ]

    operations = [
        migrations.RunPython(require_room_pricing_dates, migrations.RunPython.noop),
    ]
