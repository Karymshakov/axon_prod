import os
import sys
import django

sys.path.append(r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\backend")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.leads.models import LeadActivity, Lead
from apps.flows.models import LeadFlowState

lead = Lead.objects.get(id=1)
with open("scratch/trace_lead1_flow_out.txt", "w", encoding="utf-8") as f:
    f.write(f"Lead status: {lead.status}\n")
    f.write("Lead agent_context:\n")
    import pprint
    f.write(pprint.pformat(lead.agent_context) + "\n\n")

    activities = LeadActivity.objects.filter(lead=lead).order_by('created_at')
    for act in activities:
        f.write(f"[{act.created_at}] {act.activity_type}: {act.description}\n")
        if act.metadata:
            f.write(f"  Metadata: {act.metadata}\n")
        f.write("-" * 80 + "\n")

print("Done")
