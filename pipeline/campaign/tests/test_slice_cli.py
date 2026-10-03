"""Fact-slice extraction tooling: event `fact` tags, handoff slice / rm-slice /
check --facts, and transcript-check."""
import json

import pytest

from pipeline.agent.handoff import load_handoff
from pipeline.agent.validate_handoff import validate
from pipeline.campaign import handoff_ops as ops
from pipeline.campaign.tests.conftest import (
    ENTITIES, EVENTS, RELATIONS, RUN_ID, SLUG, SUMMARIES, read,
)
from pipeline.campaign.transcript import check_text, first_year

TAGGED = [dict(e, fact=i + 1) for i, e in enumerate(EVENTS)]


def _add(invoke, part, payload, *extra):
    return invoke("handoff", "add", SLUG, part, "-", *extra, input=json.dumps(payload))


@pytest.fixture
def tagged(invoke, root):
    """The conftest handoff, with every event tagged by its transcript fact number."""
    assert invoke("handoff", "init", SLUG, "--title", "Golden Age").exit_code == 0
    for part, payload in (("events", TAGGED), ("entities", ENTITIES), ("relations", RELATIONS),
                          ("summaries", SUMMARIES)):
        res = _add(invoke, part, payload)
        assert res.exit_code == 0, res.output
    return root / "output" / "campaign" / "extractions" / RUN_ID / "candidates.json"


# ── fact field ──────────────────────────────────────────────────────────────

def test_event_fact_is_stored_and_ignored_by_the_pipeline_loader(tagged):
    raw = read(tagged)
    assert [e["fact"] for e in raw["parsed_events"]] == [1, 2, 3]
    doc = load_handoff(tagged)  # ParsedEvent ignores the campaign-only key
    assert not hasattr(doc.parsed_events[0], "fact")
    assert validate(str(tagged)) == []


def test_event_fact_coerces_digit_strings_and_rejects_junk(invoke, tagged):
    res = _add(invoke, "events", [{"label": "Reign of Tamar", "fact": "3"},
                                  {"label": "Bad zero", "start_date": "1100", "fact": 0},
                                  {"label": "Bad bool", "start_date": "1100", "fact": True},
                                  {"label": "Bad text", "start_date": "1100", "fact": "x"}])
    assert res.exit_code == 1
    assert res.output.count("must be the transcript fact number") == 3
    assert read(tagged)["parsed_events"][2]["fact"] == 3


def test_event_fact_survives_merge_and_null_clears_it(invoke, tagged):
    assert _add(invoke, "events", [{"label": "Battle of Didgori", "description": "New."}]).exit_code == 0
    assert read(tagged)["parsed_events"][1]["fact"] == 2
    assert _add(invoke, "events", [{"label": "Battle of Didgori", "fact": None}]).exit_code == 0
    assert "fact" not in read(tagged)["parsed_events"][1]


def test_show_prefixes_events_with_fact(invoke, tagged):
    out = invoke("handoff", "show", SLUG, "--part", "events").output.splitlines()
    assert out[1] == "#2 1121.. Battle of Didgori"


# ── parse / format ──────────────────────────────────────────────────────────

def test_parse_and_format_fact_ranges():
    assert ops.parse_facts("21-23") == [21, 22, 23]
    assert ops.parse_facts("5, 7-9,8") == [5, 7, 8, 9]
    assert ops.fmt_facts([1, 2, 3, 7, 9, 10]) == "1-3,7,9-10"
    for bad in ("", "0-3", "5-2", "a-b", "1-"):
        with pytest.raises(ops.OpError):
            ops.parse_facts(bad)


# ── slice ───────────────────────────────────────────────────────────────────

