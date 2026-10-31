"""Write OHM-link records as JSONL (part files, the merged file) plus a run manifest; all writes are atomic."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _write_lines_atomic(path: Path, lines: Iterable[str]) -> int:
    """Stream lines to `<path>.tmp`, fsync, then rename over `path`. Returns the number of lines."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    count = 0

    try:
        with temp_path.open("w", encoding="utf-8") as handle:
            for line in lines:
                handle.write(line)
                count += 1
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise

    os.replace(temp_path, path)
    return count


def _jsonl_lines(records: Iterable[dict[str, Any]]) -> Iterator[str]:
    for record in records:
        yield json.dumps(record, ensure_ascii=False) + "\n"


def write_part(records: Iterable[dict[str, Any]], path: str | Path) -> int:
    """Atomically write one source's records as JSONL. Returns the number of records."""
    return _write_lines_atomic(Path(path), _jsonl_lines(records))


def read_jsonl(path: str | Path) -> Iterator[dict[str, Any]]:
    """Yield the records of a JSONL file, one per non-empty line."""
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def write_records(records: Iterable[dict[str, Any]], path: str | Path) -> dict[str, int]:
    """Atomically write one record per line, keeping the first record for each (osm_type, osm_id)."""
    seen: set[tuple[str, int]] = set()
    duplicates = 0

    def first_of_each() -> Iterator[dict[str, Any]]:
        nonlocal duplicates
        for record in records:
            key = (record["osm_type"], record["osm_id"])
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            yield record

    written = _write_lines_atomic(Path(path), _jsonl_lines(first_of_each()))
    return {"records": written, "duplicates": duplicates}


def write_manifest(path: str | Path, run_id: str, counts: dict[str, int]) -> None:
    """Atomically write the run manifest (run id, generation time, counts) as JSON."""
    manifest = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "counts": counts,
    }
    _write_lines_atomic(Path(path), [json.dumps(manifest, indent=2) + "\n"])
