import os
import sys
import django

sys.path.append(r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\backend")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.flows.models import ConversationFlow, FlowCard, FlowConnection

flow = ConversationFlow.objects.get(id=1)
cards = FlowCard.objects.filter(flow=flow)
connections = FlowConnection.objects.filter(flow=flow)

with open("scratch/inspect_flow_out.txt", "w", encoding="utf-8") as f:
    f.write(f"Flow: {flow.name}\n")
    f.write("=== CARDS ===\n")
    for card in cards:
        f.write(f"[{card.id}] {card.title} (Type: {card.card_type})\n")
    
    f.write("\n=== CONNECTIONS ===\n")
    for conn in connections:
        f.write(f"[{conn.id}] {conn.source_card.title} ({conn.source_card.id}) → {conn.target_card.title} ({conn.target_card.id})\n")
        f.write(f"  Condition Label: {conn.condition_label}\n")
        f.write(f"  Keywords: {conn.condition_keywords}\n")
        f.write("-" * 40 + "\n")

print("Done")
