from __future__ import annotations

import json
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from pipeline.agent.config import AgentConfig
from pipeline.agent.llm import create_llm_with_fallbacks
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.entities import CandidateEntity
from pipeline.agent.schemas.relations import CandidateRelation
from pipeline.agent.json_utils import parse_llm_json
from pipeline.agent.log_config import get_logger
from pipeline.agent.schemas.validation import AuditEvent, PipelineError

logger = get_logger(__name__)

# Bound on critic passes. A single extraction pass leaves ~half the entities
# unconnected (orphans) and misses container polities / implicit relations; a
# couple of "what did you miss?" passes recover most of the tail without
# unbounded cost. The loop also stops early as soon as a pass finds nothing new.
MAX_CRITIC_ITERATIONS = 2

_PROMPT = """You are a completeness critic for a historical knowledge-graph extractor. You are given the source
text and the entities and relations already extracted from it. Your job is to find what is MISSING — do not
repeat anything already present.

Look specifically for:
1. Container polities/dynasties named or clearly implied but not yet an entity (empires, kingdoms, states).
2. People, places, battles/wars, technologies, religions, or DISEASES mentioned in the text but not yet
   extracted. Named diseases/plagues/pandemics ("Black Death", "Spanish Flu", "smallpox") must be their own
   `epidemic_disease` entity, not just an event.
3. IMPLICIT relations the text supports but that are absent: succeeded_by/preceded_by, part_of (member states ↔
   coalitions/empires), capital_of, participated_in / victorious_at / defeated_at for every belligerent of a
   battle, born_in/died_in, at_war_with between opposing sides.
4. Relations among ALREADY-extracted entities that were never connected (reduce orphan entities).

PRIORITY — orphans: the `orphan_entities` list below contains entities with NO relationships yet. Add at least
one relationship for EACH of them that the source text or well-established history supports (e.g. a belligerent
polity must be `at_war_with` its opponent and/or `participated_in` the relevant war/battle).

PRECISION: only add relationships actually supported by the text or well-established history — do not pad. Respect
relation-type semantics: `member_of_dynasty` connects a PERSON to a named ruling DYNASTY only — never to a
republic, empire, or state (use `part_of` / `governed_by` for those).

Use the same entity_type and relationship_type vocabulary as the existing items. Output ONLY new items not
already in the provided lists. If nothing is missing, return empty lists.

Output strictly as JSON:
{"candidate_entities": [{"label": "...", "entity_type": "...", "start_date": "...", "end_date": "...", "aliases": []}],
 "candidate_relations": [{"source_label": "...", "target_label": "...", "relationship_type": "...", "start_date": "...", "end_date": "..."}]}
"""


def _entity_key(label: str) -> str:
    return (label or "").strip().lower()


def _relation_key(source: str, rtype: str, target: str) -> tuple[str, str, str]:
    return ((source or "").strip().lower(), (rtype or "").strip().lower(), (target or "").strip().lower())


def completeness_critic(state: AgentRunState) -> AgentRunState:
    """Re-read the source text and add entities/relations the first extraction
    missed. Bounded self-loop: keeps going (up to MAX_CRITIC_ITERATIONS) while
    each pass still finds something new, then routes downstream."""
    cfg = AgentConfig()
    iterations = state.get("critic_iterations", 0) + 1
    state["critic_iterations"] = iterations

    existing_entities = state["candidate_entities"]
    existing_relations = state["candidate_relations"]
    entity_keys = {_entity_key(e.label) for e in existing_entities}
    relation_keys = {
        _relation_key(r.source_label, r.relationship_type, r.target_label) for r in existing_relations
    }

    # Entities not touched by any relation yet — the critic is told to connect these.
    connected = set()
    for r in existing_relations:
        connected.add(_entity_key(r.source_label))
        connected.add(_entity_key(r.target_label))
    orphan_labels = [e.label for e in existing_entities if _entity_key(e.label) not in connected]

    context = {
        "source_text": state["raw_input"],
        "existing_entities": [{"label": e.label, "type": e.entity_type} for e in existing_entities],
        "existing_relations": [
            {"source": r.source_label, "type": r.relationship_type, "target": r.target_label}
            for r in existing_relations
        ],
        "orphan_entities": orphan_labels,
    }

    llm = create_llm_with_fallbacks("extract_model", cfg)
    logger.info("LLM call: completeness_critic pass %d (entities=%d, relations=%d)",
                iterations, len(existing_entities), len(existing_relations))
    messages = [SystemMessage(content=_PROMPT), HumanMessage(content=json.dumps(context, default=str))]
    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)

    added_entities = 0
    added_relations = 0
    try:
        data = parse_llm_json(content)
        for raw in data.get("candidate_entities", []):
            try:
                entity = CandidateEntity(**raw)
            except TypeError:
                continue
            key = _entity_key(entity.label)
            if not key or key in entity_keys:
                continue
            entity_keys.add(key)
            existing_entities.append(entity)
            added_entities += 1
        for raw in data.get("candidate_relations", []):
            if not raw.get("source_label") or not raw.get("target_label"):
                continue
            try:
                relation = CandidateRelation(**raw)
            except TypeError:
                continue
            key = _relation_key(relation.source_label, relation.relationship_type, relation.target_label)
            if key in relation_keys:
                continue
            relation_keys.add(key)
            existing_relations.append(relation)
            added_relations += 1
    except (json.JSONDecodeError, TypeError) as exc:
        state["errors"].append(
            PipelineError(
                node="completeness_critic",
                error_type="json_parse",
                message=str(exc),
                context={"raw_response": content, "iteration": iterations},
            )
        )

    added = added_entities + added_relations
    state["candidate_entities"] = existing_entities
    state["candidate_relations"] = existing_relations
    # Done when this pass found nothing new, or we've hit the iteration cap.
    state["critic_done"] = added == 0 or iterations >= MAX_CRITIC_ITERATIONS

    state["audit_log"].append(
        AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            node="completeness_critic",
            action="critic_pass",
            output_summary=(
                f"pass {iterations}: +{added_entities} entities, +{added_relations} relations "
                f"(done={state['critic_done']})"
            ),
        )
    )
    return state


def route_after_critic(state: AgentRunState) -> str:
    """Loop back for another critic pass, or proceed to enrichment."""
    return "done" if state.get("critic_done") else "loop"
