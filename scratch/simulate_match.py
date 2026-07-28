import os
import sys
import django

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ['DATABASE_URL'] = "postgresql://postgres:admin@localhost:5432/app_dev"
django.setup()

from apps.organizations.models import Organization
from apps.hotel_media.models import HotelMediaItem, SocialContentItem, MediaFingerprint
from apps.hotel_media.services import _create_fingerprints
from apps.hotel_media.fingerprints import compute_image_fingerprints
from apps.leads.services.media_context import find_best_fingerprint_context

# Clean up any existing social content items and their fingerprints
SocialContentItem.objects.filter(caption="Dream Team kids in pool").delete()

org = Organization.objects.first()
brain_dir = r"C:\Users\kille\.gemini\antigravity-ide\brain\038af392-e861-4635-a8ea-f0505fd421c1"
pool_photo_path = os.path.join(brain_dir, "media__1782054631555.jpg")
screenshot_path = os.path.join(brain_dir, "media__1782054631685.jpg")

# Create SocialContentItem
social_item = SocialContentItem.objects.create(
    organization=org,
    platform=SocialContentItem.PLATFORM_INSTAGRAM,
    external_id="story_pool_123",
    content_type=SocialContentItem.TYPE_STORY,
    title="Dream Team",
    caption="Dream Team kids in pool",
    review_status=SocialContentItem.REVIEW_NEEDS_REVIEW,
    is_active=True
)

# Compute and save fingerprints for the pool photo (linked to the SocialContentItem)
records = compute_image_fingerprints(pool_photo_path)
_create_fingerprints(records, organization=org, social_content_item=social_item)
print(f"Created {len(records)} fingerprints for SocialContentItem ID={social_item.id}")

# Run matching on screenshot
print("\nRunning find_best_fingerprint_context on screenshot...")
context = find_best_fingerprint_context(screenshot_path)
if context:
    print("\nSUCCESS! Match found:")
    print(f"  Source: {context.get('source')}")
    print(f"  Hotel Media Item ID: {context.get('hotel_media_item_id')}")
    print(f"  Social Content ID: {context.get('social_content_id')}")
    print(f"  Title: {context.get('title')}")
    print(f"  Confidence: {context.get('confidence')}")
    print(f"  Hash kind/distance: {context.get('hash_kind')} / {context.get('hash_distance')}")
else:
    print("\nFAILURE! No match found.")

# Clean up
social_item.delete()
