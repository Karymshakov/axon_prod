from __future__ import annotations

from .models import AIConfig, Lead


CHANNEL_PAUSE_FIELDS = {
    'telegram': 'telegram_ai_paused',
    'instagram': 'instagram_ai_paused',
    'whatsapp': 'whatsapp_ai_paused',
}


def get_channel_pause_field(channel: str) -> str | None:
    return CHANNEL_PAUSE_FIELDS.get((channel or '').lower())


def is_channel_ai_globally_paused(channel: str, *, config: AIConfig | None = None, lead: Lead | None = None) -> bool:
    field_name = get_channel_pause_field(channel)
    if not field_name:
        return False

    resolved_config = config
    if resolved_config is None and lead is not None:
        resolved_config = AIConfig.get_config(org=lead.organization)

    if resolved_config is None:
        return False

    return bool(getattr(resolved_config, field_name, False))


def get_channel_ai_status_label(channel: str, *, config: AIConfig | None = None, lead: Lead | None = None) -> str:
    return 'Paused globally for this channel' if is_channel_ai_globally_paused(channel, config=config, lead=lead) else 'Active'
