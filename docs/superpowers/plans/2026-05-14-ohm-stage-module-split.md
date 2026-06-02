# OHM Stage Module Split Implementation Plan

> **Status (as of 2026-06-01):** COMPLETED. `pipeline/ohm_borders/stages.py` remains a compatibility facade; stage logic lives in `stage_common.py`, `stage_fetch.py`, `stage_parse.py`, `stage_enrich.py`, `stage_build.py`, and `stage_relations.py`. Tests pass.
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Split `pipeline/ohm_borders/stages.py` into stage-specific modules while preserving the existing `pipeline.ohm_borders.stages` import API.

**Architecture:** Extract shared helpers into a common internal module, move each stage family into its own module, and keep `pipeline.ohm_borders.stages` as a thin compatibility facade that re-exports the same public functions. Validate the split with focused compatibility coverage plus the existing OHM stage pytest suites.

**Tech Stack:** Python 3.10+, Click CLI, pytest, existing OHM borders artifact helpers and stage tests.

---

### Task 1: Add facade compatibility coverage

**Files:**
- Modify: `pipeline/tests/test_ohm_borders_stages.py`

- [x] **Step 1: Write the failing compatibility test**
Add a test that imports the public stage functions from `pipeline.ohm_borders.stages` and asserts the module still exposes the expected callable names after the split.

- [x] **Step 2: Run the targeted test to verify it fails if the facade is broken**
Run: `py -m pytest pipeline/tests/test_ohm_borders_stages.py -k facade -v`
Expected: The new test is collected and will guard the public API during the refactor.

- [x] **Step 3: Keep the test in place during refactor**
Do not change its expectation away from the current public API.

### Task 2: Extract shared helpers

**Files:**
- Create: `pipeline/ohm_borders/stage_common.py`
- Modify: `pipeline/ohm_borders/stages.py`

- [x] **Step 1: Move shared helper functions and shared constants**
Extract artifact resolution helpers, manifest update helpers, JSONL IO helpers, path sorting, timestamps, and shared counters/constants into `stage_common.py`.

- [x] **Step 2: Update imports in `stages.py` to use the common module**
Keep behavior unchanged while reducing `stages.py` responsibility.

- [x] **Step 3: Run focused tests**
Run: `py -m pytest pipeline/tests/test_ohm_borders_stages.py -k "fetch or parse" -v`
Expected: Existing fetch/parse tests still pass.

### Task 3: Extract fetch and parse stages

**Files:**
- Create: `pipeline/ohm_borders/stage_fetch.py`
- Create: `pipeline/ohm_borders/stage_parse.py`
- Modify: `pipeline/ohm_borders/stages.py`

- [x] **Step 1: Move `run_fetch_stage` and fetch-specific helpers into `stage_fetch.py`**
Move raw relation sharding logic with only the imports it actually needs.

- [x] **Step 2: Move `run_parse_stage` and parse worker helpers into `stage_parse.py`**
Include relation lookup DB helpers, chronology helpers, parse worker globals, and parse-specific worker functions.

- [x] **Step 3: Re-export from `stages.py`**
Import and re-export `run_fetch_stage`, `run_parse_stage`, `default_parallelism`, `resolve_run_id`, `resolve_artifact_dir`, `manifest_path_for`, and `plan_parsed_shards`.

- [x] **Step 4: Run focused tests**
Run: `py -m pytest pipeline/tests/test_ohm_borders_stages.py -v`
Expected: Stage tests remain green.

### Task 4: Extract enrich, build, and relations stages

**Files:**
- Create: `pipeline/ohm_borders/stage_enrich.py`
- Create: `pipeline/ohm_borders/stage_build.py`
- Create: `pipeline/ohm_borders/stage_relations.py`
- Modify: `pipeline/ohm_borders/stages.py`

- [x] **Step 1: Move `run_enrich_stage` into `stage_enrich.py`**
Move only the enrichment-specific batching logic and keep shared JSON helpers in the common module.

- [x] **Step 2: Move `run_build_stage` and build worker helpers into `stage_build.py`**
Include build worker globals and final JSONL assembly usage.

- [x] **Step 3: Move relation stage entrypoints into `stage_relations.py`**
Keep relation-specific manifest updates and final entity/hint assembly there.

- [x] **Step 4: Reduce `stages.py` to a facade**
Leave the module as imports/re-exports only.

### Task 5: Run full focused verification

**Files:**
- Verify only

- [x] **Step 1: Run the core stage test suite**
Run: `py -m pytest pipeline/tests/test_ohm_borders_stages.py -v`
Expected: PASS

- [x] **Step 2: Run relation stage tests**
Run: `py -m pytest pipeline/tests/test_ohm_borders_relations_extractor.py pipeline/tests/test_ohm_borders_relations_enricher.py pipeline/tests/test_ohm_borders_relations_stages.py -v`
Expected: PASS

- [x] **Step 3: Run deadlock/build safety tests**
Run: `py -m pytest pipeline/tests/test_ohm_borders_deadlock_safety.py -v`
Expected: PASS

- [x] **Step 4: If needed, run a narrow CLI smoke test**
Run: `py -m pytest pipeline/tests/test_ohm_borders_stages.py -k cli -v`
Expected: PASS if CLI-focused tests are present.
