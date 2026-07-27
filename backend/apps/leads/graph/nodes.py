from __future__ import annotations

import logging
from typing import Any

from apps.leads.graph.state import AgentState

logger = logging.getLogger(__name__)


def _get_lead(state: AgentState):
    from apps.leads.models import Lead

    return Lead.objects.select_related('organization').get(pk=state['lead_id'])


def _get_selected_media(state: AgentState):
    selected_media = state.get('selected_media')
    if selected_media is not None:
        return selected_media

    media_id = state.get('selected_media_id')
    if not isinstance(media_id, int):
        return None

    from apps.hotel_media.models import HotelMediaItem

    return HotelMediaItem.objects.filter(pk=media_id).first()


def load_context_node(state: AgentState) -> dict[str, Any]:
    from apps.leads.agent_dispatcher import (
        _sync_context_from_flow_state,
        load_agent_context,
        save_agent_context,
    )

    lead = _get_lead(state)
    context = load_agent_context(lead)
    if _sync_context_from_flow_state(lead, context):
        save_agent_context(lead, context)

    return {
        'organization_id': lead.organization_id,
        'context': context,
        'metadata': {'lead_pk': lead.pk},
    }


def inbound_guardrails_node(state: AgentState) -> dict[str, Any]:
    from apps.leads.agent_dispatcher import _guardrail_response

    response = _guardrail_response(state.get('message', ''), lead=_get_lead(state))
    if response:
        return {
            'guardrail_response': response,
            'final_response': response,
            'route': 'end',
        }
    return {'route': 'router'}


def route_intent_node(state: AgentState) -> dict[str, Any]:
    from apps.leads.ai_service import ai_service
    from apps.leads.agent_dispatcher import (
        classify_intent,
        save_agent_context,
    )

    lead = _get_lead(state)
    context = dict(state.get('context') or {})
    history = state.get('conversation_history') or []
    message = state.get('message', '')
    last_messages = [turn.get('content', '') for turn in history[-3:] if turn.get('content')]
    if message and message not in last_messages:
        last_messages.append(message)

    result = classify_intent(
        ai_service.client,
        last_messages,
        context=context,
        model=ai_service._model,
        org=lead.organization,
    )
    intent = result['intent']
    confidence = result['confidence']

    context['previous_agent'] = context.get('current_agent', 'booking')
    context['last_intent'] = intent
    save_agent_context(lead, context)

    if intent in ('faq', 'off_topic'):
        route = 'cs'
    elif intent == 'undecided':
        route = 'consultant'
    else:
        route = 'stage_resolver'

    return {
        'context': context,
        'intent': intent,
        'confidence': confidence,
        'route': route,
    }


def stage_resolver_node(state: AgentState) -> dict[str, Any]:
    from apps.leads.agent_dispatcher import save_agent_context
    from apps.leads.services.stage_resolver import infer_required_fields_from_card, sync_stage_state

    lead = _get_lead(state)
    context = dict(state.get('context') or {})

    try:
        flow_state = lead.flow_state
        card = flow_state.current_card
    except Exception:
        return {'route': 'booking'}

    if not card:
        return {'route': 'booking'}

    resolution = sync_stage_state(
        flow_state,
        lead,
        state.get('lead_data') or {},
        state.get('message', ''),
    )
    if resolution.changed:
        flow_state.save(update_fields=['collected_data', 'updated_at'])

    context['flow_stage_policy'] = {
        'card_id': card.pk,
        'title': card.title,
        'goal': card.goal,
        'required_fields': infer_required_fields_from_card(card),
        'success_conditions': card.success_conditions or {},
        'allowed_tools': card.allowed_tools or [],
        'response_policy': card.response_policy or {},
        'return_to_funnel_instruction': card.return_to_funnel_instruction,
        'missing_fields': resolution.missing_fields,
        'is_complete': resolution.is_complete,
    }
    save_agent_context(lead, context)

    return {
        'context': context,
        'lead_data': {**(state.get('lead_data') or {}), **resolution.collected_data},
        'stage_resolution': resolution.as_dict(),
        'route': 'booking',
    }


