from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hotel_info', '0015_roomcombinationnote_is_hidden'),
    ]

    operations = [
        migrations.AddField(
            model_name='roompricing',
            name='guest_type',
            field=models.CharField(
                choices=[('any', 'Any'), ('family', 'Family')],
                default='any',
                help_text='any = standard/comfort rooms; family = family rooms (only suggested when kids are present)',
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name='roomcombinationnote',
            name='combination_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('Основной', 'Основной'),
                    ('Альтернатива', 'Альтернатива'),
                    ('Семейный', 'Семейный'),
                ],
                help_text='Manually set type; null = auto-assigned from pricing',
                max_length=20,
                null=True,
            ),
        ),
    ]
