import pytest

from pipeline.ohm_borders.artifacts import raw_overpass_path, raw_shard_path, subgraph_closure_report_path, subgraph_seed_path
from pipeline.ohm_borders.subgraph_extractor import (
    SeedResolutionError,
    extract_country_subgraph,
    validate_bundle_closure,
)
from pipeline.ohm_borders.stage_extract_subgraph import run_extract_subgraph_stage


def _fixture_overpass() -> dict:
    return {
        "version": 0.6,
        "elements": [
            {
                "type": "relation",
                "id": 100,
                "tags": {
                    "type": "chronology",
                    "boundary": "administrative",
                    "admin_level": "2",
                    "name": "Roman Empire",
                    "wikidata": "Q1",
                },
                "members": [
                    {"type": "relation", "ref": 101, "role": ""},
                    {"type": "relation", "ref": 102, "role": ""},
                ],
            },
            {
                "type": "relation",
                "id": 101,
                "tags": {
                    "boundary": "administrative",
                    "admin_level": "2",
                    "name": "Roman Empire at peak",
                    "wikidata": "Q1",
                    "predecessor:wikidata": "Q2",
                    "successor:wikidata": "Q3",
                    "end_event:wikidata": "Q999",
                },
                "members": [],
            },
            {
                "type": "relation",
                "id": 102,
                "tags": {
                    "boundary": "administrative",
                    "admin_level": "2",
                    "name": "Late Roman Empire",
                    "wikidata": "Q1",
                    "successor:wikidata": "Q3",
                },
                "members": [],
            },
            {
                "type": "relation",
                "id": 200,
                "tags": {
                    "boundary": "administrative",
                    "admin_level": "2",
                    "name": "Roman Republic",
                    "wikidata": "Q2",
                    "successor:wikidata": "Q1",
                },
                "members": [],
            },
            {
                "type": "relation",
                "id": 300,
                "tags": {
                    "boundary": "administrative",
                    "admin_level": "2",
                    "name": "Byzantine Empire",
                    "wikidata": "Q3",
                    "predecessor:wikidata": "Q1",
                    "successor:wikidata": "Q4",
                },
                "members": [],
            },
            {
                "type": "relation",
                "id": 400,
                "tags": {
                    "boundary": "administrative",
                    "admin_level": "2",
                    "name": "Ottoman Empire",
                    "wikidata": "Q4",
                    "predecessor:wikidata": "Q3",
                },
                "members": [],
            },
            {
                "type": "relation",
                "id": 500,
                "tags": {
                    "boundary": "administrative",
                    "admin_level": "2",
                    "name": "Han Dynasty",
                    "wikidata": "Q5",
                },
                "members": [],
            },
            {
                "type": "relation",
                "id": 600,
                "tags": {
                    "boundary": "administrative",
                    "admin_level": "2",
                    "name": "Ambiguous Empire",
                    "wikidata": "Q6",
                },
                "members": [],
            },
            {
                "type": "relation",
                "id": 601,
                "tags": {
                    "boundary": "administrative",
                    "admin_level": "2",
                    "name": "Ambiguous Empire",
                    "wikidata": "Q7",
                },
                "members": [],
            },
        ],
    }


def test_extract_country_subgraph_expands_bidirectionally_across_linked_relations() -> None:
    result = extract_country_subgraph(
        _fixture_overpass(),
        seed_qid="Q1",
        max_depth=1,
        max_nodes=10,
    )

    assert result["seed"]["wikidata_id"] == "Q1"
    assert result["closure_report"]["truncated"] is False
    assert result["closure_report"]["included_relation_ids"] == [100, 101, 102, 200, 300]
    assert [element["id"] for element in result["reduced_payload"]["elements"]] == [100, 101, 102, 200, 300]


def test_extract_country_subgraph_reports_truncation_and_missing_references() -> None:
    result = extract_country_subgraph(
        _fixture_overpass(),
        seed_qid="Q1",
        max_depth=1,
        max_nodes=4,
    )

    closure_report = result["closure_report"]

    assert closure_report["truncated"] is True
    assert closure_report["truncation_reasons"]
    assert closure_report["missing_wikidata_ids"] == ["Q999"]
    assert closure_report["traversal"]["seed_qid"] == "Q1"
    assert closure_report["traversal"]["max_depth"] == 1
    assert closure_report["traversal"]["max_nodes"] == 4


