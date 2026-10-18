# Content bundles, part 1: export and validate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `php artisan content:export` writes a versioned content bundle (zip or directory of JSONL files plus a `_base/` snapshot and a manifest), and `php artisan content:validate` checks a bundle, layer by layer, against machine-readable JSON Schemas and the record and reference rules.

**Architecture:**
- Pure format code lives in `App\Support\ContentBundle\`: record types, profiles, serializers, scopes, reader/writer, validator.
- Orchestration lives in two Actions under `App\Actions\ContentBundle\`.
- Two thin artisan commands call those Actions.
- The JSON Schemas live under `api/resources/schemas/content-bundle/v1/` so they ship with the app image. The import engine (part 2) reuses the reader, schemas and validator unchanged.

**Tech Stack:** Laravel 13 / PHP 8.4, PostgreSQL 16 + PostGIS, `opis/json-schema` (new), PHPUnit feature tests with `RefreshDatabase`, Pint.

**Spec:** `docs/superpowers/specs/2026-10-18-content-bundles-import-export-design.md` §2–§4 (this plan covers build-order step 1 only).

---

## Ground rules for every task

- **Work only in the worktree** `/home/pickle/code/history-mapped/.claude/worktrees/content-bundles`, on branch `feature/content-bundles`. Never touch `/home/pickle/code/history-mapped` itself: another session works there.
- **Never run PHP on the host.** Every PHP, composer or artisan command goes through the runner script, which mounts the worktree into the app image with its own vendor volume and its own test database (`history-mapped_test_cb`):
  ```bash
  R=/tmp/claude-1000/-home-pickle-code-history-mapped/f9dc46f4-aea0-4438-bd33-6dde6b5f1a51/scratchpad/wt-art.sh
  $R php artisan test --filter ContentBundle      # run tests
  $R vendor/bin/pint --dirty                     # format changed PHP files
  $R composer require opis/json-schema           # dependencies
  ```
  Never point tests at another database. `RefreshDatabase` wipes whatever it runs against.
- **Style:**
  - `declare(strict_types=1);` at the top of every file.
  - Final classes where nothing extends them.
  - Constructor promotion.
  - PHPDoc array shapes on public methods.
  - Match the comment density of nearby files: a short class docblock saying *why*, no line-by-line narration.
- **Tests:**
  - PHPUnit classes (`class FooTest extends TestCase`) with `test_snake_case` methods.
  - DB tests `use RefreshDatabase`.
  - Feature tests go in `api/tests/Feature/ContentBundle/`. Pure-unit tests go in `api/tests/Unit/ContentBundle/` and extend `PHPUnit\Framework\TestCase` unless they need the app.
  - Factories exist for `Entity`, `Chronicle`, `ChronicleEntry`, `EntityGeoRef`. Create other rows with `Model::query()->create([...])` or `DB::table()->insert()`.
- **Commits:** commit at the end of each task with a conventional message (`feat(content-bundle): …`), ending with:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01KdC7HiEv8t4gyeN5Zz1q99
  ```
  Stage only the files your task created or changed (`git add <paths>`), never `git add -A`.
- **No pushing.** No migrations in this part.

## Record shapes (shared by every task)

Each bundle line is one JSON object with keys **in exactly this order**. Exports always emit every key (null or `[]` when empty) and never emit `_op`. In files written by people, every key except where noted is optional, because a missing key means "leave untouched".

| File (RecordType case) | PK column | Keys in order |
|---|---|---|
| `entities.jsonl` (`Entities`) | `entity_id` | `id, name, entity_type, wikidata_id, summary, significance, impact_score, display_priority, icon_class, confidence, verification_status, date_method, date_confidence, duration_type, location_method, location_confidence, primary_geo_ref_id, attributes, source_citations, aliases, tags, temporal_ranges, locations` |
| `relationships.jsonl` (`Relationships`) | `relationship_id` | `id, source_entity_id, target_entity_id, relationship_type, temporal_start, temporal_end, start_year, end_year, description, confidence, derive_geometry_period, source_citations` |
| `geometry_periods.jsonl` (`GeometryPeriods`) | `geometry_period_id` | `id, entity_id, period_type, start_year, end_year, description, confidence, provenance_mode, relationship_id, source_event_id, geom, territory_geom` |
| `geo_refs.jsonl` (`GeoRefs`) | `geo_ref_id` | `id, entity_id, provider, external_type, external_id, match_role, retrieval_method, temporal_start, temporal_end, temporal_start_year, temporal_end_year, geometry_period_id, match_score, is_active, external_tags, source_meta` |
| `chronicles.jsonl` (`Chronicles`) | `chronicle_id` | `id, slug, title, source_type, source_reference, status, start_year, end_year, impact_score, approximate_location, metadata, tags` |
| `chronicle_entries.jsonl` (`ChronicleEntries`) | `entry_id` | `id, chronicle_id, sequence_order, start_year, end_year, impact_score, primary_relationship_id, narrative_text, notes, approximate_location, source_evidence, generated_by, entities` |

