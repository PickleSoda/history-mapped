from __future__ import annotations

import json
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from pipeline.agent.config import AgentConfig
from pipeline.agent.llm import create_llm_with_fallbacks
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.entities import CandidateEntity
from pipeline.agent.schemas.relations import CandidateRelation
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

Every entity was pulled from this chronicle, so each one IS connected to the story — be generous and thorough in
wiring them together. Each `existing_entities` item carries a `source_event`: entities sharing a source_event
almost always relate to each other and to that event, so connect them. Also connect each entity to its container
polity and to its temporal neighbours (succeeded_by / preceded_by).

PRIORITY — orphans: the `orphan_entities` list below contains entities with NO relationships yet. Give EACH of
them at least TWO relationships that the source text or well-established history supports — first to entities from
its own `source_event`, then to its container polity, the central figure/event of the chronicle, or a temporal
neighbour (e.g. a person `participated_in` the event they appear in and `member_of_dynasty`/`born_in` something;
a belligerent polity is `at_war_with` its opponent and `participated_in` the war). No entity should be left
unconnected.

PRECISION: only add relationships actually supported by the text or well-established history — do not pad. Respect
relation-type semantics: `member_of_dynasty` connects a PERSON to a named ruling DYNASTY only — never to a
republic, empire, or state (use `part_of` / `governed_by` for those).