def test_extract_country_subgraph_raises_for_ambiguous_or_missing_seed_names() -> None:
    with pytest.raises(SeedResolutionError, match="Ambiguous seed"):
        extract_country_subgraph(
            _fixture_overpass(),
            seed_name="Ambiguous Empire",
            max_depth=1,
            max_nodes=10,
        )

    with pytest.raises(SeedResolutionError, match="No seed relation"):
        extract_country_subgraph(
            _fixture_overpass(),
            seed_name="Missing Empire",
            max_depth=1,
            max_nodes=10,
        )


def test_validate_bundle_closure_reports_import_readiness() -> None:
    validation = validate_bundle_closure(
        main_entities=[{"wikidata_id": "Q1"}, {"wikidata_id": "Q2"}],
        relation_entities=[{"wikidata_id": "Q3"}],
        relation_hints=[
            {"source_wikidata_id": "Q1", "target_wikidata_id": "Q2"},
            {"source_wikidata_id": "Q1", "target_wikidata_id": "Q3"},
            {"source_wikidata_id": "Q1", "target_wikidata_id": "Q404"},
        ],
    )

    assert validation["import_ready"] is False
    assert validation["missing_wikidata_ids"] == ["Q404"]
    assert validation["known_wikidata_ids"] == ["Q1", "Q2", "Q3"]


def test_run_extract_subgraph_stage_writes_subset_artifacts_and_manifest(tmp_path) -> None:
    source_path = tmp_path / "global-overpass.json"
    artifact_dir = tmp_path / "subset-artifacts"
    source_path.write_text(__import__("json").dumps(_fixture_overpass()), encoding="utf-8")

    result = run_extract_subgraph_stage(
        run_id="roman-subset",
        artifact_dir=artifact_dir,
        input_path=source_path,
        seed_qid="Q1",
        max_depth=1,
        max_nodes=10,
        raw_shard_size=2,
    )

    manifest = __import__("json").loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    reduced_payload = __import__("json").loads(raw_overpass_path(artifact_dir).read_text(encoding="utf-8"))
    closure_report = __import__("json").loads(subgraph_closure_report_path(artifact_dir).read_text(encoding="utf-8"))

    assert result["status"] == "completed"
    assert [element["id"] for element in reduced_payload["elements"]] == [100, 101, 102, 200, 300]
    assert raw_shard_path(artifact_dir, 1).exists()
    assert raw_shard_path(artifact_dir, 2).exists()
    assert subgraph_seed_path(artifact_dir).exists()
    assert manifest["stages"]["extract_subgraph"]["status"] == "completed"
    assert manifest["summary"]["subgraph_seed_qid"] == "Q1"
    assert manifest["summary"]["subgraph_max_depth"] == 1
    assert closure_report["traversal"]["max_nodes"] == 10


def test_run_extract_subgraph_stage_resume_rejects_parameter_drift(tmp_path) -> None:
    source_path = tmp_path / "global-overpass.json"
    artifact_dir = tmp_path / "subset-artifacts"
    source_path.write_text(__import__("json").dumps(_fixture_overpass()), encoding="utf-8")

    run_extract_subgraph_stage(
        run_id="roman-subset",
        artifact_dir=artifact_dir,
        input_path=source_path,
        seed_qid="Q1",
        max_depth=1,
        max_nodes=10,
        raw_shard_size=2,
    )

    with pytest.raises(RuntimeError, match="--force"):
        run_extract_subgraph_stage(
            run_id="roman-subset",
            artifact_dir=artifact_dir,
            input_path=source_path,
            seed_qid="Q1",
            max_depth=2,
            max_nodes=10,
            raw_shard_size=2,
            resume=True,
        )


def test_run_extract_subgraph_stage_accepts_utf8_bom_input(tmp_path) -> None:
    source_path = tmp_path / "global-overpass-bom.json"
    artifact_dir = tmp_path / "subset-artifacts"
    source_path.write_text(__import__("json").dumps(_fixture_overpass()), encoding="utf-8-sig")

    result = run_extract_subgraph_stage(
        run_id="roman-subset",
        artifact_dir=artifact_dir,
        input_path=source_path,
        seed_qid="Q1",
        max_depth=1,
        max_nodes=10,
    )

    assert result["status"] == "completed"
    assert raw_overpass_path(artifact_dir).exists()
