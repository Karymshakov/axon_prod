from django.core.management.base import BaseCommand
from apps.leads.models import Lead, LeadActivity


class Command(BaseCommand):
    help = 'Backfill last_contacted from activity timeline for leads where it is null'

    def handle(self, *args, **options):
        leads_without = Lead.objects.filter(last_contacted__isnull=True)
        total = leads_without.count()
        updated = 0
        skipped = 0

        for lead in leads_without.iterator():
            latest_activity = (
                LeadActivity.objects.filter(lead=lead)
                .order_by('-created_at')
                .values_list('created_at', flat=True)
                .first()
            )
            if latest_activity:
                Lead.objects.filter(id=lead.id).update(last_contacted=latest_activity.date())
                updated += 1
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Backfill complete: {updated} leads updated, '
                f'{skipped} leads skipped (no activity), '
                f'{total} total processed'
            )
        )
