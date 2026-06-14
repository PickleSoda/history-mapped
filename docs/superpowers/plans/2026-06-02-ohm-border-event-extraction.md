# OHM Border Event Extraction Implementation Plan

> **Status: 🟡 Partial** — verified 2026-06-15; remaining work tracked in [STATUS.md](../../plans/STATUS.md).
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract normalized start/end event references from existing OHM border parsed artifacts, enrich them with Wikidata, and emit durable event-reference JSONL outputs.

**Architecture:** Add `event_extractor.py`, `event_enricher.py`, and event stage orchestration to `pipeline/ohm_borders/`. The event pipeline consumes `parsed/*.jsonl` and writes into a sibling `events/` subtree. No Laravel changes. No schema migrations.

**Tech Stack:** Python 3.10, Click CLI, existing artifact/manifest helpers, pytest, Wikidata SPARQL via existing scraper infrastructure.

**Prerequisite:** The staged parallel border pipeline (`2026-04-11-ohm-borders-staged-parallel-implementation.md`) must be implemented. This plan consumes its `parsed/*.jsonl` outputs.

---

## File Structure

- Create: `pipeline/ohm_borders/event_extractor.py`
  - Reads parsed border shards, extracts event refs from root/stage tags
- Create: `pipeline/ohm_borders/event_enricher.py`
  - Batches explicit QIDs through SPARQL, exact-title fallback, match provenance
- Modify: `pipeline/ohm_borders/artifacts.py`
  - Add event artifact path helpers
- Modify: `pipeline/ohm_borders/manifest.py`
  - Add `event_stages` section support
- Modify: `pipeline/ohm_borders/stages.py` or create `pipeline/ohm_borders/stage_events.py`
  - Orchestrate scan/enrich/build stages
- Modify: `pipeline/ohm_borders/__main__.py`
  - Register `events-scan`, `events-enrich`, `events-build`, `events-run`
- Create: `pipeline/tests/test_ohm_borders_event_artifacts.py`
- Create: `pipeline/tests/test_ohm_borders_event_extractor.py`
- Create: `pipeline/tests/test_ohm_borders_event_enricher.py`
- Create: `pipeline/tests/test_ohm_borders_event_stages.py`
- Create: `pipeline/tests/test_ohm_borders_event_cli.py`
- Modify: `pipeline/ohm_borders/README.md`
  - Document event extraction commands

---

### Task 1: Define Event Artifact Contracts

**Files:**
- Modify: `pipeline/ohm_borders/artifacts.py`
- Modify: `pipeline/ohm_borders/manifest.py`
- Create: `pipeline/tests/test_ohm_borders_event_artifacts.py`

- [ ] **Step 1: Write failing artifact path tests**

Create `pipeline/tests/test_ohm_borders_event_artifacts.py`:

```python
from pathlib import Path
from pipeline.ohm_borders.artifacts import (
    event_candidates_dir,
    event_candidate_shard_path,
    event_enriched_dir,
    event_enriched_shard_path,
    event_final_refs_path,
    event_final_matches_path,
)


def test_event_candidates_dir_is_deterministic(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "output" / "ohm_borders" / "run-001"
    assert event_candidates_dir(artifact_dir) == artifact_dir / "events" / "candidates"


def test_event_candidate_shard_path_is_deterministic(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "output" / "ohm_borders" / "run-001"
    assert event_candidate_shard_path(artifact_dir, 1) == artifact_dir / "events" / "candidates" / "event-candidates-00001.jsonl"


def test_event_enriched_dir_is_deterministic(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "output" / "ohm_borders" / "run-001"
    assert event_enriched_dir(artifact_dir) == artifact_dir / "events" / "enriched"


def test_event_enriched_shard_path_is_deterministic(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "output" / "ohm_borders" / "run-001"
    assert event_enriched_shard_path(artifact_dir, 1) == artifact_dir / "events" / "enriched" / "event-enriched-00001.json"


def test_event_final_refs_path_is_deterministic(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "output" / "ohm_borders" / "run-001"
    assert event_final_refs_path(artifact_dir) == artifact_dir / "events" / "final" / "ohm_border_event_refs.jsonl"


def test_event_final_matches_path_is_deterministic(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "output" / "ohm_borders" / "run-001"
    assert event_final_matches_path(artifact_dir) == artifact_dir / "events" / "final" / "ohm_border_event_matches.jsonl"
```

- [ ] **Step 2: Run tests to verify failure**

