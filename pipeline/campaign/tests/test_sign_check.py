"""`handoff check` / `handoff add` BCE/CE sign guards and the measure's lifespan
classification (2026-10-07 sign fix)."""
import json
import subprocess

from pipeline.campaign import handoff_ops as ops
from pipeline.campaign import measure
from pipeline.campaign.tests.conftest import RUN_ID, SLUG, read

ROMAN_SLUG = "e06__europe__roman-gaul"
ROMAN_RUN = f"campaign_{ROMAN_SLUG}"
ROMAN = """Roman Gaul (27 BCE - 69 CE)

1. In 27 BCE Augustus organises the conquered Gallic lands into the provinces of Gallia Aquitania, Gallia Lugdunensis and Gallia Belgica.
2. On 31 December 1384 CE John Wycliffe dies at Lutterworth (England).
3. Between 595 and 589 BCE Psamtik II erects obelisks at Heliopolis.
"""


def _doc(entities, relations=(), events=None):
    return {
        "run_id": ROMAN_RUN, "source_transcript": f"output/transcripts/campaign/{ROMAN_SLUG}.txt", "title": "T",
        "summaries_precomputed": False,
        "parsed_events": events if events is not None else [
            {"label": "Gallic provinces", "description": "d", "start_date": "-27", "fact": 1},
            {"label": "Death of Wycliffe", "description": "d", "start_date": "1384-12-31", "fact": 2},
            {"label": "Obelisks", "description": "d", "start_date": "-595", "end_date": "-589", "fact": 3},
        ],
        "candidate_entities": list(entities), "candidate_relations": list(relations), "summaries": {},
    }


def _write(root, doc, slug=ROMAN_SLUG, transcript=ROMAN):
    tdir = root / "output" / "transcripts" / "campaign"
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / f"{slug}.txt").write_text(transcript, encoding="utf-8")
    hdir = root / "output" / "campaign" / "extractions" / f"campaign_{slug}"
    hdir.mkdir(parents=True, exist_ok=True)
    path = hdir / "candidates.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def _ent(label, etype, start=None, end=None, source_event=None):
    return {"label": label, "entity_type": etype, "start_date": start, "end_date": end, "source_event": source_event}


def _rel(src, rtype, dst, start=None, end=None, source_event=None):
    return {"source_label": src, "relationship_type": rtype, "target_label": dst, "start_date": start,
            "end_date": end, "source_event": source_event, "description": "d"}


def test_stated_eras_reads_ranges_and_shared_markers():
    eras = ops.stated_eras("Between 595 and 589 BCE ... c. 130–100 BCE ... from 41 to 54 CE ... between 2 BCE and 2 CE")
    assert eras[595] == eras[589] == eras[130] == eras[100] == {"bce"}
    assert eras[41] == eras[54] == {"ce"}
    assert eras[2] == {"bce", "ce"}


def test_sign_mismatches_against_the_fact():
    fact = "In 27 BCE Augustus organises Gallia Belgica."
    assert ops.sign_mismatches({"start_date": "27"}, fact) == [("start_date", "27", "-27")]
    assert ops.sign_mismatches({"start_date": "-27", "end_date": "14"}, fact) == []
    assert ops.sign_mismatches({"end_date": "-1384"}, "On 31 December 1384 CE John Wycliffe dies") == [
        ("end_date", "-1384", "1384")]
    # A mirrored span (-500..500) is not flagged: the stated year belongs to the other bound.
    assert ops.sign_mismatches({"start_date": "-500", "end_date": "500"}, "until c. 500 CE") == []


def test_check_fails_on_sign_mismatch_lifespan_and_relation_mirror(invoke, root):
    doc = _doc(
        [_ent("Augustus", "person", "-63", "14", "Gallic provinces"),
         _ent("Gallia Belgica", "political_entity", "27", "500", "Gallic provinces"),
         _ent("Bagrat IV", "person", "-1015", "1072", "Gallic provinces"),
         _ent("John Wycliffe", "person", "1330", "1384", "Death of Wycliffe"),
         _ent("Lutterworth", "city"),
         _ent("Ismail I", "person", "1487", "1524"),
         _ent("Safavid dynasty", "dynasty", "1501", "1736")],
        [_rel("Augustus", "rules", "Gallia Belgica", "-27", "14", "Gallic provinces"),
         _rel("John Wycliffe", "died_in", "Lutterworth", "-1384", "-1384", "Death of Wycliffe"),
         _rel("Ismail I", "rules", "Safavid dynasty", "-1501", "1524")])
    _write(root, doc)
    res = invoke("handoff", "check", ROMAN_SLUG)
    assert res.exit_code == 1, res.output
    out = res.output
    errors, warnings = out.split("warnings")[0], out.split("warnings")[1]
    # Entities and lifespan mirrors warn; events and relations dated by their fact fail.
    assert "sign-mismatch: entity 'Gallia Belgica': start_date '27' -> '-27'? (fact 1 states 27 BCE" in warnings
    assert "implausible-lifespan: entity 'Bagrat IV': sign split" in out
    assert "sign-mismatch: relation 'John Wycliffe|died_in|Lutterworth': start_date '-1384' -> '1384'? (fact 2 states 1384 CE" in errors
    # No fact for Ismail I's relation: his lifespan catches it.
    assert ("sign-mismatch: relation 'Ismail I|rules|Safavid dynasty': start_date '-1501' -> '1501'? "
            "(-1501 lies outside Ismail I's lifespan 1487..1524; 1501 lies inside)") in warnings
    assert "implausible-lifespan: entity 'Bagrat IV'" in errors
    assert "Augustus" not in out.split("errors")[1].split("warnings")[0]


