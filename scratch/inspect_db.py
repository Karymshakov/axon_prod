import os
import sys
import django

# Set up django path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ['DATABASE_URL'] = "postgresql://postgres:admin@localhost:5432/app_dev"
django.setup()

from apps.hotel_media.models import HotelMediaItem, SocialContentItem, MediaFingerprint

print("HotelMediaItem count:", HotelMediaItem.objects.count())
for item in HotelMediaItem.objects.all():
    print(f"  ID={item.id}, Title={item.title}, RoomCategory={item.room_category}, Category={item.category}")

print("\nSocialContentItem count:", SocialContentItem.objects.count())
for item in SocialContentItem.objects.all():
    print(f"  ID={item.id}, ExternalID={item.external_id}, Title={item.title or item.caption[:30]}, Category={item.effective_category}, RoomCategory={item.effective_room_category}")

print("\nMediaFingerprint count:", MediaFingerprint.objects.count())
print("By source:")
print("  Hotel media item links:", MediaFingerprint.objects.filter(hotel_media_item__isnull=False).count())
print("  Social content item links:", MediaFingerprint.objects.filter(social_content_item__isnull=False).count())
