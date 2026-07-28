import os
import sys
import django

sys.path.append(r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\backend")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.hotel_info.models import Playbook

# Get all field names
fields = [f.name for f in Playbook._meta.get_fields()]
print(f"Playbook fields: {fields}")

with open("scratch/playbooks_output.txt", "w", encoding="utf-8") as f:
    f.write(f"Playbook fields: {fields}\n")
    for pb in Playbook.objects.all():
        f.write(f"\n[Playbook ID: {pb.id}] Name: {pb.name} (Active: {pb.is_active})\n")
        if hasattr(pb, 'instructions'):
            f.write(f"Instructions:\n{pb.instructions}\n")
        if hasattr(pb, 'content'):
            f.write(f"Content: {pb.content}\n")
        if hasattr(pb, 'trigger_rules'):
            f.write(f"Trigger Rules: {pb.trigger_rules}\n")
