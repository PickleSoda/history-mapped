# Generic map stories (any entity, any chronicle, on the timeline) — design

**Status:** proposed 2026-10-31. It builds on schema v2 (`2026-10-31-map-story-schema-v2-design.md`) and becomes schema 3. It must land before the admin/AI editor, so that the editor is built on the generic format.

## Problem

The atlas has two halves of one idea, and they don't meet.

| | Chronicles (302 chronicles, 25,870 entries) | Map stories (5 battles) |
|---|---|---|
| Steps | entries | steps |
| Dates per step | yes: `start_year`/`end_year`, which drive the timeline | no: a free-text `time` label; the timeline is set once to `doc.year` |
| Entities per step | yes: a primary relationship plus secondary entities | only units with QIDs |
| Custom drawing | none: the map flies to a bbox and shows the entities | arrows, formations, terrain, notes, states |
| Attached to | itself | one entity (`map_stories.entity_id`, any type) |
| Vocabulary | — | military: sides, units, formations, charges |

Trade routes (29 `trade_route` entities and many trade chronicles), epidemics (91 `epidemic_disease`), migrations (148), wars (1,528) and voyages all need the drawing half *and* the timeline and entity half.

## Decision: one story format, attachable anywhere, timeline-native

### 1. Attachment

- `map_stories` gains `chronicle_id` (nullable fk); `entity_id` becomes nullable. A story needs at least one of the two.
- **An entity's story:** any entity type can have one. Examples: Battle of Waterloo, the Black Death, the Silk Road, the Magellan expedition.
- **A chronicle's map layer:** when a chronicle has a story, its steps may set `entry: <chronicle entry_id>`. While the chronicle plays, the map draws the matching step's layers, and the ChroniclePlayer stays the text UI. Entries without a matching step fall back to today's behaviour.

### 2. Steps live on the timeline

- **`step.date`:** `{year, month?, day?, end?: {year, month?, day?}}`. While a story plays, each step sets the timeline instant, so the historical basemap, borders and the entity layer follow the story. `time` stays as the display label.
- **`doc.period`:** `{start, end}`, defaulting to the range of the step dates. It is used for listing stories and for ambient mode (§5).
- **Battles** may give a single `date` on the document. Steps without dates inherit it, so v1 and v2 documents stay valid.

### 3. Entities on each step

- **`step.entities`:** `[{entity_id?, wikidata?, name, role?, show?: boolean}]`. These are the relevant entities for the step: the people, polities, cities and events involved. The sync resolves QIDs to `entity_id`, as it does for commanders today.
- **Player:** shows them as chips that open the entity.
- **Map:** `show: true` draws that entity's *own atlas geometry* for the step's date, on top of the story layers. Examples: a polity's border, a city point, a route's line. A story can therefore reuse the atlas's data instead of redrawing it.
- **Atlas overlay during a story:** today the story hides the whole entity overlay. It now shows only the entities attached to the current step.

### 4. A generic vocabulary

Schema v2's terrain items plus per-step `terrain_state` are already "persistent features with a per-step state". They become the general mechanism, named **features**. `terrain` stays as an accepted alias so v1 and v2 files still load.

**Feature kinds** (terrain kinds plus these):

| Group | Kinds |
|---|---|
| Point | `city`, `port`, `market`, `mine`, `outbreak`, `site` |
| Line | `route`, which needs `route_kind`: `trade`, `voyage`, `migration`, `pilgrimage`, `campaign` or `road` |
| Area | `region`, which needs `region_kind`: `spread`, `extent`, `influence`, `affected` or `front` |

Features may set `entity` (an entity id or QID) and `goods: [string]` for trade.

**Feature state per step** (`step.features`, alias `terrain_state`) adds these fields:

| Field | Values |
|---|---|
| `active` | boolean: draw the feature or not, for example a route opening or closing |
| `state` | adds `infected`, `peak`, `recovered`, `founded`, `abandoned`, `disrupted`, `new` |
| `value_n` + `value_label` | proportional symbol size, route width, or region shading. Examples: deaths, cargo volume, population |
| `intensity` | 0–1, for colour ramps such as the spread of an epidemic |
| `area` / `line` | replace the feature's geometry from this step on: a spreading region, a moving front |
| `area_from_entity` | the area is that entity's atlas geometry at the step's date |

**Renderer behaviour:**
- **Routes:** a line whose width follows `value_n`, with animated dashes flowing in the route's direction (`bidirectional` gives two-way dashes). Goods appear in the tooltip.
- **Regions:** fill shaded by `intensity`. When a region's geometry changes between steps, the renderer crossfades it rather than morphing it. When it doesn't change, the shade animates.
- **Point features:** proportional circles for `value_n`.

**Actors.** `sides` and `units` stay, but the names are generic:
- `sides` are the parties: belligerents, trading powers, or none at all, since a side is optional for non-military stories.
- New point unit kinds:
  - `army`: a campaign-scale marker, not a formation;
  - `fleet`;
  - `caravan`;
  - `merchant_ship`;
  - `expedition`;
  - `group`: people on the move.
- New move types: `sail`, `trade`, `migrate`, `explore`, `spread`.

**Story kinds:**
- the current `battle`, `naval_battle`, `siege` and `campaign`;
- plus `war`, `trade_route`, `epidemic`, `migration`, `exploration`, `expansion` (a polity's growth or collapse), `diffusion` (religion, technology, language) and `event`.

Validator spread and teleport limits are set per kind; `epidemic` and `exploration` are continental or global.

**Legend.** The player shows an automatic legend (sides, route kinds, region shading) with optional `legend: [{swatch, label}]` entries.

### 5. Ambient mode: stories everywhere on the timeline

When no story is playing:
- **Display:** stories with `ambient: true` show a faint version of their features on the atlas. Typical opt-ins are trade routes, spread regions and migration paths. What shows is the state at the step whose date is nearest to, and not after, the current instant, inside the current view.
- **Interaction:** clicking a feature opens a "Play" card.
- **Endpoint:** `GET /api/v1/map-stories/ambient?year=&bbox=` returns compact precomputed geometry per step for each story. It is computed at sync time and stored on the row, and it is ETag-cached like the map features.
- **Opt-in:** battles default to `ambient: false`. They stay as the swords icon on their entity.

So a viewer scrubbing to 1348 sees the Black Death's spread region, and at 1450 the Hanseatic routes, without opening anything.

## Samples to prove it

One sample per new shape, built with the existing toolkit:

1. **Black Death, 1346–1353** (`epidemic`): spread regions per half-year, outbreak cities with death estimates, and the Caffa–Messina–Marseille ship arrows. Step entities: cities, the Golden Horde, Genoa. Ambient on.
2. **A trade network** (`trade_route`): the Hanseatic League or the Venice–Alexandria spice route, with routes by volume, ports, goods, and disruptions such as war or plague. Ambient on.
3. **1918 influenza** (`epidemic`, global scale): three waves as region intensity, troop-ship arrows, and city points. This is the user's "flu expansion" example.
4. **One chronicle map layer:** pick an existing trade chronicle, such as "Indian Ocean Dhow Trade, Ports and Monsoon Commerce", and give its entries steps with routes and monsoon wind arrows.

## Out of scope

- Morphing polygons.
- Per-feature time series finer than steps.
- User-contributed stories through the public contribution flow, which waits for the admin editor.
