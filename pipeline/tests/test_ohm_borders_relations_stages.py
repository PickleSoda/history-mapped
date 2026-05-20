import json
from pathlib import Path

from click.testing import CliRunner

from pipeline.__main__ import cli as root_cli
from pipeline.ohm_borders.__main__ import cli as borders_cli
from pipeline.ohm_borders.stages import run_relations_build_stage



def test_run_relations_build_stage_emits_final_entities_and_hints(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    enriched_path = artifact_dir / "relations_enriched" / "relations-enriched-00001.json"
    enriched_path.parent.mkdir(parents=True, exist_ok=True)
    enriched_path.write_text(
        json.dumps(
            [
                {
                    "source_ohm_relation_id": "100",
                    "source_wikidata_id": "Q100",
                    "source_name": "Kingdom of Testland",
                    "relationship_type": "preceded_by",
                    "inverse_relationship_type": "succeeded_by",
                    "target_wikidata_id": "Q090",
                    "target_label": "Old Testland",
                    "source_tag_key": "predecessor",
                    "source": "wikidata:P155",
                    "temporal_start": None,
                    "temporal_end": None,
                    "target_entity": {
                        "name": "Old Testland",
                        "entity_type": "political_entity",
                        "entity_group": "POLITY",
                        "wikidata_id": "Q090",
                        "summary": "former kingdom",
                        "alternative_names": [],
                        "temporal_start": "1700",
                        "temporal_end": "1799",
                        "verification_status": "pipeline_draft",
                        "confidence": "medium",
                        "source_citations": [{"source": "wikidata", "wikidata_id": "Q090"}],
                    },
                }
            ]
        ),
        encoding="utf-8",
    )

    result = run_relations_build_stage(run_id="run-001", artifact_dir=artifact_dir)

    entities_path = artifact_dir / "relations_final" / "ohm_relation_entities.jsonl"
    hints_path = artifact_dir / "relations_final" / "ohm_relation_hints.jsonl"
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))

    assert result["status"] == "completed"
    assert entities_path.exists()
    assert hints_path.exists()
    assert entities_path.read_text(encoding="utf-8").count("\n") == 1
    assert hints_path.read_text(encoding="utf-8").count("\n") == 1
    assert manifest["relation_stages"]["build"]["status"] == "completed"
    assert manifest["summary"]["relation_final_entities"] == 1
    assert manifest["summary"]["relation_final_hints"] == 1


