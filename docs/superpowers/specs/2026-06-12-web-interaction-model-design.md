# Web Interaction Model — Sidebar-Primary Entity & Chronicle Navigation — Design Spec

> **Date:** 2026-06-12
> **Status:** Design (proposed — foundational interaction model for the customer `web/` SPA; the admin dashboard can adopt it too).
> **Area:** `web/` (customer SPA, currently a stub) and `api/resources/js` (admin dashboard); the public read API.
> **Related:** [chronicle-dashboard-display-design](2026-06-12-chronicle-dashboard-display-design.md) (the Chronicles mode), [map-bbox-query-optimization-design](2026-06-12-map-bbox-query-optimization-design.md) (D19 borders-from-OHM + the bbox/index work this depends on), and the UI/UX reference [game_inspired_ui_ux.md](../../reference/implementation-docs/game_inspired_ui_ux.md).

## 1. Intent

Make a **sidebar list the primary way to find and select entities**, with the map as a spatial *view* rather than the
primary click target. Clicking a tiny point on a map (a person, a battle) is a poor affordance; a filterable, ranked list
is a far better one — and many entities (cultural works, languages, economic systems) have **no** geometry at all, so they
can only be reached from a list. This is the intended primary interaction for the customer web build.

This is not a new direction: the UI/UX reference already specifies an **"Entity Explorer"** (Civ VI Report Screen pattern:
"tabular browse with sort, filter, click-to-map", High priority) and **"Period Highlights"** (Era Score pattern: surface
high-`display_priority` entities when scrubbing to a period). This spec promotes those to the **primary** navigation model
and defines the selection behavior.

## 2. Goals / Non-goals

**Goals**
- A sidebar **Entity Explorer**: browse important entities, filtered by year + (optional) viewport + type/group + search,
  ranked by importance.
- A single **selection model** shared across the list, the map, and chronicles: select once, everything reflects it.
- **Selection behavior:** select an entity → if it has a point, highlight/pan to it on the map; if it has a territory
  (OHM-linked), highlight the OHM basemap feature; if it has **no geometry**, just highlight the list row and show its
  detail (no map action).
- **Bidirectional:** clicking a map marker highlights its list row, and vice versa.
- Compose with **Chronicles** (curated tours) and a **Selection detail** panel (Civilopedia-style stats + narrative).

**Non-goals (this spec)**
- Building the full `web/` SPA (this is the interaction-model spec; component build is a follow-on).
- Map lenses, comparison/balance-of-power, causal-chain trees — valuable (in the UI/UX reference) but later layers on this model.

## 3. The model (three aside modes + map + timeline)

