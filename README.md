# Historical Atlas Project

## Foundational Architecture Document

### Platform, Map Layers, Storage, and Application Design

> *Mapping History Through Space and Time*
> AI-Generated Data · Human Verification · Open Infrastructure

**Version 1.1 — March 2026**
Companion documents: Data Pipeline and Storage Architecture, [Entity Specification v2.1](docs/entity_specification.md)

---

## Table of Contents

1. [Project Vision and Problem Statement](#1-project-vision-and-problem-statement)
2. [Architecture Overview: The Three-Layer Model](#2-architecture-overview-the-three-layer-model)
3. [Layer 1: Historical Base Map (OpenHistoricalMap)](#3-layer-1-historical-base-map-openhistoricalmap)
4. [Layer 2: Historical Entity Data (Custom Database)](#4-layer-2-historical-entity-data-custom-database)
5. [Layer 3: Annotations, Beziers, and Custom Geometry](#5-layer-3-annotations-beziers-and-custom-geometry)
6. [The AI-to-Human Verification Lifecycle](#6-the-ai-to-human-verification-lifecycle)
7. [AI-Generated Location Data: Feasibility and Strategy](#7-ai-generated-location-data-feasibility-and-strategy)
8. [Data Model: Connecting Entities to the Map](#8-data-model-connecting-entities-to-the-map)
9. [Technology Stack](#9-technology-stack)
10. [Cost Analysis: Why Not ArcGIS](#10-cost-analysis-why-not-arcgis)
11. [API Design](#11-api-design)
12. [Frontend Architecture](#12-frontend-architecture)
13. [Deployment and Infrastructure](#13-deployment-and-infrastructure)
14. [Development Roadmap](#14-development-roadmap)
15. [Open Questions and Future Considerations](#15-open-questions-and-future-considerations)

---

## 1. Project Vision and Problem Statement

This document defines the foundational technical architecture for the Historical Atlas Project: an interactive, map-based application for visualizing historical data across time and geography. The system enables users to explore political entities, historical figures, events, trade routes, resources, and cultural movements on a temporal map that shows the world as it was at any point in history.

The project originates from a comprehensive historical database design encompassing 30 primary entities with detailed field specifications, comprehensive relationship mappings between all entities, and 48 analytical queries organized across multiple categories. That design specification provides the data model. The companion Data Pipeline and Storage Architecture document provides the ingestion and processing pipeline. This document provides the technical platform to bring that data to life on a map.

### 1.1 Core Principles

- **AI-first data generation:** Initial datasets are produced by large language models working in concert with NLP extraction tools, providing breadth of coverage across time periods and regions while offloading deterministic tasks from the LLM
- **Human verification:** All AI-generated data passes through a structured review pipeline where domain experts correct coordinates, validate dates, enrich sources, and adjust confidence levels
- **Open infrastructure:** Built entirely on open-source tools and open data (OpenHistoricalMap, PostgreSQL, PostGIS, pgvector, MapLibre GL JS), avoiding vendor lock-in and minimizing recurring costs
- **Temporal-spatial native:** Every entity in the system has both a time range and a geographic footprint, making time a first-class dimension alongside space
- **Source traceability:** Every fact links to citations, with confidence levels and support for competing historical interpretations
- **Resources as foundation:** The system treats natural resources and extraction infrastructure as fundamental to historical understanding, with separate entities and relationship types for resource control, trade, and economic dynamics

### 1.2 What Users Will Experience

A user opens the application and sees a map of the world. They drag a time slider to 200 CE. The map transforms: borders shift to show the Roman Empire, Han Dynasty, Kushan Empire, and Parthian Empire. Cities appear at their historical locations with population indicators. The user clicks on Rome and sees a panel with population data, ruling dynasty, active trade routes, and linked events. They click a trade route connecting Rome to Chang'an and see the goods traded, the cities along the way, and the timeline of the route's activity. They advance the slider to 400 CE and watch borders contract, cities change hands, and new political entities emerge.

A researcher uses the search bar to find "collapse of bronze age trade networks." Semantic search via pgvector embeddings returns entities about the Late Bronze Age Collapse, the Sea Peoples, the destruction of Ugarit, and the disruption of tin trade routes — even though none of those entities contain the exact search terms. The researcher clicks "Similar entities" and discovers structural parallels with the Crisis of the Third Century and the fall of the Han Dynasty, surfaced automatically by embedding similarity.

This is the experience the architecture must support.

---

## 2. Architecture Overview: The Three-Layer Model

The system uses a three-layer architecture where each layer serves a distinct purpose and can be developed, scaled, and maintained independently. The layers compose visually in the browser: the base map provides geographic context, the entity layer provides historical content, and the annotation layer provides analytical and editorial overlays.

| Layer | Purpose | Technology | Data Source |
|-------|---------|------------|-------------|
| **1. Historical Base Map** | Period-accurate geography: borders, cities, roads, rivers, terrain as they existed at a given date | OpenHistoricalMap vector tiles rendered via MapLibre GL JS | OpenHistoricalMap (open, community-maintained, CC0) |
| **2. Entity Data Overlay** | Historical entities: events, people, dynasties, military units, resources, trade routes, and the other 30 entity types from the database specification | PostgreSQL + PostGIS + pgvector served as GeoJSON via custom REST API | AI-generated via the 8-stage pipeline, human-verified |
| **3. Annotations & Custom Geometry** | User-drawn bezier curves for campaign routes and trade flows, text annotations, relationship arrows, analytical overlays like influence zones and heatmaps | MapLibre drawing tools + custom geometry stored in PostGIS | User-created within the application |

### 2.1 How the Layers Interact

The base map (Layer 1) and entity data (Layer 2) share a temporal axis. When the user moves the time slider, both layers update simultaneously: OHM tiles filter to show geography at that date, and the API returns entities whose temporal range includes that date. Annotations (Layer 3) can optionally be time-bound as well, appearing and disappearing with the time slider, or they can be persistent overlays visible at all times.

Entity data from Layer 2 can reference OHM features from Layer 1. For example, a political entity record may store a reference to the OHM relation ID for its border polygon rather than duplicating the geometry, drawing the border from OHM while enriching it with metadata from the entity database.

---

## 3. Layer 1: Historical Base Map (OpenHistoricalMap)

### 3.1 Why OpenHistoricalMap

OpenHistoricalMap (OHM) is a community-driven collaborative mapping project that maps historical geography using OpenStreetMap technology and processes. Whereas OpenStreetMap only includes present-day data, OHM welcomes historical data and preserves multiple copies of a feature as it changes over time. The project has been active since 2013 and became a charter project of OpenStreetMap U.S. in 2021.

Using OHM as the base layer provides several critical advantages:

- **Free and open:** OHM data is in the public domain under a CC0 dedication, with no licensing costs
- **Time-aware:** Every feature has `start_decdate` and `end_decdate` properties, enabling temporal filtering from 4001 BCE to the present
- **Vector tiles:** Published as standard vector tilesets compatible with MapLibre GL JS, with multiple styles including Historical and Woodblock
- **Community maintained:** Growing contributor base including professional historians, GIS specialists, and OpenStreetMap contributors
- **No hosting cost:** Tiles are served from OHM's infrastructure; your application consumes them directly
- **Rich data access:** Overpass API for structured queries, SPARQL via QLever for federated queries with Wikidata, Nominatim for search, and full planet dumps for bulk processing

### 3.2 OHM Vector Tile Integration

OHM publishes vector tilesets that can be consumed by any MapLibre-compatible client. The `@openhistoricalmap/map-styles` NPM module provides ready-to-use stylesheets. For custom styling, you can write your own stylesheet pointing to OHM vector tiles. The integration steps are:

1. Configure MapLibre GL JS to load OHM vector tiles as the base style source
2. Apply temporal filtering using the `start_decdate` and `end_decdate` properties on each feature
3. Bind the time slider UI control to update the filter expression on the map style dynamically
4. Optionally write custom stylesheets for visual differentiation of borders, cities, roads, and waterways at different historical periods

### 3.3 OHM Limitations and Mitigation

OHM focuses on historical objects (borders, infrastructure, physical features) but explicitly does not collect data on historical events. This is precisely the gap that Layer 2 fills. Additionally, OHM coverage is uneven across regions and periods. For areas with sparse OHM data, the application should:

- Fall back to modern OpenStreetMap tiles with a visual dimming effect indicating approximate geography
- Show a "coverage quality" indicator so users understand the base map's reliability
- Proactively contribute verified geographic corrections back to OHM, creating a virtuous cycle between the two projects

---

## 4. Layer 2: Historical Entity Data (Custom Database)

### 4.1 Entity Types

The historical database design specifies 30 primary entity types organized into 5 entity groups (see [Entity Specification v2.1](docs/entity_specification.md)). Each has temporal bounds (start/end dates in EDTF format), spatial attributes (coordinates or geographic scope), source citations, and confidence levels. The entities that appear on the map are organized by group:

| Group | Entity Types (30 total) | Map Representation |
|-------|------------------------|--------------------|
| **POLITY** (6) | Political Entities, Dynasties, Persons, Military Units, Diplomatic Relationships, Social Classes | Polygons (borders) from OHM or custom, labeled regions, capital markers, point markers for persons |
| **PLACE** (4) | Cities, Infrastructure/Monuments, Extraction Infrastructure, Educational Institutions | Point markers at locations, building icons, mine/farm markers |
| **EVENT** (9) | Wars, Battles, Treaties, Rebellions, Natural Disasters, Tech Adoptions, Legal Reforms, Migrations, Epidemics | Point markers, area indicators, temporal highlight animations, animated wavefronts |
| **ECONOMY** (3) | Trade Routes, Natural Resources, Currencies/Monetary Systems | Line strings (routes), point markers (resources), flow indicators |
| **CULTURE** (8) | Cultural Works, Intellectual Movements, Archaeological Cultures, Languages, Religious Texts, Legal Codes, Religious Movements, Technologies | Shaded regions showing geographic spread and diffusion over time |

### 4.2 PostGIS Spatial Capabilities

PostGIS provides the same spatial query capabilities that ArcGIS charges thousands of dollars per year for. Every spatial operation the application needs is available as a PostgreSQL function:

- **Spatial indexing** (GiST indexes) for sub-millisecond geographic lookups across millions of records
- **Spatial joins:** Find all events within a political entity's borders at a given date
- **Buffer operations:** Find all entities within N kilometers of a point or along a route
- **Polygon intersection and containment:** Determine which political entity controlled a location at a specific time
- **Distance calculations** along trade route LineStrings
- **Coordinate transformation** between reference systems (WGS84 for storage, Web Mercator for display)
- **Geometry simplification** for efficient rendering at different zoom levels

### 4.3 The Temporal Query Pattern

The fundamental query for the map is: "show me all entities that existed at time T within bounding box B." This combines PostGIS spatial intersection with temporal range overlap:

```sql
-- Core map query: entities within viewport at a given point in time
select *, ST_AsGeoJSON(geom) as geojson
from entities
where geom && ST_MakeEnvelope(west, south, east, north, 4326)
  and temporal_start <= T
  and (temporal_end is null or temporal_end >= T)
  and verification_status in ('human_verified', 'expert_verified')
order by display_priority desc
limit 500;
```

PostGIS GiST indexes on the geometry column and B-tree indexes on the temporal columns make this query performant even with millions of records. The `verification_status` filter ensures only reviewed data appears to regular users; reviewers see all data including unverified entities.

---

## 5. Layer 3: Annotations, Beziers, and Custom Geometry

### 5.1 Purpose

The annotation layer enables users and editors to add visual elements to the map that go beyond what the entity database stores. These serve both analytical and presentational purposes:

- **Bezier curves** representing campaign routes, migration paths, or trade flow visualizations with directional indicators
- **Text annotations** labeling regions, explaining events, or providing context that doesn't belong in an entity record
- **Relationship arrows** connecting related entities visually (e.g., diplomatic ties, trade partnerships, influence lines)
- **Analytical overlays** such as influence zones, population density gradients, resource distribution heatmaps, or cultural diffusion frontiers
- **Freeform polygons** for marking areas of interest, contested territories, approximate regions for entities without precise borders

### 5.2 Data Model

Annotations are stored in PostGIS as standard geometries with metadata:

| Field | Type | Description |
|-------|------|-------------|
| `annotation_id` | UUID | Unique identifier |
| `geometry` | PostGIS geometry | Point, LineString, Polygon, or raw bezier control points |
| `annotation_type` | enum | `bezier_curve`, `text_label`, `arrow`, `overlay`, `freeform_polygon` |
| `style` | JSONB | Rendering properties: color, weight, opacity, dash pattern, arrow heads, fill pattern |
| `temporal_start` | text (EDTF) | Optional: when this annotation becomes visible on the time slider |
| `temporal_end` | text (EDTF) | Optional: when this annotation disappears |
| `linked_entities` | UUID[] | Array of entity IDs this annotation relates to |
| `author_id` | UUID | The user who created the annotation |
| `layer_group` | text | Named layer for toggling visibility (e.g., `"trade_flows"`, `"campaign_routes"`) |
| `label_text` | text | Display text for `text_label` annotations |

### 5.3 Bezier Curve Handling

MapLibre GL JS does not natively render bezier curves. The solution is to store bezier control points in PostGIS and interpolate them into dense LineString geometries for rendering. The API stores the canonical control points as a JSONB array (start point, control point 1, control point 2, end point for each segment). The rendering endpoint returns either raw control points (for interactive editing) or interpolated GeoJSON LineStrings (for display at the appropriate resolution for the current zoom level).

Client-side, a custom drawing tool lets users place and drag control points with real-time curve preview. The tool snaps to existing entity markers when the user drags near them, enabling quick creation of relationship arrows and route curves between entities.

---

## 6. The AI-to-Human Verification Lifecycle

### 6.1 Lifecycle Stages

Every entity in the system passes through a defined lifecycle. The companion Data Pipeline document describes the eight technical stages in detail; this section focuses on how the lifecycle manifests in the application.

> **Note:** Status values align with the `verification_status` enum defined in [Entity Specification v2.1, Section 2.2](docs/entity_specification.md).

| Status | What It Means | Who Sees It | Map Indicator |
|--------|---------------|-------------|---------------|
| `pipeline_draft` | Entity created by the pipeline (Stages 1–7 complete). Not yet validated. | Reviewers only | Red marker with dashed outline |
| `auto_validated` | Entity passed Stage 7 automated checks. Awaiting human review. | Reviewers only | Red marker, solid outline |
| `needs_review` | Entity in the human review queue, awaiting a reviewer. | Reviewers only | Red marker, listed in review dashboard |
| `in_review` | A reviewer has claimed this entity and is actively examining it. | The assigned reviewer + admins | Yellow marker |
| `human_verified` | A reviewer has approved the entity, possibly with corrections. | All users | Green marker (standard display) |
| `expert_verified` | A domain expert has confirmed a contested or complex entity. | All users | Green marker with expert badge |
| `flagged` | Multiple reviewers or sources disagree; entity is visible but under re-examination. | All users | Orange marker with info icon |
| `rejected` | Entity was determined to be fabricated, duplicate, or nonsensical. | Admins only (for audit) | Not displayed on map |
| `merged` | Entity was merged into another entity (duplicate resolution). | Admins only (for audit) | Not displayed; redirect to merge target |

### 6.2 Review Interface

The review interface is built into the main application, not a separate tool. It presents a split view: the map on the left showing the entity's location on the OHM base map at the relevant time period, and a structured data form on the right. The reviewer sees:

- The entity marker on the map (draggable for coordinate correction)
- The LLM-generated summary with inline source citations
- The raw source context windows (expandable)
- Any validation failures highlighted in red
- The geocoding cascade result showing which service matched and at what confidence
- The date resolution chain from raw text to resolved EDTF value
- Suggested relationships to nearby entities

Review actions include: **Approve** (accept as-is), **Approve with Edits** (correct fields and approve), **Request Re-synthesis** (send back to the LLM with notes), **Flag for Expert** (escalate to domain specialist), **Reject** (mark invalid with reason), and **Merge** (combine with an existing verified entity).

### 6.3 Batch Review Mode

For efficiency, reviewers can work in batch mode: the interface shows a scrollable list of entities for a given region and period, with map markers for all of them visible simultaneously. The reviewer can quickly scan the map for obvious placement errors (a Roman battle marker in South America), approve straightforward entities in bulk, and focus detailed attention on flagged or low-confidence entities. The batch view also highlights clusters of nearby entities that might be duplicates, making it easy to spot overlap the automated pipeline missed.

---

## 7. AI-Generated Location Data: Feasibility and Strategy

### 7.1 What Works Well

For the majority of historical entities, AI-generated coordinates (whether from LLM output or NLP-extracted place names geocoded against reference databases) are accurate enough to be useful. The key insight is that the AI does not need to be perfect — it needs to be good enough that a human reviewer's job is mostly confirmation rather than research.

| Entity Type | AI Accuracy | Notes |
|-------------|-------------|-------|
| Named cities and landmarks | **High** (within 1–5 km) | Well-documented in training data and geocoding databases. Rome, Constantinople, Chang'an are precisely locatable. |
| Major battle sites | **High to Medium** (within 5–20 km) | Famous battles are well-documented. Lesser-known engagements may be placed at the nearest known settlement. |
| Trade route waypoints | **Medium** (major nodes accurate, minor stops approximate) | The LLM and geocoders know the Silk Road's major cities. Caravanserais and minor waypoints are less reliable. |
| Resource extraction sites | **Medium to Low** | Major mines (Laurion silver mines, Spanish silver) are well-known. Minor sites require human expertise. |
| Obscure or contested locations | **Low** (may hallucinate plausible but incorrect coordinates) | The highest-risk category. Flagged for human review with "low" location confidence. |
| Political borders (polygons) | **Do not generate with AI** | Pull from OHM or existing historical GIS datasets. AI generates metadata only. |

### 7.2 The Geocoding-First Strategy

Rather than asking the LLM to generate coordinates from its training data, the preferred approach is to extract place names via NLP and resolve them against authoritative geocoding services. The pipeline document describes the five-level geocoding cascade: OHM Nominatim, Wikidata SPARQL, GeoNames, Pleiades (for the ancient world), and finally LLM disambiguation as a fallback. This produces coordinates grounded in reference databases rather than generated from the LLM's memory.

The LLM's role in location resolution is limited to **disambiguation**: when the geocoder returns multiple candidates (the "Alexandria problem"), the LLM reads the surrounding source context and selects the most appropriate match. This is a focused, cheap call rather than open-ended coordinate generation.

### 7.3 Expected Review Workload

Based on the accuracy estimates above, the expected review workload for location data breaks down approximately as follows:

- **70–80%** of entities for well-documented periods (Classical Mediterranean, Chinese dynasties, medieval Europe): locations are accurate enough to need only confirmation or minor adjustment
- **40–60%** of entities for less-documented periods or regions: locations need moderate correction or research
- **Polygon borders:** always sourced from OHM or imported datasets, not AI-generated. The reviewer verifies the metadata (who controlled it, when) rather than the geometry

The review interface is designed to make location correction fast: the reviewer sees the marker on the OHM base map at the correct time period and can immediately tell if the placement looks wrong. A drag-to-reposition takes seconds.

---

## 8. Data Model: Connecting Entities to the Map

### 8.1 Spatial and Rendering Fields

Each of the 30 entity types gains spatial and rendering metadata for map integration. These fields are added to the base entity record (the full field list is in [Entity Specification v2.1, Section 3](docs/entity_specification.md)):

| Field | Type | Purpose |
|-------|------|---------|
| `geom` | PostGIS geometry | The entity's spatial representation (point, line, polygon, multi-polygon) |
| `territory_geom` | PostGIS geometry | Nullable polygon extent for polities, linestrings for routes |
| `temporal_start` | text (EDTF) | When this entity begins existing or becomes active |
| `temporal_end` | text (EDTF) | When this entity ceases to exist or becomes inactive |
| `duration_type` | enum | `point`, `period`, `ongoing`, `uncertain` |
| `date_raw` | text | Original date text from source ("during the reign of Augustus") |
| `date_method` | enum | How date was resolved (`nlp_direct`, `llm_reign_resolution`, `era_table_lookup`, `human_assigned`, etc.) |
| `date_confidence` | enum | `high`, `medium`, `low`, `unresolved` |
| `verification_status` | enum | `pipeline_draft`, `auto_validated`, `needs_review`, `in_review`, `human_verified`, `expert_verified`, `flagged`, `rejected`, `merged` |
| `confidence` | enum | `high`, `medium`, `low`, `unresolved` |
| `location_confidence` | enum | `high`, `medium`, `low`, `unresolved` |
| `location_method` | enum | Which geocoder matched (`ohm_nominatim`, `wikidata`, `geonames`, `pleiades`, `llm_disambiguation`, `human_assigned`) |
| `source_citations` | JSONB | Array of `{source_id, page, quote, accessed_date, bucket_path}` |
| `embedding` | vector(1536) | pgvector embedding for semantic search and similarity |
| `display_priority` | integer | Controls rendering order and minimum zoom level for visibility |
| `icon_class` | enum | Visual category for map marker styling, derived from `entity_type` |

### 8.2 Embedding Strategy

Each entity receives a pgvector embedding generated from a concatenation of its key identifying information: entity type, name, temporal range, location name, and summary text. This supports five core use cases detailed in the companion pipeline document: semantic search, entity deduplication, related entity discovery, thematic clustering for period overviews, and cross-civilization pattern detection.

The thematic clustering capability is particularly relevant for the user experience: when a user navigates to a time period, the application can display an automatically generated overview summarizing the major themes of that era, derived from clustering entity embeddings and feeding each cluster to the LLM for summarization.

---

## 9. Technology Stack

| Component | Technology | Role |
|-----------|------------|------|
| **Map Renderer** | MapLibre GL JS (open source) | Client-side vector tile rendering, layer composition, drawing tools, interaction handling |
| **Base Map Tiles** | OpenHistoricalMap | Historical vector tiles with temporal metadata, served from OHM infrastructure |
| **Database** | PostgreSQL 16 + PostGIS 3.4 + pgvector | Spatial data, temporal queries, entity relationships, vector similarity search, full-text search |
| **Object Storage** | S3-compatible (MinIO or AWS S3 / Cloudflare R2) | Raw source documents, NLP outputs, LLM logs, exports, backups |
| **API Server** | Python (FastAPI) or Node.js (Express) | REST API serving GeoJSON, entity CRUD, review workflow, authentication |
| **Frontend Framework** | React or Vue.js | Time slider, review interface, search, entity panels, annotation tools |
| **Authentication** | Keycloak (self-hosted) or Auth0 | User management, reviewer roles, API keys, OAuth 2.0 |
| **AI Generation** | Anthropic Claude API / OpenAI API | Entity synthesis (Stage 6 of pipeline) with structured JSON output |
| **NLP Pipeline** | spaCy (`en_core_web_trf`) / Stanza / HeidelTime | Named entity recognition, temporal expression extraction, co-reference detection |
| **Geocoding** | Geopy + OHM Nominatim + Wikidata + GeoNames + Pleiades | Place name to coordinate resolution via cascading services |
| **Task Queue** | Celery (Python) or BullMQ (Node.js) | Pipeline orchestration, retry logic, batch processing |
| **Cache** | Redis | Tile metadata caching, session management, API response caching, rate limiting |
| **Search** | PostgreSQL full-text + trigram + pgvector | Keyword search, fuzzy matching, and semantic similarity search combined |

### 9.1 Key Technology Rationale

**MapLibre GL JS** is the open-source fork of Mapbox GL JS. It is the only production-grade web map renderer that supports OHM's vector tiles with temporal filtering, custom GeoJSON overlays, and drawing tools via plugins — all with zero licensing cost.

**PostgreSQL + PostGIS + pgvector** provides spatial queries, temporal indexing, vector similarity search, full-text search, and JSONB document storage in a single database. This eliminates the need for separate systems for geographic data, vector search, and structured queries. The three extensions compose naturally: you can write a single query that finds entities spatially near a point, temporally within a range, and semantically similar to a description.

**Two-tier storage (PostgreSQL + S3)** separates structured queryable data (entity records, summaries, embeddings, annotations, citations) from archival files (raw source PDFs, NLP extraction JSON, LLM logs). Entity records in PostgreSQL reference object storage files via URLs, with signed URL generation for secure access.

---

## 10. Cost Analysis: Why Not ArcGIS

### 10.1 ArcGIS Online Pricing Summary

ArcGIS Online uses per-user annual licensing plus a credit system for storage and computation. For context, 1,000 credits cost \$100, and feature storage alone consumes 2.4 credits per 10 MB stored per month.

| Item | ArcGIS Online Cost | Open Stack Equivalent |
|------|--------------------|-----------------------|
| Editor license (Creator) | \$845/user/year | \$0 (custom app) |
| Viewer license | \$100/user/year | \$0 (custom app) |
| Feature storage (10 MB/month) | 2.4 credits (\$0.24/month) | \$0 (PostGIS on own server) |
| 1,000 additional credits | \$100 | N/A |
| Premium Feature Data Store | \$2,400–\$24,000/year | \$20–\$100/month (managed PostgreSQL) |
| Geocoding (1,000 addresses) | 40 credits (\$4) | \$0 (Nominatim/Photon self-hosted) |
| Spatial analysis | Credits per operation | \$0 (PostGIS) |
| Historical base maps | **Not available** | \$0 (OHM) |

### 10.2 Projected Annual Cost Comparison

For a team of 5 editors, 20 viewers, and approximately 50 GB of feature data:

| Category | ArcGIS Online | Open Stack |
|----------|---------------|------------|
| Editor licenses | \$4,225 (5 × \$845) | \$0 |
| Viewer licenses | \$2,000 (20 × \$100) | \$0 |
| Feature storage (50 GB) | ~\$2,880/year in credits | \$0 (included in server) |
| Analysis credits | \$500–\$2,000 | \$0 (PostGIS) |
| Server infrastructure | \$0 (included in SaaS) | \$1,200–\$2,400 |
| Domain + SSL | \$0 (included) | \$50–\$100 |
| **TOTAL** | **\$9,605–\$11,105/year** | **\$1,250–\$2,500/year** |

### 10.3 Functional Mismatch

Beyond cost, ArcGIS is architecturally unsuited for this project:

- **No native time slider for historical data.** ArcGIS basemaps show the modern world only. OHM's vector tiles are purpose-built for temporal filtering.
- **No historical base map layer.** The most fundamental requirement of this project — showing the world as it was at a given date — is not an ArcGIS capability.
- **Data model limitations.** ArcGIS does not natively support confidence levels, competing interpretations, source citations with resolution chains, or EDTF date formats as first-class fields.
- **Review workflow mismatch.** ArcGIS editing tools are designed for utility workers and surveyors, not historical researchers reviewing AI-generated data with inline source checking.
- **No embedding/semantic search.** ArcGIS has no equivalent to pgvector for semantic similarity search, thematic clustering, or cross-civilization pattern detection.

---

## 11. API Design

### 11.1 Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/entities?bbox=W,S,E,N&time=T&types=...` | Fetch entities within bounding box at time T, filtered by type. Returns GeoJSON FeatureCollection. |
| `GET` | `/api/entities/:id` | Full entity details: all fields, relationships, source citations, revision history. |
| `POST` | `/api/entities` | Create a new entity (pipeline insertion or manual entry). |
| `PATCH` | `/api/entities/:id` | Update entity fields (review interface corrections). |
| `GET` | `/api/entities/:id/similar` | pgvector nearest-neighbor query returning semantically similar entities. |
| `GET` | `/api/entities/:id/history` | Audit trail of all changes to this entity. |
| `GET` | `/api/annotations?bbox=W,S,E,N&layer=...` | Fetch annotations within bounding box, filtered by layer group. |
| `POST` | `/api/annotations` | Create annotation (bezier, label, arrow, overlay). |
| `PATCH` | `/api/annotations/:id` | Edit annotation geometry or style. |
| `GET` | `/api/review/queue?region=...&period=...` | Entities pending review, filterable by region and time period. |
| `POST` | `/api/review/:id/approve` | Mark entity as `human_verified` with reviewer metadata. |
| `POST` | `/api/review/:id/reject` | Reject entity with reason (fed back to improve pipeline). |
| `GET` | `/api/search?q=...&time_start=...&time_end=...` | Combined keyword + semantic search with temporal and spatial filtering. |
| `GET` | `/api/overview?region=...&time=...` | Thematic cluster overview for a region/period (embedding-based). |

### 11.2 Response Format

All spatial endpoints return standard GeoJSON FeatureCollections. Each feature includes the entity's geometry plus essential properties (type, name, temporal range, verification status, display priority). Full details including relationships, citations, and revision history are available via the individual entity endpoint, keeping collection responses lightweight for map rendering.

The `/api/overview` endpoint returns a structured object with thematic clusters, each containing a cluster label, an LLM-generated summary, member entity IDs, and a representative centroid coordinate for map placement. This powers the period overview feature described in [Section 1.2](#12-what-users-will-experience).

---

## 12. Frontend Architecture

### 12.1 Core UI Components

- **Map viewport:** Full-screen MapLibre GL JS instance composing all three layers with zoom, pan, and rotation controls
- **Time slider:** Horizontal slider from 4000 BCE to present, with play/pause animation, speed control, and snap-to-century/decade modes
- **Entity panel:** Slide-out panel showing entity details when a marker is clicked, with tabs for attributes, relationships, sources, similar entities, and revision history
- **Search bar:** Combined keyword and semantic search with temporal and spatial filtering, autocomplete against entity names and alternative names
- **Review dashboard:** Queue of entities pending review with filters for region, period, entity type, and validation status. Includes batch review mode.
- **Annotation toolbar:** Drawing tools for bezier curves (with control point editing), text labels, directional arrows, and freeform polygons
- **Layer controls:** Toggles for entity type visibility, annotation layer groups, base map styles (Historical, Woodblock, Satellite), and confidence level filtering
- **Period overview:** Automatically generated thematic summary displayed when navigating to a new time period, powered by embedding clusters

### 12.2 Map Interaction Model

The map loads OHM tiles as the base layer and applies temporal filtering based on the time slider position. Entity data is fetched from the API as GeoJSON for the visible bounding box and current time. When the user pans or zooms, new entity data is requested. When the time slider moves, both the OHM tile filter and the entity API query update simultaneously.

Clicking an entity marker opens the detail panel. In review mode, clicking switches to an edit form with drag-to-reposition enabled for point entities and vertex editing for polygons. The annotation toolbar activates drawing mode where clicks create control points for beziers or vertices for polygons, with real-time rendering of the shape as it's drawn.

The "Similar entities" tab in the entity panel triggers a pgvector nearest-neighbor query, displaying results as a list with similarity scores and as highlighted markers on the map, enabling visual exploration of thematic connections across time and space.

---

## 13. Deployment and Infrastructure

### 13.1 Minimum Viable Deployment

The entire application can run on a single server for development and early production:

| Component | Specification | Estimated Monthly Cost |
|-----------|--------------|------------------------|
| VPS (API + Database + Redis) | 4 vCPU, 16 GB RAM, 200 GB SSD | \$40–\$80 |
| Domain + SSL | Custom domain + Let's Encrypt | \$1 (domain only, amortized) |
| Object storage | MinIO on same server, or Cloudflare R2 | \$0–\$5 |
| OHM tiles | Consumed from OHM's servers | \$0 |
| CDN | Cloudflare free tier for static assets | \$0 |
| **TOTAL** | | **\$41–\$86/month** |

### 13.2 Scaled Deployment

As data volume and user count grow:

- **Database:** Migrate to managed PostgreSQL (AWS RDS, Supabase, or Neon) with PostGIS and pgvector extensions, plus read replicas for map queries
- **API:** Containerize with Docker, deploy behind a load balancer with horizontal scaling
- **Cache:** Dedicated Redis instance for entity data caching, session management, and rate limiting
- **Search:** Add Meilisearch or Elasticsearch if PostgreSQL full-text search becomes insufficient at scale
- **AI pipeline:** Run on separate worker instances (or serverless functions) to avoid impacting API performance
- **Object storage:** Move to managed S3 with lifecycle policies for archival tiering

---

## 14. Development Roadmap

### Phase 1: Foundation (Months 1–3)

- Set up PostgreSQL + PostGIS + pgvector with the core entity schema
- Build a minimal MapLibre frontend loading OHM vector tiles with a working time slider
- Implement the GeoJSON API serving entities from PostGIS within bounding box and time range
- Create the entity detail panel (click marker, view data, see sources)
- Run the NLP + geocoding + LLM pipeline on a seed batch: Classical Mediterranean, 200 BCE–200 CE
- Generate initial embeddings and validate semantic search

### Phase 2: Review Pipeline (Months 4–6)

- Build the review dashboard with queue management, filters, and batch mode
- Implement the split-view review interface with drag-to-reposition and inline source viewing
- Add the verification status workflow with audit trail
- Implement user authentication and role-based access (admin, reviewer, viewer)
- Begin systematic human review of the seed dataset
- Track review metrics and refine AI generation prompts based on rejection patterns

### Phase 3: Annotations and Relationships (Months 7–9)

- Implement the annotation layer: bezier drawing tool, text labels, directional arrows, freeform polygons
- Build relationship visualization between entities on the map
- Add the remaining entity types from the 30-entity specification
- Implement combined keyword + semantic search with temporal filtering
- Build the period overview feature using embedding cluster summarization
- Expand the dataset to additional time periods and regions

### Phase 4: Analysis and Scale (Months 10–12)

- Build the analytical query interface for the 48 predefined queries from the database specification
- Add comparative visualization tools (side-by-side entity comparison, parallel timelines)
- Implement data export in standard formats (GeoJSON, CSV, Shapefile, GeoPackage)
- Performance optimization: query tuning, spatial index optimization, client-side data management, tile caching
- Deploy public API with documentation for external researchers

### Phase 5: Community and Expansion (Year 2+)

- Open contributor registration with structured onboarding and quality gates
- Deepen integration with Wikidata and other linked open data sources
- Build advanced analytical tools: pattern detection, network analysis, influence mapping, resource flow modeling
- Contribute verified geographic corrections back to OpenHistoricalMap
- Mobile-responsive interface for field research and presentation use
- Multilingual support for entity data and the user interface

---

## 15. Open Questions and Future Considerations

### 15.1 OHM Coverage and Contribution

OpenHistoricalMap coverage varies significantly by region and period. For the project's initial focus on the Classical Mediterranean, coverage is relatively strong. For other regions (sub-Saharan Africa, pre-Columbian Americas, Central Asia), coverage may be sparse. The project should identify coverage gaps early and consider organized contribution campaigns to OHM for focus regions, which benefits both projects.

### 15.2 Conflicting Historical Interpretations

The database design supports multiple interpretations and confidence levels. The map interface needs a way to expose this visually. Options include:

- Toggling between "consensus view" (showing the most confident interpretation) and "contested view" (showing all interpretations with visual differentiation)
- Displaying contested borders as dashed or gradient-filled lines
- Including an "interpretation notes" section in the entity detail panel

### 15.3 Embedding Model Selection

The choice of embedding model affects the quality of semantic search, entity deduplication, and thematic clustering. Historical text has unique characteristics (archaic terminology, specialized vocabulary, cross-cultural concepts) that general-purpose embedding models may not capture well. Testing with historical corpora is needed to evaluate whether a general model (OpenAI `text-embedding-3-large`, `nomic-embed-text`) is sufficient or whether fine-tuning on historical text improves results meaningfully.

### 15.4 Scale of AI Generation

Generating entities for all of human history across all regions is an enormous task. The phased approach (starting with well-documented periods where AI accuracy can be validated against known reference data) is essential. Metrics from early review rounds — particularly the geocoding accuracy rate, date resolution accuracy, and LLM summary quality — will inform how aggressively to scale AI generation and which regions to prioritize next.

### 15.5 Offline and Export Use Cases

Researchers may want to work with the data offline or export subsets for publication. The API should support bulk export with temporal, spatial, and entity-type filtering. Export formats should include GeoJSON (for web mapping), Shapefile and GeoPackage (for desktop GIS), CSV (for spreadsheet analysis), and potentially RDF/Linked Data (for integration with academic knowledge graphs).

### 15.6 Long-Term Sustainability

The project's reliance on open infrastructure means no single vendor can force a migration or price increase. However, long-term sustainability depends on:

- Building a community of contributors (both for data verification and code maintenance)
- Securing hosting funding (the infrastructure costs are modest but nonzero)
- Establishing the project's academic credibility to attract domain expert reviewers

---

## Related Documents

| Document | Description |
|----------|-------------|
| [Entity Specification v2.1](docs/entity_specification.md) | 30 entity types, 5 entity groups, all enums, type-specific fields, JSONB schemas |
| [Game-Inspired UI/UX Design Guide](docs/game_inspired_ui_ux.md) | Civ VI and Total War: Rome II patterns applied to the Historical Atlas frontend |
| [Reference Tables](docs/reference_tables.md) | Historical periods, geographic regions, calendar systems, writing systems, and other lookup data |
