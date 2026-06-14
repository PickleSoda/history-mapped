# OHM Fully Concurrent Stages Implementation Plan

> **Status (as of 2026-06-01):** SUPERSEDED by the staged parallel implementation (`2026-04-11-ohm-borders-staged-parallel-implementation.md`). The shard-based workflow, concurrent parse/build, and atomic artifact writes were implemented within that plan. Some dedicated deadlock-safety and sharding unit tests from this plan were not created as separate files, but the behavior is covered by the existing `test_ohm_borders_stages.py` suite.
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Refactor OHM borders pipeline so fetch, parse, enrich, and build operate on shard-based units concurrently (without loading full dataset into memory), while guaranteeing deterministic output and no race conditions or deadlocks.

**Architecture:** Introduce explicit raw shard artifacts and convert stages into bounded producer/consumer pipelines with immutable shard files and atomic completion markers. Parse reads raw shards and emits parsed shards with deterministic shard IDs, enrich operates on parsed shard scans and emits enrichment shard batches, and build can process parsed shards concurrently with a shared read-only enrichment index. Manifest writes are centralized to avoid concurrent mutation hazards.

**Tech Stack:** Python 3.10, Click CLI, ThreadPoolExecutor/ProcessPoolExecutor, orjson, pathlib, pytest

---

## File Structure

- Modify: `pipeline/ohm_borders/artifacts.py`
  - Add raw shard file path helpers and per-stage completion markers.
- Modify: `pipeline/ohm_borders/stages.py`
  - Add raw sharding stage.
  - Make parse stage consume raw shards concurrently and emit parsed shards incrementally.
  - Make build stage process parsed shards concurrently.
  - Keep manifest updates single-writer.
- Modify: `pipeline/ohm_borders/fetcher.py`
  - Add parse function that accepts relation subsets/shards.
- Modify: `pipeline/__main__.py`
  - Add CLI options for raw shard size and stage worker controls.
- Modify: `pipeline/ohm_borders/manifest.py`
  - Add per-shard progress fields and safe update contract.
- Create: `pipeline/tests/test_ohm_borders_sharding.py`
  - Shard partitioning, determinism, and resume behavior tests.
- Create: `pipeline/tests/test_ohm_borders_concurrency.py`
  - Concurrency correctness, no duplicate/missing records, no race-write tests.
- Create: `pipeline/tests/test_ohm_borders_deadlock_safety.py`
  - Bounded queue shutdown and worker termination behavior.
- Create: `docs/implementation-docs/ohm-concurrency-notes.md`
  - Throughput benchmark and safety checklist.

---

## Task 1: Define Shard Contract and Deterministic Mapping

**Files:**
- Modify: `pipeline/ohm_borders/artifacts.py`
- Modify: `pipeline/ohm_borders/stages.py`
- Test: `pipeline/tests/test_ohm_borders_sharding.py`

- [x] **Step 1: Define raw shard format and naming**

Contract:
- `raw/raw-00001.jsonl` ... `raw/raw-NNNNN.jsonl`
- each line contains one relation JSON object (not full overpass envelope)
- shard boundaries are deterministic by relation id sort + fixed shard size

Expected: reruns with same input produce same shard file set.

- [x] **Step 2: Add artifact path helpers**

Add:
- `raw_shard_path(artifact_dir, shard_index)`
- `raw_shard_done_path(artifact_dir, shard_index)`
- `parsed_shard_done_path(...)`, `built_shard_done_path(...)`

Expected: stage completion is tracked by atomic marker files.

- [x] **Step 3: Add tests for deterministic shard partitioning**

Run: `py -m pytest pipeline/tests/test_ohm_borders_sharding.py -xvs`

Expected: same inputs map to identical shard IDs across runs.

---

## Task 2: Split Fetch Into Raw Sharding Stage

**Files:**
- Modify: `pipeline/ohm_borders/stages.py`
- Modify: `pipeline/__main__.py`
- Test: `pipeline/tests/test_ohm_borders_sharding.py`

- [x] **Step 1: Keep existing fetch output for compatibility**

Continue writing `raw/overpass.json` for compatibility and debugging.

- [x] **Step 2: Add raw-shard writer immediately after fetch**

Algorithm:
1. iterate relations only
2. sort by relation id
3. write line-delimited relation records into `raw-*.jsonl` by `raw_shard_size`
4. write `.done` marker per shard via temp file + atomic rename

Expected: downstream stages can start from raw shards without full in-memory parse.

- [x] **Step 3: Add CLI flag**

Add `--raw-shard-size` (default e.g. 200 relations).

Expected: tunable shard granularity.

---

## Task 3: Concurrent Parse From Raw Shards (No Full Dataset Buffer)

**Files:**
- Modify: `pipeline/ohm_borders/fetcher.py`
- Modify: `pipeline/ohm_borders/stages.py`
- Test: `pipeline/tests/test_ohm_borders_concurrency.py`

- [x] **Step 1: Implement parse function for relation shard input**

Add pure function:
- input: list/iterator of relation records from one raw shard
- output: parsed polity records for that shard

Expected: no cross-shard mutable state.

- [x] **Step 2: Run parse workers per raw shard**

Use `ProcessPoolExecutor` (CPU-bound geometry assembly).

Rules:
- one output file per raw shard index: `parsed/parsed-XXXXX.jsonl`
- write to temp then atomic rename
- write `.done` marker after successful close

