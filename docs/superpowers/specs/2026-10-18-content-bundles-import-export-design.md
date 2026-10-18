# Content bundles: export, edit, validate, import — design

Date: 2026-10-18 · Status: in progress — part 1 (export + validate) built; import not started

Contributors can now change prod content: approved text corrections, missing
fields, aliases. The only way content moves between environments today is the
pg_dump full replace (`docs/implementation-docs/content-data-transfer.md`),
which wipes those edits. The pipeline imports either skip existing rows or
overwrite them with `--force`, with no dry run and no check against edits made
on the site.

This spec defines one concrete way to move content: a versioned **content
bundle** with a fixed four-step workflow (export → modify → validate → import).
The importer compares three versions of every field and never deletes anything
the bundle does not explicitly delete. Conflicts become change requests whose
initiator is the import. Bundles replace the full replace for local → prod.
Import is admin-only. Export is open to every signed-in user.

## 1. The workflow

| Step | How | Who |
|---|---|---|
| **Export** | `php artisan content:export out.zip [--scope …] [--profile full\|public]`, the admin "Export" page, or the SPA export dialog | any signed-in user (public profile); admins (full profile) |
| **Modify** | Edit the JSONL files by hand, in a script, or from the pipeline, following the rules in §3 | anyone |
| **Validate** | `php artisan content:validate out.zip [--against-site] [--json]` (the admin upload runs the same checks) | anyone (CLI); admins (upload) |
| **Import** | `php artisan content:import out.zip --mode=review\|override [--dry-run]` or the admin "Import" page | admins only |

Every import starts with a **preview**: the same planner run as a dry run. It
shows counts per record type, sample diffs, every conflict and every
validation error. Nothing is written until the admin confirms the mode.

## 2. Bundle format

A `.zip` (or an unzipped directory for local work) with this layout:

```
manifest.json
entities.jsonl
relationships.jsonl
geometry_periods.jsonl
geo_refs.jsonl
chronicles.jsonl
chronicle_entries.jsonl
_base/                  ← snapshot of every record as exported; do not edit
  entities.jsonl  …     (same files, same ids)
LICENSE.md              ← public profile: sources and attribution
```

**`manifest.json`**

```jsonc
{
  "format": "history-mapped/content-bundle",
  "version": 1,
  "profile": "full",                 // full | public
  "exported_at": "2026-10-18T12:00:00Z",
  "source": "prod",                  // APP_ENV/remote name of the exporting site
  "scope": ["chronicle:fall-of-constantinople"],
  "base": "export",                  // export | baseline:<remote> (see §7)
  "counts": { "entities": 412, "relationships": 1093 },
  "checksums": { "_base/entities.jsonl": "sha256:…" }
}
```

**Record files.** One JSON object per line, UTF-8, LF line endings, sorted by
id, with keys in schema order, so `git diff` and text diffs stay readable.
Each record has its UUID as `id`. Owned child rows without references from
elsewhere are nested inside their parent. Rows that other records reference
get their own file.

| File | Record | Nested | References |
|---|---|---|---|
| `entities.jsonl` | `entities` row: name, entity_type, wikidata_id, summary, significance, impact_score, display_priority, icon_class, confidence, date/location/duration method + confidence, verification_status, attributes, source_citations | `aliases` [{name, language, source, is_primary}], `tags` [slugs, manual/curated only], `temporal_ranges` […], `locations` [… geom as GeoJSON] | `primary_geo_ref_id` → geo_refs |
| `relationships.jsonl` | source_entity_id, target_entity_id, relationship_type, temporal_start/end, start/end_year, description, confidence, derive_geometry_period, source_citations | — | entities |
| `geometry_periods.jsonl` | entity_id, period_type, start/end_year, geom + territory_geom (GeoJSON, 7 dp), description, provenance_mode, confidence | — | entities, relationships, `source_event_id` → entities |
| `geo_refs.jsonl` | entity_id, provider, external_id, external_type, match_role, temporal_*, external_tags, source_meta, match_score, is_active, retrieval_method | — | entities, geometry_periods |
| `chronicles.jsonl` | slug, title, source_type, source_reference, status, metadata, start/end_year, impact_score, approximate_location | `tags` [{slug, source}] | — |
| `chronicle_entries.jsonl` | chronicle_id, sequence_order, narrative_text, notes, primary_relationship_id, start/end_year, impact_score, approximate_location, source_evidence, generated_by | `entities` [{entity_id, role, sequence_in_entry}] | chronicles, relationships, entities |

