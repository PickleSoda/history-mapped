# OHM Subgraph Index Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the full-memory OHM country-subgraph extraction path with a streaming SQLite-backed index so repeated country extraction runs are memory-bounded, reuse a persistent index, and provide deterministic fuzzy seed suggestions.

**Architecture:** Add a dedicated index builder that streams the global `overpass.json` into SQLite metadata and edge tables, then refactor `extract-subgraph` to read seed lookup and traversal data from that index instead of reparsing the raw payload. Preserve the existing subset artifact outputs and downstream parse/relation compatibility while making rerun, lock, and schema/fingerprint checks explicit.

**Tech Stack:** Python 3.10+, SQLite, streaming JSON parser (`ijson` or equivalent), `rapidfuzz`, Click CLI, existing OHM artifact stages, pytest.

---

### Task 1: Lock the index-store contract with failing tests

**Files:**
- Create: `pipeline/tests/test_ohm_borders_index_store.py`
- Modify: `pipeline/requirements.txt`

- [x] **Step 1: Write metadata-contract tests**
Add tests that expect a single-row `index_metadata` table with `schema_version`, `payload_format_version`, `source_fingerprint_sha256`, `source_path`, `source_size_bytes`, `source_mtime_epoch`, `build_completed_at`, `fuzzy_matcher_name`, `fuzzy_matcher_version`, and `fuzzy_threshold`.

- [x] **Step 2: Write relation and edge schema tests**
Assert the SQLite store creates `relations`, `chronology_edges`, `qid_edges`, and `qid_to_relations` with the required constraints and indexes.

- [x] **Step 3: Write lock-file behavior tests**
Cover active lock failure, stale lock cleanup after timeout, PID/hostname/timestamp capture in the lock contents, exclusive create semantics, cleanup logging, and process-specific temporary index file naming.

- [x] **Step 4: Add any package dependency declarations**
Pin `rapidfuzz` and `ijson` explicitly in `pipeline/requirements.txt` so the matcher and streaming parser are deterministic across runs.

- [x] **Step 5: Run the focused tests to verify they fail**
Run: `py -m pytest pipeline/tests/test_ohm_borders_index_store.py -v`
Expected: FAIL because the store module and schema do not exist yet.

### Task 2: Implement the SQLite store and lock handling

**Files:**
- Create: `pipeline/ohm_borders/index_store.py`
- Modify: `pipeline/requirements.txt`

- [x] **Step 1: Implement schema creation and metadata writes**
Create helpers that initialize the SQLite schema, insert the `index_metadata` row only after successful completion, and enforce the expected schema and payload format versions.

- [x] **Step 2: Implement relation and edge insert helpers**
Add batched insert APIs for `relations`, `chronology_edges`, `qid_edges`, and `qid_to_relations`, including index-friendly lookup helpers.

- [x] **Step 3: Implement lock acquisition and stale-lock recovery**
Use `<index-path>.lock` with exclusive create semantics, PID/hostname/timestamp/source-path metadata, concurrent-builder rejection, a documented stale-timeout constant, cleanup logging, and explicit cleanup on success/failure.

- [x] **Step 4: Implement Windows-safe replace failure handling**
When an existing index cannot be atomically replaced because active readers still hold the file, surface a clear retry message and leave the old completed index untouched.

- [x] **Step 5: Implement compatibility readers**
Add helpers to read metadata, compare schema version and source fingerprint, and open the database in read-only mode for extraction.

- [x] **Step 6: Run the store tests to verify they pass**
Run: `py -m pytest pipeline/tests/test_ohm_borders_index_store.py -v`
Expected: PASS.

### Task 3: Add failing streaming index-builder tests

**Files:**
- Create: `pipeline/tests/test_ohm_borders_index_builder.py`

- [x] **Step 1: Write streaming ingest fixture tests**
Use a small Overpass fixture and assert the builder writes the expected rows for chronology relations, stage relations, and QID edge kinds.

- [x] **Step 2: Write fingerprint and rebuild tests**
Assert identical-content inputs at different paths are compatible, one-byte-different inputs are incompatible, and `--force` is required to rebuild.

- [x] **Step 3: Write BOM and partial-build tests**
Cover BOM-prefixed input acceptance and the temp-index replacement path when a build fails before completion.

- [x] **Step 4: Run the focused builder tests to verify they fail**
Run: `py -m pytest pipeline/tests/test_ohm_borders_index_builder.py -v`
Expected: FAIL because the builder module does not exist yet.

### Task 4: Implement the streaming index builder

