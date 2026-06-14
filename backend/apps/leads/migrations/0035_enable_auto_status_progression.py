from django.db import migrations


def enable_auto_status_progression(apps, schema_editor):
    AIConfig = apps.get_model('leads', 'AIConfig')
    config = AIConfig.objects.first()
    if config:
        config.auto_status_progression = True
        config.save()


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0034_alter_aiconfig_system_prompt'),
    ]

    operations = [
        migrations.RunPython(enable_auto_status_progression, migrations.RunPython.noop),
    ]
