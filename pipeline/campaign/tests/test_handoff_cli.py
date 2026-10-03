import json

from pipeline.agent.handoff import load_handoff
from pipeline.agent.validate_handoff import validate
from pipeline.campaign.tests.conftest import (
    ENTITIES, EVENTS, RELATIONS, RUN_ID, SLUG, SUMMARIES, read,
)


def _add(invoke, part, payload, run=SLUG, *extra):
    return invoke("handoff", "add", run, part, "-", *extra, input=json.dumps(payload))


# ── init ────────────────────────────────────────────────────────────────────

def test_init_creates_skeleton(invoke, root):
    res = invoke("handoff", "init", RUN_ID, "--title", "Golden Age")
    assert res.exit_code == 0, res.output
    assert "transcript facts=3" in res.output
    doc = read(root / "output/campaign/extractions" / RUN_ID / "candidates.json")
    assert doc == {
        "run_id": RUN_ID,
        "source_transcript": f"output/transcripts/campaign/{SLUG}.txt",
        "title": "Golden Age",
        "summaries_precomputed": True,
        "parsed_events": [], "candidate_entities": [], "candidate_relations": [], "summaries": {},
    }


def test_init_refuses_existing_unless_force(invoke, built):
    res = invoke("handoff", "init", SLUG, "--title", "Again")
    assert res.exit_code == 1
    assert "already exists" in res.output
    res = invoke("handoff", "init", SLUG, "--title", "Again", "--force")
    assert res.exit_code == 0
    assert read(built)["candidate_entities"] == []
    assert len(read(built.with_name("candidates.prev.json"))["candidate_entities"]) == len(ENTITIES)


def test_init_warns_when_transcript_missing(invoke):
    res = invoke("handoff", "init", "e08__nowhere__nothing", "--title", "X")
    assert res.exit_code == 0
    assert "not found" in res.output


# ── add ─────────────────────────────────────────────────────────────────────

def test_built_handoff_loads_and_validates(built):
    doc = load_handoff(built)
    assert len(doc.parsed_events) == 3 and len(doc.candidate_relations) == 7
    assert validate(str(built)) == []
    raw = read(built)
    assert raw["parsed_events"][1]["start_date"] == "1121"
    ent = raw["candidate_entities"][1]
    assert ent["aliases"] == [] and ent["wikidata_id"] is None and ent["confidence"] == 0.0
    rel = raw["candidate_relations"][0]
    assert rel["final_confidence"] == 0.0 and rel["source_wikidata_id"] is None


def test_add_prints_totals(invoke, built):
    res = _add(invoke, "events", [EVENTS[0]])
    assert res.exit_code == 0
    assert "events: added=0 updated=1 rejected=0" in res.output
    assert "events=3 entities=5 relations=7 summaries=5" in res.output


def test_add_requires_existing_handoff(invoke):
    res = _add(invoke, "events", EVENTS)
    assert res.exit_code == 1
    assert "handoff init" in res.output


def test_add_rejects_bad_items_but_keeps_good_ones(invoke, built):
    payload = [
        {"source_label": "Tamar of Georgia", "relationship_type": "knows", "target_label": "Seljuk Empire"},
        {"source_label": "Tamar of Georgia", "relationship_type": "at_war_with", "target_label": "Ghost"},
        {"source_label": "Tamar of Georgia", "relationship_type": "at_war_with", "target_label": "Seljuk Empire",
         "start_date": "1190", "description": "Fought the Seljuks."},
        {"source_label": "Tamar of Georgia", "relationship_type": "rules", "target_label": "Tamar of Georgia"},
    ]
    res = _add(invoke, "relations", payload)
    assert res.exit_code == 1
    assert "rejected [0]" in res.output and "'knows' not allowed" in res.output
    assert "rejected [1]" in res.output and "'Ghost' is not an entity label" in res.output
    assert "rejected [3]" in res.output and "same entity" in res.output
    assert "added=1" in res.output and "rejected=3" in res.output
    assert len(read(built)["candidate_relations"]) == 8


