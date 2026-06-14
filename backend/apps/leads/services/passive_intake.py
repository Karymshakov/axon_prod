from __future__ import annotations

import logging
from typing import Any

from apps.leads.ai_memory import filter_activities_since_last_ai_reset
from apps.leads.ai_service import ai_service
from apps.leads.models import AIConfig, Lead, LeadActivity
from apps.leads.services.discovery_sources import normalize_discovery_source

logger = logging.getLogger(__name__)


_FAKE_EMAIL_DOMAINS = {
    'example.com', 'example.org', 'example.net', 'example.io',
    'test.com', 'test.org', 'test.net',
    'placeholder.com', 'email.com', 'domain.com', 'yourdomain.com',
}

_FAKE_EMAIL_LOCALS = {
    'john.doe', 'jane.doe', 'firstname.lastname', 'test',
    'user', 'name', 'email', 'sample', 'demo',
}

_CHANNEL_ACTIVITY_TYPES = {
    'telegram': [LeadActivity.TYPE_TELEGRAM_RECEIVED, LeadActivity.TYPE_TELEGRAM_SENT],
    'instagram': [LeadActivity.TYPE_INSTAGRAM_RECEIVED, LeadActivity.TYPE_INSTAGRAM_SENT],
    'whatsapp': [LeadActivity.TYPE_WHATSAPP_RECEIVED, LeadActivity.TYPE_WHATSAPP_SENT],
}

_RECEIVED_ACTIVITY_TYPES = {
    LeadActivity.TYPE_TELEGRAM_RECEIVED,
    LeadActivity.TYPE_INSTAGRAM_RECEIVED,
    LeadActivity.TYPE_WHATSAPP_RECEIVED,
}

def _is_fake_email(email: str) -> bool:
    if not email or '@' not in email:
        return False
    local, _, domain = email.rpartition('@')
    if domain.lower() in _FAKE_EMAIL_DOMAINS:
        return True
    if local.lower() in _FAKE_EMAIL_LOCALS:
        return True
    return False


def _apply_extracted_data(lead: Lead, extracted_data: dict[str, Any]) -> list[str]:
    updated_fields: list[str] = []

    if extracted_data.get('contact_person') and lead.contact_person != extracted_data['contact_person']:
        lead.contact_person = extracted_data['contact_person']
        updated_fields.append('contact_person')

    if extracted_data.get('phone') and lead.phone != extracted_data['phone']:
        lead.phone = extracted_data['phone']
        updated_fields.append('phone')

    if extracted_data.get('email') and not _is_fake_email(str(extracted_data['email'])) and lead.email != extracted_data['email']:
        lead.email = extracted_data['email']
        updated_fields.append('email')

    if extracted_data.get('problem_description') and lead.problem_description != extracted_data['problem_description']:
        lead.problem_description = extracted_data['problem_description']
        updated_fields.append('problem_description')

    if extracted_data.get('preferred_contact_time') and lead.preferred_contact_time != extracted_data['preferred_contact_time']:
        lead.preferred_contact_time = extracted_data['preferred_contact_time']
        updated_fields.append('preferred_contact_time')

    if extracted_data.get('check_in_date') and str(lead.check_in_date or '') != extracted_data['check_in_date']:
        lead.check_in_date = extracted_data['check_in_date']
        updated_fields.append('check_in_date')

    if extracted_data.get('check_out_date') and str(lead.check_out_date or '') != extracted_data['check_out_date']:
        lead.check_out_date = extracted_data['check_out_date']
        updated_fields.append('check_out_date')

    if extracted_data.get('guest_count') and lead.guest_count != int(extracted_data['guest_count']):
        lead.guest_count = int(extracted_data['guest_count'])
        updated_fields.append('guest_count')

    if extracted_data.get('room_type_preference') and lead.room_type_preference != extracted_data['room_type_preference']:
        lead.room_type_preference = extracted_data['room_type_preference']
        updated_fields.append('room_type_preference')

    if extracted_data.get('meal_plan'):
        valid_meal_plans = {'none', 'breakfast', 'lunch', 'dinner', 'half_board_bl', 'half_board_bd', 'full_board'}
        if extracted_data['meal_plan'] in valid_meal_plans and lead.meal_plan != extracted_data['meal_plan']:
            lead.meal_plan = extracted_data['meal_plan']
            updated_fields.append('meal_plan')

    if extracted_data.get('discovery_source'):
        discovery_source = normalize_discovery_source(extracted_data['discovery_source'], lead.organization)
        if discovery_source and lead.discovery_source != discovery_source:
            lead.discovery_source = discovery_source
            updated_fields.append('discovery_source')

    if extracted_data.get('discovery_source_detail') and lead.discovery_source_detail != extracted_data['discovery_source_detail']:
        lead.discovery_source_detail = str(extracted_data['discovery_source_detail'])[:255]
        updated_fields.append('discovery_source_detail')

    if updated_fields:
        lead.save(update_fields=list(dict.fromkeys(updated_fields)))

    return list(dict.fromkeys(updated_fields))


def run_passive_ai_intake(lead: Lead, message_text: str, *, channel: str) -> list[str]:
    """
    Update CRM memory while auto-replies are disabled or a manager has taken over.

    This never sends a guest-facing message and never schedules follow-ups. It only
    refreshes the internal summary and extracts structured lead data when enabled.
    """
    if not ai_service.is_configured():
        return []

    updated_fields: list[str] = []
    config = AIConfig.get_config(org=lead.organization)

    try:
        summary = ai_service.generate_conversation_summary(lead)
        if summary and lead.notes != summary:
            Lead.objects.filter(id=lead.id).update(notes=summary)
            lead.notes = summary
            updated_fields.append('notes')
    except Exception as exc:
        logger.warning("Passive summary update failed for lead %s: %s", lead.id, exc)

    if not config or not getattr(config, 'auto_extract_data', False):
        return updated_fields

    activity_types = _CHANNEL_ACTIVITY_TYPES.get(channel, [])
    if not activity_types:
        return updated_fields

    try:
        conversation_history = []
        qs = filter_activities_since_last_ai_reset(
            LeadActivity.objects.filter(lead=lead, activity_type__in=activity_types),
            lead,
        ).order_by('created_at').only('activity_type', 'metadata', 'description')

        for activity in qs:
            msg_text = (activity.metadata or {}).get('text', '') or activity.description or ''
            if not msg_text:
                continue
            role = 'user' if activity.activity_type in _RECEIVED_ACTIVITY_TYPES else 'assistant'
            conversation_history.append({'role': role, 'content': msg_text})

        our_company_name = config.company_profile.split('\n')[0] if config.company_profile else None
        extracted_data = ai_service.extract_lead_data(
            message_text,
            conversation_history,
            our_company_name,
            lead.organization,
        )
        if extracted_data:
            updated_fields.extend(_apply_extracted_data(lead, extracted_data))
            logger.info("Passive AI intake updated lead %s fields: %s", lead.id, updated_fields)
    except Exception as exc:
        logger.warning("Passive extraction failed for lead %s: %s", lead.id, exc)

    return list(dict.fromkeys(updated_fields))
