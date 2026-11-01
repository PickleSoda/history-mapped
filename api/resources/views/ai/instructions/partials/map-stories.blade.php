## Map stories

A map story replays a battle, siege, campaign, epidemic, trade network, migration… step by step on the atlas. It belongs to an entity (`entity`) or is a chronicle's map layer (`chronicle: {slug}`). Read it with `get_map_story` (`slug`, or the `entity_id`; `part` = overview, sides, units, terrain, steps, step:<id>, full), start one with `create_map_story`, change it with `update_map_story`, check it with `validate_map_story`. The full guide: docs/implementation-docs/map-story-authoring.md.

The document (coordinates are `[lon, lat]`; bearings 0 = north; distances in metres; ids lowercase-kebab):

```
{schema: 3, slug, kind, entity: {name, wikidata}, chronicle?: {slug},
 title, date_label, year (first year, BCE negative), intro, outcome, uncertainty?, sources: [{title, url?, kind?}],
 period?: {start: {year}, end: {year}}, ambient?: bool (every step then needs a date), legend?: [{swatch, label, style}],
 sides: [{id, name, color "#rrggbb", polity?: {name, wikidata}, commanders: [{name, wikidata?}], strength?, losses?, contingents?}],
 units: [{id, side?, kind, label (≤28 chars), strength?, strength_n?, commander?, wikidata?, note?}],
 features: [{id, kind, label, at | line | area, route_kind? (route), region_kind? (region), entity?, goods?, value_n?, intensity?, active?, conjectural?}],
 steps: [{id, title, narrative (150–1100 chars), date?: {year, month?, day?, end?}, time?, entry? (chronicle layers: the entry's 0-based sequence_order),
   entities?: [{name, wikidata, role?, show?}], camera?, light?, wind?, sun?, focus?: [unit ids],
   positions: {unit id: {at, facing, width, depth, shape?, state?, with?, from?, into?, frame?, conjectural?}},
   moves: [{unit, type, path: [[lon, lat], …], label?, conjectural?}], notes: [{at, text (≤70), kind?}],
   features: {feature id: {state?, held_by?, active?, value_n?, value_label?, intensity?, at?/line?/area?/area_from_entity?}},
   beats?: [{label, positions?, moves?, notes?}] (≤4)}]}
```

Older stories say `terrain` for `features` and a step's `terrain_state` for its `features` — patch the key the story uses (`get_map_story` reports `features_key`).

Rules the map relies on:
- **Placements carry forward**: a step lists only the units that change. A unit's first placement needs `at` (or `with`). `at` is the formation's centre; `width` is its frontage across `facing`.
- **A move ends where the unit stands after the step**: when you move a unit (`positions.<id>.at`), add a `moves` arrow from where it stood to the new `at`, in the same step — a unit that jumps far without an arrow is a warning.
- **Feature state carries forward too**, key by key; `null` clears a key.
- Kinds and vocabularies are fixed (the validator lists them in its errors). Story kinds: battle, naval_battle, siege, campaign, war, trade_route, epidemic, migration, exploration, expansion, diffusion, event.

Patching (`update_map_story`, RFC 6902 JSON Patch):
- Read the part first; use the `pointer`s it shows (`/steps/3/narrative`, `/units/2/label`, `/steps/3/positions/roman-left/at`). Lists take an index or `-` (append); map keys are the unit or feature ids.
- Prefer small `replace`/`add` ops to rewriting whole steps. To insert a step use `add /steps/<index>`.
- The whole patch is checked: if it is rejected, nothing was staged — fix what the errors name and resend the whole patch. Warnings don't block; fix the ones that matter.
- Coordinates come from the place tools (`find_place`, `point_from_offset`, `point_between`, `nearest_coast`), never from memory. Round to 5 decimals.
- Write the prose yourself, plainly; keep it to what sources support. Mark reconstructed positions, routes and features `"conjectural": true` and say what is uncertain in `uncertainty`.
- Link people, polities and places by verified Wikidata Q-id (`verify_wikidata`).
