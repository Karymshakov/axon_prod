from django.db import migrations


def backfill_roles(apps, schema_editor):
    User = apps.get_model('users', 'User')
    User.objects.filter(is_admin=True).update(role='admin')


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_add_role_field'),
    ]

    operations = [
        migrations.RunPython(backfill_roles, migrations.RunPython.noop),
    ]
