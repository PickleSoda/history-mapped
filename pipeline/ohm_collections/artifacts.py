from __future__ import annotations

from pathlib import Path


def collection_artifact_paths(output_root: str | Path) -> dict[str, Path]:
    root = Path(output_root)
    return {
        "root": root,
        "reports_dir": root / "reports",
        "included_report": root / "reports" / "included.jsonl",
        "excluded_report": root / "reports" / "excluded.jsonl",
        "borders_dir": root / "borders_final",
        "borders_file": root / "borders_final" / "ohm_borders.jsonl",
        "entities_dir": root / "entities_final",
        "entities_file": root / "entities_final" / "egypt_collection.jsonl",
        "relations_dir": root / "relations_final",
        "manifest": root / "manifest.json",
    }


def ensure_collection_artifact_dirs(output_root: str | Path) -> dict[str, Path]:
    paths = collection_artifact_paths(output_root)
    for key in ("root", "reports_dir", "borders_dir", "entities_dir", "relations_dir"):
        paths[key].mkdir(parents=True, exist_ok=True)
    return paths