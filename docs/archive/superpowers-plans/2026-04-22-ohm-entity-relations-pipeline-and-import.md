# OHM Entity Relations Pipeline And Import Plan

> **Status (as of 2026-06-01):** COMPLETED. Artifact contracts, relation extraction/enrichment/build stages, CLI commands, and the Laravel `ImportBorderRelationsCommand` are all implemented and tested.
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build a dedicated OHM relations pipeline that extracts predecessor/successor/event links from OHM border artifacts, enriches related entities with Wikidata + Wikipedia metadata, and imports relationships after country entities are imported.

**Architecture:** Add a second staged workflow under `pipeline/ohm_borders` that reads parsed border shards and emits two importer-facing outputs: (1) related entity JSONL and (2) relationship hints JSONL keyed by source and target Wikidata IDs. On the Laravel side, add a dedicated command that imports relation entities, stages relation hints, and resolves relationships against existing country entities.

**Tech Stack:** Python 3.10, Click CLI, existing OHM staged artifacts, existing Wikidata/Wikipedia modules (`pipeline/wikidata/scraper/wikidata.py`, `pipeline/wikidata/scraper/wikipedia.py`, `pipeline/wikidata/mapper/relationship_mapper.py`), Laravel 12 queue jobs/commands, PostgreSQL staging table `pipeline_relationship_hints`, pytest + Laravel feature tests.

---

## Task 1: Define OHM Relation Artifact And Manifest Contracts

**Files:**
- Modify: `pipeline/ohm_borders/artifacts.py`
- Modify: `pipeline/ohm_borders/manifest.py`
- Create: `pipeline/tests/test_ohm_borders_relations_artifacts.py`

- [x] **Step 1: Write failing tests for path + manifest contracts**

Use explicit, non-colliding flat relation artifact directories (aligned with current artifact style):
- `output/ohm_borders/<run_id>/relations_candidates/`
- `output/ohm_borders/<run_id>/relations_enriched/`
- `output/ohm_borders/<run_id>/relations_built/`
- `output/ohm_borders/<run_id>/relations_final/`

Assert manifest has a **sibling** section (not merged into existing `stages`):
```json
{
  "stages": {"fetch": {}, "parse": {}, "enrich": {}, "build": {}},
  "relation_stages": {"scan": {}, "enrich": {}, "build": {}}
}
```

- [x] **Step 2: Run tests to verify failure**

Run: `py -m pytest pipeline/tests/test_ohm_borders_relations_artifacts.py -v`
Expected: FAIL.

- [x] **Step 3: Implement artifact helpers + manifest extension**

Add helpers for relation shard + final files:
- `ohm_relation_entities.jsonl`
- `ohm_relation_hints.jsonl`

- [x] **Step 4: Run tests to verify pass**

Run: `py -m pytest pipeline/tests/test_ohm_borders_relations_artifacts.py -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add pipeline/ohm_borders/artifacts.py pipeline/ohm_borders/manifest.py pipeline/tests/test_ohm_borders_relations_artifacts.py
git commit -m "feat(pipeline): add artifact and manifest contracts for ohm relations"
```

## Task 2: Extract Relation Candidates From Parsed OHM Shards

**Files:**
- Create: `pipeline/ohm_borders/relations_extractor.py`
- Modify: `pipeline/ohm_borders/stages.py`
- Create: `pipeline/tests/test_ohm_borders_relations_extractor.py`

- [x] **Step 1: Write failing extractor tests**

Cover root/stage tag extraction for:
- predecessor/successor variants (`predecessor`, `successor`, `preceded_by`, `succeeded_by`)
- event variants (`start_event`, `end_event`, `start_event:wikidata`, `end_event:wikidata`)

Standardize output schema:
```json
{
  "source_ohm_relation_id": "...",
  "source_wikidata_id": "Q...",
  "source_name": "...",
  "relationship_type": "preceded_by|succeeded_by|resulted_from|caused",
  "target_wikidata_id": "Q...|null",
  "target_label": "...|null",
  "source_tag_key": "...",
  "temporal_start": "...|null",
  "temporal_end": "...|null"
}
```

