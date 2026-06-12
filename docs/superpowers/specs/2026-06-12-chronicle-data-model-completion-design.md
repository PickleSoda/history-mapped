# Chronicle Data-Model Completion — Design Spec

> **Date:** 2026-06-12
> **Status:** Design (approved) — ready for implementation planning
> **Area:** `api/` (Chronicle models, actions, FormRequests, resources, controllers, migration) + the agent importer.
> **Source:** bug report LC-2, LC-4, LC-5, LC-6.
> **Sub-project:** D of the audit-remediation set.

## 1. Problem

The Chronicle feature (added June 2026) is wired through some layers but not consistently validated/serialized/typed
across all of them, so several of its fields are unreachable or crash:

- **LC-2 (high):** `UpdateChronicleRequest`'s slug-unique rule references a non-existent `{chronicle}` route key against a
  non-existent `id` column → **500 on every edit**.
- **LC-4 (medium):** `source_evidence` is validated as an `array` but the column is `text` with no cast → write crash.
- **LC-5 (medium):** `narrative_text` is NOT NULL but the validator allows null and the action defaults null → NOT NULL crash.
- **LC-6 (medium):** the June-11 temporal/impact/location fields are in the schema/model/DTO but stripped by the
  FormRequests and omitted by all serializers → unreachable over HTTP.

## 2. Goals / Non-goals

**Goals**
- Editing a chronicle no longer 500s.
- `source_evidence` has one coherent representation across validator/column/cast/pipeline.
- `narrative_text` is consistently required.
- The June-11 fields round-trip through the web + API surfaces and are populated by the pipeline.

**Non-goals**
- Chronicle *generation* logic in the agent (sub-project B handles import; C handles confidence).

## 3. Accepted decisions

- **`source_evidence` → `jsonb` array.** Migrate the column `text → jsonb`, add `'source_evidence' => 'array'` cast,
  keep the validator as `array`, and have the pipeline emit a list (`["event:0"]`).
- **June-11 fields → user-editable AND pipeline-populated.** Extend both FormRequests + all three serializers + a
  round-trip test, and have `ImportChroniclesCommand` set them from the agent JSON.
- **`narrative_text` → required.** Action coalesces to `''` defensively AND the FormRequest requires it when an entry is present.

## 4. Architecture

Five thin, well-bounded changes across the Chronicle slice; no structural redesign.

### 4.1 Components

**Migration `2026_06_12_*_chronicle_source_evidence_jsonb`.** `ALTER TABLE chronicle_entries ALTER COLUMN source_evidence
TYPE jsonb USING to_jsonb(...)` (wrapping existing string values into a single-element array), nullable.

**`ChronicleEntry` model.** Add `'source_evidence' => 'array'` to `$casts`.

**`StoreChronicleRequest` / `UpdateChronicleRequest`.**
- Fix the slug-unique rule: `Rule::unique('chronicles','slug')->ignore($this->resolveChronicleId(), 'chronicle_id')`,
  resolving the `{slug}` route param to the chronicle's id (LC-2).
- Add the chronicle-level and `entries.*` fields `start_year`/`end_year`/`impact_score`/`approximate_location` with
  rules (`integer`/`min`, `array` for location) (LC-6).
- Require `entries.*.narrative_text` when an entry is present (`required_with`/`required`) (LC-5).
- Keep `entries.*.source_evidence` as `array` (now backed by jsonb) (LC-4).

**`CreateChronicleAction` / `UpdateChronicleAction`.** Coalesce `narrative_text` to `''` (defensive) and store the new
fields (already partly supported by the DTO).

**Serializers.** `ChronicleResource`, `ChronicleEntryResource`, and `Web\ChronicleController::serializeChronicle` emit the
four chronicle-level and four entry-level fields (LC-6).

**`ImportChroniclesCommand`.** Read and persist the June-11 fields from the agent JSON; expect `source_evidence` as a list.

## 5. Data flow

Web create/update → FormRequest (now accepts all fields, requires narrative_text, ignores own slug) → DTO → action
(stores jsonb array source_evidence + new fields) → serializers (round-trip all fields). Pipeline import →
`ImportChroniclesCommand` (persists new fields, list source_evidence).

## 6. Error handling

- Editing with the record's own slug no longer 500s (own id excluded).
- Submitting an array `source_evidence` no longer crashes (column is jsonb + cast).
- Omitting `narrative_text` is a clean 422 (required) rather than a NOT NULL 500.

## 7. Testing

- Feature test: update a chronicle resubmitting its current slug → 200 (LC-2).
- Feature test: create with `source_evidence: ["event:0"]` → persisted as jsonb array (LC-4).
- Feature test: create an entry omitting `narrative_text` → 422 (LC-5).
- Round-trip test: POST then GET the four new chronicle + entry fields through web and API (LC-6).
- Importer test: `chronicles:import` persists the new fields and a list `source_evidence`.

## 8. Sequencing (feeds the plan)

1. Migration (text→jsonb) + model cast (unblocks the array representation).
2. Slug-unique fix (the 500).
3. narrative_text required + action coalesce.
4. FormRequests + serializers for the June-11 fields.
5. Importer populates the new fields.

## 9. Risks

- **Data migration** of existing `source_evidence` strings — the `USING to_jsonb(...)`/`jsonb_build_array(...)` expression
  must wrap non-null strings into arrays and leave nulls null; test on a copy first.
- **Slug-id resolution in the request** — resolving the chronicle inside the FormRequest must not double-query
  expensively; resolve once and cache on the request instance.