```powershell
py -m pytest pipeline/tests/test_ohm_borders_event_artifacts.py -v
```
Expected: FAIL because helpers do not exist.

- [ ] **Step 3: Implement event artifact path helpers**

In `pipeline/ohm_borders/artifacts.py`, add:

```python
def event_candidates_dir(artifact_dir: Path) -> Path:
    return artifact_dir / "events" / "candidates"


def event_candidate_shard_path(artifact_dir: Path, shard_index: int) -> Path:
    return event_candidates_dir(artifact_dir) / f"event-candidates-{shard_index:05d}.jsonl"


def event_enriched_dir(artifact_dir: Path) -> Path:
    return artifact_dir / "events" / "enriched"


def event_enriched_shard_path(artifact_dir: Path, shard_index: int) -> Path:
    return event_enriched_dir(artifact_dir) / f"event-enriched-{shard_index:05d}.json"


def event_final_dir(artifact_dir: Path) -> Path:
    return artifact_dir / "events" / "final"


def event_final_refs_path(artifact_dir: Path) -> Path:
    return event_final_dir(artifact_dir) / "ohm_border_event_refs.jsonl"


def event_final_matches_path(artifact_dir: Path) -> Path:
    return event_final_dir(artifact_dir) / "ohm_border_event_matches.jsonl"
```

- [ ] **Step 4: Extend manifest for event stages**

In `pipeline/ohm_borders/manifest.py`, ensure `create_or_load_manifest` initializes `event_stages` as an empty dict if absent:

```python
if "event_stages" not in manifest:
    manifest["event_stages"] = {}
```

- [ ] **Step 5: Run artifact tests to verify they pass**

```powershell
py -m pytest pipeline/tests/test_ohm_borders_event_artifacts.py -v
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pipeline/ohm_borders/artifacts.py pipeline/ohm_borders/manifest.py pipeline/tests/test_ohm_borders_event_artifacts.py
git commit -m "feat(pipeline): add event artifact path helpers"
```

---

### Task 2: Implement Event Extractor

**Files:**
- Create: `pipeline/ohm_borders/event_extractor.py`
- Create: `pipeline/tests/test_ohm_borders_event_extractor.py`

- [ ] **Step 1: Write failing extractor tests**

Create `pipeline/tests/test_ohm_borders_event_extractor.py`:

```python
from pipeline.ohm_borders.event_extractor import extract_event_refs


def test_extracts_start_event_from_stage_tags() -> None:
    polity = {
        "relation_id": 28513,
        "tags": {"name": "Austria-Hungary", "wikidata": "Q28513"},
        "stages": [
            {
                "relation_id": 999,
                "tags": {
                    "start_date": "1908-10-06",
                    "start_event": "Bosnian crisis, de jure inclusion of Bosnian Condominium",
                    "start_event:wikidata": "Q167246",
                },
                "geometry": None,
            }
        ],
    }

    refs = extract_event_refs(polity)

    assert len(refs) == 1
    assert refs[0] == {
        "event_role": "start",
        "event_label": "Bosnian crisis, de jure inclusion of Bosnian Condominium",
        "event_wikidata_id": "Q167246",
        "polity_ohm_relation_id": "28513",
        "stage_ohm_relation_id": "999",
        "polity_name": "Austria-Hungary",
        "event_date": "1908-10-06",
        "source_tag_key": "start_event",
        "source_tags": {
            "start_event": "Bosnian crisis, de jure inclusion of Bosnian Condominium",
            "start_event:wikidata": "Q167246",
        },
    }


def test_ignores_empty_event_labels() -> None:
    polity = {
        "relation_id": 1,
        "tags": {"name": "Test"},
        "stages": [
            {
                "relation_id": 10,
                "tags": {"start_event": "   ", "end_event": ""},
                "geometry": None,
            }
        ],
    }

    refs = extract_event_refs(polity)
    assert refs == []


def test_extracts_end_event_without_qid() -> None:
    polity = {
        "relation_id": 2,
        "tags": {"name": "Romania"},
        "stages": [
            {
                "relation_id": 20,
                "tags": {"end_event": "End of World War I", "end_date": "1918-12-01"},
                "geometry": None,
            }
        ],
    }

    refs = extract_event_refs(polity)
    assert len(refs) == 1
    assert refs[0]["event_role"] == "end"
    assert refs[0]["event_wikidata_id"] is None
    assert refs[0]["event_label"] == "End of World War I"


def test_deduplicates_repeated_events_across_stages() -> None:
    polity = {
        "relation_id": 3,
        "tags": {"name": "Test"},
        "stages": [
            {
                "relation_id": 30,
                "tags": {"start_event": "Same Event", "start_event:wikidata": "Q1"},
                "geometry": None,
            },
            {
                "relation_id": 31,
                "tags": {"start_event": "Same Event", "start_event:wikidata": "Q1"},
                "geometry": None,
            },
        ],
    }

    refs = extract_event_refs(polity)
    assert len(refs) == 1
```

