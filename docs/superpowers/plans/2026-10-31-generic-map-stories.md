# Generic map stories (schema 3) — Implementation Plan

> **For agentic workers:** three agents run in parallel after schema v2 lands. Part G1 is the pipeline, toolkit, samples and guide; Part G2 is the API; Part G3 is the web. Steps use checkbox (`- [ ]`) syntax.

**Goal:** a map story can belong to any entity or to a chronicle. Its steps are dated, so they drive the timeline, and they carry the relevant entities. It can draw trade routes, spread regions and valued places as well as battles. Stories that opt in show faintly on the plain atlas at their dates (ambient mode). Four samples prove it: the Black Death, the Hanseatic League, the 1918 influenza, and the map layer of one chronicle.

**Spec:** `docs/superpowers/specs/2026-10-31-generic-map-stories-design.md`, approved by the user, including that a chronicle *carries a map layer* and that ambient mode is *opt-in per story*. The contract below makes the spec exact. Where the two differ, this plan wins.

## The contract (schema 3)

Every schema 1 and 2 document stays valid. The fields below require `"schema": 3`, and a v1 or v2 document that uses one is rejected with "bump schema".

### Document level

```jsonc
{
  "schema": 3,
  "kind": "epidemic",                 // + war, trade_route, migration, exploration, expansion, diffusion, event
  "entity": { "name": "Black Death", "wikidata": "Q42005" },   // optional when "chronicle" is set
  "chronicle": { "slug": "indian-ocean-dhow-trade-..." },       // optional; sync adds "chronicle_id"
  "year": 1346,                       // still required: the first year, used for sorting and cards
  "period": { "start": {"year": 1346}, "end": {"year": 1353} }, // optional; defaults to the range of step dates
  "ambient": true,                    // default false
  "legend": [ { "swatch": "#7f1d1d", "label": "Plague reached", "style": "fill" } ],   // style: fill|line|dot
  "sides": [],                        // may be empty for non-military kinds
  "units": [ { "id": "genoese-galleys", "kind": "merchant_ship", "label": "Genoese galleys" } ],  // side optional when sides is empty
  "features": [ ... ],                // = v2 "terrain"; "terrain" stays an accepted alias; both at once is an error
  "steps": [ ... ]
}
```

**Validator rules:**
- At least one of `entity` or `chronicle` is required.
- When `ambient` is true, every step needs a `date`.

### Dates

A date spec is `{year: int, month?: 1–12, day?: 1–31}` and uses the same year numbering as `year` and the entity years. A step's `date` is a date spec with an optional `end` date spec. A step without a `date` inherits the document's `year`, which keeps v1 and v2 battles valid.

### Features

Persistent features are the generalised v2 terrain items:

```jsonc
{ "id": "caffa", "kind": "outbreak", "label": "Caffa", "at": [35.38, 45.03],
  "entity": { "name": "Feodosia", "wikidata": "Q..." },          // optional; sync adds entity_id
  "side": "genoa",                                               // optional: colour from that side
  "goods": ["grain", "furs"],                                    // optional, trade only
  "route_kind": "trade",            // required for kind=route: trade|voyage|migration|pilgrimage|campaign|road
  "region_kind": "spread",          // required for kind=region: spread|extent|influence|affected|front
  "bidirectional": false, "active": true, "value_n": 0, "intensity": 0, "conjectural": false }
```

**New kinds:**
- Point: `city`, `port`, `market`, `mine`, `outbreak`, `site`.
- Line: `route`.
- Area: `region` and `mask`, the latter from v2.

**`area`** may be one ring or a list of rings (a multipolygon of simple polygons, with no holes) for every area kind.

### Steps

