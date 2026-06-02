# OHM Country Subgraph Extraction Implementation Plan

> **Status (as of 2026-06-01):** COMPLETED. The extractor, stage orchestration, CLI wiring, and runbook are all implemented. `subgraph_extractor.py` and `stage_extract_subgraph.py` exist; tests pass.
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add a staged extractor that carves a country-centered OHM relation subgraph from an existing global `overpass.json`, then feeds that subset through the existing parse, enrich, build, and relation workflows with closure validation and rerun documentation.

**Architecture:** Introduce a new pre-stage that writes a reduced Overpass payload plus normal raw shards into a standard OHM artifact directory. Keep downstream parse and relation stages unchanged, validate bundle closure before import, and document both first-run and second-run operator flows.

**Tech Stack:** Python 3.10+, Click CLI, existing OHM stage helpers, JSONL artifact pipeline, pytest, Laravel import runbook assumptions.

---

### Task 1: Add failing extraction-core tests

**Files:**
- Create: `pipeline/tests/test_ohm_country_subgraph_extractor.py`

- [x] **Step 1: Write a fixture-sized graph test for bidirectional expansion**
Add a fixture payload with a seed chronology, predecessor/successor-linked relations, and at least one branch that should be excluded by depth.

- [x] **Step 2: Write closure-report contract tests**
Assert that the extractor reports inclusion counts, truncation details, unresolved references, traversal parameters, and missing referenced Wikidata IDs when a relation target cannot be closed inside the bundle.

- [x] **Step 3: Write stop-condition tests**
Cover both `max_depth` and `max_nodes` truncation so the extractor contract is fixed before implementation.

- [x] **Step 4: Write seed failure and ambiguity tests**
Cover seed-not-found, ambiguous exact-name matches, and the priority rule where `--seed-qid` overrides `--seed-name`.

- [x] **Step 5: Run the targeted tests to verify they fail**
Run: `py -m pytest pipeline/tests/test_ohm_country_subgraph_extractor.py -v`
Expected: FAIL because the extractor module and behavior do not exist yet.

### Task 2: Implement the extraction core

**Files:**
- Create: `pipeline/ohm_borders/subgraph_extractor.py`

- [x] **Step 1: Implement seed resolution helpers**
Support seed lookup by explicit QID and exact-name fallback within the provided Overpass payload.

- [x] **Step 2: Implement adjacency indexing and recursive traversal**
Index chronology links, succession/event tag links, and OHM relation/QID mappings so traversal can expand forward and backward.

- [x] **Step 3: Implement reduced payload and graph-edge output builders**
Return included relation elements plus audit-oriented edge records.

- [x] **Step 4: Implement closure-report generation**
Record included nodes, truncation reasons, unresolved references, and traversal parameters.

- [x] **Step 5: Implement explicit QID-to-OHM mapping rules**
Handle QIDs that map to zero, one, or multiple eligible OHM polity roots and record the outcome for auditability.

- [x] **Step 6: Run focused extractor tests**
Run: `py -m pytest pipeline/tests/test_ohm_country_subgraph_extractor.py -v`
Expected: PASS.

### Task 3: Add the staged subgraph extraction entrypoint

**Files:**
- Create: `pipeline/ohm_borders/stage_extract_subgraph.py`
- Modify: `pipeline/ohm_borders/artifacts.py`
- Modify: `pipeline/ohm_borders/stage_common.py`

- [x] **Step 1: Add artifact helpers for subgraph outputs**
Define paths for `subgraph/seed.json`, `subgraph/graph_edges.jsonl`, and `subgraph/closure_report.json`.

- [x] **Step 2: Implement `run_extract_subgraph_stage`**
Make it read an existing global `overpass.json`, call the extractor, write the reduced `raw/overpass.json`, materialize `raw-*.jsonl`, and update the manifest.

- [x] **Step 3: Preserve resume/force semantics**
Ensure a second run with `--resume` reuses subset artifacts and `--force` rebuilds them.

- [x] **Step 4: Persist and compare traversal parameters in the manifest**
Store source input path, seed identity, `max_depth`, `max_nodes`, and `raw_shard_size`; fail fast on `--resume` drift unless `--force` is supplied.

