# Event Relationship Pipeline Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make multi-entity events import and render reliably by formalizing the event-as-hub relationship model, fixing batch relationship resolution, and making unresolved relationship hints visible and retryable.

**Architecture:** Preserve the current binary `relationships` table as the canonical graph edge store and standardize multi-party events as event-centered clusters of pairwise edges. Stabilize the pipeline around deterministic two-phase import, a single relationship-mapping source of truth, and explicit unresolved-hint review instead of silent loss.

**Tech Stack:** Laravel 13, PHP 8.4, PostgreSQL 16, PostGIS, Python pipeline CLI, JSONL batch import, PHPUnit feature tests, Python `pytest` tests for pipeline modules, documentation in `docs/entity-model` and `docs/implementation-docs`.

**Execution Root:** Unless a step says otherwise, run commands from the repository root: `C:\Users\Achi\Code\FL\history-mapped`.

---

## Scope

This plan deliberately does **not** introduce a true n-ary relationship table in the first pass. The implementation target is:

- battles, treaties, migrations, and other multi-party events remain modeled as an event entity plus multiple binary edges
- the pipeline must resolve those edges deterministically for one batch without dropping late-arriving targets
- ambiguous or unsupported source facts must remain reviewable instead of being silently flattened into misleading edges

Out of scope for this plan:

- full replacement of `relationships` with an event-participation schema
- major authoring UI redesign
- retrofitting all historical semantics into one release

---

## Canonical Modeling Rules

The implementation should codify these rules in docs and tests:

- A multi-entity event is represented as one event node plus many binary edges.
- Event membership is expressed through repeated pairwise relations, not one row containing all participants.
- Place linkage is separate from participant linkage.
- Works and historians are linked through authorship and subject relations, not treated as event participants unless source data explicitly says so.

Battle example for target behavior:

- `Army A -> participated_in -> Battle of Gaugamela`
- `Army B -> participated_in -> Battle of Gaugamela`
- `Alexander -> commanded -> Macedonian Army`
- `Alexander -> victorious_at -> Battle of Gaugamela`
- `Darius III -> defeated_at -> Battle of Gaugamela`
- `Battle of Gaugamela -> part_of -> Wars of Alexander`
- `Battle of Gaugamela -> located_at -> Gaugamela region` or equivalent canonical place relation
- `Arrian -> authored -> Anabasis of Alexander`
- `Anabasis of Alexander -> source/subject link -> Battle of Gaugamela` only when that relation vocabulary is explicitly supported

---

### Task 1: Write the Event-Hub Modeling Spec

**Files:**
- Modify: `docs/entity-model/for-historians.md`
- Modify: `docs/entity-model/diagrams.md`
- Modify: `docs/implementation-docs/data_pipeline_architecture.md`
- Create: `docs/implementation-docs/event-relationship-ingestion-rules.md`

- [ ] **Step 1: Write the failing documentation checklist**

Document these required statements before editing:

- multi-party events use event-centered binary edges
- a battle example with at least 6 linked entities
- unsupported compound assertions are flagged for review rather than guessed
- place, participant, commander, source-work, and historian roles are explicitly separated

- [ ] **Step 2: Draft the canonical battle example**

Write one battle example showing:

- participant entities
- place entity linkage
- commander linkage
- source-work linkage
- which facts belong in `relationships` versus citations or notes

- [ ] **Step 3: Draft the canonical treaty example**

Write one treaty example showing:

- signatory linkage
- location linkage
- mediator linkage
- source-work linkage
- which facts are unsupported without a richer schema

- [ ] **Step 4: Update `for-historians.md`**

Add a historian-facing explanation of the event-hub model and both examples.

- [ ] **Step 5: Update `diagrams.md`**

Add one explicit note that `relationships` stores binary edges and event clusters are reconstructed by traversal.

- [ ] **Step 6: Update `data_pipeline_architecture.md`**

Add one section explaining how `_relationship_hints` become event-centered edges during import.

- [ ] **Step 7: Create `event-relationship-ingestion-rules.md`**

Add this checklist verbatim as the initial seed:

```md
- Participant edges are emitted per entity, not as one compound row.
- Missing target entities remain reviewable and retryable.
- Unsupported compound facts are retained for audit instead of guessed.
```

- [ ] **Step 8: Review docs for terminology consistency**

