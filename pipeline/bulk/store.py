"""On-disk state for bulk slices: QID lists, claims across slices, parts."""
from __future__ import annotations

import fcntl
import gzip
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

REPO = Path(__file__).resolve().parents[2]
ROOT = Path(os.environ.get("BULK_ROOT", REPO / "output" / "bulk"))
API_DROP = REPO / "api" / "storage" / "app" / "pipeline" / "bulk"
PART_SIZE = 2000


@contextmanager
def locked(name: str) -> Iterator[None]:
    ROOT.mkdir(parents=True, exist_ok=True)
    with open(ROOT / f"{name}.lock", "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


class SliceStore:
    def __init__(self, slice_id: str):
        self.id = slice_id
        self.dir = ROOT / slice_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.dir / "state.json"

    # ── state ───────────────────────────────────────────────────────────
    def state(self) -> dict[str, Any]:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text())
        return {"shards_done": [], "shards_failed": []}

    def save(self, state: dict[str, Any]) -> None:
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=1, sort_keys=True))
        tmp.replace(self.state_path)

    # ── QIDs ────────────────────────────────────────────────────────────
    @property
    def listed_path(self) -> Path:
        return self.dir / "listed.tsv"

    @property
    def queue_path(self) -> Path:
        return self.dir / "queue.tsv"

    def add_listed(self, rows: list[tuple[str, int]], shard: str) -> None:
        with open(self.listed_path, "a") as fh:
            for qid, sl in rows:
                fh.write(f"{qid}\t{sl}\t{shard}\n")

    def listed(self) -> dict[str, int]:
        out: dict[str, int] = {}
        if self.listed_path.exists():
            for line in self.listed_path.read_text().splitlines():
                qid, sl, *_ = line.split("\t")
                out[qid] = max(out.get(qid, 0), int(sl))
        return out

    def queue(self) -> list[tuple[str, int]]:
        if not self.queue_path.exists():
            return []
        rows = []
        for line in self.queue_path.read_text().splitlines():
            qid, sl = line.split("\t")[:2]
            rows.append((qid, int(sl)))
        return rows

    # ── parts ───────────────────────────────────────────────────────────
    def raw_path(self, n: int) -> Path:
        return self.dir / "raw" / f"part-{n:04d}.jsonl.gz"

    def part_path(self, n: int) -> Path:
        return self.dir / "parts" / f"part-{n:04d}.jsonl"

    def write_raw(self, n: int, raws: list[dict]) -> None:
        path = self.raw_path(n)
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, "wt") as fh:
            for r in raws:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    def read_raw(self, n: int) -> list[dict]:
        with gzip.open(self.raw_path(n), "rt") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    # Per-part metadata lives in its own files, so the fetcher (meta) and
    # the importer (import) never rewrite each other's state.
    def meta_path(self, n: int) -> Path:
        return self.dir / "parts" / f"part-{n:04d}.meta.json"

    def import_path(self, n: int) -> Path:
        return self.dir / "parts" / f"part-{n:04d}.import.json"

    def read_json(self, path: Path) -> dict[str, Any] | None:
        return json.loads(path.read_text()) if path.exists() else None

    def write_json(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1, sort_keys=True))
        tmp.replace(path)

    def part_numbers(self) -> list[int]:
        return sorted(int(p.name[5:9]) for p in (self.dir / "parts").glob("part-*.meta.json"))

    def write_part(self, n: int, records: list[dict]) -> Path:
        path = self.part_path(n)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as fh:
            for r in records:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        return path


def claims() -> dict[str, str]:
    path = ROOT / "claims.tsv"
    out: dict[str, str] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            qid, sid = line.split("\t")[:2]
            out.setdefault(qid, sid)
    return out


def add_claims(qids: list[str], slice_id: str) -> None:
    with open(ROOT / "claims.tsv", "a") as fh:
        for q in qids:
            fh.write(f"{q}\t{slice_id}\n")


def db_qids() -> set[str]:
    import psycopg

    from pipeline.local_db import dsn

    with psycopg.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute("select wikidata_id from entities where wikidata_id is not null")
        return {r[0] for r in cur.fetchall()}