REFERENTIAL INTEGRITY (critical): every source_label and target_label you use in a relation MUST be a real
entity. If you connect something to an entity that is NOT in existing_entities and NOT one you are adding, then
ALSO add that thing to candidate_entities with its correct type (e.g. when you write "Leonardo da Vinci authored
Mona Lisa", add "Mona Lisa" as a cultural_work). A relation whose endpoint is not an entity is useless — it is
dropped. So pair every new relation with the entities it needs.

Use the same entity_type and relationship_type vocabulary as the existing items. Output ONLY new items not
already in the provided lists. If nothing is missing, return empty lists.

Output strictly as JSON:
{"candidate_entities": [{"label": "...", "entity_type": "...", "start_date": "...", "end_date": "...", "aliases": []}],
 "candidate_relations": [{"source_label": "...", "target_label": "...", "relationship_type": "...", "start_date": "...", "end_date": "..."}]}
"""


# Type to give an auto-created missing relation endpoint, inferred from the
# relationship's semantics. (source_type, target_type); None on a side means that
# side carries no reliable type signal. When the relevant side is None — or the
# relationship is absent from this map — a dangling relation is dropped rather than
# create a mistyped entity. This connects the common orphan-makers (a person's
# authored work / commanded unit / dynasty / battle) with the right type, while
# refusing to guess on the genuinely ambiguous ones.
_REL_ENDPOINT_TYPES: dict[str, tuple[str | None, str | None]] = {
    "authored": (None, "cultural_work"),
    "commissioned": (None, "cultural_work"),
    "translated_into": ("religious_text", None),
    "invented": (None, "technology"),
    "adopted": (None, "technology"),
    "built_by": ("infrastructure_monument", None),
    "destroyed_by": ("infrastructure_monument", None),
    "commanded": (None, "military_unit"),
    "member_of_dynasty": (None, "dynasty"),
    "adheres_to": (None, "religious_movement"),
    "official_religion_of": ("religious_movement", "political_entity"),
    "capital_of": ("city", "political_entity"),
    "at_war_with": ("political_entity", "political_entity"),
    "allied_with": ("political_entity", "political_entity"),
    "part_of": (None, "political_entity"),
    "contains": ("political_entity", "political_entity"),
    "succeeded_by": ("political_entity", "political_entity"),
    "preceded_by": ("political_entity", "political_entity"),
    "vassal_of": ("political_entity", "political_entity"),
    "suzerain_of": ("political_entity", "political_entity"),
    "spread_to": (None, "political_entity"),
    "participated_in": (None, "event_war"),
    "victorious_at": (None, "event_battle"),
    "defeated_at": (None, "event_battle"),
    "fought_at": (None, "event_battle"),
}


def _ensure_relation_endpoints(entities, relations) -> tuple[int, int]:
    """Guarantee every relation endpoint is a candidate entity.

    The LLM routinely emits a relation to a thing it never extracted (e.g.
    "Leonardo da Vinci authored Mona Lisa" without a Mona Lisa entity); validate
    then drops the relation, leaving the person an orphan. For each missing
    endpoint we create a minimal entity whose type is inferred from the
    relationship (it still gets Wikidata-enriched + summarised downstream). When
    the type can't be safely inferred we drop the relation instead of inventing a
    mistyped entity. Returns (entities_added, relations_dropped). Mutates the lists.
    """
    have = {_entity_key(e.label) for e in entities}
    added = 0
    kept = []
    dropped = 0
    for rel in relations:
        src_type, tgt_type = _REL_ENDPOINT_TYPES.get(rel.relationship_type, (None, None))
        ok = True
        for label, inferred in ((rel.source_label, src_type), (rel.target_label, tgt_type)):
            if _entity_key(label) in have:
                continue
            if not inferred:
                ok = False  # missing endpoint we can't type — drop the relation
                break
            entities.append(CandidateEntity(label=label, entity_type=inferred))
            have.add(_entity_key(label))
            added += 1
        if ok:
            kept.append(rel)
        else:
            dropped += 1
    relations[:] = kept
    return added, dropped


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
        "existing_entities": [
            {"label": e.label, "type": e.entity_type, "source_event": e.source_event,
             "start_date": e.start_date}
            for e in existing_entities
        ],
        "existing_relations": [
            {"source": r.source_label, "type": r.relationship_type, "target": r.target_label}
            for r in existing_relations
        ],
        "orphan_entities": orphan_labels,
    }

    llm = create_llm_with_fallbacks("extract_model", cfg, reasoning_effort=cfg.reasoning_effort)
    logger.info("LLM call: completeness_critic pass %d (entities=%d, relations=%d)",
                iterations, len(existing_entities), len(existing_relations))
    messages = [SystemMessage(content=_PROMPT), HumanMessage(content=json.dumps(context, default=str))]

    added_entities = 0
    added_relations = 0
    # No validate predicate: a critic response with no additions is legitimate
    # ("nothing more to add" → done). invoke_json still retries/falls back on a
    # malformed or empty body (the free-model failure mode), instead of dropping
    # the whole pass on the first bad parse.
    try:
        data = llm.invoke_json(messages)
        for raw in data.get("candidate_entities", []):
            try:
                entity = CandidateEntity(**raw)
            except (TypeError, ValidationError):
                continue  # one malformed entity (e.g. missing entity_type) skips, not aborts
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
            except (TypeError, ValidationError):
                continue
            key = _relation_key(relation.source_label, relation.relationship_type, relation.target_label)
            if key in relation_keys:
                continue
            relation_keys.add(key)
            existing_relations.append(relation)
            added_relations += 1
    except Exception as exc:
        state["errors"].append(
            PipelineError(
                node="completeness_critic",
                error_type="json_parse",
                message=str(exc),
                context={"iteration": iterations},
            )
        )

    added = added_entities + added_relations
    # Done when this pass found nothing new, or we've hit the iteration cap.
    state["critic_done"] = added == 0 or iterations >= MAX_CRITIC_ITERATIONS

    # Final cleanup once the LLM passes are exhausted: materialise any relation
    # endpoint the model referenced but never extracted (so the relation survives
    # validate and connects its entity instead of orphaning it), and drop the
    # un-typeable danglers.
    backstop_entities = backstop_dropped = 0
    if state["critic_done"]:
        backstop_entities, backstop_dropped = _ensure_relation_endpoints(
            existing_entities, existing_relations
        )

    state["candidate_entities"] = existing_entities
    state["candidate_relations"] = existing_relations

    state["audit_log"].append(
        AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            node="completeness_critic",
            action="critic_pass",
            output_summary=(
                f"pass {iterations}: +{added_entities} entities, +{added_relations} relations "
                f"(done={state['critic_done']}); backstop +{backstop_entities} endpoints, "
                f"-{backstop_dropped} dangling relations"
            ),
        )
    )
    return state


def route_after_critic(state: AgentRunState) -> str:
    """Loop back for another critic pass, or proceed to enrichment."""
    return "done" if state.get("critic_done") else "loop"