**Nested lists** (each item's keys in this order; lists sorted for deterministic output):

- **`entities.aliases`**: `{name, language, source, is_primary}`, from `entity_aliases`. Sorted by `is_primary` (true first), then `name`, then `language` (nulls last).
- **`entities.tags`**: `{slug, source}`, from `entity_tags` where `source in ('manual','curated')`; derived tags are never exported. Sorted by `slug`.
- **`entities.temporal_ranges`**: `{range_type, start_year, end_year, start_date, end_date, duration_type, date_method, date_confidence, is_primary, notes}`, from `entity_temporal_ranges`. Sorted by `is_primary` (true first), then `range_type`, then `start_year`, then `end_year`.
- **`entities.locations`**: `{location_name, location_method, location_confidence, is_primary, notes, geom, territory_geom}`, from `entity_locations`. Sorted by `is_primary` (true first), then `location_name`.
- **`chronicles.tags`**: `{slug, source}`, from `chronicle_tags` where `source in ('manual','curated')`. Sorted by `slug`.
- **`chronicle_entries.entities`**: `{entity_id, role, sequence_in_entry}`, from `chronicle_entry_entities`. Sorted by `sequence_in_entry`, then `entity_id`.

**Value rules:**
- Enums are emitted as their string value.
- Geometry is GeoJSON from `ST_AsGeoJSON(col, 7)`: select it as `<col>_geojson` so the `App\Casts\GeoJson` cast picks it up without an N+1. See the cast's `get()`.
- Every jsonb column that is an object in the DB must be emitted as a JSON object even when empty. PHP decodes `{}` into `[]`, so serializers cast empty object-typed values with `(object) []`. Check each jsonb column's real shape in the dev data before deciding object vs list (for example `source_citations` may be a list). Read-only check:
  ```bash
  cd /home/pickle/code/history-mapped && docker compose -f docker/docker-compose.yml exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c "select jsonb_typeof(source_citations), count(*) from entities group by 1"'
  ```
- **Object-typed jsonb columns are emitted as `{}` when empty, even when the DB stores `[]`.** `entity_geo_refs.external_tags` is `[]` in most rows and an object in the rest. Part 2's hashing must treat `[]` and `{}` as equal for these columns. Note that in a code comment where the normalization happens.
- `chronicle_entries.source_evidence` is a jsonb **string** in every current row (e.g. `"event:0"`), although the model casts it to `array`. Emit the stored JSON value as-is; its schema accepts any JSON value.
- `match_score` (numeric) is emitted as a JSON number.
- **opis validates decoded JSON objects (`stdClass`), not PHP associative arrays.** Always validate `json_decode(JsonLine::encode($record))`.
- **Tag rows store the slug in a column named `tag`**, emitted as `slug`. `entity_tags.tag` and `chronicle_tags.tag` have FKs to `tags.slug`, so tests must insert the vocabulary rows (`tags`: slug, name, facet) first.
- **Performance:**
  - The entity query selects explicit columns. Never `select *`: `embedding` is ~12 KB per row.
  - Chronicle entry entities are read from `chronicle_entry_entities` directly, never by hydrating `Entity` models.
- **Factories:** fix two before relying on them (Task 2):
  - `EntityFactory` double-encodes `attributes` (`json_encode` plus the model's json cast). It should pass a plain array.
  - `ChronicleFactory` picks `start_year`/`end_year` independently, so start > end about half the time. It should keep end ≥ start.
- Not exported: `entity_group`, `embedding`, `reviewer_id`, `review_date`, `created_by`, `created_at`, `updated_at`, and all `*_id` PKs of nested children.

**`_op`**: optional on every line, one of `merge` (default), `replace` or `delete`. A `delete` line needs `id`. A line without `id` is a new record and must carry that type's **creation fields**. These are the NOT NULL, no-default columns that are bundle keys; `entity_group` is derived from `entity_type` on create, so it is not one:

| Type | Creation fields |
|---|---|
| entities | `name, entity_type` |
| relationships | `source_entity_id, target_entity_id, relationship_type` |
| geometry_periods | `entity_id, period_type, start_year, provenance_mode` |
| geo_refs | `entity_id, provider, external_type, external_id, match_role, retrieval_method` |
| chronicles | `title, slug, source_type` |
| chronicle_entries | `chronicle_id, narrative_text` |

**Profiles** (`Profile` enum: `Full`, `Public`). `Public` drops:
- `attributes` keys starting with `_`;
- the `source_meta` key of geo refs. In the public profile, emit the key as `null`, so the key set stays fixed.

Everything else is identical.

## File structure

```
api/resources/schemas/content-bundle/v1/
  common.schema.json            $defs: uuid, year, slug, qid, geojson geometry, op, tag
  manifest.schema.json
  entities.schema.json          one per record file
  relationships.schema.json
  geometry_periods.schema.json
  geo_refs.schema.json
  chronicles.schema.json
  chronicle_entries.schema.json
api/resources/content-bundle/LICENSE.public.md   copied into public bundles
api/app/Support/ContentBundle/
  BundleFormat.php        constants: FORMAT, VERSION, MANIFEST, BASE_DIR, LICENSE, SCHEMA_DIR
  RecordType.php          enum: file(), primaryKey(), modelClass(), keys(), schemaPath()
  Profile.php             enum Full|Public
  Schemas.php             loads + caches compiled opis schemas (validator() and schema(RecordType))
  JsonLine.php            encode(array): string, the single JSON encoding used for bundle lines
  Serializers/RecordSerializer.php        interface
  Serializers/EntitySerializer.php
  Serializers/RelationshipSerializer.php
  Serializers/GeometryPeriodSerializer.php
  Serializers/GeoRefSerializer.php
  Serializers/ChronicleSerializer.php
  Serializers/ChronicleEntrySerializer.php
  Serializers/Serializers.php             RecordType → serializer lookup
  Scope/ExportScope.php                   parses --scope strings
  Scope/ScopeResolver.php                 scope → id queries per RecordType
  BundleWriter.php
  BundleReader.php
  Validation/Issue.php
  Validation/ValidationReport.php
  Validation/BundleValidator.php          runs the layers in order
  Validation/PackageChecks.php
  Validation/StructureChecks.php
  Validation/RecordChecks.php
  Validation/ReferenceChecks.php
api/app/Actions/ContentBundle/ExportContentBundleAction.php
api/app/Actions/ContentBundle/ValidateContentBundleAction.php
api/app/Console/Commands/ContentExportCommand.php       content:export
api/app/Console/Commands/ContentValidateCommand.php     content:validate
docs/schemas/content-bundle.md            format guide + editing rules for people
```

---

### Task 1: JSON Schemas, record types and the schema dependency

**Files:**
- Create: everything under `api/resources/schemas/content-bundle/v1/`
- Create: `api/app/Support/ContentBundle/{BundleFormat,RecordType,Profile,Schemas}.php`
- Modify: `api/composer.json`, `api/composer.lock` (via `composer require opis/json-schema`)
- Test: `api/tests/Feature/ContentBundle/SchemasTest.php`

- [ ] **Step 1:** `$R composer require opis/json-schema` (latest 2.x).
- [ ] **Step 2: Write `common.schema.json`** (draft 2020-12, `$id` `https://history-mapped.local/schemas/content-bundle/v1/common.schema.json`). It defines `$defs`:
  - `uuid` (string, format uuid, pattern lowercase hex 8-4-4-4-12);
  - `year` (integer, `-20000..3000`, negative = BCE);
  - `slug` (`^[^\sA-Z/]+$`, max 255: lowercase, no whitespace or slashes; non-ASCII letters and trailing hyphens are allowed because existing slugs such as `chavín-horizon-c-750330-bce` use them);
  - `qid` (`^Q[1-9]\d*$`);
  - `op` (enum merge|replace|delete);
  - `tag` (object {slug, source(enum manual|curated)}, no extra keys);
  - `geometry` (GeoJSON geometry object: `type` in Point, MultiPoint, LineString, MultiLineString, Polygon, MultiPolygon, GeometryCollection, plus `coordinates` (array) or `geometries` (array)).
- [ ] **Step 3: Write one schema per record file** following the "Record shapes" table:
  - `type: object` and `additionalProperties: false`.
  - Every key from the table, plus `_op`. Nullable columns are `["<type>","null"]`.
  - Enum columns: a NOT NULL enum column is `{"enum":[…]}`. A nullable enum column is `{"anyOf":[{"enum":[…]},{"type":"null"}]}`. (`enum` is checked independently of `type`, so `type:["string","null"]` plus `enum` would reject null.)
  - `geometry_periods.provenance_mode` is an enum of its DB check constraint values: `derived, manual, ohm_import`. Read each column's enum from the model casts in `app/Models/*` and the enum in `app/Enums/*`. A column with no PHP enum (e.g. `period_type`, `range_type`, `provenance_mode`, `relationships.temporal_start`) is a plain string.
  - Nested list items are objects with `additionalProperties: false`.
  - `if {_op: const delete} then required [id]`.
  - `if not required [id] then required [<creation fields>]`, using the creation fields derived as described under "`_op`" above.
  - References use `common#/$defs/uuid`.
- [ ] **Step 4: Write `manifest.schema.json`** with these keys:
  - required `format` (const `history-mapped/content-bundle`);
  - `version` (integer);
  - `profile` (enum full|public);
  - `exported_at` (date-time string);
  - `source` (string);
  - `scope` (array of strings);
  - `base` (string, pattern `^(export|baseline:[a-z0-9_-]+)$`);
  - `counts` (object of integers keyed by record file stem);
  - `checksums` (object: keys match `^_base/[a-z_]+\.jsonl$`, values match `^sha256:[0-9a-f]{64}$`);
  - `additionalProperties: false`.
- [ ] **Step 5: Write the PHP format types:**
  - `BundleFormat`: `FORMAT = 'history-mapped/content-bundle'`, `VERSION = 1`, `MANIFEST = 'manifest.json'`, `BASE_DIR = '_base'`, `LICENSE = 'LICENSE.md'`, `SCHEMA_DIR = resource_path('schemas/content-bundle/v1')` (a static method, since it calls a helper).
  - `RecordType`: string-backed enum whose cases' values are the file stems (`entities`, `relationships`, `geometry_periods`, `geo_refs`, `chronicles`, `chronicle_entries`), in that order. Methods: `file()` (`<stem>.jsonl`), `primaryKey()`, `modelClass()`, `keys()` (the ordered key list from the table, without `_op`), `schemaPath()`. Plus a static `fromFile(string): ?self`.
  - `Profile`: string enum `full`/`public`.
  - `Schemas`: builds one `Opis\JsonSchema\Validator` with a resolver prefix mapping the `$id` base URL to `SCHEMA_DIR`. Exposes `validator()`, `recordSchemaId(RecordType)` and `manifestSchemaId()`. Bind it as a singleton in `AppServiceProvider` only if needed; a `static` lazy instance is fine.
- [ ] **Step 6: Write the failing tests** in `SchemasTest`:
  1. Every `*.schema.json` parses and compiles (validate `{}` against each without exceptions).
  2. For each enum-backed column in every schema, the schema's `enum` list equals `array_column(Enum::cases(), 'value')` for the PHP enum the model casts that column to.
     - Read the list from the `enum` itself, or from the non-null `anyOf` branch.
     - Read the cast map from `(new Model)->getCasts()` so the test follows the models.
     - Also assert the PHP values equal the Postgres enum labels of that column's type: `udt_name` from `information_schema.columns`, then `select e.enumlabel from pg_enum e join pg_type t on t.oid = e.enumtypid where t.typname = ? order by e.enumsortorder`.
  3. Each schema's `properties` keys, minus `_op`, equal `RecordType::keys()` in the same order.
  4. A minimal valid line per type passes. A line with an unknown key fails. A `{"_op":"delete"}` without `id` fails. A new record without its creation fields fails.
- [ ] **Step 7:** Run `$R php artisan test --filter SchemasTest`. Expect a fail first, then a pass once everything is in place.
- [ ] **Step 8:** Run `$R vendor/bin/pint --dirty`, then commit (`feat(content-bundle): JSON schemas and record types for content bundles`).

### Task 2: Line encoding and the entity serializer

**Files:**
- Create: `api/app/Support/ContentBundle/JsonLine.php`
- Create: `api/app/Support/ContentBundle/Serializers/{RecordSerializer,EntitySerializer}.php`
- Test: `api/tests/Unit/ContentBundle/JsonLineTest.php`, `api/tests/Feature/ContentBundle/EntitySerializerTest.php`

- [ ] **Fix the two factories** described under "Value rules". Then run the **full** suite (`$R php artisan test`) and confirm nothing else depended on the old behaviour.
- [ ] **`JsonLine::encode(array $record): string`:**
  - `json_encode` with `JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRESERVE_ZERO_FRACTION | JSON_THROW_ON_ERROR`;
  - no trailing newline;
  - key order preserved as given.

  Unit tests:
  - unicode stays literal (`"Constantinople — Κωνσταντινούπολις"`);
  - `/` is not escaped;
  - `1.0` stays `1.0`;
  - `(object) []` encodes as `{}`;
  - key order is preserved.
- [ ] **`RecordSerializer` interface:**
  ```php
  interface RecordSerializer
  {
      public function type(): RecordType;
      /** Base query for this type: eager loads and geojson selects; callers add scope + ordering. */
      public function query(): Builder;
      /** @return array<string, mixed> keys exactly RecordType::keys(), in order */
      public function serialize(Model $model, Profile $profile): array;
  }
  ```
- [ ] **`EntitySerializer`:**
  - `query()` selects explicit entity columns (no `embedding`) and eager-loads `aliases`, `entityTags` (constrained to manual/curated), `temporalRanges`, and `locations`. Locations are selected with `ST_AsGeoJSON(geom, 7) as geom_geojson` and the same for `territory_geom`.
  - `serialize()` builds the record in key order with the nested lists shaped and sorted as in "Record shapes".
  - The Public profile drops `_`-prefixed `attributes` keys. Empty `attributes` becomes `{}`.
- [ ] **Feature test.** Build one entity with:
  - two aliases (one primary);
  - one manual tag, one curated tag and one derived tag;
  - two temporal ranges;
  - a location with a Point geom;
  - `attributes` containing a `_rejected_wikidata_id` key and a normal key.

  Assert:
  - key order;
  - nested sorting;
  - the derived tag is absent;
  - geom is GeoJSON with ≤ 7 decimals;
  - in the public profile the `_` key is absent but kept in full;
  - an entity with empty attributes encodes `"attributes":{}`;
  - the full serialized record validates against `entities.schema.json` via `Schemas`.

  Also assert the query count: serializing 5 entities from `query()->get()` runs a constant number of queries, so no N+1. Use `DB::enableQueryLog()`.
- [ ] Run, pint, commit (`feat(content-bundle): entity serializer and canonical line encoding`).

### Task 3: The other five serializers

**Files:**
- Create: `api/app/Support/ContentBundle/Serializers/{Relationship,GeometryPeriod,GeoRef,Chronicle,ChronicleEntry}Serializer.php` and `Serializers.php`
- Test: `api/tests/Feature/ContentBundle/RecordSerializersTest.php`

- [ ] Implement each serializer exactly like `EntitySerializer`, with these specifics:
  - `GeometryPeriodSerializer` selects `geom_geojson` and `territory_geom_geojson`.
  - `ChronicleSerializer` eager-loads chronicle tags filtered to manual/curated. Use the `chronicle_tags` table: check `Chronicle::tags()` and whether a pivot `source` is exposed; query the table directly if needed. `metadata` and `approximate_location` are objects (`{}` when empty, `null` when null).
  - `ChronicleEntrySerializer` reads `chronicle_entry_entities` rows directly (an eager-loaded `hasMany` on a small pivot model, or one grouped query per chunk), never hydrating `Entity`.
  - `GeoRefSerializer` emits `source_meta: null` in the public profile and `match_score` as a float or null.
- [ ] `Serializers::for(RecordType): RecordSerializer` and `Serializers::all(): array<string, RecordSerializer>` in RecordType order. Resolve through the container.
- [ ] **Feature test** (data provider over the five types):
  - build one realistic record per type;
  - assert key order equals `RecordType::keys()`;
  - assert it validates against its schema;
  - check the type-specific bits: geometry GeoJSON, empty jsonb → `{}`, the public `source_meta` null, pivot role/sequence, curated-only chronicle tags.
- [ ] Run, pint, commit (`feat(content-bundle): serializers for relationships, geometry, geo refs and chronicles`).

### Task 4: Export scopes

**Files:**
- Create: `api/app/Support/ContentBundle/Scope/{ExportScope,ScopeResolver}.php`
- Test: `api/tests/Unit/ContentBundle/ExportScopeTest.php`, `api/tests/Feature/ContentBundle/ScopeResolverTest.php`

- [ ] **`ExportScope::parse(list<string> $specs): self`.** `[]` means `all`. Accepted specs (anything else throws `InvalidArgumentException` with the bad spec in the message):
  - `all`;
  - `chronicle:<slug>`;
  - `entity:<uuid>`;
  - `neighbours:<uuid>` (the entity plus every entity one relationship away);
  - `type:<entity_type>[,<entity_type>…]` (validated against `EntityType`);
  - `group:<entity_group>` (validated against `EntityGroup`);
  - `years:<from>..<to>` (signed ints, from ≤ to, e.g. `years:-500..-100`);
  - `ids:<path>` (a file with one entity uuid per line; blank lines and `#` comments ignored). `parse()` reads the file and rejects non-uuid lines with their line number, so Postgres never sees a bad uuid cast.

  `specs(): list<string>` returns the normalized specs for the manifest.
- [ ] **`ScopeResolver::resolve(ExportScope): array<string, Builder>`** returns, per RecordType value, an Eloquent builder of that type's models restricted to the scope. The serializer's `query()` is the base, and the PK is used for ordering by the writer. Multiple specs union their entity sets E and chronicle sets C.
  - `all`: no restriction on any type.
  - **Entity specs** add to E. `years` matches entities whose primary temporal range (`entity_temporal_ranges.is_primary`) overlaps [from, to]. A null end counts as open-ended, a null start as unknown (excluded).
  - **`chronicle:<slug>`** adds the chronicle to C. Its E contribution is every entity linked to its entries via `chronicle_entry_entities`, plus both endpoints of every entry's `primary_relationship_id`.
  - **Closure:**
    - entities = E;
    - relationships = (both ends in E) ∪ (primary relationships of C's entries);
    - geometry_periods = entity_id in E;
    - geo_refs = entity_id in E;
    - chronicles = C;
    - chronicle_entries = chronicle_id in C.
  - Use subqueries (`whereIn(col, $subquery)`) rather than loading id arrays into PHP. The `all` scope must stay a plain unrestricted query.
- [ ] **Tests:**
  - parsing (each valid form, each invalid form);
  - resolver (a small graph of 6 entities, 5 relationships, one chronicle with 2 entries). Assert the exact id sets for `entity:`, `neighbours:`, `type:`, `years:` (with an open-ended range), `chronicle:`, a union of two specs, and `all`.
- [ ] Run, pint, commit (`feat(content-bundle): export scopes`).

### Task 5: Bundle writer, reader and `content:export`

**Files:**
- Create: `api/app/Support/ContentBundle/{BundleWriter,BundleReader}.php`, `api/resources/content-bundle/LICENSE.public.md`
- Create: `api/app/Actions/ContentBundle/ExportContentBundleAction.php`, `api/app/Console/Commands/ContentExportCommand.php`
- Test: `api/tests/Feature/ContentBundle/BundleReaderWriterTest.php`, `api/tests/Feature/ContentBundle/ContentExportCommandTest.php`

- [ ] **`BundleWriter`:**
  - `open(string $path)`: a `.zip` path builds in a temp directory under `storage_path('app/tmp')` and zips on `close()`. Any other path is a directory, which must not exist or must be empty.
  - `writeRecords(RecordType, iterable<array> $records)`: streams lines plus `\n` into `<file>` and an identical copy into `_base/<file>`, and counts records.
  - `close(array $manifest)`: writes `manifest.json` (pretty-printed, keys in schema order). The writer fills `counts` and `checksums` (`sha256:` of each `_base/*` file). For the public profile it also copies `LICENSE.md` from `resources/content-bundle/LICENSE.public.md`.
  - Files for types with zero records are still written (empty).
- [ ] **`LICENSE.public.md`.** A short markdown note stating:
  - the bundle comes from History Mapped;
  - Wikidata-derived facts are CC0;
  - prose derived from Wikipedia is CC BY-SA 4.0, attributed per record through `source_citations`;
  - OpenHistoricalMap geometry is CC0;
  - images are referenced as Wikimedia Commons links with their credits, never copied.

  End it with a link to the format guide path `docs/schemas/content-bundle.md`.
- [ ] **`BundleReader::open(string $path)`.** A zip (via `ZipArchive`) or a directory. If the root has no `manifest.json` but contains exactly one directory that does, that directory is the root, because re-zipped folders often look like that. API:
  - `manifest(): ?array` (null when missing or unparseable; the parse error is in `manifestError()`);
  - `files(): list<string>` (relative paths, `/` separators, directories excluded; `__MACOSX/` entries and `.DS_Store` files are ignored, since macOS adds them when re-zipping);
  - `has(string)`;
  - `sha256(string)`;
  - `lines(string $file): Generator<int, string>` (1-based line number ⇒ line without the `\n`; a final empty line is not yielded);
  - `close()`.
- [ ] **`ExportContentBundleAction(string $path, ExportScope $scope, Profile $profile, ?string $source = null): array`** returns the manifest written.
  - For each RecordType in order, stream `ScopeResolver` builders with `lazyById(500, <pk>)`. `lazyById` orders by the PK, which gives the sort-by-id rule. Pass each model through its serializer into `writeRecords`.
  - Manifest: `format`, `version`, `profile`, `exported_at` (UTC ISO 8601), `source` (`$source ?? config('app.env')`), `scope` (`$scope->specs()`), `base: 'export'`, `counts`, `checksums`.
- [ ] **`content:export {path} {--scope=*} {--profile=full} {--source=}`.**
  - Bad scope or profile → error line and exit 1.
  - On success it prints one line per type with its count and the output path, and exits 0.
  - Class docblock in the style of the neighbouring commands (e.g. `SyncTagsCommand`).
- [ ] **Tests:**
  - writer + reader round-trip for both a zip and a directory;
  - the reader finds a nested root;
  - `_base` files are byte-identical to record files;
  - checksums verify;
  - **determinism**: two exports of the same data produce identical record files;
  - the command exports a seeded dataset (2 entities with children, 1 relationship, 1 geometry period with a polygon, 1 geo ref, 1 chronicle with 2 entries); counts in the manifest are right, and every line validates against its schema;
  - `--profile=public` includes `LICENSE.md` and strips `_` attribute keys;
  - `--scope=chronicle:<slug>` exports only the closure;
  - an invalid `--scope` exits 1.
- [ ] Run, pint, commit (`feat(content-bundle): bundle reader/writer and content:export`).

### Task 6: Validation report, package checks and structure checks

**Files:**
- Create: `api/app/Support/ContentBundle/Validation/{Issue,ValidationReport,BundleValidator,PackageChecks,StructureChecks}.php`
- Test: `api/tests/Feature/ContentBundle/ValidatePackageAndStructureTest.php`

- [ ] **`Issue`:** readonly class with `severity` (`error`|`warning`), `layer` (`package`|`structure`|`records`|`references`), `?string file`, `?int line`, `?string field` (JSON pointer, e.g. `/aliases/0/name`), `string message`. Plus `toArray()` and `__toString()` as `file:line: field: message`, omitting missing parts.
- [ ] **`ValidationReport`:** `add(Issue)`, `errors()`, `warnings()`, `isValid()` (no errors), `hasErrorsIn(string $layer)`, `toArray()` (`{valid, errors, warnings, issues: [...]}`).
- [ ] **`BundleValidator::validate(BundleReader $bundle, bool $againstSite = false): ValidationReport`.** Runs the layers in order: package → structure → records → references. It stops after package if package has errors, and after structure if structure has errors. Records and references are empty stubs in this task (Task 7 fills them).
- [ ] **Unchanged lines downgrade to warnings.** A record line whose raw text is byte-identical to the `_base/` line with the same `id` is **unchanged since export**. Any error on such a line, from any layer, becomes a warning with the suffix ` (unchanged since export)`.
  - **Why:** the import never writes unchanged values, and an export of a site with old data problems must still validate. The dev data has a chronicle entry with start_year 1642 > end_year 1400, and an exact duplicate `commanded_by` relationship.
  - **Where:** implement it once in `BundleValidator` (e.g. a small `BaseIndex`: per record file, id → sha1 of the base line). Checks attach the line's `id` to each `Issue` (add a nullable `id` property).
  - **Ordering:** the stop-after-structure rule counts errors **after** downgrading.
  - **Test:** a pre-existing bad value in an unchanged line is a warning; the same value in an edited line is an error.
- [ ] **`PackageChecks`:**
  - `manifest.json` present and valid against `manifest.schema.json`. Each opis error becomes an issue with the field pointer.
  - `format` must be the expected value, and `version` must equal `BundleFormat::VERSION` (message: "unsupported bundle version N; this site reads version 1").
  - Every `checksums` entry's file exists and matches. On mismatch: "_base snapshot was modified; re-export instead of editing _base/".
  - A `_base/` file not listed in `checksums` is an error.
  - Unknown files are errors. Allowed: `manifest.json`, `LICENSE.md`, the six record files at the root, and the six under `_base/`.
  - Missing record files are fine, because partial bundles may drop files.
- [ ] **`StructureChecks`:** for every record file present (not `_base/`), each line:
  - must `json_decode` (error "invalid JSON: <msg>");
  - must be an object;
  - must validate against its schema. Collect all opis errors with `ErrorFormatter` and map them to the JSON pointer and message.
  - Cap at 200 issues per file, then add one "…and N more issues in this file" warning.
- [ ] **Tests** (start from a valid exported bundle written by `ExportContentBundleAction` into a temp dir, then mutate files):
  1. A valid bundle produces 0 issues.
  2. A missing manifest is an error.
  3. A wrong version gives an error with the message above.
  4. An edited `_base/entities.jsonl` fails the checksum.
  5. A stray file `notes.txt` is an unknown-file error.
  6. A deleted `geo_refs.jsonl` produces no issue.
  7. A broken JSON line gives an error with the right line number.
  8. The unknown key `sumary` gives an error with field `/sumary` or the root pointer, and a message mentioning it.
  9. A wrong enum value gives an error with the field pointer.
  10. Records and references do not run when structure fails.
- [ ] Run, pint, commit (`feat(content-bundle): bundle validator package and structure layers`).

### Task 7: Record and reference checks, and `content:validate`

**Files:**
- Create: `api/app/Support/ContentBundle/Validation/{RecordChecks,ReferenceChecks}.php`
- Create: `api/app/Actions/ContentBundle/ValidateContentBundleAction.php`, `api/app/Console/Commands/ContentValidateCommand.php`
- Modify: `api/app/Support/ContentBundle/Validation/BundleValidator.php` (wire the two layers)
- Test: `api/tests/Feature/ContentBundle/ValidateRecordsAndReferencesTest.php`, `api/tests/Feature/ContentBundle/ContentValidateCommandTest.php`

- [ ] **`RecordChecks`** (errors unless noted):
  - Duplicate `id` within a file. The message names both line numbers.
  - Duplicate relationship `(source_entity_id, target_entity_id, relationship_type, start_year, end_year)` among non-delete lines. The same triple with different years is legitimate: a ruler can have several reigns over one polity.
  - Duplicate chronicle `slug` among non-delete lines.
  - **Warning**: the same `wikidata_id` on two entity lines.
  - `start_year > end_year` on any object that has both non-null. Year pairs: relationships `start_year/end_year`; geometry periods `start_year/end_year`; geo refs `temporal_start_year/temporal_end_year`; chronicles and entries `start_year/end_year`; each `entities.temporal_ranges` item `start_year/end_year`.
  - **Text year vs integer year.** Pairs: relationships `(temporal_start, start_year)` and `(temporal_end, end_year)`; geo refs `(temporal_start, temporal_start_year)` and `(temporal_end, temporal_end_year)`; temporal ranges `(start_date, start_year)` and `(end_date, end_year)`. When both are non-null, the leading signed integer of the text (`/^-?\d+/`, the rule from `EntityData::extractYear`) must equal the integer. If only the sign differs, the message says "BCE/CE sign mismatch: text says -0331, year is 331". Otherwise it says "year mismatch".
- [ ] **`ReferenceChecks`:**
  1. Collect the ids of every non-delete line per type (live ids) and every delete line (deleted ids).
  2. Reference fields:
     - entities: `primary_geo_ref_id` → geo_refs;
     - relationships: `source_entity_id`, `target_entity_id` → entities;
     - geometry_periods: `entity_id`, `source_event_id` → entities, `relationship_id` → relationships;
     - geo_refs: `entity_id` → entities, `geometry_period_id` → geometry_periods;
     - chronicle_entries: `chronicle_id` → chronicles, `primary_relationship_id` → relationships, `entities[].entity_id` → entities.
  3. For each non-null reference on a non-delete line:
     - pointing at a deleted id → error "references <type> <id>, which this bundle deletes";
     - in live ids → ok;
     - otherwise, with `$againstSite`, it must exist on the site (batch `whereIn` lookups of ≤ 1000 ids per query), else error "references <type> <id>, which is neither in the bundle nor on the site";
     - without `$againstSite` → warning "… not in the bundle; it must exist on the site at import".
  4. **Same-owner rules** (DB FKs `entities_primary_geo_ref_owner_fk`, `egr_geometry_period_owner_fk`):
     - an entity's `primary_geo_ref_id` must point at a geo ref whose `entity_id` is that entity;
     - a geo ref's `geometry_period_id` must point at a geometry period with the same `entity_id`.

     Check against the bundle line when the target is in the bundle, and against the site row with `$againstSite`. Otherwise skip.
  5. **With `$againstSite`, for each deleted id**, find site rows that still reference it:
     - relationships by source/target;
     - geometry_periods by `entity_id`, `source_event_id`, `relationship_id`;
     - geo_refs by `entity_id`, `geometry_period_id`;
     - `chronicle_entry_entities` by `entity_id`;
     - chronicle_entries by `primary_relationship_id`;
     - entities by `primary_geo_ref_id`.

     A referencing row is excused if the bundle deletes it, or has a line for it whose reference field is present with a different value. Otherwise it is an error on the delete line: "N site records still reference it (e.g. relationships <id>); delete or re-point them in this bundle". `chronicle_entry_entities` rows are excused when the bundle has the entry's line with an `entities` list that no longer contains the id.
  6. **With `$againstSite`, check every geometry value** (geometry periods `geom`/`territory_geom`, entity `locations[].geom`/`territory_geom`) with `SELECT ST_IsValid(g), ST_IsValidReason(g) FROM (SELECT ST_GeomFromGeoJSON(?) g) s`. Invalid → error with the reason. A PostGIS exception → error "unreadable GeoJSON: <msg>".
- [ ] **`ValidateContentBundleAction(string $path, bool $againstSite): ValidationReport`** opens the reader, runs the validator and closes the reader. An unreadable path or archive produces a single package error instead of throwing.
- [ ] **`content:validate {path} {--against-site} {--json}`:**
  - Text mode prints each issue as `ERROR file:line: field: message` / `WARN …`, then a summary line `N errors, M warnings`.
  - `--json` prints `ValidationReport::toArray()` as pretty JSON and nothing else.
  - Exit 0 when valid (warnings allowed), 1 when there are errors. Code 2 is reserved for the import planner's conflicts in part 2; mention that in the class docblock.
- [ ] **Tests:**
  - each record rule (a duplicate id names both lines; the sign-slip message);
  - a dangling reference: warning without `--against-site`, error with it, ok when the record exists on the site;
  - a reference to a deleted id;
  - deleting an entity that a site relationship still references is an error; the same delete is ok when the bundle also deletes the relationship, and ok when it re-points it;
  - an invalid polygon (self-intersecting bow-tie) with `--against-site` gives an error with a reason;
  - command text output and exit codes;
  - `--json` shape;
  - **round trip**: export a seeded dataset (as in Task 5), then `content:validate --against-site` exits 0 with 0 issues.
- [ ] Run the full ContentBundle suite (`$R php artisan test --filter ContentBundle`), pint, commit (`feat(content-bundle): record and reference checks and content:validate`).

### Task 8: Format guide and docs index

**Files:**
- Create: `docs/schemas/content-bundle.md`
- Modify: `docs/README.md` (add the guide under schemas), `docs/schemas/README.md` if it exists
- Modify: the spec's status line → `Status: in progress (part 1: export + validate)`

- [ ] **Write `docs/schemas/content-bundle.md`**, the human guide. It covers:
  - the four-step workflow with the exact commands;
  - the bundle layout;
  - the record-shape table and nested lists;
  - the editing rules (spec §3, adapted to what part 1 implements; import arrives in part 2);
  - validation layers and how to read the report (`file:line: field: message`, exit codes);
  - profiles;
  - scopes, with examples;
  - where the schemas live (`api/resources/schemas/content-bundle/v1/`).

  Keep it practical: worked examples of editing a summary, adding an alias, adding a new entity with a relationship to it (generated UUID), and deleting a relationship.
- [ ] Link it from `docs/README.md` in the schemas section, matching the existing entry style.
- [ ] In the spec's §2 manifest example, change `scope` to a list of strings (`["chronicle:fall-of-constantinople"]`) to match the implementation.
- [ ] **Smoke test on real data** (controller runs this; export is read-only). Run `content:export` against the dev database (not the test DB) into the scratchpad as a zip, then `content:validate --against-site`. Expect 0 errors. Pre-existing problems show as "unchanged since export" warnings. Record counts and timings in the task report.
- [ ] Commit (`docs(content-bundle): format guide for content bundles`).