Verify the docs consistently use:

- `event-centered graph`
- `binary edge`
- `unresolved hint`
- `reviewable failure`

- [ ] **Step 9: Commit**

```bash
git add docs/entity-model/for-historians.md docs/entity-model/diagrams.md docs/implementation-docs/data_pipeline_architecture.md docs/implementation-docs/event-relationship-ingestion-rules.md
git commit -m "docs: define event-centered relationship ingestion model"
```

### Task 2: Make Relationship Resolution Retryable and Batch-Safe

**Files:**
- Modify: `api/app/Console/Commands/ImportEntitiesCommand.php`
- Create: `api/app/Console/Commands/ResolvePipelineRelationshipsCommand.php`
- Modify: `api/app/Jobs/ResolveRelationshipsJob.php`
- Test: `api/tests/Feature/Feature/ResolveRelationshipsJobTest.php`
- Test: create `api/tests/Feature/Feature/ResolvePipelineRelationshipsCommandTest.php`

- [ ] **Step 1: Write the failing staging-table retryability tests**

Add coverage for:

- unresolved targets remain retryable instead of finalized
- rerunning the resolver after the target entity exists creates the relationship
- duplicate reruns remain idempotent

Example assertion:

```php
$this->assertDatabaseHas('pipeline_relationship_hints', [
	'target_wikidata_id' => 'Q9999',
	'resolved' => false,
]);
```

- [ ] **Step 2: Write the failing fallback-path retryability test**

Add coverage for the embedded-hint fallback path so unresolved hints are not deleted from entity attributes when the target is still missing.

- [ ] **Step 3: Run the focused resolver tests to verify failure**

Run: `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/ResolveRelationshipsJobTest.php`
Expected: FAIL because `target_not_found` is currently terminal and the fallback path deletes unresolved embedded hints.

- [ ] **Step 4: Change staging-table resolution semantics in `ResolveRelationshipsJob`**

Implement these rules:

- unresolved target rows must not be marked fully resolved
- use a distinct retryable note or leave `resolved=false`
- only final invalid states such as `unknown_type` and `self_reference` should be terminal
- successful creation and true dedup should remain terminal

- [ ] **Step 5: Change fallback attribute resolution semantics in `ResolveRelationshipsJob`**

Implement these rules for the embedded-hint path:

- unresolved embedded hints must remain stored on the entity
- only successfully created or terminally invalid hints may be removed from attributes
- add code comments explaining why retryability matters here

- [ ] **Step 6: Write the failing command test for explicit batch resolution**

Cover this contract:

- `php artisan pipeline:resolve-relationships {batchId}` resolves one batch on demand
- the command is safe to rerun
- the command reports counts for created, retryable, and terminal hints

- [ ] **Step 7: Run the command test to verify failure**

Run: `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/ResolvePipelineRelationshipsCommandTest.php`
Expected: FAIL because the command does not exist yet.

- [ ] **Step 8: Add explicit batch-finalization command flow**

Implement this behavior:

- `--sync` mode continues to resolve relationships inline after entity creation
- async import mode prints a warning that relationship resolution must be triggered after workers drain
- new `pipeline:resolve-relationships {batchId}` command invokes `ResolveRelationshipsJob` deterministically for that batch

- [ ] **Step 9: Verify the new command is registered**

Run: `docker compose -f docker/docker-compose.yml exec app php artisan list | grep pipeline:resolve-relationships`
Expected: one matching command entry is shown.

- [ ] **Step 10: Rerun resolver and command tests**