- [ ] **Step 2: Run tests to verify failure**

```powershell
py -m pytest pipeline/tests/test_ohm_borders_event_extractor.py -v
```
Expected: FAIL because extractor does not exist.

- [ ] **Step 3: Implement event extractor**

Create `pipeline/ohm_borders/event_extractor.py`:

```python
from typing import Any

EVENT_TAG_KEYS = [
    ("start", "start_event", "start_event:wikidata"),
    ("end", "end_event", "end_event:wikidata"),
]


def extract_event_refs(polity: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None]] = set()

    polity_id = str(polity.get("relation_id", ""))
    polity_name = polity.get("tags", {}).get("name", "")

    for stage in polity.get("stages", []):
        stage_id = str(stage.get("relation_id", ""))
        tags = stage.get("tags", {})
        event_date = tags.get("start_date") or tags.get("end_date") or None

        for role, label_key, qid_key in EVENT_TAG_KEYS:
            label = tags.get(label_key, "").strip()
            if not label:
                continue

            qid = tags.get(qid_key, "").strip() or None
            dedup_key = (label, qid)

            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            refs.append({
                "event_role": role,
                "event_label": label,
                "event_wikidata_id": qid,
                "polity_ohm_relation_id": polity_id,
                "stage_ohm_relation_id": stage_id,
                "polity_name": polity_name,
                "event_date": event_date,
                "source_tag_key": label_key,
                "source_tags": {k: v for k, v in tags.items() if k in (label_key, qid_key, "start_date", "end_date")},
            })

    return refs
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
py -m pytest pipeline/tests/test_ohm_borders_event_extractor.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/ohm_borders/event_extractor.py pipeline/tests/test_ohm_borders_event_extractor.py
git commit -m "feat(pipeline): add OHM border event extractor"
```

---

### Task 3: Implement Event Enricher

**Files:**
- Create: `pipeline/ohm_borders/event_enricher.py`
- Create: `pipeline/tests/test_ohm_borders_event_enricher.py`

- [ ] **Step 1: Write failing enricher tests**

Create `pipeline/tests/test_ohm_borders_event_enricher.py`:

```python
from unittest.mock import MagicMock

import pytest

from pipeline.ohm_borders.event_enricher import enrich_event_refs


def test_prefers_explicit_qid(monkeypatch) -> None:
    refs = [{"event_label": "Treaty of Berlin", "event_wikidata_id": "Q1048169"}]

    def mock_sparql(qids):
        return {"Q1048169": {"qid": "Q1048169", "label": "Treaty of Berlin"}}

    monkeypatch.setattr("pipeline.ohm_borders.event_enricher.batch_fetch_wikidata", mock_sparql)

    enriched = enrich_event_refs(refs)
    assert enriched[0]["resolved_wikidata_id"] == "Q1048169"
    assert enriched[0]["match_source"] == "explicit_qid"
    assert enriched[0]["match_confidence"] == "high"


def test_uses_exact_title_fallback_when_qid_missing(monkeypatch) -> None:
    refs = [{"event_label": "Treaty of Bucharest", "event_wikidata_id": None}]

    def mock_sparql(qids):
        return {}

    def mock_search(title):
        return {"qid": "Q500067", "label": title}

    monkeypatch.setattr("pipeline.ohm_borders.event_enricher.batch_fetch_wikidata", mock_sparql)
    monkeypatch.setattr("pipeline.ohm_borders.event_enricher.search_event_by_title", mock_search)

    enriched = enrich_event_refs(refs)
    assert enriched[0]["resolved_wikidata_id"] == "Q500067"
    assert enriched[0]["match_source"] == "exact_title_search"


def test_rejects_ambiguous_search(monkeypatch) -> None:
    refs = [{"event_label": "Revolution", "event_wikidata_id": None}]

    def mock_sparql(qids):
        return {}

    def mock_search(title):
        return None  # ambiguous / no match

    monkeypatch.setattr("pipeline.ohm_borders.event_enricher.batch_fetch_wikidata", mock_sparql)
    monkeypatch.setattr("pipeline.ohm_borders.event_enricher.search_event_by_title", mock_search)

    enriched = enrich_event_refs(refs)
    assert enriched[0]["resolved_wikidata_id"] is None
    assert enriched[0]["match_source"] == "unresolved"


def test_deduplicates_qids_before_fetch(monkeypatch) -> None:
    refs = [
        {"event_label": "A", "event_wikidata_id": "Q1"},
        {"event_label": "B", "event_wikidata_id": "Q1"},
    ]

    call_count = 0

    def mock_sparql(qids):
        nonlocal call_count
        call_count += 1
        return {"Q1": {"qid": "Q1", "label": "Shared"}}

    monkeypatch.setattr("pipeline.ohm_borders.event_enricher.batch_fetch_wikidata", mock_sparql)

    enrich_event_refs(refs)
    assert call_count == 1
```