```jsonc
{ "id": "s3", "title": "…", "narrative": "…",
  "date": { "year": 1347, "month": 10, "end": { "year": 1348, "month": 3 } },
  "entry": 4,                        // chronicle stories only: the entry's sequence_order; sync adds "entry_id"
  "entities": [ { "name": "Messina", "wikidata": "Q13666", "role": "first Sicilian outbreak", "show": true } ],
  "features": {                      // = v2 terrain_state (alias accepted; both at once is an error)
    "plague-1348": { "area": [[...ring...], [...ring...]], "intensity": 0.8, "value_label": "≈30–50% died" },
    "lubeck-bergen": { "active": true, "value_n": 120, "value_label": "120 ships a year", "state": "disrupted" },
    "caffa": { "state": "infected" },
    "kingdom-x": { "area_from_entity": { "wikidata": "Q..." } } },
  "positions": {}, "moves": [], "notes": [], "beats": [], "light": "day" }
```

- **Feature state fields:** the v2 fields (`held_by`, `state`, `label`) plus `active`, `value_n`, `value_label`, `intensity` (0–1), `at`, `line`, `area`, and `area_from_entity` (a linked ref that sync resolves to `entity_id`).
- **Carry-forward:** each key carries forward on its own, as positions do.
- **New feature states:** `infected`, `peak`, `recovered`, `founded`, `abandoned`, `disrupted`, `new`.
- **New point unit kinds:** `army`, `fleet`, `caravan`, `merchant_ship`, `expedition`, `group`.
- **New move types:** `sail`, `trade`, `migrate`, `explore`, `spread`.

**Validator scale per kind** (spread km / teleport m):

| Kinds | Spread km | Teleport m |
|---|---|---|
| battle, naval_battle, siege | as v2 | as v2 |
| campaign, war, expansion | 3,000 | 150,000 |
| diffusion, event | 5,000 | 300,000 |
| epidemic, trade_route, migration, exploration | 20,000 | 2,000,000 |

### What sync stores

The stored document adds resolved ids next to the authored refs:
- `chronicle.chronicle_id`
- `steps[].entry_id`
- `steps[].entities[].entity_id`
- `features[].entity.entity_id`
- `steps[].features[*].area_from_entity.entity_id`

The `map_stories` table also gains:
- `chronicle_id` (nullable fk; set null on delete);
- `entity_id`, which becomes nullable, with a check constraint that one of the two is set;
- `period_start` and `period_end` (integer years);
- `ambient` (boolean);
- `bbox` (geometry or four numbers);
- `ambient_steps` (jsonb, precomputed, described next).

### API

- **`GET /api/v1/map-stories/{slug}`** is unchanged, plus `chronicle_id`, `period` and `ambient`.
- **`ChronicleResource`** gains `map_story: {id, slug, kind, title, step_count} | null`.
- **`GET /api/v1/map-stories/ambient?year=Y&bbox=w,s,e,n`** returns stories with `ambient`, a period that covers Y, and a bbox that intersects. For each, it gives the state at the last step whose date starts at or before Y:
  ```jsonc
  { "data": [ { "slug": "black-death", "kind": "epidemic", "title": "…", "step_index": 3, "step_title": "…",
      "features": { "type": "FeatureCollection", "features": [
        { "type": "Feature", "geometry": {...}, "properties": {
            "id": "plague-1348", "kind": "region", "region_kind": "spread", "route_kind": null,
            "label": "…", "color": "#7f1d1d", "value_n": null, "intensity": 0.8, "state": null } } ] } } ] }
  ```
  - Only active `route`, `region`, `outbreak`, `port`, `market` and `city` features are returned, with geometry simplified to about 0.01°.
  - `color` comes from the feature's side, or else from a fixed palette per route_kind or region_kind, which G2 defines and G3 mirrors.
  - The response is ETag-cached like `/entities/map`.

## Ground rules (all parts)

- **Shared checkout.** Work in `/home/pickle/code/history-mapped`.
  - Don't commit, and don't run git commands that change state.
  - Edit only the files your part owns. If you need a change in a file you don't own, ask for it in your report.
  - A peer session in another worktree edits `web/src/components/map/MapCanvas.tsx`, `api/routes/api.php` and the map-config files. Keep your changes to those files to a few lines.
