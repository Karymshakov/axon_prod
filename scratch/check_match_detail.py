import os
import sys
import django

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ['DATABASE_URL'] = "postgresql://postgres:admin@localhost:5432/app_dev"
django.setup()

from apps.hotel_media.models import MediaFingerprint
from apps.leads.services.media_context import find_best_fingerprint_context

brain_dir = r"C:\Users\kille\.gemini\antigravity-ide\brain\038af392-e861-4635-a8ea-f0505fd421c1"
filepath = os.path.join(brain_dir, "media__1782054631555.jpg")

context = find_best_fingerprint_context(filepath)
if context:
    print("Match detail:")
    print("  hotel_media_item_id:", context.get('hotel_media_item_id'))
    print("  hotel_media_photo_id:", context.get('hotel_media_photo_id'))
    print("  hash_kind:", context.get('hash_kind'))
    print("  hash_distance:", context.get('hash_distance'))
    print("  incoming_crop_label:", context.get('incoming_crop_label'))
    
    # Query the database for the exact photo file path
    from apps.hotel_media.models import HotelMediaPhoto
    if context.get('hotel_media_photo_id'):
        photo = HotelMediaPhoto.objects.get(id=context.get('hotel_media_photo_id'))
        print(f"  Photo file path: {photo.file.path if photo.file else 'None'}")
        print(f"  Photo URL: {photo.file.url if photo.file else 'None'}")
else:
    print("No match found.")
