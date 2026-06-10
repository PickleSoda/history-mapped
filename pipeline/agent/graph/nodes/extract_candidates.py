from __future__ import annotations

import json
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from pipeline.agent.config import AgentConfig
from pipeline.agent.llm import create_llm_with_fallbacks
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.entities import CandidateEntity
from pipeline.agent.schemas.relations import CandidateRelation
from pipeline.agent.schemas.validation import AuditEvent, PipelineError

_PROMPT = """You are a historical entity extractor. Given a list of events, extract all candidate entities and relations.

Allowed entity types (grouped by domain):

POLITY — political_entity, dynasty, person, military_unit, diplomatic_relationship, social_class
PLACE — city, infrastructure_monument, extraction_infra, educational_institution
EVENT — event_war, event_battle, event_treaty, event_rebellion, event_natural_disaster, event_tech_adoption, event_legal_reform, migration, epidemic_disease
ECONOMY — trade_route, natural_resource, currency_monetary_system
CULTURE — cultural_work, intellectual_movement, archaeological_culture, language, religious_text, legal_code, religious_movement, technology

Allowed relation types (grouped by domain):

Political — rules, governed_by, vassal_of, suzerain_of, allied_with, at_war_with, succeeded_by, preceded_by, part_of, contains, capital_of, split_from, merged_into
Person — born_in, died_in, resided_in, commanded, founded, authored, commissioned, married_to, parent_of, child_of, sibling_of, mentor_of, student_of, assassinated_by, member_of_dynasty, patron_of
Military — participated_in, fought_at, defeated_at, victorious_at, stationed_at, recruited_from, commanded_by
Economic — trades_with, connects, produces, extracts, supplies, controlled_by, passes_through, minted_by, used_currency
Religious/Cultural — adheres_to, official_religion_of, persecuted_by, influenced_by, inspired, schism_from, translated_into, located_at, built_by, destroyed_by, restored_by
Causal — caused, resulted_from, contributed_to, enabled, prevented, weakened, strengthened
Knowledge — invented, adopted, taught_at, spread_to, required_by, replaced_by
Diplomatic — signed_by, violated_by, guaranteed_by, mediated_by, enforced_by

Output strictly as JSON:
{"candidate_entities": [{"label": "...", "entity_type": "...", "start_date": "...", "end_date": "...", "source_event": "...", "aliases": []}], "candidate_relations": [{"source_label": "...", "target_label": "...", "relationship_type": "...", "start_date": "...", "end_date": "...", "source_event": "..."}]}
"""


def extract_candidates(state: AgentRunState) -> AgentRunState:
    cfg = AgentConfig()
    llm = create_llm_with_fallbacks("extract_model", cfg)
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
