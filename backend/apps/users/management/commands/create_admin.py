import secrets
import string

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create or update a superuser with a generated password'

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True)
        parser.add_argument('--password', default=None)

    def handle(self, *args, **options):
        User = get_user_model()
        email = options['email']
        if options['password']:
            password = options['password']
        else:
            alphabet = string.ascii_letters + string.digits + '!@#$%^&*'
            password = ''.join(secrets.choice(alphabet) for _ in range(20))

        user, created = User.objects.get_or_create(email=email)
        user.set_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.role = 'admin'
        user.save()

        action = 'Created' if created else 'Updated'
        self.stdout.write(f'{action} superuser: {email}')
        self.stdout.write(f'Password: {password}')