Run: `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/ResolveRelationshipsJobTest.php tests/Feature/Feature/ResolvePipelineRelationshipsCommandTest.php`
Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add api/app/Console/Commands/ImportEntitiesCommand.php api/app/Console/Commands/ResolvePipelineRelationshipsCommand.php api/app/Jobs/ResolveRelationshipsJob.php api/tests/Feature/Feature/ResolveRelationshipsJobTest.php api/tests/Feature/Feature/ResolvePipelineRelationshipsCommandTest.php
git commit -m "fix: make pipeline relationship resolution retryable and explicit"
```

### Task 3: Unify Relationship Mapping Logic

**Files:**
- Modify: `pipeline/requirements.txt`
- Create: `pipeline/tests/__init__.py`
- Modify: `pipeline/mapper/entity_mapper.py`
- Modify: `pipeline/mapper/relationship_mapper.py`
- Test: create `pipeline/tests/test_relationship_mapper.py`
- Test: create `pipeline/tests/test_entity_mapper_relationship_hints.py`

- [ ] **Step 1: Add the Python test harness dependency and test package stub**

Make these preparatory changes:

- add `pytest>=8.0.0` to `pipeline/requirements.txt`
- create `pipeline/tests/__init__.py`

- [ ] **Step 2: Write the failing Python tests for mapping behavior**

Add coverage for:

- one shared mapping source is used for hint extraction
- `P710` uses entity-type context correctly
- battle participants are emitted as event-centered hints
- invalid or unsupported properties are skipped explicitly
- no mapping drift exists between extraction and helper utilities

Example test shape:

```python
def test_treaty_participants_map_to_signed_by():
	assert get_relationship_type("P710", source_entity_type="event_treaty") == "signed_by"
```

- [ ] **Step 3: Install pipeline test dependencies**

- Run: `Set-Location pipeline; pip install -r requirements.txt`

- [ ] **Step 4: Run the mapper tests to verify failure**

Run: `Set-Location pipeline; pytest tests/test_relationship_mapper.py tests/test_entity_mapper_relationship_hints.py -q`
Expected: FAIL because `entity_mapper.py` currently maintains its own inline property map.

- [ ] **Step 5: Refactor `entity_mapper.py` to consume shared mapping helpers**

Requirements:

- use `relationship_mapper.py` as the single source of truth
- keep context-sensitive mappings in one place
- preserve current JSONL `_relationship_hints` shape unless an explicit migration is required
- document any intentionally unsupported properties

- [ ] **Step 6: Rerun Python mapping tests**

Run: `Set-Location pipeline; pytest tests/test_relationship_mapper.py tests/test_entity_mapper_relationship_hints.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add pipeline/requirements.txt pipeline/tests/__init__.py pipeline/mapper/entity_mapper.py pipeline/mapper/relationship_mapper.py pipeline/tests/test_relationship_mapper.py pipeline/tests/test_entity_mapper_relationship_hints.py
git commit -m "refactor: unify pipeline relationship mapping"
```

### Task 4: Add Reviewable Unresolved-Hint Reporting

**Files:**
- Modify: `api/app/Jobs/ResolveRelationshipsJob.php`
- Create: `api/app/Console/Commands/ReportPipelineRelationshipHintsCommand.php`
- Test: create `api/tests/Feature/Feature/ReportPipelineRelationshipHintsCommandTest.php`
- Modify: `docs/implementation-docs/data_pipeline_architecture.md`

- [ ] **Step 1: Write the failing command test for unresolved-hint reporting**

The report must distinguish:

- retryable missing targets
- terminal invalid relationship types
- self references
- deduplicated rows
- successfully created rows
- fallback embedded hints still awaiting resolution

- [ ] **Step 2: Run the command test to verify failure**

Run: `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/ReportPipelineRelationshipHintsCommandTest.php`
Expected: FAIL because the reporting command does not exist.

- [ ] **Step 3: Implement the batch summary output block**

Print counts by `batch_id` and total rows by resolution class.

- [ ] **Step 4: Implement the unresolved staging-table sample block**

Print sample unresolved rows including `target_wikidata_id` and current retryability state.

- [ ] **Step 5: Implement the unresolved embedded-hint sample block**

Print sample entities whose attributes still contain unresolved `_relationship_hints`.

- [ ] **Step 6: Verify the new reporting command is registered**

Run: `docker compose -f docker/docker-compose.yml exec app php artisan list | grep pipeline:report-relationship-hints`
Expected: one matching command entry is shown.

- [ ] **Step 7: Rerun the command test**

Run: `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/ReportPipelineRelationshipHintsCommandTest.php`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add api/app/Jobs/ResolveRelationshipsJob.php api/app/Console/Commands/ReportPipelineRelationshipHintsCommand.php api/tests/Feature/Feature/ReportPipelineRelationshipHintsCommandTest.php docs/implementation-docs/data_pipeline_architecture.md
git commit -m "feat: report unresolved pipeline relationship hints"
```

### Task 5: Add Regression Coverage for Event-Derived Presence and Timeline Projection

