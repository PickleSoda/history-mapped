# Historical Atlas — Web Frontend Design Brief (prompt for the Claude design agent)

> **Date:** 2026-06-12
> **Use:** Paste the section below (from "## DESIGN BRIEF" onward) to the Claude design agent (frontend-design). It is
> self-contained: product concept, data model, interaction model, layout, aesthetic direction, technical constraints, and
> deliverables. Trim the data-model detail if you want a tighter prompt.
> **Grounded in:** [web-interaction-model-design](2026-06-12-web-interaction-model-design.md), the borders-from-OHM policy
> (D19), and the UI/UX reference [game_inspired_ui_ux.md](../../reference/implementation-docs/game_inspired_ui_ux.md).

---

## DESIGN BRIEF

You are designing the **customer-facing web frontend for a Historical Atlas** — an interactive map of world history across
space and time, built on an AI-curated, human-verified knowledge graph of historical entities and their relationships.
Produce a distinctive, production-grade design and the React components to realize it. **Avoid generic SaaS/AI-dashboard
aesthetics** — this should feel like a living historical atlas, not an admin panel.

### 1. Product concept
A user explores world history by **place, time, and connection**. They scrub a timeline to a year, see what existed then
on a historical map, browse a ranked list of the important entities of that era, select one to read its story and see it on
the map, follow its relationships to other entities, and step through curated **Chronicles** (narrative tours). The map
shows period-accurate borders (from the OpenHistoricalMap basemap); the app overlays the entities (people, cities, events,
trade routes, ideas) as markers.

### 2. The data model (what you are visualizing)

**Entities** — the atoms. Every studyable historical thing is an entity in one of **five groups**, each with concrete
**types** (~30 total). Use these to drive an icon language, grouping, and color accents:
- **POLITY** — `political_entity` (states/empires), `dynasty`, `person` (rulers/figures), `military_unit`, `social_class`, `diplomatic_agreement`.
- **PLACE** — `city`, `infrastructure`/`monument`, `educational_institution`, `archaeological_culture`.
- **EVENT** — `event_battle`, `event_war`, `event_treaty`, `rebellion`, `disaster`, `migration`, `epidemic`.
- **ECONOMY** — `trade_route`, `natural_resource`, `currency`.
- **CULTURE** — `cultural_work` (art/literature), `religious_text`, `religion`/`religious_movement`, `language`,
  `legal_code`, `technology`, `intellectual_movement`.

Each entity carries a **stats block** + **narrative** (design the detail panel as "stats block + prose", Civilopedia-style):
- Identity: `name`, alternative names (aliases), `entity_type`, `entity_group`, `tags`, `wikidata_id`.
- Narrative: `summary` (1–2 sentences), `significance` (longer).
- Time: a temporal range — `start_year`/`end_year` as **signed integers (BCE = negative)**, possibly **open-ended**
  (unknown start or ongoing end); a human `date_raw`/era label.
- Space: a **point** (lng/lat) and/or a **territory** (polygon, shown via the OHM layer — see §4); many entities have **no
  geometry at all** (a language, a law code) and live only in the list/detail.
- Trust signals (design these as ambient, glanceable indicators — see the "stacked modifier" idea): `confidence`
  (`high`/`medium`/`low`/`unresolved`), `verification_status` (`pipeline_draft` → `needs_review` → `human_verified` →
  `expert_verified`), `impact_score` and `display_priority` (importance/ranking), source citations.

**Relationships** — the edges. Directed `source → target`, each with a **type** (76 total), an optional **time window**, a
`confidence`, and a `description`. Categories to express visually (e.g., as connection chips, cause→effect chains):
political (`rules`, `vassal_of`, `succeeded_by`, `part_of`, `capital_of`), person (`born_in`, `married_to`, `mentor_of`,
`member_of_dynasty`), military (`participated_in`, `commanded`, `victorious_at`), economic (`trades_with`, `produces`,
`controlled_by`), religious/cultural (`adheres_to`, `influenced_by`, `built_by`), causal (`caused`, `resulted_from`,
`weakened`, `enabled`), knowledge/tech (`invented`, `adopted`, `spread_to`), diplomatic (`signed_by`, `mediated_by`).
Direction is meaning: *Augustus* **rules** *Roman Empire*.

**Chronicles** — curated narrative tours. A chronicle has a title and an **ordered list of entries**; each entry has
`narrative_text`, a year, a **primary relationship** (two entities), and **secondary entities** — i.e., a step in a story
pinned to a moment and place. Stepping through a chronicle should move the timeline and the map.

