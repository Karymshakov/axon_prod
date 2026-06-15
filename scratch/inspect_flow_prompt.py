import os
import sys
import django

sys.path.append(r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\backend")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.flows.models import ConversationFlow

cf = ConversationFlow.objects.get(id=1)
with open("scratch/inspect_flow_prompt.txt", "w", encoding="utf-8") as f:
    f.write("=== GLOBAL FLOW PROMPT ===\n")
    f.write(cf.global_prompt)

print("Done")
