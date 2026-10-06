# Entity & chronicle full pages with relation graphs — design

Status: implemented (2026-10-04) — backend endpoints, entity page and chronicle page all landed.
Frontend reference: `docs/architecture/frontend-app.md` (Routing → full page, EntityPage, ChroniclePage,
RelationGraph). Known gaps: the mobile sheet swaps (doesn't stack) an entity page opened over the
chronicle page; the graph canvas has no keyboard node navigation (the lists are the accessible view).

## Problem

The atlas shows an entity in a 380px side panel (desktop) or the vaul sheet (mobile). It renders
`summary ?? significance`, so one of the two texts is always hidden. It also drops most `EntityResource`
fields (alternative names, tags, Wikidata id, raw date, confidence, verification, sources, attributes),
and it lists relations only as a flat timeline. Chronicles (one per campaign transcript) are shown one
step at a time. Nothing shows how a chronicle's entities connect to each other or to the rest of the atlas.

## Goals

1. **Entity page.** Expand the selected entity into a full, scrollable page that rises from the bottom of
   the screen. It shows every field the API has, both texts, and the sources.
2. **Entity relation graph.** The page shows a filterable graph of related entities. Any node can be
   expanded to load *its* relations, so the user can follow multi-hop chains.
3. **Chronicle page.** Use the same bottom-up page for a chronicle. It has a whole-chronicle graph of
   all its entities, the relations between them, and (toggleable) what those entities relate to outside
   the chronicle. It then lists the steps, each with its own graph.

## Non-goals

- Editing (the admin handles that) and new DB columns.
- Server-side graph analytics (centrality, paths).

## Routing / state

- A new nuqs boolean param **`full`** (`?sel=<uuid>&full=1`, `?chron=<slug>&full=1`) is pushed to
  history, so Back collapses the page.
- `sel` wins over `chron`, as it does today. An entity page opened from a chronicle page sits on top of
  it, and closing the entity page returns to the chronicle page.
- **Desktop:** the page slides up from the bottom edge over the map and timeline; the TopBar stays
  visible. A transform transition is used (no new animation dependency), and it respects
  `prefers-reduced-motion`. `DetailPanel` and `ChroniclePlayer` get an *Expand* button, and the page has
  *Collapse* (`full` removed) and *Close* (selection cleared) buttons.
- **Mobile:** `MobileSheet` at the `full` snap point renders the same page component, and `full=1`
  snaps the sheet to full. Leaving full snap removes `full`.

## API (Laravel, `/api/v1`, public, read-only)

Both endpoints return the same node and edge shapes.

```jsonc
// node
{ "id": "<entity uuid>", "name": "…", "entity_type": "…", "entity_group": "…",
  "start_year": -490, "end_year": null, "impact_score": 42, "depth": 0 }  // impact_score: integer 1-100
// edge (source/target are entity uuids; direction = source → target)
{ "id": "<relationship uuid>", "source": "…", "target": "…", "relationship_type": "…",
  "start_year": -490, "end_year": -479, "description": "…", "confidence": "high" }  // confidence: high|medium|low|unresolved|null
```

### `GET /entities/{uuid}/graph`

| param | default | notes |
|---|---|---|
| `depth` | 1 | 1 or 2. Depth 2 follows edges out of each depth-1 node. |
| `relationship_types` | all | comma list |
| `groups` | all | comma list of entity groups. Filters non-root nodes; edges to removed nodes are removed too. |
| `from`, `to` | — | year overlap on the relationship `start_year`/`end_year`. Null years pass. |
| `limit` | 300 | max edges, hard cap 1000. Ordered by confidence desc, then the other end's impact desc. |

Response: `{ "data": { "root": "<uuid>", "nodes": [...], "edges": [...], "truncated": bool } }`.
The client implements *expand node* by calling this endpoint with `depth=1` for that node and merging
the result.

### `GET /chronicles/{slug}/graph`

| param | default | notes |
|---|---|---|
| `external` | 1 | include relations from chronicle entities to entities outside the chronicle |
| `external_limit` | 12 | max external edges per chronicle entity (by confidence, then the other end's impact) |
| `relationship_types` | all | comma list |

The chronicle entity set is the union of the `chronicle_entry_entities` pivot and both ends of every
entry's primary relationship.

```jsonc
{ "data": {
  "chronicle_id": "…", "slug": "…",
  "nodes": [ { /* node */, "in_chronicle": true, "steps": [1, 4] } ],
  "edges": [ { /* edge */, "scope": "primary" | "internal" | "external", "steps": [4] } ],
  "steps": [ { "entry_id": "…", "sequence_order": 4, "start_year": -480, "end_year": null,
               "primary_relationship_id": "…", "entity_ids": ["…"], "relationship_ids": ["…"] } ]
} }
```

- `internal`: both ends are in the chronicle set.
- `external`: exactly one end is in the set.
- Step membership:
  - `entity_ids` = the step's pivot entities plus the ends of its primary relationship.
  - `relationship_ids` = the primary relationship plus every internal edge whose two ends are both among
    that step's entities.

Implementation notes (backend, binding): invalid params (depth not 1|2, unknown relationship type or
group, `limit` > 1000, negative `external_limit`) return 422 when `Accept: application/json` is sent;
unknown entity/slug or a non-uuid id returns 404. Chronicle primary relationships are always returned
(scope `primary`) even if `relationship_types` would exclude them; the filter applies to internal and
external edges. Step/edge `steps` values are `sequence_order` numbers. Full contract:
`docs/schemas/relation-graph-api.md`.

### Fix in passing

`RelationshipResource` embeds `EntitySummaryResource` for both ends without loading years or location,
so `temporal_start`, `temporal_end`, `location_name` and `geom` come back null. Load what the summary
needs.

## Frontend (`web/`)

- **Graph library:** `cytoscape` + `cytoscape-fcose`, lazy-loaded with a dynamic import so the atlas
  bundle doesn't grow.
  - Why: it is canvas-rendered and stays fluid at the several hundred nodes a chronicle graph with
    externals reaches.
  - fcose gives good incremental layouts; element show/hide makes filtering cheap.
  - It is already proven in the lockfile through mermaid.
  - React Flow was rejected: DOM nodes degrade at this size and it needs a separate layout engine.
- **`RelationGraph`** (shared):
  - Node colour comes from the existing entity-group tokens, node size from `impact_score`, and edge
    label is the relationship type (shown on hover/selection). Direction is drawn with arrows.
  - Theme-aware in light and dark.
  - Clicking a node opens an info card with *Open* (select that entity) and *Expand* (merge its depth-1
    neighbourhood; the layout runs only on the new nodes, around the expanded one, with existing nodes
    locked). Expanded nodes are marked, and *Collapse* removes the nodes that expansion added and that
    no other node still needs.
  - Filter bar: relationship-type chips, entity-group chips, a year-range control, and a
    *show external* toggle on chronicles. Filters hide elements and do not refetch.
  - Controls: fit, reset, and a legend.
  - Graph merge, filter and subgraph logic live in pure functions with Vitest tests.
- **`EntityPage`:**
  - Header: type, name, alternative names, dates (raw date on hover), location, impact, confidence,
    verification status, and a Wikidata link.
  - Summary *and* significance, an attributes table, and tags.
  - Chronicle chips and the relation graph.
  - The relationship timeline (kept as the accessible list view) and timeline entries
    (`/entities/{uuid}/timeline`).
  - Sources (`source_citations`) and media.
  - Widen the zod schemas to keep these fields.
- **`ChroniclePage`:**
  - Header: title, source type and reference, span, entry count.
  - The whole-chronicle graph. Chronicle entities are solid and externals dimmed. A step scrubber
    highlights a step's subgraph in place.
  - The step list. Each step shows its narrative and its **own** graph (the step's entities and edges,
    with the primary edge emphasised and an optional *+ external* toggle). Step graphs mount lazily
    (IntersectionObserver) and unmount when far off-screen.
  - Clicking a node opens that entity's page on top.

## Testing

- PHPUnit feature tests for both endpoints. They cover filters, depth, limit/truncation, external
  capping, step membership and the 404s. They run against the `history-mapped_test` DB.
- Vitest covers the graph merge/collapse/filter/step-subgraph functions.
- `pnpm lint`, `types:check` and `build` must pass in `web/`.