```
 ┌───────────────────────── ambient stats ribbon (count • coverage • avg confidence) ─────────────┐
 │                                                                                                  │
 │   ┌────────────────────────────── map view ──────────────────────────┐   ┌── explorer aside ──┐ │
 │   │  OHM historical basemap (date-filtered) + entity marker overlay   │   │ [Browse|Chronicles| │ │
 │   │  • markers for point entities (icon by type, size by impact)      │   │  Selection]         │ │
 │   │  • OHM feature highlight for territory entities                   │   │                     │ │
 │   │  • click marker ⇄ highlights list row                             │   │  Browse: ranked     │ │
 │   └───────────────────────────────────────────────────────────────────┘   │  filterable list    │ │
 │                                                                            │  Chronicles: tours  │ │
 │   ┌──────────────────────── timeline scrubber (year, BCE-aware) ─────────┐ │  Selection: detail  │ │
 │   └──────────────────────────────────────────────────────────────────────┘ └────────────────────┘ │
 └──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Browse (Entity Explorer)
- Source: `GET /v1/entities` (`ListEntitiesAction`) filtered by `year`/range, optional `bbox` (current viewport),
  `types`/`group`, `search`, `min_confidence`; ranked by `impact_score`/`display_priority`; paginated/virtualized.
- Grouped/tabbed by `entity_group` (POLITY/PLACE/EVENT/ECONOMY/CULTURE), each row an icon + name + dates + a confidence
  chip (the "stats-block" glance). Type-icon language per the UI/UX reference.
- **Period Highlights:** when the year changes, the list re-scopes to that period and the top-N important entities float to
  the top (the Era Score pattern).
- "What's on screen" toggle: filter the list to the current map viewport (bbox) vs. global/search mode.

### 3.2 Chronicles
- The curated-tour mode from the chronicle-dashboard spec — both modes drive the same selection state. (This spec
  generalizes that spec's two-tab aside into a three-mode aside: **Browse | Chronicles | Selection**.)

### 3.3 Selection (detail)
- Civilopedia-style: structured stats block (type, group, dates, confidence breakdown, location method) + the narrative
  `summary`/`significance` + source citations + related entities (relationships, directed + temporal). Source:
  `GET /v1/entities/{id}`.

### 3.4 Selection behavior (the core rule)
On select (`selectedEntityId`):
| Entity geometry | Map action | Aside |
|---|---|---|
| Point `geom` | pan + pulse the marker | switch to Selection detail |
| Territory (OHM-linked, has `ohm_external_id`) | highlight the OHM basemap feature (per D19 / plan A Task 9b) | Selection detail |
| **No geometry** | none (map unchanged) | highlight the list row + Selection detail |

Bidirectional: a map marker click sets `selectedEntityId` and scrolls/highlights the matching Browse row.

## 4. Data dependencies

- **`GET /v1/entities`** with working `year`/`bbox`/`types`/`group`/`search` filters and importance ranking — the
  index-driven version from **sub-project A** (MQ-4 EntityBuilder rewrite, MQ-13 group filter, the bbox endpoint). Until A
  lands, the list works but is slower and the `group` filter is a no-op.
- **`ohm_external_id`** on map features and (for the detail/territory highlight) on the entity — **sub-project A** (Task 9b)
  + **D19** borders-from-OHM.
- **`GET /v1/chronicles`** — the Chronicles mode (chronicle-dashboard spec); enhanced by **sub-project D**.
- A representative **point** for every mappable entity (so markers exist even when borders come from OHM) — guaranteed by
  the borders-from-OHM policy (D19: hydrate/keep the point).

## 5. State & flow

A single `selectedEntityId` + `selectedYear` (+ `selectedChronicleSlug`/`activeEntryId` for tours) shared by all modes.
Browse/Chronicle row click → set selection → map reacts per §3.4. Map marker click → set selection → Browse highlights.
Year scrubber → re-scope Browse (Period Highlights) + refresh the map (existing year query). Viewport change (if "what's on
screen" is on) → re-scope Browse to the new bbox.

## 6. Error / edge handling

- No-geometry entity → list-only selection (no map churn). This is a first-class case, not a degraded one.
- Empty period/search → empty state with a "broaden filters" hint.
- Large result sets → virtualized list + pagination; never render thousands of rows.
- Marker overlap at low zoom → cluster markers (progressive disclosure per the UI/UX reference); the list is the reliable
  selector when markers overlap.

## 7. Testing (model-level; component tests live in the build plan)

- Selecting a point entity pans+highlights the marker; a territory entity highlights the OHM feature; a no-geometry entity
  highlights only the row.
- Map marker click highlights the matching Browse row (bidirectional).
- Year change re-scopes Browse to the period and re-ranks by importance.
- "What's on screen" filters the list to the viewport bbox.

## 8. Sequencing / rollout

1. Adopt the three-mode aside (Browse | Chronicles | Selection) on the **admin dashboard** first (fastest feedback; the
   chronicle spec already starts this) — Browse uses `GET /v1/entities`.
2. Wire the §3.4 selection behavior + bidirectional map↔list highlight.
3. Period Highlights on year change; "what's on screen" viewport filter.
4. Port the validated model to the customer **`web/`** SPA as its primary shell (replacing the stub), with the
   game-inspired visual treatment (see the design brief, [web-frontend-design-brief](2026-06-12-web-frontend-design-brief.md)).

## 9. Risks

- **Ranking quality** — "important" leans on `impact_score`/`display_priority`; if those are sparse/uncurated the list is
  noisy. Mitigation: combine with `verification_status` and per-period normalization; this is tunable, not structural.
- **Two surfaces** (admin + web) — build the model once as shared hooks/components where practical to avoid drift.
- **Depends on sub-project A** for a fast, correctly-filtered list — sequence the polished version after A.
