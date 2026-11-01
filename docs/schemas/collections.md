# Curated collections

Editorial sets of entities, chronicles, map stories and tags for the public site's browse pages (`/browse`,
`/browse/collections/:slug`). They are authored as JSON files, loaded into the `collections` table by an artisan command,
and served read-only under `/api/v1`. There is no admin editing in v1: the file is the source of truth.

Code: `App\Models\Collection`, `App\Actions\Collection\SyncCollectionFileAction` (file to row),
`App\Actions\Collection\ResolveCollectionItemsAction` (items to payloads), `App\Console\Commands\SyncCollectionsCommand`,
`App\Http\Api\V1\Controllers\CollectionController`. Spec: D4 in
[`../superpowers/specs/2026-11-01-public-site-design.md`](../superpowers/specs/2026-11-01-public-site-design.md).

## File format

One file per set: `api/resources/collections/<slug>.json`.

```jsonc
{
  "slug": "the-roman-world",            // required; lower-case words joined by "-"; must equal the file name
  "title": "The Roman World",           // required, ≤ 255
  "subtitle": "From a city on the Tiber to an empire of the Mediterranean",   // optional, ≤ 255
  "description": "Two sentences of **markdown**.",                            // optional, ≤ 10,000
  "cover_qid": "Q2277",                 // optional: the cover entity (Wikidata id, or an entity uuid)
  "status": "published",                // optional: published (default) | draft
  "sort_order": 10,                     // optional integer, default 0; lower comes first
  "items": [                            // required list (may be empty), ≤ 200, in display order
    { "kind": "entity",    "ref": "Q1048", "note": "Optional editorial note, ≤ 1,000." },
    { "kind": "chronicle", "ref": "fall-of-the-roman-republic-c-100-30-bce" },
    { "kind": "story",     "ref": "battle-of-cannae" },
    { "kind": "tag",       "ref": "classical" }
  ]
}
```

| `kind` | `ref` | resolved through |
|---|---|---|
| `entity` | Wikidata id (`Q…`); an entity uuid is accepted as a fallback | `entities.wikidata_id` (the highest-impact entity, should two share an id), else `entities.entity_id` |
| `chronicle` | chronicle slug | `chronicles.slug` |
| `story` | map-story slug | `map_stories.slug` |
| `tag` | tag slug | `tags.slug` |

Rules the sync enforces (an invalid file is reported and skipped, the others still load):

- the file is a JSON object; unknown top-level fields are errors (keys starting with `_`, e.g. `_comment`, are ignored);
- `slug` matches the file name; `status` is `published` or `draft`;
- each item has exactly `kind`, `ref` and optionally `note`; an entity `ref` is `Q<digits>` or a uuid; other refs are slugs
  (no spaces or slashes); the same `kind` + `ref` appears once.

Refs use Wikidata ids and slugs, not uuids, because entity merges and re-imports change uuids. **Items are resolved when
served, not at sync time**: a ref that matches nothing is simply left out of the response (with a `Log::warning` when the
set is shown), never an error. Only `cover_qid` is resolved at sync time, into `collections.cover_entity_id` (FK to
`entities`, set null on delete); a cover that matches no entity is a warning and leaves the cover empty. Re-run the sync
after a content load that may have replaced the cover entities.

## Loading: `php artisan collections:sync`

```bash
docker compose -f docker/docker-compose.yml exec app php artisan collections:sync            # resources/collections
docker compose -f docker/docker-compose.yml exec app php artisan collections:sync --path=/tmp/sets
```

Upserts by slug and deletes nothing: to hide a set, set `"status": "draft"` (or delete its row by hand). Prints one line per
file (`<slug> ...... created | updated | unchanged | invalid`), then any errors and warnings; exits non-zero when a file was
invalid.

Table `collections`: `collection_id uuid pk`, `slug text unique`, `title text`, `subtitle text null`,
`description text null` (markdown), `cover_entity_id uuid null` (FK `entities`, null on delete), `items jsonb not null
default '[]'` (as written, with empty notes dropped), `status varchar(16) default 'published'` (check: draft | published),
`sort_order int default 0`, timestamps.

## API

Both endpoints are public, return `Cache-Control: public, max-age=300`, and only ever show `published` sets.

### `GET /api/v1/collections`

```jsonc
{ "data": [
  { "slug": "the-roman-world", "title": "The Roman World", "subtitle": "…", "description": "…markdown…",
    "cover": { /* EntitySummaryResource (as GET /entities lists it) */ } | null,
    "item_count": 15,
    "items_by_kind": { "entity": 8, "chronicle": 4, "story": 2, "tag": 1 } }
] }
```

Ordered by `sort_order`, then `title`. The counts include only items that currently resolve (one existence query per kind
for the whole list).

### `GET /api/v1/collections/{slug}`

The same object plus `items`, in file order, each `{kind, note, <kind>: payload}`:

```jsonc
{ "data": { "slug": "…", "title": "…", "subtitle": "…", "description": "…", "cover": { … } | null,
  "item_count": 4, "items_by_kind": { "entity": 1, "chronicle": 1, "story": 1, "tag": 1 },
  "items": [
    { "kind": "entity", "note": "…" | null, "entity": { /* EntitySummaryResource */ } },
    { "kind": "chronicle", "note": null, "chronicle": { /* ChronicleResource without entries (as GET /chronicles lists it):
        chronicle_id, slug, title, description, start_year, end_year, map_story, entry_count, tags, … */ } },
    { "kind": "story", "note": null, "story": { "id", "slug", "kind", "title", "year", "step_count",
        "entity": { "id", "name", "entity_type" } | null, "chronicle": { "slug", "title" } | null } },
    { "kind": "tag", "note": null, "tag": { "slug", "name", "facet", "parent", "description", "start_year", "end_year",
        "chronicle_count", "entity_count" } }
  ] } }
```

The story payload is the `GET /api/v1/map-stories` row; the tag payload is the `GET /api/v1/tags` row. Items resolve in
one query per kind (plus the chronicles' tags and map layers, eager-loaded). 404 for an unknown or draft slug.
