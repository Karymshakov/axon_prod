from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('hotel_info', '0020_playbook_expires_at'),
        ('organizations', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReplyTemplateCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('order', models.PositiveIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('organization', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='reply_categories', to='organizations.organization')),
            ],
            options={
                'verbose_name': 'Reply Template Category',
                'verbose_name_plural': 'Reply Template Categories',
                'ordering': ['order', 'id'],
            },
        ),
        migrations.CreateModel(
            name='ReplyTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=120)),
                ('text', models.TextField()),
                ('channel', models.CharField(blank=True, default='all', help_text='all/telegram/whatsapp/instagram', max_length=30)),
                ('tags', models.JSONField(blank=True, default=list)),
                ('order', models.PositiveIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='templates', to='hotel_info.replytemplatecategory')),
                ('organization', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='reply_templates', to='organizations.organization')),
            ],
            options={
                'verbose_name': 'Reply Template',
                'verbose_name_plural': 'Reply Templates',
                'ordering': ['order', 'id'],
            },
        ),
    ]