def dialogue_director_node(state: AgentState) -> dict[str, Any]:
    from apps.leads.agent_dispatcher import save_agent_context
    from apps.leads.services.dialogue_director import build_dialogue_directive

    lead = _get_lead(state)
    context = dict(state.get('context') or {})
    directive = build_dialogue_directive(
        lead=lead,
        intent=state.get('intent') or 'booking',
        stage_resolution=state.get('stage_resolution') or None,
    )
    directive_dict = directive.as_dict()
    context['dialogue_directive'] = directive_dict
    context['current_agent'] = directive.route
    save_agent_context(lead, context)

    logger.info(
        '[DialogueDirector] lead=%s intent=%s route=%s stage=%r missing=%s',
        getattr(lead, 'pk', None),
        directive.intent,
        directive.route,
        directive.stage_title,
        directive.missing_fields,
    )

    return {
        'context': context,
        'dialogue_directive': directive_dict,
        'route': directive.route,
    }


def booking_agent_node(state: AgentState) -> dict[str, Any]:
    from apps.leads.ai_service import ai_service
    from apps.leads.agent_dispatcher import save_agent_context

    lead = _get_lead(state)
    context = dict(state.get('context') or {})
    context['current_agent'] = 'booking'

    message = state.get('message', '')
    recommendation = context.get('consultant_recommendation')
    return_to_step = context.get('return_to_step')
    if recommendation:
        message = f'[Consultant recommendation: {recommendation}]'
        if return_to_step:
            message += f' [Resume booking from step: {return_to_step}]'
        message += f'\n{state.get("message", "")}'
        context['consultant_recommendation'] = None
        context['return_to_step'] = None

    save_agent_context(lead, context)
    response = ai_service.generate_response(
        message,
        state.get('lead_data') or {},
        state.get('conversation_history') or [],
        selected_media=_get_selected_media(state),
        is_pooled=bool(state.get('is_pooled')),
        activity_history=state.get('activity_history'),
        lead=lead,
    )
    return {'agent_response': response, 'context': context, 'route': 'sanitize'}


def cs_agent_node(state: AgentState) -> dict[str, Any]:
    from apps.leads.ai_service import ai_service
    from apps.leads.agent_dispatcher import (
        _execute_sales_handoff_if_needed,
        _load_agent_cfg,
        _playbook_fallback_answer,
        run_cs_agent,
        save_agent_context,
    )

    lead = _get_lead(state)
    context = dict(state.get('context') or {})
    context['current_agent'] = 'cs'
    save_agent_context(lead, context)

    selected_media = _get_selected_media(state)
    response = run_cs_agent(
        ai_service.client,
        state.get('message', ''),
        context,
        _load_agent_cfg('cs', org=lead.organization),
        state.get('lead_data') or {},
        state.get('conversation_history') or [],
        lead=lead,
        selected_media=selected_media,
        model=ai_service._model,
    )
    response = response or _playbook_fallback_answer(state.get('message', ''), lead)
    if selected_media:
        response = ai_service._ensure_selected_media_guest_message(response, selected_media)

    _execute_sales_handoff_if_needed(state.get('message', ''), response, state.get('lead_data') or {}, lead)
    context['current_agent'] = 'booking'
    save_agent_context(lead, context)
    return {'agent_response': response, 'context': context, 'route': 'sanitize'}


def consultant_agent_node(state: AgentState) -> dict[str, Any]:
    from apps.leads.ai_service import ai_service
    from apps.leads.agent_dispatcher import _load_agent_cfg, run_consultant_agent, save_agent_context

    lead = _get_lead(state)
    context = dict(state.get('context') or {})
    context['current_agent'] = 'consultant'
    save_agent_context(lead, context)

    response = run_consultant_agent(
        ai_service.client,
        state.get('message', ''),
        context,
        _load_agent_cfg('consultant', org=lead.organization),
        state.get('lead_data') or {},
        state.get('conversation_history') or [],
        ai_service,
        lead,
        model=ai_service._model,
    )

    context['current_agent'] = 'booking'
    save_agent_context(lead, context)
    return {'agent_response': response, 'context': context, 'route': 'sanitize'}


def sanitize_response_node(state: AgentState) -> dict[str, Any]:
    from apps.leads.ai_service import ai_service, sanitize_public_response

    lead = _get_lead(state)
    response = state.get('agent_response')
    if response is None and state.get('intent') == 'undecided':
        response = ai_service.generate_response(
            state.get('message', ''),
            state.get('lead_data') or {},
            state.get('conversation_history') or [],
            selected_media=_get_selected_media(state),
            is_pooled=bool(state.get('is_pooled')),
            activity_history=state.get('activity_history'),
            lead=lead,
        )

    response = sanitize_public_response(
        response,
        state.get('message', ''),
        lead=lead,
        lead_data=state.get('lead_data') or {},
    )
    return {'final_response': response, 'route': 'end'}


