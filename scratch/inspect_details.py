import os
import sys
import django

sys.path.append(r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\backend")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.hotel_info.models import Playbook
from apps.flows.models import FlowCard

# Inspect Playbook 10
p10 = Playbook.objects.get(id=10)

# Inspect FlowCard 12
fc12 = FlowCard.objects.get(id=12)

with open("scratch/inspect_details_output.txt", "w", encoding="utf-8") as f:
    f.write("=== PLAYBOOK 10 ===\n")
    f.write(f"ID: {p10.id}\n")
    f.write(f"Name: {p10.name}\n")
    f.write("Instructions:\n")
    f.write(f"{p10.instructions}\n")
    f.write("Content:\n")
    f.write(f"{p10.content}\n\n")

    f.write("=== FLOWCARD 12 ===\n")
    f.write(f"ID: {fc12.id}\n")
    f.write(f"Title: {fc12.title}\n")
    f.write("Template:\n")
    f.write(f"{fc12.message_template}\n")

print("Done writing to scratch/inspect_details_output.txt")