**Files:**
- Create: `pipeline/ohm_borders/index_builder.py`

- [x] **Step 1: Implement streaming relation ingestion**
Use `ijson` or the chosen streaming parser explicitly to iterate `elements` incrementally, accept BOM-prefixed UTF-8 input, and write only relevant relation records into the store.

- [x] **Step 2: Implement normalized-name and edge extraction**
Normalize names with the spec-defined NFC/casefold/whitespace-collapsing function and extract chronology and QID edges with the supported taxonomy.

- [x] **Step 3: Implement source fingerprint calculation and temp-file replacement**
Calculate SHA256 over the source content, build into a process-specific temporary SQLite file, then atomically replace the target path on success.

- [x] **Step 4: Implement `build-index` result summaries**
Return row counts, fingerprint, index path, and skipped/completed status for CLI and stage consumers.

- [x] **Step 5: Run the focused builder tests to verify they pass**
Run: `py -m pytest pipeline/tests/test_ohm_borders_index_builder.py -v`
Expected: PASS.

### Task 5: Lock the indexed seed-resolution and fuzzy-search behavior with failing tests

**Files:**
- Create: `pipeline/tests/test_ohm_country_subgraph_indexed_extractor.py`

- [x] **Step 1: Copy and adapt the existing country-subgraph fixture for indexed extraction**
Create an indexed-test fixture derived from `pipeline/tests/test_ohm_country_subgraph_extractor.py::_fixture_overpass` so the indexed BFS parity test compares against known relation ids and edge outputs.

- [x] **Step 2: Write exact and normalized lookup tests**
Assert lookup by `--seed-qid`, exact `--seed-name`, and normalized exact name all resolve to the same indexed seed identity.

- [x] **Step 3: Write fuzzy algorithm contract tests**
Cover the full algorithm: NFC normalization, casefolding, whitespace collapse, 3-character prefix candidate query capped at 1000 rows, 2-character fallback capped at 1000 rows, default `0.85` threshold, top-5 suggestions, no unbounded scan, and non-interactive failure behavior.

- [x] **Step 4: Write explicit `--auto-select-fuzzy` tests**
Assert only a clear best match above threshold is auto-selected when the flag is present and that ambiguous candidates still fail with suggestions.

- [x] **Step 5: Write indexed BFS parity tests**
Assert the SQLite-backed traversal produces the same relation ids, edges, and closure report as the current known-good fixture expectations.

- [x] **Step 6: Run the focused extractor tests to verify they fail**
Run: `py -m pytest pipeline/tests/test_ohm_country_subgraph_indexed_extractor.py -v`
Expected: FAIL because the extractor still depends on full in-memory raw JSON indexes.

### Task 6: Refactor the extractor to use SQLite

**Files:**
- Modify: `pipeline/ohm_borders/subgraph_extractor.py`
- Modify: `pipeline/ohm_borders/stage_extract_subgraph.py`

- [x] **Step 1: Split backend-independent helpers from data access**
Refactor `pipeline/ohm_borders/subgraph_extractor.py` so traversal, closure-report assembly, and payload reconstruction can operate on store-driven seed and neighbor lookups instead of only raw payload dicts.

- [x] **Step 2: Implement indexed seed resolution**
Implement indexed seed resolution in `pipeline/ohm_borders/subgraph_extractor.py` using metadata-backed exact, normalized, and fuzzy lookup with `unicodedata.normalize("NFC", value)`, `.casefold()`, whitespace collapsing, recorded matcher version/threshold handling, and the bounded prefix-prefilter algorithm.

- [x] **Step 3: Implement indexed BFS and payload reconstruction**
Implement indexed BFS and payload reconstruction in `pipeline/ohm_borders/subgraph_extractor.py`: traverse via SQLite edge tables, fetch only the needed relation payload blobs, and reconstruct the reduced `raw/overpass.json` plus graph edges without rereading the source file.

- [x] **Step 4: Preserve resume-equivalence checks**
Update `pipeline/ohm_borders/stage_extract_subgraph.py` so `subgraph/seed.json` records resolved seed relation ids and extraction metadata, and so `--seed-name` and `--seed-qid` can be treated as equivalent when they resolve to the same seed on a rerun.

- [x] **Step 5: Remove the old raw full-memory extraction path from normal command execution**
Make indexed extraction the only supported `extract-subgraph` runtime path and fail fast when no compatible index is available and auto-build is not enabled.

- [x] **Step 6: Run the indexed extractor tests to verify they pass**
Run: `py -m pytest pipeline/tests/test_ohm_country_subgraph_indexed_extractor.py -v`
Expected: PASS.

