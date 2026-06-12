# Chronicle Data-Model Completion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Chronicle feature consistent end-to-end: editing no longer 500s, `source_evidence` is a jsonb array everywhere, `narrative_text` is consistently required, and the June-11 temporal/impact/location fields round-trip through web + API and are populated by the importer.

**Architecture:** Five thin changes across the Chronicle slice — a `text→jsonb` migration + model cast, a slug-unique fix, a required-field fix, FormRequest/serializer field additions, and an importer update. No structural redesign.

**Tech Stack:** Laravel 13 (PHP 8), PostgreSQL 16 (jsonb), PHPUnit.

**Spec:** [../specs/2026-06-12-chronicle-data-model-completion-design.md](../specs/2026-06-12-chronicle-data-model-completion-design.md)

---

## File structure

| File | Change |
|------|--------|
| `api/database/migrations/2026_06_12_000002_chronicle_source_evidence_jsonb.php` | Create: `source_evidence` text→jsonb |
| `api/app/Models/ChronicleEntry.php` | Add `'source_evidence' => 'array'` cast |
| `api/app/Http/Requests/Web/UpdateChronicleRequest.php` | Fix slug-unique; add June-11 fields; require narrative_text |
| `api/app/Http/Requests/Web/StoreChronicleRequest.php` | Add June-11 fields; require narrative_text |
| `api/app/Actions/Chronicle/CreateChronicleAction.php` / `UpdateChronicleAction.php` | Coalesce narrative_text; store new fields |
| `api/app/Http/Api/V1/Resources/ChronicleResource.php` / `ChronicleEntryResource.php` | Emit June-11 fields |
| `api/app/Http/Controllers/Web/ChronicleController.php` | `serializeChronicle` emits June-11 fields |
| `api/app/Console/Commands/ImportChroniclesCommand.php` | Persist June-11 fields; list source_evidence |

> Run: `docker compose -f docker/docker-compose.yml exec app php artisan test --filter=<name>`.

---

## Task 1: Migrate `source_evidence` text→jsonb (LC-4)

**Files:** Create `api/database/migrations/2026_06_12_000002_chronicle_source_evidence_jsonb.php`; Test `api/tests/Feature/ChronicleSourceEvidenceTest.php` (new)

- [ ] **Step 1: Write the failing test** — create a `ChronicleEntry` with `source_evidence => ['event:0']`, reload, assert it reads back as an array `['event:0']`.
- [ ] **Step 2: Run → FAIL** (column is text, no cast). `... artisan test --filter=ChronicleSourceEvidenceTest`
- [ ] **Step 3: Write the migration**

```php
public function up(): void {
    DB::statement("ALTER TABLE chronicle_entries
        ALTER COLUMN source_evidence TYPE jsonb
        USING CASE WHEN source_evidence IS NULL THEN NULL
                   ELSE jsonb_build_array(source_evidence) END");
}
public function down(): void {
    DB::statement("ALTER TABLE chronicle_entries
        ALTER COLUMN source_evidence TYPE text
        USING CASE WHEN source_evidence IS NULL THEN NULL
                   ELSE (source_evidence->>0) END");
}
```

- [ ] **Step 4: Add the cast** — in `ChronicleEntry.php` `$casts`, add `'source_evidence' => 'array'`.
- [ ] **Step 5: Run → PASS** (`... artisan migrate` then the test).
- [ ] **Step 6: Commit** `feat(api): chronicle source_evidence as jsonb array`

## Task 2: Fix the slug-unique 500 on edit (LC-2)

**Files:** Modify `UpdateChronicleRequest.php:26`; Test `api/tests/Feature/Web/ChronicleUpdateTest.php` (new)

- [ ] **Step 1: Write the failing test** — create a chronicle, then PUT `/chronicles/{slug}` resubmitting the same slug; assert 200/302 (not 500).
- [ ] **Step 2: Run → FAIL** (PG `column "id" does not exist`).
- [ ] **Step 3: Implement** — resolve the chronicle from the `{slug}` route param once (cache on the request), and use `Rule::unique('chronicles','slug')->ignore($chronicle->chronicle_id, 'chronicle_id')`.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `fix(api): chronicle slug-unique rule ignores own record on update`

## Task 3: Require `narrative_text` (LC-5)

**Files:** Modify `StoreChronicleRequest.php`, `UpdateChronicleRequest.php`, `CreateChronicleAction.php:63`, `UpdateChronicleAction.php`; Test `ChronicleNarrativeRequiredTest.php` (new)

- [ ] **Step 1: Write the failing test** — POST a chronicle with an entry omitting `narrative_text` → 422 (not a 500 NOT NULL).
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — change the rule to `['required','string']` (within the `entries.*` block); defensively coalesce `'narrative_text' => $entryData['narrative_text'] ?? ''` in both actions.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `fix(api): require chronicle entry narrative_text`

## Task 4: June-11 fields editable + serialized (LC-6)

**Files:** Modify both FormRequests, `ChronicleResource.php`, `ChronicleEntryResource.php`, `ChronicleController.php` (`serializeChronicle`); Test `ChronicleExtendedFieldsTest.php` (new)

- [ ] **Step 1: Write the failing round-trip test** — POST a chronicle with `start_year`/`end_year`/`impact_score`/`approximate_location` (chronicle-level) and the same on an entry; GET it back via the web serializer and the API resource; assert all eight values round-trip.
- [ ] **Step 2: Run → FAIL** (stripped by validation, omitted by serializers).
- [ ] **Step 3: Implement** — add rules for the four chronicle-level fields and `entries.*.{start_year,end_year,impact_score,approximate_location}` (`integer`/`min:...`, `array` for location) to both FormRequests; add the fields to `ChronicleResource`, `ChronicleEntryResource`, and `serializeChronicle`.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `feat(api): expose chronicle temporal/impact/location fields over web + API`

## Task 5: Importer persists the new fields + list source_evidence

**Files:** Modify `ImportChroniclesCommand.php`; Test `api/tests/Feature/ImportChroniclesCommandTest.php`

- [ ] **Step 1: Write the failing test** — a chronicle JSON fixture with the June-11 fields and `source_evidence: ["event:0"]` imports with those values persisted.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — map the four chronicle-level and four entry-level fields from the JSON onto the models; store `source_evidence` as the provided list (now jsonb).
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `feat(api): chronicles:import persists temporal/impact/location and list source_evidence`

---

## Self-review (coverage)

- LC-4 → T1. LC-2 → T2. LC-5 → T3. LC-6 → T4 (+ T5 for the pipeline path). All spec requirements mapped. The pipeline-side
  emission of a list `source_evidence` is also a small change in `pipeline/agent/graph/nodes/chronicle_builder.py` —
  tracked in sub-project B's cleanup, cross-referenced here.

## Execution handoff

Subagent-driven recommended. Task 1 (migration + cast) first, since Tasks 4–5 depend on the jsonb column.