def test_add_rejects_a_relation_date_its_fact_contradicts(invoke, root):
    _write(root, _doc([_ent("Augustus", "person", "-63", "14"), _ent("Gallia Lugdunensis", "political_entity")]))
    res = invoke("handoff", "add", ROMAN_SLUG, "relations", "-",
                 input=json.dumps([_rel("Augustus", "rules", "Gallia Lugdunensis", "27", None, "Gallic provinces")]))
    assert "start_date '27' -> '-27'? (fact 1 states 27 BCE" in res.output
    assert read(root / "output/campaign/extractions" / ROMAN_RUN / "candidates.json")["candidate_relations"] == []


def test_check_warns_on_a_mirrorable_bce_start_in_a_ce_era_run(invoke, root):
    slug = "e09__anatolia__byzantine-end"
    doc = _doc([_ent("Byzantine Empire", "political_entity", "-330", "1453")], events=[])
    doc["run_id"] = f"campaign_{slug}"
    _write(root, doc, slug=slug, transcript="Byzantine end\n\n1. In 1453 CE Constantinople falls.\n")
    res = invoke("handoff", "check", slug)
    assert "sign-split: entity 'Byzantine Empire': start -330 is BCE in a CE-era run" in res.output


# ── measure ────────────────────────────────────────────────────────────────

def test_classify_lifespans_traces_each_bound(root):
    doc = _doc([_ent("Bagrat IV", "person", "-1015", "1072"), _ent("Lewis Powell", "person", None, "1865-07-07"),
                _ent("Botai 14", "person", "-3517", "-3108")])
    _write(root, doc)
    rows = [
        ["lifespan_row", "e1", "Q451986", "-1015", "1072", ROMAN_RUN, "Bagrat IV"],
        ["lifespan_row", "e2", "Q6536971", "1576", "1865-07-07", ROMAN_RUN, "Lewis Powell"],
        ["lifespan_row", "e3", "Q153037", "-0100", "0100", ROMAN_RUN, "Coponius"],
        ["lifespan_row", "e4", "", "-3517", "-3108", ROMAN_RUN, "Botai 14"],
        ["rel_sign_row", "r1", "-1501", "1524", ROMAN_RUN, "Ismail I 1487..1524", "Ismail I -rules-> Safavid dynasty"],
    ]
    found = {x.id: x for x in measure.classify_lifespans(rows)}
    assert found["e1"].verdict == "sign-handoff"
    assert found["e2"].verdict == "mixed" and "start 1576 from wikidata" in found["e2"].evidence
    assert found["e3"].verdict == "sign-wikidata" and "century? start+end" in found["e3"].evidence
    assert found["e4"].verdict == "handoff"
    assert found["r1"].verdict == "relation-sign"
    lines = measure.report_lines([["entities", "9"], *rows, ["ce_bce_starts", "2", "1"], ["year0", "3", "0"]])
    assert any(line.startswith("person lifespans >110y    4   (sign-handoff=1 sign-wikidata=1 mixed=1 handoff=1;")
               for line in lines), lines
    assert any("entities=2 relations=1" in line for line in lines)


def test_measure_writes_the_sign_csv(invoke, root, monkeypatch):
    _write(root, _doc([_ent("Bagrat IV", "person", "-1015", "1072")]))
    out = "entities|1\nlifespan_row|e1|Q451986|-1015|1072|" + ROMAN_RUN + "|Bagrat IV\nyear0|0|0\nce_bce_starts|0|0\n"

    def fake_run(cmd, **kw):
        if "ps" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="db\n", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

    monkeypatch.setattr(measure.subprocess, "run", fake_run)
    target = root / "sign.csv"
    res = invoke("measure", "--sign-csv", target)
    assert res.exit_code == 0, res.output
    assert "person lifespans >110y    1   (sign-handoff=1" in res.output
    assert "wrote 1 lifespan/sign finding(s)" in res.output
    assert target.read_text(encoding="utf-8").splitlines()[1].startswith("lifespan,e1,Bagrat IV,-1015,1072,")


def test_unrelated_fixture_handoff_still_checks_clean(invoke, built):
    # The Georgian golden-age fixture (all CE, plausible lifespans) gains no new errors.
    assert invoke("handoff", "check", SLUG).exit_code == 0
    assert RUN_ID.endswith(SLUG)
