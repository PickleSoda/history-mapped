# Egypt Historical Collection Design

**Context**

The current OHM borders workflow is optimized for seed-centered administrative relations extracted from a global `overpass.json`. That works well for relation-backed polities such as the Roman Empire, but it is the wrong abstraction for Egypt as a historical collection. Egypt is spread across many disconnected periods, labels, aliases, nodes, ways, and relations, and the local XML export at `output/map.xml` is likely to contain historically useful point features that never appear in the current admin-level-2 JSON dump.

The operator already decided that point-only OHM records count as valid final entities and georefs. They also want a broad Egypt collection across all historical periods, including ancient, classical, medieval, Ottoman, Kingdom, and Republic phases. The inclusion policy is hybrid: territorial, political, regional, city, period, war, battle, and event entities are included by default, while culture, religion, script, and currency entities are included only when they are strongly Egypt-linked.

The `output/map.xml` file is large enough that the solution must treat it as a streaming input source rather than opening it wholesale.

**Goal**

Add a new Egypt historical collection workflow that:

- streams `output/map.xml` into a reusable local index without loading the full file into memory
- discovers Egypt-related OHM candidates using broad lexical and metadata matching
- keeps point-only OHM features as valid final entities
- prefers OHM-derived points when present, but falls back to the normal pipeline's Wikidata/Wikipedia coordinates when OHM has no better location
- preserves the current OHM border importer path for relation-backed polities with staged history
- emits importer-compatible artifacts for both OHM territorial entities and non-border Egypt entities such as wars, battles, periods, and dynasties

**Approved Scope Decisions**

- Geometry policy: keep entities even without OHM coverage and use the normal pipeline's Wikidata/Wikipedia coordinates by default unless OHM has a better point.
- Match policy: broad Egypt matching across names, aliases, tags, OHM labels, and Wikidata labels.
- Period scope: all historical Egypt, including Ottoman, Khedivate, Kingdom, and Republic forms when they match.
- Entity-type scope: hybrid. Include territorial/political/event entities by default; include culture/religion/script/currency only when strongly Egypt-linked.
- Architecture style: split approach. Build reusable XML indexing primitives, but keep the first matching and inclusion rules Egypt-specific.

**Non-Goals**

- No attempt to replace the existing OHM borders pipeline for general seed-centered extraction.
- No requirement to reconstruct complete polygon coverage for every Egypt entity.
- No redesign of Laravel import jobs beyond what is necessary to consume the new artifact layout.
- No attempt to generalize the first collection ruleset for all civilizations before Egypt is working.
- No live Overpass dependency for the first pass; the local `output/map.xml` file is the primary discovery source.

**Approach**

Use two layers.

1. Reusable XML indexing primitives

These primitives stream `output/map.xml`, persist a disk-backed SQLite index of OHM nodes/ways/relations, and expose lookup helpers by normalized name, alias, tag value, and `wikidata` id. They also expose a best-available OHM point resolver for matched objects.

2. Egypt-specific collection rules and assembly

These rules apply the approved Egypt scope, score candidates, and assemble importer-facing outputs. Relation-backed polities continue through the OHM border artifact contract so `entity_geo_refs` and `geometry_periods` remain intact. Point-only or non-border entities are emitted as regular pipeline entities with `geojson` populated from the best available point source.

This split keeps the expensive XML work reusable while allowing the inclusion logic to stay tightly tuned to Egypt first.

**Architecture**

The workflow should introduce a new `pipeline/ohm_collections/` package rather than continuing to overload `pipeline/ohm_borders/`. The two packages solve related but distinct problems.

- `pipeline/ohm_borders/` remains the authoritative relation/stage pipeline for OHM border chronologies and relation-derived artifacts.
- `pipeline/ohm_collections/` becomes the discovery and assembly layer for broad historical collections that mix OHM point features, relation-backed territorial entities, and normal pipeline entities.

Suggested components:

