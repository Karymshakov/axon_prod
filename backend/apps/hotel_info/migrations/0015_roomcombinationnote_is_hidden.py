from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hotel_info', '0014_roomcombinationnote_is_custom_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='roomcombinationnote',
            name='is_hidden',
            field=models.BooleanField(default=False, help_text='True hides this combination from the API and AI responses'),
        ),
    ]
