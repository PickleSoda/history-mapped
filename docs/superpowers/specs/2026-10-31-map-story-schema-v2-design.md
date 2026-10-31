# Map-story schema v2 — design

**Status:** approved 2026-10-31. Extends schema 1 (`2026-10-31-battle-maps-and-descriptions-design.md`). Every v1 document stays valid unchanged.

**Why:** the five sample authors listed what schema 1 could not express. This adds those features, items 1–7 plus extras, as one contract shared by four implementations, which must change together:

| Layer | Files |
|---|---|
| Pipeline vocabulary and validator | `pipeline/map_stories/schema.py`, `validate.py` |
| API validator | `api/app/Support/MapStory/MapStoryVocabulary.php`, `MapStoryDocument.php` |
| Web parser and renderer | `web/src/lib/schemas/map-story.ts`, `web/src/lib/map-story/*`, `StoryOverlay.tsx`, `StoryPlayer.tsx` |
| Authoring guide | `docs/implementation-docs/map-story-authoring.md` |

## Versioning

- `schema` may be `1` or `2`. Every field below is optional and additive.
- Validators accept both versions. The new fields are accepted only when `schema: 2`; a v1 document that uses one gets an error saying to bump `schema`.
- The web parser stays tolerant. Unknown enum values degrade to the v1 default: a block for formations, `advance` for moves, `label` for notes.

## 1. Off-stage placements and off-map arrows

- **`placement.frame: false`** — the unit is drawn, but it is left out of the step's automatic camera framing (`stepBounds`) and out of the validator's spread checks. Use it for distant reserves and approaching armies.
- **`move.continues: {toward: LngLat, label?: string}`** — the arrow's last point is extended toward `toward`, a far point that may be off-map, as a fading dashed tail. The `label` (for example "to Brussels") is drawn near the map edge. The tail is not framed.
- **Off-screen indicator (renderer only)** — a unit that is on the field but outside the viewport gets a small chevron on the viewport edge in its side's colour. The chevron's tooltip is the unit's label.

## 2. Detach, split and merge

- **`placement.from: unitId`** — set on a unit's first placement. The unit detaches from `from`: it tweens out of that unit's position in the previous frame instead of fading in. The validator checks that `from` was on the field in the previous step.
- **`placement.into: unitId`** — the unit merges into `into` during this step. It tweens to the target's position, then leaves the field (it resolves as hidden afterwards). The target must be on the field in this step.
- Strength changes go on the placement as usual (`strength`, `strength_n`).

## 3. Beats (sub-phases within a step)

```jsonc
"beats": [
  { "label": "Norman cavalry feign flight", "positions": {...}, "moves": [...], "notes": [...] },
  { "label": "…then wheel on the pursuers", "positions": {...}, "moves": [...] }
]
```

- **Resolution:** the step's own `positions` apply first, then each beat's `positions` in order. The step's resolved frame, which carries forward, is the state after the last beat.
- **Arrows and notes:** the step's own `moves`/`notes` show for the whole step. A beat's `moves`/`notes` appear when that beat plays and stay until the step ends.
- **Playback:** stepping forward plays the beats in sequence, about 1.2 s each after the step's own tween, and shows the beat's `label` as a map caption. Jumping or stepping backward lands directly on the final frame.
- **Helper:** the validator and the renderer expose `resolve_beats(doc, step_index)` / `resolveBeats(doc, i)`, which return `[frame_before_beats, after_beat_1, …]`. The existing `resolve_steps` / `resolveFrames` keep their signature and output.
- **Validator:** the teleport check runs per beat. A beat needs `positions` or `moves`. Each step may have at most 4 beats.

## 4. Terrain and strongpoint state per step

```jsonc
"terrain_state": { "hougoumont": { "held_by": "allied", "state": "burning" } }
```

- **`step.terrain_state`** maps a terrain id to `{held_by?: sideId | null, state?: TerrainState, label?: string}`. It carries forward like positions, and a later step can override or clear it (`held_by: null`).
- **`TerrainState`:** `held | contested | captured | burning | destroyed | flooded`.
- **Rendering:** a held point or area feature (village, farm, building, fortification, camp, bridge, pass) is outlined or tinted in the holder's colour. A small state glyph is drawn: flames, crossed swords, or a flag for captured.
- **Captured baggage or camp** that is a *unit* uses the unit state `captured` (below).

## 5. Light, wind and sun

