from django.core.management.base import BaseCommand

from apps.hotel_media.models import HotelMediaItem, SocialContentItem
from apps.hotel_media.services import rebuild_hotel_media_item_fingerprints, rebuild_social_content_fingerprints


class Command(BaseCommand):
    help = 'Rebuild perceptual fingerprints for hotel media and linked social content.'

    def add_arguments(self, parser):
        parser.add_argument('--organization-id', type=int, default=None)
        parser.add_argument('--social-only', action='store_true')
        parser.add_argument('--hotel-media-only', action='store_true')

    def handle(self, *args, **options):
        org_id = options.get('organization_id')
        social_only = options.get('social_only')
        hotel_media_only = options.get('hotel_media_only')

        total = 0
        if not social_only:
            items = HotelMediaItem.objects.filter(is_active=True)
            if org_id:
                items = items.filter(organization_id=org_id)
            for item in items.iterator():
                created = rebuild_hotel_media_item_fingerprints(item)
                total += created
                self.stdout.write(f'HotelMediaItem {item.id}: {created} fingerprints')

        if not hotel_media_only:
            social_items = SocialContentItem.objects.filter(is_active=True)
            if org_id:
                social_items = social_items.filter(organization_id=org_id)
            for item in social_items.iterator():
                created = rebuild_social_content_fingerprints(item)
                total += created
                self.stdout.write(f'SocialContentItem {item.id}: {created} fingerprints')

        self.stdout.write(self.style.SUCCESS(f'Done. Created {total} fingerprints.'))