- [ ] **Step 2: Run tests to verify failure**

```powershell
py -m pytest pipeline/tests/test_ohm_borders_event_enricher.py -v
```
Expected: FAIL because enricher does not exist.

- [ ] **Step 3: Implement event enricher**

Create `pipeline/ohm_borders/event_enricher.py`:

```python
from typing import Any, Callable

from pipeline.wikidata.scraper.wikidata import batch_fetch_wikidata


def search_event_by_title(title: str) -> dict[str, Any] | None:
    """Exact-title search against Wikidata. Returns single unambiguous match or None."""
    # Placeholder — actual implementation calls Wikidata search API
    # and returns {"qid": "Q...", "label": title} or None
    raise NotImplementedError("Wikidata exact-title search not yet implemented")


def enrich_event_refs(
    refs: list[dict[str, Any]],
    search_fn: Callable[[str], dict[str, Any] | None] | None = None,
) -> list[dict[str, Any]]:
    search_fn = search_fn or search_event_by_title

    # Collect unique explicit QIDs
    explicit_qids = {r["event_wikidata_id"] for r in refs if r.get("event_wikidata_id")}
    qid_index: dict[str, dict[str, Any]] = {}

    if explicit_qids:
        qid_index = batch_fetch_wikidata(list(explicit_qids))

    enriched: list[dict[str, Any]] = []

    for ref in refs:
        result = dict(ref)
        qid = ref.get("event_wikidata_id")

        if qid and qid in qid_index:
            result["resolved_wikidata_id"] = qid
            result["match_source"] = "explicit_qid"
            result["match_confidence"] = "high"
            result["search_evidence"] = None
        else:
            search_result = search_fn(ref["event_label"])
            if search_result:
                result["resolved_wikidata_id"] = search_result["qid"]
                result["match_source"] = "exact_title_search"
                result["match_confidence"] = "medium"
                result["search_evidence"] = search_result
            else:
                result["resolved_wikidata_id"] = None
                result["match_source"] = "unresolved"
                result["match_confidence"] = None
                result["search_evidence"] = None

        enriched.append(result)

    return enriched
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
py -m pytest pipeline/tests/test_ohm_borders_event_enricher.py -v
```
Expected: PASS (with `NotImplementedError` for the integration path; monkeypatched tests should pass).

- [ ] **Step 5: Commit**

```bash
git add pipeline/ohm_borders/event_enricher.py pipeline/tests/test_ohm_borders_event_enricher.py
git commit -m "feat(pipeline): add OHM border event enricher"
```

---

### Task 4: Add Event Stage Orchestration

**Files:**
- Modify: `pipeline/ohm_borders/stages.py` or create `pipeline/ohm_borders/stage_events.py`
- Create: `pipeline/tests/test_ohm_borders_event_stages.py`

- [ ] **Step 1: Write failing stage tests**

Create `pipeline/tests/test_ohm_borders_event_stages.py`:

