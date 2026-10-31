"""Write OHM-link records as JSONL plus a run manifest."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_records(records: Iterable[dict[str, Any]], path: str | Path) -> dict[str, int]:
    """Write one record per line, keeping the first record for each (osm_type, osm_id)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    seen: set[tuple[str, int]] = set()
    written = 0
    duplicates = 0

    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            key = (record["osm_type"], record["osm_id"])
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1

    return {"records": written, "duplicates": duplicates}


def write_manifest(path: str | Path, run_id: str, counts: dict[str, int]) -> None:
    """Write the run manifest (run id, generation time, counts) as JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    manifest = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "counts": counts,
    }
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
