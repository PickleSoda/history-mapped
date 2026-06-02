# OHM Border Event Extraction Implementation Plan

> **Status (as of 2026-06-01):** NOT IMPLEMENTED. No event extractor, event enricher, or event-stage CLI commands exist. This plan is awaiting execution.
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a separate post-processing pipeline that reads existing OHM border run artifacts and extracts normalized start/end event references without re-querying OpenHistoricalMap.

**Architecture:** Build a second staged workflow on top of the existing `output/ohm_borders/<run_id>/parsed/*.jsonl` artifacts. The new workflow scans root and stage OHM tags for `start_event`, `end_event`, and related Wikidata ids, enriches explicit or inferred Wikidata matches, and emits durable event-reference artifacts and final JSONL outputs. The existing border extraction and Laravel border importer remain unchanged in this slice.

**Tech Stack:** Python 3.10, Click CLI, existing `pipeline/ohm_borders/` staged artifact helpers, JSON/JSONL artifacts, pytest, direct HTTP calls to the Wikidata Query Service SPARQL endpoint, optional direct HTTP calls to the Wikidata search API for exact-title fallback.

**Prerequisite:** `docs/superpowers/plans/2026-04-11-ohm-borders-staged-parallel-implementation.md` Tasks 1 through 5 must already be implemented because this plan consumes the staged border artifact directory and extends its helpers.

---

## Task 1: Define Event Reference Contracts And Artifact Layout

**Files:**

- Modify: `pipeline/ohm_borders/artifacts.py`
- Modify: `pipeline/ohm_borders/manifest.py`
- Create: `pipeline/tests/test_ohm_borders_event_artifacts.py`
- Reference existing doc: `docs/implementation-docs/ohm_border_extraction_step_by_step.md`

- [ ] **Step 1: Write the failing tests**

Add tests covering:

- deterministic event artifact directories under an existing OHM border run
- deterministic filenames for event scan shards, enrichment shards, and final outputs
- manifest top-level shape with new event stages present but isolated from the border stages
- atomic manifest update behavior for event-stage writes

Example test cases to include:

```python
def test_event_artifact_paths_are_deterministic(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "output" / "ohm_borders" / "run-001"
    assert event_candidates_dir(artifact_dir) == artifact_dir / "events" / "candidates"
    assert event_candidate_shard_path(artifact_dir, 1) == artifact_dir / "events" / "candidates" / "event-candidates-00001.jsonl"
    assert event_final_refs_path(artifact_dir) == artifact_dir / "events" / "final" / "ohm_border_event_refs.jsonl"


def test_event_manifest_stage_shape_matches_contract(tmp_path: Path) -> None:
    manifest = create_or_extend_manifest_for_event_pipeline("run-001", tmp_path / "output" / "ohm_borders" / "run-001")
    assert set(manifest["event_stages"].keys()) == {"scan", "enrich", "build"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest pipeline/tests/test_ohm_borders_event_artifacts.py -v`

Expected: FAIL because the event artifact helpers and manifest extension do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Implement:

- event artifact path helpers beneath `output/ohm_borders/<run_id>/events/`
- filenames for:
  - `events/candidates/event-candidates-00001.jsonl`
  - `events/enriched/event-enriched-00001.json`
  - `events/final/ohm_border_event_refs.jsonl`
  - `events/final/ohm_border_event_matches.jsonl`
- manifest support for a separate `event_stages` section so the border workflow does not have to change semantics

Document the final manifest shape explicitly in code and tests:

```json
{
  "run_id": "run-001",
  "artifact_dir": "output/ohm_borders/run-001",
  "options": {},
  "summary": {},
  "stages": {"fetch": {}, "parse": {}, "enrich": {}, "build": {}},
  "event_stages": {"scan": {}, "enrich": {}, "build": {}}
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest pipeline/tests/test_ohm_borders_event_artifacts.py -v`

Expected: PASS

## Task 2: Extract Raw Start/End Event References From Parsed Border Shards

**Files:**

- Create: `pipeline/ohm_borders/event_extractor.py`
- Create: `pipeline/tests/test_ohm_borders_event_extractor.py`
- Reference: `pipeline/ohm_borders/fetcher.py`
- Reference: `pipeline/ohm_borders/mapper.py`

- [ ] **Step 1: Write the failing tests**

Add tests covering:

- extraction of root-level `start_event` and `end_event` tags from parsed polity records
- extraction of per-stage `start_event`, `end_event`, `start_event:wikidata`, and `end_event:wikidata`
- preservation of source relation ids for both polity roots and stage members
- handling of missing event labels, missing event QIDs, and duplicate repeated events across stages
- deterministic normalization of event roles into a stable output schema

Example test cases to include:

