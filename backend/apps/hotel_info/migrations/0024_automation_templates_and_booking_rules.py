from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion


DEFAULT_TEMPLATES = {
    'telegram_start': {
        'ru': 'Здравствуйте! 🌊 Рады приветствовать вас в Nomad Camp. Чем могу помочь?',
        'ky': 'Саламатсызбы! 🌊 Nomad Camp мейманканасына кош келиңиз. Сизге кандай жардам бере алам?',
        'en': 'Hello! 🌊 Welcome to Nomad Camp. How can I help?',
    },
    'story_mention_ack': {
        'ru': 'Спасибо, что отметили нас в сторис! 🌊 Нам очень приятно.',
        'ky': 'Бизди сториске белгилегениңиз үчүн рахмат! 🌊 Бизге абдан жагымдуу болду.',
        'en': 'Thank you for mentioning us in your story! 🌊 We really appreciate it.',
    },
    'story_courtesy_close': {
        'ru': 'И вам спасибо! Будем рады видеть вас снова 🌊',
        'ky': 'Сизге да рахмат! Дагы жолугушканга кубанычтабыз 🌊',
        'en': 'Thank you too! We will be happy to welcome you again 🌊',
    },
    'pricing_unavailable': {
        'ru': 'На эти даты тариф нужно подтвердить вручную. Запрос уже передан менеджеру; он уточнит стоимость.',
        'ky': 'Бул күндөргө тарифти кол менен ырастоо керек. Сурам менеджерге өткөрүлдү; ал бааны тактайт.',
        'en': 'The rate for these dates needs manual confirmation. The request has been sent to a manager for verification.',
    },
    'pricing_check_required': {
        'ru': 'Сейчас система не подтвердила тариф. Данные вашего запроса сохранены; могу передать проверку менеджеру.',
        'ky': 'Азыр система тарифти ырастаган жок. Сурамыңыздын маалыматы сакталды; текшерүүнү менеджерге өткөрүп бере алам.',
        'en': 'The system could not verify the rate just now. Your request details are saved; I can ask a manager to check it.',
    },
    'manager_handoff': {
        'ru': 'Запрос передан менеджеру. Он проверит детали и ответит вам.',
        'ky': 'Сурам менеджерге өткөрүлдү. Ал маалыматты текшерип, сизге жооп берет.',
        'en': 'The request has been sent to a manager. They will review the details and reply.',
    },
    'media_unavailable': {
        'ru': 'Сейчас фото не загрузились. Могу пока подробно рассказать о номере или передать запрос менеджеру.',
        'ky': 'Азыр сүрөттөр жүктөлбөй калды. Азырынча номер тууралуу айтып берейин же менеджерге өткөрүп берейин.',
        'en': 'The photos did not load just now. I can describe the room or pass the request to a manager.',
    },
}


def seed_defaults(apps, schema_editor):
    Organization = apps.get_model('organizations', 'Organization')
    Template = apps.get_model('hotel_info', 'AutomationMessageTemplate')
    BookingRules = apps.get_model('hotel_info', 'BookingRules')
    for org in Organization.objects.all():
        BookingRules.objects.get_or_create(
            organization=org,
            defaults={
                'child_free_max_age': Decimal('6.0'),
                'child_free_requires_no_bed': True,
                'family_rooms_self_service_enabled': False,
                'followup_delay_minutes': 10,
            },
        )
        for event_key, translations in DEFAULT_TEMPLATES.items():
            for language, text in translations.items():
                channel = 'telegram' if event_key == 'telegram_start' else (
                    'instagram' if event_key.startswith('story_') else 'all'
                )
                Template.objects.get_or_create(
                    organization=org,
                    event_key=event_key,
                    language=language,
                    channel=channel,
                    defaults={'text': text, 'is_active': True},
                )


class Migration(migrations.Migration):
    dependencies = [
        ('hotel_info', '0023_replytemplatecategory_replytemplate'),
        ('organizations', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AutomationMessageTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_key', models.CharField(choices=[('telegram_start', 'Telegram /start greeting'), ('story_mention_ack', 'Instagram story mention acknowledgement'), ('story_courtesy_close', 'Instagram courtesy reply after acknowledgement'), ('pricing_unavailable', 'Current price is unavailable'), ('pricing_check_required', 'Price could not be verified'), ('manager_handoff', 'Manager handoff confirmation'), ('media_unavailable', 'Requested media is unavailable')], max_length=50)),
                ('language', models.CharField(choices=[('ru', 'Русский'), ('ky', 'Кыргызча'), ('en', 'English')], default='ru', max_length=5)),
                ('channel', models.CharField(choices=[('all', 'All'), ('telegram', 'Telegram'), ('instagram', 'Instagram'), ('whatsapp', 'WhatsApp')], default='all', max_length=20)),
                ('text', models.TextField()),
                ('is_active', models.BooleanField(default=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('organization', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='organizations.organization')),
            ],
            options={'ordering': ['event_key', 'language', 'channel']},
        ),
        migrations.CreateModel(
            name='BookingRules',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('child_free_max_age', models.DecimalField(decimal_places=1, default=6, help_text='Maximum child age for free stay without a separate bed.', max_digits=4)),
                ('child_free_requires_no_bed', models.BooleanField(default=True)),
                ('family_rooms_self_service_enabled', models.BooleanField(default=False, help_text='When disabled, family rooms are never offered automatically.')),
                ('followup_delay_minutes', models.PositiveIntegerField(default=10)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('organization', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='booking_rules', to='organizations.organization')),
            ],
            options={'verbose_name': 'Booking Rules', 'verbose_name_plural': 'Booking Rules'},
        ),
        migrations.AddConstraint(
            model_name='automationmessagetemplate',
            constraint=models.UniqueConstraint(fields=('organization', 'event_key', 'language', 'channel'), name='uniq_automation_message_template'),
        ),
        migrations.RunPython(seed_defaults, migrations.RunPython.noop),
    ]