- `xml_index_store.py`
  - schema creation and compatibility metadata for the streamed XML index
- `xml_index_builder.py`
  - streaming `iterparse` ingest for `output/map.xml`
- `xml_lookup.py`
  - normalized search helpers over indexed OHM objects
- `point_resolver.py`
  - best-available OHM point derivation for nodes, ways, and relations
- `egypt_rules.py`
  - Egypt-specific lexical families, type gates, scoring, and inclusion decisions
- `collection_builder.py`
  - assemble final Egypt artifacts, route candidates into border-backed vs. regular entity outputs, and emit reports
- `artifacts.py`
  - artifact directories and manifest helpers for collection runs

**Data Sources And Source Of Truth**

There are three relevant sources.

1. `output/map.xml`

Primary source for broad OHM discovery. It may include nodes, ways, relations, aliases, and point features that are absent from the current `overpass.json` admin-relation workflow.

2. Existing OHM borders index and stage pipeline

When an Egypt candidate resolves to a relation-backed OHM polity that already fits the border pipeline, the collection workflow should reuse that path instead of reimplementing relation-stage logic from scratch. The existing OHM border index remains the authoritative source for stage membership, chronology edges, and border import artifacts.

3. Normal pipeline entity mapping and geo fallback

For non-border entities or OHM-discovered entities without usable OHM geometry, the existing pipeline mapper and geo resolver remain the fallback path for coordinates and general entity enrichment.

The first pass is OHM-first for discovery. Non-OHM entities may still enter the final collection, but only after they are pulled in by normal pipeline enrichment from an included OHM-discovered candidate or an included Egypt-linked relation target; the workflow should not start with an unrestricted generic Egypt scrape.

**Egypt Candidate Discovery Rules**

The initial collection rules are Egypt-specific and intentionally explicit.

Lexical family:

- `Egypt`
- `Egyptian`
- `Kemet`
- `Aegyptus`
- `Upper Egypt`
- `Lower Egypt`

The rules should match against:

- raw OHM `name`
- normalized OHM names
- common alias tag fields such as `alt_name`, `official_name`, `short_name`, `name:en`, and comparable multilingual name tags when present
- OHM freeform tag values that mention Egypt directly
- `wikidata`-linked names and descriptions after enrichment

The first pass should prefer deterministic normalized string matching and explicit vocabulary expansion over fuzzy search. This is a curated collection workflow, not a general-purpose discovery engine.

**Entity-Type Inclusion Policy**

Default include:

- political entities and state forms
- dynasties
- geographic regions and administrative territorial entities
- cities and historically relevant places
- historical periods
- wars, battles, and event entities

Conditional include:

- culture
- religion
- writing system / script
- currency
- other non-territorial reference-like historical entities

Strong Egypt linkage for conditional types means at least one of:

- a direct lexical match against the Egypt vocabulary in name, alias, or OHM tags
- explicit `wikidata` metadata placing the entity in Egypt or an already included Egypt territorial entity
- an enriched summary/description that directly identifies Egypt as the entity's domain, location, or usage context

Incidental or weak mentions should not be enough to include a conditional entity.

**Point Resolution Policy**

Point-only OHM records are valid final entities.

The point selection order should be:

1. OHM-native point from the XML index
   - node latitude/longitude
   - direct point geometry if present
2. OHM-derived representative point
   - representative point from a way or relation geometry when enough member geometry exists locally
3. Existing mapped `geojson` from the normal pipeline entity record
4. Existing geo resolver fallback (`_geo_resolution` / Wikidata / Wikipedia coordinates)
5. No geometry, but keep the entity

For events, wars, and battles, this means the workflow should assign the point at which they happened using the best available point from OHM first and generic pipeline coordinates second. A polygon is never required.

When both OHM and generic pipeline coordinates exist, OHM wins and the manifest should record that choice explicitly.

**Artifact Contract**

The collection workflow should emit separate importer-facing outputs rather than force one importer to do both jobs.

