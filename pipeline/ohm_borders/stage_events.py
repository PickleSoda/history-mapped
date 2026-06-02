"""Event extraction and enrichment stage orchestration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipeline.ohm_borders.artifacts import (
    event_candidates_dir,
    event_candidate_shard_path,
    event_enriched_dir,
    event_enriched_shard_path,
    event_final_refs_path,
    event_final_matches_path,
    parsed_dir,
)
from pipeline.ohm_borders.event_extractor import extract_event_refs
from pipeline.ohm_borders.manifest import create_manifest, load_manifest, save_manifest


def run_event_scan_stage(run_id: str, artifact_dir: Path, candidate_shard_size: int = 500) -> dict[str, Any]:
    """Scan parsed border shards and extract event references."""
    parsed_path = parsed_dir(artifact_dir)
    candidates_dir = event_candidates_dir(artifact_dir)
    candidates_dir.mkdir(parents=True, exist_ok=True)

    all_refs: list[dict[str, Any]] = []

    for shard_file in sorted(parsed_path.glob("parsed-*.jsonl")):
        with open(shard_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                polity = json.loads(line)
                all_refs.extend(extract_event_refs(polity))

    # Shard candidates
    shard_index = 1
    for i in range(0, len(all_refs), candidate_shard_size):
        shard_path = event_candidate_shard_path(artifact_dir, shard_index)
        with open(shard_path, "w", encoding="utf-8") as f:
            for ref in all_refs[i : i + candidate_shard_size]:
                f.write(json.dumps(ref, ensure_ascii=False) + "\n")
        shard_index += 1

    manifest_path = artifact_dir / "manifest.json"
    if manifest_path.exists():
        manifest = load_manifest(manifest_path)
    else:
        manifest = create_manifest(run_id=run_id, artifact_dir=artifact_dir)
    manifest["event_stages"]["scan"] = {
        "status": "completed",
        "reference_count": len(all_refs),
        "shard_count": shard_index - 1,
    }
    save_manifest(manifest_path, manifest)

    return {"status": "completed", "reference_count": len(all_refs)}


def run_event_build_stage(run_id: str, artifact_dir: Path) -> dict[str, Any]:
    """Build final event reference and match files."""
    enriched_dir = event_enriched_dir(artifact_dir)
    final_dir = event_final_refs_path(artifact_dir).parent
    final_dir.mkdir(parents=True, exist_ok=True)

    refs_path = event_final_refs_path(artifact_dir)
    matches_path = event_final_matches_path(artifact_dir)

    with open(refs_path, "w", encoding="utf-8") as refs_f, open(matches_path, "w", encoding="utf-8") as matches_f:
        for enriched_file in sorted(enriched_dir.glob("event-enriched-*.json")):
            with open(enriched_file, "r", encoding="utf-8") as f:
                records = json.load(f)

            for record in records:
                refs_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                matches_f.write(
                    json.dumps(
                        {
                            "event_label": record["event_label"],
                            "resolved_wikidata_id": record.get("resolved_wikidata_id"),
                            "match_source": record.get("match_source"),
                            "match_confidence": record.get("match_confidence"),
                        },
                        ensure_ascii=False,
                    ) + "\n"
                )

    manifest_path = artifact_dir / "manifest.json"
    if manifest_path.exists():
        manifest = load_manifest(manifest_path)
    else:
        manifest = create_manifest(run_id=run_id, artifact_dir=artifact_dir)
    manifest["event_stages"]["build"] = {"status": "completed"}
    save_manifest(manifest_path, manifest)

    return {"status": "completed"}