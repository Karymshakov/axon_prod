"""
Data migration: create "Nomad Camp" organization, assign admin@example.com as owner,
and backfill organization FK on ALL existing records across every app.
CRITICAL: preserves all existing data — nothing is deleted.
"""
from django.db import migrations


def create_org_and_backfill(apps, schema_editor):
    Organization = apps.get_model('organizations', 'Organization')
    OrganizationMember = apps.get_model('organizations', 'OrganizationMember')
    User = apps.get_model('users', 'User')

    # 1. Find or create admin@example.com
    try:
        admin = User.objects.get(email='admin@example.com')
    except User.DoesNotExist:
        # Fall back to first staff/admin user
        admin = User.objects.filter(is_staff=True).first() or User.objects.first()
        if admin is None:
            return  # No users yet (empty DB), skip

    # 2. Create the default organization
    org, created = Organization.objects.get_or_create(
        slug='nomad-camp',
        defaults={
            'name': 'Nomad Camp',
            'plan': 'free',
            'is_active': True,
            'owner': admin,
        },
    )

    # 3. Create owner membership
    OrganizationMember.objects.get_or_create(
        organization=org,
        user=admin,
        defaults={'role': 'owner', 'is_active': True},
    )

    # 4. Set admin as superadmin + set current_organization
    User.objects.filter(email='admin@example.com').update(
        is_superadmin=True,
        current_organization=org,
    )

    # 5. Backfill all other users' current_organization if unset
    User.objects.filter(current_organization__isnull=True).update(current_organization=org)

    # ── Leads app ────────────────────────────────────────────────────────────
    for model_name in [
        'Segment', 'PipelineStage', 'Lead', 'LeadActivity', 'LeadGoal',
        'Task', 'Customer',
        'TelegramConfig', 'InstagramConnection', 'InstagramAppConfig',
        'WhatsAppAppConfig', 'WhatsAppConfig', 'RingCentralConfig', 'AIConfig',
    ]:
        Model = apps.get_model('leads', model_name)
        Model.objects.filter(organization__isnull=True).update(organization=org)

    # ── Hotel Info app ───────────────────────────────────────────────────────
    for model_name in [
        'HotelProfile', 'HotelPolicy', 'HotelFAQ',
        'HandoverContact', 'RoomPricing', 'Playbook',
    ]:
        Model = apps.get_model('hotel_info', model_name)
        Model.objects.filter(organization__isnull=True).update(organization=org)

    # ── Hotel Media app ──────────────────────────────────────────────────────
    apps.get_model('hotel_media', 'HotelMediaItem').objects.filter(
        organization__isnull=True
    ).update(organization=org)

    # ── Flows app ────────────────────────────────────────────────────────────
    for model_name in [
        'ConversationFlow', 'AIFlowMode', 'AITool',
        'AIModelConfig', 'ManagerTransferConfig', 'AgentConfig',
    ]:
        Model = apps.get_model('flows', model_name)
        Model.objects.filter(organization__isnull=True).update(organization=org)


def reverse_migration(apps, schema_editor):
    # Reverse: just clear the org FK from all records and delete the org
    Organization = apps.get_model('organizations', 'Organization')
    for model_name in [
        ('leads', 'Segment'), ('leads', 'PipelineStage'), ('leads', 'Lead'),
        ('leads', 'LeadActivity'), ('leads', 'LeadGoal'), ('leads', 'Task'),
        ('leads', 'Customer'), ('leads', 'TelegramConfig'), ('leads', 'InstagramConnection'),
        ('leads', 'InstagramAppConfig'), ('leads', 'WhatsAppAppConfig'),
        ('leads', 'WhatsAppConfig'), ('leads', 'RingCentralConfig'), ('leads', 'AIConfig'),
        ('hotel_info', 'HotelProfile'), ('hotel_info', 'HotelPolicy'),
        ('hotel_info', 'HotelFAQ'), ('hotel_info', 'HandoverContact'),
        ('hotel_info', 'RoomPricing'), ('hotel_info', 'Playbook'),
        ('hotel_media', 'HotelMediaItem'),
        ('flows', 'ConversationFlow'), ('flows', 'AIFlowMode'), ('flows', 'AITool'),
        ('flows', 'AIModelConfig'), ('flows', 'ManagerTransferConfig'), ('flows', 'AgentConfig'),
    ]:
        apps.get_model(*model_name).objects.all().update(organization=None)
    Organization.objects.filter(slug='nomad-camp').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0001_initial'),
        ('users', '0005_user_current_organization_user_is_superadmin'),
        ('leads', '0058_aiconfig_organization_customer_organization_and_more'),
        ('hotel_info', '0018_handovercontact_organization_hotelfaq_organization_and_more'),
        ('hotel_media', '0004_hotelmediaitem_organization'),
        ('flows', '0021_agentconfig_organization_aiflowmode_organization_and_more'),
    ]

    operations = [
        migrations.RunPython(create_org_and_backfill, reverse_code=reverse_migration),
    ]
