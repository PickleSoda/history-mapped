import json
from pathlib import Path

from click.testing import CliRunner

from pipeline.__main__ import cli as root_cli



def test_relations_workflow_emits_import_ready_outputs_and_manifest(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    parsed_path = artifact_dir / "parsed" / "parsed-00001.jsonl"
    parsed_path.parent.mkdir(parents=True, exist_ok=True)
    parsed_path.write_text(
        json.dumps(
            {
                "relation_id": 100,
                "tags": {
                    "name": "Kingdom of Testland",
                    "wikidata": "Q100",
                    "predecessor": "Old Testland",
                    "predecessor:wikidata": "Q090",
                    "start_date": "1700",
                    "end_date": "1799",
                },
                "stages": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(root_cli, ["borders", "relations-run", "--artifact-dir", str(artifact_dir)])

    assert result.exit_code == 0

    entities_path = artifact_dir / "relations_final" / "ohm_relation_entities.jsonl"
    hints_path = artifact_dir / "relations_final" / "ohm_relation_hints.jsonl"
    manifest_path = artifact_dir / "manifest.json"

    assert entities_path.exists()
    assert hints_path.exists()
    assert manifest_path.exists()

    entities = [json.loads(line) for line in entities_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    hints = [json.loads(line) for line in hints_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert entities == [
        {
            "name": "Old Testland",
            "entity_type": "political_entity",
            "entity_group": "POLITY",
            "wikidata_id": "Q090",
            "summary": None,
            "alternative_names": [],
            "temporal_start": None,
            "temporal_end": None,
            "verification_status": "pipeline_draft",
            "confidence": "medium",
            "source_citations": [{"source": "wikidata", "wikidata_id": "Q090"}],
        }
    ]

    assert hints == [
        {
            "source_wikidata_id": "Q100",
            "source_name": "Kingdom of Testland",
            "relationship_type": "preceded_by",
            "target_wikidata_id": "Q090",
            "target_label": "Old Testland",
            "temporal_start": None,
            "temporal_end": None,
            "confidence": "medium",
            "source": "wikidata:P155",
        }
    ]

    assert manifest["relation_stages"]["scan"]["status"] == "completed"
    assert manifest["relation_stages"]["enrich"]["status"] == "completed"
    assert manifest["relation_stages"]["build"]["status"] == "completed"
    assert manifest["summary"]["relation_final_entities"] == 1
    assert manifest["summary"]["relation_final_hints"] == 1
