# Egypt Wikidata Fallback Design

> **Date:** 2026-06-02
> **Status:** Approved
> **Related plans:** `2026-05-30-egypt-historical-collection.md`, `2026-06-02-egypt-wikidata-fallback.md`

**Context**

The current Egypt historical collection workflow was designed around OHM-first discovery. In practice, the local OHM XML export and the existing OHM/Overpass-derived indexes are not surfacing the Egypt entities the operator actually needs. The recent real-data run demonstrates the failure mode clearly: the collection mostly matched `British Empire` records whose metadata mentions Egypt events, rather than Egypt entities themselves.

That means the current bottleneck is not importer compatibility. The repository already has a mature Wikidata pipeline that can produce importer-ready entity JSONL with typed entities, groups, summaries, temporal fields, coordinates, geoshapes, citations, and relationship hints. The bottleneck is entity discovery.

For now, the operator wants a practical fallback that gets Egypt entities into the database without waiting for OHM coverage or better XML/Overpass extraction. This design therefore pivots the Egypt collection from OHM-first discovery to direct Wikidata import.

**Goal**

Add a temporary Egypt-specific Wikidata fallback workflow that:

- imports Egypt entities directly from Wikidata as generic importer-ready entities
- bypasses OHM XML discovery, OHM border staging, and OHM geometry-period generation for this fallback path
- preserves the existing generic Laravel import contract
- uses Wikidata coordinates and geoshapes when available
- keeps the result focused on Egypt rather than broad topic-walk noise

**Approved Scope Decisions**

- Data source: Wikidata-first for this fallback.
- Output shape: generic entities only.
- Geometry policy: use Wikidata point coordinates and Wikidata geoshapes only; do not require OHM geometry.
- Border policy: no `borders_final` output, no `geometry_periods`, and no OHM border importer for this fallback.
- Temporary status: this is an operator-focused fallback to unblock Egypt imports now, not a replacement for the long-term OHM collection design.

**Non-Goals**

- No attempt to reconstruct OHM border chronologies or geometry periods from Wikidata.
- No attempt to force the fallback through `pipeline:import-borders`.
- No broad unrestricted Egypt scrape across all possible Wikidata neighbors.
- No requirement to solve every historical Egypt entity in the first pass.
- No replacement of the existing generic Wikidata pipeline for non-Egypt topics.

**Approaches Considered**

1. Reuse the existing `topic` BFS directly from an Egypt seed

This is the smallest code change, but it is too noisy for the current problem. The topic walk follows many graph edges that are useful for historical discovery in general but too permissive for a country/civilization collection, and it already has special rules around modern states that cut against Egypt as a seed.

2. Use existing type scrapers and post-filter to Egypt

This avoids OHM entirely, but it is likely to over-collect because type scrapes are broad and Egypt filtering would happen after the expensive fetch. It also risks reproducing the same weak-association problem in a different form.

3. Add a dedicated Egypt Wikidata fallback builder from curated seed QIDs

This is the recommended approach.

It changes the problem from “discover Egypt by text mentions in OHM” to “fetch a known Egypt entity set from Wikidata, optionally expand in bounded ways, and emit importer-ready entities.” That is the most reliable path to useful results with the least dependency on incomplete OHM data.

**Recommended Approach**

Implement a new Egypt Wikidata fallback workflow driven by a curated seed set and bounded Wikidata expansion.

The workflow should:

- start from a curated list of Egypt-relevant Wikidata QIDs
- fetch those entities directly from Wikidata using the existing scraper/mapper infrastructure where possible
- optionally perform tightly bounded expansion only through Egypt-relevant properties
- map results through the existing `EntityMapper`
- deduplicate through the existing Wikidata deduplicator
- emit importer-ready generic entity JSONL under a collection-oriented output directory

This keeps the Egypt fallback narrow, deterministic, and compatible with the repository’s existing import path.

**Why A Curated Seed Set Is Necessary**

The operator’s failure case is not “Wikidata has no Egypt entities.” It is “our current discovery path reaches the wrong things first.” A curated seed set fixes that.

The first pass should not rely on one generic Egypt seed alone. It should define a curated base set that spans the historical collection the operator actually wants, including representative territorial forms, periods, and high-value places.

Examples of expected seed categories:

