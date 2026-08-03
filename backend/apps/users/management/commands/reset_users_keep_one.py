from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = (
        'Delete every user except --keep-email, reassign ownership of all '
        'organizations to that user, and promote them to platform super-admin. '
        'Defaults to a dry run — pass --confirm to actually apply changes.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--keep-email', default='erdem@axondigital.com')
        parser.add_argument(
            '--confirm', action='store_true',
            help='Apply the changes. Without this flag, only prints what would happen.',
        )

    def handle(self, *args, **options):
        from apps.organizations.models import Organization, OrganizationMember

        User = get_user_model()
        keep_email = options['keep_email']
        confirm = options['confirm']

        try:
            keep_user = User.objects.get(email__iexact=keep_email)
        except User.DoesNotExist:
            raise CommandError(f'No user found with email {keep_email!r} — aborting.')

        other_users = User.objects.exclude(pk=keep_user.pk).order_by('email')
        orgs_to_reassign = Organization.objects.exclude(owner=keep_user)

        self.stdout.write(self.style.WARNING(
            f'{"APPLY" if confirm else "DRY RUN"} — keeping {keep_user.email} (id={keep_user.pk})'
        ))
        self.stdout.write(f'Organizations to reassign to {keep_user.email}: {orgs_to_reassign.count()}')
        for org in orgs_to_reassign:
            self.stdout.write(f'  - {org.name!r} (id={org.pk}), current owner: {org.owner.email}')
        self.stdout.write(f'Users to delete: {other_users.count()}')
        for user in other_users:
            self.stdout.write(f'  - {user.email} (id={user.pk}, role={user.role})')

        if not confirm:
            self.stdout.write(self.style.NOTICE(
                'Dry run only — no changes made. Re-run with --confirm to apply.'
            ))
            return

        with transaction.atomic():
            for org in orgs_to_reassign:
                org.owner = keep_user
                org.save(update_fields=['owner'])
                OrganizationMember.objects.get_or_create(
                    organization=org,
                    user=keep_user,
                    defaults={'role': OrganizationMember.Role.OWNER},
                )

            deleted_count, _ = other_users.delete()

            keep_user.is_superadmin = True
            keep_user.is_staff = True
            keep_user.is_superuser = True
            keep_user.is_active = True
            keep_user.role = User.Role.ADMIN
            if keep_user.current_organization_id is None:
                main_org = Organization.objects.filter(owner=keep_user).order_by('id').first()
                if main_org:
                    keep_user.current_organization = main_org
            keep_user.save()

        self.stdout.write(self.style.SUCCESS(
            f'Done. Deleted {deleted_count} user(s). '
            f'{keep_user.email} is now super-admin and owns {orgs_to_reassign.count()} organization(s).'
        ))