def test_run_relations_build_stage_updates_subgraph_closure_report_with_bundle_validation(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    enriched_path = artifact_dir / "relations_enriched" / "relations-enriched-00001.json"
    enriched_path.parent.mkdir(parents=True, exist_ok=True)
    enriched_path.write_text(
        json.dumps(
            [
                {
                    "source_ohm_relation_id": "100",
                    "source_wikidata_id": "Q100",
                    "source_name": "Kingdom of Testland",
                    "relationship_type": "preceded_by",
                    "inverse_relationship_type": "succeeded_by",
                    "target_wikidata_id": "Q090",
                    "target_label": "Old Testland",
                    "source_tag_key": "predecessor",
                    "source": "wikidata:P155",
                    "temporal_start": None,
                    "temporal_end": None,
                    "target_entity": {
                        "name": "Old Testland",
                        "entity_type": "political_entity",
                        "entity_group": "POLITY",
                        "wikidata_id": "Q090",
                    },
                },
                {
                    "source_ohm_relation_id": "100",
                    "source_wikidata_id": "Q100",
                    "source_name": "Kingdom of Testland",
                    "relationship_type": "succeeded_by",
                    "inverse_relationship_type": "preceded_by",
                    "target_wikidata_id": "Q404",
                    "target_label": "Missing Testland",
                    "source_tag_key": "successor",
                    "source": "wikidata:P156",
                    "temporal_start": None,
                    "temporal_end": None,
                    "target_entity": {
                        "name": "Missing Testland",
                        "entity_type": "political_entity",
                        "entity_group": "POLITY",
                        "wikidata_id": "Q404",
                    },
                },
            ]
        ),
        encoding="utf-8",
    )
    (artifact_dir / "final").mkdir(parents=True, exist_ok=True)
    (artifact_dir / "final" / "ohm_borders.jsonl").write_text(
        json.dumps({"wikidata_id": "Q100", "name": "Kingdom of Testland"}) + "\n",
        encoding="utf-8",
    )
    (artifact_dir / "subgraph").mkdir(parents=True, exist_ok=True)
    (artifact_dir / "subgraph" / "closure_report.json").write_text(
        json.dumps({"included_relation_count": 1}, indent=2),
        encoding="utf-8",
    )

    run_relations_build_stage(run_id="run-001", artifact_dir=artifact_dir)

    closure_report = json.loads((artifact_dir / "subgraph" / "closure_report.json").read_text(encoding="utf-8"))

    assert closure_report["bundle_validation"]["import_ready"] is True
    assert closure_report["bundle_validation"]["known_wikidata_ids"] == ["Q090", "Q100", "Q404"]
    assert closure_report["bundle_validation"]["missing_wikidata_ids"] == []



def test_relations_commands_are_wired_in_ohm_borders_cli(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    enriched_path = artifact_dir / "relations_enriched" / "relations-enriched-00001.json"
    enriched_path.parent.mkdir(parents=True, exist_ok=True)
    enriched_path.write_text(
        json.dumps(
            [
                {
                    "source_ohm_relation_id": "100",
                    "source_wikidata_id": "Q100",
                    "source_name": "Kingdom of Testland",
                    "relationship_type": "preceded_by",
                    "inverse_relationship_type": "succeeded_by",
                    "target_wikidata_id": "Q090",
                    "target_label": "Old Testland",
                    "source_tag_key": "predecessor",
                    "source": "wikidata:P155",
                    "temporal_start": None,
                    "temporal_end": None,
                    "target_entity": {
                        "name": "Old Testland",
                        "entity_type": "political_entity",
                        "entity_group": "POLITY",
                        "wikidata_id": "Q090",
                        "summary": "former kingdom",
                        "alternative_names": [],
                        "temporal_start": "1700",
                        "temporal_end": "1799",
                        "verification_status": "pipeline_draft",
                        "confidence": "medium",
                        "source_citations": [{"source": "wikidata", "wikidata_id": "Q090"}],
                    },
                }
            ]
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(borders_cli, ["relations-build", "--artifact-dir", str(artifact_dir)])

    assert result.exit_code == 0
    assert "Relations build completed" in result.output
    assert (artifact_dir / "relations_final" / "ohm_relation_entities.jsonl").exists()
    assert (artifact_dir / "relations_final" / "ohm_relation_hints.jsonl").exists()



def test_relations_commands_are_wired_in_top_level_borders_cli(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    enriched_path = artifact_dir / "relations_enriched" / "relations-enriched-00001.json"
    enriched_path.parent.mkdir(parents=True, exist_ok=True)
    enriched_path.write_text(
        json.dumps(
            [
                {
                    "source_ohm_relation_id": "100",
                    "source_wikidata_id": "Q100",
                    "source_name": "Kingdom of Testland",
                    "relationship_type": "preceded_by",
                    "inverse_relationship_type": "succeeded_by",
                    "target_wikidata_id": "Q090",
                    "target_label": "Old Testland",
                    "source_tag_key": "predecessor",
                    "source": "wikidata:P155",
                    "temporal_start": None,
                    "temporal_end": None,
                    "target_entity": {
                        "name": "Old Testland",
                        "entity_type": "political_entity",
                        "entity_group": "POLITY",
                        "wikidata_id": "Q090",
                        "summary": "former kingdom",
                        "alternative_names": [],
                        "temporal_start": "1700",
                        "temporal_end": "1799",
                        "verification_status": "pipeline_draft",
                        "confidence": "medium",
                        "source_citations": [{"source": "wikidata", "wikidata_id": "Q090"}],
                    },
                }
            ]
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(root_cli, ["borders", "relations-build", "--artifact-dir", str(artifact_dir)])

    assert result.exit_code == 0
    assert "Relations build completed" in result.output



def test_relations_run_command_executes_scan_enrich_build(tmp_path: Path) -> None:
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
                },
                "stages": [],
            }
        ) + "\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(borders_cli, ["relations-run", "--artifact-dir", str(artifact_dir)])

    assert result.exit_code == 0
    assert (artifact_dir / "relations_candidates" / "relations-candidates-00001.jsonl").exists()
    assert (artifact_dir / "relations_enriched" / "relations-enriched-00001.json").exists()
    assert (artifact_dir / "relations_final" / "ohm_relation_entities.jsonl").exists()
    assert (artifact_dir / "relations_final" / "ohm_relation_hints.jsonl").exists()
