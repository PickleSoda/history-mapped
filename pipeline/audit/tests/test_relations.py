"""C7 relationship endpoint rules."""
from pipeline.audit.relations import endpoint_problem, era_problem, relation_flags
from pipeline.audit.tests.conftest import make_row


def test_impossible_endpoints():
    assert endpoint_problem("commanded", "city", "event_battle")  # a non-person commanding a battle
    assert endpoint_problem("participated_in", "event_battle", "person")  # a battle participating in a person
    assert endpoint_problem("born_in", "person", "event_war")
    assert endpoint_problem("commanded", "person", "event_battle") is None
    assert endpoint_problem("participated_in", "political_entity", "event_war") is None
    assert endpoint_problem("influenced_by", "person", "city") is None  # no rule: never flagged


def test_era_gap_uses_the_larger_tolerance():
    hannibal = make_row("Hannibal", start=-247, end=-183)
    cannae = make_row("Battle of Cannae", "event_battle", start=-216, end=-216)
    waterloo = make_row("Battle of Waterloo", "event_battle", start=1815, end=1815)
    assert era_problem("commanded", hannibal, cannae) is None
    assert era_problem("commanded", hannibal, waterloo)[0] > 1000
    assert era_problem("influenced_by", hannibal, waterloo) is None  # not contemporaneous


def test_relation_flags_output():
    rows = {r.id: r for r in (make_row("Rome", "city", id="r"), make_row("Cannae", "event_battle", id="c"))}
    flags = relation_flags(rows, [{"id": "x", "source": "r", "target": "c", "type": "commanded",
                                   "start": None, "end": None, "description": ""}])
    assert [f["check"] for f in flags] == ["endpoint_type"]


def test_membership_in_a_league_is_not_impossible_but_in_a_person_is():
    assert endpoint_problem("participated_in", "city", "diplomatic_relationship") is None
    assert endpoint_problem("participated_in", "political_entity", "political_entity") is None
    assert endpoint_problem("signed_by", "political_entity", "event_treaty")  # stored backwards


def test_open_ended_polity_is_not_an_era_problem():
    england = make_row("England", "political_entity", start=927)
    lanfranc = make_row("Lanfranc", start=1005, end=1089)
    assert era_problem("resided_in", lanfranc, england) is None
