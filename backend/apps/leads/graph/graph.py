from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, StateGraph

from apps.leads.graph.nodes import (
    booking_agent_node,
    consultant_agent_node,
    cs_agent_node,
    dialogue_director_node,
    extract_stage_data_node,
    inbound_guardrails_node,
    load_context_node,
    route_intent_node,
    sanitize_response_node,
    stage_resolver_node,
)
from apps.leads.graph.state import AgentState


def _route(state: AgentState) -> str:
    route = state.get('route')
    if route == 'end':
        return END
    if route in {
        'router',
        'extract_stage_data',
        'stage_resolver',
        'dialogue_director',
        'booking',
        'cs',
        'consultant',
        'sanitize',
    }:
        return route
    return 'booking'


@lru_cache(maxsize=1)
def build_lead_dialogue_graph():
    graph = StateGraph(AgentState)

    graph.add_node('load_context', load_context_node)
    graph.add_node('guardrails', inbound_guardrails_node)
    graph.add_node('router', route_intent_node)
    graph.add_node('extract_stage_data', extract_stage_data_node)
    graph.add_node('stage_resolver', stage_resolver_node)
    graph.add_node('dialogue_director', dialogue_director_node)
    graph.add_node('booking', booking_agent_node)
    graph.add_node('cs', cs_agent_node)
    graph.add_node('consultant', consultant_agent_node)
    graph.add_node('sanitize', sanitize_response_node)

    graph.set_entry_point('load_context')
    graph.add_edge('load_context', 'guardrails')
    graph.add_conditional_edges('guardrails', _route)
    # Every routed message passes through extraction + stage resolution so side
    # questions cannot knock the guest out of the active funnel stage.
    graph.add_edge('router', 'extract_stage_data')
    graph.add_edge('extract_stage_data', 'stage_resolver')
    graph.add_edge('stage_resolver', 'dialogue_director')
    graph.add_conditional_edges('dialogue_director', _route)
    graph.add_edge('booking', 'sanitize')
    graph.add_edge('cs', 'sanitize')
    graph.add_edge('consultant', 'sanitize')
    graph.add_edge('sanitize', END)

    return graph.compile()


def run_lead_dialogue_graph(
    *,
    lead,
    combined_text: str,
    lead_data: dict | None = None,
    conversation_history: list[dict[str, str]] | None = None,
    activity_history: str | None = None,
    selected_media=None,
    is_pooled: bool = False,
    channel: str = '',
) -> str | None:
    selected_media_id = getattr(selected_media, 'pk', None)
    if not isinstance(selected_media_id, int):
        selected_media_id = None

    initial_state: AgentState = {
        'lead_id': lead.pk,
        'organization_id': lead.organization_id,
        'channel': channel,
        'message': combined_text,
        'lead_data': lead_data or {},
        'conversation_history': conversation_history or [],
        'activity_history': activity_history,
        'selected_media_id': selected_media_id,
        'selected_media': selected_media if selected_media_id is None else None,
        'is_pooled': is_pooled,
        'context': {},
        'tool_results': [],
        'errors': [],
        'metadata': {},
        'stage_resolution': {},
    }
    final_state = build_lead_dialogue_graph().invoke(initial_state)
    return final_state.get('final_response')
