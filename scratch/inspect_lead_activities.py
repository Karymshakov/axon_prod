import os
import sys
import django

sys.path.append(r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\backend")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.leads.models import LeadActivity

activities = LeadActivity.objects.filter(lead_id=1).order_by('-created_at')[:20]

with open("scratch/lead_activities_out.txt", "w", encoding="utf-8") as f:
    f.write(f"Total activities: {LeadActivity.objects.filter(lead_id=1).count()}\n\n")
    for act in activities:
        f.write(f"[{act.created_at}] Type: {act.activity_type}\n")
        f.write(f"Description: {act.description}\n")
        f.write(f"Metadata: {act.metadata}\n")
        f.write("-" * 80 + "\n")

print("Done writing to scratch/lead_activities_out.txt")