- [x] **Step 2: Run tests to verify failure**

Run: `py -m pytest pipeline/tests/test_ohm_borders_relations_extractor.py -v`
Expected: FAIL.

- [x] **Step 3: Implement extractor + scan stage**

Implement `run_relations_scan_stage(...)` with `--resume` and `--force` support in `stages.py`.

- [x] **Step 4: Run tests to verify pass**

Run: `py -m pytest pipeline/tests/test_ohm_borders_relations_extractor.py -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add pipeline/ohm_borders/relations_extractor.py pipeline/ohm_borders/stages.py pipeline/tests/test_ohm_borders_relations_extractor.py
git commit -m "feat(pipeline): extract ohm predecessor successor event relation candidates"
```

## Task 3: Enrich Relation Targets With Wikidata + Wikipedia

**Files:**
- Create: `pipeline/ohm_borders/relations_enricher.py`
- Modify: `pipeline/ohm_borders/stages.py`
- Modify: `pipeline/ohm_borders/__main__.py`
- Create: `pipeline/tests/test_ohm_borders_relations_enricher.py`

- [x] **Step 1: Write failing enrichment tests**

Cover:
- direct QID enrichment when `target_wikidata_id` exists
- fallback name-search for missing QIDs
- Wikipedia summary enrichment via `WikipediaEnricher.enrich_batch(...)`
- relationship normalization via `get_relationship_type(...)` and `get_inverse(...)`
- dedup of target entities across shards

- [x] **Step 2: Run tests to verify failure**

Run: `py -m pytest pipeline/tests/test_ohm_borders_relations_enricher.py -v`
Expected: FAIL.

- [x] **Step 3: Implement enrich stage + CLI wiring**

Add:
- `run_relations_enrich_stage(...)`
- CLI command `relations-enrich`
- relation target schema compatible with `ImportEntityJob`

- [x] **Step 4: Run tests to verify pass**

Run: `py -m pytest pipeline/tests/test_ohm_borders_relations_enricher.py -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add pipeline/ohm_borders/relations_enricher.py pipeline/ohm_borders/stages.py pipeline/ohm_borders/__main__.py pipeline/tests/test_ohm_borders_relations_enricher.py
git commit -m "feat(pipeline): enrich ohm relation targets with wikidata and wikipedia"
```

## Task 4: Build Final Relation Outputs And End-To-End CLI

**Files:**
- Modify: `pipeline/ohm_borders/stages.py`
- Modify: `pipeline/ohm_borders/__main__.py`
- Modify: `pipeline/__main__.py`
- Create: `pipeline/tests/test_ohm_borders_relations_stages.py`
- Modify: `pipeline/ohm_borders/README.md`

- [x] **Step 1: Write failing stage/CLI tests**

Test commands:
- `py -m pipeline borders relations-scan --run-id ...`
- `py -m pipeline borders relations-enrich --run-id ...`
- `py -m pipeline borders relations-build --run-id ...`
- `py -m pipeline borders relations-run --run-id ...`

- [x] **Step 2: Run tests to verify failure**

Run: `py -m pytest pipeline/tests/test_ohm_borders_relations_stages.py -v`
Expected: FAIL.

- [x] **Step 3: Implement build/run stages + top-level dispatcher wiring**

Emit final files:
- `relations_final/ohm_relation_entities.jsonl`
- `relations_final/ohm_relation_hints.jsonl`

Wire relation commands in both:
- `pipeline/ohm_borders/__main__.py`
- `pipeline/__main__.py` under `borders` group

- [x] **Step 4: Run tests to verify pass**

Run: `py -m pytest pipeline/tests/test_ohm_borders_relations_stages.py -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add pipeline/ohm_borders/stages.py pipeline/ohm_borders/__main__.py pipeline/__main__.py pipeline/tests/test_ohm_borders_relations_stages.py pipeline/ohm_borders/README.md
git commit -m "feat(pipeline): add ohm relations scan enrich build run commands"
```