- **Commands:** use the docker, Pint, Python and web commands from `2026-10-31-map-story-schema-v2.md` § Ground rules. Never run PHP on the host, and never run Pint with `--dirty`.
- **HTTP:** every request uses User-Agent `history-mapped/1.0 (https://github.com/PickleSoda/history-mapped)`. Never put an email address in a request.
- **Research:** use the toolkit's `research` and `places` commands, which are cached, not WebFetch.
- **Prose:** write it yourself. Don't copy Wikipedia sentences.

---

## Part G1 — vocabulary, validator, toolkit, samples, guide

**Owns:**
- `pipeline/map_stories/` (all modules and `stories/`)
- `pipeline/tests/test_map_stories*.py`
- `api/resources/map-stories/*.json`
- `api/resources/entity-descriptions/*.md` for the sample entities that have none
- `docs/implementation-docs/map-story-authoring.md` and `battle-map-bulk-run.md`

- [ ] **G1.0 Lint fix carried over from v2.** In `lint.py`, `check_arrows` compares a beat's arrows with the frame before all the beats. It should compare with the previous beat, `resolve_beats(doc, i)[k-1]`. Today it wrongly flags Cannae's second beat. Add a test.
- [ ] **G1.1 Vocabulary and validator.**
  - Schema 3 in `schema.py`: the kinds, feature kinds and states, unit kinds, move types and per-kind scales.
  - `validate.py`:
    - accept the `features`/`terrain` and `step.features`/`terrain_state` aliases, normalising to the new names internally;
    - date specs (month and day ranges; `end` not before the start);
    - ambient requires dates;
    - the entity/chronicle requirement;
    - `side` optional when there are no sides;
    - multipolygon areas;
    - `area_from_entity`, `entry` (an integer ≥ 1) and the per-kind scale limits.
  - Keep `resolve_steps` stable, and add `resolve_features(doc) -> list[dict]`, which gives the feature state per step.
  - Tests: one valid and one invalid case per rule.
- [ ] **G1.2 Toolkit.**
  - `layout.py` and `geo.py` helpers:
    - `great_circle(a, b, n)`;
    - `route(*waypoints, sea=False)`, which densifies the waypoints and keeps them as given (no land avoidance);
    - `buffer_ring(point, km, n=24)`;
    - `hull_region(points, buffer_km)`, a convex hull plus a buffer that gives a spread region from infected places;
    - `merge_rings(...)`, which returns a list of rings.
  - `lint.py` scales its checks by kind and skips the formation checks for point-only kinds.
  - The cheatsheet gains a short "non-battle stories" block.
  - `preview` draws routes (width by `value_n`), regions (shaded by `intensity`) and valued points.
- [ ] **G1.3 Samples**, each with `ambient: true` except the chronicle layer, whose ambient flag is your call. Check every entity in the local DB first.
  1. **`black-death`**: entity "Black Death" (Q42005). Half-yearly steps from 1346 to 1353:
     - `hull_region` spread regions grown from the outbreak places;
     - outbreak points with mortality labels;
     - the Caffa → Constantinople → Messina → Marseille ship arrows (`spread`);
     - step entities: the Golden Horde, Genoa, the cities affected, Pope Clement VI;
     - `conjectural` where the routes are inferred.
  2. **`hanseatic-league`**: entity "Hanseatic League" (Q42908; the audit may flag its DB type, but leave it). About 8 steps from the 13th to the 16th century:
     - Kontore (Bruges, Bergen, Novgorod, London) as `market` features;
     - the Lübeck–Hamburg axis and the Baltic and North Sea `route`s, with `goods` and `value_n` where the sources give numbers;
     - the war with Denmark (Peace of Stralsund) as `disrupted`, then restored;
     - the decline.
  3. **`1918-influenza`**: entity "1918 influenza pandemic" (Q178275). Steps for the three waves, spring 1918 to 1919:
     - region `intensity` by continent;
     - troop-ship `sail`/`spread` arrows;
     - city points with deaths;
     - step entities such as Camp Funston and Brest.

     Note the uncertainty about where it started in `uncertainty`, and give `alt_sites` for the competing origins.
  4. **A chronicle layer** for the chronicle titled "Indian Ocean Dhow Trade, Ports and Monsoon Commerce (c. 500-1000 CE)". Look up its slug and entries in the DB.
     - Steps keyed by `entry` (sequence_order) for the entries that the map can show;
     - ports as `port` features with goods;
     - monsoon `wind` per season;
     - dhow routes.

  For each sample: `build` and `check` with no errors, one contact-sheet look, and a description `.md` only if the entity has no `description` yet (check the DB).
