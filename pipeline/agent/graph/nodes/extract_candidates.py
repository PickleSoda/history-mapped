from __future__ import annotations

import json
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from pipeline.agent.config import AgentConfig
from pipeline.agent.llm import create_llm
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.entities import CandidateEntity
from pipeline.agent.schemas.relations import CandidateRelation
from pipeline.agent.schemas.validation import AuditEvent, PipelineError

_PROMPT = """You are a historical entity extractor. Given a list of events, extract all candidate entities and relations.

Allowed entity types: person, political_entity, dynasty, city, event_battle, event_war, event_treaty, trade_route, cultural_work, archaeological_culture, language, religious_movement, infrastructure_monument, currency_monetary_system, natural_resource.

Allowed relation types: participated_in, fought_at, rules, governed_by, part_of, contains, capital_of, born_in, died_in, preceded_by, succeeded_by, caused, resulted_from, at_war_with, allied_with, trades_with.

Output strictly as JSON:
{"candidate_entities": [{"label": "...", "entity_type": "...", "start_date": "...", "end_date": "...", "source_event": "...", "aliases": []}], "candidate_relations": [{"source_label": "...", "target_label": "...", "relationship_type": "...", "start_date": "...", "end_date": "...", "source_event": "..."}]}
"""


def extract_candidates(state: AgentRunState) -> AgentRunState:
    cfg = AgentConfig()
    llm = create_llm(cfg.extract_model, cfg.openai_api_key, cfg.llm_base_url)
    events_json = json.dumps([e.model_dump() for e in state["parsed_events"]], default=str)
    messages = [SystemMessage(content=_PROMPT), HumanMessage(content=events_json)]
    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)
    try:
        data = json.loads(content)
        entities = [CandidateEntity(**e) for e in data.get("candidate_entities", [])]
        relations = [CandidateRelation(**r) for r in data.get("candidate_relations", [])]
    except (json.JSONDecodeError, TypeError) as exc:
        state["errors"].append(
            PipelineError(
                node="extract_candidates",
                error_type="json_parse",
                message=str(exc),
                context={"raw_response": content},
            )
        )
        entities = []
        relations = []
    state["candidate_entities"] = entities
    state["candidate_relations"] = relations
    state["audit_log"].append(
        AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            node="extract_candidates",
            action="extracted_candidates",
            output_summary=f"{len(entities)} entities, {len(relations)} relations",
        )
    )
    return state
