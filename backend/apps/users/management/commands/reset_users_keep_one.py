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
            '--main-org', default='Nomad Camp',
            help='Name of the organization to set as the kept user\'s current_organization '
                 '(the one they land in / create managers under by default).',
        )
        parser.add_argument(
            '--confirm', action='store_true',
            help='Apply the changes. Without this flag, only prints what would happen.',
        )

    def handle(self, *args, **options):
        from apps.organizations.models import Organization, OrganizationMember

        User = get_user_model()
        keep_email = options['keep_email']
        main_org_name = options['main_org']
        confirm = options['confirm']

        try:
            keep_user = User.objects.get(email__iexact=keep_email)
        except User.DoesNotExist:
            raise CommandError(f'No user found with email {keep_email!r} — aborting.')

        try:
            main_org = Organization.objects.get(name__iexact=main_org_name)
        except Organization.DoesNotExist:
            raise CommandError(f'No organization found named {main_org_name!r} — aborting.')
        except Organization.MultipleObjectsReturned:
            raise CommandError(
                f'Multiple organizations named {main_org_name!r} — pass --main-org with the exact one '
                f'or resolve the duplicate first.'
            )

        other_users = User.objects.exclude(pk=keep_user.pk).order_by('email')
        orgs_to_reassign = Organization.objects.exclude(owner=keep_user)

        self.stdout.write(self.style.WARNING(
            f'{"APPLY" if confirm else "DRY RUN"} — keeping {keep_user.email} (id={keep_user.pk})'
        ))
        self.stdout.write(
            f'Main organization (current_organization for {keep_user.email}): '
            f'{main_org.name!r} (id={main_org.pk})'
        )
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

            # Belt-and-suspenders: guarantee membership in --main-org even if it was
            # already owned by keep_user before this run (and so skipped the loop above).
            OrganizationMember.objects.get_or_create(
                organization=main_org,
                user=keep_user,
                defaults={'role': OrganizationMember.Role.OWNER},
            )

            keep_user.is_superadmin = True
            keep_user.is_staff = True
            keep_user.is_superuser = True
            keep_user.is_active = True
            keep_user.role = User.Role.ADMIN
            # Explicitly pin current_organization to --main-org (default: Nomad Camp)
            # rather than leaving it to whatever it happened to be before — this is
            # the org new managers get attached to when created via the admin portal
            # (AdminUserCreateSerializer.create() uses request.user.current_organization).
            keep_user.current_organization = main_org
            keep_user.save()

        self.stdout.write(self.style.SUCCESS(
            f'Done. Deleted {deleted_count} user(s). '
            f'{keep_user.email} is now super-admin, owns {orgs_to_reassign.count()} organization(s), '
            f'and is attached to {main_org.name!r} (managers created via the admin portal will join this org).'
        ))