- [ ] **G1.4 Guide.** Add a "Stories beyond battles" section covering each kind, the features/state table, dates and timeline, step entities, chronicle layers and ambient mode, with one short example each. Keep it compact: a cheatsheet line beats a paragraph.
- [ ] **G1.5 Verify.**
  - pytest for both files, and `check` on all nine stories.
  - Once G2's validator is in (check `git diff api/app/Support/MapStory`), run `php artisan map-stories:sync`. If G2 isn't there yet, say so in your report; the orchestrator will sync.

**Report** in at most 15 lines.

---

## Part G2 — API

**Owns:**
- the new migration
- `api/app/Models/MapStory.php`
- `api/app/Support/MapStory/*`
- `api/app/Actions/MapStory/*`
- map-story controllers and resources, including a new `MapStoryAmbientController`
- `ChronicleResource` (the `map_story` field only)
- `api/tests/Feature/MapStory/*` and new tests
- the `map-stories/ambient` route line in `api/routes/api.php`, which must come before `{slug}`
- `docs/schemas/` or the API docs for map stories, if any exist

- [ ] **G2.1 Migration.**
  - The `map_stories` columns: `chronicle_id` fk (nullable, set null on delete); `entity_id` made nullable; a check that one of the two is set; `period_start` and `period_end`; `ambient`; a bbox (PostGIS geometry with a GiST index, following how the codebase stores bboxes); `ambient_steps` jsonb.
  - Indexes on (ambient, period_start, period_end).