### 3. The interaction model (sidebar-primary — this is the spine of the UX)
The **list/sidebar is the primary way to find and select entities** (clicking tiny points on a map is unreliable, and many
entities have no point). The map is a spatial *view*. Selection is **shared** across list, map, and chronicles.

- **Explorer aside** with three modes:
  - **Browse** — a ranked, filterable list of the important entities for the current year/era (filter by group/type,
    search, "what's on screen" viewport toggle; rank by importance). When the year changes, surface the era's
    **Period Highlights** at the top.
  - **Chronicles** — the curated tours; selecting an entry advances the timeline + map + selection.
  - **Selection** — the Civilopedia-style detail (stats block + narrative + relationships + sources).
- **Selection behavior:** select an entity → **point** entity: pan + pulse its marker; **territory** entity: highlight the
  OHM basemap feature; **no-geometry** entity: highlight the list row + open detail, leave the map unchanged. **Bidirectional**:
  clicking a map marker highlights its list row.
- **Timeline scrubber** (BCE-aware) is the temporal control; an **ambient stats ribbon** shows era metrics
  (entity count, coverage, average confidence) at the top edge — glanceable, never modal. Optional **map lenses** recolor
  the entity overlay by a dimension (political / trade / religion / military). **Progressive disclosure**: clustered markers
  at low zoom → region overview → entity detail. **Hover tooltips** everywhere on dates, places, confidence.

### 4. The map (important constraint)
Borders are **not** stored or drawn by the app — they come from the **OpenHistoricalMap (OHM) vector basemap**, date-filtered
to the selected year. The app overlays **entity markers** (points) and, on selection of a territory entity, **highlights the
matching OHM feature**. So design the map as: *period-accurate OHM basemap + a clean entity-marker overlay + a highlight
state*. Markers use the type icon, sized by importance; territory entities are represented by a marker plus the OHM
highlight on select.

### 5. Layout
- **Map canvas** dominant (center). **Explorer aside** (Browse | Chronicles | Selection) docked right (or left — your call).
- **Top:** slim ambient stats ribbon + era label + lens selector + search.
- **Bottom:** timeline scrubber with era bands; optionally chronicle/era "highlight" markers on the track.
- Fully **responsive**: on mobile, the aside becomes a bottom sheet / drawer; the map stays primary.

### 6. Aesthetic direction
Game-inspired (Sid Meier's **Civilization VI**, Creative Assembly's **Total War: Rome II**) applied to a scholarly atlas:
information density at the edges, a confident custom **icon language** for the entity types, "explained metrics" for
confidence, a timeline as the heartbeat. Visually: **cartographic and tactile** — think aged-map/ink-and-parchment accents,
era-aware theming, strong typographic hierarchy (a characterful display face for titles, a highly legible text face), subtle
motion (marker pulses, smooth map fly-to, timeline easing). Restrained, premium, and **distinctive** — not flat generic SaaS.
Dark and light themes; accessible contrast; a coherent color system keyed off the five entity groups.

### 7. Technical constraints (design to these)
- **Stack:** React 19 + TypeScript, MapLibre GL JS for the map with the **OpenHistoricalMap** basemap style (date-filtered),
  TanStack Query for data, Vite. Components should be real and composable.
- **Data comes from a REST API:** `GET /v1/entities` (filterable, paginated list → Browse), `GET /v1/entities/{id}`
  (detail), `GET /v1/entities/map` (viewport-bounded GeoJSON markers, with each feature carrying an `ohm_external_id` for
  territory highlight), `GET /v1/chronicles` + `/v1/chronicles/{slug}` (tours).
- **Performance:** the map fetches only the **viewport** at zoom-appropriate detail; the list is **virtualized**; selection
  is shared state (no duplicate fetches).

### 8. Deliverables
1. A **design system**: color (keyed to the five groups + light/dark), typography scale, spacing, the **entity-type SVG icon
   set**, confidence/verification indicators, motion guidelines.
2. **High-fidelity layouts** for the key screens/states: default (map + Browse), entity selected (point / territory /
   no-geometry variants), a chronicle tour mid-step, Period Highlights on year change, search, empty + loading, and mobile.
3. **Production-grade React components** for the shell: map canvas, explorer aside with the three modes, entity row + detail
   (stats block + prose + relationships), timeline scrubber, stats ribbon, marker + highlight, tooltips.
4. A short rationale tying the visual choices to the product (why it reads as a living atlas, not a dashboard).

Make deliberate, opinionated choices. Prioritize a memorable, coherent, genuinely atlas-like experience over safe defaults.
