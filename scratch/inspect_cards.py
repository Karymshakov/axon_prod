import os
import sys
import django

sys.path.append(r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\backend")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.flows.models import ConversationFlow, FlowCard

with open("scratch/cards_output.txt", "w", encoding="utf-8") as f:
    f.write("--- CONVERSATION FLOWS ---\n")
    for flow in ConversationFlow.objects.all():
        f.write(f"Flow ID: {flow.id}, Name: {flow.name}, Active: {flow.is_active}\n")

    f.write("\n--- FLOW CARDS FOR ACTIVE FLOW ---\n")
    active_flow = ConversationFlow.objects.filter(is_active=True).first()
    if active_flow:
        cards = FlowCard.objects.filter(flow=active_flow).order_by('id')
        for card in cards:
            f.write(f"\n[Card ID: {card.id}] {card.title}\n")
            f.write("Template:\n")
            f.write(card.message_template + "\n")
    else:
        f.write("No active flow found.\n")

print("Output written to scratch/cards_output.txt")
