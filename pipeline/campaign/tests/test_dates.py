"""Padded -01-01 dates: detection (pipeline.campaign.dates), the handoff add/check/
fix-dates path, and the measure's classification of DB rows."""
import csv
import json
import subprocess

import pytest

from pipeline.campaign import measure
from pipeline.campaign.dates import depad, jan1_years, states_jan1

from .conftest import ENTITIES, EVENTS, RELATIONS, RUN_ID, SLUG, SUMMARIES, read


# ── depad ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("date, fact, expected", [
    ("1873-01-01", "48. In 1873 CE the Meiji government begins the Land Tax Reform.", "1873"),
    ("1873-01-01", "47. In January 1873 CE the Meiji government issues the Conscription Ordinance.", "1873-01"),
    ("1921-01-01", "63. In 1921 CE Turkish forces win the First Battle of İnönü (January).", "1921-01"),
    ("1873-01-01", "On 11 January 1873 something happens.", "1873-01"),
    ("1873-01-01", "On January 10, 1873 something happens.", "1873-01"),
    ("1801-01-01", "6. In 1800 CE ... and on 1 January 1801 CE the United Kingdom comes into being.", None),
    ("1800-01-01", "6. In 1800 CE ... and on 1 January 1801 CE the United Kingdom comes into being.", "1800"),
    ("1863-01-01", "On January 1, 1863 Lincoln issues the Emancipation Proclamation.", None),
    ("1886-01-01", "57. In 1886 CE Britain annexes Upper Burma on 1 January.", None),
    ("-45-01-01", "On 1 January 45 BCE the Julian calendar takes effect.", None),
    ("1801-01-01", "New Year's Day 1801 brings the Union into force.", None),
    ("1755-01-01", None, "1755"),
    ("-0490-01-01", "In 490 BCE ...", "-490"),
    ("1854-03", "In March 1854 ...", None),
    ("1854-03-31", "On 31 March 1854 ...", None),
    ("1066", "In 1066 CE ...", None),
    (None, "x", None),
])
def test_depad(date, fact, expected):
    assert depad(date, fact) == expected


def test_depad_accepts_jan1_stated_by_another_fact_of_the_transcript():
    facts = ["1. In August 1791 CE the Haitian Revolution begins.",
             "8. On 1 January 1804 CE Dessalines declares the independence of Haiti."]
    years = jan1_years(facts)
    assert years == {1804}
    assert depad("1804-01-01", facts[0], years) is None   # Haitian Revolution ends on 1 January 1804
    assert depad("1805-01-01", facts[0], years) == "1805"


def test_states_jan1_needs_matching_year():
    assert states_jan1("On 1 January 1801 CE ...", 1801)
    assert not states_jan1("On 1 January 1801 CE ...", 1800)
    assert not states_jan1("On 21 January 1801 CE ...", 1801)
    assert not states_jan1("In January 1801 CE ...", 1801)


# ── handoff add / check / fix-dates ─────────────────────────────────────────

TRANSCRIPT_JAN1 = """Georgia's Golden Age (1089-1213 CE)

1. David IV becomes king of Georgia in 1089 CE.
2. On 1 January 1121 CE David IV defeats the Seljuks at the Battle of Didgori.
3) In January 1184 CE Tamar of Georgia begins to rule the kingdom, until 1213 CE.
"""


def _tagged_events():
    return [{**e, "fact": i} for i, e in enumerate(EVENTS, start=1)]


@pytest.fixture
def jan1_built(invoke, root):
    (root / "output/transcripts/campaign" / f"{SLUG}.txt").write_text(TRANSCRIPT_JAN1, encoding="utf-8")
    assert invoke("handoff", "init", SLUG, "--title", "Golden Age").exit_code == 0
    for part, payload in (("events", _tagged_events()), ("entities", ENTITIES), ("relations", RELATIONS),
                          ("summaries", SUMMARIES)):
        res = invoke("handoff", "add", SLUG, part, "-", input=json.dumps(payload))
        assert res.exit_code == 0, res.output
    return root / "output" / "campaign" / "extractions" / RUN_ID / "candidates.json"


