# Map story authoring guide

A **map story** replays how a battle (or siege, naval battle, campaign) unfolded,
step by step, on the atlas map: coloured formation blocks for each body of troops,
arrows for their movements, markers for commanders and camps, terrain the fight
turned on, and a short narrative per step. The atlas animates units between steps.

Design: [`2026-10-31-battle-maps-and-descriptions-design.md`](../superpowers/specs/2026-10-31-battle-maps-and-descriptions-design.md)
(schema 1) and [`2026-10-31-map-story-schema-v2-design.md`](../superpowers/specs/2026-10-31-map-story-schema-v2-design.md)
(schema 2), and [`2026-10-31-generic-map-stories-design.md`](../superpowers/specs/2026-10-31-generic-map-stories-design.md)
with the contract in [its plan](../superpowers/plans/2026-10-31-generic-map-stories.md) (schema 3: any
entity or chronicle, dated steps, routes, regions, ambient mode — see
[Stories beyond battles](#stories-beyond-battles-schema-3)). Running many authors at once:
[`battle-map-bulk-run.md`](battle-map-bulk-run.md).

## Pipeline

```
pipeline/map_stories/stories/<module>.py   build() -> dict      (you write this)
        │  python -m pipeline.map_stories build <module>        (validates, lints, writes JSON)
        ▼
api/resources/map-stories/<slug>.json                            (committed, ships with the API image)
        │  php artisan map-stories:sync                          (resolves Q-ids, upserts the DB)
        │  php artisan map-stories:relink                        (re-resolves stored stories: new entities, step geometry)
        ▼
map_stories table  →  GET /api/v1/map-stories/{slug}  →  atlas story player
        ▲   │
        │   └─ php artisan map-stories:export   (DB → JSON file, when edited in the admin)
  admin editor / AI tools (/map-stories/{slug}/edit; saves with a revision)
```

Run every command through the repo's venv and memory cap. `CLI` below means
`scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.map_stories`.

```bash
CLI cheatsheet                         # vocabulary, helper signatures, builder skeleton: read this first
CLI research "Battle of Cannae"        # infobox + section outline; --section NAME, --qids Q1 Q2 …
CLI places "Canne della Battaglia" --near Q179591 --elevation    # coordinates; --geometry river for a line
CLI build battle_of_cannae             # run the builder, validate + lint, write the JSON
CLI check api/resources/map-stories/battle-of-cannae.json        # validate + lint an existing file
CLI preview api/resources/map-stories/battle-of-cannae.json      # contact sheet of every step
CLI preview api/resources/map-stories/battle-of-cannae.json --step 4   # one step (id or number), 900×600
CLI digest api/resources/map-stories/battle-of-cannae.json --links     # check every Q-id's label and class
```

`preview` writes `output/map-stories/preview/<slug>/contact.png` (every step,
small), `step-NN.png` with `--step ID|N`, or the old large `grid.png` with
`--all-steps`, drawn over OpenTopoMap (contours, rivers, villages). **Look at the
preview** (read the PNG) and fix what's wrong before you finish: it is the only
way to see that the line really stands on the ridge and the river really covers
the flank. `digest` prints the prose without coordinates, for review.

## Editing in the admin, and the DB copy

The `map_stories` row is the **live copy**; the JSON file is how a story ships
and is reviewed. Stories can be changed in three places, all validated by the
same rules (`MapStoryDocument` errors block, `MapStoryWarnings` only warn):

- **Builder → file → sync** (above): the authoring path for new stories.
- **Admin editor**, `/map-stories` (sidebar "Map stories"; also listed on each
  entity's edit page, which has **Add a map story**, a skeleton with
  placeholders). The editor is split: a form (Overview, Sides & units,
  Features, Steps, JSON) on the left, and the public atlas on the right as a
  live preview of the unsaved draft. Pick points and paths by clicking the
  preview (double-click or Enter ends a path, Esc cancels), drag a unit in the
  preview to move it in the shown step, and "Use current preview view" copies
  the preview camera into a step or the overview. Saving sends the whole
  document; errors come back next to their tab and field. Needs `entities.write`.
- **AI agent** in the admin: `get_map_story`, `validate_map_story`,
  `create_map_story`, `update_map_story` (JSON Patch). Writes are proposals you
  approve, as for every other AI edit ([admin-ai-agent.md](admin-ai-agent.md)).

Every save — admin, AI, sync, import, restore — keeps a **revision** in
`map_story_revisions` (the last 50 per story; the first save of a story also
records the version before it). The editor's **History** drawer shows them,
loads one as a draft, or restores one (saved as a new revision).

**Sync and export policy.** The row remembers the hash of the file it was last
synced from (`file_hash`), when (`synced_at`), and when it was last edited in
the admin or by the AI (`edited_at`, `edited_by`). A story is **edited** when it
changed after its last sync; the list shows a badge and filters on it.

- `php artisan map-stories:sync` leaves an edited story alone ("kept admin
  edits — export first or use --force"), skips files whose hash is unchanged,
  and imports the rest. `--force` overwrites admin edits with the file.
- `php artisan map-stories:relink [--slug=…]` re-resolves the stored stories
  against the atlas as it is now, without reading files: Q-ids of entities
  created (or merged) since a story was synced, step entities' `geometry` and
  `ohm` (so also after OHM geo-refs change), the period, extent and ambient layer. Sync skips an unchanged file, so a story
  never links an entity created after its sync unless you relink. A story is
  saved, with one revision (`sync`, note `relink`), only when something
  changed; edits and the file bookkeeping are kept. It prints `relinked`,
  `unchanged` or `failed: …` per story. Run it **after creating entities a
  story names** (commanders, places) and **after a full content load** on prod.
- `php artisan map-stories:export [--slug=…] [--edited] [--path=…]` writes the
  DB copy back to `api/resources/map-stories/<slug>.json` in the builder's exact
  format (1-space indent, key order kept, trailing newline, resolved ids
  dropped), then marks the story synced. Commit the file to ship the edit; a
  story exported unchanged is byte-identical to its file.
- The **builder refuses** to overwrite a JSON file that changed since it last
  wrote it (hashes in `api/resources/map-stories/.build-hashes.json`, committed),
  because that file was hand-edited or exported from the admin. Fold the
  change into the builder module, then rebuild with `--force`.

Deleting a story in the admin removes the row and its revisions; a file of the
same slug brings it back on the next sync unless the file is deleted too.

## Writing a builder

A builder is a Python module whose `build()` returns the document. Work in
metres around real anchors with the helpers in `pipeline/map_stories/geo.py`,
never by guessing decimal degrees:

| Helper | Use |
|---|---|
| `offset(p, east=, north=)` | a point so many metres east/north of `p` |
| `dest(p, bearing, metres)` | a point along a compass bearing |
| `rel(p, facing, ahead=, right=)` | a point relative to a formation: ahead of / right of it |
| `lerp(a, b, t)`, `mid(a, b)`, `along(line, t)` | points between points / along a line |
| `arc(a, b, bulge)` | a curved path (flanking sweep) bowing `bulge` m to the right |
| `ellipse(c, rx, ry, rotate)` | an oval ring for a hill, wood, marsh or camp |
| `bearing(a, b)`, `distance(a, b)`, `local(p, origin)` | measure |
| `point_in_ring(p, ring)`, `distance_to_line(p, line)` | is it inside that area, how far from that shore |
| `elevation(points)`, `profile(a, b)` | SRTM heights: find the ridge, the slope, the valley floor |

Prefer the `places` command to the lookup helpers (`nominatim`, `place_geometry`).
Get anchors from real sources: the battle's Wikipedia coordinates, OSM places
(villages, farms, rivers that still exist), elevation profiles for ridges and
hills. Where the ancient landscape differed (a river moved, a coastline silted up,
a marsh drained), say so in `uncertainty` and draw the historical feature as
terrain.

## The document

Coordinates are `[lon, lat]` (GeoJSON order). Bearings are compass degrees
(0 = north, 90 = east). Distances are metres. Ids are lowercase kebab-case.

```jsonc
{
  "schema": 2,                             // 1 or 2; schema-2 fields (below) need 2
  "slug": "battle-of-cannae",             // unique, kebab-case; the file name
  "kind": "battle",                        // battle | naval_battle | siege | campaign
  "entity": {"name": "Battle of Cannae", "wikidata": "Q179591"},   // the atlas entity it belongs to
  "title": "Battle of Cannae",
  "date_label": "2 August 216 BC",
  "year": -216,                            // negative = BCE
  "intro": "…",                            // 1 paragraph: who, where, why they met here (250–1400 chars)
  "outcome": "…",                          // 1 sentence result
  "uncertainty": "…",                      // what is debated and which reconstruction this map follows (≤1500)
  "sources": [{"title": "Polybius, Histories 3.107–117", "kind": "primary"},
              {"title": "Battle of Cannae — Wikipedia", "url": "https://en.wikipedia.org/wiki/Battle_of_Cannae", "kind": "web"}],
  "camera": {"center": [16.13, 41.31], "zoom": 12.5, "bearing": 0},   // optional overview

  "sides": [
    {"id": "carthage", "name": "Carthaginian army", "color": "#6d28d9",
     "polity": {"name": "Carthage", "wikidata": "Q2429397"},
     "commanders": [{"name": "Hannibal", "wikidata": "Q36456", "role": "commander-in-chief"}],
     "strength": "c. 50,000", "losses": "c. 5,700 killed"}
  ],

  "units": [
    {"id": "hasdrubal-horse", "side": "carthage", "kind": "heavy_cavalry",
     "label": "Spanish & Gallic horse",       // ≤ 28 chars ideally; it's drawn on the map
     "strength": "c. 6,500", "commander": "Hasdrubal", "note": "Optional one-liner shown on hover"},
    {"id": "hannibal", "side": "carthage", "kind": "commander", "label": "Hannibal", "wikidata": "Q36456"}
  ],

  "terrain": [
    {"id": "aufidus", "kind": "river", "label": "Aufidus (Ofanto)", "line": [[16.10, 41.30], [16.15, 41.31]]},
    {"id": "cannae", "kind": "town", "label": "Cannae", "at": [16.1325, 41.3064]},
    {"id": "hill-x", "kind": "hill", "label": "…", "area": [[…], […], […]]}
  ],

  "steps": [
    {
      "id": "deployment",
      "title": "The armies deploy",
      "time": "Dawn",                        // free text: "c. 11:30", "Day 2, evening"
      "narrative": "…",                      // 2–6 sentences of original prose (150–1100 chars)
      "camera": {"center": […], "zoom": 13.4},   // optional; default frames this step's units + arrows
      "positions": {
        "hasdrubal-horse": {"at": [16.12, 41.30], "facing": 20, "width": 900, "depth": 80},
        "gallic-centre": {"at": […], "facing": 20, "width": 1400, "depth": 60, "shape": "crescent", "curve": 250},
        "hannibal": {"with": "gallic-centre"}
      },
      "moves": [
        {"unit": "hasdrubal-horse", "type": "charge", "path": [[…], […]], "label": "optional"}
      ],
      "notes": [{"at": […], "text": "Paullus is killed", "kind": "death"}],
      "focus": ["hasdrubal-horse"]           // optional: units to emphasise this step
    }
  ]
}
```

### Vocabulary

`CLI cheatsheet` prints the live lists. In short:

- **Unit kinds**: foot `infantry`, `heavy_infantry`, `light_infantry` (skirmishers,
  velites, peltasts, riflemen), `pikemen` (phalanx), `archers`, `slingers`,
  `crossbowmen`, `musketeers`; mounted `cavalry`, `heavy_cavalry` (cataphracts,
  knights, cuirassiers), `light_cavalry` (Numidians, hussars), `horse_archers`,
  `chariots`, `elephants`, `camels`; support `artillery`, `siege_engine`; naval
  `warship` (a squadron), `transport`; markers (a pin, not a block): `commander`,
  `camp`, `baggage`, and in v2 `standard` (a flag: an eagle, a royal banner) and
  `ship` (one named vessel). Use the closest kind and put specifics in `label`/`note`.
- **Shapes**: `block` (default), `line`, `column`, `wedge` (point toward the front),
  `crescent` (front bows forward by `curve` metres; negative bows it back),
  `square`, `circle`.
- **States**: `ready` (default), `engaged`, `wavering`, `routed` (faded, dashed),
  `destroyed` (ghosted), `hidden` (not drawn: an ambush not yet sprung, troops off
  the field). v2: `killed`, `wounded` (markers), `captured` (any unit; needs
  `by: <side id>`, the captor), `sunk`, `aground` (warship, ship, transport), `burning`.
- **Move types**: `advance`, `attack`, `charge` (thick), `flank`, `pursuit`: solid;
  `retreat`, `rout`, `feint`: dashed; `march`: dotted; `fire`: thin dotted (missile
  or artillery fire; may end at its target). v2 naval: `ram`, `back_water`,
  `blockade` (a cordon line with no head), `landing` (water to shore).
- **Note kinds**: `label`, `clash`, `death`, `capture`, `event`. ≤ 70 characters.
- **Terrain kinds**: points (`at`): `town`, `village`, `farm`, `building`, `bridge`,
  `pass`, `label`; lines (`line`): `river`, `stream`, `road`, `ridge`, `wall`,
  `coast`; areas (`area`, an unclosed ring): `hill`, `woods`, `marsh`, `lake`,
  `sea`, `island`, `fortification`, `camp`, `field`, and in v2 `mask`.

### Rules the atlas relies on

1. **Placements carry forward.** A step lists only units whose placement changes;
   each listed key overrides the previous value, including the v2 placement keys
   (`frame`, `lines`, `subunits`, …: reset them when the formation changes). A
   unit appears from the first step that places it (`at` or `with` required then).
2. **`at` is the centre of the formation; `facing` is the bearing its front
   faces; `width` is its frontage, `depth` front-to-back.** A unit facing north at
   `at` occupies `width` metres east–west.
3. **Moves happen during the step (or beat) they're listed in and end where the
   unit stands after it.** Start the path where the unit stood and end it at the
   new `at` (a `fire` arrow may end on its target; a `blockade` is just a line).
   The validator warns when they disagree or when a unit jumps far with no arrow.
4. **`with`** pins a marker (a commander, the baggage) to a unit; it's drawn just
   behind that unit and moves with it. Re-place it with `at` when it separates.
5. **Leave `camera` out** unless a step needs a wider or tighter frame than its
   units (an approach march, a close-up of one flank). The atlas frames each step
   on its visible units, arrows and notes.

## Schema 2 features

Set `"schema": 2` to use any of these; a schema-1 file that uses one fails with
"… need schema 2". **Use a feature only where the sources support it**, and mark
reconstructions `conjectural`. Full semantics are in the reference at the end.

| Feature (where) | Example | Use it when |
|---|---|---|
| `frame: false` (placement) | `"bulow": {"frame": false}` | a distant reserve or approaching army is drawn but must not pull the camera out; set `true` when it arrives |
| `continues` (move) | `"continues": {"toward": [4.44, 50.41], "label": "to Charleroi"}` | the march goes on off the map (a fading tail, not framed) |
| `from` (placement) | `"artemisia": {"from": "carians", "at": […]}` | a detachment splits off: on its first placement it slides out of its parent |
| `into` (placement) | `"artemisia": {"into": "carians"}` | a unit rejoins another: it slides onto it and is then off the field |
| `beats` (step) | see below | one step holds a quick sequence: a feint, then the wheel |
| `terrain_state` (step) | `{"hougoumont": {"held_by": "allied", "state": "burning"}}` | a farm, village, camp or bridge is held, contested, captured, burning, destroyed or flooded |
| `light` (step) | `"light": "dawn"` | the time of day matters: `night`, `dawn`, `day` (default), `dusk` |
| `wind`, `sun` (step) | `"wind": {"from": 135, "strength": "strong", "label": "Volturnus"}`, `"sun": {"from": 95}` | a source says wind or sun mattered; `from` is the direction it comes from |
| `lines` (placement) | `"lines": 3` | the formation stood in separate lines (the triplex acies) |
| `lanes` (placement) | `"lanes": 4` | open lanes through the ranks (against chariots or elephants) |
| `subunits` (placement) | `"shape": "square", "subunits": 5, "lines": 2` | separate blocks across the front; with `square` they are squares, with `lines > 1` a chequerboard |
| `ranks` (unit) | `[{"kind": "archers", "share": 0.3}, {"kind": "heavy_infantry", "share": 0.7}]` | one body mixes arms front to back; shares sum to about 1 |
| `strength_n` (unit or placement) | `"strength_n": 200` | a sourced number; `strength` stays the display text |
| `contingents` (side), `contingent` (unit) | `{"id": "nassau", "name": "Nassauers", "color": "#…", "wikidata": "Q…"}` | a side is a coalition; units get the contingent's colour or a shade; a contingent's optional Q-id links it like a side's polity (the player's side list opens it) |
| `orient: "path"` (move) | `{"type": "march", "orient": "path", …}` | ships (or columns) turn along the route; not on `back_water` |
| `target`, `arc` (`fire` move) | `"target": "picton", "arc": true` | fire falls on a unit; `arc` for high-angle shooting |
| `conjectural` (placement, move, terrain, note) | `"conjectural": true` | a position, route or feature is reconstructed rather than attested (drawn dashed) |
| `alt_sites` (document) | `[{"at": […], "label": "Left-bank theory", "note": "…"}]` | the battle's site is disputed |
| `mask` (terrain area) | `{"kind": "mask", "area": […]}` | landfill or a modern reservoir covers the historical ground |

Beats play after the step's own movement, about a second each, with the label
as a caption:

```jsonc
"beats": [  // at most 4; each needs a label and positions or moves
  {"label": "Horsemen feign flight", "positions": {"french-horse": {"at": […]}},
   "moves": [{"unit": "french-horse", "type": "feint", "path": […]}]},
  {"label": "…then wheel on the pursuers", "positions": {…}, "moves": […], "notes": […]}
]
```

### Scale and realism

Size blocks from the numbers and frontages in the sources, not by eye:

- Close-order ancient/medieval foot: ~0.9–1 m of frontage per file; depth = ranks ×
  ~1 m. A 9,000-man phalanx 16 deep ≈ 560 m × 16 m. Rome at Cannae deepened its
  maniples so ~55,000 foot held only ~1.5–2 km.
- Cavalry: ~1–1.5 m per horse in close order, 4–8 ranks deep; light horse looser.
- Napoleonic: a battalion of 600 in three-rank line ≈ 180 m × 10 m; in column
  ≈ 60 × 50 m; a squadron ≈ 100 m front; an 8-gun battery ≈ 120 m.
- Ships: a trireme ≈ 37 m × 5 m; a squadron in line abreast ≈ 25–40 m per ship.

One block per tactically distinct body: what the sources describe moving on its
own. 8–20 units is typical for a battle. Too few and the manoeuvre can't be
shown; too many and the map is noise.

### Steps

6–12 steps for a battle: the approach or camps (if they matter), deployment, the
opening, each turning point, the collapse, the pursuit/aftermath. Each narrative
says what moves and why it matters, in 2–6 sentences. Give `time` where known.

### Text: original, plain, sourced

- Write every sentence yourself. Use Wikipedia, academic sources and video
  transcripts for **facts**; never copy or closely paraphrase their wording.
- Plain prose: no markdown, no lists, no emojis. Name people and places as the
  atlas does (English common names).
- Where sources disagree (numbers, the side of the river, the hour), pick the
  mainstream reconstruction, use it consistently, and say so in `uncertainty`.

## Stories beyond battles (schema 3)

Set `"schema": 3`. Schema 1 and 2 documents stay valid; a v1/v2 document that uses
anything below is rejected with "bump schema to 3". Samples:
`stories/black_death.py`, `hanseatic_league.py`, `influenza_1918.py` and the
chronicle layer `indian_ocean_dhow_trade.py`. `CLI cheatsheet` ends with a
one-screen summary.

**Kinds and scale.** The validator's spread (km from the centre) and teleport
(m between frames without an arrow) limits, and lint's arrow-start slack, scale
with the kind. Formation lint (overlap, contact, density, static) runs only for
military kinds with formation units.

| Kind | Use | Spread km / teleport m |
|---|---|---|
| `battle` `naval_battle` `siege` | as before (two sides, units) | 20–30 / 600–1,500 |
| `campaign` `war` `expansion` | a march, a war, a polity growing or collapsing | 3,000 / 150,000 |
| `diffusion` `event` | a religion, technology or language spreading; one event | 5,000 / 300,000 |
| `epidemic` `trade_route` `migration` `exploration` | continental or global | 20,000 / 2,000,000 |

`sides` may be `[]` for non-military kinds, and then units need no `side`;
`units` may be empty too (keep a ship or caravan marker for arrows). New point
unit kinds: `army` `fleet` `caravan` `merchant_ship` `expedition` `group`. New move
types: `sail` `trade` `migrate` `explore` `spread`.

**Attachment.** `entity` and/or `chronicle: {slug}` — at least one. Sync adds
`chronicle.chronicle_id`. `year` is still required: the first year, for sorting
and cards.

**Dates and the timeline.** A step's `date` is `{year, month?, day?, end?}`
(`when(1347, 10, end=(1348, 3))`); it moves the atlas timeline while the step
plays, and `time` stays the display label. A step without a date inherits
`year`. `period: {start, end}` defaults to the range of step dates. Steps out of
date order, dates outside `period`, and a `year` that isn't the first year are
warnings; a month outside 1–12, an impossible day, a day without a month, and an
`end` before its start are errors.

**Features** (= v2 `terrain`; the alias is accepted, both at once is an error):

| Group | Kinds | Required |
|---|---|---|
| Point (`at`) | terrain points + `city` `port` `market` `mine` `outbreak` `site` | — |
| Line (`line`) | terrain lines + `route` | `route_kind`: `trade` `voyage` `migration` `pilgrimage` `campaign` `road` |
| Area (`area`) | terrain areas + `region` | `region_kind`: `spread` `extent` `influence` `affected` `front` |

Optional on any feature: `entity` {name, wikidata} (sync adds `entity_id`),
`side` (colour from that side), `goods` [names], `bidirectional`, `active`
(default true; start a feature `false` and switch it on), `value_n`,
`intensity` 0–1, `conjectural`. Any `area` may be one ring or a list of rings
(`merge_rings` makes one), with no holes.

**Feature state per step** (`step.features`, alias `terrain_state`):

| Field | Meaning |
|---|---|
| `active` | draw it or not (a route opens or closes) |
| `state` | v2 states + `infected` `peak` `recovered` `founded` `abandoned` `disrupted` `new` |
| `value_n`, `value_label` | route width, circle size or shade, with its caption ("120 ships a year") |
| `intensity` | 0–1 colour ramp (an epidemic's severity) |
| `at` / `line` / `area` | replace the geometry from this step on (a growing region) |
| `area_from_entity` | `{wikidata}`: the area is that entity's atlas geometry at the step's date |
| `held_by`, `label` | as in v2 (`held_by` is not drawn on lines) |

Each key carries forward on its own; `None` clears it. A new `at`/`line`/`area`/
`area_from_entity` replaces the earlier geometry. `resolve_features(doc)` gives
each step's merged features. In a builder: `st.state("lubeck-bergen",
state="disrupted")`, `st.state("plague", area=hull_region(places, 160), intensity=.9)`.

**Geometry helpers:** `route(a, b, c, sea=True)` keeps the waypoints exactly
(name the capes and straits: there is no land avoidance) and densifies each leg
along the great circle; `great_circle(a, b, n)`; `buffer_ring(pt, km)`;
`hull_region(places, buffer_km)` (convex hull plus a buffer: a spread region
grown from infected places); `merge_rings(...)`. Nothing may cross the
antimeridian: show Pacific islands as points. Mark schematic hulls and inferred
routes `conjectural`, and say in `uncertainty` that they are schematic.

**Step entities.** `entities: [ent("Genoa", "Q1449", role="its galleys carried the plague", show=True)]`.
The player shows them as chips; `show: true` also draws the entity's own atlas
geometry for the step's date, so link polities with `show` rather than
redrawing them. Sync resolves Q-ids to `entity_id`; `digest --links` checks
them too. For a shown, linked entity, sync also stores its geometry at the
step's year (the step's `date.year`, else the story's `year`) as `geometry`
beside it, picking the first that exists:

1. its area: the territory (or polygon) geometry period covering the year,
   simplified (harder for a large empire, to keep the story small);
2. a dated point: a point or line geometry period covering the year;
3. its undated location (the entity's `geom`);
4. nothing (`geometry: null`; the chip still shows).

The atlas DB holds no polygons yet: polity borders live in OpenHistoricalMap.
So sync also stores `ohm: ["relation/123", …]` for a shown entity: its active
OHM geo-refs to a relation or way whose years cover the step's year (open ends
cover), the primary one when it covers, else the others by match score; never
a rejected ref or a `type=chronology` relation (OHM draws none). The player
outlines those on OHM's boundary-polygon tiles (`ohm_admin` / `boundaries`,
signed `osm_id`), as they stood at the step's date, instead of the dot; the
dot remains when no geo-ref covers the year. OHM's general tiles can't do
this: their boundary lines carry way ids, not the polity's relation.
`geometry` and `ohm` are resolved, not authored: export, the editor and
revisions drop them. A stored story without `geometry` (resolved before it
existed, or an admin preview draft) draws the entity's undated `geom`, fetched
by the player.

**Chronicle layers.** A story with `chronicle: {slug}` is the map layer of that
chronicle: give a step `entry: <the entry's sequence_order as stored>` (0-based)
for each entry the map can show. While the chronicle plays, the map draws the
matching step; entries without a step keep the default map. Each entry gets at
most one step, and sync fails on an unknown entry. Look the entries up first:

```bash
docker compose -f docker/docker-compose.yml exec -T db psql -U history-mapped history-mapped -At -c \
  "select e.sequence_order, e.start_year, left(e.narrative_text, 120) from chronicle_entries e
   join chronicles c using (chronicle_id) where c.slug = '<slug>' order by 1"
```

**Ambient mode.** `ambient: true` (default false) shows the story faintly on
the plain atlas: at year Y, the state of the last step whose date starts at or
before Y, inside the view. Only active routes, regions and `outbreak`/`port`/
`market`/`city` points are shown. Every step then needs a `date`. Opt in for
trade routes, spread regions and migrations; battles stay off.

**Legend.** `legend: [{swatch: "#7f1d1d", label: "Plague reached", style: "fill"}]`
(`fill` | `line` | `dot`) adds to the automatic legend.

## Entity descriptions

A battle author also writes the battle entity's long description:
`api/resources/entity-descriptions/<slug>.md`, loaded by
`php artisan entities:sync-descriptions`.

```markdown
---
wikidata: Q179591
name: Battle of Cannae
---
First paragraph: what happened, when, where, between whom, and the result.

Second paragraph: the background — how the armies came to be there.

Third/fourth: how the battle unfolded, the decisive moments, the commanders' choices.

Last: consequences and legacy; what remains debated.
```

3–6 paragraphs, 1,500–4,000 characters, plain text paragraphs separated by a
blank line (no headings, lists or markup). Original prose, same rules as above.

## Looking things up in the atlas DB

```bash
docker compose -f docker/docker-compose.yml exec -T db psql -U history-mapped -d history-mapped \
  -c "select entity_id, name, wikidata_id, entity_type from entities where name ilike '%Hannibal%'"
```

Link sides, commanders and named units to atlas entities by Wikidata Q-id when
the atlas has them; the sync resolves Q-ids to entity ids so the player can link
to their pages. Confirm every Q-id with `CLI research --qids` or `CLI digest --links`.

## Reference: schema 2 semantics

- **Beats.** The step's own `positions` apply first, then each beat's in order;
  the frame that carries into the next step is the one after the last beat. The
  step's own arrows and notes show for the whole step; a beat's appear when it
  plays and stay until the step ends. A beat's arrows start where the unit stood
  after the previous beat. `resolve_beats(doc, i)` in `validate.py` returns
  `[frame_before_beats, after_beat_1, …]`; `resolve_steps(doc)` returns each
  step's final frame.
- **`from` / `into`.** `from` goes on a placement where the unit was not on the
  field in the previous frame, and the parent must have been. An `into` unit
  resolves onto its target's point in that frame (the target must be on the
  field), then is `hidden`; give it a `state` again to bring it back.
- **`terrain_state`** (schema 3: `step.features`) carries forward key by key;
  `held_by: null` clears the holder. A holder is drawn on point and area features,
  not lines. Captured baggage or
  a camp that is a *unit* uses the unit state `captured` instead.
- **`light`, `wind`, `sun`** carry forward; light defaults to `day`. Change the
  sun's `from` as the day goes on rather than leaving the morning sun all day.
- **States that fit the kind:** `killed`/`wounded` on markers, `sunk`/`aground`
  on warship, ship and transport; anything else is a warning.
- **Land/water check** (warnings; skipped when the story draws no water):
  ships must sit inside a `sea`/`lake` area (and not on an `island`) or within
  400 m of a `river`/`coast` line; land units must not stand in a `sea`/`lake`
  area unless they have a `landing` move that step. Draw the historical water as
  a `sea` area, `conjectural` where its shore is approximate.
- **Spread and framing.** The spread check skips `frame: false` placements (and
  their arrows), `continues` tails and `alt_sites`; the atlas leaves them out of
  automatic framing too.
- **Errors vs warnings.** Unknown ids, bad enums or types, `captured` without
  `by`, more than four beats, a beat without positions or moves, and `from`/`into`
  that don't meet the rules above are errors (the API sync rejects them too).
  Teleports, stray arrows, spread, state/kind fit and land/water are warnings
  (Python only). `check` also lints (overlaps, units off an explicit camera,
  colliding notes): see [`battle-map-bulk-run.md`](battle-map-bulk-run.md).