```python
def test_extract_event_refs_from_stage_tags() -> None:
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

    assert refs == [
        {
            "event_role": "start",
            "event_label": "Bosnian crisis, de jure inclusion of Bosnian Condominium",
            "event_wikidata_id": "Q167246",
            "polity_ohm_relation_id": "28513",
            "stage_ohm_relation_id": "999",
            "event_date": "1908-10-06",
        }
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest pipeline/tests/test_ohm_borders_event_extractor.py -v`

Expected: FAIL because the extractor does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Implement extraction helpers that:

- read root `tags` and each stage `tags`
- emit one normalized reference record per discovered start/end event
- preserve:
  - `polity_ohm_relation_id`
  - `stage_ohm_relation_id`
  - `polity_name`
  - `polity_wikidata_id`
  - `event_role`
  - `event_label`
  - `event_wikidata_id`
  - `event_date`
  - `source_tag_key`
  - `source_tags`
- ignore empty strings and whitespace-only event labels

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest pipeline/tests/test_ohm_borders_event_extractor.py -v`

Expected: PASS

## Task 3: Add A Staged Event Scan Command Over Existing Border Artifacts

**Files:**

- Modify: `pipeline/ohm_borders/stages.py`
- Modify: `pipeline/__main__.py`
- Test: `pipeline/tests/test_ohm_borders_event_stages.py`

- [ ] **Step 1: Write the failing tests**

Add tests covering:

- `borders events-scan` reading `parsed/*.jsonl` from an existing border run
- candidate shard planning and JSONL output
- manifest counters for extracted references and scanned polity shards
- `--resume` skipping existing event candidate shards unless `--force` is set

Example test cases to include:

```python
def test_event_scan_reads_parsed_shards_and_writes_candidate_shards(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    parsed_shard_path(artifact_dir, 1).write_text(
        '{"relation_id":1,"tags":{"name":"Romania"},"stages":[{"relation_id":10,"tags":{"start_event":"Declaration of Kingdom"},"geometry":null}]}' + "\n",
        encoding="utf-8",
    )

    result = run_event_scan_stage(run_id="run-001", artifact_dir=artifact_dir, candidate_shard_size=10)
    assert result["reference_count"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest pipeline/tests/test_ohm_borders_event_stages.py -k "scan" -v`

Expected: FAIL because the event scan stage and CLI do not exist.

- [ ] **Step 3: Write minimal implementation**

Implement:

- `run_event_scan_stage(...)` in `pipeline/ohm_borders/stages.py`
- candidate sharding over extracted event references
- CLI command registration:
  - `python -m pipeline borders events-scan --run-id ...`
- defaults:
  - `--candidate-shard-size=500`
- resume and force semantics matching the existing border stages

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest pipeline/tests/test_ohm_borders_event_stages.py -k "scan" -v`

Expected: PASS

## Task 4: Enrich Event References With Explicit QIDs And Exact-Title Fallbacks

**Files:**

- Create: `pipeline/ohm_borders/event_enricher.py`
- Modify: `pipeline/ohm_borders/stages.py`
- Modify: `pipeline/__main__.py`
- Test: `pipeline/tests/test_ohm_borders_event_enricher.py`
- Test: `pipeline/tests/test_ohm_borders_event_stages.py`

- [ ] **Step 1: Write the failing tests**

Add tests covering:

- Wikidata enrichment for event references that already include `start_event:wikidata` or `end_event:wikidata`
- exact-title fallback lookup for event references with labels but no QID
- rejection of ambiguous name-search results
- preservation of confidence and match source in the enriched payload
- event enrichment shards written independently with partial-failure tolerance

Example test cases to include:

```python
def test_enrich_event_refs_prefers_explicit_qid() -> None:
    refs = [{"event_label": "Treaty of Berlin", "event_wikidata_id": "Q1048169"}]
    enriched = enrich_event_refs(refs)
    assert enriched[0]["resolved_wikidata_id"] == "Q1048169"
    assert enriched[0]["match_source"] == "explicit_qid"


def test_enrich_event_refs_uses_exact_title_fallback_when_qid_missing(monkeypatch) -> None:
    monkeypatch.setattr(event_enricher_module, "search_event_by_title", lambda title: {"qid": "Q500067", "label": title, "confidence": "exact_title"})
    refs = [{"event_label": "Treaty of Bucharest", "event_wikidata_id": None}]
    enriched = enrich_event_refs(refs)
    assert enriched[0]["resolved_wikidata_id"] == "Q500067"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest pipeline/tests/test_ohm_borders_event_enricher.py pipeline/tests/test_ohm_borders_event_stages.py -k "enrich" -v`

Expected: FAIL because the event enricher and event enrich stage do not exist.

- [ ] **Step 3: Write minimal implementation**

Implement:

- an event enricher that:
  - batches explicit event QIDs through Wikidata SPARQL
  - optionally searches Wikidata by exact English title for references missing a QID
  - records `match_source` as one of:
    - `explicit_qid`
    - `exact_title_search`
    - `unresolved`
  - records confidence and raw search evidence for later auditing
- `run_event_enrich_stage(...)`
- CLI command registration:
  - `python -m pipeline borders events-enrich --run-id ...`
- defaults:
  - `--event-enrich-batch-size=50`
  - `--event-enrich-workers=4`

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest pipeline/tests/test_ohm_borders_event_enricher.py pipeline/tests/test_ohm_borders_event_stages.py -k "enrich" -v`

Expected: PASS

## Task 5: Build Final Event Reference Outputs For Downstream Consumers

**Files:**

- Modify: `pipeline/ohm_borders/stages.py`
- Modify: `pipeline/__main__.py`
- Test: `pipeline/tests/test_ohm_borders_event_stages.py`
- Test: `pipeline/tests/test_ohm_borders_event_cli.py`

- [ ] **Step 1: Write the failing tests**

Add tests covering:

- `events-build` merging candidate shards with enrichment shards
- deterministic final JSONL ordering
- output of a normalized event reference file for downstream pipelines
- output of a separate match-audit file showing explicit versus inferred Wikidata resolution
- `events-run` wiring scan to enrich to build end to end

Expected final outputs:

- `events/final/ohm_border_event_refs.jsonl`
- `events/final/ohm_border_event_matches.jsonl`

Example test cases to include:

```python
def test_event_build_writes_refs_and_match_audit(tmp_path: Path) -> None:
    result = run_event_build_stage(run_id="run-001", artifact_dir=tmp_path / "artifacts")
    assert result["status"] == "completed"
    assert event_final_refs_path(tmp_path / "artifacts").exists()
    assert event_final_matches_path(tmp_path / "artifacts").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest pipeline/tests/test_ohm_borders_event_stages.py pipeline/tests/test_ohm_borders_event_cli.py -k "build or run" -v`

Expected: FAIL because the build stage and CLI wrapper do not exist.

- [ ] **Step 3: Write minimal implementation**

Implement:

- `run_event_build_stage(...)`
- final JSONL schema for `ohm_border_event_refs.jsonl` with fields including:
  - `event_role`
  - `event_label`
  - `resolved_wikidata_id`
  - `polity_ohm_relation_id`
  - `stage_ohm_relation_id`
  - `polity_name`
  - `event_date`
  - `match_source`
  - `match_confidence`
  - `source_tags`
- CLI commands:
  - `python -m pipeline borders events-build --run-id ...`
  - `python -m pipeline borders events-run --run-id ...`

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest pipeline/tests/test_ohm_borders_event_stages.py pipeline/tests/test_ohm_borders_event_cli.py -k "build or run" -v`

Expected: PASS

## Task 6: Document The Event Pipeline And Verify It Against A Real Border Run

**Files:**

- Modify: `pipeline/README.md`
- Modify: `docs/implementation-docs/ohm_border_extraction_step_by_step.md`
- Test: `pipeline/tests/test_ohm_borders_event_artifacts.py`
- Test: `pipeline/tests/test_ohm_borders_event_extractor.py`
- Test: `pipeline/tests/test_ohm_borders_event_enricher.py`
- Test: `pipeline/tests/test_ohm_borders_event_stages.py`
- Test: `pipeline/tests/test_ohm_borders_event_cli.py`

- [ ] **Step 1: Update documentation**

Document:

- the new event pipeline commands
- that the event pipeline consumes existing border artifacts instead of refetching OHM
- the event output files and their intended downstream use
- the exact-title Wikidata fallback behavior and its limitations

- [ ] **Step 2: Run the full Python event test slice**

Run: `python -m pytest pipeline/tests/test_ohm_borders_event_artifacts.py pipeline/tests/test_ohm_borders_event_extractor.py pipeline/tests/test_ohm_borders_event_enricher.py pipeline/tests/test_ohm_borders_event_stages.py pipeline/tests/test_ohm_borders_event_cli.py -v`

Expected: PASS

- [ ] **Step 3: Manual smoke test against a real OHM border run**

Run the new event pipeline against an existing border artifact directory containing parsed shards, for example:

```powershell
python -m pipeline borders events-run --run-id smoke-20260411
```

Verify:

- `events/candidates/*.jsonl` exists
- `events/enriched/*.json` exists
- `events/final/ohm_border_event_refs.jsonl` exists
- sample rows include observed tags like `start_event:wikidata` and `end_event:wikidata`

- [ ] **Step 4: Spot-check sample outputs for known data**

Verify at least one sample includes expected values such as:

- `Treaty of Munich` with `start_event:wikidata=Q2518869`
- `Aster Revolution` with `end_event:wikidata=Q689527`
- records with text-only `start_event` or `end_event` preserved even when unresolved

## Out Of Scope For This Plan

- importing event reference outputs into Laravel
- creating or updating event entities in the database
- attaching `source_event_id` onto `geometry_periods`
- adding new schema columns for separate start-event and end-event foreign keys

Those can be planned in a follow-up slice once the extraction output quality is known.
