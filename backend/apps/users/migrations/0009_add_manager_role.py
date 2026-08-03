from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0008_alter_user_role'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(choices=[('admin', 'Admin / Manager'), ('manager', 'Manager'), ('support', 'Support'), ('tax_accountant', 'Tax Accountant')], default='support', max_length=50),
        ),
    ]
