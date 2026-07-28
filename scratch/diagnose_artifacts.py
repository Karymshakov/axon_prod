import os
import sys
import django

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ['DATABASE_URL'] = "postgresql://postgres:admin@localhost:5432/app_dev"
django.setup()

from apps.leads.services.media_context import find_best_fingerprint_context

brain_dir = r"C:\Users\kille\.gemini\antigravity-ide\brain\038af392-e861-4635-a8ea-f0505fd421c1"
files = [
    "media__1782054631555.jpg",
    "media__1782054631599.jpg",
    "media__1782054631655.jpg",
    "media__1782054631685.jpg",
    "media__1782054631699.jpg",
    "media__1782055205355.png"
]

for filename in files:
    filepath = os.path.join(brain_dir, filename)
    if os.path.exists(filepath):
        print(f"\n--- Diagnosing {filename} ---")
        context = find_best_fingerprint_context(filepath)
        if context:
            print("Match found:")
            print(f"  Source: {context.get('source')}")
            print(f"  Hotel Media Item ID: {context.get('hotel_media_item_id')}")
            print(f"  Social Content ID: {context.get('social_content_id')}")
            print(f"  Title: {context.get('title')}")
            print(f"  Confidence: {context.get('confidence')}")
            print(f"  Category: {context.get('category')}")
            print(f"  Room Category: {context.get('room_category')}")
            print(f"  Hash kind/distance: {context.get('hash_kind')} / {context.get('hash_distance')}")
        else:
            print("No match found.")
    else:
        print(f"File {filename} does not exist at {filepath}")
