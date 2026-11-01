"""C2b: the entity_type → Wikidata class table."""
import re

import pytest

from pipeline.audit import classes as C
from pipeline.audit.tests.conftest import CLOSURE, rec

SPEC_TYPES = """political_entity dynasty person military_unit diplomatic_relationship social_class city
infrastructure_monument extraction_infra educational_institution event_war event_battle event_treaty
event_rebellion event_natural_disaster event_tech_adoption event_legal_reform migration epidemic_disease
trade_route natural_resource currency_monetary_system cultural_work intellectual_movement archaeological_culture
language religious_text legal_code religious_movement technology""".split()


def test_every_spec_type_has_a_rule():
    assert len(SPEC_TYPES) == 30
    assert set(C.TYPE_RULES) == set(SPEC_TYPES)


def test_rules_are_well_formed():
    for etype, (allowed, contradict) in C.TYPE_RULES.items():
        for q in (allowed or set()) | contradict:
            assert re.fullmatch(r"Q\d+", q), (etype, q)
            assert q in C.ALL_ROOTS, (etype, q)
        if allowed is not None:
            assert not allowed & contradict, etype


@pytest.mark.parametrize("etype,p31,expected", [
    ("person", ["Q5"], "ok"),
    ("person", ["Q11446"], "contradiction"),         # a ship named like the person
    ("person", ["Q99999"], "contradiction"),         # a person must be human (or person-like)
    ("person", [], "unknown"),
    ("event_battle", ["Q178561"], "ok"),
    ("event_battle", ["Q1261499"], "ok"),            # naval battle is a subclass of battle
    ("event_battle", ["Q515"], "contradiction"),     # a city on a battle row
    ("event_battle", ["Q99999"], "unmatched"),
    ("political_entity", ["Q3024240"], "ok"),
    ("political_entity", ["Q773711"], "ok"),         # symmachia (alliance) for a league
    ("political_entity", ["Q5"], "contradiction"),
    ("military_unit", ["Q176799"], "ok"),
    ("natural_resource", ["Q16521"], "ok"),          # a taxon is fine for a resource
    ("natural_resource", ["Q5"], "contradiction"),
    ("city", ["Q4167410"], "contradiction"),         # disambiguation page
    ("city", ["Q101352"], "contradiction"),          # family name
])
def test_classify(etype, p31, expected):
    assert C.classify(etype, p31, CLOSURE) == expected


def test_generic_class_only_for_individual_types():
    concept = rec("imperial guard", p31=["Q176799"], p279=["Q176799"])
    assert C.is_generic_class("person", rec("pharaoh", p31=["Q99999"], p279=["Q99999"]))
    assert C.is_generic_class("military_unit", concept)
    assert not C.is_generic_class("technology", rec("paper", p31=["Q99999"], p279=["Q99999"]))
    assert not C.is_generic_class("military_unit", rec("Imperial Guard", p31=["Q176799"]))


def test_kind_label():
    assert C.kind_label(C.kinds_of(["Q1261499"], CLOSURE)) == "battle"
    assert C.kind_label(set()) == "-"


def test_village_is_not_a_polity():
    closure = {"Q532": {"Q486972", "Q56061", "Q1048835"}, "Q3624078": {"Q3624078", "Q7275"}}
    assert C.classify("political_entity", ["Q532"], closure) == "contradiction"  # Normandy, Surrey
    assert C.contradiction_strength("political_entity", ["Q532"], closure) == "soft"
    assert C.classify("political_entity", ["Q3624078"], closure) == "ok"  # Duchy of Normandy


def test_a_deity_is_not_fiction():
    closure = {"Q22989102": {"Q178885", "Q14897293"}, "Q215380": {"Q215380", "Q43229"}}
    assert C.FICTION.isdisjoint(C.kinds_of(["Q22989102"], closure))
    assert C.contradiction_strength("religious_movement", ["Q22989102"], closure) is None
    assert C.never_historical("religious_movement", ["Q215380"], closure)  # a band
    assert not C.never_historical("cultural_work", ["Q215380"], closure)


def test_weak_polity_root_alone_does_not_contradict():
    closure = {"Q5275": {"Q15642541", "Q16686448", "Q386724"}}  # Antikythera mechanism's 'national treasure'
    assert C.classify("technology", ["Q5275"], closure) == "ok"


def test_an_admin_district_is_not_a_city_candidate():
    closure = {"Q122987736": {"Q1048835", "Q15642541", "Q82794"}, "Q486972": {"Q486972"}}
    assert C.admin_area_for_city("city", ["Q122987736"], closure)       # Kumbakonam Taluk
    assert not C.admin_area_for_city("city", ["Q486972"], closure)      # a human settlement
    assert not C.admin_area_for_city("political_entity", ["Q122987736"], closure)