### Task 7: Wire the CLI and stage orchestration

**Files:**
- Modify: `pipeline/ohm_borders/__main__.py`
- Modify: `pipeline/__main__.py`
- Modify: `pipeline/ohm_borders/stages.py`
- Modify: `pipeline/ohm_borders/stage_extract_subgraph.py`

- [x] **Step 1: Add `build-index` to the OHM borders CLI**
Expose `--input`, `--index-path`, and `--force` with clear result summaries.

- [x] **Step 2: Extend `extract-subgraph` flags**
Add `--index-path`, `--build-index-if-missing`, and `--auto-select-fuzzy`, and make indexed extraction the only supported execution path.

- [x] **Step 3: Implement index discovery and compatibility checks**
Apply the explicit discovery order, metadata checks, incompatible-index hard-fail behavior, and `build-index --force` guidance.

- [x] **Step 4: Add command-path coverage for indexed-only execution**
Add tests that prove `extract-subgraph` no longer falls back to the old full-memory extraction path during normal command execution.

- [x] **Step 5: Add CLI coverage**
Extend tests to cover `build-index`, fresh extraction with auto-build, incompatible-index failure, and top-level legacy dispatcher wiring.

- [x] **Step 6: Run the focused CLI tests**
Run: `py -m pytest pipeline/tests/test_ohm_country_subgraph_indexed_extractor.py -k "cli or command" -v`
Expected: PASS.

### Task 8: Run focused end-to-end verification

**Files:**
- Verify only

- [x] **Step 1: Run all new index-related test files**
Run: `py -m pytest pipeline/tests/test_ohm_borders_index_store.py pipeline/tests/test_ohm_borders_index_builder.py pipeline/tests/test_ohm_country_subgraph_indexed_extractor.py -v`
Expected: PASS.

- [x] **Step 2: Run existing OHM compatibility suites**
Run: `py -m pytest pipeline/tests/test_ohm_country_subgraph_extractor.py pipeline/tests/test_ohm_borders_relations_extractor.py pipeline/tests/test_ohm_borders_relations_stages.py pipeline/tests/test_ohm_borders_stages.py -v`
Expected: PASS.

- [x] **Step 3: Run a first-run smoke sequence**
Run: `py -m pipeline borders build-index --input pipeline/output/smoke-subgraph-fixture/overpass.json --index-path pipeline/output/smoke-subgraph-fixture/overpass.sqlite3`
Expected: index is created with completed metadata and no full-memory extraction required.

- [x] **Step 4: Run a second-run extraction smoke sequence**
Run: `py -m pipeline borders extract-subgraph --input pipeline/output/smoke-subgraph-fixture/overpass.json --index-path pipeline/output/smoke-subgraph-fixture/overpass.sqlite3 --seed-qid Q1 --run-id smoke-indexed-subgraph --max-depth 3 --max-nodes 400`
Expected: subset artifacts are written from the index and the command avoids reparsing the raw source payload.

- [x] **Step 5: Verify indexed extraction avoids the old full-memory path**
Add a concrete guard such as a test-only hook or monkeypatch that raises if the old raw full-payload extraction path is invoked, and assert the second extraction run succeeds without triggering that guard.

- [x] **Step 6: Verify Windows-specific replacement failure handling**
Add a Windows-focused test or simulated lock scenario that proves `build-index --force` reports a clear retry message when active readers prevent safe index replacement.

- [x] **Step 7: Verify memory-bounded ingest and extraction behavior**
Add a concrete check by monkeypatching the old full-payload JSON loader to raise and by instrumenting the streaming parser call count or iterator consumption so `build-index` proves incremental parsing while second-run extraction proves SQLite-only execution.

### Task 9: Update docs and operator guidance

**Files:**
- Modify: `docs/implementation-docs/ohm_country_subgraph_runbook.md`
- Modify: `pipeline/ohm_borders/README.md`

- [x] **Step 1: Document first-run index build**
Add the explicit `build-index` workflow against the global `overpass.json` and explain where the SQLite index lives by default.

- [x] **Step 2: Document second-run extraction reuse**
Explain that repeated country extraction should reuse the existing index and should no longer parse the full raw payload again.

- [x] **Step 3: Document fuzzy seed suggestions and failure handling**
Show how exact, normalized, and fuzzy lookup work, when `--auto-select-fuzzy` is allowed, and how to react to incompatible-index or stale-lock failures.

- [x] **Step 4: Update README summary**
Add a concise index-first workflow summary and point to the full runbook.