- [x] **Step 5: Add focused stage tests**
Extend or add tests covering artifact writing, manifest updates, validation status, and rerun behavior.

- [x] **Step 6: Run the targeted stage tests**
Run: `py -m pytest pipeline/tests/test_ohm_country_subgraph_extractor.py -k stage -v`
Expected: PASS.

### Task 4: Wire the CLI surface

**Files:**
- Modify: `pipeline/ohm_borders/__main__.py`
- Modify: `pipeline/__main__.py`

- [x] **Step 1: Add the `extract-subgraph` command to the OHM borders CLI**
Expose `--input`, `--seed-qid`, `--seed-name`, `--run-id`, `--artifact-dir`, `--max-depth`, `--max-nodes`, `--raw-shard-size`, `--resume`, and `--force`.

- [x] **Step 2: Expose the same command via the top-level legacy dispatcher**
Keep the `python -m pipeline borders ...` interface consistent with current usage.

- [x] **Step 3: Add CLI coverage**
Add or extend tests that invoke the command with a fixture payload and assert artifact creation.

- [x] **Step 4: Run focused CLI tests**
Run: `py -m pytest pipeline/tests/test_ohm_country_subgraph_extractor.py -k cli -v`
Expected: PASS.

### Task 5: Prove downstream compatibility

**Files:**
- Modify: `pipeline/tests/test_ohm_country_subgraph_extractor.py`
- Reuse existing tests where possible

- [x] **Step 1: Add an integration-style test for parse compatibility**
Run the new extraction stage on a fixture payload, then run existing parse logic against the subset artifact directory.

- [x] **Step 2: Add a relation-stage compatibility test**
Verify a subset run can produce relation candidates and closure metadata without breaking the current relation extractor assumptions.

- [x] **Step 3: Implement import-readiness validation**
Add the validation logic that compares relation hint Wikidata references against the combined entity outputs and marks the subset run as not import-ready when closure fails.

- [x] **Step 4: Add tests for import-readiness validation**
Verify both passing and failing bundle-closure cases and assert the validation result is persisted in `closure_report.json`.

- [x] **Step 5: Run focused downstream tests**
Run: `py -m pytest pipeline/tests/test_ohm_country_subgraph_extractor.py -k "parse or relation" -v`
Expected: PASS.

### Task 6: Write the reusable operator guide

**Files:**
- Create: `docs/implementation-docs/ohm_country_subgraph_runbook.md`
- Modify: `pipeline/ohm_borders/README.md`

- [x] **Step 1: Write a first-run guide**
Document how to point the extractor at the global `output/ohm_borders/global-2026-04-14/raw/overpass.json`, choose a seed, run the subset extractor, then run parse/enrich/build/relations.

- [x] **Step 2: Add second-run guidance**
Document `--resume`, `--force`, and how to reuse an existing subset artifact directory safely.

- [x] **Step 3: Add validation, seed-failure, and import-order guidance**
Explain how to inspect `closure_report.json`, handle seed ambiguity/failure, import entities first, then relation entities, then resolve relations.

- [x] **Step 4: Update the OHM borders README**
Add a concise section that points operators to the full runbook and shows the high-level subset workflow.

### Task 7: Run end-to-end focused verification

**Files:**
- Verify only

- [x] **Step 1: Run the new extractor test file**
Run: `py -m pytest pipeline/tests/test_ohm_country_subgraph_extractor.py -v`
Expected: PASS.

- [x] **Step 2: Run existing OHM relation tests affected by the new workflow**
Run: `py -m pytest pipeline/tests/test_ohm_borders_relations_extractor.py pipeline/tests/test_ohm_borders_relations_stages.py -v`
Expected: PASS.

- [x] **Step 3: Run existing OHM stage tests that cover artifact flow**
Run: `py -m pytest pipeline/tests/test_ohm_borders_stages.py -v`
Expected: PASS.

- [x] **Step 4: Perform a manual CLI smoke test against a small fixture or subset payload**
Run: `py -m pipeline borders extract-subgraph --input <fixture-overpass.json> --seed-qid <qid> --run-id smoke-subgraph`
Expected: subset artifacts are written and reusable by parse.