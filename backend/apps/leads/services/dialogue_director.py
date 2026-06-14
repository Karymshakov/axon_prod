from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.leads.services.stage_resolver import StageResolution, infer_required_fields_from_card, normalize_stage_field


BOOKING_ROUTE = 'booking'
CS_ROUTE = 'cs'
CONSULTANT_ROUTE = 'consultant'


@dataclass(frozen=True)
class DialogueDirective:
    route: str
    intent: str
    stage_active: bool
    stage_title: str = ''
    stage_goal: str = ''
    required_fields: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    collected_data: dict[str, Any] = field(default_factory=dict)
    allowed_tools: list[str] = field(default_factory=list)
    response_policy: dict[str, Any] = field(default_factory=dict)
    return_to_funnel_instruction: str = ''
    must_return_to_funnel: bool = False
    response_goal: str = ''
    forbidden_actions: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            'route': self.route,
            'intent': self.intent,
            'stage_active': self.stage_active,
            'stage_title': self.stage_title,
            'stage_goal': self.stage_goal,
            'required_fields': self.required_fields,
            'missing_fields': self.missing_fields,
            'collected_data': self.collected_data,
            'allowed_tools': self.allowed_tools,
            'response_policy': self.response_policy,
            'return_to_funnel_instruction': self.return_to_funnel_instruction,
            'must_return_to_funnel': self.must_return_to_funnel,
            'response_goal': self.response_goal,
            'forbidden_actions': self.forbidden_actions,
        }

    def to_system_instruction(self) -> str:
        if not self.stage_active:
            return ''

        lines = [
            'The server-side Dialogue Director is authoritative for this turn.',
            f'Intent route: {self.intent} -> {self.route}.',
            f'Current funnel stage: {self.stage_title or "unknown"}.',
        ]
        if self.stage_goal:
            lines.append(f'Stage goal: {self.stage_goal}')
        if self.required_fields:
            lines.append('Required fields: ' + ', '.join(self.required_fields))
        if self.missing_fields:
            lines.append('Missing fields that must still be collected: ' + ', '.join(self.missing_fields))
        else:
            lines.append('Stage status: complete.')
        if self.allowed_tools:
            lines.append('Allowed tools on this stage: ' + ', '.join(self.allowed_tools))
        if self.response_goal:
            lines.append('Response goal for this exact turn: ' + self.response_goal)
        if self.response_policy:
            lines.append(f'Response policy: {self.response_policy}')
        if self.return_to_funnel_instruction:
            lines.append('Return-to-funnel rule: ' + self.return_to_funnel_instruction)
        if self.must_return_to_funnel:
            lines.append(
                'If the guest asked a side question, answer it briefly first, then immediately return '
                'to the current funnel stage and ask for the missing field(s).'
            )
        if self.forbidden_actions:
            lines.append('Forbidden this turn: ' + '; '.join(self.forbidden_actions))
        lines.append(
            'Never advance the funnel yourself. The backend advances stages only after required fields are present.'
        )
        return '\n'.join(lines)


def _base_route(intent: str) -> str:
    if intent in {'faq', 'off_topic'}:
        return CS_ROUTE
    if intent == 'undecided':
        return CONSULTANT_ROUTE
    return BOOKING_ROUTE


def _resolution_from_dict(data: dict[str, Any] | None) -> StageResolution | None:
    if not isinstance(data, dict) or not data:
        return None
    return StageResolution(
        collected_data=dict(data.get('collected_data') or {}),
        required_fields=[
            normalize_stage_field(str(field))
            for field in (data.get('required_fields') or [])
            if str(field).strip()
        ],
        missing_fields=[
            normalize_stage_field(str(field))
            for field in (data.get('missing_fields') or [])
            if str(field).strip()
        ],
        is_complete=bool(data.get('is_complete', True)),
        changed=bool(data.get('changed', False)),
    )


def _lead_is_final_or_booking_complete(lead, resolution: StageResolution | None = None) -> bool:
    if lead is None:
        return False

    try:
        from apps.leads.ai_diagnostics import get_lead_stage

        stage = get_lead_stage(lead)
        if getattr(stage, 'is_final', False):
            return True
    except Exception:
        pass

    if str(getattr(lead, 'status', '') or '').lower() in {'won', 'converted'}:
        return True

    try:
        from apps.leads.services.stage_resolver import is_reliable_contact_person

        has_reliable_name = is_reliable_contact_person(lead)
    except Exception:
        has_reliable_name = bool(str(getattr(lead, 'contact_person', '') or '').strip())

    lead_has_booking = all(
        bool(getattr(lead, field, None))
        for field in ('phone', 'check_in_date', 'check_out_date', 'guest_count', 'room_type_preference', 'meal_plan')
    )
    if has_reliable_name and lead_has_booking:
        return True

    if resolution is not None and resolution.is_complete:
        collected = resolution.collected_data or {}
        has_contact = bool(collected.get('phone') or getattr(lead, 'phone', None))
        has_dates = bool(
            collected.get('check_in_date')
            and collected.get('check_out_date')
        ) or bool(getattr(lead, 'check_in_date', None) and getattr(lead, 'check_out_date', None))
        has_guest_count = bool(collected.get('guest_count') or getattr(lead, 'guest_count', None))
        has_room = bool(collected.get('room_type_preference') or getattr(lead, 'room_type_preference', None))
        has_meal = bool(collected.get('meal_plan') or getattr(lead, 'meal_plan', None))
        if has_reliable_name and has_contact and has_dates and has_guest_count and has_room and has_meal:
            return True

    return False


