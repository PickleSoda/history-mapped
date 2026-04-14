import json
import time
from pathlib import Path

import orjson
import pytest

from pipeline.ohm_borders.artifacts import parsed_shard_path, raw_shard_path
from pipeline.ohm_borders.stages import run_build_stage, run_parse_stage


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        for record in records:
            handle.write(orjson.dumps(record) + b"\n")


def test_parse_stage_worker_failure_exits_promptly_with_inflight_workers(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"

    for relation_id in (1, 2, 3):
        _write_jsonl(
            raw_shard_path(artifact_dir, relation_id),
            [{"type": "relation", "id": relation_id, "tags": {"name": f"R{relation_id}"}, "members": []}],
        )

    def fail_fast_parser(elements: list[dict]) -> list[dict]:
        relation_id = int(elements[0]["id"])
        if relation_id == 2:
            raise RuntimeError("parse worker failed")

        # Keep other workers in-flight long enough to catch blocking result loops.
        time.sleep(1.0)
        return [{"relation_id": relation_id, "tags": {"name": f"P{relation_id}"}, "stages": []}]

    started = time.perf_counter()
    with pytest.raises(RuntimeError, match="parse worker failed"):
        run_parse_stage(
            run_id="run-001",
            artifact_dir=artifact_dir,
            parsed_shard_size=10,
            parse_workers=3,
            parser=fail_fast_parser,
        )
    elapsed = time.perf_counter() - started

    assert elapsed < 0.8

    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["stages"]["parse"]["status"] == "failed"


def test_build_stage_worker_failure_exits_promptly_with_inflight_workers(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"

    for relation_id in (1, 2, 3):
        _write_jsonl(
            parsed_shard_path(artifact_dir, relation_id),
            [{"relation_id": relation_id, "tags": {"name": f"P{relation_id}"}, "stages": []}],
        )

    def fail_fast_mapper(record: dict, _: dict) -> dict:
        relation_id = int(record["relation_id"])
        if relation_id == 2:
            raise RuntimeError("build worker failed")

        # Keep other workers in-flight long enough to catch blocking result loops.
        time.sleep(1.0)
        return {"name": record["tags"]["name"], "_ohm_relation_id": str(relation_id)}

    started = time.perf_counter()
    with pytest.raises(RuntimeError, match="build worker failed"):
        run_build_stage(
            run_id="run-001",
            artifact_dir=artifact_dir,
            no_enrich=True,
            build_workers=3,
            mapper=fail_fast_mapper,
        )
    elapsed = time.perf_counter() - started

    assert elapsed < 0.8

    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["stages"]["build"]["status"] == "failed"