**Files:**
- Modify: `api/app/Builders/EntityTimelineEntryBuilder.php`
- Test: `api/tests/Feature/Api/EntityTimelineApiTest.php`
- Test: `api/tests/Feature/Admin/RelationshipControllerTest.php`

- [ ] **Step 1: Add the non-auto presence regression test**

Extend `RelationshipControllerTest.php` so `participated_in` explicitly behaves like other non-auto relationship types and does not create `geometry_periods`.

- [ ] **Step 2: Add the event-hub timeline regression test**

Extend `EntityTimelineApiTest.php` with a battle-cluster scenario that asserts relationship type and related event name are still denormalized correctly.

- [ ] **Step 3: Run the focused relationship and timeline tests**

Run: `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Api/EntityTimelineApiTest.php tests/Feature/Admin/RelationshipControllerTest.php`
Expected: either FAIL on the new event-hub regression scenario or PASS and confirm no code change is needed.

- [ ] **Step 4: If the new regression test fails, update timeline-entry denormalization only**

Allowed code-change scope:

- preserve the current auto-derived presence allowlist
- fix only event-hub timeline denormalization gaps exposed by the new test
- do not widen auto-presence to generic `participated_in`

- [ ] **Step 5: Rerun focused tests**

Run: `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Api/EntityTimelineApiTest.php tests/Feature/Admin/RelationshipControllerTest.php`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add api/app/Builders/EntityTimelineEntryBuilder.php api/tests/Feature/Api/EntityTimelineApiTest.php api/tests/Feature/Admin/RelationshipControllerTest.php
git commit -m "test: lock event-derived presence and timeline semantics"
```

### Task 6: Add an End-to-End Multi-Entity Event Import Verification Test

**Files:**
- Test: create `api/tests/Feature/Feature/PipelineEventHubImportTest.php`

- [ ] **Step 1: Write the failing end-to-end import test**

Scenario:

- seed JSONL-like records for a battle, two armies, two commanders, and one place
- import them into one batch
- run `pipeline:resolve-relationships {batchId}`
- assert the final graph contains the expected event-centered edges
- assert no relationship was lost because a target entity arrived later in the batch

- [ ] **Step 2: Run the end-to-end test to verify failure**

Run: `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/PipelineEventHubImportTest.php`
Expected: If this test is authored before Tasks 2 and 3 land, it should FAIL; otherwise it becomes the final confirmation test for those tasks.

- [ ] **Step 3: After Tasks 2 and 3 land, rerun the end-to-end test**

Run: `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/PipelineEventHubImportTest.php`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add api/tests/Feature/Feature/PipelineEventHubImportTest.php
git commit -m "test: verify end-to-end event hub pipeline import"
```

---

## Validation Sequence

- [ ] `Set-Location pipeline; pip install -r requirements.txt`
- [ ] `Set-Location pipeline; pytest tests/test_relationship_mapper.py tests/test_entity_mapper_relationship_hints.py -q`
- [ ] `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/ResolveRelationshipsJobTest.php`
- [ ] `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/ResolvePipelineRelationshipsCommandTest.php`
- [ ] `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/ReportPipelineRelationshipHintsCommandTest.php`
- [ ] `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Api/EntityTimelineApiTest.php tests/Feature/Admin/RelationshipControllerTest.php`
- [ ] `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Feature/Feature/PipelineEventHubImportTest.php`

Recommended final sweep:

- [ ] `docker compose -f docker/docker-compose.yml exec app php artisan test`

---

## Decision Gates

Stop and escalate to human review if any of these occur:

- the team decides event-participant role metadata must be first-class in this release
- source data regularly requires one fact to bind more than two entities atomically
- battle/treaty authoring requires side, contingent, casualty, or rank metadata that cannot fit cleanly in binary edges
- async queue guarantees for import batches cannot be made trustworthy without broader job orchestration changes

If any gate is triggered, write a follow-up design for a dedicated event participation schema before continuing.

---

## Expected Outcome

After this plan is complete:

- the repository has a documented canonical answer for how multi-party events are represented
- the pipeline no longer silently loses relationship edges due to target timing
- unresolved relationship hints are visible, retryable, and auditable
- event-driven timeline and map projections remain semantically conservative
- the codebase is ready for a later decision on whether a dedicated participation table is actually needed