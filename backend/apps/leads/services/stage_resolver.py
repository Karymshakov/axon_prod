from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


FIELD_ALIASES = {
    'checkin_date': 'check_in_date',
    'check_in': 'check_in_date',
    'checkout_date': 'check_out_date',
    'check_out': 'check_out_date',
    'num_guests': 'guest_count',
    'guests': 'guest_count',
    'room_type': 'room_type_preference',
}

LEAD_STAGE_FIELDS = (
    'contact_person',
    'phone',
    'email',
    'check_in_date',
    'check_out_date',
    'guest_count',
    'room_type_preference',
    'meal_plan',
    'problem_description',
    'preferred_contact_time',
    'discovery_source',
    'discovery_source_detail',
)


def is_reliable_contact_person(lead, value: Any | None = None) -> bool:
    """Return True when contact_person looks like a real guest name, not a handle."""
    name = str(value if value is not None else getattr(lead, 'contact_person', '') or '').strip()
    if not has_stage_value(name):
        return False

    lowered = name.lower().lstrip('@')
    telegram_username = str(getattr(lead, 'telegram_username', '') or '').lower().lstrip('@')
    instagram_username = str(getattr(lead, 'instagram_username', '') or '').lower().lstrip('@')
    compact_name = re.sub(r'[\s._-]+', '', lowered)
    compact_telegram = re.sub(r'[\s._-]+', '', telegram_username)
    compact_instagram = re.sub(r'[\s._-]+', '', instagram_username)
    if compact_name and compact_name in {compact_telegram, compact_instagram}:
        return False
    if re.search(r'[@_\d]', name):
        return False

    words = re.findall(r'[A-Za-zА-Яа-яЁёӨөҮүҢңҚқҺһІі-]+', name)
    if not (1 <= len(words) <= 4):
        return False

    # Telegram/Instagram display names are often short Latin handles such as
    # "NK" or "Qim". Do not treat them as the real booking guest name.
    has_social_handle = bool(compact_telegram or compact_instagram)
    latin_letters = ''.join(re.findall(r'[A-Za-z]', name))
    non_latin_letters = re.sub(r'[A-Za-z\s-]', '', name)
    if has_social_handle and latin_letters and not non_latin_letters:
        if len(latin_letters) <= 3:
            return False
        if len(latin_letters) <= 4 and name.upper() == name:
            return False

    return 1 <= len(words) <= 4


_TITLE_REQUIRED_FIELD_FALLBACKS = (
    (('meal', 'питан', 'рацион', 'завтрак', 'ужин'), ('meal_plan',)),
    (('contact', 'контакт', 'телефон', 'phone'), ('contact_person', 'phone')),
    (('room selection', 'выбор номера', 'подбор номера'), ('room_type_preference',)),
)


@dataclass(frozen=True)
class StageResolution:
    collected_data: dict[str, Any]
    required_fields: list[str]
    missing_fields: list[str]
    is_complete: bool
    changed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            'collected_data': self.collected_data,
            'required_fields': self.required_fields,
            'missing_fields': self.missing_fields,
            'is_complete': self.is_complete,
            'changed': self.changed,
        }


def normalize_stage_field(field: str) -> str:
    field = (field or '').strip()
    return FIELD_ALIASES.get(field, field)


def infer_required_fields_from_card(card) -> list[str]:
    explicit = [
        normalize_stage_field(str(field))
        for field in (getattr(card, 'required_fields', None) or [])
        if str(field).strip()
    ]
    title = (
        f"{getattr(card, 'title', '') or ''} "
        f"{getattr(card, 'goal', '') or ''}"
    ).lower()
    is_contact_stage = any(marker in title for marker in ('contact', 'контакт', 'телефон', 'phone'))
    if explicit:
        if is_contact_stage:
            fields = [field for field in explicit if field != 'email']
            for field in ('contact_person', 'phone'):
                if field not in fields:
                    fields.append(field)
            return fields
        return explicit

    for markers, fields in _TITLE_REQUIRED_FIELD_FALLBACKS:
        if any(marker in title for marker in markers):
            return [normalize_stage_field(field) for field in fields]
    return []


def has_stage_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip()) and value.strip().lower() not in {
            'none', 'null', 'unknown', 'not specified', 'не указано', 'неизвестно', '-',
        }
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _serialize_stage_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def collect_stage_data(lead, lead_data: dict[str, Any] | None = None, message: str = '') -> dict[str, Any]:
    data: dict[str, Any] = {}

    for field in LEAD_STAGE_FIELDS:
        value = getattr(lead, field, None) if lead is not None else None
        value = _serialize_stage_value(value)
        if field == 'contact_person' and not is_reliable_contact_person(lead, value):
            continue
        if has_stage_value(value):
            data[field] = value

    custom_fields = getattr(lead, 'custom_fields', None) if lead is not None else None
    if isinstance(custom_fields, dict):
        for key, value in custom_fields.items():
            norm_key = normalize_stage_field(str(key))
            if has_stage_value(value):
                data[norm_key] = value

    for key, value in (lead_data or {}).items():
        norm_key = normalize_stage_field(str(key))
        value = _serialize_stage_value(value)
        if norm_key == 'contact_person' and not is_reliable_contact_person(lead, value):
            continue
        if has_stage_value(value):
            data[norm_key] = value

    # Regex fallback: only fills fields that are STILL missing after reading the
    # Lead model and lead_data dict. The LLM extractor at the view layer runs first
    # and persists results on the Lead model, so this block is a no-op in the
    # normal request path and only activates for preview calls or direct unit tests.
    if message:
        try:
            from apps.leads.services.booking_tools import _extract_guest_count_from_text, _infer_relative_booking_dates

            if 'guest_count' not in data:
                guest_count = _extract_guest_count_from_text(message)
                if guest_count:
                    data['guest_count'] = guest_count

            if 'check_in_date' not in data or 'check_out_date' not in data:
                check_in, check_out = _infer_relative_booking_dates(message)
                if check_in and 'check_in_date' not in data:
                    data['check_in_date'] = check_in
                if check_out and 'check_out_date' not in data:
                    data['check_out_date'] = check_out
        except Exception:
            pass

    return data


def resolve_stage(card, collected_data: dict[str, Any] | None, *, changed: bool = False) -> StageResolution:
    required_fields = infer_required_fields_from_card(card)
    data = dict(collected_data or {})
    missing_fields = [
        field for field in required_fields
        if not has_stage_value(data.get(field))
    ]
    return StageResolution(
        collected_data=data,
        required_fields=required_fields,
        missing_fields=missing_fields,
        is_complete=not missing_fields,
        changed=changed,
    )


def sync_stage_state(flow_state, lead, lead_data: dict[str, Any] | None = None, message: str = '') -> StageResolution:
    existing = dict(flow_state.collected_data or {})
    latest = collect_stage_data(lead, lead_data, message)
    merged = {**existing, **latest}
    changed = flow_state.collected_data != merged
    resolution = resolve_stage(flow_state.current_card, merged, changed=changed)

    if resolution.changed:
        flow_state.collected_data = resolution.collected_data

    return resolution


def stage_resolution_instruction(resolution: StageResolution) -> str:
    if not resolution.required_fields:
        return ''
    if resolution.is_complete:
        return 'Stage status: all required fields are collected.'
    return (
        'Stage status: stay on this stage until these fields are collected: '
        + ', '.join(resolution.missing_fields)
        + '. If the guest asks a side question, answer it briefly and then return to collecting the missing fields.'
    )