**Not exported:**
- Derived data, which is rebuilt after an import: `entity_group` (from the type), `entity_timeline_entries`, derived tags, `embedding`.
- Environment-specific data: `reviewer_id`, `created_by`, timestamps.
- Local pipeline staging: `pipeline_relationship_hints`.
- Per-user tables.
- Tables that are empty today: `sources` and the `ref_*` tables.
- The tag vocabulary, which stays in the repo (`tags:sync`).

**Profiles.**
- **`full`**: everything above. Admins only.
- **`public`**: the fields the public API already exposes. That is nearly everything, so the public profile drops only `attributes` keys starting with `_` (pipeline bookkeeping such as `_rejected_wikidata_id`) and the geo refs' raw provider payload, `source_meta`. The full profile is a superset of the public one, so both import the same way: a field missing from a record means "leave untouched".

**`_base/`** stores each record's values at export time, used as the base of
the three-way comparison in §5. Field hashes are SHA-256 of canonical JSON:
sorted keys, geometry as GeoJSON rounded to 7 dp.

## 3. Editing rules (the contract for whoever modifies a bundle)

1. **Keep `id`.** It is how a line maps to a record. Never change it, never reuse it.
2. **A missing field means untouched.** Leave out a field and the site value is kept. Set a field to `null` and the site value is cleared, where the schema allows it.
3. **A missing record means untouched.** Removing a line never deletes anything. Partial bundles are normal: export a chronicle, edit two entities, delete every other line, import.
4. **New records** omit `id`, or carry a UUID you generate. A UUID lets other lines in the same bundle reference the new record, for example a new entity together with its relationships. The importer matches new records against existing ones (§5.1) before creating anything.
5. **`_op` per line** (default `merge`):
   - `merge` writes only the fields present. A nested list that is present replaces that list. For example, `aliases: [...]` becomes the entity's full alias list.
   - `replace` sets the record to exactly this line. Absent fields are cleared and absent nested lists emptied. For a chronicle, entries of that chronicle that are not in the bundle are deleted.
   - `delete` removes the record and its owned children. Validation fails if anything left on the site would still reference it, unless the bundle also deletes or re-points those records.
6. **References** point at an `id` in the bundle or on the site.
7. **Do not edit** `_base/` or `manifest.json`. Validation verifies the checksums and refuses a bundle whose base was altered.
8. **Unknown keys are errors.** This catches typos like `sumary`. Pipeline-only keys starting with `_` (other than `_op`) are rejected too.

## 4. Validation (`content:validate`)