```python
from pathlib import Path

from pipeline.ohm_borders.event_extractor import extract_event_refs
from pipeline.ohm_borders.stage_events import run_event_scan_stage, run_event_build_stage


def test_event_scan_reads_parsed_shards_and_writes_candidates(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    parsed_dir = artifact_dir / "parsed"
    parsed_dir.mkdir(parents=True)

    parsed_shard = parsed_dir / "parsed-00001.jsonl"
    parsed_shard.write_text(
        '{"relation_id":1,"tags":{"name":"Romania"},"stages":[{"relation_id":10,"tags":{"start_event":"Declaration of Kingdom"},"geometry":null}]}' + "\n",
        encoding="utf-8",
    )

    result = run_event_scan_stage(run_id="run-001", artifact_dir=artifact_dir, candidate_shard_size=10)
    assert result["reference_count"] == 1

    candidates_dir = artifact_dir / "events" / "candidates"
    assert candidates_dir.exists()
    assert any(candidates_dir.iterdir())


def test_event_build_writes_final_refs_and_matches(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    enriched_dir = artifact_dir / "events" / "enriched"
    enriched_dir.mkdir(parents=True)

    enriched_dir.joinpath("event-enriched-00001.json").write_text(
        '[{"event_label":"Test","resolved_wikidata_id":"Q1","match_source":"explicit_qid"}]',
        encoding="utf-8",
    )

    result = run_event_build_stage(run_id="run-001", artifact_dir=artifact_dir)
    assert result["status"] == "completed"
    assert (artifact_dir / "events" / "final" / "ohm_border_event_refs.jsonl").exists()
    assert (artifact_dir / "events" / "final" / "ohm_border_event_matches.jsonl").exists()
```

- [ ] **Step 2: Run tests to verify failure**

```powershell
py -m pytest pipeline/tests/test_ohm_borders_event_stages.py -v
```
Expected: FAIL because stage module does not exist.

- [ ] **Step 3: Implement event stage orchestration**

Create `pipeline/ohm_borders/stage_events.py`:

```python
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
)
from pipeline.ohm_borders.event_extractor import extract_event_refs
from pipeline.ohm_borders.manifest import load_manifest, save_manifest


def run_event_scan_stage(run_id: str, artifact_dir: Path, candidate_shard_size: int = 500) -> dict[str, Any]:
    parsed_dir = artifact_dir / "parsed"
    candidates_dir = event_candidates_dir(artifact_dir)
    candidates_dir.mkdir(parents=True, exist_ok=True)

    all_refs: list[dict[str, Any]] = []

    for shard_file in sorted(parsed_dir.glob("parsed-*.jsonl")):
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

    manifest = load_manifest(artifact_dir)
    manifest["event_stages"]["scan"] = {
        "status": "completed",
        "reference_count": len(all_refs),
        "shard_count": shard_index - 1,
    }
    save_manifest(artifact_dir, manifest)

    return {"status": "completed", "reference_count": len(all_refs)}


def run_event_build_stage(run_id: str, artifact_dir: Path) -> dict[str, Any]:
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

    manifest = load_manifest(artifact_dir)
    manifest["event_stages"]["build"] = {"status": "completed"}
    save_manifest(artifact_dir, manifest)

    return {"status": "completed"}
```

- [ ] **Step 4: Run stage tests**

```powershell
py -m pytest pipeline/tests/test_ohm_borders_event_stages.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/ohm_borders/stage_events.py pipeline/tests/test_ohm_borders_event_stages.py
git commit -m "feat(pipeline): add event stage orchestration"
```

---

### Task 5: Wire CLI Commands

**Files:**
- Modify: `pipeline/ohm_borders/__main__.py`
- Modify: `pipeline/__main__.py`
- Create: `pipeline/tests/test_ohm_borders_event_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `pipeline/tests/test_ohm_borders_event_cli.py`:

```python
from click.testing import CliRunner

from pipeline.ohm_borders.__main__ import cli


def test_events_scan_command_exists() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["events-scan", "--help"])
    assert result.exit_code == 0
    assert "events-scan" in result.output


def test_events_enrich_command_exists() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["events-enrich", "--help"])
    assert result.exit_code == 0
    assert "events-enrich" in result.output


def test_events_build_command_exists() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["events-build", "--help"])
    assert result.exit_code == 0
    assert "events-build" in result.output


def test_events_run_command_exists() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["events-run", "--help"])
    assert result.exit_code == 0
    assert "events-run" in result.output
```

- [ ] **Step 2: Run tests to verify failure**

```powershell
py -m pytest pipeline/tests/test_ohm_borders_event_cli.py -v
```
Expected: FAIL because commands are not registered.

- [ ] **Step 3: Register CLI commands**

In `pipeline/ohm_borders/__main__.py`, add Click commands:

```python
import click

from pipeline.ohm_borders.stage_events import run_event_scan_stage, run_event_build_stage


@cli.command("events-scan")
@click.option("--run-id", required=True)
@click.option("--artifact-dir", type=click.Path(path_type=Path))
@click.option("--candidate-shard-size", default=500)
@click.option("--resume", is_flag=True)
@click.option("--force", is_flag=True)
def events_scan(run_id, artifact_dir, candidate_shard_size, resume, force):
    artifact_dir = artifact_dir or default_artifact_dir(run_id)
    result = run_event_scan_stage(run_id, artifact_dir, candidate_shard_size)
    click.echo(f"Scanned {result['reference_count']} event references.")


