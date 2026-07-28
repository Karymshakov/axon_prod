import os
import sys
import django

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ['DATABASE_URL'] = "postgresql://postgres:admin@localhost:5432/app_dev"
django.setup()

from apps.hotel_media.models import HotelMediaItem

for item in HotelMediaItem.objects.all():
    file_url = item.file.url if item.file else 'No file'
    print(f"ID={item.id}, Title='{item.title}', RoomCategory='{item.room_category}', Category='{item.category}', File='{file_url}'")
    for photo in item.photos.all():
        print(f"  Photo ID={photo.id}, File='{photo.file.url if photo.file else 'No file'}'")