The checks run in layers. Validation stops after any layer that has errors, because later layers assume the earlier ones held. The CLI and the admin upload share one implementation (`App\Support\ContentBundle\Validation\`). The user-facing guide is `docs/schemas/content-bundle.md`.

1. **Package**: manifest present and schema-valid, supported `version`, `_base/` checksums match, and file names are known and safe. Duplicate zip entries are errors. Size, entry-count and compression-ratio limits guard against zip bombs.
2. **Structure**: every line is checked against the JSON Schema for its file. That covers types, enums, QID/slug/uuid formats, `_op` values, and the creation fields of lines without `id`.
   - The schemas live in `api/resources/schemas/content-bundle/v1/*.schema.json`, as the single source of truth. They sit under `api/` so they ship with the app image, and the pipeline reads them from the repo.
   - PHP validates with `opis/json-schema` (new dependency). The pipeline can validate the bundles it writes with Python `jsonschema` against the same files.
   - Enums come from the PHP enums the models cast to, and a test asserts they match the Postgres enum types.
3. **Records** (`RecordChecks`, with the per-record rules in `RecordRules` for reuse by the part-2 planner):
   - no duplicate ids, relationships (source, target, type, start_year, end_year) or chronicle slugs; a duplicate Wikidata id is a warning;
   - `start_year ≤ end_year`, and text years agree with integer years, including the BCE/CE sign-slip message;
   - the DB CHECK constraints on geometry periods and entity locations, mirrored.
4. **References** (`ReferenceChecks`):
   - every id resolves to the bundle or, with `--against-site`, to the site;
   - same-owner rules for primary geo refs and geo-ref periods;
   - with `--against-site`: deletes leave no site row still referencing them, and every geometry passes PostGIS `ST_IsValid`.

   Without `--against-site`, references outside the bundle get one summary warning per file and field.
5. **Plan** (part 2): the dry run of §5, reporting creates, updates, unchanged rows, conflicts, deletes, and pending user contributions that the import would make stale.

**Unchanged lines are downgraded.** An error on a line that is byte-identical to its `_base/` line is downgraded to a warning, marked "(unchanged since export)". The import never writes unchanged values, and an export of a site with old data problems must still validate. A cross-line issue downgrades only when every line involved is unchanged. Per-file caps (200 issues each for errors and warnings) keep reports readable, and the totals stay exact.

The report lists `file:line: field: message`, sorted by layer, file and line. Exit code 0 means valid (warnings allowed) and 1 means errors. Code 2 is reserved for the part-2 planner ("valid with conflicts"). `--json` produces machine-readable output for scripts and CI.

## 5. Import

### 5.1 Matching records

- **A line whose `id` exists on the site** is that record.
- **A line whose `id` is unknown, or that has no `id`, is a candidate new record.** First it is checked against what is already there:
  - entities: by `wikidata_id`, when exactly one entity carries it;
  - chronicles: by `slug`;
  - relationships: by (source, target, type);
  - geo refs: by (entity, provider, external_id);
  - geometry periods: by (entity, period_type, start, end).

  A match is a **record conflict** ("already exists"). With no match, the record is created.
- **A line that has a base but no record on the site** means the record was deleted on the site after the export. If the file changed it, that is a record conflict. Otherwise the line is skipped.

### 5.2 Three-way comparison per field

`base` is the value in `_base/` (or in the baseline, §7). `file` is the
bundle's value. `site` is the current value on the site.

| file vs base | site vs base | Result |
|---|---|---|
| same | any | nothing to do (site edits kept) |
| changed | same | **apply** (clean change) |
| changed | changed, equal to file | nothing to do |
| changed | changed, different | **conflict** |
| no base (new record, or a bundle without base) | — | differs from site → **conflict**; equal → nothing |

Fields are independent. If a contributor fixed `summary` on the site and the
bundle changes `start_year`, both survive. Nested lists (aliases, tags,
temporal ranges, entry entities) compare as one value. `delete` on a record
whose site version changed since the base is a conflict.

### 5.3 Modes

- **`review`**:
  - Clean changes, creates and uncontested deletes are applied.
  - Each conflict is saved as a pending change request (§6).
  - The import ends with status `applied_with_conflicts` until every conflict is resolved.
- **`override`**:
  - Every conflict is resolved in the file's favour.
  - Each overwritten site value is still recorded, as an approved change request with the importing admin as reviewer, so it can be inspected or reverted later.

### 5.4 Applying

- **One import at a time**, enforced by a cache lock. The apply runs as a queued job with progress shown on the import page.
- **The plan is recomputed when the apply starts.** The preview is advisory: if someone edited a record between preview and confirm, that field becomes a conflict instead of being overwritten.
- **All writes run in a single DB transaction.** Model saves are used, not raw queries, so observers run (timeline rebuilds, relationship → geometry). Afterwards, touched entities have their tags re-derived and their embeddings queued, and caches are cleared.
- **Before anything is written, the importer exports the current site version of every record it will touch** to `storage/app/content-imports/<id>/undo.zip`. Importing that bundle in `override` mode reverts the import, including recreating records it deleted.
- **The import also writes `applied.zip`**: the post-import site version of every touched record, used for baselines (§7).
- **The report is stored on the import record** and lists what was applied, what conflicted and what was skipped.

## 6. Conflicts as change requests

Conflicts reuse the `contributions` table and review screens. A conflict is a
contribution whose initiator is an import instead of a contributor.

**New table `content_imports`**: id, user_id (the admin), filename, sha256,
manifest (jsonb), mode, status (`validating → previewed → applying → applied |
applied_with_conflicts | failed`), counts (jsonb), report (jsonb), undo_path,
applied_path, timestamps.

**`contributions` changes:**
- `import_id` (nullable FK to `content_imports`). When set, the row was raised by that import.
- `kind`: `field` (today's rows), `create` (a new record matched an existing one), or `delete` (a delete of a changed record).
- `base_value`, `proposed_value` (jsonb, nullable), for non-prose fields. Prose fields keep `base_text`/`proposed_text` and the word diff. Those three columns become nullable.
- `bundle_base` (jsonb, nullable): the bundle's base value, so the screen can show all three versions (export had X, site now has Y, file wants Z).
- `target_type` gains `geometry_period` and `geo_ref`. User contributions keep today's editable-field list. Import rows may target any field in the bundle schema.

As with user contributions, `base_*` holds the **site value at import time**,
so the existing stale check (`isStaleAgainst`) and `ApproveContributionAction`
work unchanged: if the site moves again before resolution, the reviewer must
confirm the overwrite.

**Resolution:**
- **Take import** approves the change: the file value is applied.
- **Keep site** rejects it.
- **Edit** approves an edited, merged value. This is available for text, with the diff viewer.
- **`create` conflicts** offer: update the existing record, create a separate record, or skip.

**Screens (Inertia admin):**
- `/admin/imports`: the list of imports, plus upload → preview → mode → apply.
- `/admin/imports/{id}`: the report and the **conflict screen**.
  - Conflicts are grouped by record, filterable by type and field.
  - Bulk "take import" / "keep site" on a selection.
  - Structured values shown side by side.
  - Geometry shown on a small map (follow-up).
- `/admin/contributions`: gets a source filter (Contributors / Imports). Import rows link back to their import.
- Import conflicts can be resolved only by users with `content.import`, so admins only. Reviewers with only `contributions.review` see contributor rows only.

## 7. Moving content between environments (replaces the full replace)

A local → prod sync is an ordinary import, with one addition. The base must be
the **last state both sides agreed on**, not the exporting site's current
state. Otherwise a value a contributor fixed on prod would look like a local
change and be overwritten.

**Baseline.** A local-only table `content_baselines` (remote, record_type,
record_id, values jsonb, hashes jsonb, synced_at) records each record's prod
values as of the last sync. Exports and imports run with `--remote=prod` take
their base from it instead of from `_base/`. Every import run with
`--remote=prod` updates the baseline for the records it contains.

**Bootstrap (once, now).** Accounts reached prod on 2026-10-18, so prod has no
approved contributions yet, and prod's current content is a valid common
ancestor.
1. Run `content:export` (full) on prod.
2. Locally, run `content:baseline prod-export.zip --remote=prod`.

From then on, local work that prod lacks shows up as local changes against the
baseline, which is correct.

The timing matters. If contributions are approved on prod before the
bootstrap, prod-now is no longer the common ancestor, and the first push would
overwrite those edits. In that case, build the baseline from the last dump
actually loaded on prod instead: restore it into a scratch DB, export it and
run `content:baseline` on that export.

**Each sync cycle:**
1. **Pull.** Export prod (full) and run `content:import prod.zip --remote=prod --mode=review` locally. Prod's changes since the baseline (contributions, admin edits) land locally. Fields that both sides changed become conflicts and are resolved locally, with local tools and no prod access.
2. **Push.** Run `content:export push.zip --remote=prod --changed [--with-deletes]` locally. The bundle holds every record whose local value differs from the baseline, with the baseline as base. `--with-deletes` adds `delete` lines for baseline records that local removed, such as dedup merges. Validate it, then import it on prod (admin upload, or artisan on the droplet) in `review` mode. Because the pull just happened, conflicts are rare. Anything changed on prod in between is still caught.
3. **Close.** Download the import's `applied.zip` and run `content:import applied.zip --remote=prod --mode=override` locally. Local now matches prod for every touched record, and the baseline moves forward. Without this step, a conflict resolved as "keep prod" on prod would be re-proposed by the next push.

**Partial syncs** fall out naturally: `--scope chronicle:<slug>` (or an entity
type, a year range, an id list) limits the push to that slice. The rest of
prod is never touched.

`docs/implementation-docs/content-data-transfer.md` is rewritten as the
runbook for this cycle. The pg_dump loader stays only as a disaster-recovery
restore.

## 8. Export for signed-in users

- **Who:** a new `content.export` permission, granted to the `user` role (and so to every account). `content.export.full` and `content.import` are admin-only.
- **Scopes:**
  - one entity, with optional neighbours;
  - one chronicle, with its entries, the entities they mention and the relationships between those entities;
  - entity type or group;
  - year range;
  - everything.

  References that point outside the scope stay as ids.
- **Delivery:**
  - `POST /api/v1/exports {scope}` queues a job.
  - `GET /api/v1/exports/{id}` reports status and returns a signed, expiring download URL.
  - Rate limit: 10 scoped exports per user per day.
  - "Everything" is prebuilt nightly by the scheduler (`content:export --profile public --scope all`) and served from storage to signed-in users, with no per-request build.
- **Public profile only**, with a `LICENSE.md`:
  - Wikidata facts: CC0.
  - Wikipedia-derived prose: CC BY-SA 4.0, attributed per record via `source_citations`.
  - OpenHistoricalMap geometry: CC0.
  - Images are Commons links with credits, never copies.

  Public bundles carry `_base/`, so a user can send an edited bundle to an admin, who can import it in `review` mode like any other.
- **SPA:**
  - an "Export data" item on entity and chronicle pages (current scope);
  - an Exports page under the account menu, listing recent exports and the full nightly bundle;
  - a short format guide linking to the editing rules (§3).

## 9. Permissions

| Permission | Roles | Grants |
|---|---|---|
| `content.export` | user, moderators, admin | public-profile exports (SPA, API) |
| `content.export.full` | admin | full-profile export (admin page, artisan has no gate) |
| `content.import` | admin | import pages, resolving import conflicts |

These are seeded in `PermissionSeeder`, plus a migration, because deploys only
run `migrate`.

## 10. Build order

1. **Format + export + validate** (the plan layer of §4 arrives with the import engine in step 2):
   - the JSON Schemas;
   - `content:export` (full and public profiles, scopes);
   - `content:validate` (package, structure, records, references);
   - round-trip tests: export → validate → re-import with no changes means zero writes.
2. **Import engine:**
   - the planner (three-way per field, record matching, ops);
   - the applier (transaction, undo/applied bundles);
   - `content:import --dry-run|--mode`;
   - `content_imports` and the contributions columns.
3. **Admin UI:** imports list, upload → preview → apply, conflict screen with bulk actions, contributions source filter.
4. **Sync:** `content_baselines`, `--remote`/`--changed`/`--with-deletes`, the bootstrap from prod, the runbook rewrite.
5. **User export:** permissions, API + queued job + signed downloads + rate limit, nightly full bundle, SPA export dialog and Exports page.

Each phase ships with tests. The planner's table in §5.2 becomes a
data-provider test, one case per row.

## 11. Known gaps / follow-ups

- **`chronicles:import --force` gives entries new UUIDs.** That breaks id matching (a re-ingested chronicle looks like "delete all entries, create new ones"). Fix it to keep the ids of entries it can match by sequence and text before the first sync. Until then, avoid `--force` on chronicles that have prod edits.
- **`pipeline:import --force` rewrites aliases and resets `verification_status` locally.** That is fine: the change reaches prod as a normal push, and any prod-side alias edit becomes a conflict instead of vanishing.
- **Direct-SQL pipeline tools** (`merge_entities.py`, `repair_committed_data.py` …) need no hooks: the push compares values against the baseline, not a change log.
- **Upload size limits on prod** (Caddy and FrankenPHP) need raising for large pushes. Artisan on the droplet with scp is the fallback.
- **Geometry conflicts** are shown as GeoJSON text until the map preview lands.
- **Contributor-submitted bundles** (a signed-in user uploading an edited bundle for review) are a natural follow-up, but not part of this spec. For now the user sends the file to an admin.

### Found while building part 1 (export + validate), for the part-2 planner

- **`_base/` is untrusted input.** Anyone can edit `_base/` and recompute the manifest checksums. That has two effects:
  - Schema-invalid lines can pass validation as "unchanged since export" warnings.
  - In part 2, a doctored base can make site edits look untouched, so the import silently overwrites contributor edits instead of raising conflicts.

  For admin imports that is no worse than override mode. Before bundles come from anyone else, though, the exporter should sign the `_base` checksums, for example with an HMAC keyed by the exporting site's `APP_KEY`. The importer then treats an unsigned or mismatched base as "no base", so every difference becomes a conflict.
- **Equality rules for the three-way comparison:**
  - `[]` and `{}` are equal for object-typed jsonb columns (`external_tags` stores both).
  - Key order inside free-form jsonb is irrelevant.
  - Geometry compares numerically (both sides through `ST_AsGeoJSON(…, 7)`), not as bytes. PHP re-encodes numbers such as `1.0e-5`.
- **Rules that need the merged record, not the line.** `RecordRules::check($type, $record, complete: true)` already runs on a fully merged record. The planner must also cover:
  - a geo-ref merge line that changes `geometry_period_id` without naming `entity_id`;
  - a line that gives a geo ref or geometry period a new `entity_id` while site rows still pair it with the old owner. Both owner FKs are NO ACTION on update.
- **Cascades.** Deleting a chronicle cascades to its entries, and the preview must show that count. A chronicle `replace` deletes entries that are not in the bundle, so their entry-entity links count as excused.
- **Cost.** Validation runs at about 10k lines/s: about 20–30 s for a full export, with ~90 MB peak memory. A bundle that deletes every entity peaks at ~270 MB with site checks. The admin upload must therefore validate and import in the queue worker, with a raised memory limit, never in the web request.
- **Data found by the first real-data validation**, all pre-existing and all reported as "unchanged since export" warnings:
  - two entity pairs share a Wikidata id: Q299663 ("Piero de' Medici" / "Piero di Cosimo de' Medici") and Q16722863 ("Dom Jeronimo" / "Yusuf ibn al-Hasan");
  - a Polynesian chronicle entry runs 1642 → 1400;
  - one `commanded_by` relationship exists twice.

  These are cleanup candidates.