def test_add_entity_rejections(invoke, built):
    payload = [
        {"label": "Bad Date", "entity_type": "person", "start_date": "331 BCE"},
        {"label": "Reversed", "entity_type": "person", "start_date": "1200", "end_date": "1100"},
        {"label": "Odd Type", "entity_type": "historical_period"},
        {"label": "Has QID", "entity_type": "person", "wikidata_id": "Q42"},
        {"label": "Bad Event", "entity_type": "person", "source_event": "No Such Event"},
        {"label": "Extra", "entity_type": "person", "summary": "nope"},
        {"entity_type": "person"},
    ]
    res = _add(invoke, "entities", payload)
    assert res.exit_code == 1
    out = res.output
    assert "'331 BCE' must be a year string" in out
    assert "start 1200 > end 1100" in out
    assert "'historical_period' is not canonical" in out
    assert "wikidata_id must stay null" in out
    assert "'No Such Event' is not an event label" in out
    assert "unknown field(s) summary" in out and "handoff add RUN summaries" in out
    assert "label: Field required" in out
    assert "rejected=7" in out
    assert len(read(built)["candidate_entities"]) == len(ENTITIES)


def test_add_event_outside_era_bounds_rejected(invoke, built):
    res = _add(invoke, "events", [{"label": "Too early", "start_date": "-500"}])
    assert res.exit_code == 1
    assert "outside e08 bounds" in res.output


def test_add_normalizes_synonym_type_with_note(invoke, built):
    res = _add(invoke, "entities", [{"label": "Kingdom of Kakheti", "entity_type": "kingdom",
                                     "start_date": 1014, "source_event": None}])
    assert res.exit_code == 0
    assert "'kingdom' -> 'political_entity'" in res.output
    ent = read(built)["candidate_entities"][-1]
    assert ent["entity_type"] == "political_entity" and ent["start_date"] == "1014"


def test_add_merges_partial_update(invoke, built):
    res = _add(invoke, "entities", [{"label": "Kingdom of Georgia", "end_date": "1490"}])
    assert res.exit_code == 0 and "updated=1" in res.output
    ent = next(e for e in read(built)["candidate_entities"] if e["label"] == "Kingdom of Georgia")
    assert ent["end_date"] == "1490" and ent["entity_type"] == "political_entity" and ent["start_date"] == "1008"

    res = _add(invoke, "relations", [{"source_label": "Tamar of Georgia", "relationship_type": "rules",
                                      "target_label": "Kingdom of Georgia", "description": "Queen regnant."}])
    rel = next(r for r in read(built)["candidate_relations"]
               if r["source_label"] == "Tamar of Georgia" and r["relationship_type"] == "rules")
    assert rel["description"] == "Queen regnant." and rel["start_date"] == "1184"


def test_add_replace_flag_replaces_wholesale(invoke, built):
    res = _add(invoke, "entities", [{"label": "Kingdom of Georgia", "entity_type": "political_entity"}],
               SLUG, "--replace")
    assert res.exit_code == 0
    ent = next(e for e in read(built)["candidate_entities"] if e["label"] == "Kingdom of Georgia")
    assert ent["start_date"] is None and ent["source_event"] is None


def test_add_summaries_array_form_and_orphan_rejection(invoke, built):
    payload = [
        {"label": "Tamar of Georgia", "summary": "New summary.", "significance": "New significance."},
        {"label": "Nobody", "summary": "x", "significance": "y"},
        {"label": "Seljuk Empire", "summary": "", "significance": "y"},
    ]
    res = _add(invoke, "summaries", payload)
    assert res.exit_code == 1
    assert "no entity labelled 'Nobody'" in res.output
    assert "summary must be a non-empty string" in res.output
    s = read(built)["summaries"]
    assert s["Tamar of Georgia"] == {"summary": "New summary.", "significance": "New significance."}
    assert s["Seljuk Empire"] == SUMMARIES["Seljuk Empire"]


def test_add_invalid_json_writes_nothing(invoke, built):
    before = built.read_text()
    res = invoke("handoff", "add", SLUG, "events", "-", input="[{not json")
    assert res.exit_code == 1 and "invalid JSON" in res.output
    assert built.read_text() == before


def test_add_accepts_code_fenced_json_and_file(invoke, built, tmp_path):
    res = invoke("handoff", "add", SLUG, "events", "-",
                 input="```json\n" + json.dumps([{"label": "Council of Ruisi-Urbnisi", "start_date": "1103"}]) + "\n```")
    assert res.exit_code == 0, res.output
    f = tmp_path / "ev.json"
    f.write_text(json.dumps({"label": "Siege of Tbilisi", "start_date": "1122"}))
    assert invoke("handoff", "add", SLUG, "events", f).exit_code == 0
    assert len(read(built)["parsed_events"]) == 5


def test_written_file_is_one_item_per_line(built):
    lines = built.read_text().splitlines()
    assert sum(1 for line in lines if line.startswith('    {"label"')) == len(EVENTS) + len(ENTITIES)


# ── rm / rename ─────────────────────────────────────────────────────────────

