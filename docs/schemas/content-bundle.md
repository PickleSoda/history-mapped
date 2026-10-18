# Content Bundle Format Guide

> How to export a content bundle, edit it by hand or by script, and validate it.
> Design and intent: [../superpowers/specs/2026-10-18-content-bundles-import-export-design.md](../superpowers/specs/2026-10-18-content-bundles-import-export-design.md).

A **content bundle** is a versioned, diff-friendly snapshot of site content (entities, relationships, geometry, geo refs, chronicles) as JSON Lines files, plus a manifest and a byte-identical snapshot of what was exported.

## What exists today

| Step | Status | Command |
|------|--------|---------|
| Export | Built (part 1) | `php artisan content:export` |
| Modify | By hand or script, following [Editing rules](#editing-rules) | any editor |
| Validate | Built (part 1) | `php artisan content:validate` |
| Import | **Not built yet (part 2).** Nothing reads a bundle back into the site. | n/a |

Because import does not exist yet, a validated bundle cannot be applied to a site. The [editing rules](#editing-rules) are the contract the importer will follow, so edit to them now, but nothing happens to site data until part 2 ships. This guide is for editors and pipeline maintainers who export, edit and validate bundles.

## The workflow

Run commands inside the `app` container (see the repo `CLAUDE.md`):

```bash
docker compose -f docker/docker-compose.yml exec app php artisan <command>
```

```bash
# 1. Export (a .zip, or an empty/absent directory)
php artisan content:export storage/app/rome.zip --scope=chronicle:fall-of-the-roman-empire --profile=public

# 2. Modify: unzip, edit the *.jsonl files (not _base/ or manifest.json), re-zip or keep the folder
unzip storage/app/rome.zip -d storage/app/rome

# 3. Validate (a directory or a .zip)
php artisan content:validate storage/app/rome
php artisan content:validate storage/app/rome --against-site   # also check references and geometry against this database
php artisan content:validate storage/app/rome --json           # machine-readable

# 4. Import: arrives in part 2
```

`content:export` options:

| Option | Meaning |
|--------|---------|
| `path` (argument) | Target. A path ending in `.zip` must not exist yet. Otherwise a directory that is absent or empty. The parent directory must exist and be writable. |
| `--scope=*` | Repeatable. See [Scopes](#scopes). No `--scope` means `all`. |
| `--profile=full\|public` | Default `full`. See [Profiles](#profiles). |
| `--source=` | Free text recorded in the manifest. Default: the app environment name (`APP_ENV`). |

It prints one `<record type> <count>` line per file, warns `Warning: scope selected no entities.` for a non-`all` scope that matched none, and finishes with `Bundle written to <path>`. Exit code `0` on success, `1` on a bad option, scope or path.

The whole export reads one consistent database snapshot (a single read-only transaction), so the six files agree with each other.

## Bundle layout

```
manifest.json
LICENSE.md                  (public profile only)
entities.jsonl
relationships.jsonl
geometry_periods.jsonl
geo_refs.jsonl
chronicles.jsonl
chronicle_entries.jsonl
_base/
  entities.jsonl            (the same six files, byte-identical to the export)
  relationships.jsonl
  geometry_periods.jsonl
  geo_refs.jsonl
  chronicles.jsonl
  chronicle_entries.jsonl
```

- Every record file is written even when empty. A **partial bundle** may delete whole record files or delete lines from them (see [rule 3](#editing-rules)). Keep all six `_base/` files and the manifest as exported.
- Nothing else may be in the bundle. An unknown file name is an error.
- A zip may hold everything at the top level, or under a single wrapper directory that contains `manifest.json` (what you get from zipping a folder). `__MACOSX/` and `.DS_Store` entries are ignored.
- Record files are UTF-8, one JSON object per line, LF line endings, sorted by `id`, keys in the order listed below. Unicode and `/` are not escaped, and floats keep their `.0`. Key order does not matter for validation, but keeping it keeps text diffs small.

### Manifest

`manifest.json` is pretty-printed JSON. Do not edit it.

| Field | Meaning |
|-------|---------|
| `format` | Always `history-mapped/content-bundle`. |
| `version` | Format version. `1`. A different number is a package error. |
| `profile` | `full` or `public`. |
| `exported_at` | UTC timestamp, `2026-10-18T12:00:00Z`. |
| `source` | Where it came from (`--source`, default the app environment). |
| `scope` | The normalised scope specs, as a list of strings. `ids:` lists appear as `ids:<file name>`. |
| `base` | `export` for a bundle made by `content:export`. The pattern `baseline:<name>` is reserved for part 2. |
| `counts` | Records per file **at export time**. Edits do not update it and validation does not check it. |
| `checksums` | `sha256:<hex>` of each `_base/*.jsonl`. Validation recomputes them. |

## Record files

Each record has `id`, a lowercase UUID. Nested lists are owned child rows that are exported inside their parent.

| File | Keys, in order |
|------|----------------|
| `entities.jsonl` | `id`, `name`, `entity_type`, `wikidata_id`, `summary`, `significance`, `impact_score`, `display_priority`, `icon_class`, `confidence`, `verification_status`, `date_method`, `date_confidence`, `duration_type`, `location_method`, `location_confidence`, `primary_geo_ref_id`, `attributes`, `source_citations`, `aliases`, `tags`, `temporal_ranges`, `locations` |
| `relationships.jsonl` | `id`, `source_entity_id`, `target_entity_id`, `relationship_type`, `temporal_start`, `temporal_end`, `start_year`, `end_year`, `description`, `confidence`, `derive_geometry_period`, `source_citations` |
| `geometry_periods.jsonl` | `id`, `entity_id`, `period_type`, `start_year`, `end_year`, `description`, `confidence`, `provenance_mode`, `relationship_id`, `source_event_id`, `geom`, `territory_geom` |
| `geo_refs.jsonl` | `id`, `entity_id`, `provider`, `external_type`, `external_id`, `match_role`, `retrieval_method`, `temporal_start`, `temporal_end`, `temporal_start_year`, `temporal_end_year`, `geometry_period_id`, `match_score`, `is_active`, `external_tags`, `source_meta` |
| `chronicles.jsonl` | `id`, `slug`, `title`, `source_type`, `source_reference`, `status`, `start_year`, `end_year`, `impact_score`, `approximate_location`, `metadata`, `tags` |
| `chronicle_entries.jsonl` | `id`, `chronicle_id`, `sequence_order`, `start_year`, `end_year`, `impact_score`, `primary_relationship_id`, `narrative_text`, `notes`, `approximate_location`, `source_evidence`, `generated_by`, `entities` |

Every line may also carry `_op` (see [Editing rules](#editing-rules)). The exporter never writes it.

### Nested lists

| Parent field | Item keys, in order | Sort order in the export |
|--------------|---------------------|--------------------------|
| `entities.aliases` | `name`, `language`, `source`, `is_primary` | primary first, then `name`, then `language` with **nulls last** |
| `entities.tags` | `slug`, `source` | by `slug` |
| `entities.temporal_ranges` | `range_type`, `start_year`, `end_year`, `start_date`, `end_date`, `duration_type`, `date_method`, `date_confidence`, `is_primary`, `notes` | primary first, then `range_type`, then `start_year`, then `end_year`, both with **nulls first** (an unknown year sorts lowest) |
| `entities.locations` | `location_name`, `location_method`, `location_confidence`, `is_primary`, `notes`, `geom`, `territory_geom` | primary first, then `location_name` (null counts as empty) |
| `chronicles.tags` | `slug`, `source` | by `slug` |
| `chronicle_entries.entities` | `entity_id`, `role`, `sequence_in_entry` | `sequence_in_entry` with **nulls last**, then `entity_id` |

Ties break on the encoded item, so the order never depends on database row order. Inside a nested item, `name` (aliases), `slug` and `source` (tags on entities and chronicles) and `entity_id` (entry entities) are required; temporal ranges and locations have no required keys. Unknown item keys are errors.

Allowed values are in the schemas. Examples: 30 `entity_type` values, 74 `relationship_type` values, `confidence` in `high|medium|low|unresolved`, `status` in `draft|published|archived`, `provenance_mode` in `derived|manual|ohm_import`, tag `source` in `manual|curated`, entry entity `role` in `participant|mentioned|location|outcome`.

### Value rules you will hit

- **Enums are plain strings** such as `"city"` or `"human_verified"`. An unknown value in the database is exported as it is, and the validator reports it.
- **Years** are integers, negative for BCE, between -20000 and 3000. `temporal_start` / `temporal_end` / `start_date` / `end_date` are free text and are checked against the integer year (see [Records layer](#the-four-layers)).
- **GeoJSON** (`geom`, `territory_geom`) is a GeoJSON geometry object (`type` plus `coordinates`, or `geometries` for a `GeometryCollection`), with coordinates rounded to **7 decimal places**. `null` means no geometry.
- **jsonb is kept as stored.** `attributes`, `source_citations`, `external_tags`, `metadata`, `approximate_location` and `source_evidence` carry whatever the database holds. A top-level empty object is always written as `{}` (never `[]`), and `attributes` and `metadata` are never `null`. A null column stays `null`. Nested content is not touched. `source_evidence` can be any JSON value (in practice a string).
- **`match_score`** is a JSON number. `derive_geometry_period`, `is_active` and `is_primary` are booleans.
- **Tags** export only the `manual` and `curated` sources. Derived (rule-generated) tags are rebuilt by `tags:sync`, not carried.

### What is not exported

Derived data that is rebuilt elsewhere: `entity_group` (from `entity_type`), timeline entries, derived tags, embeddings. Environment-specific data: timestamps, `created_by`, `reviewer_id`. Also not exported: staging tables (relationship hints), per-user tables, the `sources` and `ref_*` tables, and the tag vocabulary (which stays in the repo). Do not add these keys; unknown keys are errors.

## Editing rules

This is the contract for whoever modifies a bundle. It is quoted from the design spec (§3); import (part 2) will apply it. Today `content:validate` enforces what it can check offline, noted below.

1. **Keep `id`.** It maps a line to a record. Never change or reuse one. Ids are lowercase UUIDs.
2. **A missing field means untouched.** Leave a field out and the site value is kept. Set it to `null` and the site value is cleared, where the schema allows `null`. Fields like `name`, `entity_type`, `narrative_text` and `verification_status` do not.
3. **A missing record means untouched.** Removing a line never deletes anything. Partial bundles are normal: export a chronicle, edit two entities, delete every other line, import.
4. **New records** omit `id`, or carry a UUID you generate. A generated UUID lets other lines in the same bundle point at the new record, for example a new entity plus its relationships. A new record must carry its creation fields:

   | File | Required to create |
   |------|--------------------|
   | `entities.jsonl` | `name`, `entity_type` |
   | `relationships.jsonl` | `source_entity_id`, `target_entity_id`, `relationship_type` |
   | `geometry_periods.jsonl` | `entity_id`, `period_type`, `start_year`, `provenance_mode` (and a `geom` or `territory_geom`, see [Records layer](#the-four-layers)) |
   | `geo_refs.jsonl` | `entity_id`, `provider`, `external_type`, `external_id`, `match_role`, `retrieval_method` |
   | `chronicles.jsonl` | `title`, `slug`, `source_type` |
   | `chronicle_entries.jsonl` | `chronicle_id`, `narrative_text` |

   **Validation only enforces this for lines without an `id`.** A line with a generated UUID looks exactly like an edit of an existing record, so validate cannot tell it is new. Include the creation fields anyway; the importer will check them (part 2).
5. **`_op` per line** (default `merge`):
   - `merge` writes only the fields present. A nested list that is present **replaces the whole list**: `aliases: [...]` becomes the entity's full alias list.
   - `replace` sets the record to exactly this line. Absent fields are cleared and absent nested lists emptied. For a chronicle, entries of that chronicle that are not in the bundle are deleted.
   - `delete` removes the record and its owned children. A delete line must have `id`. Validation fails if anything on the site would still reference the record, unless the bundle also deletes or re-points those records (see [References](#references)).
6. **References** point at an `id` in the bundle or on the site. See [References](#references).
7. **Do not edit `_base/` or `manifest.json`.** Validation recomputes the `_base/` checksums and rejects a bundle whose snapshot changed. Re-export instead.
8. **Unknown keys are errors**, which catches typos such as `sumary`. Keys starting with `_` other than `_op` are rejected too. This applies inside nested items.

A few consequences worth knowing:

- Merge lines can be tiny: `{"id": "…", "summary": "…"}` is a complete, valid edit.
- Editing a full exported line in place also works. Fields you did not change equal the snapshot.
- You can drop a whole record file from a partial bundle. Keep its `_base/` copy.
- Validation does not check that an `id` exists on the site or in `_base/`; that is the importer's job.

### References

Reference fields and the file they point into:

| Field | Points at |
|-------|-----------|
| `entities.primary_geo_ref_id` | `geo_refs` (and that geo ref must belong to this entity) |
| `relationships.source_entity_id`, `target_entity_id` | `entities` |
| `geometry_periods.entity_id`, `source_event_id` | `entities` |
| `geometry_periods.relationship_id` | `relationships` |
| `geo_refs.entity_id` | `entities` |
| `geo_refs.geometry_period_id` | `geometry_periods` (and that period must belong to the geo ref's entity) |
| `chronicle_entries.chronicle_id` | `chronicles` |
| `chronicle_entries.primary_relationship_id` | `relationships` |
| `chronicle_entries.entities[].entity_id` | `entities` |

A reference may point at a record in the bundle (including a new one with a generated UUID) or at a record that is only on the site. Pointing at a record the same bundle deletes is an error.

## Validation

```bash
php artisan content:validate <bundle.zip|dir> [--against-site] [--json]
```

### The four layers

Layers run in this order. After a layer that has errors, validation stops, because later layers assume the earlier ones held. Warnings never stop it.

| Layer | Checks |
|-------|--------|
| **package** | The path is a readable zip or directory within the [limits](#limits-and-file-hygiene). `manifest.json` exists, parses and matches `manifest.schema.json`. `version` is 1. Every file name is known and safe (no `..`, absolute paths, backslashes, control characters), with no duplicate zip entries. Each `_base/*.jsonl` is listed in `checksums` and its SHA-256 matches. |
| **structure** | Every line of every present record file is valid JSON, is an object, and matches that file's JSON Schema: known keys only, types, enums, UUID, QID (`Q42`), slug, year range, `_op` value, the creation fields of an id-less line, and the `id` of a delete line. |
| **records** | Per-line rules the schema cannot express (below). |
| **references** | Every reference resolves, deletes leave nothing dangling, same-owner links hold. With `--against-site`, also geometry validity. |

The **records** layer reports:

- a duplicate `id` within a file (error), a duplicate relationship with the same source, target, type, `start_year` and `end_year` (error), a duplicate chronicle `slug` (error), a duplicate `wikidata_id` (**warning**);
- `start_year` after `end_year` (relationships, geo refs `temporal_*_year`, geometry periods, chronicles, entries, entity `temporal_ranges`);
- a year that disagrees with its text: `temporal_start` "-27" against `start_year` 27 reports `BCE/CE sign mismatch`;
- the database CHECK rules: a geometry period needs `geom` or `territory_geom`, a `derived` one needs `relationship_id` or `source_event_id`, a `presence` one needs `relationship_id`; an entity location needs `location_name`, `geom` or `territory_geom`.

Delete lines skip the records rules. A new-record or `replace` line is checked as if absent fields were `null`. A partial `merge` line is checked only for rules whose keys are all present, since the full result depends on the site record.

The **references** layer, without `--against-site`, works from the bundle alone. A reference to something not in the bundle cannot be resolved, so it is counted and reported once per file and field as a warning (see below). Same-owner rules and deleted-target rules are checked on what the bundle contains.

### Reading the output

```
ERROR entities.jsonl:1: /sumary: unknown key `sumary`
ERROR entities.jsonl:2: /id: duplicate id `0b6f2a52-…0004`: also on line 1
WARN relationships.jsonl: /target_entity_id: 1 reference points outside the bundle (first on line 1); it must exist on the site at import (run with --against-site to check it)
2 errors, 1 warnings
```

- Format: `ERROR|WARN file:line: field: message`. `field` is a JSON pointer inside the line (`/summary`, `/aliases/0/name`, `/locations/1/geom`). `line` is the physical line number in the file you edited. Either part is left out when it does not apply (package problems have no line, summary warnings have no line).
- Order: by layer, then file (`entities`, `relationships`, `geometry_periods`, `geo_refs`, `chronicles`, `chronicle_entries`, then other files), then line.
- The last line is `<N> errors, <M> warnings`. The counts are true totals, including issues hidden by the [per-file cap](#per-file-caps).
- `--json` prints one JSON document and nothing else:

  ```json
  {"valid": false, "errors": 1, "warnings": 0, "issues": [
    {"severity": "error", "layer": "structure", "file": "entities.jsonl", "line": 3,
     "field": null, "message": "a delete (`_op`: \"delete\") needs `id`", "id": null, "unchanged": false}]}
  ```

  `layer` is `package`, `structure`, `records` or `references`. `id` is the record id when known. `unchanged` is explained next.

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Valid. There are no errors; warnings are allowed. |
| `1` | At least one error. |
| `2` | Reserved for the part-2 import planner (valid but with conflicts). `content:validate` never returns it. |

### "Unchanged since export" warnings

The importer never writes a value that equals the snapshot, so old problems in untouched data must not block you. If a line is **byte-for-byte identical** to the same line in `_base/` (after removing a BOM and CR), any error on it is **downgraded to a warning** with the suffix ` (unchanged since export)`, and `"unchanged": true` in `--json`.

```
WARN entities.jsonl:41: /wikidata_id: duplicate wikidata_id Q299663: also on line 12 (unchanged since export)
```

This is why a freshly exported bundle validates with 0 errors even when the database has old problems (for example two entities sharing a Wikidata id, or an entry that runs 1642 → 1400). Fix those in a separate clean-up if you care; they do not block.

Rules for the downgrade:

- It applies to **every** line an issue involves. A duplicate or a dangling reference is downgraded only when **all** the lines it names are unchanged. A new line colliding with an old one stays an error.
- Edit a line and it is judged on its own merits, including problems that were already in the old values.
- If `_base/` has more than 500,000 lines, nothing is downgraded and validation warns that errors on unchanged lines stay errors.
- `_base/` is not trusted: it is only checked against the manifest checksums, and anyone can recompute those. The downgrade protects against accidents, not against a doctored bundle.

### Per-file caps

To keep output readable, each file reports at most **200 errors and 200 warnings** per layer. The rest are counted and shown as an overflow line, for example `entities.jsonl: …and 1,204 more errors in this file`. They are included in the totals and in the exit code, though not in the list. In the structure layer, a file is abandoned after **10,000 lines with errors** (`validation of this file stopped after 10000 lines with errors`).

### Outside references and `--against-site`

Partial bundles legitimately point at records that are not in the bundle. Without `--against-site` these only produce one summary warning per file and field:

```
WARN relationships.jsonl: /target_entity_id: 3 references point outside the bundle (first on line 7); they must exist on the site at import (run with --against-site to check them)
```

Use `--against-site` before importing, from an environment connected to the database the bundle is meant for. It then also:

- looks up every outside reference on the site; one that exists nowhere is an error (`references entities <uuid>, which is neither in the bundle nor on the site`);
- checks same-owner links against the site (`… which belongs to entity <a>, not entity <b>`);
- for each deleted record, finds site rows that still reference it and are not themselves deleted or re-pointed by the bundle (`N site records still reference it (e.g. …); delete or re-point them in this bundle`);
- validates each `geom` / `territory_geom` (geometry periods and entity locations) with PostGIS (`invalid geometry: <reason>` or `unreadable GeoJSON: …`).

It does not compare values with the site; that is the importer's job.

## Limits and file hygiene

Bundles are read as untrusted input, never extracted to disk. Exceeding a limit is a package error and stops validation.

| Limit | Value |
|-------|-------|
| Entries in a zip or directory | 64 |
| One file, uncompressed | 2 GiB |
| The bundle, uncompressed | 4 GiB |
| Compression ratio | an entry over 1 MiB may not compress more than 100:1 (zip-bomb guard) |
| One line | 8 MiB (an over-long line is an error naming the line) |
| `manifest.json` | 1 MiB |

Tolerated, with a warning where noted:

| Situation | Behaviour |
|-----------|-----------|
| Blank or whitespace-only lines | Skipped. Warning `N blank lines ignored`. Line numbers in messages stay physical. |
| UTF-8 byte-order mark at the start of a file | Stripped. Warning `file starts with a byte-order mark; it was ignored`. |
| CRLF line endings | The `\r` is stripped. No warning. |
| Zip with one top-level folder containing `manifest.json` | That folder is the bundle root. |
| `__MACOSX/`, `.DS_Store` | Ignored. |

Not tolerated: duplicate entry names in a zip, encrypted zips, a corrupt or truncated entry, backslashes or `..` in names, and any file outside the layout above. Symlinks inside a directory bundle are ignored.

## Profiles

| | `full` | `public` |
|---|---|---|
| Records, nested lists, geometry | all | all |
| `attributes` keys starting with `_` (pipeline bookkeeping) | kept | **dropped** |
| `geo_refs.source_meta` (raw provider payload) | kept | **`null`** (the key stays) |
| `LICENSE.md` | no | **added** |

The `full` profile is a superset of `public`, so both are edited and validated the same way. In a public bundle, leave `source_meta` as exported (`null`); the dropped `_` attributes are simply absent.

`LICENSE.md` (public profile) states: Wikidata-derived facts are CC0 1.0, Wikipedia-derived prose is CC BY-SA 4.0 with per-record attribution in `source_citations`, OpenHistoricalMap geometry is CC0 1.0, and images are Wikimedia Commons links with credits, never copies. Reuse of a record must keep the licence that applies to its parts. Keep `LICENSE.md` with the bundle when you share it.

## Scopes

`--scope` is repeatable; the selections are combined (union). No `--scope` is the same as `all`. The normalised list is written to `manifest.json`.

| Spec | Selects | Example |
|------|---------|---------|
| `all` | everything | `--scope=all` |
| `chronicle:<slug>` | the chronicle, its entries, every entity linked from those entries or named by their primary relationships, and the relationships among those entities plus the entries' primary relationships | `--scope=chronicle:fall-of-constantinople` |
| `entity:<uuid>` | that one entity with its geometry periods and geo refs | `--scope=entity:3c8e5f10-92ab-4d67-b1e4-0a7d6c2f9e54` |
| `neighbours:<uuid>` | the entity plus every entity it shares a relationship with (either direction) | `--scope=neighbours:3c8e5f10-92ab-4d67-b1e4-0a7d6c2f9e54` |
| `type:<a,b>` | entities of those `entity_type` values | `--scope=type:city,person` |
| `group:<g>` | entities of an entity group (`POLITY`, `PLACE`, `EVENT`, `ECONOMY`, `CULTURE`, uppercase) | `--scope=group:EVENT` |
| `years:<from>..<to>` | entities whose **primary temporal range** overlaps the span (inclusive, -20000 to 3000) | `--scope=years:-500..500` |
| `ids:<file>` | entities listed in a text file, one UUID per line (`#` comments and blank lines allowed, 10 MB max). **Command line only.** | `--scope=ids:keep.txt` |

Combine: `--scope=type:city --scope=years:-500..500` exports the union (cities plus everything in that span), not the intersection.

For every scope other than `all`:

- Entities, geometry periods and geo refs follow the selected entities. Relationships are exported when **both** ends are selected (or when a selected chronicle names them as a primary relationship). Chronicles and entries are exported only for `chronicle:` scopes. Anything else a record points at stays as an id outside the bundle (see [outside references](#outside-references-and---against-site)).
- `years:` matches an entity's **primary** temporal range. An entity with no primary range, or one whose `start_year` is unknown (null), never matches. A null `end_year` counts as open-ended.
- `ids:` is refused anywhere except `content:export` on the command line, because it reads a local file. It records only the file's base name in the manifest.
- Slugs must be lowercase with no spaces or slashes, UUIDs are lowercase-normalised, and `type` / `group` values must be known.

## Where the schemas live

`api/resources/schemas/content-bundle/v1/` is the single source of truth (JSON Schema draft 2020-12):

- `manifest.schema.json`
- `entities.schema.json`, `relationships.schema.json`, `geometry_periods.schema.json`, `geo_refs.schema.json`, `chronicles.schema.json`, `chronicle_entries.schema.json`
- `common.schema.json`, shared definitions (`uuid`, `year`, `slug`, `qid`, `confidence`, `geometry`, `op`, `tag`, and so on)

Each record schema validates **one line** (a JSON object). The files refer to each other with relative `$ref`s such as `common.schema.json#/$defs/uuid` and carry `$id`s under `https://history-mapped.local/schemas/content-bundle/v1/`, so a script's validator needs the whole directory registered (for Python `jsonschema`, a `referencing` registry; for other languages, load all files by `$id`). Schemas check shape only; the records and references rules above live in the PHP validator, so run `content:validate` for the full answer. Enums in the schemas are asserted by tests to match the PHP enums and the Postgres enum types.

PHP entry points, for reference: `App\Support\ContentBundle\…` (`RecordType`, `BundleReader`, `BundleWriter`, `Validation\BundleValidator`).

## Worked examples

Ids are shortened with `…` only in prose; lines below use illustrative UUIDs. Assume an exported folder `rome/`.

### 1. Fix a summary

Keep only the line you want (delete the others, or leave them; unchanged lines are no-ops) and change the field. A merge line may be just the id and the field:

```json
{"id":"3c8e5f10-92ab-4d67-b1e4-0a7d6c2f9e54","summary":"Roman statesman and the first emperor of Rome, ruling from 27 BCE to 14 CE."}
```

Everything not named is untouched. Validate:

```
$ php artisan content:validate rome
0 errors, 0 warnings
```

### 2. Add an alias

`aliases` **replaces the whole list**. Copy the existing aliases from the exported line and add the new item; if you send only the new one, the others would be removed at import.

```json
{"id":"3c8e5f10-92ab-4d67-b1e4-0a7d6c2f9e54","aliases":[{"name":"Augustus","language":"en","source":"wikidata","is_primary":true},{"name":"Octavian","language":"en","source":"wikidata","is_primary":false},{"name":"Imperator Caesar Divi Filius Augustus","language":"la","source":null,"is_primary":false}]}
```

Only `name` is required in an item.

### 3. Add a new entity and a relationship to it

Generate a UUID (`uuidgen | tr A-Z a-z`, or `php artisan tinker --execute="echo Str::uuid();"`) and use it as the new entity's `id`. The relationship is a new record too, so it has no `id`, but it points at the new entity.

`entities.jsonl`:

```json
{"id":"7d1c4b9e-3f52-4a8e-9c1d-5e2b8a6f0c11","name":"Battle of Actium","entity_type":"event_battle","summary":"Naval battle of 2 September 31 BCE.","verification_status":"needs_review","temporal_ranges":[{"range_type":"primary","start_year":-31,"end_year":-31,"is_primary":true}]}
```

`relationships.jsonl`:

```json
{"source_entity_id":"3c8e5f10-92ab-4d67-b1e4-0a7d6c2f9e54","target_entity_id":"7d1c4b9e-3f52-4a8e-9c1d-5e2b8a6f0c11","relationship_type":"participated_in","start_year":-31,"end_year":-31}
```

The relationship's `target_entity_id` resolves inside the bundle. Its `source_entity_id` is an entity that is not in this bundle, so without `--against-site` you get one summary warning for it:

```
WARN relationships.jsonl: /source_entity_id: 1 reference points outside the bundle (first on line 1); it must exist on the site at import (run with --against-site to check it)
0 errors, 1 warnings
```

### 4. Delete a relationship

A delete line needs only `id` and `_op`:

```json
{"id":"b4e2a7c0-1d6f-4e39-8a52-9f0c3d7b6e28","_op":"delete"}
```

With `--against-site`, validation checks that nothing left on the site still points at it (for example a chronicle entry whose `primary_relationship_id` is this relationship, or a geometry period derived from it). If something does, you get an error on the delete line:

```
ERROR relationships.jsonl:1: /id: 1 site record still references it (e.g. chronicle_entries <uuid>); delete or re-point them in this bundle
```

### 5. What validate says when you get it wrong

```
ERROR entities.jsonl:1: /sumary: unknown key `sumary`
ERROR entities.jsonl:2: /entity_type: invalid value "kingdom"; allowed: "political_entity", "dynasty", "person", "military_unit", "diplomatic_relationship", "social_class", "city", "infrastructure_monument", "extraction_infra", "educational_institution", "event_war", "event_battle", …
ERROR entities.jsonl:3: a new record (no id) needs `entity_type`
ERROR entities.jsonl:4: /wikidata_id: must be a Wikidata id like Q42
ERROR entities.jsonl:4: /aliases/0/bogus: unknown key `bogus`
5 errors, 0 warnings
```

These come from the structure layer, so nothing deeper runs until they are fixed. A `replace` line is held to the same creation rules, so `{"id":"…","_op":"replace","summary":"x"}` gets ``a `replace` line needs `name`, `entity_type` `` (absent fields would be cleared, so they must be present).

Once the structure is clean, the next layers speak. Records-layer problems from one run:

```
ERROR entities.jsonl:2: /id: duplicate id `0b6f2a52-6c0e-4d43-9f6f-3a2f6a1c0001`: also on line 1
ERROR relationships.jsonl:1: /start_year: `start_year` 500 is after `end_year` 400
2 errors, 0 warnings
```

Validation stops after the first layer that has errors, so reference problems only show once those are fixed. A relationship pointing at a record that is not in the bundle is a summary warning without `--against-site`:

```
WARN relationships.jsonl: /target_entity_id: 1 reference points outside the bundle (first on line 1); it must exist on the site at import (run with --against-site to check it)
0 errors, 1 warnings
```

and an error with it:

```
ERROR relationships.jsonl:1: /target_entity_id: references entities 0b6f2a52-6c0e-4d43-9f6f-3a2f6a1c00ff, which is neither in the bundle nor on the site
1 errors, 0 warnings
```

A delete line without an `id` is a structure error: ``a delete (`_op`: "delete") needs `id` ``. If you touched `_base/`:

```
ERROR _base/entities.jsonl: _base snapshot was modified; re-export instead of editing _base/
```