- Egypt as a modern state
- Ancient Egypt
- major historical state forms such as Old Kingdom, Middle Kingdom, New Kingdom, Ptolemaic Kingdom, Roman Egypt, Ayyubid Egypt, Mamluk Sultanate, Ottoman Egypt, Khedivate, Sultanate, Kingdom, Republic
- major Egypt places where the collection clearly benefits from direct inclusion, such as Memphis, Thebes, Alexandria, Cairo, Giza, Luxor
- optionally high-value historical periods or dynasties that are central to the collection’s purpose

The exact seed file is an implementation detail, but it should be explicit, versioned, and easy to review.

**Architecture**

The fallback should reuse the existing Wikidata pipeline instead of creating a new parallel importer shape.

Recommended additions:

- `pipeline/wikidata/collections/egypt_seed_set.py`
  - loads curated Egypt seed QIDs and optional metadata such as preferred labels or include categories
- `pipeline/wikidata/collections/egypt_fallback.py`
  - orchestrates fetch, bounded expansion, mapping, dedup, artifact writing, and manifest generation
- `pipeline/wikidata/collections/artifacts.py`
  - output directory helpers for collection runs if reuse from `ohm_collections/artifacts.py` is not appropriate
- CLI wiring in either:
  - `py -m pipeline collections egypt-wikidata-build`, or
  - `py -m pipeline wikidata egypt-fallback-build`

The recommended operator surface is under `collections`, because this is functionally a replacement collection builder for Egypt rather than a generic scrape mode.

**Data Flow**

1. Load seed set

Read a curated Egypt seed definition from a repository file. The seed definition may include:

- `qid`
- `category`
- optional notes or include rationale
- optional flags for whether expansion is allowed from that seed

2. Fetch exact entities from Wikidata

Resolve each seed QID directly from Wikidata rather than through text search. This should avoid ambiguity and eliminate the weak lexical-matching problem that affected the OHM-first approach.

3. Apply bounded expansion

Expansion should be optional and conservative. The purpose is to pick up clearly Egypt-linked adjacent entities, not to recreate a broad topic walk.

Allowed examples:

- predecessor / successor
- part of / has part
- capital / capital of
- directly located in Egypt or directly part of an included Egypt polity
- selected dynastic or period edges when they remain inside the Egypt domain

Expansion should be rejected when it only creates a weak contextual tie. For example, neighboring empires, colonial powers, or broad Mediterranean entities should not be included solely because they interacted with Egypt.

4. Classify and map entities

Map all retained raw items through the existing `EntityMapper` so the output stays importer-compatible and consistent with the rest of the pipeline.

5. Deduplicate

Run the existing Wikidata deduplicator so the fallback respects exact QID dedup and the existing name/temporal rules.

6. Write collection artifacts

Write importer-ready outputs and run metadata.

**Output Contract**

This fallback should emit only the artifacts that are meaningful for a generic Wikidata import.

Recommended output layout under `output/wikidata_collections/<run_id>/`:

- `entities_final/egypt_collection.jsonl`
  - importer-ready generic entities
- `reports/included.jsonl`
  - included entities with seed/expansion provenance and inclusion rationale
- `reports/excluded.jsonl`
  - rejected candidate entities with rejection rationale
- `manifest.json`
  - counts, seed metadata, expansion metadata, and geometry statistics

If minimizing operator churn is more important than path purity, the implementation may keep the existing collection run root naming under `output/ohm_collections/<run_id>/`. The important part is the artifact contract, not the parent folder name.

No `borders_final/` output is required.
No `relations_final/` output is required for the first pass.

**Entity Schema And Import Contract**

The fallback must emit the same generic entity JSONL schema the current Wikidata pipeline already produces. That means each final entity may include:

- `name`
- `entity_type`
- `entity_group`
- `wikidata_id`
- `summary`
- `alternative_names`
- temporal fields when available
- `geojson` point coordinates when available
- `territory_geojson` when Wikidata geoshapes are available
- `attributes`
- `tags`
- `source_citations`
- `_relationship_hints` when already supported by the mapper

That allows the fallback to use the normal Laravel generic import command without a new importer fork.

**Geometry Policy**

Because this fallback bypasses OHM, its geometry policy must be explicit.

Priority order:

