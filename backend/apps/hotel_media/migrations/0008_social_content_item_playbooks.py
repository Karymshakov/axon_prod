import logging

from django.db import migrations, models


logger = logging.getLogger(__name__)


def migrate_playbook_keys_to_m2m(apps, schema_editor):
    """Best-effort match of legacy free-text playbook_keys against real Playbook
    names within the same organization. Keys that don't match any playbook are
    dropped (they were never validated against real data in the first place)."""
    SocialContentItem = apps.get_model('hotel_media', 'SocialContentItem')
    Playbook = apps.get_model('hotel_info', 'Playbook')

    for item in SocialContentItem.objects.exclude(playbook_keys=[]).iterator():
        keys = item.playbook_keys if isinstance(item.playbook_keys, list) else []
        if not keys:
            continue
        org_playbooks = {
            pb.name.strip().casefold(): pb
            for pb in Playbook.objects.filter(organization_id=item.organization_id)
        }
        matched = []
        for key in keys:
            playbook = org_playbooks.get(str(key).strip().casefold())
            if playbook:
                matched.append(playbook)
            else:
                logger.warning(
                    'SocialContentItem %s: playbook_key %r has no matching Playbook in org %s',
                    item.id, key, item.organization_id,
                )
        if matched:
            item.playbooks.set(matched)


class Migration(migrations.Migration):

    dependencies = [
        ('hotel_media', '0007_remove_inbound_social_content'),
        ('hotel_info', '0024_automation_templates_and_booking_rules'),
    ]

    operations = [
        migrations.AddField(
            model_name='socialcontentitem',
            name='playbooks',
            field=models.ManyToManyField(
                blank=True,
                help_text='Playbooks to prefer when a guest replies to this content',
                related_name='social_content_items',
                to='hotel_info.playbook',
            ),
        ),
        migrations.RunPython(
            migrate_playbook_keys_to_m2m,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name='socialcontentitem',
            name='playbook_keys',
        ),
    ]
