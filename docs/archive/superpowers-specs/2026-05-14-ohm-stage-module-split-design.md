# OHM Stage Module Split Design

**Context**

`pipeline/ohm_borders/stages.py` currently contains stage entrypoints, worker initialization, manifest helpers, JSONL/artifact helpers, and relation-stage helpers in a single 1700+ line file. This makes the module difficult to navigate and is a likely contributor to GitNexus failing while extracting scopes from the file.

**Goal**

Split the OHM stage implementation into smaller, responsibility-focused modules while preserving the existing public API exposed from `pipeline.ohm_borders.stages`.

**Approach**

Use a compatibility facade:
- keep `pipeline/ohm_borders/stages.py` as the stable import surface
- move common helper logic into a shared internal module
- move each stage family into its own module
- re-export the existing public functions from `stages.py`

**Proposed module boundaries**

- `pipeline/ohm_borders/stage_common.py`
  Shared helpers used across multiple stages: artifact resolution, manifest updates, JSONL IO, sorting, enrichment index loading, shared worker constants.
- `pipeline/ohm_borders/stage_fetch.py`
  `run_fetch_stage` and raw-shard materialization logic.
- `pipeline/ohm_borders/stage_parse.py`
  `run_parse_stage` and parse worker / relation lookup helpers.
- `pipeline/ohm_borders/stage_enrich.py`
  `run_enrich_stage` and enrichment-specific shard batching helpers.
- `pipeline/ohm_borders/stage_build.py`
  `run_build_stage` and build worker / final assembly helpers.
- `pipeline/ohm_borders/stage_relations.py`
  `run_relations_scan_stage`, `run_relations_enrich_stage`, `run_relations_build_stage`.
- `pipeline/ohm_borders/stages.py`
  Small compatibility layer re-exporting the public API.

**Compatibility requirements**

- Existing imports from `pipeline.ohm_borders.stages` must continue to work unchanged.
- CLI behavior in `pipeline/ohm_borders/__main__.py` and `pipeline/__main__.py` must remain unchanged.
- Existing pipeline tests should remain the primary regression safety net.

**Testing strategy**

- Add a focused compatibility test that imports stage entrypoints from `pipeline.ohm_borders.stages` and verifies they still resolve.
- Run the existing OHM stage-focused pytest files after the split.

**Non-goals**

- No behavior changes to fetch/parse/enrich/build semantics.
- No CLI or artifact-format changes.
- No unrelated cleanup inside the stage logic beyond what is required for the split.
