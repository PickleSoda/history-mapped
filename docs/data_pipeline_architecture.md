# Data Pipeline Architecture — v1

> **Companion to:** Entity Specification v2.1, Architecture Overview, Reference Tables
> **Status:** v1 — core scrape-import-embed pipeline
> **Source directory:** `pipeline/`

---

## Table of Contents

1. [Overview](#1-overview)
2. [System Design](#2-system-design)
3. [Python Pipeline](#3-python-pipeline)
4. [JSONL Schema](#4-jsonl-schema)
5. [Laravel Import Layer](#5-laravel-import-layer)
6. [Deduplication Strategy](#6-deduplication-strategy)
7. [Relationship Resolution](#7-relationship-resolution)
8. [Embedding Generation](#8-embedding-generation)
9. [Verification Workflow](#9-verification-workflow)
10. [Operational Runbook](#10-operational-runbook)
11. [v2+ Roadmap](#11-v2-roadmap)

---

## 1. Overview

The data pipeline populates the entity database from Wikidata's structured knowledge graph and Wikipedia's unstructured text. It is designed as a **two-phase, offline-first process**:

1. **Python scraper** queries Wikidata (SPARQL) and Wikipedia (REST API) → writes JSONL files.
2. **Laravel import** reads JSONL → creates entities and relationships via queued jobs.

This architecture avoids streaming infrastructure (Kafka, RabbitMQ) in favor of simple file-based data exchange. The JSONL files act as a durable checkpoint: you can re-import, audit, or diff them without re-scraping.

### Design Principles

| Principle | Rationale |
|-----------|-----------|
| **Offline-first** | Scraping is slow and rate-limited. Decoupling scrape and import lets you iterate on import logic without re-scraping. |
| **JSONL as interchange** | Human-readable, `git diff`-able, appendable. One entity per line enables streaming reads. |
| **Idempotent imports** | Re-running import on the same JSONL file should not create duplicates. `wikidata_id` is the natural dedup key. |
| **Pipeline-draft status** | All machine-generated data enters as `pipeline_draft` and must pass through verification before reaching `human_verified`. |
| **Separate embedding pass** | Embeddings are expensive and model-specific. Generating them as a post-import step allows re-embedding when switching models without re-importing. |

---

## 2. System Design

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Python Pipeline                              │
│                                                                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐      │
│  │ Wikidata │    │Wikipedia │    │  Entity  │    │  Dedup   │      │
│  │ SPARQL   │───▶│ Enricher │───▶│  Mapper  │───▶│          │──┐   │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │   │
│                                                                 │   │
│                                                    ┌────────────┘   │
│                                                    ▼                │
│                                               .jsonl files          │
│                                          pipeline/output/           │
└──────────────────────────────────────────────────────────────────────┘
                            │
                            │  php artisan pipeline:import
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         Laravel Import                               │
│                                                                      │
│  ┌──────────────────┐    ┌──────────────────┐    ┌────────────────┐ │
│  │ImportEntities    │    │ImportEntityJob    │    │ResolveRelation-│ │
│  │Command           │───▶│(queued per chunk) │───▶│shipsJob        │ │
│  └──────────────────┘    └──────────────────┘    └────────────────┘ │
│                                                                      │
│           ┌──────────────────┐    ┌──────────────────┐              │
│           │GenerateEmbeddings│    │GenerateEntity     │              │
│           │Command           │───▶│EmbeddingJob       │              │
│           └──────────────────┘    └──────────────────┘              │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │        PostgreSQL (entities, relationships, embeddings)      │    │
│  │        + pipeline_relationship_hints staging table           │    │
│  └─────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

### Data Flow Summary

| Stage | Input | Output | Tool |
|-------|-------|--------|------|
| 1. Scrape | SPARQL endpoint | Raw Wikidata items (dicts) | `pipeline.scraper.wikidata` |
| 2. Enrich | Raw items + Wikipedia API | Items with summaries, infobox data | `pipeline.scraper.wikipedia` |
| 3. Map | Enriched items | JSONL entities matching entity spec | `pipeline.mapper.entity_mapper` |
| 4. Dedup | Mapped entities | Deduplicated entity list | `pipeline.dedup.deduplicator` |
| 5. Write | Deduplicated entities | `pipeline/output/{type}.jsonl` | CLI |
| 6. Import | JSONL files | `entities` + `pipeline_relationship_hints` rows | `pipeline:import` |
| 7. Resolve | Staging table | `relationships` rows | `ResolveRelationshipsJob` |
| 8. Embed | Entities without embeddings | `embedding` column filled | `pipeline:embeddings` |

---

## 3. Python Pipeline

### Directory Structure

```
pipeline/
├── __init__.py
├── __main__.py          # CLI entry point (click + rich)
├── config.py            # Settings from .env, entity group registry
├── requirements.txt     # Python dependencies
├── .env.example
├── scraper/
│   ├── wikidata.py      # SPARQL query builder + result parser
│   └── wikipedia.py     # Wikipedia REST API + wptools infobox
├── mapper/
│   ├── type_configs.py  # Wikidata QID → entity_type mapping for all 30 types
│   ├── entity_mapper.py # Raw item → JSONL entity
│   └── relationship_mapper.py  # Wikidata P-properties → 76 relationship types
├── dedup/
│   └── deduplicator.py  # 3-layer dedup (QID, fuzzy, DB)
├── embeddings/
│   └── generator.py     # OpenAI embedding generation (optional Python-side)
├── queries/
│   ├── polity.sparql    # Reference SPARQL for manual testing
│   ├── place.sparql
│   ├── event.sparql
│   ├── economy.sparql
│   └── culture.sparql
└── output/
    └── .gitkeep         # JSONL output directory (gitignored)
```

### CLI Usage

```bash
# Install dependencies
cd pipeline && pip install -r requirements.txt

# Scrape a single type
python -m pipeline scrape --type political_entity --limit 200 --start-year -3000

# Scrape an entire group
python -m pipeline scrape --group POLITY --limit 100

# Dedup an existing JSONL file
python -m pipeline dedup pipeline/output/political_entity.jsonl

# Dedup with DB check (requires DATABASE_URL in .env)
python -m pipeline dedup pipeline/output/political_entity.jsonl --check-db
```

### 3.1 Wikidata Scraper (`scraper/wikidata.py`)

Builds SPARQL queries per entity type using configuration from `mapper/type_configs.py`. Each type maps to one or more Wikidata classes (Q-items) and properties (P-items).

**Query structure:**

```sparql
SELECT ?item ?itemLabel ?coord ?inception ?dissolved ?article WHERE {
  ?item wdt:P31/wdt:P279* wd:Q3024240 .       # instance of (or subclass of) historical country
  OPTIONAL { ?item wdt:P625 ?coord . }          # coordinate location
  OPTIONAL { ?item wdt:P571 ?inception . }      # inception date
  OPTIONAL { ?item wdt:P576 ?dissolved . }      # dissolved date
  OPTIONAL { ?article schema:about ?item ;
             schema:isPartOf <https://en.wikipedia.org/> . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
}
LIMIT 200
```

**Rate limiting:** 1 request per second to the public SPARQL endpoint. Batch property enrichment uses 50 QIDs per request.

**Coordinate parsing:** Wikidata returns WKT `Point(lon lat)` strings. The scraper parses these into `[lon, lat]` arrays suitable for GeoJSON.

**Date parsing:** `xsd:dateTime` values are parsed to year integers. Negative years indicate BCE dates.

### 3.2 Wikipedia Enricher (`scraper/wikipedia.py`)

For each entity that has a linked Wikipedia article:

1. **TextExtracts API** — fetches the first 3 sentences (plain text, no HTML).
2. **wptools infobox** — parses structured infobox data for supplementary attributes.
3. **Redirect collection** — captures redirect titles as `alternative_names`.

Batch API calls: up to 20 titles per request (Wikipedia API limit).

### 3.3 Entity Mapper (`mapper/entity_mapper.py`)

Transforms raw scraped items into the JSONL schema that matches the Entity Specification v2.1. Key transformations:

| Source | Target Field | Logic |
|--------|-------------|-------|
| `itemLabel` | `name` | Direct mapping |
| Redirect titles | `alternative_names` | Collected from Wikipedia redirects |
| `coord` | `geom` | `{"type": "Point", "coordinates": [lon, lat]}` |
| `inception` | `temporal_start`, `temporal_start_year` | Year extraction, sign for BCE |
| `dissolved` | `temporal_end`, `temporal_end_year` | Year extraction |
| Start/end distance | `duration_type` | `instant` if same year, `period` otherwise |
| TextExtract | `summary` | First 3 sentences from Wikipedia |
| Heuristic analysis | `tags` | Era detection (ancient, medieval, etc.) + geographic keywords |
| Article length + property count | `impact_score` | 0.0–1.0 heuristic estimate |
| Type config `field_map` | `attributes` | Type-specific JSONB attributes |

**Relationship hints:** The mapper also extracts `_relationship_hints` — an array of objects like:

```json
{
  "relationship_type": "capital_of",
  "target_wikidata_id": "Q220",
  "target_label": "Rome",
  "wikidata_property": "P36",
  "confidence": "high"
}
```

These are passed through in the JSONL but stripped by `ImportEntityJob` before entity creation. They're staged in `pipeline_relationship_hints` for later batch resolution.

### 3.4 Type Configuration (`mapper/type_configs.py`)

Maps all 30 entity types to their Wikidata classes and properties. Example:

```python
"political_entity": {
    "classes": ["Q3024240", "Q6256", "Q3624078"],  # historical country, country, sovereign state
    "properties": {
        "P36": "capital",
        "P17": "country",
        "P571": "inception",
        "P576": "dissolved",
    },
    "field_map": {
        "government_type": "P122",
        "official_language": "P37",
    },
},
```

### 3.5 Relationship Mapper (`mapper/relationship_mapper.py`)

Maps ~35 Wikidata properties to the 76 WikiGlobe relationship types. Features:

- **Context disambiguation:** Some Wikidata properties map to different relationship types depending on entity type. E.g., `P710` (participant) → `signed_by` for treaties, `participated_in` otherwise.
- **Inverse tracking:** Records both the forward relationship and the inverse (e.g., `administered_by` ↔ `administered`).
- **Symmetric types:** Relationships like `married_to` and `allied_with` are marked symmetric — only one direction needs to be stored.

---

## 4. JSONL Schema

Each line in a `.jsonl` file is a JSON object conforming to this schema:

```jsonc
{
  // Required
  "name": "Roman Empire",
  "entity_type": "political_entity",
  "entity_group": "POLITY",
  "wikidata_id": "Q2277",

  // Temporal (nullable)
  "temporal_start": "27 BCE",
  "temporal_end": "476 CE",
  "temporal_start_year": -27,
  "temporal_end_year": 476,
  "duration_type": "period",

  // Spatial (nullable)
  "geom": {
    "type": "Point",
    "coordinates": [12.4964, 41.9028]
  },

  // Content
  "summary": "The Roman Empire was the post-Republican state...",
  "significance": null,
  "alternative_names": ["Imperium Romanum", "Eastern Roman Empire"],
  "tags": ["ancient", "europe", "mediterranean"],

  // Type-specific
  "attributes": {
    "government_type": "autocracy",
    "official_language": "Latin"
  },

  // Pipeline metadata
  "impact_score": 0.92,
  "sources": [
    {
      "source_type": "url",
      "url": "https://www.wikidata.org/wiki/Q2277",
      "accessed_at": "2026-03-21"
    },
    {
      "source_type": "url",
      "url": "https://en.wikipedia.org/wiki/Roman_Empire",
      "accessed_at": "2026-03-21"
    }
  ],

  // Stripped before import (staged separately)
  "_relationship_hints": [
    {
      "relationship_type": "capital_of",
      "target_wikidata_id": "Q220",
      "target_label": "Rome",
      "wikidata_property": "P36",
      "confidence": "high"
    }
  ]
}
```

**Conventions:**

- Fields prefixed with `_` are pipeline metadata stripped during import.
- `wikidata_id` is the primary dedup key across all pipeline operations.
- `temporal_start_year` / `temporal_end_year` are integers (negative = BCE).
- `geom` uses GeoJSON geometry format (currently Point; v2 adds Polygon/LineString).
- `sources` array carries provenance for every entity.

---

## 5. Laravel Import Layer

### 5.1 Import Command (`pipeline:import`)

```bash
# Import a single file
php artisan pipeline:import pipeline/output/political_entity.jsonl

# Import all JSONL files in the output directory
php artisan pipeline:import pipeline/output/ --all

# Synchronous mode (for debugging / small batches)
php artisan pipeline:import pipeline/output/city.jsonl --sync

# Skip dedup check (when you know the file is clean)
php artisan pipeline:import pipeline/output/city.jsonl --skip-dedup

# Custom batch ID for tracking
php artisan pipeline:import pipeline/output/ --all --batch-id=v1-initial
```

**Behavior:**

1. Reads each `.jsonl` file line by line (memory-efficient streaming).
2. Checks for existing entities by `wikidata_id` or exact `name + entity_type` match.
3. Dispatches `ImportEntityJob` for each new entity (or processes synchronously with `--sync`).
4. After all entity jobs complete, dispatches `ResolveRelationshipsJob` to process the staging table.

### 5.2 Import Entity Job

- Validates minimum required fields (`name`, `entity_type`, `entity_group`).
- Strips `_relationship_hints` and `_infobox` metadata.
- Forces `verification_status` to `pipeline_draft`.
- Builds `EntityData` DTO and calls `CreateEntityAction`.
- Stages relationship hints in `pipeline_relationship_hints` table.
- Queued with 3 retries, 10-second backoff.

### 5.3 Embedding Command (`pipeline:embeddings`)

```bash
# Generate embeddings for all entities that don't have one
php artisan pipeline:embeddings --pending

# Regenerate all embeddings (e.g., after model upgrade)
php artisan pipeline:embeddings --all --reembed

# Only a specific type
php artisan pipeline:embeddings --type political_entity
```

### 5.4 Embedding Job

Builds a canonical text representation of the entity:

```
[political_entity] Roman Empire (Imperium Romanum; Eastern Roman Empire)
The Roman Empire was the post-Republican state of ancient Rome.
Significance: [if available]
Tags: ancient, europe, mediterranean
Temporal: 27 BCE – 476 CE
Location: 41.9028°N, 12.4964°E
```

Calls OpenAI `text-embedding-3-small` (1536 dimensions) and stores the result vector in the `embedding` column. The same canonical format is used in both the Python `pipeline/embeddings/generator.py` and the PHP `GenerateEntityEmbeddingJob` to ensure consistency.

---

## 6. Deduplication Strategy

Deduplication operates at three layers:

### Layer 1: Wikidata ID Exact Match

**Where:** Python pipeline + Laravel import.

If two entities share the same `wikidata_id` (QID), they are the same entity. The first occurrence wins; later occurrences merge their `alternative_names` and `sources`.

### Layer 2: Fuzzy Name + Temporal Overlap

**Where:** Python pipeline (`pipeline/dedup/deduplicator.py`).

For entities without a QID match, the deduplicator applies:

1. **Same `entity_type`** — only compares within the same type.
2. **Fuzzy name match** — `thefuzz.fuzz.token_sort_ratio(a, b) >= 88`.
3. **Temporal overlap** — if both entities have temporal data, their year ranges must overlap. Missing dates are treated as "can't disprove overlap" (conservative).

When a fuzzy match is found, names are merged and the entity with more attributes wins.

### Layer 3: Database Check (Optional)

**Where:** Python pipeline with `--check-db` flag.

Queries PostgreSQL using `pg_trgm` trigram similarity:

```sql
SELECT entity_id, name, entity_type
FROM entities
WHERE entity_type = $1
  AND similarity(name, $2) > 0.6
ORDER BY similarity(name, $2) DESC
LIMIT 5;
```

Results are then verified in Python with `token_sort_ratio >= 88` to avoid false positives from the DB's coarser similarity threshold.

**Requires:** `pg_trgm` extension (already in `docker/db/init-extensions.sql`).

### Import-Time Dedup

The `ImportEntitiesCommand` performs a final check before dispatching jobs:

```php
// Check by wikidata_id
$exists = Entity::where('wikidata_id', $data['wikidata_id'])->exists();

// If no wikidata_id, check by exact name + type
if (!$exists && isset($data['name'])) {
    $exists = Entity::where('name', $data['name'])
        ->where('entity_type', $data['entity_type'])
        ->exists();
}
```

---

## 7. Relationship Resolution

Relationships cannot be created during entity import because the target entity may not exist yet. The pipeline uses a **two-phase approach**:

### Phase 1: Hint Staging (During Import)

`ImportEntityJob` writes relationship hints to the `pipeline_relationship_hints` table:

| Column | Type | Description |
|--------|------|-------------|
| `source_entity_id` | uuid (FK) | The entity that was just imported |
| `relationship_type` | string | One of the 76 WikiGlobe relationship types |
| `target_wikidata_id` | string | QID of the target entity (e.g., `Q220`) |
| `target_label` | string | Human-readable label for logging |
| `confidence` | string | `high`, `medium`, or `low` |
| `wikidata_property` | string | Source Wikidata property (e.g., `P36`) |
| `batch_id` | string | Groups hints for batch processing |
| `resolved` | boolean | Set to `true` after processing |

### Phase 2: Batch Resolution (After Import)

`ResolveRelationshipsJob` processes all unresolved hints for a batch:

1. **Lookup target**: `Entity::where('wikidata_id', $hint->target_wikidata_id)->first()`
2. **Dedup check**: Ensures no existing relationship with the same `(source, target, type)` or `(target, source, type)` for symmetric types.
3. **Self-reference guard**: Skips hints where source and target resolve to the same entity.
4. **Create relationship**: Inserts into the `relationships` table with source citations.
5. **Mark resolved**: Sets `resolved = true` and records a note.

**Symmetric types** (e.g., `married_to`, `allied_with`, `neighbour_of`) are checked bidirectionally — if `A married_to B` already exists, `B married_to A` is skipped.

### Wikidata Property Mapping

~35 Wikidata properties are mapped to WikiGlobe relationship types in `mapper/relationship_mapper.py`. Examples:

| Wikidata Property | WikiGlobe Type | Inverse |
|-------------------|----------------|---------|
| P36 (capital) | `capital_of` | `has_capital` |
| P17 (country) | `located_in_territory` | `administered` |
| P155 (follows) | `succeeded_by` | `preceded_by` |
| P156 (followed by) | `preceded_by` | `succeeded_by` |
| P710 (participant) | `participated_in` / `signed_by` | context-dependent |
| P22 (father) | `parent_of` | `child_of` |
| P40 (child) | `child_of` | `parent_of` |
| P26 (spouse) | `married_to` | `married_to` (symmetric) |
| P530 (diplomatic relation) | `allied_with` | `allied_with` (symmetric) |
| P127 (owned by) | `patronized` | `patronized_by` |
| P108 (employer) | `employed_by` | `employed` |

---

## 8. Embedding Generation

### Strategy

Embeddings are generated as a **separate post-import pass**, not during scraping. This decision is driven by:

1. **Model flexibility** — re-embed everything when switching from `text-embedding-3-small` to a newer model.
2. **Update handling** — when an entity's summary or attributes change, its embedding can be regenerated independently.
3. **Cost control** — embeddings are the most expensive pipeline operation; separating them allows throttling.

### Canonical Text Format

Both the Python (`pipeline/embeddings/generator.py`) and PHP (`GenerateEntityEmbeddingJob.php`) implementations produce identical text for the same entity:

```
[{entity_type}] {name} ({alternative_names joined by "; "})
{summary}
Significance: {significance}
Tags: {tags joined by ", "}
Temporal: {temporal_start} – {temporal_end}
Location: {lat}°N/S, {lon}°E/W
```

This ensures that embeddings generated in Python (for bulk pre-generation) and PHP (for incremental updates via admin panel) are directly comparable in vector space.

### Storage

- **Column:** `embedding vector(1536)` on the `entities` table.
- **Index:** HNSW with `vector_cosine_ops` for approximate nearest-neighbor search.
- **Version tracking:** `embedding_version` column stores the model name/version.

### Search Query

```sql
SELECT entity_id, name, entity_type,
       1 - (embedding <=> $1::vector) AS similarity
FROM entities
WHERE embedding IS NOT NULL
ORDER BY embedding <=> $1::vector
LIMIT 20;
```

---

## 9. Verification Workflow

All pipeline-imported data follows the verification status workflow:

```
pipeline_draft → auto_validated → needs_review → human_verified
       │                                              │
       └──────────── rejected ◄──────────────────────┘
```

| Status | Meaning |
|--------|---------|
| `pipeline_draft` | Machine-generated, not yet validated |
| `auto_validated` | Passed automated checks (has name, type, temporal data, reasonable coordinates) |
| `needs_review` | Flagged for human attention (low confidence, missing fields, unusual data) |
| `human_verified` | Confirmed correct by a human reviewer |
| `rejected` | Determined to be incorrect or duplicate |

**v1 scope:** All imported entities start as `pipeline_draft`. Auto-validation and the review queue are v2 features.

---

## 10. Operational Runbook

### First-Time Setup

```bash
# 1. Set up Python environment
cd pipeline
python -m venv .venv
.venv/bin/activate        # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
# Edit .env: set OPENAI_API_KEY, adjust rate limits

# 2. Ensure Laravel queue worker is running
cd ../api
php artisan queue:work --queue=default --tries=3

# 3. Ensure pg_trgm extension exists (for DB dedup)
# Already handled by docker/db/init-extensions.sql
```

### Full Pipeline Run

```bash
# Step 1: Scrape all groups (conservative limits for v1)
cd pipeline
python -m pipeline scrape --group POLITY --limit 200
python -m pipeline scrape --group PLACE --limit 200
python -m pipeline scrape --group EVENT --limit 200
python -m pipeline scrape --group ECONOMY --limit 100
python -m pipeline scrape --group CULTURE --limit 100

# Step 2: Review JSONL output
ls -la output/               # Check file sizes
head -1 output/political_entity.jsonl | python -m json.tool   # Spot check

# Step 3: Import into Laravel
cd ../api
php artisan pipeline:import ../pipeline/output/ --all --batch-id=v1-initial

# Step 4: Check import results
php artisan tinker --execute="echo Entity::count();"

# Step 5: Generate embeddings
php artisan pipeline:embeddings --pending

# Step 6: Verify embedding coverage
php artisan tinker --execute="echo Entity::whereNull('embedding')->count();"
```

### Incremental Updates

```bash
# Scrape only new political entities from the last 500 years
python -m pipeline scrape --type political_entity --start-year 1500 --limit 50

# Import (dedup will skip existing entities)
php artisan pipeline:import ../pipeline/output/political_entity.jsonl

# Generate embeddings for new entities only
php artisan pipeline:embeddings --pending
```

### Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| SPARQL timeout | Query too broad | Reduce `--limit`, add `--start-year`/`--end-year` filters |
| `ImportEntityJob` fails | Missing required fields | Check JSONL line with `jq`. Must have `name`, `entity_type`, `entity_group`. |
| Duplicate entities after import | `wikidata_id` missing | Run `python -m pipeline dedup` before importing |
| Embedding job timeout | OpenAI rate limit | Reduce chunk size in `GenerateEmbeddingsCommand` |
| Relationships not created | Target entity not imported yet | Re-run `ResolveRelationshipsJob` after importing more data |

---

## 11. v2+ Roadmap

### v2: LLM Enrichment & Auto-Validation

- **LLM enrichment pass** — Use GPT-4o / Claude to generate `significance` text, resolve fuzzy dates ("mid-3rd century" → year range), and fill missing attributes.
- **Auto-validation rules** — Automated checks that promote `pipeline_draft` → `auto_validated`:
  - Has `name` and `entity_type`
  - Has at least one temporal field
  - Coordinates are within valid ranges
  - `summary` length > 50 characters
  - `wikidata_id` is well-formed (Q + digits)
- **Review queue UI** — Admin panel page listing `needs_review` entities with inline editing.

### v2: Advanced Geometry

- **Polygons for territories** — Scrape simplified boundary geometries from Wikidata/OpenHistoricalMap for political entities and display on the map.
- **LineStrings for trade routes** — Approximate route geometries from waypoint sequences.
- **Geometry snapshots** — Time-varying geometries stored in the `geometry_snapshots` table (see `plans/attributes_and_geometry_snapshots.md`).

### v3: Scheduled Pipeline & Monitoring

- **Cron-based scraping** — Laravel scheduler triggers Python scraper via `Process::run()`.
- **Data quality dashboard** — Track coverage per entity type, field completeness, embedding coverage.
- **Change detection** — Compare Wikidata entity revision IDs to detect upstream changes and trigger re-imports.
- **Pipeline metrics** — Import rate, failure rate, dedup hit rate, relationship resolution rate.

### v3: Community Contributions

- **CSV/JSONL upload** — Allow researchers to upload entity files through the admin panel.
- **Wikipedia watchlist integration** — Monitor Wikipedia articles linked to entities and flag changes.
- **Source quality scoring** — Weight sources by reliability and freshness.

---

## Appendix A: Configuration Reference

### Python Pipeline (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `WIKIDATA_ENDPOINT` | `https://query.wikidata.org/sparql` | SPARQL endpoint URL |
| `USER_AGENT` | `WikiGlobePipeline/1.0` | HTTP User-Agent header |
| `OPENAI_API_KEY` | (none) | For Python-side embedding generation |
| `OUTPUT_DIR` | `pipeline/output` | JSONL output directory |
| `RATE_LIMIT_CALLS` | `1` | Max requests per rate-limit period |
| `RATE_LIMIT_PERIOD` | `1` | Seconds per rate-limit period |
| `DATABASE_URL` | (none) | PostgreSQL connection for DB dedup |

### Laravel (`.env`)

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | For PHP-side embedding generation |
| `OPENAI_EMBEDDING_MODEL` | Model name (default: `text-embedding-3-small`) |

### Laravel Config (`config/services.php`)

```php
'openai' => [
    'api_key' => env('OPENAI_API_KEY'),
    'embedding_model' => env('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small'),
],
```

---

## Appendix B: Migration Reference

### `pipeline_relationship_hints` Table

```sql
CREATE TABLE pipeline_relationship_hints (
    id              BIGSERIAL PRIMARY KEY,
    source_entity_id UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    relationship_type VARCHAR NOT NULL,
    target_wikidata_id VARCHAR NOT NULL,
    target_label     VARCHAR,
    confidence       VARCHAR DEFAULT 'medium',
    wikidata_property VARCHAR,
    batch_id         VARCHAR NOT NULL,
    resolved         BOOLEAN DEFAULT FALSE,
    resolution_note  VARCHAR,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_prh_batch ON pipeline_relationship_hints (batch_id);
CREATE INDEX idx_prh_resolved_batch ON pipeline_relationship_hints (resolved, batch_id);
CREATE INDEX idx_prh_target_wikidata ON pipeline_relationship_hints (target_wikidata_id);
```

---

## Appendix C: Entity Type → Wikidata Class Reference

| Entity Type | Primary Wikidata Class | QID |
|------------|----------------------|-----|
| `political_entity` | Historical country | Q3024240 |
| `dynasty` | Dynasty | Q164950 |
| `person` | Human (filtered: politician) | Q5 |
| `military_unit` | Military unit | Q176799 |
| `diplomatic_relationship` | Treaty | Q131569 |
| `social_class` | Social class | Q187588 |
| `city` | City | Q515 |
| `infrastructure_monument` | Monument | Q4989906 |
| `extraction_infra` | Mine | Q820477 |
| `educational_institution` | University | Q3918 |
| `event_war` | War | Q198 |
| `event_battle` | Battle | Q178561 |
| `event_treaty` | Treaty | Q131569 |
| `event_rebellion` | Rebellion | Q124734 |
| `event_natural_disaster` | Natural disaster | Q8065 |
| `event_tech_adoption` | Invention | Q15061650 |
| `event_legal_reform` | Reform | Q327333 |
| `migration` | Human migration | Q187668 |
| `epidemic_disease` | Epidemic | Q44512 |
| `trade_route` | Trade route | Q208736 |
| `natural_resource` | Natural resource | Q188460 |
| `currency_monetary_system` | Currency | Q8142 |
| `cultural_work` | Work of art | Q838948 |
| `intellectual_movement` | Intellectual movement | Q2198855 |
| `archaeological_culture` | Archaeological culture | Q465299 |
| `language` | Language | Q34770 |
| `religious_text` | Religious text | Q179461 |
| `legal_code` | Code of law | Q2135540 |
| `religious_movement` | Religious movement | Q2061186 |
| `technology` | Technology | Q11016 |
