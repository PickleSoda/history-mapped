import json
from pathlib import Path

from pipeline.agent.validate_handoff import main
from pipeline.agent.tests.test_handoff import _sample_doc


def _write(tmp_path, mutate=None):
    doc = _sample_doc()
    if mutate:
        mutate(doc)
    p = tmp_path / "candidates.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return str(p)


def test_valid_handoff_passes(tmp_path, capsys):
    assert main(_write(tmp_path)) == 0
    assert "OK" in capsys.readouterr().out


def test_orphan_relation_endpoint_fails(tmp_path):
    def mutate(doc):
        doc["candidate_relations"][0]["target_label"] = "Ghost Entity"
    assert main(_write(tmp_path, mutate)) == 1


def test_disallowed_relation_type_fails(tmp_path):
    def mutate(doc):
        doc["candidate_relations"][0]["relationship_type"] = "knows"
    assert main(_write(tmp_path, mutate)) == 1


def test_missing_summary_fails_when_precomputed(tmp_path):
    def mutate(doc):
        doc["summaries"] = {}
    assert main(_write(tmp_path, mutate)) == 1


def test_reversed_dates_fail(tmp_path):
    def mutate(doc):
        doc["candidate_entities"][0]["start_date"] = "1125"
        doc["candidate_entities"][0]["end_date"] = "1073"
    assert main(_write(tmp_path, mutate)) == 1


def test_non_canonical_entity_type_fails(tmp_path):
    def mutate(doc):
        doc["candidate_entities"][0]["entity_type"] = "historical_period"
    assert main(_write(tmp_path, mutate)) == 1


def test_malformed_json_fails(tmp_path):
    p = tmp_path / "candidates.json"
    p.write_text("{not json", encoding="utf-8")
    assert main(str(p)) == 1


def test_era_bounds_checked_when_encoded_in_filename(tmp_path):
    d = tmp_path / "e04__x"
    d.mkdir()
    p = d / "candidates.json"
    doc = _sample_doc()
    doc["candidate_entities"][0]["start_date"] = "-3000"
    p.write_text(json.dumps(doc), encoding="utf-8")
    assert main(str(p)) == 1