def persist_graph_error_node(state: AgentState) -> dict[str, Any]:
    logger.exception('LangGraph dialogue failed for lead_id=%s', state.get('lead_id'))
    return {'errors': ['dialogue_graph_failed'], 'route': 'end'}


def extract_stage_data_node(state: AgentState) -> dict[str, Any]:
    """
    LLM-based field extraction node.

    Runs after intent routing (booking/greeting path), before stage_resolver.
    Calls ai_service.extract_lead_data() to pull structured booking fields out of
    the guest message, persists non-null results to the Lead model, and syncs
    LeadFlowState.collected_data so stage_resolver sees fresh data without needing
    a prior view-level extraction.

    This makes the LangGraph path self-contained: it works correctly even when
    invoked from WhatsApp / Instagram or future channels that skip view-level
    pre-extraction, and provides a second chance for Telegram where the view
    already ran LLM extraction but may have raced with a DB save.

    Returns extracted_data dict (may be empty on failure – does not block the graph).
    """
    from apps.leads.ai_service import ai_service

    message = state.get('message', '')
    if not message or not ai_service.is_configured():
        return {'extracted_data': {}}

    lead = _get_lead(state)

    # Only run if the current flow card has required_fields we haven't collected yet.
    required_fields: list[str] = []
    try:
        flow_state = lead.flow_state
        card = flow_state.current_card
        required_fields = list(card.required_fields or []) if card else []
    except Exception:
        pass  # no flow card → skip extraction, stage_resolver will handle it

    if not required_fields:
        return {'extracted_data': {}}

    from apps.leads.services.stage_resolver import (
        collect_stage_data,
        has_stage_value,
        normalize_stage_field,
    )

    current = collect_stage_data(lead, state.get('lead_data') or {})
    missing = [
        f for f in required_fields
        if not has_stage_value(
            current.get(normalize_stage_field(str(f))),
            field=normalize_stage_field(str(f)),
        )
    ]
    if not missing:
        return {'extracted_data': {}}  # all fields already collected

    # Resolve company name for the extractor (optional context hint).
    company_name: str | None = None
    try:
        from apps.leads.models import AIConfig
        cfg = AIConfig.get_config(org=getattr(lead, 'organization', None))
        if cfg and cfg.company_profile:
            company_name = cfg.company_profile.split('\n')[0].strip() or None
    except Exception:
        pass

    try:
        extracted: dict = ai_service.extract_lead_data(
            message,
            state.get('conversation_history') or [],
            company_name,
        )
    except Exception as exc:
        logger.warning('extract_stage_data_node: extract_lead_data failed: %s', exc)
        return {'extracted_data': {}, 'errors': [f'extraction_error: {exc}']}

    if not extracted:
        return {'extracted_data': {}}

    # Persist non-null extracted values to the Lead model so that the rest of
    # the pipeline (stage_resolver, generate_response) sees up-to-date data.
    update_fields: list[str] = []
    date_fields = {'check_in_date', 'check_out_date'}
    for field, value in extracted.items():
        if not hasattr(lead, field) or value is None:
            continue
        if field in date_fields:
            if str(getattr(lead, field, '') or '') != str(value):
                setattr(lead, field, value)
                update_fields.append(field)
        elif field == 'guest_count':
            try:
                int_val = int(value)
                if lead.guest_count != int_val:
                    lead.guest_count = int_val
                    update_fields.append(field)
            except (TypeError, ValueError):
                pass
        else:
            if getattr(lead, field, None) != value:
                setattr(lead, field, value)
                update_fields.append(field)

    if update_fields:
        lead.save(update_fields=update_fields)
        logger.info('extract_stage_data_node: persisted %s to lead %s', update_fields, lead.pk)

    # Sync LeadFlowState.collected_data so stage_resolver picks up the new values.
    try:
        from apps.leads.services.stage_resolver import sync_stage_state
        flow_state = lead.flow_state
        resolution = sync_stage_state(
            flow_state,
            lead,
            {**(state.get('lead_data') or {}), **extracted},
        )
        if resolution.changed:
            flow_state.save(update_fields=['collected_data', 'updated_at'])
    except Exception as exc:
        logger.debug('extract_stage_data_node: flow_state sync skipped: %s', exc)

    return {'extracted_data': extracted}
