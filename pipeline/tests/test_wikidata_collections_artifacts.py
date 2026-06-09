from pathlib import Path

from pipeline.wikidata.collections.artifacts import (
    collection_artifact_dir,
    entities_final_path,
    reports_dir,
    manifest_path,
)


def test_collection_artifact_dir_is_deterministic(tmp_path: Path) -> None:
    root = collection_artifact_dir("egypt-test", base_dir=tmp_path)
    assert root == tmp_path / "egypt-test"


def test_collection_artifact_dir_uses_default_root(tmp_path: Path) -> None:
    import pipeline.wikidata.collections.artifacts as artifacts
    original = artifacts.DEFAULT_COLLECTION_ROOT
    try:
        artifacts.DEFAULT_COLLECTION_ROOT = tmp_path / "default_root"
        root = collection_artifact_dir("egypt-test")
        assert root == tmp_path / "default_root" / "egypt-test"
    finally:
        artifacts.DEFAULT_COLLECTION_ROOT = original


def test_entities_final_path_is_deterministic(tmp_path: Path) -> None:
    root = collection_artifact_dir("egypt-test", base_dir=tmp_path)
    assert entities_final_path(root) == root / "entities_final" / "egypt_collection.jsonl"


def test_reports_dir_is_deterministic(tmp_path: Path) -> None:
    root = collection_artifact_dir("egypt-test", base_dir=tmp_path)
    assert reports_dir(root) == root / "reports"


def test_manifest_path_is_deterministic(tmp_path: Path) -> None:
    root = collection_artifact_dir("egypt-test", base_dir=tmp_path)
    assert manifest_path(root) == root / "manifest.json"