def build_dialogue_directive(
    *,
    lead,
    intent: str,
    stage_resolution: StageResolution | dict[str, Any] | None = None,
) -> DialogueDirective:
    """
    Convert current flow state and router intent into a deterministic routing
    and response policy. The LLM may write the text, but this object owns the
    funnel rules for the turn.
    """
    route = _base_route(intent)
    flow_state = None
    card = None
    try:
        flow_state = lead.flow_state if lead is not None else None
        card = flow_state.current_card if flow_state is not None else None
    except Exception:
        card = None

    if card is None:
        return DialogueDirective(
            route=route,
            intent=intent,
            stage_active=False,
            response_goal='Handle the guest request naturally and keep the conversation moving toward booking.',
        )

    if isinstance(stage_resolution, dict):
        resolution = _resolution_from_dict(stage_resolution)
    else:
        resolution = stage_resolution

    if resolution is None:
        try:
            from apps.leads.services.stage_resolver import resolve_stage

            resolution = resolve_stage(card, getattr(flow_state, 'collected_data', None) or {})
        except Exception:
            required = infer_required_fields_from_card(card)
            resolution = StageResolution(
                collected_data={},
                required_fields=required,
                missing_fields=required,
                is_complete=False,
            )

    missing = list(resolution.missing_fields)
    try:
        from apps.leads.services.stage_policy import get_stage_policy

        policy = get_stage_policy(lead)
        policy_tools = policy.allowed_tools if policy else None
    except Exception:
        policy_tools = None
    allowed_tools = sorted(policy_tools) if policy_tools is not None else sorted(
        str(tool).strip()
        for tool in (getattr(card, 'allowed_tools', None) or [])
        if str(tool).strip()
    )
    booking_complete = _lead_is_final_or_booking_complete(lead, resolution)
    must_return = bool(missing and intent in {'faq', 'off_topic', 'undecided'} and not booking_complete)

    forbidden = []
    if booking_complete:
        forbidden.append('do not ask to continue booking; the booking request is already complete')
        forbidden.append('do not repeat booking confirmation unless the guest explicitly asks to review it')
    if missing:
        forbidden.append('do not say the booking stage is complete')
        forbidden.append('do not ask again for fields already in collected_data')
    if policy_tools is not None and 'transfer_to_manager' not in policy_tools:
        forbidden.append('do not promise a manager handoff or say a manager will contact the guest')
    if policy_tools is not None and not ({'get_room_options', 'get_family_room'} & policy_tools):
        forbidden.append('do not quote room prices or availability unless already present in verified tool data')

    if booking_complete:
        response_goal = (
            'Handle this as a post-booking guest question. Answer the question directly from verified facts. '
            'If exact information is unavailable, say that the manager can clarify it during confirmation; '
            'do not imply the manager is already preparing an answer.'
        )
    elif missing:
        if must_return:
            response_goal = (
                'Answer the side question in one short paragraph, then ask for: '
                + ', '.join(missing)
            )
        else:
            response_goal = 'Collect the next missing field(s): ' + ', '.join(missing)
    else:
        response_goal = 'Continue to the next logical booking step.'

    return DialogueDirective(
        route=route,
        intent=intent,
        stage_active=True,
        stage_title=getattr(card, 'title', '') or '',
        stage_goal=getattr(card, 'goal', '') or '',
        required_fields=list(resolution.required_fields),
        missing_fields=missing,
        collected_data=dict(resolution.collected_data),
        allowed_tools=allowed_tools,
        response_policy=dict(getattr(card, 'response_policy', None) or {}),
        return_to_funnel_instruction=getattr(card, 'return_to_funnel_instruction', '') or '',
        must_return_to_funnel=must_return,
        response_goal=response_goal,
        forbidden_actions=forbidden,
    )


def dialogue_directive_instruction(directive: dict[str, Any] | DialogueDirective | None) -> str:
    if directive is None:
        return ''
    if isinstance(directive, DialogueDirective):
        return directive.to_system_instruction()
    if not isinstance(directive, dict) or not directive.get('stage_active'):
        return ''
    return DialogueDirective(
        route=str(directive.get('route') or BOOKING_ROUTE),
        intent=str(directive.get('intent') or 'booking'),
        stage_active=bool(directive.get('stage_active')),
        stage_title=str(directive.get('stage_title') or ''),
        stage_goal=str(directive.get('stage_goal') or ''),
        required_fields=list(directive.get('required_fields') or []),
        missing_fields=list(directive.get('missing_fields') or []),
        collected_data=dict(directive.get('collected_data') or {}),
        allowed_tools=list(directive.get('allowed_tools') or []),
        response_policy=dict(directive.get('response_policy') or {}),
        return_to_funnel_instruction=str(directive.get('return_to_funnel_instruction') or ''),
        must_return_to_funnel=bool(directive.get('must_return_to_funnel')),
        response_goal=str(directive.get('response_goal') or ''),
        forbidden_actions=list(directive.get('forbidden_actions') or []),
    ).to_system_instruction()