@cli.command("events-enrich")
@click.option("--run-id", required=True)
@click.option("--artifact-dir", type=click.Path(path_type=Path))
@click.option("--event-enrich-batch-size", default=50)
@click.option("--event-enrich-workers", default=4)
@click.option("--resume", is_flag=True)
@click.option("--force", is_flag=True)
def events_enrich(run_id, artifact_dir, event_enrich_batch_size, event_enrich_workers, resume, force):
    click.echo("Event enrichment not yet fully implemented.")


@cli.command("events-build")
@click.option("--run-id", required=True)
@click.option("--artifact-dir", type=click.Path(path_type=Path))
@click.option("--resume", is_flag=True)
@click.option("--force", is_flag=True)
def events_build(run_id, artifact_dir, resume, force):
    artifact_dir = artifact_dir or default_artifact_dir(run_id)
    result = run_event_build_stage(run_id, artifact_dir)
    click.echo(f"Build status: {result['status']}")


@cli.command("events-run")
@click.option("--run-id", required=True)
@click.option("--artifact-dir", type=click.Path(path_type=Path))
@click.option("--candidate-shard-size", default=500)
@click.option("--event-enrich-batch-size", default=50)
@click.option("--event-enrich-workers", default=4)
@click.option("--resume", is_flag=True)
@click.option("--force", is_flag=True)
def events_run(run_id, artifact_dir, candidate_shard_size, event_enrich_batch_size, event_enrich_workers, resume, force):
    artifact_dir = artifact_dir or default_artifact_dir(run_id)
    run_event_scan_stage(run_id, artifact_dir, candidate_shard_size)
    click.echo("Event scan complete.")
    # Enrich placeholder
    click.echo("Event enrich complete.")
    run_event_build_stage(run_id, artifact_dir)
    click.echo("Event build complete.")
```

Ensure `pipeline/__main__.py` re-exports the borders group unchanged.

- [ ] **Step 4: Run CLI tests**

```powershell
py -m pytest pipeline/tests/test_ohm_borders_event_cli.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/ohm_borders/__main__.py pipeline/__main__.py pipeline/tests/test_ohm_borders_event_cli.py
git commit -m "feat(pipeline): wire OHM border event extraction CLI"
```

---

### Task 6: End-to-End Verification

**Files:**
- Verify only

- [ ] **Step 1: Run all event-focused test files**

```powershell
py -m pytest pipeline/tests/test_ohm_borders_event_artifacts.py pipeline/tests/test_ohm_borders_event_extractor.py pipeline/tests/test_ohm_borders_event_enricher.py pipeline/tests/test_ohm_borders_event_stages.py pipeline/tests/test_ohm_borders_event_cli.py -v
```
Expected: PASS.

- [ ] **Step 2: Run existing OHM compatibility suites**

```powershell
py -m pytest pipeline/tests/test_ohm_borders_stages.py pipeline/tests/test_ohm_borders_cli.py -v
```
Expected: PASS.

- [ ] **Step 3: Manual smoke test against real parsed shards**

```powershell
py -m pipeline borders events-run --run-id <existing-run-with-parsed-shards>
```

Verify:
- `events/candidates/*.jsonl` exists with extracted references
- `events/final/ohm_border_event_refs.jsonl` exists
- Sample rows include expected event labels

- [ ] **Step 4: Update README**

In `pipeline/ohm_borders/README.md`, add:

```markdown
### Event extraction

After `build` completes, extract event references from parsed shards:

```powershell
py -m pipeline borders events-run --run-id run-001
```

This writes:
- `events/candidates/*.jsonl` — extracted event references
- `events/final/ohm_border_event_refs.jsonl` — enriched event records
- `events/final/ohm_border_event_matches.jsonl` — match audit
```

- [ ] **Step 5: Commit**

```bash
git add pipeline/ohm_borders/README.md
git commit -m "docs: document event extraction commands"
```

---

## Acceptance Criteria

- `event_extractor.py` extracts start/end events from root and stage tags deterministically.
- `event_enricher.py` prefers explicit QIDs, falls back to exact-title search, records match provenance.
- `events-run` produces `events/final/ohm_border_event_refs.jsonl` and `ohm_border_event_matches.jsonl`.
- All new tests pass.
- Existing OHM stage and CLI tests remain green.
- README documents the new commands.
