from django.core.management.base import BaseCommand

from apps.hotel_media.services import sync_instagram_social_content
from apps.organizations.models import Organization


class Command(BaseCommand):
    help = 'Sync Instagram posts/reels/stories into the social content registry.'

    def add_arguments(self, parser):
        parser.add_argument('--organization-id', type=int, default=None)

    def handle(self, *args, **options):
        organization = None
        if options.get('organization_id'):
            organization = Organization.objects.get(id=options['organization_id'])

        result = sync_instagram_social_content(organization=organization)
        self.stdout.write(self.style.SUCCESS(f"Connections: {result['connections']}"))
        self.stdout.write(f"Posts/reels synced: {result['items_synced']}")
        self.stdout.write(f"Stories synced: {result['stories_synced']}")
        self.stdout.write(f"Stories expired: {result['stories_expired']}")
        for error in result.get('errors') or []:
            self.stdout.write(self.style.WARNING(error))

