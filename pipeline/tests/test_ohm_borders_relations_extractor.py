import json
from pathlib import Path

import orjson

from pipeline.ohm_borders.relations_extractor import extract_relation_candidates
from pipeline.ohm_borders.stages import run_relations_scan_stage



def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        for record in records:
            handle.write(orjson.dumps(record) + b"\n")



def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]



def test_extract_relation_candidates_supports_predecessor_successor_and_event_variants() -> None:
    polity = {
        "relation_id": 100,
        "tags": {
            "name": "Kingdom of Testland",
            "wikidata": "Q100",
            "predecessor": "Old Testland",
            "predecessor:wikidata": "Q090",
        },
        "stages": [
            {
                "relation_id": 101,
                "tags": {
                    "start_date": "1800",
                    "end_date": "1850",
                    "successor": "New Testland",
                    "successor:wikidata": "Q110",
                    "start_event": "Testland Revolution",
                    "start_event:wikidata": "Q120",
                    "end_event": "Treaty of Testland",
                    "end_event:wikidata": "Q130",
                },
                "geometry": None,
            }
        ],
    }

    assert extract_relation_candidates(polity) == [
        {
            "source_ohm_relation_id": "100",
            "source_wikidata_id": "Q100",
            "source_name": "Kingdom of Testland",
            "relationship_type": "caused",
            "target_wikidata_id": "Q130",
            "target_label": "Treaty of Testland",
            "source_tag_key": "end_event",
            "temporal_start": "1800",
            "temporal_end": "1850",
        },
        {
            "source_ohm_relation_id": "100",
            "source_wikidata_id": "Q100",
            "source_name": "Kingdom of Testland",
            "relationship_type": "preceded_by",
            "target_wikidata_id": "Q090",
            "target_label": "Old Testland",
            "source_tag_key": "predecessor",
            "temporal_start": None,
            "temporal_end": None,
        },
        {
            "source_ohm_relation_id": "100",
            "source_wikidata_id": "Q100",
            "source_name": "Kingdom of Testland",
            "relationship_type": "resulted_from",
            "target_wikidata_id": "Q120",
            "target_label": "Testland Revolution",
            "source_tag_key": "start_event",
            "temporal_start": "1800",
            "temporal_end": "1850",
        },
        {
            "source_ohm_relation_id": "100",
            "source_wikidata_id": "Q100",
            "source_name": "Kingdom of Testland",
            "relationship_type": "succeeded_by",
            "target_wikidata_id": "Q110",
            "target_label": "New Testland",
            "source_tag_key": "successor",
            "temporal_start": "1800",
            "temporal_end": "1850",
        },
    ]



def test_extract_relation_candidates_ignores_records_without_source_wikidata() -> None:
    polity = {
        "relation_id": 100,
        "tags": {
            "name": "Unknown Testland",
            "predecessor": "Older Testland",
            "predecessor:wikidata": "Q090",
        },
        "stages": [],
    }

    assert extract_relation_candidates(polity) == []



def test_run_relations_scan_stage_writes_candidate_shards_and_updates_manifest(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    parsed_path = artifact_dir / "parsed" / "parsed-00001.jsonl"
    _write_jsonl(
        parsed_path,
        [
            {
                "relation_id": 100,
                "tags": {
                    "name": "Kingdom of Testland",
                    "wikidata": "Q100",
                    "predecessor": "Old Testland",
                    "predecessor:wikidata": "Q090",
                },
                "stages": [
                    {
                        "relation_id": 101,
                        "tags": {
                            "start_date": "1800",
                            "end_date": "1850",
                            "successor": "New Testland",
                            "successor:wikidata": "Q110",
                        },
                        "geometry": None,
                    }
                ],
            }
        ],
    )

    result = run_relations_scan_stage(
        run_id="run-001",
        artifact_dir=artifact_dir,
    )

    output_path = artifact_dir / "relations_candidates" / "relations-candidates-00001.jsonl"
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))

    assert result["status"] == "completed"
    assert result["candidate_count"] == 2
    assert _read_jsonl(output_path) == [
        {
            "source_ohm_relation_id": "100",
            "source_wikidata_id": "Q100",
            "source_name": "Kingdom of Testland",
            "relationship_type": "preceded_by",
            "target_wikidata_id": "Q090",
            "target_label": "Old Testland",
            "source_tag_key": "predecessor",
            "temporal_start": None,
            "temporal_end": None,
        },
        {
            "source_ohm_relation_id": "100",
            "source_wikidata_id": "Q100",
            "source_name": "Kingdom of Testland",
            "relationship_type": "succeeded_by",
            "target_wikidata_id": "Q110",
            "target_label": "New Testland",
            "source_tag_key": "successor",
            "temporal_start": "1800",
            "temporal_end": "1850",
        },
    ]
    assert manifest["relation_stages"]["scan"]["status"] == "completed"
    assert manifest["relation_stages"]["scan"]["outputs"] == [
        "relations_candidates/relations-candidates-00001.jsonl"
    ]
    assert manifest["summary"]["relation_candidate_shards"] == 1
    assert manifest["summary"]["relation_candidates"] == 2
