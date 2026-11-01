"""C4 duplicate grouping."""
from pipeline.audit.dups import find_duplicates, merge_command, qualifier_year, strip_qualifier
from pipeline.audit.tests.conftest import make_row


def _rows(*rows):
    return {r.id: r for r in rows}


def test_same_qid_group_keeps_the_relation_rich_row():
    rows = _rows(make_row("Augustus", qid="Q1405", start=-63, end=14, id="a", rels=2),
                 make_row("Octavian", qid="Q1405", start=-63, end=14, id="b", rels=40))
    out = find_duplicates(rows)
    assert len(out) == 1
    assert out[0]["category"] == "same_qid" and out[0]["survivor_id"] == "b" and out[0]["loser_id"] == "a"
    assert "merge(c.cursor(), 'b', 'a')" in out[0]["merge_command"]


def test_same_name_overlapping_dates_is_high():
    rows = _rows(make_row("Hannibal", start=-247, end=-183, id="a", qid="Q36456", rels=9),
                 make_row("Hannibal", start=-247, end=-181, id="b"))
    out = find_duplicates(rows)
    assert [(d["category"], d["confidence"], d["survivor_id"]) for d in out] == [("same_name", "high", "a")]


def test_same_name_different_qids_or_eras_is_not_a_duplicate():
    rows = _rows(make_row("Philip II", start=-382, end=-336, id="a", qid="Q35505"),
                 make_row("Philip II", start=1527, end=1598, id="b", qid="Q140222"),
                 make_row("Philip II", start=1165, end=1223, id="c"))
    assert find_duplicates(rows) == []


def test_places_far_apart_are_not_duplicates():
    rows = _rows(make_row("Alexandria", "city", id="a", point=(29.9, 31.2)),
                 make_row("Alexandria", "city", id="b", point=(65.7, 31.6)))
    assert find_duplicates(rows) == []


def test_disambiguator_variant():
    rows = _rows(make_row("Battle of Salamis", "event_battle", qid="Q178850", start=-480, end=-480, id="a"),
                 make_row("Battle of Salamis (306 BCE)", "event_battle", qid="Q1247317", start=-306, end=-306, id="b"),
                 make_row("Battle of Salamis (480 BCE)", "event_battle", start=-480, end=-480, id="c"))
    out = find_duplicates(rows)
    pairs = {(d["category"], d["survivor_id"], d["loser_id"]) for d in out}
    assert pairs == {("disambiguator", "a", "c")}


def test_chained_rows_only_merge_with_compatible_survivor():
    rows = _rows(make_row("Ptolemy", start=-367, end=-282, id="a", rels=5),
                 make_row("Ptolemy", id="b"),
                 make_row("Ptolemy", start=100, end=170, id="c", rels=1))
    out = find_duplicates(rows)
    assert {(d["survivor_id"], d["loser_id"]) for d in out} == {("a", "b")}


def test_qualifier_helpers():
    assert strip_qualifier("Battle of Salamis (306 BCE)") == ("Battle of Salamis", "306 BCE")
    assert strip_qualifier("Salamis") == ("Salamis", None)
    assert qualifier_year("306 BCE") == -306
    assert qualifier_year("1285") == 1285
    assert qualifier_year("city") is None
    assert merge_command("s", "l").startswith("scripts/capped.sh pipeline/.venv/bin/python3 -c")


def test_dates_are_sign_sensitive_and_use_audit_tolerance():
    # Yan (-222) is not Yan (Gongsun Yuan, 237-238); Constantine IV's dates are not Constantine V's
    rows = _rows(make_row("Yan", "political_entity", start=-222, end=-222, id="a", qid="Q3056696"),
                 make_row("Yan (Gongsun Yuan)", "political_entity", start=237, end=238, id="b"),
                 make_row("Constantine V", start=720, end=775, id="c"),
                 make_row("Constantine V", start=652, end=685, id="d"))
    assert find_duplicates(rows) == []


def test_word_qualifier_needs_overlapping_dates_or_same_place():
    rows = _rows(make_row("Rome", "city", qid="Q220", id="a", point=(12.5, 41.9), rels=300),
                 make_row("Rome (New York)", "city", id="b", point=(-75.5, 43.2)),
                 make_row("Honorius", qid="Q159798", start=384, end=423, id="c", rels=9),
                 make_row("Honorius (emperor)", start=384, end=423, id="d"))
    out = find_duplicates(rows)
    assert {(d["survivor_id"], d["loser_id"]) for d in out} == {("c", "d")}