def test_add_unpads_year_only_dates_with_a_note(invoke, jan1_built):
    res = invoke("handoff", "add", SLUG, "events", "-", input=json.dumps(
        [{"label": "Accession of David IV", "start_date": "1089-01-01", "end_date": "1089-01-01"}]))
    assert res.exit_code == 0, res.output
    assert "padded-date start_date '1089-01-01' -> '1089' (fact 1 states no 1 January" in res.output
    ev = next(e for e in read(jan1_built)["parsed_events"] if e["label"] == "Accession of David IV")
    assert (ev["start_date"], ev["end_date"]) == ("1089", "1089")


def test_add_keeps_a_stated_jan1_and_uses_january_month(invoke, jan1_built):
    res = invoke("handoff", "add", SLUG, "relations", "-", input=json.dumps([
        {"source_label": "Kingdom of Georgia", "relationship_type": "victorious_at", "target_label": "Battle of Didgori",
         "start_date": "1121-01-01", "source_event": "Battle of Didgori"},
        {"source_label": "Tamar of Georgia", "relationship_type": "rules", "target_label": "Kingdom of Georgia",
         "start_date": "1184-01-01", "end_date": "1213", "source_event": "Reign of Tamar"},
    ]))
    assert res.exit_code == 0, res.output
    rels = {(r["source_label"], r["relationship_type"]): r for r in read(jan1_built)["candidate_relations"]}
    assert rels[("Kingdom of Georgia", "victorious_at")]["start_date"] == "1121-01-01"   # fact 2 states it
    assert rels[("Tamar of Georgia", "rules")]["start_date"] == "1184-01"                # fact 3: January
    assert "'1121-01-01'" not in res.output


def test_add_unpads_entity_lifespan_not_in_its_fact(invoke, jan1_built):
    res = invoke("handoff", "add", SLUG, "entities", "-", input=json.dumps(
        [{"label": "David IV of Georgia", "start_date": "1073-01-01"}]))
    assert res.exit_code == 0, res.output
    ent = next(e for e in read(jan1_built)["candidate_entities"] if e["label"] == "David IV of Georgia")
    assert ent["start_date"] == "1073"


def _write_padded(path):
    doc = read(path)
    doc["parsed_events"][0]["start_date"] = "1089-01-01"
    doc["candidate_relations"][0]["start_date"] = "1089-01-01"
    doc["candidate_relations"][1]["start_date"] = "1121-01-01"   # stated by fact 2: stays
    path.write_text(json.dumps(doc), encoding="utf-8")


def test_check_fails_on_padded_dates_already_in_the_handoff(invoke, jan1_built):
    _write_padded(jan1_built)
    res = invoke("handoff", "check", SLUG)
    assert res.exit_code == 1
    assert res.output.count("padded-date:") == 2
    assert "event 'Accession of David IV': start_date '1089-01-01' -> '1089'" in res.output
    assert "handoff fix-dates RUN --apply" in res.output


def test_fix_dates_lists_by_default_and_writes_with_apply(invoke, jan1_built):
    _write_padded(jan1_built)
    res = invoke("handoff", "fix-dates", SLUG)
    assert res.exit_code == 0, res.output
    assert "would fix (rerun with --apply) 2 padded date(s)" in res.output
    assert read(jan1_built)["parsed_events"][0]["start_date"] == "1089-01-01"

    res = invoke("handoff", "fix-dates", SLUG, "--apply")
    assert "fixed 2 padded date(s)" in res.output
    doc = read(jan1_built)
    assert doc["parsed_events"][0]["start_date"] == "1089"
    assert doc["candidate_relations"][0]["start_date"] == "1089"
    assert doc["candidate_relations"][1]["start_date"] == "1121-01-01"
    assert invoke("handoff", "check", SLUG).exit_code == 0


# ── measure classification ──────────────────────────────────────────────────

