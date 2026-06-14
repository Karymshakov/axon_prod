from django.db import migrations, models


def convert_tax_accountants_to_support(apps, schema_editor):
    User = apps.get_model('users', 'User')
    User.objects.filter(role='tax_accountant').update(role='support')


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0006_alter_user_language'),
    ]

    operations = [
        migrations.RunPython(convert_tax_accountants_to_support, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(
                choices=[('admin', 'Admin'), ('support', 'Support')],
                default='support',
                max_length=50,
            ),
        ),
    ]