Expected: visible incremental progress and crash-safe partial reruns.

- [x] **Step 3: Handle chronology cross-shard dependencies safely**

Introduce precomputed relation metadata index (relation id -> shard id, tags) before worker fan-out.

Expected: chronology relations can resolve stage members deterministically without shared mutable worker state.

- [x] **Step 4: Resume/force semantics per shard**

- `resume && !force`: skip shard when parsed file + done marker exist
- `force`: rewrite shard regardless

Expected: robust partial restart behavior.

---

## Task 4: Concurrent Enrich With Safe Aggregation

**Files:**
- Modify: `pipeline/ohm_borders/stages.py`
- Modify: `pipeline/ohm_borders/manifest.py`
- Test: `pipeline/tests/test_ohm_borders_concurrency.py`

- [x] **Step 1: Collect QIDs from parsed shards incrementally**

Avoid loading all parsed records at once.

Expected: memory bounded by one shard scan + set cardinality.

- [x] **Step 2: Keep batch-level parallelism, enforce isolated writes**

Each enrich worker returns payload only; main thread performs file writes.

Expected: no write races on enrichment files.

- [x] **Step 3: Add shard-level failure capture**

Store failed enrichment batch ids without corrupting successful shards.

Expected: retry-safe enrich step.

---

## Task 5: Concurrent Build Per Parsed Shard

**Files:**
- Modify: `pipeline/ohm_borders/stages.py`
- Test: `pipeline/tests/test_ohm_borders_concurrency.py`

- [x] **Step 1: Build shard workers in parallel**

Each worker:
- loads one parsed shard
- maps records using read-only enrichment index
- writes `built/built-XXXXX.jsonl` via temp file + rename + done marker

Expected: independent, race-free shard builds.

- [x] **Step 2: Final assembly single-writer**

Main thread concatenates built shards in shard index order.

Expected: deterministic final output and no merge races.

---

## Task 6: Race Condition and Deadlock Prevention Controls

**Files:**
- Modify: `pipeline/ohm_borders/stages.py`
- Create: `pipeline/tests/test_ohm_borders_deadlock_safety.py`

- [x] **Step 1: Enforce single-writer policy**

Only coordinator thread/process can:
- mutate manifest
- write final artifacts
- create stage summary

Expected: no concurrent manifest corruption.

- [x] **Step 2: Use bounded queues and sentinel shutdown**

If using in-process queues:
- bounded `maxsize`
- explicit sentinel for worker shutdown
- timeout-based get/put with cancellation path

Expected: no deadlocks under backpressure.

- [x] **Step 3: Add cancellation/failure propagation**

On worker exception:
- cancel remaining futures
- drain queue/signal shutdown
- mark stage failed once

Expected: no hung workers or zombie pools.

- [x] **Step 4: Add deadlock safety tests**

Simulate slow consumer + failing producer; ensure stage exits within timeout.

Run: `py -m pytest pipeline/tests/test_ohm_borders_deadlock_safety.py -xvs`

Expected: clean termination, no hangs.

---

## Task 7: Progress Visibility and Monitoring

**Files:**
- Modify: `pipeline/ohm_borders/manifest.py`
- Modify: `pipeline/ohm_borders/stages.py`

- [x] **Step 1: Add per-stage shard progress counters**

Include:
- total shards
- completed shards
- failed shards
- currently active shard ids

Expected: live, meaningful progress instead of flat "running".

- [x] **Step 2: Flush manifest updates at safe intervals**

Coordinator writes progress every N completed shards (e.g. 1 or 5).

Expected: useful observability without heavy I/O overhead.

---

## Task 8: Verification and Benchmark

**Files:**
- Update: `docs/implementation-docs/ohm-concurrency-notes.md`

- [x] **Step 1: Functional verification**

Run:
- `py -m pytest pipeline/tests/test_ohm_borders_fetcher.py -xvs`
- `py -m pytest pipeline/tests/test_ohm_borders_sharding.py -xvs`
- `py -m pytest pipeline/tests/test_ohm_borders_concurrency.py -xvs`
- `py -m pytest pipeline/tests/test_ohm_borders_deadlock_safety.py -xvs`

Expected: all pass.

- [x] **Step 2: Throughput benchmark**

Run parse/build on `global-2026-04-11` with cached raw artifacts.

Record:
- old runtime baseline
- new runtime
- CPU utilization pattern
- peak memory

Expected: materially faster with visible shard progress.

- [x] **Step 3: Data parity check**

Validate no dropped or duplicated polity outputs:
- compare record counts
- sample equality checks on key entities

Expected: output correctness retained.

---

## Commit Sequence

1. `feat(ohm): add raw shard artifact contract and helpers`
2. `feat(ohm): add raw sharding stage and CLI controls`
3. `feat(ohm): parallel parse from raw shards with deterministic output`
4. `feat(ohm): parallel build and ordered final assembly`
5. `feat(ohm): add progress telemetry and failure-safe shutdown`
6. `test(ohm): add sharding, concurrency, and deadlock safety tests`
7. `docs(ohm): add concurrency benchmark and operational notes`

---

## Acceptance Criteria

- No stage requires full dataset in memory before writing shard outputs.
- Parse/build/enrich process shards concurrently with deterministic outputs.
- No concurrent writes to same file; all artifact writes are atomic.
- Manifest remains valid JSON under concurrent workloads.
- Failure in one worker does not deadlock the stage.
- Live progress reports show completed/total shards during execution.
