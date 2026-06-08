from django.db import migrations


def remove_tool(apps, schema_editor):
    AITool = apps.get_model('flows', 'AITool')
    AITool.objects.filter(name='send_media').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('flows', '0013_seed_send_media_tool'),
    ]

    operations = [
        migrations.RunPython(remove_tool, migrations.RunPython.noop),
    ]