def test_rm_entity_cascades(invoke, built):
    res = invoke("handoff", "rm", SLUG, "entities", "Seljuk Empire")
    assert res.exit_code == 0
    assert "cascaded relation Seljuk Empire|defeated_at|Battle of Didgori" in res.output
    assert "cascaded relation Seljuk Empire|at_war_with|Kingdom of Georgia" in res.output
    assert "cascaded summary" in res.output
    doc = read(built)
    assert len(doc["candidate_relations"]) == 5 and "Seljuk Empire" not in doc["summaries"]
    assert validate(str(built)) == []


def test_rm_relation_and_missing_key(invoke, built):
    res = invoke("handoff", "rm", SLUG, "relations", "Tamar of Georgia|rules|Kingdom of Georgia", "A|rules|B")
    assert res.exit_code == 1
    assert "removed relation Tamar of Georgia|rules|Kingdom of Georgia" in res.output
    assert "not found: A|rules|B" in res.output
    assert len(read(built)["candidate_relations"]) == 6


def test_rm_relation_bad_key_format(invoke, built):
    res = invoke("handoff", "rm", SLUG, "relations", "A-rules-B")
    assert res.exit_code == 1 and "SOURCE|TYPE|TARGET" in res.output


def test_rm_event_clears_source_event(invoke, built):
    res = invoke("handoff", "rm", SLUG, "events", "Reign of Tamar")
    assert res.exit_code == 0
    assert "cleared source_event on 1 entities, 2 relations" in res.output
    doc = read(built)
    assert all(e["source_event"] != "Reign of Tamar" for e in doc["candidate_entities"])


def test_rename_entity_everywhere(invoke, built):
    res = invoke("handoff", "rename", SLUG, "David IV of Georgia", "David IV")
    assert res.exit_code == 0, res.output
    doc = read(built)
    assert "David IV" in {e["label"] for e in doc["candidate_entities"]}
    assert "David IV" in doc["summaries"] and "David IV of Georgia" not in doc["summaries"]
    assert sum(r["source_label"] == "David IV" for r in doc["candidate_relations"]) == 2
    assert doc["parsed_events"][0]["mentioned_entities"][0] == "David IV"
    assert validate(str(built)) == []


def test_rename_onto_existing_requires_merge(invoke, built):
    res = invoke("handoff", "rename", SLUG, "Tamar of Georgia", "David IV of Georgia")
    assert res.exit_code == 1 and "--merge" in res.output


def test_rename_merge_folds_entity(invoke, built):
    _add(invoke, "entities", [{"label": "David the Builder", "entity_type": "person", "aliases": ["Davit IV"]}])
    _add(invoke, "relations", [
        {"source_label": "David the Builder", "relationship_type": "rules", "target_label": "Kingdom of Georgia"},
        {"source_label": "David the Builder", "relationship_type": "at_war_with", "target_label": "Seljuk Empire"},
    ])
    res = invoke("handoff", "rename", SLUG, "David the Builder", "David IV of Georgia", "--merge")
    assert res.exit_code == 0, res.output
    assert "dropped duplicate relation David IV of Georgia|rules|Kingdom of Georgia" in res.output
    doc = read(built)
    labels = [e["label"] for e in doc["candidate_entities"]]
    assert "David the Builder" not in labels
    david = next(e for e in doc["candidate_entities"] if e["label"] == "David IV of Georgia")
    assert "Davit IV" in david["aliases"]
    keys = {(r["source_label"], r["relationship_type"], r["target_label"]) for r in doc["candidate_relations"]}
    assert ("David IV of Georgia", "at_war_with", "Seljuk Empire") in keys
    assert len(doc["candidate_relations"]) == 8


def test_rename_event_updates_references(invoke, built):
    res = invoke("handoff", "rename-event", SLUG, "Battle of Didgori", "Didgori campaign")
    assert res.exit_code == 0
    assert "repointed source_event on 2 entities, 4 relations" in res.output
    doc = read(built)
    assert {e["label"] for e in doc["candidate_entities"]} >= {"Battle of Didgori"}
    assert not any(r["source_event"] == "Battle of Didgori" for r in doc["candidate_relations"])


# ── show / get ──────────────────────────────────────────────────────────────

def test_show_formats(invoke, built):
    out = invoke("handoff", "show", SLUG, "--part", "events").output.splitlines()
    assert out[2] == "1184..1213 Reign of Tamar"
    out = invoke("handoff", "show", SLUG, "--part", "entities").output.splitlines()
    assert out[0] == "David IV of Georgia [person] 1073..1125"
    out = invoke("handoff", "show", SLUG, "--part", "relations").output.splitlines()
    assert out[0] == "David IV of Georgia -rules-> Kingdom of Georgia (1089)"
    out = invoke("handoff", "show", SLUG, "--part", "relations", "--labels-only").output.splitlines()
    assert out[0] == "David IV of Georgia|rules|Kingdom of Georgia"
    out = invoke("handoff", "show", SLUG).output
    assert "# events (3)" in out and "# summaries (5)" in out


