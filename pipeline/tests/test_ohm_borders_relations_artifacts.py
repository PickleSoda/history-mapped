from pathlib import Path

from pipeline.ohm_borders.artifacts import (
    artifact_dir_for_run,
    relation_candidates_dir,
    relation_enriched_dir,
    relation_built_dir,
    relation_final_dir,
    relation_entities_final_path,
    relation_hints_final_path,
)
from pipeline.ohm_borders.manifest import create_manifest


def test_relation_artifact_paths_are_deterministic_from_run_id(tmp_path: Path) -> None:
    artifact_root = tmp_path / "output" / "ohm_borders"
    artifact_dir = artifact_dir_for_run("20260422-120000", artifact_root)

    assert relation_candidates_dir(artifact_dir) == artifact_dir / "relations_candidates"
    assert relation_enriched_dir(artifact_dir) == artifact_dir / "relations_enriched"
    assert relation_built_dir(artifact_dir) == artifact_dir / "relations_built"
    assert relation_final_dir(artifact_dir) == artifact_dir / "relations_final"



def test_relation_final_output_paths_are_deterministic() -> None:
    artifact_dir = Path("output/ohm_borders/20260422-120000")

    assert relation_entities_final_path(artifact_dir) == artifact_dir / "relations_final" / "ohm_relation_entities.jsonl"
    assert relation_hints_final_path(artifact_dir) == artifact_dir / "relations_final" / "ohm_relation_hints.jsonl"



def test_create_manifest_includes_relation_stages_as_sibling_section(tmp_path: Path) -> None:
    artifact_dir = artifact_dir_for_run("20260422-120000", tmp_path / "output" / "ohm_borders")

    manifest = create_manifest(
        run_id="20260422-120000",
        artifact_dir=artifact_dir,
        options={"parse_workers": 4, "parsed_shard_size": 100},
    )

    assert list(manifest.keys()) == ["run_id", "artifact_dir", "options", "summary", "stages", "relation_stages"]
    assert list(manifest["stages"].keys()) == ["fetch", "parse", "enrich", "build"]
    assert list(manifest["relation_stages"].keys()) == ["scan", "enrich", "build"]

    for stage_name in ("scan", "enrich", "build"):
        assert manifest["relation_stages"][stage_name] == {
            "status": "pending",
            "inputs": [],
            "outputs": [],
            "started_at": None,
            "finished_at": None,
            "failed_shards": [],
        }
