from pathlib import Path

DEFAULT_COLLECTION_ROOT = Path("output") / "wikidata_collections"


def collection_artifact_dir(run_id: str, base_dir: Path | None = None) -> Path:
    root = base_dir or DEFAULT_COLLECTION_ROOT
    return root / run_id


def entities_final_path(artifact_dir: Path) -> Path:
    return artifact_dir / "entities_final" / "egypt_collection.jsonl"


def reports_dir(artifact_dir: Path) -> Path:
    return artifact_dir / "reports"


def included_report_path(artifact_dir: Path) -> Path:
    return reports_dir(artifact_dir) / "included.jsonl"


def excluded_report_path(artifact_dir: Path) -> Path:
    return reports_dir(artifact_dir) / "excluded.jsonl"


def manifest_path(artifact_dir: Path) -> Path:
    return artifact_dir / "manifest.json"


def ensure_dirs(artifact_dir: Path) -> None:
    entities_final_path(artifact_dir).parent.mkdir(parents=True, exist_ok=True)
    reports_dir(artifact_dir).mkdir(parents=True, exist_ok=True)
