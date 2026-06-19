from django.core.management.base import BaseCommand
from django.db.models import Count

from apps.hotel_media.models import MediaFingerprint
from apps.leads.services.media_context import find_best_fingerprint_context
from apps.organizations.models import Organization


class Command(BaseCommand):
    help = 'Diagnose perceptual-hash matching for an incoming media file.'

    def add_arguments(self, parser):
        parser.add_argument('image_path')
        parser.add_argument('--organization-id', type=int, default=None)

    def handle(self, *args, **options):
        organization = None
        if options.get('organization_id'):
            organization = Organization.objects.get(id=options['organization_id'])

        queryset = MediaFingerprint.objects.all()
        if organization is not None:
            queryset = queryset.filter(organization=organization)

        self.stdout.write(f'Fingerprints total: {queryset.count()}')
        for row in queryset.values('hash_kind').annotate(count=Count('id')).order_by('hash_kind'):
            self.stdout.write(f"  {row['hash_kind']}: {row['count']}")

        context = find_best_fingerprint_context(options['image_path'], organization=organization)
        if not context:
            self.stdout.write(self.style.WARNING('No accepted match. Check logs for best_seen distance.'))
            return

        self.stdout.write(self.style.SUCCESS('Accepted match:'))
        for key in [
            'source',
            'hotel_media_item_id',
            'hotel_media_photo_id',
            'social_content_id',
            'title',
            'category',
            'room_category',
            'hash_kind',
            'hash_distance',
            'confidence',
            'needs_clarification',
        ]:
            self.stdout.write(f'  {key}: {context.get(key)}')

