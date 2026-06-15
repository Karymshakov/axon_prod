import os
import django
import sys

sys.path.append(r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\backend")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.hotel_media.models import HotelMediaItem, HotelMediaPhoto

print("--- HOTEL MEDIA ITEMS ---")
for item in HotelMediaItem.objects.all():
    print(f"ID: {item.id}, Title: {item.title}, File: {item.file.name if item.file else 'None'}, File URL: {item.file.url if item.file else 'None'}")

print("\n--- HOTEL MEDIA PHOTOS ---")
for photo in HotelMediaPhoto.objects.all():
    print(f"ID: {photo.id}, Item: {photo.item.title}, File: {photo.file.name if photo.file else 'None'}, File URL: {photo.file.url if photo.file else 'None'}")