def test_slice_prints_facts_tagged_events_and_labels(invoke, tagged):
    res = invoke("handoff", "slice", SLUG, "--facts", "2-3")
    assert res.exit_code == 0, res.output
    lines = res.output.splitlines()
    assert lines[0].startswith("# facts 2-3 of 3 (output/transcripts/campaign/")
    assert lines[1] == "2. David IV defeats the Seljuks at the Battle of Didgori in 1121 CE."
    assert lines[2] == "3) Tamar of Georgia rules the kingdom from 1184 to 1213 CE."
    assert "1. David IV becomes king" not in res.output
    assert "#2 1121.. Battle of Didgori" in lines and "#3 1184..1213 Reign of Tamar" in lines
    assert "person: David IV of Georgia; Tamar of Georgia" in lines
    assert "event_battle: Battle of Didgori" in lines


def test_slice_before_init_and_out_of_range(invoke, root):
    res = invoke("handoff", "slice", SLUG, "--facts", "3-5")
    assert res.exit_code == 0
    assert "(not in transcript: 4-5)" in res.output
    assert "no handoff yet" in res.output


def test_slice_errors(invoke, root):
    assert invoke("handoff", "slice", SLUG, "--facts", "x").exit_code == 1
    assert invoke("handoff", "slice", "e08__nowhere__x", "--facts", "1").exit_code == 1


# ── rm-slice ────────────────────────────────────────────────────────────────

def test_rm_slice_removes_events_relations_and_unshared_entities(invoke, tagged):
    res = invoke("handoff", "rm-slice", SLUG, "--facts", "2")
    assert res.exit_code == 0, res.output
    assert "removed events=1 relations=4 entities=2 summaries=2" in res.output
    doc = read(tagged)
    assert [e["label"] for e in doc["parsed_events"]] == ["Accession of David IV", "Reign of Tamar"]
    labels = {e["label"] for e in doc["candidate_entities"]}
    assert labels == {"David IV of Georgia", "Kingdom of Georgia", "Tamar of Georgia"}
    assert set(doc["summaries"]) == labels
    assert all(r["source_event"] != "Battle of Didgori" for r in doc["candidate_relations"])
    assert invoke("handoff", "check", SLUG).exit_code == 0


def test_rm_slice_keeps_entities_other_facts_use(invoke, tagged):
    _add(invoke, "events", [{"label": "Reign of Tamar",
                             "mentioned_entities": ["Tamar of Georgia", "Seljuk Empire"]}])
    res = invoke("handoff", "rm-slice", SLUG, "--facts", "2")
    assert "kept 1 entities still used by other facts" in res.output
    ent = {e["label"]: e for e in read(tagged)["candidate_entities"]}
    assert ent["Seljuk Empire"]["source_event"] == "Reign of Tamar"
    assert "Battle of Didgori" not in ent


def test_rm_slice_then_reextract_does_not_duplicate(invoke, tagged):
    before = read(tagged)
    invoke("handoff", "rm-slice", SLUG, "--facts", "2")
    for part, payload in (("events", [TAGGED[1]]),
                          ("entities", [e for e in ENTITIES if e["source_event"] == "Battle of Didgori"]),
                          ("relations", [r for r in RELATIONS if r["source_event"] == "Battle of Didgori"]),
                          ("summaries", {k: SUMMARIES[k] for k in ("Seljuk Empire", "Battle of Didgori")})):
        assert _add(invoke, part, payload).exit_code == 0
    after = read(tagged)
    assert ops.counts(after) == ops.counts(before)
    assert invoke("handoff", "check", SLUG).exit_code == 0


def test_rm_slice_on_untagged_events_is_a_noop(invoke, built):
    res = invoke("handoff", "rm-slice", SLUG, "--facts", "1-3")
    assert res.exit_code == 0
    assert "nothing removed (3 events have no fact number)" in res.output


# ── check --facts and fact warnings ─────────────────────────────────────────

