# Map story authoring guide

A **map story** replays how a battle (or siege, naval battle, campaign) unfolded,
step by step, on the atlas map: coloured formation blocks for each body of troops,
arrows for their movements, markers for commanders and camps, terrain the fight
turned on, and a short narrative per step. The atlas animates units between steps.

Design: [`docs/superpowers/specs/2026-10-31-battle-maps-and-descriptions-design.md`](../superpowers/specs/2026-10-31-battle-maps-and-descriptions-design.md).

## Pipeline

```
pipeline/map_stories/stories/<module>.py   build() -> dict      (you write this)
        │  python -m pipeline.map_stories build <module>        (validates, writes JSON)
        ▼
api/resources/map-stories/<slug>.json                            (committed, ships with the API image)
        │  php artisan map-stories:sync                          (resolves Q-ids, upserts the DB)
        ▼
map_stories table  →  GET /api/v1/map-stories/{slug}  →  atlas story player
```

Run Python through the repo's venv and memory cap:

```bash
scripts/capped.sh pipeline/.venv/bin/python -m pipeline.map_stories build battle_of_cannae
scripts/capped.sh pipeline/.venv/bin/python -m pipeline.map_stories preview api/resources/map-stories/battle-of-cannae.json
scripts/capped.sh pipeline/.venv/bin/python -m pipeline.map_stories preview api/resources/map-stories/battle-of-cannae.json --step 4
```

`preview` writes `output/map-stories/preview/<slug>/grid.png` (every step) or
`step-NN.png`, drawn over OpenTopoMap (contours, rivers, villages). **Look at the
preview** (read the PNG) and fix what's wrong before you finish: the preview is
the only way to see that the line really stands on the ridge and the river really
covers the flank.

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
| `nominatim("Canne della Battaglia")` | OSM place search → lon/lat (cached, 1 call/s) |
| `place_geometry("Fiume Ofanto", "waterway")` + `lines_of()` + `clip()` + `simplify()` | a real river / coast / lake outline near the field (query rivers by their local name) |
| `elevation(points)`, `profile(a, b)` | SRTM heights — find the ridge, the slope, the valley floor |

Get anchors from real sources: the battle's Wikipedia coordinates, OSM places
(villages, farms, rivers that still exist), elevation profiles for ridges and
hills. Where the ancient landscape differed (a river moved, a coastline silted up,
a marsh drained), say so in `uncertainty` and draw the historical feature as
terrain.

## The document (schema 1)

Coordinates are `[lon, lat]` (GeoJSON order). Bearings are compass degrees
(0 = north, 90 = east). Distances are metres. Ids are lowercase kebab-case.

```jsonc
{
  "schema": 1,
  "slug": "battle-of-cannae",             // unique, kebab-case; the file name
  "kind": "battle",                        // battle | naval_battle | siege | campaign
  "entity": {"name": "Battle of Cannae", "wikidata": "Q179591"},   // the atlas entity it belongs to
  "title": "Battle of Cannae",
  "date_label": "2 August 216 BC",
  "year": -216,                            // negative = BCE
  "intro": "…",                            // 1 paragraph: who, where, why they met here (250–1400 chars)
  "outcome": "…",                          // 1 sentence result
  "uncertainty": "…",                      // what is debated and which reconstruction this map follows
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

- **Unit kinds** — foot: `infantry`, `heavy_infantry`, `light_infantry` (skirmishers,
  velites, peltasts, riflemen), `pikemen` (phalanx), `archers`, `slingers`,
  `crossbowmen`, `musketeers`; mounted: `cavalry`, `heavy_cavalry` (cataphracts,
  knights, cuirassiers), `light_cavalry` (Numidians, hussars), `horse_archers`,
  `chariots`, `elephants`, `camels`; support: `artillery`, `siege_engine`; naval:
  `warship`, `transport`; markers (drawn as a pin, not a block): `commander`,
  `camp`, `baggage`. Use the closest kind and put specifics in `label`/`note`.
- **Shapes** (`positions.*.shape`): `block` (default), `line`, `column`, `wedge`
  (point toward the front), `crescent` (front bows forward by `curve` metres;
  negative `curve` bows it back), `square` (infantry square), `circle`.
- **States**: `ready` (default), `engaged`, `wavering`, `routed` (drawn faded and
  dashed), `destroyed` (ghosted), `hidden` (not drawn: an ambush not yet sprung,
  troops off the field).
- **Move types**: `advance`, `attack`, `charge` (thick), `flank`, `pursuit` — solid;
  `retreat`, `rout`, `feint` — dashed; `march` — dotted (approach, redeployment);
  `fire` — thin dotted (missile or artillery fire; may end at the target).
- **Note kinds**: `label`, `clash`, `death`, `capture`, `event`. ≤ 70 characters.
- **Terrain kinds**: points (`at`): `town`, `village`, `farm`, `building`, `bridge`,
  `pass`, `label`; lines (`line`): `river`, `stream`, `road`, `ridge`, `wall`,
  `coast`; areas (`area`, an unclosed ring): `hill`, `woods`, `marsh`, `lake`,
  `sea`, `island`, `fortification`, `camp`, `field`.

### Rules the atlas relies on

1. **Placements carry forward.** A step lists only units whose placement changes;
   each listed key (`at`, `facing`, `width`, `depth`, `shape`, `curve`, `state`,
   `label`) overrides the previous step's value. A unit appears from the first
   step that places it (`at` or `with` required then).
2. **`at` is the centre of the formation; `facing` is the bearing its front
   faces; `width` is its frontage, `depth` front-to-back.** A unit facing north at
   `at` occupies `width` metres east–west.
3. **Moves happen during the step they're listed in and end where the unit stands
   in that step.** The atlas slides the unit along the arrow's path into its new
   placement, so start the path at the unit's previous position and end it at the
   new `at` (a `fire` arrow may end on its target instead). The validator warns
   when they disagree or when a unit jumps far with no arrow.
4. **`with`** pins a marker (a commander, the baggage) to a unit; it's drawn just
   behind that unit and moves with it. Re-place it with `at` when it separates.
5. **Leave `camera` out** unless a step needs a wider or tighter frame than its
   units (an approach march, a close-up of one flank). The atlas frames each step
   on its visible units, arrows and notes.

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
to their pages.
