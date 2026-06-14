from django.db import migrations, models


def copy_is_weekend_to_day_type(apps, schema_editor):
    RoomPricing = apps.get_model('hotel_info', 'RoomPricing')
    RoomPricing.objects.filter(is_weekend=True).update(day_type='weekend')
    # is_weekend=False rows keep the default 'weekday'


def reverse_day_type_to_is_weekend(apps, schema_editor):
    RoomPricing = apps.get_model('hotel_info', 'RoomPricing')
    RoomPricing.objects.filter(day_type='weekend').update(is_weekend=True)
    RoomPricing.objects.exclude(day_type='weekend').update(is_weekend=False)


class Migration(migrations.Migration):

    dependencies = [
        ('hotel_info', '0003_alter_roompricing_options_roompricing_is_weekend_and_more'),
    ]

    operations = [
        # 1. Add the new field with a default so existing rows get 'weekday'
        migrations.AddField(
            model_name='roompricing',
            name='day_type',
            field=models.CharField(
                choices=[
                    ('weekday', 'Weekday (Mon\u2013Thu)'),
                    ('weekend', 'Weekend (Fri\u2013Sun)'),
                    ('both', 'Weekday & Weekend'),
                ],
                default='weekday',
                max_length=10,
            ),
        ),
        # 2. Copy data: flip rows that had is_weekend=True to 'weekend'
        migrations.RunPython(
            copy_is_weekend_to_day_type,
            reverse_code=reverse_day_type_to_is_weekend,
        ),
        # 3. Remove the old boolean column
        migrations.RemoveField(
            model_name='roompricing',
            name='is_weekend',
        ),
        # 4. Update model ordering to use day_type
        migrations.AlterModelOptions(
            name='roompricing',
            options={'ordering': ['room_type', 'persons', 'day_type', 'meal_plan']},
        ),
    ]
