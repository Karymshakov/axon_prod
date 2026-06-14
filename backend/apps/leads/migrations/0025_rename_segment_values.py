from django.db import migrations, models


def rename_segment_values_forward(apps, schema_editor):
    PipelineStage = apps.get_model('leads', 'PipelineStage')
    Lead = apps.get_model('leads', 'Lead')
    Customer = apps.get_model('leads', 'Customer')
    for Model in (PipelineStage, Lead, Customer):
        Model.objects.filter(segment='usa').update(segment='individual')
        Model.objects.filter(segment='china').update(segment='business')


def rename_segment_values_backward(apps, schema_editor):
    PipelineStage = apps.get_model('leads', 'PipelineStage')
    Lead = apps.get_model('leads', 'Lead')
    Customer = apps.get_model('leads', 'Customer')
    for Model in (PipelineStage, Lead, Customer):
        Model.objects.filter(segment='individual').update(segment='usa')
        Model.objects.filter(segment='business').update(segment='china')


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0024_remove_customer_address_and_more'),
    ]

    operations = [
        migrations.RunPython(rename_segment_values_forward, rename_segment_values_backward),
        migrations.AlterField(
            model_name='pipelinestage',
            name='segment',
            field=models.CharField(
                choices=[('individual', 'Individual'), ('business', 'Business')],
                default='individual',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='lead',
            name='segment',
            field=models.CharField(
                choices=[('individual', 'Individual'), ('business', 'Business')],
                default='individual',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='customer',
            name='segment',
            field=models.CharField(
                choices=[('individual', 'Individual'), ('business', 'Business')],
                default='individual',
                max_length=20,
            ),
        ),
    ]