def test_get_prints_full_items(invoke, built):
    res = invoke("handoff", "get", SLUG, "relations", "Seljuk Empire|defeated_at|Battle of Didgori")
    item = json.loads(res.output.strip())
    assert item["description"] == "Seljuk defeat."
    assert invoke("handoff", "get", SLUG, "entities", "Nope").exit_code == 1


# ── check / finalize ────────────────────────────────────────────────────────

def test_check_clean_handoff(invoke, built):
    res = invoke("handoff", "check", SLUG)
    assert res.exit_code == 0, res.output
    assert f"check {RUN_ID}: facts=3 events=3 entities=5 relations=7" in res.output
    assert "self-audit" in res.output
    assert res.output.strip().endswith("OK: 0 error(s), 1 warning(s)")


def test_check_reports_hard_errors_and_warnings(invoke, built):
    doc = read(built)
    doc["candidate_relations"].append({"source_label": "Ghost", "relationship_type": "befriends",
                                       "target_label": "Kingdom of Georgia"})
    doc["candidate_entities"].append({"label": "Kingdom of  Georgia!", "entity_type": "political_entity"})
    doc["candidate_entities"].append({"label": "Bagrat III", "entity_type": "person",
                                      "aliases": ["Tamar of Georgia"], "source_event": "Unknown"})
    doc["summaries"].pop("Tamar of Georgia")
    doc["parsed_events"].append({"label": "Way off", "start_date": "1800"})
    built.write_text(json.dumps(doc))
    res = invoke("handoff", "check", SLUG)
    assert res.exit_code == 1
    out = res.output
    assert "dangling-endpoint: relation 'Ghost|befriends|Kingdom of Georgia'" in out
    assert "relation-type:" in out
    assert "summary-missing: entity 'Tamar of Georgia'" in out
    assert "era-bounds: event 'Way off'" in out
    assert "near-duplicate: 'Kingdom of Georgia' ~ 'Kingdom of  Georgia!'" in out
    assert "alias 'Tamar of Georgia' matches entity 'Tamar of Georgia'" in out
    assert "orphan: entity 'Bagrat III'" in out
    assert "source-event: entity 'Bagrat III'" in out
    assert "summary-missing" in out.split("warnings")[0]
    assert "FAIL:" in out


def test_check_density_and_coverage_warnings(invoke, built):
    invoke("handoff", "rm", SLUG, "relations", "Seljuk Empire|at_war_with|Kingdom of Georgia",
           "David IV of Georgia|commanded|Battle of Didgori", "Tamar of Georgia|resided_in|Kingdom of Georgia")
    res = invoke("handoff", "check", SLUG)
    assert res.exit_code == 0
    assert "density: relations/entities 0.80 < 1.3" in res.output


def test_finalize_stamps_self_audit_and_validates(invoke, built):
    doc = read(built)
    doc["self_audit"] = {"notes": "keep me"}
    built.write_text(json.dumps(doc))
    res = invoke("handoff", "finalize", SLUG, "--critic-iterations", "3")
    assert res.exit_code == 0, res.output
    assert "OK " in res.output
    assert read(built)["self_audit"] == {"notes": "keep me", "critic_iterations": 3, "orphan_check_done": True}


def test_finalize_exit_mirrors_validator(invoke, built):
    doc = read(built)
    doc["summaries"] = {}
    built.write_text(json.dumps(doc))
    res = invoke("handoff", "finalize", SLUG)
    assert res.exit_code == 1
    assert "INVALID handoff" in res.output


def test_check_caps_warnings_unless_all(invoke, built):
    orphans = [{"label": f"Village {i}", "entity_type": "city"} for i in range(33)]
    assert _add(invoke, "entities", orphans).exit_code == 0
    res = invoke("handoff", "check", SLUG)
    assert "orphan: ... +3 more (use --all)" in res.output
    assert res.output.count("  orphan: entity") == 30
    res = invoke("handoff", "check", SLUG, "--all")
    assert res.output.count("  orphan: entity") == 33 and "use --all" not in res.output


def test_finalize_default_critic_iterations(invoke, built):
    assert invoke("handoff", "finalize", SLUG).exit_code == 0
    assert read(built)["self_audit"] == {"critic_iterations": 2, "orphan_check_done": True}
