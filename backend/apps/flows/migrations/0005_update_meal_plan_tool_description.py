from django.db import migrations

NEW_DESCRIPTION = (
    "Look up meal plan prices for a specific room type. "
    "Call this after room selection AND whenever the guest asks ANY question about "
    "food, meals, питание, dining, or что включено в стоимость. "
    "This is the ONLY authoritative source for meal pricing — "
    "never answer food questions from memory. "
    "Returns total_price_per_night for each meal plan — this is the COMPLETE all-in nightly rate "
    "(room + meals combined). It is NOT an add-on fee. Do NOT subtract the room base price. "
    "Quote total_price_per_night directly as the new rate: 'с полупансионом — 8 800 сом/ночь'. "
    "Never do arithmetic with the room price. Never present a delta. Just quote total_price_per_night."
)


def update_description(apps, schema_editor):
    AITool = apps.get_model('flows', 'AITool')
    AITool.objects.filter(name='get_meal_plan_pricing').update(description=NEW_DESCRIPTION)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('flows', '0004_alter_flowcard_message_template'),
    ]

    operations = [
        migrations.RunPython(update_description, noop),
    ]
