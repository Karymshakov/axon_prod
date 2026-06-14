from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict


AgentIntent = Literal['booking', 'faq', 'undecided', 'greeting', 'off_topic']
AgentRoute = Literal[
    'guardrails',
    'router',
    'extract_stage_data',
    'stage_resolver',
    'dialogue_director',
    'booking',
    'cs',
    'consultant',
    'sanitize',
    'end',
]


def append_items(left: list[Any] | None, right: list[Any] | None) -> list[Any]:
    return [*(left or []), *(right or [])]


def merge_dicts(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    return {**(left or {}), **(right or {})}


class AgentState(TypedDict, total=False):
    lead_id: int
    organization_id: int | None
    channel: str

    message: str
    lead_data: dict[str, Any]
    conversation_history: list[dict[str, str]]
    activity_history: str | None
    is_pooled: bool
    selected_media_id: int | None
    selected_media: Any | None

    context: Annotated[dict[str, Any], merge_dicts]
    intent: AgentIntent
    confidence: float
    route: AgentRoute
    stage_resolution: Annotated[dict[str, Any], merge_dicts]
    dialogue_directive: Annotated[dict[str, Any], merge_dicts]

    guardrail_response: str | None
    agent_response: str | None
    final_response: str | None

    extracted_data: Annotated[dict[str, Any], merge_dicts]
    tool_results: Annotated[list[dict[str, Any]], append_items]
    errors: Annotated[list[str], append_items]
    metadata: Annotated[dict[str, Any], merge_dicts]