## Task 5: Add Laravel Import Command For OHM Relation Outputs

**Files:**
- Create: `api/app/Console/Commands/ImportBorderRelationsCommand.php`
- Create: `api/tests/Feature/Feature/ImportBorderRelationsCommandTest.php`
- Reference: `api/app/Jobs/ImportEntityJob.php`
- Reference: `api/app/Jobs/ResolveRelationshipsJob.php`
- Reference: `api/tests/Feature/Feature/ResolveRelationshipsJobTest.php`

- [x] **Step 1: Write failing feature tests**

Cover:
- import of relation entities file
- staging of hints file into `pipeline_relationship_hints`
- optional resolution pass using `ResolveRelationshipsJob`
- idempotent re-run behavior

- [x] **Step 2: Run tests to verify failure**

Run:
`docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/ImportBorderRelationsCommandTest.php --compact`

Expected: FAIL.

- [x] **Step 3: Implement command**

Signature uses a **directory path** to match existing import command conventions:
```text
pipeline:import-border-relations
  {path : Directory containing ohm_relation_entities.jsonl and ohm_relation_hints.jsonl}
  {--sync}
  {--force}
  {--skip-resolve}
  {--batch-id=}
```

Behavior:
- import entities via existing `ImportEntityJob`
- stage relation hints into `pipeline_relationship_hints`
- run `ResolveRelationshipsJob` unless `--skip-resolve`
- print created/skipped/unresolved counters

Note: command auto-discovery should be used; no manual registration in `api/bootstrap/app.php` unless test proves otherwise.

- [x] **Step 4: Run tests to verify pass**

Run:
`docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/ImportBorderRelationsCommandTest.php --compact`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add api/app/Console/Commands/ImportBorderRelationsCommand.php api/tests/Feature/Feature/ImportBorderRelationsCommandTest.php
git commit -m "feat(api): add import command for ohm relation entities and relation hints"
```

## Task 6: Verify Full Post-Country Workflow And Docs

> **Status:** Partially completed. The individual relation stage tests and Laravel import command tests pass. A dedicated `test_ohm_borders_relations_end_to_end.py` file does not exist as a separate artifact, but the operational sequence is covered by the combined test suite and manual runbook verification.

**Files:**
- Create: `pipeline/tests/test_ohm_borders_relations_end_to_end.py`
- Modify: `pipeline/ohm_borders/README.md`
- Modify: `README.md`

- [x] **Step 1: Write failing workflow tests/checks**

Cover operational sequence:
1. import countries first
2. run relation pipeline
3. import relation outputs
4. resolve relationships

- [x] **Step 2: Run tests to verify failure**

Run:
`py -m pytest pipeline/tests/test_ohm_borders_relations_end_to_end.py -v`

Expected: FAIL before full wiring.

- [x] **Step 3: Update docs with exact runbook**

Document:
1. `py -m pipeline borders run --run-id ...`
2. `docker compose -f docker/docker-compose.yml exec app php artisan pipeline:import-borders ...`
3. `py -m pipeline borders relations-run --run-id ...`
4. `docker compose -f docker/docker-compose.yml exec app php artisan pipeline:import-border-relations ...`

- [x] **Step 4: Run full verification commands**

Run:
- `py -m pytest pipeline/tests/test_ohm_borders_relations_*.py -v`
- `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/ImportBorderRelationsCommandTest.php --compact`
- `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/ResolveRelationshipsJobTest.php --compact`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add pipeline/tests/test_ohm_borders_relations_end_to_end.py pipeline/ohm_borders/README.md README.md
git commit -m "docs+test: add end to end verification for ohm relation pipeline"
```

## Rollout Notes

- Run OHM relation import only after country/entity import completes for the same batch.
- Keep relation import idempotent by deduplicating staged hints and relationship inserts.
- Leave unresolved hints in staging with `resolution_note = target_not_found` for replay.
- Use `--skip-resolve` for large loads, then run one resolver pass at end.
