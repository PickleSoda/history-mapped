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

CRITICAL RULES — entity & relation modeling:
1. EVENTS for conflicts: for every battle, siege, war, campaign, or rebellion named or described, create an EVENT entity (event_battle for a single battle/siege; event_war for a war/campaign; event_rebellion for a revolt) with its proper name (e.g. "Battle of Issus", "Siege of Tyre").
2. Military outcomes point at the EVENT, never at a person or army:
   - winner            -> victorious_at  -> <the battle/war event>
   - loser             -> defeated_at    -> <the battle/war event>
   - any participant   -> participated_in / fought_at -> <the battle/war event>
   NEVER write "X defeated_at Y" / "X victorious_at Y" where Y is a person, polity, or army. If the text says "A defeated B at the Battle of C", emit: A victorious_at "Battle of C" AND B defeated_at "Battle of C".
3. Belligerents: connect the two opposing sides to each other with at_war_with (group <-> group).
4. Direction matters:
   - "A is succeeded by B"  => A succeeded_by B   (B comes AFTER A)
   - "A is preceded by B"   => A preceded_by B    (B comes BEFORE A)
   - "Y killed/assassinated X" => X assassinated_by Y
   - "A commanded/led an army" => A commanded <military_unit>
   - born_in / died_in / founded / capital_of point FROM the person or polity TO the place.
5. Names: use the full canonical historical name; never truncate ("Tyre", not "Ty"). Disambiguate rulers by polity/era when the text allows ("Philip II of Macedon", not just "Philip II").
6. Extract relations among ALL entities mentioned, not only the main subject.
7. Dates: ALWAYS include an explicit era marker — write "323 BCE", "527 CE", "4000 BCE". Never emit a bare number or an ISO calendar string (e.g. "4000-01-01") for ancient years, and never put a minus sign on a CE year. Put the earlier year first so start_date is on or before end_date. Give EVERY entity start/end dates where the text or your knowledge supports it — including peoples, ethnic groups, and dynasties (use their era of historical prominence, e.g. the Goths "200 CE"–"600 CE", the Sumerians "4500 BCE"–"1900 BCE").
8. Extract EVERY named entity in each event — including the "container" polity, not just the people. If the text names an empire/kingdom/state/dynasty (e.g. "New Kingdom of Egypt", "Macedonian Empire", "Byzantine Empire", "Mongol Empire", "Ottoman Empire", "Qing Dynasty"), emit it as its own political_entity/dynasty AND relate the people/events to it. Also extract:
   - technologies / inventions named as significant -> entity_type "technology" (e.g. "ballistae", "gunpowder", "stirrup", "printing press");
   - religions / religious movements -> entity_type "religious_movement" (e.g. "Christianity", "Orthodoxy", "Catholicism", "Islam"), and use schism_from / influenced_by for splits like the East–West Schism.
   - named diseases, plagues, epidemics, and pandemics -> entity_type "epidemic_disease" (e.g. "Black Death", "Plague of Justinian", "Plague of Athens", "Antonine Plague", "smallpox", "Spanish Flu"). Extract the DISEASE itself as its own entity — do NOT model a pandemic only as an event. Connect it to what it struck with "spread_to" (places) and "caused" (consequences).
   A good rule of thumb: every proper noun that denotes a polity, person, place, event, technology, religion, or disease in the sentence should appear as a candidate entity.
9. COALITIONS & ALLIANCES are NOT single places. A multi-state coalition, alliance, or league (e.g. "Allied Powers", "Central Powers", "Axis", "Triple Entente", "Triple Alliance", "Delian League", "Holy League", "Eight-Nation Alliance", "League of Corinth") must be typed entity_type "diplomatic_relationship" — NEVER "political_entity" — and must not be given a territory. Instead, link each member state to it: "<member state> part_of <coalition>" (one relation per member you can identify), and connect opposing sides with "<side A> at_war_with <side B>". A sovereign state that happens to be a federation/union (e.g. "Soviet Union") is a political_entity, not a coalition.

Worked example — input "In 333 BCE Alexander defeated Darius III at the Battle of Issus, then besieged Tyre.":
{"candidate_entities": [
  {"label": "Alexander the Great", "entity_type": "person"},
  {"label": "Darius III", "entity_type": "person"},
  {"label": "Battle of Issus", "entity_type": "event_battle", "start_date": "333 BCE"},
  {"label": "Siege of Tyre", "entity_type": "event_battle", "start_date": "332 BCE"},
  {"label": "Tyre", "entity_type": "city"}],
 "candidate_relations": [
  {"source_label": "Alexander the Great", "target_label": "Battle of Issus", "relationship_type": "victorious_at", "start_date": "333 BCE"},
  {"source_label": "Darius III", "target_label": "Battle of Issus", "relationship_type": "defeated_at", "start_date": "333 BCE"},
  {"source_label": "Alexander the Great", "target_label": "Siege of Tyre", "relationship_type": "victorious_at", "start_date": "332 BCE"}]}

Output strictly as JSON:
{"candidate_entities": [{"label": "...", "entity_type": "...", "start_date": "...", "end_date": "...", "source_event": "...", "aliases": []}], "candidate_relations": [{"source_label": "...", "target_label": "...", "relationship_type": "...", "start_date": "...", "end_date": "...", "source_event": "..."}]}
"""


def extract_candidates(state: AgentRunState) -> AgentRunState:
    cfg = AgentConfig()
    llm = create_llm_with_fallbacks("extract_model", cfg)
    events_json = json.dumps([e.model_dump() for e in state["parsed_events"]], default=str)
    logger.info("LLM call: extract_candidates (model=%s, events=%d)", cfg.extract_model, len(state["parsed_events"]))
    messages = [SystemMessage(content=_PROMPT), HumanMessage(content=events_json)]
    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)
    logger.info("LLM response: %d chars", len(content))
    try:
        data = parse_llm_json(content)
        entities = [CandidateEntity(**e) for e in data.get("candidate_entities", [])]
        raw_relations = data.get("candidate_relations", [])
        relations = []
        for r in raw_relations:
            if not r.get("source_label") or not r.get("target_label"):
                logger.warning("Skipping relation with null source/target: %s", r)
                continue
            relations.append(CandidateRelation(**r))
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