def test_check_facts_scopes_to_the_slice(invoke, tagged):
    _add(invoke, "entities", [{"label": "Unrelated", "entity_type": "person", "source_event": "Reign of Tamar"}])
    res = invoke("handoff", "check", SLUG, "--facts", "2")
    assert res.exit_code == 0, res.output
    assert "slice=2 facts=1 events=1 new_entities=2 relations=4 rel/fact=4.0 rel/new_ent=2.0" in res.output
    assert "Unrelated" not in res.output
    assert "(1 error(s) outside this slice not shown" in res.output
    res = invoke("handoff", "check", SLUG, "--facts", "3")
    assert res.exit_code == 1
    assert "summary-missing: entity 'Unrelated'" in res.output
    assert "orphan: entity 'Unrelated' [person] has no relations (fact 3)" in res.output


def test_check_facts_slice_density_and_uncovered(invoke, tagged):
    invoke("handoff", "rm", SLUG, "relations", "Tamar of Georgia|resided_in|Kingdom of Georgia")
    res = invoke("handoff", "check", SLUG, "--facts", "3")
    assert "slice-density: relations/fact 1.00 < 2.0" in res.output
    assert "slice-density: relations/new entity 1.00 < 1.5" in res.output
    invoke("handoff", "rm", SLUG, "events", "Accession of David IV")
    res = invoke("handoff", "check", SLUG, "--facts", "1-3")
    assert "fact-uncovered: facts with no event: 1" in res.output


def test_check_global_fact_and_mention_warnings(invoke, tagged):
    _add(invoke, "events", [{"label": "Stray", "start_date": "1100", "mentioned_entities": ["Ghost"]},
                            {"label": "Beyond", "start_date": "1100", "fact": 9}])
    res = invoke("handoff", "check", SLUG)
    assert res.exit_code == 0, res.output
    assert "fact-missing: 1 event(s) have no fact number: 'Stray'" in res.output
    assert "fact-range: event 'Beyond': fact 9 is not a numbered transcript fact" in res.output
    assert "mention-missing: event 'Stray' mentions 'Ghost'" in res.output


# ── transcript-check ────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,year", [
    ("In 490 BCE Miltiades wins.", -490),
    ("Between c. 8500 and 7900 BCE villagers settle.", -8500),
    ("Around c. 11,050 BCE foragers cultivate rye.", -11050),
    ("The war (1756–1763 CE) ends on 10 February 1763.", 1756),
    ("On 14 July 1789 CE crowds storm the Bastille.", 1789),
    ("During the 6th millennium BCE the Samarra culture spreads.", -6000),
    ("In the 12th century CE, after 1150 CE, the order grows.", 1100),
    ("A generic statement about trade with 7,000 men.", None),
])
def test_first_year(text, year):
    assert first_year(text) == year


def test_check_text_rules():
    text = "T\n\n1. In 700 BCE A.\n2. In 780 BCE B.\n2. Undated filler about society.\n4. In 900 BCE C.\n"
    rep = check_text(text, "e04")
    codes = [c for c, _ in rep.errors]
    assert codes.count("undated") == 1 and "numbering" in codes
    warns = [f"{c}: {m}" for c, m in rep.warnings]

    def has(fragment):
        return any(fragment in w for w in warns)

    assert has("numbering: missing fact numbers: 3")
    assert has("era-edge: fact 2: first year 780 BCE is outside the e04 span")
    assert has("out-of-era: fact 4: first year 900 BCE is outside e04")
    assert has("order: fact 2 (780 BCE) starts before fact 1 (700 BCE)")
    assert not has("fact 1:")
    assert rep.facts == 4 and rep.dated == 3


def test_transcript_check_cli(invoke, root):
    res = invoke("transcript-check", SLUG)
    assert res.exit_code == 0, res.output
    assert "facts=3 dated=3 era=e08" in res.output
    assert "count: 3 facts < floor 60" in res.output
    path = root / "output/transcripts/campaign" / f"{SLUG}.txt"
    path.write_text(path.read_text(encoding="utf-8") + "4. Society changes a lot.\n", encoding="utf-8")
    res = invoke("transcript-check", SLUG)
    assert res.exit_code == 1 and "undated: fact 4" in res.output
    assert invoke("transcript-check", "e08__nowhere__x").exit_code == 1
