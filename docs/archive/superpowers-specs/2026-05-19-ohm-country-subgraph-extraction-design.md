# OHM Country Subgraph Extraction Design

**Context**

The OHM borders pipeline currently assumes a full Overpass fetch followed by parse, enrich, build, and relation stages over the entire `admin_level=2` dataset. For country-focused work, we need a smaller, repeatable workflow that can start from the existing global `overpass.json`, extract one seed polity plus its connected OHM border graph, and then reuse the existing staged pipeline without creating a second parsing model.

The target use case is a reusable "country module" workflow: extract a seed country such as the Roman Empire, include related OHM border relations in both forward and backward directions, enrich the resulting subset with the existing OHM/Wikidata stages, and produce importer-ready entity and relation outputs that remain connected when imported into Laravel.

**Goal**

Add a pre-stage to the OHM borders pipeline that extracts a bounded, bidirectional country-centered subgraph from an existing global Overpass payload and writes it back into the same artifact shape expected by the current parse/enrich/build/relation stages.

**Approach**

Use a compatibility-preserving staged design:
- keep the existing parse, enrich, build, and relation stages unchanged as much as possible
- add a new extraction command that reads `raw/overpass.json` from a prior global run
- resolve a seed polity by Wikidata ID first, with exact-name fallback for operator convenience
- expand recursively in both directions across OHM polity relations with bounded `max_depth` and `max_nodes`
- emit a reduced Overpass-shaped payload plus normal `raw/raw-*.jsonl` shards so downstream stages run unchanged
- validate graph closure before import by checking that relation outputs do not reference missing entities within the produced bundle

**Expansion model**

The extractor starts from a seed chronology relation or direct `admin_level=2` relation and recursively expands both backward and forward through OHM-derived connections.

Included edge sources:
- chronology membership: chronology relation to stage relations and stage relations back to chronology
- succession tags: `predecessor`, `preceded_by`, `successor`, `succeeded_by`
- event tags used in the current relation extractor: `start_event`, `end_event`
- Wikidata-linked relation targets when a target QID can be mapped back to another OHM `admin_level=2` relation or chronology in the same source dump

Default stop conditions use a hybrid safety model:
- `max_depth`: limits recursive hops from the seed
- `max_nodes`: limits included OHM relations overall

If either limit truncates the reachable graph, the extractor records that truncation explicitly in the closure report.

**CLI surface**

Add a new command under `python -m pipeline borders` and `python -m pipeline ohm-borders`:

`extract-subgraph`

Expected inputs:
- `--input`: path to an existing global `overpass.json`
- `--seed-qid`: preferred explicit seed
- `--seed-name`: exact-name fallback when no QID is provided
- `--run-id`: target artifact run identifier
- `--artifact-dir`: optional explicit artifact directory
- `--max-depth`: hop limit
- `--max-nodes`: node cap
- `--raw-shard-size`: relation shard size for the subset
- `--resume` and `--force`: same semantics as the rest of the staged pipeline

The command writes a subset artifact tree compatible with existing stages rather than a one-off export format.

**Artifact layout**

The subset run should preserve the current OHM layout and add a small subgraph metadata area.

Manifest handling:
- add a distinct `extract_subgraph` stage record rather than overloading `fetch`
- keep the existing `fetch`, `parse`, `enrich`, and `build` stage semantics unchanged for downstream steps
- record subset-run metadata in the manifest under the new stage summary so `--resume` can compare prior traversal parameters with the current invocation

Expected outputs under `output/ohm_borders/<run_id>/`:
- `raw/overpass.json`: reduced Overpass payload containing only the extracted relation subgraph
- `raw/raw-*.jsonl`: normal relation shards derived from the reduced payload
- `subgraph/seed.json`: resolved seed metadata and operator inputs
- `subgraph/graph_edges.jsonl`: extracted graph edges for audit/debugging
- `subgraph/closure_report.json`: inclusion counts, truncation details, unresolved references, and bundle-closure checks
- normal downstream stage outputs from parse, enrich, build, and relation stages

This design intentionally keeps parse-source detection compatible with the current stage contract: a run with subset `raw/overpass.json` still behaves like a normal fetched run.

Parse compatibility rule:
- the reduced `raw/overpass.json` is the canonical subset artifact
- `raw/raw-*.jsonl` shards are derived from that reduced payload for parity with existing artifact inspection and resume behavior
- downstream parse should continue to resolve a single input source exactly as it does today; the subset stage writes artifacts in the existing shape rather than changing parse to consume two sources at once

