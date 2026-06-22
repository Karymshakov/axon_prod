from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from django.utils import timezone

from .channel_ai_control import is_channel_ai_globally_paused
from .models import Lead, LeadActivity, PipelineStage


OUTCOME_REPLIED = 'replied'
OUTCOME_SKIPPED = 'skipped'
OUTCOME_DELAYED = 'delayed'
OUTCOME_FAILED = 'failed'
OUTCOME_PROCESSING = 'processing'


def _now_iso() -> str:
    return timezone.localtime(timezone.now()).isoformat()


def _activity_obj(activity_or_id: LeadActivity | int) -> LeadActivity:
    if isinstance(activity_or_id, LeadActivity):
        return activity_or_id
    return LeadActivity.objects.get(id=activity_or_id)


def _save(activity: LeadActivity, metadata: dict[str, Any]) -> None:
    activity.metadata = metadata
    activity.save(update_fields=['metadata'])


def _ensure_diagnostics(metadata: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    base = metadata.copy() if isinstance(metadata, dict) else {}
    diagnostics = base.get('ai_diagnostics')
    if not isinstance(diagnostics, dict):
        diagnostics = {}
        base['ai_diagnostics'] = diagnostics

    diagnostics.setdefault('schema_version', 1)
    diagnostics.setdefault('steps', [])
    diagnostics.setdefault('current_state', OUTCOME_PROCESSING)
    diagnostics.setdefault('final_result', OUTCOME_PROCESSING)
    diagnostics.setdefault('final_summary', 'Processing has started')
    diagnostics.setdefault('started_at', _now_iso())
    diagnostics['updated_at'] = _now_iso()
    return base, diagnostics


def _append_step(diagnostics: dict[str, Any], code: str, label: str, *, detail: str = '', status: str = 'info') -> None:
    diagnostics.setdefault('steps', []).append({
        'code': code,
        'label': label,
        'detail': detail,
        'status': status,
        'at': _now_iso(),
    })
    diagnostics['updated_at'] = _now_iso()


def _lead_reference(lead: Lead, channel: str) -> str:
    name = lead.contact_person or f'Lead #{lead.id}'
    if channel == 'telegram':
        destination = lead.telegram_username or lead.telegram_chat_id or 'Telegram contact unavailable'
    elif channel == 'whatsapp':
        destination = lead.whatsapp_phone or lead.phone or 'WhatsApp number unavailable'
    else:
        destination = lead.instagram_username or lead.instagram_user_id or 'Instagram contact unavailable'
    return f'{name} / {destination}'


def initialize_inbound_diagnostics(
    activity_or_id: LeadActivity | int,
    *,
    lead: Lead,
    channel: str,
    message_text: str,
    created_new_lead: bool = False,
) -> None:
    activity = _activity_obj(activity_or_id)
    metadata, diagnostics = _ensure_diagnostics(activity.metadata)
    diagnostics.update({
        'channel': channel,
        'message_excerpt': (message_text or '').strip()[:220],
        'lead_id': lead.id,
        'lead_label': lead.contact_person or f'Lead #{lead.id}',
    })
    if not diagnostics.get('steps'):
        _append_step(diagnostics, 'message_received', 'Message received', status='success')
        match_detail = _lead_reference(lead, channel)
        if created_new_lead:
            match_detail = f'New lead created and matched: {match_detail}'
        _append_step(diagnostics, 'conversation_matched', 'Conversation matched to lead', detail=match_detail, status='success')
    _save(activity, metadata)


def add_diagnostic_step(
    activity_or_id: LeadActivity | int,
    code: str,
    label: str,
    *,
    detail: str = '',
    status: str = 'info',
) -> None:
    activity = _activity_obj(activity_or_id)
    metadata, diagnostics = _ensure_diagnostics(activity.metadata)
    _append_step(diagnostics, code, label, detail=detail, status=status)
    _save(activity, metadata)


def normalize_ai_response_text(response_text: str | None) -> str:
    if not response_text:
        return ''

    cleaned = response_text
    cleanup_patterns = (
        (r'!\[.*?\]\(.*?\)', ''),
        (r'\[([^\]]+)\]\((https?://[^\)]+)\)', r'\2'),
        (r'\*\*(.*?)\*\*', r'\1'),
        (r'\*(.*?)\*', r'\1'),
        (r'__(.*?)__', r'\1'),
        (r'_(.*?)_', r'\1'),
        (r'`(.*?)`', r'\1'),
    )
    for pattern, replacement in cleanup_patterns:
        cleaned = re.sub(pattern, replacement, cleaned)
    return cleaned.strip()


def generate_with_blank_retry(
    activity_or_id: LeadActivity | int,
    generate_reply: Callable[[], str | None],
) -> str:
    response_text = normalize_ai_response_text(generate_reply())
    if response_text:
        add_diagnostic_step(
            activity_or_id,
            'generation_succeeded',
            'AI generation succeeded',
            detail='A reply was generated successfully',
            status='success',
        )
        add_diagnostic_step(
            activity_or_id,
            'retry_attempt',
            'Retry attempted',
            detail='No retry was needed',
            status='success',
        )
        return response_text

    add_diagnostic_step(
        activity_or_id,
        'generation_blank',
        'AI returned blank response',
        detail='The first generation attempt produced no message content',
        status='warning',
    )
    add_diagnostic_step(
        activity_or_id,
        'retry_attempt',
        'Retry attempted',
        detail='Automatic retry started using the same AI prompt path and reply logic',
        status='info',
    )

    retry_response_text = normalize_ai_response_text(generate_reply())
    if retry_response_text:
        add_diagnostic_step(
            activity_or_id,
            'retry_succeeded',
            'Retry generated a reply',
            detail='The retry returned non-empty content, so the reply will be sent normally',
            status='success',
        )
        return retry_response_text

    add_diagnostic_step(
        activity_or_id,
        'retry_blank',
        'Retry also returned blank response',
        detail='The retry also produced no message content, so nothing was sent',
        status='warning',
    )
    finalize_diagnostics(
        activity_or_id,
        result=OUTCOME_SKIPPED,
        summary='No reply sent — both AI generation attempts returned blank content',
        status='warning',
    )
    return ''


def finalize_diagnostics(
    activity_or_id: LeadActivity | int,
    *,
    result: str,
    summary: str,
    status: str = 'success',
) -> None:
    activity = _activity_obj(activity_or_id)
    metadata, diagnostics = _ensure_diagnostics(activity.metadata)
    diagnostics['current_state'] = result
    diagnostics['final_result'] = result
    diagnostics['final_summary'] = summary
    diagnostics['completed_at'] = _now_iso()
    _append_step(diagnostics, 'final_result', 'Final result', detail=summary, status=status)
    _save(activity, metadata)


def get_lead_stage(lead: Lead) -> PipelineStage | None:
    filters = {'key': lead.status}
    if lead.organization_id:
        filters['organization'] = lead.organization
    stage = PipelineStage.objects.filter(**filters).first()
    if stage:
        return stage
    return PipelineStage.objects.filter(key=lead.status).first()


def evaluate_auto_reply_eligibility(
    lead: Lead,
    *,
    channel: str,
    config: Any,
    ai_ready: bool,
    channel_ready: bool,
    destination: str,
    allow_final_stage: bool = False,
) -> tuple[bool, str]:
    if lead.ai_paused and lead.ai_paused_by != 'AI Handoff':
        return False, 'AI paused for this lead'

    if is_channel_ai_globally_paused(channel, config=config, lead=lead):
        return False, f'AI paused globally for {channel.title()}'

    stage = get_lead_stage(lead)
    if stage and stage.is_final and not allow_final_stage:
        return False, f'Lead is in a final stage: {stage.name}'

    if lead.do_not_contact:
        return False, 'Lead is marked as do not contact'

    if config is None:
        return False, 'Missing organization AI config'

    if not getattr(config, 'ai_auto_response', False):
        return False, 'Auto-response disabled in settings'

    if not ai_ready:
        return False, 'AI service is not configured'

    if not destination:
        if channel == 'telegram':
            return False, 'Missing Telegram chat ID'
        if channel == 'whatsapp':
            return False, 'Missing WhatsApp destination'
        return False, 'Missing channel destination'

    if not channel_ready:
        if channel == 'telegram':
            return False, 'Telegram sending is not configured'
        if channel == 'whatsapp':
            return False, 'WhatsApp sending is not configured'
        return False, 'Channel sending is not configured'

    return True, 'Eligible'
