# Battle maps (map stories) and long descriptions — design

> **Date:** 2026-10-31
> **Status:** Sample phase (5 battles) — review the samples before bulk generation.
> **Authoring guide:** [`docs/implementation-docs/map-story-authoring.md`](../../implementation-docs/map-story-authoring.md)

## 1. Why

- Entities carry one-sentence `summary` and `significance` only (avg 112 chars);
  there is no long-form text anywhere, and chronicles have no introduction.
- Entity timelines are derived from relationships and read as boilerplate
  ("Hannibal led the forces involved in the action in 216 BCE.").
- Battles are a single pin. Even famous ones (Waterloo, Gaugamela, the Salamis
  of 480 BC) have no point at all, and nothing shows how they were fought.

## 2. What we add

1. **`entities.description`** — long-form text (3–6 plain paragraphs). Shown in
   the detail panel (first paragraphs, "Read more") and in full on the entity
   page. Editable in the admin form, by the admin AI, through contributions, and
   loadable from `api/resources/entity-descriptions/*.md`.
2. **`chronicles.description`** — an introduction for each chronicle, shown on
   the chronicle page and in the tour's first screen.
3. **Map stories** — a step-by-step battle map attached to an entity, played in
   the atlas: formation blocks per unit coloured by side, movement arrows,
   commander/camp markers, historical terrain, a narrative per step, animated
   between steps. The steps are the battle's detailed timeline.

## 3. Data model

### `map_stories`

| column | type | notes |
|---|---|---|
| `story_id` | uuid pk | `gen_random_uuid()` |
| `entity_id` | uuid fk → entities, cascade | the battle |
| `slug` | text unique | file name / URL key |
| `kind` | varchar(24) | battle, naval_battle, siege, campaign |
| `title` | text | |
| `year` | integer | for the timeline jump |
| `step_count` | smallint | for list views |
| `document` | jsonb | the schema-1 document, Q-ids resolved (below) |
| `source_path` | text null | `resources/map-stories/<slug>.json` when synced from a file |
| `content_hash` | text null | sha1 of the file, to skip unchanged files |
| `created_at`, `updated_at` | timestamps | |

Index `entity_id`. A JSON document (not normalised unit/step tables) because it
is authored, read, and replaced whole, and its vocabulary will still change
during the sample phase.

**Q-id resolution at sync:** `document.entity.entity_id`,
`sides[].polity.entity_id`, `sides[].commanders[].entity_id`,
`units[].entity_id` are filled from `entities.wikidata_id` when found (null
otherwise). The story's own entity must resolve (by Q-id, else exact name among
event entities) or the sync fails for that file.

### Description columns

`entities.description text null`, `chronicles.description text null`.

## 4. API (public, v1)

- `GET /api/v1/entities/{id}` — adds `description` and
  `map_stories: [{id, slug, kind, title, year, step_count}]` (always an array).
- `GET /api/v1/map-stories/{slug}` —
  `{"data": {"id", "slug", "kind", "title", "year", "step_count", "entity_id", "document": {…}}}`.
- `GET /api/v1/entities/map` (+ `/map/year`) feature properties gain
  `has_map_story: bool`, so the map can badge battles that have one.
- Chronicle list/show resources add `description`.

## 5. Commands

- `php artisan map-stories:sync [--slug=…] [--prune] [--force]` — read
  `resources/map-stories/*.json`, validate (schema 1, references), resolve
  Q-ids, upsert by slug; skip files whose hash is unchanged unless `--force`;
  `--prune` deletes rows whose file is gone.
- `php artisan entities:sync-descriptions [--force]` — read
  `resources/entity-descriptions/*.md` (front matter `wikidata`, `name`), set
  `entities.description` by Q-id (fallback: exact name, must be unique).

Both are idempotent, so the deploy can run them after `migrate` once the samples
are approved.

## 6. Atlas (web/)

- **Detail panel:** "About" (the description's first ~2 paragraphs, "Read
  more" → entity page) and, when the entity has a story, a prominent "Play the
  battle map" card.
- **Entity page:** full description; a "How the battle unfolded" section listing
  the story's steps (time, title, narrative), each opening the player there.
- **Story player:** URL `story=<slug>&sstep=<n>` (push history, like `chron`/`step`).
  Takes the left panel on desktop and the sheet on mobile, like the chronicle
  tour: title, date, sides (colour, commanders, strength, losses), step dots,
  step time/title/narrative, prev/next and autoplay. While active, the entity
  overlay is hidden, the timeline jumps to the story's year, and the map shows
  the story overlay framed on the step.
- **Story overlay (MapLibre):** terrain (rivers, ridges, hills, woods…) under
  everything; formation polygons computed client-side from `at/facing/width/depth/
  shape`, filled with the side colour (routed = faded + dashed outline,
  destroyed = ghosted); a unit-kind glyph and a label on each block; commander,
  camp and baggage pins; movement arrows styled by type with arrowheads; note
  callouts. Units animate (position, facing, size) between steps, sliding along
  their move arrow when the step has one.
- **Map badge:** battles with `has_map_story` get a distinct marker.

## 7. Sample phase

Five well-documented battles exercise the format: Cannae (216 BC, double
envelopment), Gaugamela (331 BC, oblique order and the wedge), Salamis (480 BC,
naval), Hastings (1066, shield wall and feigned retreats), Waterloo (1815,
many corps, a second army arriving). Each sample author also writes the battle's
long description and reports what the schema could not express. We review the
samples in the atlas, adjust the vocabulary, then plan bulk generation:

- **Sources for bulk:** Wikipedia battle articles (deployment/battle sections),
  YouTube transcripts of animated-battle channels (fetchable with
  `youtube-transcript-api`; tested), primary-source summaries. Facts only; the
  prose is always original.
- **Who writes:** a Sonnet author per battle with the preview loop; Opus review
  for the famous ones.
- **Descriptions and chronicle introductions in bulk:** a separate pass over the
  campaign transcripts' entities, highest impact first.

## 8. Not in this phase

Admin editing UI for stories (they're files + sync for now), campaign-scale
stories (multi-day marches across a region), per-step terrain changes, sound,
3D/pitch cameras.
