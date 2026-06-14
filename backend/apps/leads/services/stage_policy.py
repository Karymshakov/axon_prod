from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable

from apps.leads.services.stage_resolver import StageResolution, resolve_stage, sync_stage_state

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StagePolicy:
    card_id: int | None
    card_title: str
    allowed_tools: set[str] | None
    resolution: StageResolution | None = None

    @property
    def is_active(self) -> bool:
        return self.card_id is not None

    @property
    def has_tool_restriction(self) -> bool:
        return self.allowed_tools is not None

    def allows_tool(self, tool_name: str) -> bool:
        if self.allowed_tools is None:
            return True
        return tool_name in self.allowed_tools

    def as_context(self) -> dict[str, Any]:
        resolution = self.resolution
        return {
            'card_id': self.card_id,
            'title': self.card_title,
            'allowed_tools': sorted(self.allowed_tools) if self.allowed_tools is not None else [],
            'missing_fields': resolution.missing_fields if resolution else [],
            'is_complete': resolution.is_complete if resolution else True,
        }


def _current_flow_card(lead):
    if lead is None:
        return None, None
    try:
        flow_state = lead.flow_state
        return flow_state, flow_state.current_card
    except Exception:
        return None, None


def _infer_allowed_tools_from_card(card) -> set[str] | None:
    title = (
        f"{getattr(card, 'title', '') or ''} "
        f"{getattr(card, 'goal', '') or ''}"
    ).lower()
    if any(marker in title for marker in ('meal', 'питан', 'рацион', 'завтрак', 'ужин')):
        return {'get_room_options', 'get_family_room'}
    if any(marker in title for marker in ('contact', 'контакт', 'телефон', 'phone')):
        return set()
    return None


def _lead_has_booking_ready_for_handoff(lead, resolution: StageResolution | None) -> bool:
    if lead is None or resolution is None or not resolution.is_complete:
        return False
    if not resolution.required_fields:
        return False

    try:
        from apps.leads.services.stage_resolver import is_reliable_contact_person

        has_name = is_reliable_contact_person(lead)
    except Exception:
        has_name = bool(str(getattr(lead, 'contact_person', '') or '').strip())

    return has_name and all(
        bool(getattr(lead, field, None))
        for field in (
            'phone',
            'check_in_date',
            'check_out_date',
            'guest_count',
            'room_type_preference',
            'meal_plan',
        )
    )


def get_stage_policy(
    lead,
    lead_data: dict[str, Any] | None = None,
    message: str = '',
    *,
    sync: bool = False,
) -> StagePolicy | None:
    flow_state, card = _current_flow_card(lead)
    if not card:
        return None

    resolution = None
    if sync and flow_state is not None:
        resolution = sync_stage_state(flow_state, lead, lead_data or {}, message)
        if resolution.changed:
            flow_state.save(update_fields=['collected_data', 'updated_at'])
    elif flow_state is not None:
        resolution = resolve_stage(card, getattr(flow_state, 'collected_data', None) or {})

    raw_allowed = getattr(card, 'allowed_tools', None) or []
    allowed_tools = {str(tool).strip() for tool in raw_allowed if str(tool).strip()}
    if not allowed_tools:
        allowed_tools = _infer_allowed_tools_from_card(card)
    if (
        allowed_tools == set()
        and _lead_has_booking_ready_for_handoff(lead, resolution)
    ):
        allowed_tools = {'transfer_to_manager'}
    return StagePolicy(
        card_id=getattr(card, 'pk', None),
        card_title=getattr(card, 'title', '') or '',
        allowed_tools=allowed_tools,
        resolution=resolution,
    )


def restrict_tool_names(
    tool_names: Iterable[str],
    lead,
    *,
    lead_data: dict[str, Any] | None = None,
    message: str = '',
    sync: bool = False,
) -> set[str]:
    names = {str(name) for name in tool_names}
    policy = get_stage_policy(lead, lead_data, message, sync=sync)
    if policy is None or not policy.has_tool_restriction:
        return names

    restricted = names & (policy.allowed_tools or set())
    removed = sorted(names - restricted)
    if removed:
        logger.info(
            "[StagePolicy] card=%s restricted tools; removed=%s allowed=%s",
            policy.card_title,
            removed,
            sorted(policy.allowed_tools or []),
        )
    return restricted


def filter_tool_schemas(tool_schemas: list[dict[str, Any]], lead) -> list[dict[str, Any]]:
    policy = get_stage_policy(lead)
    if policy is None or not policy.has_tool_restriction:
        return tool_schemas

    filtered = [
        schema for schema in tool_schemas
        if policy.allows_tool(schema.get('function', {}).get('name', ''))
    ]
    removed = [
        schema.get('function', {}).get('name', '')
        for schema in tool_schemas
        if not policy.allows_tool(schema.get('function', {}).get('name', ''))
    ]
    if removed:
        logger.info(
            "[StagePolicy] card=%s removed tool schemas=%s",
            policy.card_title,
            sorted(name for name in removed if name),
        )
    return filtered


def enforce_tool_allowed(tool_name: str, lead) -> dict[str, Any] | None:
    policy = get_stage_policy(lead)
    if policy is None or policy.allows_tool(tool_name):
        return None

    logger.warning(
        "[StagePolicy] blocked disallowed tool=%s on card=%s",
        tool_name,
        policy.card_title,
    )
    return {
        'error': 'tool_not_allowed_on_stage',
        'tool': tool_name,
        'allowed_tools': sorted(policy.allowed_tools or []),
        'message': (
            'This tool is not allowed on the current funnel stage. '
            'Answer briefly if needed and return to the current stage goal.'
        ),
    }
