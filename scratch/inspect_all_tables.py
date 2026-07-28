import os
import sys
import django

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ['DATABASE_URL'] = "postgresql://postgres:admin@localhost:5432/app_dev"
django.setup()

from apps.organizations.models import Organization
from apps.leads.models import InstagramConnection, InstagramAppConfig, Lead
from apps.hotel_media.models import HotelMediaItem, SocialContentItem

print("Organizations:")
for org in Organization.objects.all():
    print(f"  ID={org.id}, Name={org.name}")

print("\nInstagramAppConfig:")
for cfg in InstagramAppConfig.objects.all():
    print(f"  ID={cfg.id}, AppID={cfg.app_id}")

print("\nInstagramConnection:")
for conn in InstagramConnection.objects.all():
    print(f"  ID={conn.id}, Username={conn.username}, Org={conn.organization_id}")

print("\nLeads:")
print("  Total count:", Lead.objects.count())
for lead in Lead.objects.order_by('-created_at')[:10]:
    print(f"  ID={lead.id}, Name={lead.name}, Platform={lead.platform}, Created={lead.created_at}")

print("\nSocialContentItem count:", SocialContentItem.objects.count())
