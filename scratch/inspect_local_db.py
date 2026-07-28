import os
import django
import sys

sys.path.append(r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\backend")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model
from apps.organizations.models import Organization
from apps.flows.models import ConversationFlow

User = get_user_model()

print("--- LOCAL DATABASE INFO ---")
print("Organizations:")
for org in Organization.objects.all():
    print(f"  ID: {org.id}, Name: {org.name}, Slug: {org.slug}")

print("\nUsers:")
for user in User.objects.all():
    print(f"  ID: {user.id}, Email: {user.email}, Name: {user.name}, Role: {user.role}, Active: {user.is_active}")

print("\nConversation Flows:")
for flow in ConversationFlow.objects.all():
    print(f"  ID: {flow.id}, Name: {flow.name}, Active: {flow.is_active}, Global Prompt Length: {len(flow.global_prompt)}")
    print(f"  Global Prompt Preview: {flow.global_prompt[:150]!r}...")
