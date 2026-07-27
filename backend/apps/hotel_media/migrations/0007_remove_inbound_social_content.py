from django.db import migrations


def remove_inbound_social_content(apps, schema_editor):
    SocialContentItem = apps.get_model('hotel_media', 'SocialContentItem')
    SocialContentItem.objects.filter(source='webhook').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('hotel_media', '0006_social_content_automation'),
    ]

    operations = [
        migrations.RunPython(
            remove_inbound_social_content,
            migrations.RunPython.noop,
        ),
    ]
