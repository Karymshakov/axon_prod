from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.hotel_info.models import RoomPricing
from apps.organizations.models import Organization

ORG_SLUG = 'nomad-camp'
OLD_NAME = 'семейный два номера'
NEW_NAME = 'семейный номер'


class Command(BaseCommand):
    help = (
        'There is only one family room product ("семейный номер"), not two variants — '
        'rename the RoomPricing category from "семейный два номера" to match. Must run '
        'together with the matching COMBINATIONS_MAP rename in pricing_utils.py.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        try:
            org = Organization.objects.get(slug=ORG_SLUG)
        except Organization.DoesNotExist:
            raise CommandError(f'Organization with slug={ORG_SLUG!r} not found')

        with transaction.atomic():
            row = RoomPricing.objects.filter(
                organization=org, kategoria_nomera__iexact=OLD_NAME,
            ).first()
            if row is None:
                already = RoomPricing.objects.filter(
                    organization=org, kategoria_nomera__iexact=NEW_NAME,
                ).exists()
                if already:
                    self.stdout.write(self.style.WARNING('Already renamed, nothing to do.'))
                    return
                raise CommandError(f'No RoomPricing row named {OLD_NAME!r} found')

            self.stdout.write(f'id={row.id}: {row.kategoria_nomera!r} -> {NEW_NAME!r}')
            row.kategoria_nomera = NEW_NAME
            if not dry_run:
                row.save(update_fields=['kategoria_nomera', 'updated_at'])

            if dry_run:
                self.stdout.write(self.style.WARNING('DRY RUN — rolling back.'))
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS('Done.' if not dry_run else 'Dry run complete.'))
