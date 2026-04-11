# OHM Borders Staged Parallel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-pass OHM borders command with a staged, shard-based, resumable workflow that preserves the existing Laravel import contract.

**Architecture:** Introduce explicit artifact and manifest management under `pipeline/ohm_borders/`, refactor the CLI into staged subcommands, parallelize parse and enrich with bounded workers, and keep `borders run` as the compatibility path that emits the same final JSONL schema as today.

**Tech Stack:** Python 3.10, Click CLI, Rich console output, existing OHM fetcher/enricher/mapper modules, JSON/JSONL artifacts, pytest.

---

### Task 1: Add Artifact And Manifest Infrastructure

**Files:**
- Create: `pipeline/ohm_borders/artifacts.py`
- Create: `pipeline/ohm_borders/manifest.py`
- Test: `pipeline/tests/test_ohm_borders_artifacts.py`

- [ ] **Step 1: Write the failing tests**

Add tests covering:
- deterministic artifact directory calculation from `run_id`
- deterministic parsed/enriched/built shard filenames
- manifest creation with the documented top-level shape
- atomic manifest update behavior via temp-file replacement semantics

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -m pytest pipeline/tests/test_ohm_borders_artifacts.py -v`
Expected: FAIL because artifact and manifest helpers do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Implement:
- path helpers for `raw/`, `parsed/`, `enriched/`, `built/`, `final/`
- deterministic shard naming helpers
- manifest load/create/update helpers using temp-file then `os.replace`

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -m pytest pipeline/tests/test_ohm_borders_artifacts.py -v`
Expected: PASS

### Task 2: Extract Staged Fetch And Parse Commands

**Files:**
- Modify: `pipeline/__main__.py`
- Modify: `pipeline/ohm_borders/fetcher.py`
- Create: `pipeline/ohm_borders/stages.py`
- Test: `pipeline/tests/test_ohm_borders_stages.py`

- [ ] **Step 1: Write the failing tests**

Add tests covering:
- `fetch` writing `raw/overpass.json` and manifest counters
- `parse` reading raw elements and writing parsed JSONL shards of the configured size
- `fetch --resume` skipping when `raw/overpass.json` already exists unless `--force` is set
- `parse --resume` skipping existing completed shards unless `--force` is set

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -m pytest pipeline/tests/test_ohm_borders_stages.py -k "fetch or parse" -v`
Expected: FAIL because the staged command flow does not exist.

- [ ] **Step 3: Write minimal implementation**

Implement:
- stage functions for `fetch` and `parse`
- shard planning for parsed polity objects
- manifest stage updates and summary counters
- default option handling for `--parsed-shard-size` = `100` and `--parse-workers` using `max(1, cpu_count() - 1)`
- CLI option wiring for `--run-id`, `--artifact-dir`, `--query-file`, `--parsed-shard-size`, `--parse-workers`, `--resume`, and `--force`
- CLI registration for `borders fetch` and `borders parse`

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -m pytest pipeline/tests/test_ohm_borders_stages.py -k "fetch or parse" -v`
Expected: PASS

### Task 3: Add Parallel Enrichment And Build Stages

**Files:**
- Modify: `pipeline/__main__.py`
- Modify: `pipeline/ohm_borders/enricher.py`
- Modify: `pipeline/ohm_borders/mapper.py`
- Modify: `pipeline/ohm_borders/stages.py`
- Test: `pipeline/tests/test_ohm_borders_stages.py`
- Test: `pipeline/tests/test_ohm_borders_mapper.py`

- [ ] **Step 1: Write the failing tests**

Add tests covering:
- enrichment shard planning from parsed shard inputs
- partial enrich failures recorded in manifest without blocking build
- `build --resume` rebuilding only missing outputs unless `--force` is set
- `build --no-enrich` succeeding with an empty enrichment index while preserving the importer-facing JSONL schema
- build loading enrichment shards into a QID index
- build emitting deterministic built shard outputs and merged final JSONL
- existing regression that malformed reversed stage periods are dropped during build

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -m pytest pipeline/tests/test_ohm_borders_stages.py -k "enrich or build" -v`
Expected: FAIL because enrich/build stages are not implemented.

- [ ] **Step 3: Write minimal implementation**

Implement:
- enrichment batching over unique QIDs from parsed shards
- bounded concurrent workers for enrichment
- default option handling for `--enrich-batch-size` and `--enrich-workers` with defaults `50` and `4`
- per-shard success and failed shard tracking in the manifest
- build stage that merges parsed shards with the enrichment index and writes both shard outputs and `final/ohm_borders.jsonl`
- CLI option wiring for `--enrich-batch-size`, `--enrich-workers`, `--resume`, `--force`, and `--no-enrich`

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -m pytest pipeline/tests/test_ohm_borders_stages.py -k "enrich or build" -v`
Expected: PASS

### Task 4: Restore A Compatible Top-Level Borders Interface

**Files:**
- Modify: `pipeline/__main__.py`
- Test: `pipeline/tests/test_ohm_borders_cli.py`

- [ ] **Step 1: Write the failing tests**

Add tests covering:
- `py -m pipeline borders run` executing the full staged workflow
- existing-style `py -m pipeline borders --output ...` compatibility behavior
- `--no-enrich`, `--resume`, and `--force` wiring to the staged runner
- option propagation from `run` into fetch/parse/enrich/build for `--run-id`, `--artifact-dir`, worker counts, and shard sizes

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -m pytest pipeline/tests/test_ohm_borders_cli.py -v`
Expected: FAIL because the compatibility shim does not exist.

- [ ] **Step 3: Write minimal implementation**

Implement:
- `borders` as a Click group with `fetch`, `parse`, `enrich`, `build`, `run`
- compatibility path for the old one-shot invocation
- Rich console summaries per stage and final run summary

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -m pytest pipeline/tests/test_ohm_borders_cli.py -v`
Expected: PASS

### Task 5: Update Documentation And Run Verification

**Files:**
- Modify: `pipeline/README.md`
- Test: `pipeline/tests/test_ohm_borders_date_parser.py`
- Test: `pipeline/tests/test_ohm_borders_fetcher.py`
- Test: `pipeline/tests/test_ohm_borders_enricher.py`
- Test: `pipeline/tests/test_ohm_borders_mapper.py`
- Test: `pipeline/tests/test_ohm_borders_artifacts.py`
- Test: `pipeline/tests/test_ohm_borders_stages.py`
- Test: `pipeline/tests/test_ohm_borders_cli.py`

- [ ] **Step 1: Update docs**

Document:
- staged command examples
- artifact directory layout
- resume and force behavior
- throughput-oriented default worker settings

- [ ] **Step 2: Run the full OHM Python test slice**

Run: `py -m pytest pipeline/tests/test_ohm_borders_date_parser.py pipeline/tests/test_ohm_borders_fetcher.py pipeline/tests/test_ohm_borders_enricher.py pipeline/tests/test_ohm_borders_mapper.py pipeline/tests/test_ohm_borders_artifacts.py pipeline/tests/test_ohm_borders_stages.py pipeline/tests/test_ohm_borders_cli.py`
Expected: PASS

- [ ] **Step 3: Spot-check Laravel importer compatibility**

Run: `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/ImportBordersCommandTest.php`
Expected: PASS

- [ ] **Step 4: Manual smoke test**

Run a small staged borders flow into a temporary artifact directory and verify:
- raw fetch artifact exists
- parsed shards exist
- enrich shards exist or are intentionally skipped with `--no-enrich`
- final merged JSONL exists and can be imported by Laravel