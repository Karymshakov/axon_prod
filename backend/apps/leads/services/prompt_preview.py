from __future__ import annotations

import os
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from django.db.models import Q

from apps.leads.services.booking_tools import (
    _FALLBACK_DESCRIPTIONS,
    _TOOL_PARAMS,
    build_flow_card_instruction,
    detect_family_context,
    _org_from_lead,
)
from apps.leads.services.prompt_assembly import (
    PromptAssembler,
    build_scheduling_instruction,
    build_stage_tool_policy_instruction,
)
from apps.leads.services.security import _SAFETY_SYSTEM_INSTRUCTION
from apps.leads.services.stage_resolver import collect_stage_data, resolve_stage


def build_lead_data_from_model(lead, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    data = {
        'company_name': '',
        'contact_person': lead.contact_person,
        'phone': lead.phone,
        'email': lead.email,
        'source': lead.source,
        'contact_channel': getattr(lead, 'contact_channel', ''),
        'discovery_source': getattr(lead, 'discovery_source', ''),
        'discovery_source_detail': getattr(lead, 'discovery_source_detail', ''),
        'check_in_date': str(lead.check_in_date) if lead.check_in_date else None,
        'check_out_date': str(lead.check_out_date) if lead.check_out_date else None,
        'guest_count': lead.guest_count,
        'room_type_preference': lead.room_type_preference,
        'meal_plan': lead.meal_plan,
        'problem_description': lead.problem_description,
        'preferred_contact_time': lead.preferred_contact_time,
    }
    for key, value in (overrides or {}).items():
        if value not in (None, ''):
            data[key] = value
    return data


def build_prompt_preview(
    lead,
    message: str = '',
    *,
    lead_data: dict[str, Any] | None = None,
    conversation_history: list[dict[str, Any]] | None = None,
    include_content: bool = True,
) -> dict[str, Any]:
    org = _org_from_lead(lead)
    effective_lead_data = build_lead_data_from_model(lead, lead_data)
    assembler = PromptAssembler()

    _add_ai_config_sections(assembler, org)
    _add_booking_agent_section(assembler, org)
    assembler.add_system('scheduling_followups', 'SCHEDULING FOLLOW-UPS', build_scheduling_instruction())
    _add_hotel_info_section(assembler, org)
    _add_lead_context_section(assembler, lead, effective_lead_data)
    assembler.add_history(conversation_history or [])

    stage_preview = _build_stage_preview(lead, message, effective_lead_data)
    global_flow_prompt = _active_flow_global_prompt(org)
    if global_flow_prompt:
        assembler.add_system('global_flow_rules', 'GLOBAL FLOW RULES', global_flow_prompt)
    if stage_preview.get('card_instruction'):
        assembler.add_system('card_instructions', 'CARD INSTRUCTIONS', stage_preview['card_instruction'])
    if stage_preview.get('allowed_tools'):
        assembler.add_system(
            'stage_tool_policy',
            'CURRENT STAGE TOOL POLICY',
            build_stage_tool_policy_instruction(stage_preview['allowed_tools']),
        )

    assembler.add_raw_system('safety', _SAFETY_SYSTEM_INSTRUCTION)
    assembler.add_user(message)

    sections = [
        _serialize_section(section, include_content=include_content)
        for section in assembler.sections
    ]
    messages = assembler.to_messages()
    available_tools = _available_tool_names(org)
    allowed_tools = stage_preview.get('allowed_tools') or available_tools
    registered_tools = sorted(set(available_tools) & set(allowed_tools))

    return {
        'lead_id': lead.pk,
        'organization_id': getattr(lead, 'organization_id', None),
        'message': message,
        'section_keys': assembler.section_keys(),
        'sections': sections,
        'messages_count': len(messages),
        'total_prompt_chars': sum(len(str(msg.get('content') or '')) for msg in messages),
        'stage_policy': stage_preview.get('stage_policy'),
        'tool_policy': {
            'available_tools': available_tools,
            'allowed_tools': sorted(allowed_tools),
            'registered_tools': registered_tools,
        },
    }


def _serialize_section(section, *, include_content: bool) -> dict[str, Any]:
    data = {
        'key': section.key,
        'role': section.role,
        'title': section.title,
        'chars': len(section.content or ''),
    }
    if include_content:
        data['content'] = section.content
    return data


def _add_ai_config_sections(assembler: PromptAssembler, org) -> None:
    try:
        from apps.leads.models import AIConfig

        config = AIConfig.get_config(org=org)
        if config and config.system_prompt:
            assembler.add_raw_system('ai_config_system_prompt', config.system_prompt)
        if config and config.company_profile:
            assembler.add_system('company_profile', 'COMPANY PROFILE', config.company_profile)
    except Exception:
        return


def _add_booking_agent_section(assembler: PromptAssembler, org) -> None:
    try:
        from apps.flows.models import AgentConfig

        qs = AgentConfig.objects.filter(name='booking')
        if org is not None:
            qs = qs.filter(organization=org)
        cfg = qs.first()
        if not cfg:
            return

        prompt_file = os.path.normpath(os.path.join(
            os.path.dirname(__file__),
            '..', '..', 'knowledge_docs', 'prompts', 'booking_agent.md',
        ))
        if os.path.isfile(prompt_file):
            with open(prompt_file, encoding='utf-8') as handle:
                prompt_text = handle.read().strip()
        else:
            prompt_text = (cfg.system_prompt or '').strip()
        assembler.add_system('booking_agent_prompt', 'BOOKING AGENT PROMPT', prompt_text)
    except Exception:
        return


def _add_hotel_info_section(assembler: PromptAssembler, org) -> None:
    try:
        from apps.hotel_info.models import HandoverContact, HotelFAQ, HotelPolicy, HotelProfile

        profile = HotelProfile.get_profile(org=org)
        lines = []
        if profile:
            lines.append('[HOTEL INFO]')
            if profile.hotel_name:
                lines.append(f'Hotel name: {profile.hotel_name}')
            if profile.website:
                lines.append(f'Website: {profile.website}')
            if profile.description:
                lines.append(f'Description: {profile.description}')
            if profile.address:
                lines.append(f'Address: {profile.address}')
            if profile.directions:
                lines.append(f'Directions: {profile.directions}')

        policies = HotelPolicy.objects.filter(organization=org).order_by('order') if org else HotelPolicy.objects.none()
        if policies:
            lines.append('\n[HOTEL POLICIES]')
            for policy in policies:
                entry = f'{policy.emoji} {policy.label}: {policy.value}' if policy.emoji else f'{policy.label}: {policy.value}'
                if policy.description:
                    entry += f' - {policy.description}'
                lines.append(entry)

        faqs = HotelFAQ.objects.filter(organization=org).order_by('order') if org else HotelFAQ.objects.none()
        if faqs:
            lines.append('\n[HOTEL FAQ]')
            for faq in faqs:
                lines.append(f'Q: {faq.question}')
                lines.append(f'A: {faq.answer}')

        contacts = HandoverContact.objects.filter(organization=org).order_by('order') if org else HandoverContact.objects.none()
        if contacts:
            lines.append('\n[HANDOVER CONTACTS]')
            for contact in contacts:
                entry = f'- {contact.name}: {contact.phone}'
                if contact.escalate_when:
                    entry += f' | Escalate when: {contact.escalate_when}'
                lines.append(entry)

        assembler.add_raw_system('hotel_info_bundle', '\n'.join(lines))
    except Exception:
        return


def _add_lead_context_section(assembler: PromptAssembler, lead, lead_data: dict[str, Any]) -> None:
    now = datetime.now(ZoneInfo('Asia/Bishkek'))
    lines = [
        '[LEAD CONTEXT]',
        f"Current date/time: {now.strftime('%A, %d %B %Y, %H:%M')} (Kyrgyzstan, UTC+6)",
        f"Current year: {now.year}. When a guest mentions a date without a year - assume it is in {now.year}.",
    ]
    if lead_data.get('contact_person'):
        lines.append(f"Contact: {lead_data['contact_person']}")
    if lead_data.get('source'):
        lines.append(f"Source: {lead_data['source']}")

    known = []
    for label, key in (
        ('Phone', 'phone'),
        ('Email', 'email'),
        ('Guest count', 'guest_count'),
        ('Check-in', 'check_in_date'),
        ('Check-out', 'check_out_date'),
        ('Room type', 'room_type_preference'),
        ('Meal plan', 'meal_plan'),
    ):
        value = lead_data.get(key)
        if value:
            known.append(f'{label}: {value}')
    if known:
        lines.append('\nALREADY KNOWN - do NOT ask again:')
        lines.extend(f'  {item}' for item in known)

    try:
        if detect_family_context(lead):
            lines.append(
                '\nFamily/kids booking context is already present in the conversation.'
            )
    except Exception:
        pass

    assembler.add_raw_system('lead_context', '\n'.join(lines))


def _build_stage_preview(lead, message: str, lead_data: dict[str, Any]) -> dict[str, Any]:
    try:
        flow_state = lead.flow_state
        card = flow_state.current_card
    except Exception:
        return {'stage_policy': None, 'allowed_tools': None, 'card_instruction': ''}

    if not card:
        return {'stage_policy': None, 'allowed_tools': None, 'card_instruction': ''}

    existing = dict(flow_state.collected_data or {})
    latest = collect_stage_data(lead, lead_data, message)
    collected_data = {**existing, **latest}
    resolution = resolve_stage(card, collected_data)
    allowed_tools = [
        str(tool).strip()
        for tool in (getattr(card, 'allowed_tools', None) or [])
        if str(tool).strip()
    ]
    effective_data = {**lead_data, **resolution.collected_data}
    card_instruction = build_flow_card_instruction(
        card,
        effective_data,
        flow_state.flow,
        ai_service_instance=None,
        stage_resolution=resolution,
    )
    return {
        'allowed_tools': allowed_tools or None,
        'card_instruction': card_instruction,
        'stage_policy': {
            'flow_id': getattr(flow_state.flow, 'pk', None),
            'card_id': getattr(card, 'pk', None),
            'card_title': card.title,
            'required_fields': resolution.required_fields,
            'missing_fields': resolution.missing_fields,
            'is_complete': resolution.is_complete,
            'collected_data': resolution.collected_data,
            'allowed_tools': allowed_tools,
        },
    }


def build_card_policy_preview(
    card,
    *,
    sample_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Card-only preview for the no-code flow editor.

    Returns a human-readable explanation of what the AI will see at this stage,
    using supplied ``sample_data`` (or empty data) to simulate collected fields.
    No Lead model is required.
    """
    effective_data: dict[str, Any] = dict(sample_data or {})
    resolution = resolve_stage(card, effective_data)
    card_instruction = build_flow_card_instruction(
        card,
        {**effective_data, **resolution.collected_data},
        card.flow,
        ai_service_instance=None,
        stage_resolution=resolution,
    )
    allowed_tools: list[str] = [
        str(t).strip()
        for t in (getattr(card, 'allowed_tools', None) or [])
        if str(t).strip()
    ]
    return {
        'card_id': card.pk,
        'card_title': card.title,
        'card_type': card.card_type,
        'system_prompt': card_instruction,
        'stage_policy': {
            'goal': getattr(card, 'goal', '') or '',
            'required_fields': resolution.required_fields,
            'missing_fields': resolution.missing_fields,
            'is_complete': resolution.is_complete,
            'allowed_tools': allowed_tools,
            'response_policy': getattr(card, 'response_policy', None) or {},
            'return_to_funnel_instruction': getattr(card, 'return_to_funnel_instruction', '') or '',
        },
        'sample_data_used': effective_data,
    }


def _active_flow_global_prompt(org) -> str:
    try:
        from apps.flows.models import AIFlowMode, ConversationFlow

        mode = AIFlowMode.get_mode(org=org)
        if not mode or mode.mode != AIFlowMode.MODE_FLOW_GUIDED:
            return ''
        qs = ConversationFlow.objects.filter(is_active=True)
        if org is not None:
            qs = qs.filter(organization=org)
        flow = qs.only('global_prompt').first()
        return flow.global_prompt if flow and flow.global_prompt else ''
    except Exception:
        return ''


def _available_tool_names(org) -> list[str]:
    try:
        from apps.flows.models import AITool

        all_qs = AITool.objects.all()
        if org is not None:
            all_qs = all_qs.filter(Q(organization=org) | Q(organization__isnull=True))
        all_db_tool_names = set(all_qs.values_list('name', flat=True))
        db_tool_names = set(all_qs.filter(is_enabled=True).values_list('name', flat=True))
    except Exception:
        all_db_tool_names = set()
        db_tool_names = set()

    names = set()
    for name in _TOOL_PARAMS:
        if name in db_tool_names or (name not in all_db_tool_names and name in _FALLBACK_DESCRIPTIONS):
            names.add(name)
    return sorted(names)
