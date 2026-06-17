from django.db import migrations, models
import django.db.models.deletion


DEFAULT_CATEGORIES = [
    (
        'Общие',
        [
            ('Приветствие', 'Здравствуйте! Рады приветствовать Вас. Подскажите, пожалуйста, чем можем помочь?', 'all'),
            ('Завершение диалога', 'Спасибо за обращение! Если появятся вопросы, напишите нам в любое время.', 'all'),
        ],
    ),
    (
        'Бронирование',
        [
            ('Уточнить даты', 'Подскажите, пожалуйста, на какие даты планируете заезд и выезд?', 'all'),
            ('Уточнить гостей', 'Сколько гостей планирует проживание?', 'all'),
            ('Подтверждение заявки', 'Спасибо, данные приняли. Менеджер проверит детали и свяжется с Вами для подтверждения.', 'all'),
        ],
    ),
    (
        'Оплата',
        [
            ('Предоплата', 'Для фиксации заявки менеджер подскажет условия подтверждения и предоплаты.', 'all'),
            ('Способы оплаты', 'Оплатить можно удобным способом после подтверждения заявки менеджером.', 'all'),
        ],
    ),
]


def seed_reply_templates(apps, schema_editor):
    Organization = apps.get_model('organizations', 'Organization')
    ReplyTemplateCategory = apps.get_model('hotel_info', 'ReplyTemplateCategory')
    ReplyTemplate = apps.get_model('hotel_info', 'ReplyTemplate')

    for org in Organization.objects.all():
        for category_order, (category_name, templates) in enumerate(DEFAULT_CATEGORIES):
            category, _ = ReplyTemplateCategory.objects.get_or_create(
                organization=org,
                name=category_name,
                defaults={'order': category_order, 'is_active': True},
            )
            for template_order, (title, text, channel) in enumerate(templates):
                ReplyTemplate.objects.get_or_create(
                    organization=org,
                    category=category,
                    title=title,
                    defaults={
                        'text': text,
                        'channel': channel,
                        'order': template_order,
                        'is_active': True,
                        'tags': [],
                    },
                )


class Migration(migrations.Migration):

    dependencies = [
        ('hotel_info', '0020_playbook_expires_at'),
        ('organizations', '0004_organization_deleted_at_organization_is_deleted'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReplyTemplateCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('order', models.PositiveIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('organization', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='organizations.organization')),
            ],
        ),
        migrations.CreateModel(
            name='ReplyTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('text', models.TextField()),
                ('channel', models.CharField(max_length=50, default='all', help_text='telegram, instagram, whatsapp, all')),
                ('tags', models.JSONField(default=list, blank=True)),
                ('order', models.PositiveIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='templates', to='hotel_info.replytemplatecategory')),
                ('organization', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='organizations.organization')),
            ],
        ),
        migrations.RunPython(seed_reply_templates, migrations.RunPython.noop),
    ]