- [ ] **G2.2 Validator.** Port the G1.1 structural rules for schema 3 into `MapStoryDocument::errors()` and `MapStoryVocabulary`. Errors only; warnings stay in Python.
- [ ] **G2.3 Sync.**
  - **Resolution:**
    - `chronicle.slug` → `chronicle_id`;
    - `entry` → `entry_id`, by sequence_order within that chronicle; an unknown entry is a sync error;
    - every linked ref → `entity_id`: step entities, feature entity, `area_from_entity`.

    Resolve through the same QID resolver the commanders use, with the namesake/temporal guard where it applies.
  - **Columns:** compute `period_*` and `bbox` (the story's points, lines and areas, excluding `frame: false` placements and `continues` tails).
  - **Ambient steps:** compute `ambient_steps` as a list of `{index, start, title, features}`, with each step's simplified FeatureCollection exactly as the contract describes. For `area_from_entity`, use the entity's geometry for the step's year from the existing geometry-period storage.
  - **Tests:** resolution, errors and ambient precompute.
- [ ] **G2.4 Endpoints and resources.**
  - Implement the ambient endpoint per the contract: a year and bbox filter, a payload built straight from `ambient_steps`, and an ETag. `MapStoryController` must still return 404 for unknown slugs.
  - Add `map_story` to `ChronicleResource`.
  - `MapStoryResource` gains `chronicle_id`, `period` and `ambient`.
  - Check that entity `map_stories[]` and `has_map_story` still work for stories with no entity: no null errors.
  - Feature tests for each.
- [ ] **G2.5 Verify.** Run the full PHP suite, plus Pint on your files. If G1 has finished its samples, sync them and check the endpoints with curl, for example `/map-stories/ambient?year=1348&bbox=-15,25,50,65`.

**Report** in at most 15 lines, including the exact palette for route_kind and region_kind, so G3 can mirror it. If G3 is still running, send the palette to it as well.

---

## Part G3 — web

**Owns:**
- `web/src/lib/schemas/map-story.ts` and `chronicle.ts` (the `map_story` field)
- `web/src/lib/map-story/*`
- `web/src/lib/api/map-stories.ts`
- `web/src/hooks/useMapStory.ts` and the new `useAmbientStories.ts`
- `web/src/components/map/StoryOverlay.tsx` and the new `StoryAmbientLayer.tsx`
- `web/src/components/atlas/Story*.tsx`
- `ChroniclePlayer.tsx` (the minimal changes to integrate the map layer)
- the battle-maps section of `docs/architecture/frontend-app.md`

- [ ] **G3.1 Schema.** Parse schema 3 tolerantly, with the aliases normalised in one place (`normalizeDocument`).
- [ ] **G3.2 Timeline.**
  - While a story plays, each step's `date.year` (or the inherited `year`) sets the timeline instant. The timeline is year-based, so the month and day are display-only.
  - The step date appears in the player above the title; `time` is still shown when it is present.
- [ ] **G3.3 Step entities.**
  - The player shows them as chips that open the entity.
  - `show: true` draws the entity's atlas geometry for that step, using `useEntityGeometries` as ChroniclePlayer does, in a highlighted style under the story's layers.
  - While a story plays, the entity overlay stays hidden apart from these entities.
- [ ] **G3.4 Feature rendering** in `layers.ts`:
  - **Routes:** width scales with `value_n`; animated flowing dashes (a `line-dasharray` animation or a moving pattern, which must stop under reduced motion); `disrupted` dashed in red; `active: false` hidden; goods in the tooltip.
  - **Regions:** fill shaded by `intensity`, using the G2 palette. When the geometry changes between steps, crossfade over 400 ms with two sources; otherwise animate the shade.
  - **Valued points:** circles sized by `value_n`, with `value_label` in the tooltip and next to the point.
  - **Feature states:** glyphs for the new states.
  - **Units:** neutral colour when a unit has no side.
  - **Legend:** a compact chip legend in the player, from `legend` and the kinds in use.
- [ ] **G3.5 Chronicle layer.**
  - `StoryOverlay` takes its document and step from either source: the `?story=` URL, as now, or the active chronicle (`chron`/`step`) when that chronicle has a `map_story`. In the second case, the step is the one whose `entry_id` matches the current entry; if none matches, draw nothing.
  - In chronicle mode, keep the chronicle's camera and entity behaviour, and draw only the story's layers. The story's step `camera` wins if it is set.
  - In ChroniclePlayer, a small "Map layer" badge appears when the chronicle has one.
- [ ] **G3.6 Ambient layer.**
  - Fetch with `useAmbientStories(year, bbox)` (debounced; keyed on the year and a bbox rounded to tiles) and draw it in `StoryAmbientLayer.tsx` at low opacity under the entity layers.
  - Hide it while a story or chronicle plays.
  - Hovering a feature shows the story title; clicking opens a small card with "Play", which enters the story at `step_index`.
  - Mount it next to StoryOverlay with as few lines as possible in MapCanvas.
- [ ] **G3.7 Verify.**
  - Run vitest (add tests for normalisation, date-to-instant and the feature state carry-forward), tsc, eslint and build.
  - Browser checks in your own tab, at most about 12 screenshots: the five battles still play; each new sample plays with the timeline moving; ambient shows the Black Death at 1348 and the Hansa at 1400 on the plain atlas; the chronicle layer draws while the Indian Ocean chronicle plays.
  - If G1's samples aren't synced yet, use a temporary fixture inserted with psql, and delete it afterwards.

**Report** in at most 15 lines.

---

## After this plan

- The admin/AI editor plan (`2026-10-31-map-story-admin-and-ai-editing.md`) builds on schema 3.
- A `story-author` agent, a sibling of `battle-author` for the non-battle kinds, is written once the four samples show which tools they need.
