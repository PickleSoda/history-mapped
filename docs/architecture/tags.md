# Tags: finding chronicles and entities

Chronicles and entities share one tag vocabulary. A tag belongs to a **facet**,
and a row can carry many tags per facet, so "prehistoric Anatolia" is just
`prehistory` + `anatolia`.

| Facet | Examples | Applies to |
|-------|----------|------------|
| `era` | Prehistory, Neolithic, Ancient, Bronze Age, Classical Era, Medieval, Early Modern, Modern, Contemporary | both |
| `region` | Africa › Egypt, Asia › East Asia › China, Europe › Iberia, The Mediterranean, Silk Roads, Global | both |
| `theme` | War & Conflict, Religion & Belief, Trade & Economy, Farming & First Cities, Slavery & Abolition | both |
| `type` | Regional history, Empire or dynasty, War or campaign, Peoples & cultures, Thematic survey, Single event | chronicles |
| `topic` | anything else, created on demand ("Vikings", "Crusades") | both |

## Data model

- `tags` — keyed by `slug`, with `name`, `facet`, `parent_slug`, `description`,
  `sort_order`, and `start_year`/`end_year` on era tags.
- `chronicle_tags (chronicle_id, tag, source)` and `entity_tags (entity_id, tag, source)`.
  `entity_tags` predates the vocabulary and now holds a slug with an FK to `tags`.
- **Ancestors are stored.** Tagging `china` also writes `east-asia` and `asia`, so a
  filter on `asia` is a plain lookup. UIs collapse the set back to the most
  specific tags (`Tag::leafSlugs()`, `web/src/lib/tags.ts#displayTags`).
- **`source`** ranks `manual` > `curated` > `derived`. Writing a source replaces
  its own rows and the lower-ranked ones (`SyncTagsAction`):
  - `manual`: an admin save, or the API/pipeline `tags` field. On a chronicle it
    is the whole set, and `tags:sync` leaves that chronicle alone. On an entity
    it sits beside the derived tags.
  - `curated`: `api/database/data/tags/chronicles.json` (one line per chronicle,
    keyed by slug), or the optional `tags` array in a pipeline `chronicle.json`.
  - `derived`: recomputed by `tags:sync` on every run.

The vocabulary itself is `api/database/data/tags/vocabulary.json`. It is the
source of truth for every facet except `topic`: a tag removed from the file is
deleted, and its pivot rows cascade.

## Derivation (`DeriveTagsAction`)

Set-based SQL, about 4s for 37k entities.

- **Chronicles:** era tags from `start_year`/`end_year`, only for chronicles with
  no era tag and no admin tags. This covers new imports until they are curated.
- **Entities:**
  1. Era from the entity's own primary temporal range. Origin types (cities,
     monuments, works, texts, codes) take only the era they began in.
  2. Era from the entity's chronicles, if it has no dates.
  3. Sub-eras (Neolithic, Bronze/Iron Age) from its chronicles, only if its
     dates fall in the sub-era's window. Those periods differ by region, so they
     are never derived from dates alone.
  4. Region from its chronicles, skipping `thematic` ones.
  5. Theme from entity type (battle → War & Conflict, religious text → Religion…).
  6. Ancestors of all of the above.

  Inheritance from chronicles (steps 2–4) is **weighted**: a tag is kept only if
  at least half as many of the entity's chronicles carry it as carry its most
  common tag in the same facet. Hub entities such as Rome or Julius Caesar, which
  appear in dozens of chronicles, keep their dominant regions instead of
  collecting every one.

## Commands

```bash
php artisan tags:sync                    # vocabulary + curated chronicles + all derived tags (idempotent)
php artisan tags:sync --vocabulary-only  # just upsert vocabulary.json
```

Run `tags:sync` after a batch of chronicle imports. `chronicles:import` applies
an artifact's `tags` and derives chronicle eras itself, but entity tags only
catch up on `tags:sync`. The base seed (`ReferenceTableSeeder` → `TagSeeder`)
loads the vocabulary only.

## API

- `GET /api/v1/tags`: the vocabulary in display order, with `parent`, and
  `chronicle_count`/`entity_count`. Unused topic tags are omitted. Cached for
  5 minutes.
- `GET /api/v1/chronicles?search=&tags[]=&sort=chronological|recent|title|impact`:
  `tags` also accepts a comma-separated string. `search` matches titles, slugs
  and tag names.
- `GET /api/v1/entities?tags[]=` (several tags) or `?tag=` (one tag).
- Chronicle and entity payloads carry `tags` as slugs, ancestors included.

Tag filters are **AND across facets and OR within a facet**: `medieval` +
`europe` + `asia` means medieval chronicles in Europe or Asia
(`Tag::filterGroups()`). An unknown slug matches nothing.

## UI

- **Atlas SPA:** the Chronicles tab has a search box that also suggests matching
  tags, plus a "browse by" facet switcher. Regions drill down (Asia → East Asia →
  China), and picking a narrower region replaces the broader one. Rows show
  clickable tag pills. The filter lives in the URL as `ct=slug,slug`, so it can be
  shared; setting it from an entity or chronicle page (`TagPills`) opens the
  Chronicles tab.
- **Admin:** the chronicle index has a tag filter, a sort control and tag badges.
  Create/edit have a tag picker (`components/tag-picker.tsx`) that can create
  topic tags. The entity form's comma-separated tags field edits only manual tags.
