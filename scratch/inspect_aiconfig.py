import os
import sys
import django

sys.path.append(r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\backend")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.leads.models import AIConfig

cfg = AIConfig.objects.first()
with open("scratch/inspect_aiconfig_out.txt", "w", encoding="utf-8") as f:
    if cfg:
        f.write("=== AIConfig ===\n")
        f.write("System Prompt:\n")
        f.write(f"{cfg.system_prompt}\n\n")
        f.write("Company Profile:\n")
        f.write(f"{cfg.company_profile}\n")
    else:
        f.write("AIConfig not found\n")
print("Done")
