from django.db import migrations, models
import django.db.models.deletion


def assign_existing_notes_to_first_org(apps, schema_editor):
    Organization = apps.get_model('organizations', 'Organization')
    RoomCombinationNote = apps.get_model('hotel_info', 'RoomCombinationNote')
    org = Organization.objects.order_by('id').first()
    if org is not None:
        RoomCombinationNote.objects.filter(organization__isnull=True).update(organization=org)


class Migration(migrations.Migration):

    dependencies = [
        ('hotel_info', '0020_playbook_expires_at'),
        ('organizations', '0004_organization_deleted_at_organization_is_deleted'),
    ]

    operations = [
        migrations.AddField(
            model_name='roomcombinationnote',
            name='organization',
            field=models.ForeignKey(
                blank=True,
                db_index=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='+',
                to='organizations.organization',
            ),
        ),
        migrations.RunPython(assign_existing_notes_to_first_org, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name='roomcombinationnote',
            unique_together={('organization', 'guest_count', 'combination_index')},
        ),
    ]