- **`step.light`:** `night | dawn | day | dusk`. It carries forward and defaults to `day`. The renderer tints the map, for example a dark blue multiply at night and a warm wash at dawn and dusk. Units and labels stay readable.
- **`step.wind`:** `{from: degrees, strength?: "light"|"strong", label?: string}`, carried forward.
- **`step.sun`:** `{from: degrees, label?: string}`, for example the sun in the Roman eyes at Cannae. It carries forward.
- **Wind/sun widget:** a small HUD on the map shows these with an arrow pointing *with* the wind (the direction it blows toward).

## 6. Formation detail, composite units and contingents

**Placement fields (formations only):**
- `lines: 1–5` draws the formation as that many parallel lines spread over its `depth`, with gaps between them. Example: the triplex acies.
- `lanes: 0–12` cuts that many open lanes through the depth, evenly spaced across the front. Example: Zama.
- `subunits: 1–24` splits the front into that many separate blocks. With `lines > 1` the lines are staggered into a checkerboard. With `shape: "square"`, each subunit is a small hollow square. Example: the Waterloo infantry squares.

**Unit fields:**
- `ranks: [{kind: UnitKind, share: 0–1}]` gives a composite unit's bands from front to back, for example archers in front of heavy infantry. The shares sum to about 1, and each band shows its kind's glyph.
- `strength_n: integer` is a numeric strength for sizing and tooltips. `strength` stays the display string. A placement may override either one.
- `contingent: contingentId` refers to a contingent of the unit's side.

**Side fields:**
- `contingents: [{id, name, color?}]` are contingents within a side, for example the Hanoverians and Dutch-Belgians under Wellington, or the Persian satrapies. A unit of a contingent is drawn in the contingent's `color`, or in an automatic shade of the side's colour. Tooltips name the contingent.

**New unit kinds:**
- `standard`: a point marker drawn as a flag. Examples: the eagle at Waterloo, the dragon standard at Hastings.
- `ship`: a point marker drawn as one hull oriented by its facing. Use it for named flagships and single vessels; `warship` stays a formation of many hulls.
- Both join `POINT_UNIT_KINDS`.

**New unit states:**

| State | Applies to | Meaning |
|---|---|---|
| `killed` | point markers | crossed-out glyph; the marker stays on the map |
| `wounded` | point markers | marker drawn with a small red cross |
| `captured` | any unit | unit drawn hatched in the captor's colour; needs `placement.by: sideId` |
| `sunk` | `warship`, `ship`, `transport` | hull drawn faded, with a wreck glyph |
| `aground` | `warship`, `ship`, `transport` | hull drawn tilted and dimmed |
| `burning` | any unit | flame glyph |

The validator warns when a state doesn't fit the unit's kind, for example `sunk` on infantry.

## 7. Naval

- **`move.orient: "path"`** — while tweening, the unit's facing follows the path tangent. If the next placement gives no `facing`, the unit lands facing along the final segment.
- **New move types:**
  - `ram`: a short, heavy arrow with a beak head.
  - `back_water`: a dashed arrow drawn backward.
  - `blockade`: a dotted line with no head and tick marks toward the enemy.
  - `landing`: an arrow from water to shore with a beach chevron.
- **Land/water check (validator warnings):**
  - Ship kinds must sit inside a `sea`/`lake` terrain area, or within 400 m of a `river`/`coast` line.
  - Land kinds must not sit inside a `sea`/`lake` area unless they are on a `landing` move.
  - The check is skipped when the document has no water terrain.

## Extras

- **`conjectural: true`** on a placement, move, terrain item or note marks it as reconstructed rather than attested. It is drawn with a dashed outline or arrow and lighter fill. The legend line reads "dashed = conjectural".
- **`alt_sites: [{at, label, note?}]`** (document level) are other proposed sites of the battle. They are drawn on every step as faint ghost pins with a "?" and listed in "About this reconstruction". They are not framed.
- **`fire` moves** gain `target: unitId`, where the arrow ends at that unit's resolved position and the path's last point is ignored, and `arc: true` for a ballistic arc (artillery, archers) instead of a straight line.
- **Terrain `mask`** (area) hides the modern reference layers inside it (modern water, waterways, place names), drawn with the land colour under the historical terrain. Use it for landfill and modern reservoirs.
- **Text limit:** `uncertainty` may be up to **1500** characters.

## Out of scope

- Free-hand drawing and arbitrary polygons for units.
- Animated projectiles.
- 3D terrain.
- Per-unit timelines that span steps.