Reduced payload contract:
- preserve the top-level Overpass payload shape with an `elements` array
- preserve any lightweight top-level metadata fields already present in the source payload when practical
- relation elements included in the subset must remain structurally compatible with `parse_elements()` and relation subset parsing helpers

**Import integrity assumptions**

This plan assumes a strict import order rather than a Laravel retry queue for missing relation endpoints.

Operational rule:
- import border entities first
- import relation entities second
- resolve relation hints third

The first implementation must protect this workflow by validating bundle closure before import. The produced subset run should fail validation if relation hints reference Wikidata IDs that are missing from the combined entity outputs generated by the same run.

Closure validation contract:
- validation runs automatically at the end of relation build for subset runs
- the validation set is the union of Wikidata IDs present in the built main OHM entity output and `relations_final/ohm_relation_entities.jsonl`
- the checked references are every non-empty `source_wikidata_id` and `target_wikidata_id` emitted into relation hints for the same run
- a missing referenced ID marks the run as validation-failed in `closure_report.json`
- validation failure does not delete artifacts, but it is treated as a hard failure for import readiness and must be surfaced in command output and documentation

Deferred work:
- a later Laravel plan may add retryable staging for unresolved source or target entities, but that is explicitly out of scope here

**Components**

- `pipeline/ohm_borders/subgraph_extractor.py`
  Core extraction logic: seed resolution, adjacency indexing, recursive expansion, closure report assembly.
- `pipeline/ohm_borders/stage_extract_subgraph.py`
  Stage-style orchestration: artifact resolution, manifest updates, reduced payload writing, shard materialization.
- `pipeline/ohm_borders/__main__.py`
  New `extract-subgraph` CLI command wired into the existing borders surface.
- `pipeline/__main__.py`
  Legacy dispatcher exposure so the top-level `borders` group can call the new command.
- `pipeline/tests/...`
  Focused extraction tests, CLI tests, and closure-validation coverage.
- `docs/implementation-docs/...`
  Operator-facing runbook for first run and second-run reuse.

**Validation and testing strategy**

The implementation must include focused tests and operator validation guidance.

Python test coverage:
- seed resolution and exact-name fallback
- bidirectional graph expansion across chronology and succession links
- `max_depth` and `max_nodes` truncation behavior
- reduced Overpass payload and raw shard emission
- closure report generation and missing-target detection
- manifest updates for subset runs and traversal parameter persistence
- seed ambiguity and seed-not-found failures
- rerun parameter drift detection for `--resume`
- CLI smoke coverage for the new command
- regression coverage that a subset run can be consumed by existing parse and relation stages

Operator validation guidance:
- run the extractor against a small fixture payload first
- run parse, enrich, build, and relations on the subset artifact directory
- inspect `closure_report.json` before import
- for second runs, prefer `--resume` and verify that the subset manifest and raw outputs are reused unless `--force` is provided

**Second-run behavior**

The workflow must be safe to rerun for the same target country.

Requirements:
- `--resume` should skip rewriting subset artifacts when inputs and outputs already exist
- `--resume` must compare the current extraction inputs against the prior manifest summary at minimum for source input path, seed identity, `max_depth`, `max_nodes`, and `raw_shard_size`
- if those values differ, the command should fail fast with guidance to rerun using `--force` or a new `run_id`
- `--force` should rebuild the subset payload and downstream artifacts for the run
- the guide must document how to reuse an existing subset run for additional enrichment/relation passes without re-extracting unless the seed or traversal parameters change
- the closure report should record traversal parameters so rerun drift is visible

Seed resolution rules:
- if both `--seed-qid` and `--seed-name` are provided, QID takes priority and name is recorded only as operator context
- exact-name fallback must fail with a clear error if it matches zero or multiple candidate seed relations
- if a single Wikidata QID maps to multiple eligible OHM polity roots, include all matching roots in the initial frontier and record that fan-out in the closure report

**Non-goals**

- No change to the existing full OHM fetch query or global pipeline semantics
- No Laravel-side retry mechanism for missing relation endpoints in this plan
- No cultural or thematic Wikidata relevance-ranking work yet; that remains a follow-on project after the subset OHM workflow is in place