1. Wikidata `territory_geojson` when available for territorial entities
2. Wikidata point coordinates from `P625`
3. `location_name` only with no geometry
4. keep the entity even when no geometry exists

This is intentionally weaker than the long-term OHM collection design, but it is the correct temporary tradeoff for importing the right entities now.

The fallback should not perform OHM geo-resolution by default. The operator explicitly wants a direct Wikidata import path because OHM discovery is the current source of failure.

**Inclusion Rules**

The fallback should use deterministic Egypt-domain rules rather than broad lexical scoring.

An entity qualifies when at least one of the following is true:

- it is explicitly listed in the curated Egypt seed set
- it is reached through an allowed bounded expansion from an included seed and remains inside the Egypt domain
- its direct Wikidata properties place it in Egypt or a previously included Egypt polity

An entity should be rejected when:

- it is only adjacent to Egypt historically but is not itself an Egypt entity
- it is a broad imperial or regional actor whose metadata merely mentions Egypt events
- it is a modern-state or geopolitical umbrella entity outside the intended Egypt collection scope

This is the core change from the OHM-first attempt: the fallback should encode Egypt identity, not Egypt mention.

**CLI And Operator Workflow**

Recommended operator commands:

- `py -m pipeline collections egypt-wikidata-build --run-id egypt-wikidata-fallback --force`
  - build the Egypt fallback collection from Wikidata only
- optional flags:
  - `--resume`
  - `--skip-wikipedia`
  - `--seed-file <path>` for operator overrides
  - `--no-expansion` to run exact-seed-only mode

Expected import flow:

```powershell
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:import /var/www/html/storage/app/imports/egypt-wikidata-fallback/entities_final/egypt_collection.jsonl --sync --force
```

If `_relationship_hints` are preserved on the entity records, the normal generic import flow may resolve those the same way it does for the rest of the Wikidata pipeline. That is optional for the first pass and should not block entity import.

**Error Handling And Safety**

- Missing or invalid seed QIDs should be reported clearly in the manifest and included/excluded reports.
- Failed Wikidata requests should be retried according to the existing rate-limit and request safety behavior.
- Partial fetch failure should not corrupt already written final files; use temp files and atomic replace for artifact writes.
- Expansion that exceeds the allowed Egypt-domain rules should be excluded with a recorded rationale, not silently dropped.
- Missing geometry is not fatal.

**Testing Strategy**

The fallback should use focused tests before implementation broadens.

1. Seed-set tests

- load curated Egypt seed definitions
- reject malformed entries
- preserve deterministic ordering

2. Fetch and mapping tests

- exact-QID fetch returns importer-compatible entity records
- existing `EntityMapper` output is preserved
- geoshape and point geometry are retained correctly

3. Expansion-rule tests

- predecessor/successor or part-of expansion works for Egypt-domain entities
- non-Egypt adjacency such as British Empire-style matches is rejected
- exact-seed-only mode produces only seed entities

4. Artifact tests

- manifest counts match written entity/report files
- output layout matches the documented collection contract
- no border artifacts are emitted

5. Import-compatibility smoke test

- run the generated `egypt_collection.jsonl` through the normal generic importer path
- verify that the importer accepts records without OHM border metadata

**Migration And Relationship To The Existing Egypt OHM Design**

This design does not replace the previously approved OHM Egypt collection design. It is a temporary fallback that solves a different problem.

- The OHM Egypt collection design remains the long-term path for Egypt territorial discovery, staged border reuse, and richer OHM-native provenance.
- This Wikidata fallback exists to unblock entity import while OHM discovery remains incomplete or untrustworthy for Egypt.

The two workflows should coexist cleanly:

- OHM-first collection when OHM coverage is strong enough
- Wikidata fallback collection when entity identity matters more than OHM-native geometry

**Decision Summary**

The repository should temporarily stop using OHM/XML discovery as the primary source for Egypt collection assembly.

Instead, it should add a dedicated Egypt Wikidata fallback builder that:

- uses curated Egypt seed QIDs
- performs bounded Egypt-domain expansion
- maps directly through the existing Wikidata entity pipeline
- emits generic importer-ready entities only
- bypasses OHM border outputs for now

That is the smallest reliable path to importing actual Egypt entities instead of incidental neighbors.