Suggested outputs under `output/ohm_collections/<run_id>/`:

- `reports/included.jsonl`
  - included candidates with inclusion reason and geometry source
- `reports/excluded.jsonl`
  - excluded candidates with exclusion reason
- `borders_final/ohm_borders.jsonl`
  - relation-backed OHM territorial entities that should continue through `pipeline:import-borders`
- `entities_final/egypt_collection.jsonl`
  - non-border or point-only entities for `pipeline:import`
- `relations_final/`
  - relation-entity and relation-hint outputs compatible with existing relationship import flows
- `manifest.json`
  - run metadata, counters, and compatibility state

This preserves the current OHM border importer path for staged territorial entities while allowing the generic importer to handle wars, periods, dynasties, and conditionally included Egypt-linked cultural entities.

The generic entity output must reuse the existing `pipeline:import` JSONL schema, and the relations output must reuse the existing relation-entity and relation-hint contract so no Laravel-side importer fork is required for the first pass.

**CLI And Operator Workflow**

Introduce a new CLI surface under the top-level pipeline entry point.

Recommended commands:

- `py -m pipeline collections build-xml-index`
  - stream `output/map.xml` into a reusable SQLite index
- `py -m pipeline collections egypt-build`
  - assemble the Egypt collection outputs using the XML index, optional OHM border index, and normal pipeline enrichment
- `py -m pipeline collections egypt-relations-run`
  - normalize, enrich, and emit relation entities/hints for the assembled collection

These commands should be resumable and idempotent in the same operator-friendly sense as the borders workflow: reruns may skip already completed compatible artifacts when `--resume` is set, and explicit `--force` behavior should overwrite incompatible or stale outputs predictably.

The first pass should not require a live Overpass call. A future gap-fill mode may optionally query Overpass for missing objects, but that is explicitly out of scope for this design.

**Error Handling And Safety**

- XML indexing must be streamed, disk-backed, and safe on large inputs.
- Index build should use temp-file build plus atomic replace, mirroring the border-index safety model.
- Malformed XML elements should be skipped with counters and diagnostics, not treated as fatal for the whole run.
- Missing OHM geometry is not an error; it only changes the geometry source to fallback or none.
- Candidate ambiguity should be recorded in reports so the Egypt rules can be tuned later.
- The workflow should never silently drop an otherwise valid entity solely because OHM lacks a polygon.

**Testing Strategy**

The implementation should use TDD in layers.

1. XML index tests

- stream large XML fixtures without loading the full document
- capture nodes, ways, relations, names, aliases, tags, and `wikidata`
- persist index metadata and support deterministic lookup

2. Lookup and point-resolution tests

- exact normalized lookup
- alias lookup
- node point resolution
- representative point resolution for way/relation candidates
- missing-geometry fallback behavior

3. Egypt rules tests

- broad lexical inclusion for Egypt variants
- hybrid type gating
- modern-state inclusion because the approved scope is all historical Egypt
- rejection of weak incidental matches for conditional entity types

4. Builder tests

- route relation-backed polities into border artifacts
- route point-only or non-border entities into generic entity artifacts
- preserve entities with fallback coordinates when OHM coverage is missing
- record geometry provenance correctly

5. End-to-end smoke tests

- run an Egypt collection fixture through XML indexing, collection build, and relation generation
- verify compatibility with `pipeline:import-borders` for border artifacts
- verify compatibility with `pipeline:import` for generic entities

**Why XML Is Useful Here**

The XML file is useful because it can expose point features, aliases, and non-admin OHM objects that the current `overpass.json` admin-relation workflow misses. The XML file is not useful as a blind file to open or hand-inspect; it must be treated as a streamed source that feeds a reusable local index.

That gives the operator a practical way to cover New Kingdom, Middle Kingdom, Late Period, Intermediate Periods, Upper/Lower Egypt, Egypt-linked wars, and modern state forms in one broad collection without pretending they all belong to one connected border subgraph.