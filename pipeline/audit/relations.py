"""C7: relationship sanity (report only).

* endpoint_type — a relationship type whose source or target can never be of
  that entity type (rules below, read from docs/entity-model/relationships.md:
  the 'typical source/target' columns, widened to everything plausible so only
  impossible pairs remain);
* endpoint_era  — a contemporaneous relationship (``CONTEMPORANEOUS_RELATION_TYPES``:
  rules, commanded, born_in, …) whose dated endpoints are further apart than
  the C2 tolerance (the larger of the two endpoints').
"""
from __future__ import annotations

from typing import Any

from pipeline.agent.tools.disambiguation import CONTEMPORANEOUS_RELATION_TYPES
from pipeline.audit.dates import DATED_TYPES, row_range, tolerance

PERSON = {"person"}
POLITY_GROUP = {"political_entity", "dynasty", "person", "military_unit", "diplomatic_relationship", "social_class"}
EVENTS = {"event_war", "event_battle", "event_treaty", "event_rebellion", "event_natural_disaster",
          "event_tech_adoption", "event_legal_reform", "migration", "epidemic_disease"}
PLACES = {"city", "infrastructure_monument", "extraction_infra", "educational_institution"}
TERRITORY = PLACES | {"political_entity", "archaeological_culture", "trade_route"}
ACTORS = POLITY_GROUP | {"religious_movement", "archaeological_culture", "city"}
TEXTS = {"cultural_work", "religious_text", "legal_code", "event_treaty", "event_legal_reform",
         "intellectual_movement", "technology", "language"}
AGREEMENTS = {"event_treaty", "legal_code", "diplomatic_relationship", "event_legal_reform"}

# relationship_type -> (allowed source types | None, allowed target types | None)
ENDPOINT_RULES: dict[str, tuple[set[str] | None, set[str] | None]] = {
    "born_in": (PERSON, TERRITORY),
    "died_in": (PERSON, TERRITORY | EVENTS),
    "married_to": (PERSON, PERSON),
    "parent_of": (PERSON, PERSON | {"dynasty"}),
    "child_of": (PERSON | {"dynasty"}, PERSON),
    "sibling_of": (PERSON, PERSON),
    "mentor_of": (PERSON | {"religious_movement", "intellectual_movement", "educational_institution"}, PERSON),
    "student_of": (PERSON, PERSON | {"religious_movement", "intellectual_movement", "educational_institution"}),
    "member_of_dynasty": (PERSON, {"dynasty", "political_entity", "social_class"}),
    "commanded": (PERSON, EVENTS | {"military_unit", "political_entity", "city", "infrastructure_monument"}),
    "commanded_by": (ACTORS | EVENTS, PERSON),
    # target: an event, or a body one takes part in (league, alliance, movement)
    "participated_in": (ACTORS | EVENTS | {"infrastructure_monument", "technology", "intellectual_movement"},
                        EVENTS | {"political_entity", "diplomatic_relationship", "military_unit", "religious_movement",
                                  "intellectual_movement", "social_class", "archaeological_culture", "legal_code"}),
    "fought_at": (ACTORS | EVENTS, EVENTS | TERRITORY),
    "defeated_at": (ACTORS, EVENTS | TERRITORY),
    "victorious_at": (ACTORS, EVENTS | TERRITORY),
    "capital_of": ({"city", "political_entity", "infrastructure_monument", "archaeological_culture"},
                   {"political_entity", "dynasty", "archaeological_culture", "city", "religious_movement"}),
    "rules": (ACTORS, TERRITORY | {"social_class", "religious_movement", "military_unit", "dynasty"}),
    "governed_by": (TERRITORY | {"social_class", "religious_movement", "military_unit", "dynasty"}, ACTORS),
    "authored": (ACTORS | {"educational_institution"}, TEXTS | EVENTS),
    "assassinated_by": (PERSON, ACTORS),
    "signed_by": (AGREEMENTS | EVENTS, ACTORS),
    "violated_by": (AGREEMENTS | EVENTS, ACTORS),
    "guaranteed_by": (AGREEMENTS | EVENTS, ACTORS),
    "mediated_by": (AGREEMENTS | EVENTS, ACTORS),
    "enforced_by": (AGREEMENTS | EVENTS, ACTORS | {"educational_institution"}),
    "at_war_with": (ACTORS, ACTORS),
    "allied_with": (ACTORS, ACTORS),
    "vassal_of": (ACTORS, ACTORS),
    "suzerain_of": (ACTORS, ACTORS),
    "located_at": (None, TERRITORY),
    "stationed_at": ({"military_unit", "person", "political_entity"}, TERRITORY),
    "minted_by": ({"currency_monetary_system", "technology", "natural_resource", "cultural_work"}, None),
}


def endpoint_problem(rtype: str, src_type: str, tgt_type: str) -> str | None:
    rule = ENDPOINT_RULES.get(rtype)
    if not rule:
        return None
    allowed_src, allowed_tgt = rule
    bad = []
    if allowed_src is not None and src_type not in allowed_src:
        bad.append(f"source {src_type}")
    if allowed_tgt is not None and tgt_type not in allowed_tgt:
        bad.append(f"target {tgt_type}")
    return f"{rtype}: " + " and ".join(bad) + " impossible" if bad else None


def era_problem(rtype: str, src, tgt) -> tuple[int, int] | None:
    """(gap, tolerance) when a contemporaneous relation's endpoints are too far apart."""
    if rtype not in CONTEMPORANEOUS_RELATION_TYPES:
        return None
    a, b = row_range(src.type, src.start, src.end), row_range(tgt.type, tgt.start, tgt.end)
    if src.type not in DATED_TYPES or tgt.type not in DATED_TYPES or not a or not b:
        return None
    gap = max(0, max(a[0], b[0]) - min(a[1], b[1]))  # sign-sensitive: -149 is not 698
    tol = max(tolerance(src.type) or 0, tolerance(tgt.type) or 0)
    if gap is not None and gap > tol:
        return gap, tol
    return None


def relation_flags(rows: dict[str, Any], rels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for rel in rels:
        src, tgt = rows.get(rel["source"]), rows.get(rel["target"])
        if not src or not tgt:
            continue
        base = {"relationship_id": rel["id"], "relationship_type": rel["type"],
                "source_id": src.id, "source_name": src.name, "source_type": src.type, "source_span": src.span,
                "target_id": tgt.id, "target_name": tgt.name, "target_type": tgt.type, "target_span": tgt.span,
                "description": rel["description"][:160]}
        problem = endpoint_problem(rel["type"], src.type, tgt.type)
        if problem:
            out.append({**base, "check": "endpoint_type", "detail": problem, "severity": "high"})
        era = era_problem(rel["type"], src, tgt)
        if era:
            gap, tol = era
            out.append({**base, "check": "endpoint_era", "detail": f"endpoints {gap}y apart (tolerance {tol}y)",
                        "severity": "high" if gap > 100 else "medium" if gap > 25 else "low"})
    return out