def _seed_db_like(path):
    """Handoff state behind the fake DB rows below: a padded event + entity of fact 1."""
    _write_padded(path)
    doc = read(path)
    doc["candidate_entities"].append({"label": "Accession of David IV", "entity_type": "event_legal_reform",
                                      "start_date": "1089-01-01", "source_event": "Accession of David IV"})
    path.write_text(json.dumps(doc), encoding="utf-8")


# psql rows as measure.run_sql returns them: a padded and a stated relation, an event
# range padded in the handoff (start) and mirrored by the commit writer (end), a
# Wikidata-sourced range and a residue range (no handoff item, no QID any more).
DB_ROWS = [
    ["entities", "5"], ["jan1_ranges", "3"], ["jan1_relations", "2"],
    ["jan1_rel_row", "rel-1", "1089-01-01", "1089-01-01", RUN_ID, "Accession of David IV",
     "David IV of Georgia -rules-> Kingdom of Georgia"],
    ["jan1_rel_row", "rel-2", "1121-01-01", "", RUN_ID, "Battle of Didgori",
     "Kingdom of Georgia -victorious_at-> Battle of Didgori"],
    ["jan1_range_row", "tr-1", "", "1089-01-01", "1089-01-01", RUN_ID, "Accession of David IV"],
    ["jan1_range_row", "tr-2", "Q790", "1804-01-01", "", RUN_ID, "Haiti"],
    ["jan1_range_row", "tr-3", "", "2005-01-01", "", RUN_ID, "Uch"],
]


def test_classify_jan1_traces_rows_to_their_facts(jan1_built):
    _seed_db_like(jan1_built)
    fixes = {(f.id, f.table.split(".")[1]): f for f in measure.classify_jan1(DB_ROWS[3:])}
    assert len(fixes) == 7
    assert (fixes[("rel-1", "temporal_start")].verdict, fixes[("rel-1", "temporal_start")].correct) == ("padded", "1089")
    assert fixes[("rel-2", "temporal_start")].verdict == "stated"
    assert (fixes[("tr-1", "start_date")].verdict, fixes[("tr-1", "start_date")].correct) == ("padded", "1089")
    assert fixes[("tr-1", "end_date")].verdict == "padded"
    assert "mirrored from the other bound" in fixes[("tr-1", "end_date")].evidence
    assert fixes[("tr-2", "start_date")].verdict == "wikidata"
    assert (fixes[("tr-3", "start_date")].verdict, fixes[("tr-3", "start_date")].correct) == ("residue", "")


def test_measure_reports_padded_counts_and_writes_csv(invoke, jan1_built, monkeypatch, root):
    _seed_db_like(jan1_built)
    out = "\n".join("|".join(r) for r in DB_ROWS) + "\n"

    def fake_run(cmd, **kw):
        if "ps" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="db\n", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

    monkeypatch.setattr(measure.subprocess, "run", fake_run)
    target = root / "audit.csv"
    res = invoke("measure", "--jan1-csv", target)
    assert res.exit_code == 0, res.output
    # tr-1 (padded) + tr-3 (residue) are wrong, tr-2 (Wikidata) is genuine; rel-1 padded, rel-2 stated.
    assert "ranges=2 relations=1 padded (all -01-01: ranges=3 relations=2;" in res.output
    assert "wrote 7 -01-01 value(s)" in res.output
    with target.open(encoding="utf-8") as f:
        written = list(csv.reader(f))
    assert written[0] == ["table", "id", "current value", "correct value", "source run", "evidence"]
    assert written[1][:5] == ["relationships.temporal_start", "rel-1", "1089-01-01", "1089", RUN_ID]
    assert written[1][5].startswith("PADDED: David IV of Georgia -rules-> Kingdom of Georgia: fact 1:")


def test_measure_geo_line_shows_map_column_when_present():
    lines = measure.report_lines([["entities", "10"], ["geo", "EVENT", "10", "4", "3", "5", "2"]])
    assert "  EVENT     5/10 (50%)  georef=4 located=3 map=2/10 (20%)" in lines
