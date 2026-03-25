# Historical Atlas — Entity Specification v2.1

> **Companion to:** Data Pipeline Architecture, Foundational Architecture Document, Game-Inspired UI/UX Design Guide
> **Storage context:** PostgreSQL (PostGIS + pgvector) for structured/queryable data, S3-compatible object storage for raw files and logs.
> **Changes from v1.0:** Merged Economic/Trade Good into Natural Resource. Demoted Historical Period/Era and Historiographical School to reference tables (see `reference_tables.md`). Added Infrastructure/Monument, Diplomatic Relationship/Alliance, and Epidemic/Disease as new first-class entities.
> **Changes from v2.0:** Consolidated entity groups from 10 to 5. Eliminated singleton groups (PERSON, MILITARY, BELIEF) and the catch-all SOCIETY group. Absorbed KNOWLEDGE into CULTURE and PLACE. See Section 1 rationale.

---

## Table of Contents

1. [Entity Groups and Type Hierarchy](#1-entity-groups-and-type-hierarchy)
2. [Application-Wide Enums](#2-application-wide-enums)
3. [Shared Base Fields (All Entities)](#3-shared-base-fields-all-entities)
4. [Entity Specifications (1–30)](#4-entity-specifications)
5. [Meta-Entity: Source](#5-meta-entity-source)
6. [Relationship Types](#6-relationship-types)
7. [Storage Split: PostgreSQL vs S3](#7-storage-split)

---

## 1. Entity Groups and Type Hierarchy

Every entity belongs to one of **5 groups**. Groups exist for UI navigation (tab filtering, icon families, color palettes), API query scoping, and map lens organization. Each group contains 3–9 concrete `entity_type` values.

```
entity_group (enum)          entity_type (enum)                                     count
─────────────────────────────────────────────────────────────────────────────────────────
POLITY                       political_entity, dynasty, person, military_unit,
                             diplomatic_relationship, social_class                      6
PLACE                        city, infrastructure_monument, extraction_infra,
                             educational_institution                                    4
EVENT                        event_war, event_battle, event_treaty,
                             event_rebellion, event_natural_disaster,
                             event_tech_adoption, event_legal_reform,
                             migration, epidemic_disease                                9
ECONOMY                      trade_route, natural_resource,
                             currency_monetary_system                                   3
CULTURE                      cultural_work, intellectual_movement,
                             archaeological_culture, language,
                             religious_text, legal_code, religious_movement,
                             technology                                                 8
─────────────────────────────────────────────────────────────────────────────────────────
                                                                          TOTAL:       30
```

> **v2.1 consolidation rationale:**
> - **PERSON → POLITY:** Persons are political actors (rulers, generals, diplomats). Singleton group provided no navigational benefit; players in Civ VI and Total War access characters through faction context.
> - **MILITARY → POLITY:** Military units are instruments of political entities (`part_of` → Political Entity). In Rome II, armies belong to factions.
> - **SOCIETY → split:** This was a catch-all. Diplomatic relationships and social classes belong with POLITY (power structures). Migration and epidemics are temporal occurrences that belong with EVENT.
> - **BELIEF → CULTURE:** Religious movements are cultural phenomena. `religious_text` was already in CULTURE. No reason to separate belief from other intellectual/cultural movements.
> - **KNOWLEDGE → split:** Educational institutions are physical places (Library of Alexandria, Al-Azhar). Technology is cultural innovation, alongside artistic/intellectual movements.
> - **extraction_infra → PLACE:** Mines, quarries, and farms are physical map features with precise coordinates, rendering like cities and monuments.
>
> **Note:** `event_battle` was split from `event_war` because battles are point-events with precise coordinates, while wars are period-events spanning large areas. They have different spatial and temporal rendering on the map.

---

## 2. Application-Wide Enums

All enums are stored as PostgreSQL `enum` types or as `text` with CHECK constraints. Grouped below by domain.

### 2.1 Core System Enums

```sql
-- The two top-level classifiers (5 groups, 30 types)
CREATE TYPE entity_group AS ENUM (
  'POLITY', 'PLACE', 'EVENT', 'ECONOMY', 'CULTURE'
);

CREATE TYPE entity_type AS ENUM (
  -- POLITY (political actors, power structures, and their instruments)
  'political_entity', 'dynasty', 'person', 'military_unit',
  'diplomatic_relationship', 'social_class',
  -- PLACE (physical locations and structures on the map)
  'city', 'infrastructure_monument', 'extraction_infra',
  'educational_institution',
  -- EVENT (temporal occurrences: conflicts, disasters, movements)
  'event_war', 'event_battle', 'event_treaty', 'event_rebellion',
  'event_natural_disaster', 'event_tech_adoption', 'event_legal_reform',
  'migration', 'epidemic_disease',
  -- ECONOMY (trade networks, resources, and monetary systems)
  'trade_route', 'natural_resource', 'currency_monetary_system',
  -- CULTURE (ideas, beliefs, knowledge, and creative output)
  'cultural_work', 'intellectual_movement', 'archaeological_culture',
  'language', 'religious_text', 'legal_code', 'religious_movement',
  'technology'
);
```

### 2.2 Verification and Confidence Enums

```sql
CREATE TYPE verification_status AS ENUM (
  'pipeline_draft',        -- Created by pipeline, not yet validated
  'auto_validated',        -- Passed Stage 7 automated checks
  'needs_review',          -- In human review queue
  'in_review',             -- Currently assigned to a reviewer
  'human_verified',        -- Approved by reviewer
  'expert_verified',       -- Approved by domain expert
  'flagged',               -- Flagged for re-examination
  'rejected',              -- Rejected as invalid/duplicate
  'merged'                 -- Merged into another entity
);

CREATE TYPE confidence_level AS ENUM (
  'high',                  -- Strong evidence, multiple corroborating sources
  'medium',                -- Reasonable evidence, some ambiguity
  'low',                   -- Weak evidence, significant uncertainty
  'unresolved'             -- Insufficient data to assess
);

CREATE TYPE reliability_tier AS ENUM (
  'authoritative',         -- Primary sources, peer-reviewed archaeology
  'scholarly',             -- Academic secondary sources, university press
  'reference',             -- Encyclopedias, well-curated databases (e.g., Pleiades)
  'user_contributed'       -- Community submissions, Wikipedia, blogs
);
```

### 2.3 Temporal Enums

```sql
CREATE TYPE date_resolution_method AS ENUM (
  'nlp_direct',            -- Tier 1: explicit date extracted by NLP
  'nlp_approximate',       -- Tier 2: partial/approximate date via NLP
  'llm_reign_resolution',  -- Tier 3: relative date resolved by LLM
  'era_table_lookup',      -- Tier 4: era-relative resolved via reference table
  'llm_contextual_inference', -- Tier 5: inferred from co-occurring entities
  'human_assigned',        -- Tier 6 or override: assigned by human reviewer
  'source_database'        -- Imported from structured database (Pleiades, Wikidata)
);

CREATE TYPE duration_type AS ENUM (
  'point',                 -- Instantaneous event (battle, treaty signing)
  'period',                -- Bounded time range (war, reign, construction)
  'ongoing',               -- No defined end (living language, active city)
  'uncertain'              -- Duration not determinable from sources
);
```

### 2.4 Spatial Enums

```sql
CREATE TYPE location_resolution_method AS ENUM (
  'ohm_nominatim',         -- OpenHistoricalMap geocoder
  'ohm_overpass',          -- OpenHistoricalMap Overpass element/relation query
  'ohm_rest_api',          -- OpenHistoricalMap REST API lookup by element ID
  'wikidata',              -- Wikidata SPARQL coordinates
  'geonames',              -- GeoNames database
  'pleiades',              -- Pleiades ancient places gazetteer
  'llm_disambiguation',    -- LLM selected from candidate locations
  'human_assigned',        -- Reviewer placed manually
  'source_database'        -- Coordinates from structured import
);

CREATE TYPE geometry_type AS ENUM (
  'point',                 -- Single location (city, battle site, monument)
  'polygon',               -- Territory (empire borders, region extent)
  'linestring',            -- Route (trade route, migration path, river)
  'multipoint',            -- Multiple associated locations (archipelago, mine cluster)
  'multipolygon'           -- Discontinuous territory (island empire, split state)
);
```

### 2.5 Political and Governance Enums

```sql
CREATE TYPE political_entity_subtype AS ENUM (
  'empire', 'kingdom', 'republic', 'city_state', 'tribal_confederation',
  'theocracy', 'principality', 'duchy', 'khanate', 'sultanate',
  'caliphate', 'shogunate', 'confederation', 'league', 'colonial_territory',
  'protectorate', 'vassal_state', 'free_city', 'nomadic_polity', 'other'
);

CREATE TYPE government_type AS ENUM (
  'absolute_monarchy', 'constitutional_monarchy', 'elective_monarchy',
  'oligarchy', 'aristocratic_republic', 'democratic_republic',
  'theocracy', 'military_dictatorship', 'tribal_chieftainship',
  'feudal', 'bureaucratic_centralized', 'colonial_administration',
  'communist_state', 'fascist_state', 'anarchy', 'diarchy',
  'federal', 'confederal', 'other'
);

CREATE TYPE succession_type AS ENUM (
  'primogeniture', 'ultimogeniture', 'elective', 'tanistry',
  'agnatic', 'cognatic', 'appointed', 'meritocratic',
  'military_acclamation', 'divine_selection', 'rotation',
  'other', 'unknown'
);
```

### 2.6 Military Enums

```sql
CREATE TYPE military_unit_subtype AS ENUM (
  'infantry', 'cavalry', 'navy', 'archer_ranged', 'siege',
  'chariot', 'elephant_corps', 'garrison', 'mercenary_company',
  'legion', 'phalanx', 'warband', 'fleet', 'air_force',
  'special_forces', 'militia', 'guard', 'other'
);

CREATE TYPE military_composition AS ENUM (
  'professional', 'conscript', 'mercenary', 'tribal_warrior',
  'slave_soldier', 'feudal_levy', 'volunteer', 'mixed', 'unknown'
);
```

### 2.7 Place and Infrastructure Enums

```sql
CREATE TYPE settlement_subtype AS ENUM (
  'capital_city', 'major_city', 'minor_city', 'town', 'village',
  'fortress', 'port', 'religious_center', 'trade_hub',
  'administrative_center', 'mining_town', 'oasis', 'colony',
  'garrison_town', 'abandoned', 'other'
);

CREATE TYPE monument_subtype AS ENUM (
  -- Civic / Public
  'palace', 'forum', 'amphitheater', 'theater', 'bath_complex',
  'library', 'market_agora', 'government_building',
  -- Religious
  'temple', 'cathedral', 'mosque', 'monastery', 'shrine', 'pyramid',
  'megalithic_structure', 'sacred_grove',
  -- Military / Defensive
  'fortification', 'wall', 'castle', 'citadel', 'watchtower',
  -- Infrastructure
  'aqueduct', 'canal', 'bridge', 'road_section', 'harbor', 'lighthouse',
  'dam', 'granary', 'sewer_system',
  -- Monumental / Memorial
  'triumphal_arch', 'obelisk', 'mausoleum', 'tomb', 'statue',
  'memorial', 'stele',
  -- Other
  'other'
);
```

### 2.8 Economy and Resource Enums

```sql
CREATE TYPE resource_category AS ENUM (
  'grain', 'livestock', 'cash_crop', 'timber', 'metal_precious',
  'metal_strategic', 'metal_base', 'stone_building', 'gemstone',
  'salt', 'spice', 'textile_raw', 'dye', 'incense_perfume',
  'fuel', 'water', 'fish_seafood', 'animal_strategic',
  'animal_luxury', 'medicinal', 'other'
);

CREATE TYPE resource_renewability AS ENUM (
  'renewable', 'finite', 'cyclical', 'unknown'
);

CREATE TYPE resource_strategic_value AS ENUM (
  'critical', 'high', 'medium', 'low', 'negligible', 'unknown'
);

CREATE TYPE extraction_infra_subtype AS ENUM (
  'mine', 'quarry', 'farm', 'plantation', 'ranch', 'fishery',
  'forest_logging', 'hunting_ground', 'well_spring', 'salt_works',
  'workshop', 'shipyard', 'smithy_foundry', 'irrigation_system',
  'mill', 'vineyard', 'kiln', 'other'
);

CREATE TYPE trade_route_subtype AS ENUM (
  'overland', 'maritime', 'riverine', 'mixed',
  'pilgrimage', 'military_supply', 'other'
);

CREATE TYPE currency_type AS ENUM (
  'coin_metal', 'paper', 'commodity_money', 'shell_bead',
  'barter_system', 'credit_system', 'other'
);
```

### 2.9 Event Enums

```sql
CREATE TYPE war_subtype AS ENUM (
  'interstate_war', 'civil_war', 'colonial_war', 'religious_war',
  'succession_war', 'trade_war', 'border_conflict', 'raid_series',
  'invasion', 'siege_campaign', 'naval_war', 'tribal_war', 'other'
);

CREATE TYPE battle_subtype AS ENUM (
  'pitched_battle', 'siege', 'naval_battle', 'ambush',
  'skirmish', 'raid', 'last_stand', 'other'
);

CREATE TYPE battle_outcome AS ENUM (
  'decisive_victory', 'tactical_victory', 'pyrrhic_victory',
  'draw', 'tactical_defeat', 'decisive_defeat', 'inconclusive',
  'unknown'
);

CREATE TYPE treaty_subtype AS ENUM (
  'peace_treaty', 'alliance_treaty', 'trade_agreement',
  'marriage_alliance', 'tribute_agreement', 'border_demarcation',
  'non_aggression_pact', 'surrender', 'ceasefire',
  'mutual_defense', 'vassalage_agreement', 'other'
);

CREATE TYPE rebellion_subtype AS ENUM (
  'revolution', 'rebellion', 'coup', 'civil_war',
  'peasant_uprising', 'slave_revolt', 'military_mutiny',
  'separatist_movement', 'religious_uprising', 'other'
);

CREATE TYPE disaster_subtype AS ENUM (
  'earthquake', 'volcanic_eruption', 'flood', 'tsunami',
  'drought', 'famine', 'wildfire', 'hurricane_typhoon',
  'landslide', 'climate_shift', 'other'
);

CREATE TYPE reform_subtype AS ENUM (
  'legal_code', 'constitutional_change', 'administrative_reorganization',
  'land_reform', 'taxation_reform', 'military_reform',
  'religious_reform', 'educational_reform', 'economic_reform',
  'abolition', 'enfranchisement', 'other'
);
```

### 2.10 Society Enums

```sql
CREATE TYPE epidemic_subtype AS ENUM (
  'plague_bacterial', 'plague_viral', 'smallpox', 'cholera',
  'malaria', 'typhus', 'influenza', 'tuberculosis', 'leprosy',
  'dysentery', 'measles', 'unknown_pestilence', 'other'
);

CREATE TYPE epidemic_severity AS ENUM (
  'local',                 -- Confined to one city/region
  'regional',              -- Multiple provinces/regions
  'pandemic',              -- Continent-scale or beyond
  'unknown'
);

CREATE TYPE diplomatic_status AS ENUM (
  'alliance', 'defensive_pact', 'trade_agreement', 'vassalage',
  'tributary', 'protectorate', 'personal_union', 'federation_member',
  'non_aggression', 'neutrality', 'war', 'cold_war',
  'embargo', 'occupation', 'other'
);

CREATE TYPE migration_subtype AS ENUM (
  'invasion', 'colonization', 'forced_deportation', 'refugee_flight',
  'economic_migration', 'nomadic_movement', 'pilgrimage_settlement',
  'slave_trade', 'diaspora', 'other'
);

CREATE TYPE social_class_subtype AS ENUM (
  'royalty', 'nobility', 'clergy', 'warrior_class', 'merchant_class',
  'artisan_class', 'peasantry', 'serf', 'slave', 'freedman',
  'bureaucrat_literati', 'nomad_pastoral', 'outcast_untouchable',
  'intelligentsia', 'bourgeoisie', 'proletariat', 'other'
);
```

### 2.11 Culture and Knowledge Enums

```sql
CREATE TYPE cultural_work_subtype AS ENUM (
  'literary_text', 'philosophical_text', 'historical_text',
  'religious_text', 'scientific_text', 'legal_text',
  'building_architecture', 'sculpture', 'painting_mural',
  'mosaic', 'pottery_ceramics', 'textile', 'metalwork',
  'musical_composition', 'inscription', 'coin_design',
  'map_cartography', 'other'
);

CREATE TYPE language_status AS ENUM (
  'living', 'extinct', 'liturgical_only', 'reconstructed',
  'endangered', 'revived', 'unknown'
);

CREATE TYPE language_role AS ENUM (
  'vernacular', 'lingua_franca', 'administrative',
  'liturgical', 'literary', 'trade_language', 'court_language',
  'scholarly', 'other'
);

CREATE TYPE technology_domain AS ENUM (
  'military', 'agricultural', 'industrial', 'construction',
  'navigation', 'communication', 'medical', 'metallurgical',
  'textile', 'writing_printing', 'astronomical', 'hydraulic',
  'transportation', 'food_preservation', 'other'
);

CREATE TYPE intellectual_movement_subtype AS ENUM (
  'philosophical_school', 'artistic_style', 'literary_movement',
  'scientific_paradigm', 'legal_tradition', 'educational_tradition',
  'historiographical', 'other'
);

CREATE TYPE religious_movement_subtype AS ENUM (
  'monotheism', 'polytheism', 'animism', 'ancestor_worship',
  'philosophical_religion', 'mystery_cult', 'syncretic',
  'sect_denomination', 'heretical_movement', 'reform_movement',
  'missionary_movement', 'monastic_order', 'other'
);
```

### 2.12 Person Enums

```sql
CREATE TYPE person_role AS ENUM (
  'ruler', 'regent', 'heir', 'consort', 'general', 'admiral',
  'diplomat', 'governor', 'religious_leader', 'prophet',
  'philosopher', 'scientist', 'artist', 'architect', 'poet',
  'historian', 'lawgiver', 'rebel_leader', 'merchant',
  'explorer', 'spy', 'slave', 'other'
);

CREATE TYPE gender AS ENUM (
  'male', 'female', 'other', 'unknown'
);
```

### 2.13 Relationship Enums

```sql
CREATE TYPE relationship_type AS ENUM (
  -- Political
  'rules', 'governed_by', 'vassal_of', 'suzerain_of',
  'allied_with', 'at_war_with', 'succeeded_by', 'preceded_by',
  'part_of', 'contains', 'capital_of', 'split_from', 'merged_into',

  -- Person
  'born_in', 'died_in', 'resided_in', 'commanded', 'founded',
  'authored', 'commissioned', 'married_to', 'parent_of', 'child_of',
  'sibling_of', 'mentor_of', 'student_of', 'assassinated_by',
  'member_of_dynasty', 'patron_of',

  -- Military
  'participated_in', 'fought_at', 'defeated_at', 'victorious_at',
  'stationed_at', 'recruited_from', 'commanded_by',

  -- Economic
  'trades_with', 'connects', 'produces', 'extracts',
  'supplies', 'controlled_by', 'passes_through',
  'minted_by', 'used_currency',

  -- Religious/Cultural
  'adheres_to', 'official_religion_of', 'persecuted_by',
  'influenced_by', 'inspired', 'schism_from',
  'translated_into', 'located_at', 'built_by',
  'destroyed_by', 'restored_by',

  -- Causal
  'caused', 'resulted_from', 'contributed_to', 'enabled',
  'prevented', 'weakened', 'strengthened',

  -- Knowledge
  'invented', 'adopted', 'taught_at', 'spread_to',
  'required_by', 'replaced_by',

  -- Diplomatic
  'signed_by', 'violated_by', 'guaranteed_by',
  'mediated_by', 'enforced_by'
);
```

### 2.14 Display and Rendering Enums

```sql
CREATE TYPE icon_class AS ENUM (
  'crown', 'person', 'dynasty_tree', 'sword', 'city', 'monument',
  'trade_ship', 'gem', 'pickaxe', 'coin', 'people', 'migration_arrow',
  'plague', 'handshake', 'scroll', 'palette', 'ruins', 'language_glyph',
  'sacred_book', 'scales', 'crossed_swords', 'shield', 'treaty_seal',
  'fist', 'earthquake', 'gear', 'quill', 'temple', 'lightbulb',
  'university'
);

-- Maps entity_group → color palette for map rendering (5 groups)
-- Defined in frontend config, not SQL, but documented here:
-- POLITY:  #1A3A5C (navy)    — authority, governance, power
-- PLACE:   #2E86C1 (blue)    — geographic, spatial, physical
-- EVENT:   #C0392B (red)     — action, conflict, change
-- ECONOMY: #D68910 (amber)   — trade, wealth, resources
-- CULTURE: #8E44AD (purple)  — ideas, beliefs, art, knowledge
```

---

## 3. Shared Base Fields (All Entities)

Every entity in PostgreSQL shares these columns. Type-specific fields are stored in the JSONB `attributes` column (see Section 4). Time-varying geometries use a dedicated `geometry_snapshots` sub-table (see `plans/attributes_and_geometry_snapshots.md`).

| Field | Type | Storage | Source | Notes |
|-------|------|---------|--------|-------|
| `entity_id` | UUID | PG (PK) | Generated at Stage 6 | |
| `entity_type` | enum | PG (indexed) | LLM classification | One of 30 values |
| `entity_group` | enum | PG (indexed) | Derived from entity_type | Computed, not stored separately if using lookup |
| `name` | text | PG (indexed, tsvector) | NLP + LLM canonical form | Full-text searchable |
| `alternative_names` | text[] | PG | NLP extraction from all sources | |
| `wikidata_id` | text | PG (indexed) | Geocoding cascade | Nullable; stable cross-reference |
| `primary_geo_ref_id` | UUID (FK) | PG (indexed) | Stage 3 georesolution | Active row in `entity_geo_refs`; nullable |
| `geom` | geometry | PG + PostGIS (GIST index) | Geocoding at Stage 3 | Point, Polygon, LineString, etc. |
| `territory_geom` | geometry | PG + PostGIS | Manual / LLM / import | Nullable; polygon extent for polities |
| `location_name` | text | PG | Geocoding cascade | Human-readable |
| `location_confidence` | enum | PG | Geocoding confidence | high/medium/low/unresolved |
| `location_method` | enum | PG | Which geocoder matched | |
| `geo_resolution_status` | text | PG | Stage 3 georesolution | `matched_ohm`, `matched_fallback`, `empty_geom` |
| `temporal_start` | text | PG (indexed) | NLP Stage 4 | Integer year as string; negative = BCE (e.g. `"-500"`, `"1453"`) |
| `temporal_end` | text | PG (indexed) | NLP Stage 4 | Same format as `temporal_start` |
| `date_raw` | text | PG | Original source text | |
| `date_method` | enum | PG | Resolution method | |
| `date_confidence` | enum | PG | Stage 4 assessment | |
| `duration_type` | enum | PG | LLM classification | point/period/ongoing/uncertain |
| `summary` | text | PG | LLM synthesis at Stage 6 | 500–3000 chars typical |
| `significance` | text | PG | LLM assessment | |
| `confidence_notes` | text | PG | LLM-identified uncertainties | |
| `tags` | text[] | PG (GIN index) | LLM + human tagging | Freeform categorical tags |
| `impact_score` | integer | PG (B-tree index `DESC NULLS LAST`; composite index with `entity_type`) | LLM + editorial | 1–100 scale |
| `parent_entity_id` | UUID (FK) | PG (indexed) | LLM / human | Nullable; hierarchical link |
| `successor_entity_id` | UUID (FK) | PG (indexed) | LLM / human | Nullable; continuity link |
| `verification_status` | enum | PG (indexed) | Pipeline tracking | |
| `confidence` | enum | PG | Combined assessment | |
| `reviewer_id` | UUID (FK) | PG | Stage 8 | Nullable |
| `review_date` | timestamp | PG | Stage 8 | Nullable |
| `validation_flags` | text[] | PG | Stage 7 results | |
| `source_citations` | JSONB | PG | Accumulated Stages 1–6 | `[{document_id, page, quote, bucket_path}]` |
| `media_refs` | JSONB | PG | Manual / import | `[{type, url, caption, date}]`, files in S3 |
| `embedding` | vector(1536) | PG + pgvector (HNSW) | Generated after Stage 6 | |
| `embedding_version` | text | PG | Model identifier | |
| `display_priority` | integer | PG | LLM + editorial override | |
| `icon_class` | enum | PG | Derived from entity_type | |
| `entity_color` | text | PG | Derived / editorial | Hex color string |
| `created_at` | timestamp | PG | Pipeline insertion time | |
| `updated_at` | timestamp | PG | Last modification | |
| `created_by` | text | PG | Pipeline batch ID or reviewer | |

**Computed / cached fields** (regenerated on entity update, stored in PG):

| Field | Type | Derivation |
|-------|------|-----------|
| `confidence_breakdown` | JSONB | `{location: "high", date: "medium", sources: 3, verification: "human_verified"}` |
| `relationship_summary` | JSONB | `{political: 4, military: 2, economic: 1, causal: 3}` |
| `source_diversity_score` | integer | Count of unique source_types across source_citations |
| `temporal_display_range` | text | Formatted display string: "500 BCE – 31 BCE", "From 27 CE", etc. Stored when pre-computed; otherwise computed from `temporal_start`/`temporal_end` at read time |
| `nearby_entity_count` | integer | PostGIS + temporal proximity count (cached) |
| `cluster_id` | integer | HDBSCAN cluster from periodic embedding analysis |
| `era_label` | text | Mapped from temporal range via era reference table |

### 3.1 External Geospatial References (`entity_geo_refs`)

To link entities to OpenHistoricalMap (and additional border datasets), use a dedicated sub-table:

```sql
CREATE TABLE entity_geo_refs (
  geo_ref_id         UUID PRIMARY KEY,
  entity_id          UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
  provider           TEXT NOT NULL,      -- ohm | wikidata | geonames | pleiades | custom
  external_type      TEXT NOT NULL,      -- node | way | relation | feature | qid
  external_id        TEXT NOT NULL,      -- e.g. relation/2744968, way/198568124, Q16553
  match_role         TEXT NOT NULL,      -- primary | candidate | fallback | rejected
  retrieval_method   TEXT NOT NULL,      -- overpass | nominatim | rest | manual
  temporal_start     TEXT,
  temporal_end       TEXT,
  temporal_start_year INTEGER,
  temporal_end_year   INTEGER,
  external_tags      JSONB,
  source_meta        JSONB,              -- endpoint, query, attribution, license
  match_score        NUMERIC,
  is_active          BOOLEAN DEFAULT true,
  last_verified_at   TIMESTAMP,
  created_at         TIMESTAMP DEFAULT now(),
  updated_at         TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_geo_refs_entity ON entity_geo_refs(entity_id);
CREATE INDEX idx_geo_refs_provider_extid ON entity_geo_refs(provider, external_type, external_id);
CREATE INDEX idx_geo_refs_active_lookup ON entity_geo_refs(provider, external_type, external_id, is_active);
CREATE INDEX idx_geo_refs_temporal_year ON entity_geo_refs(entity_id, temporal_start_year, temporal_end_year);

-- Allow composite FK from entities(entity_id, primary_geo_ref_id)
CREATE UNIQUE INDEX uq_geo_refs_entity_pair ON entity_geo_refs(entity_id, geo_ref_id);

-- Optional: one active primary georef row per entity in refs table
CREATE UNIQUE INDEX uq_geo_refs_primary_role_per_entity
  ON entity_geo_refs(entity_id)
  WHERE is_active = true AND match_role = 'primary';

-- Ensure entities.primary_geo_ref_id belongs to the same entity (soundness guard)
ALTER TABLE entities
  ADD CONSTRAINT fk_entities_primary_geo_ref_owned
  FOREIGN KEY (entity_id, primary_geo_ref_id)
  REFERENCES entity_geo_refs(entity_id, geo_ref_id)
  DEFERRABLE INITIALLY DEFERRED;
```

`geometry_snapshots` should optionally reference `geo_ref_id` so every generated geometry is traceable to a specific OHM element or fallback source.

### 3.1.1 Reverse Lookup Query (OHM Click -> Entity -> Date-Scoped Geometry)

```sql
-- Inputs:
--   :provider        (e.g. 'ohm')
--   :external_type   ('node' | 'way' | 'relation')
--   :external_id     (e.g. '2704719')
--   :target_year     (integer year in app canonical format)

WITH ref_match AS (
  SELECT r.entity_id, r.geo_ref_id
  FROM entity_geo_refs r
  WHERE r.provider = :provider
    AND r.external_type = :external_type
    AND r.external_id = :external_id
    AND r.is_active = true
    AND (r.temporal_start_year IS NULL OR r.temporal_start_year <= :target_year)
    AND (r.temporal_end_year   IS NULL OR r.temporal_end_year   >= :target_year)
  ORDER BY CASE WHEN r.match_role = 'primary' THEN 0 ELSE 1 END, r.match_score DESC NULLS LAST
  LIMIT 1
),
snap AS (
  SELECT s.*
  FROM geometry_snapshots s
  JOIN ref_match rm ON rm.entity_id = s.entity_id
  WHERE s.year_start <= :target_year
    AND s.year_end   >= :target_year
  ORDER BY s.display_priority DESC NULLS LAST, s.updated_at DESC
  LIMIT 1
)
SELECT
  e.entity_id,
  e.name,
  e.entity_type,
  e.entity_group,
  COALESCE(s.geom, e.geom) AS resolved_geom,
  COALESCE(s.territory_geom, e.territory_geom) AS resolved_territory_geom,
  rm.geo_ref_id AS matched_geo_ref_id
FROM ref_match rm
JOIN entities e ON e.entity_id = rm.entity_id
LEFT JOIN snap s ON true;
```

### 3.2 Stage 3 Georesolution Decision Flow

Pipeline logic for `geom`/`territory_geom` assignment:

1. **Wikidata seed:** Start from QID and any available coordinates or place hints.
2. **OHM lookup:** Query OHM (`nominatim`, then `overpass`/REST for `node|way|relation`, preferring `type=chronology` relations where applicable).
3. **If OHM match found:** write `entity_geo_refs` row (`provider='ohm'`, `match_role='primary'`), hydrate `geom`/`territory_geom`, set `location_method` to `ohm_nominatim` or `ohm_overpass` or `ohm_rest_api`, and set `geo_resolution_status='matched_ohm'`.
4. **Else fallback:** try non-OHM border/geometry sources and manual digitization inputs.
5. **If fallback found:** write `entity_geo_refs` row (`match_role='fallback'`), hydrate geometry fields, set `location_method` to `source_database` or `human_assigned`, and set `geo_resolution_status='matched_fallback'`.
6. **Else unresolved:** leave geometry fields null and set `geo_resolution_status='empty_geom'` with `location_confidence='unresolved'`.

---

## 4. Entity Type–Specific Attributes

> **Storage decision:** All type-specific fields are stored as keys in the JSONB `attributes` column on the `entities` table. They are **not** separate database columns or sub-tables. This section documents the expected JSONB schema per entity type for pipeline ingestion, validation, and admin panel form generation.
>
> **Rationale:** Type-specific attributes are never queried on the map hot path (which uses only base columns from Section 3). They are loaded only when displaying entity detail views — a single-row JSON decode. JSONB avoids 30 sub-tables, 30 models, and 30 migrations while allowing schema evolution without DDL changes. For the few attribute keys used in filters, PostgreSQL expression indexes provide indexed equality lookups (see `plans/attributes_and_geometry_snapshots.md` Section 5).
>
> **Cross-entity references in JSONB:** Fields like `"city_entity_id"` or `"person_id"` stored inside JSONB arrays are **soft references** (UUID strings), not foreign keys. Referential integrity for these is enforced at the application layer during pipeline validation (Stage 7) and admin panel saves. Hard FK references that need database-level enforcement are stored as base columns (`parent_entity_id`, `successor_entity_id`) or in the `relationships` table.
>
> **Time-varying geometries:** Entities whose PostGIS geometries change over time (empire borders, trade route shifts, migration paths) use the dedicated `geometry_snapshots` table — not JSONB — because PostGIS spatial queries require GIST-indexed `geometry` columns. See `plans/attributes_and_geometry_snapshots.md` Section 4.

All entities carry every field from Section 3 in addition to the `attributes` keys listed below.

---

### 4.1 Political Entity

**entity_type:** `political_entity` | **entity_group:** `POLITY`

```jsonc
{
  "political_subtype": "empire",                              // enum: political_entity_subtype
  "government_type": "bureaucratic_centralized",              // enum: government_type
  "succession_type": "primogeniture",                         // enum: succession_type
  "government_history": [{"type": "str", "start": -753, "end": -509}],
  "capital_history": [{"city_entity_id": "uuid", "start": -753, "end": -509}],
  "population_estimates": [{"value": 55000000, "year": 117, "source": "str", "confidence": "str"}],
  "territory_area_estimates": [{"km2": 5000000, "year": 117, "source": "str"}],
  "official_languages": [{"language_entity_id": "uuid", "start": -200, "end": 476}],
  "official_religions": [{"religious_movement_id": "uuid", "start": 380, "end": 476, "status": "str"}],
  "administrative_divisions": [{"name": "Syria", "type": "province", "entity_id": "uuid"}]
}
```

**Key relationships:** `rules/governed_by` (Person), `vassal_of/suzerain_of` (Political Entity), `capital_of` (City), `at_war_with` (Political Entity), `controls` (Trade Route, Resource)
**Geometry snapshots:** Yes — territory borders change over time.

---

### 4.2 Person

**entity_type:** `person` | **entity_group:** `POLITY`

```jsonc
{
  "gender": "male",                                            // enum: gender
  "birth_date": "-356",                                        // EDTF text
  "death_date": "-323",                                        // EDTF text
  "birth_place_id": "uuid",                                    // → City entity
  "death_place_id": "uuid",                                    // → City entity
  "burial_place_id": "uuid",                                   // → City or Monument entity
  "dynasty_id": "uuid",                                        // → Dynasty entity
  "ethnicity": "Macedonian",
  "cause_of_death": "fever",
  "roles": [{"role": "ruler", "political_entity_id": "uuid", "start": -336, "end": -323, "title": "King"}]
}
```

**Key relationships:** `rules` (Political Entity), `commanded` (Military Unit), `authored` (Cultural Work), `founded` (Dynasty, City, Religious Movement), `parent_of/child_of/married_to` (Person)

---

### 4.3 Dynasty / Ruling House

**entity_type:** `dynasty` | **entity_group:** `POLITY`

```jsonc
{
  "founding_event": "str",
  "ethnic_origin": "str",
  "legitimacy_basis": "str",                                   // hereditary, divine right, etc.
  "succession_type": "primogeniture",                          // enum: succession_type
  "cadet_branches": [{"name": "str", "entity_id": "uuid", "split_date": 1200}],
  "political_entities_ruled": [{"entity_id": "uuid", "start": 1200, "end": 1400}]
}
```

**Key relationships:** `member_of_dynasty` (Person), `rules` (Political Entity), `preceded_by/succeeded_by` (Dynasty), `married_to` (Dynasty — alliance marriages)

---

### 4.4 Military Unit / Army

**entity_type:** `military_unit` | **entity_group:** `POLITY`

```jsonc
{
  "unit_subtype": "legion",                                    // enum: military_unit_subtype
  "composition": "professional",                               // enum: military_composition
  "size_estimates": [{"count": 5000, "year": 100, "source": "str"}],
  "commanders": [{"person_id": "uuid", "start": 100, "end": 110, "rank": "str"}],
  "equipment_technology": [{"technology_id": "uuid", "description": "str"}],
  "stationed_locations": [{"city_id": "uuid", "start": 100, "end": 110}],
  "notable_actions": [{"event_id": "uuid", "role": "str", "outcome": "str"}]
}
```

**Key relationships:** `part_of` (Political Entity), `commanded_by` (Person), `fought_at` (Event Battle), `stationed_at` (City)

---

### 4.5 City / Settlement

**entity_type:** `city` | **entity_group:** `PLACE`

```jsonc
{
  "settlement_subtype": "capital_city",                        // enum: settlement_subtype
  "elevation_m": 15,
  "founding_legend": "str",
  "population_estimates": [{"value": 1000000, "year": 100, "source": "str", "confidence": "str"}],
  "political_control": [{"political_entity_id": "uuid", "start": -753, "end": 476}],
  "economic_roles": [{"role": "trade_hub", "start": -200, "end": 476}],
  "infrastructure": [{"monument_id": "uuid", "built_date": -80}]
}
```

**Key relationships:** `capital_of` (Political Entity), `connects` (Trade Route), `location_of` (Event), `birth/death place of` (Person), `contains` (Monument)

---

### 4.6 Infrastructure / Monument

**entity_type:** `infrastructure_monument` | **entity_group:** `PLACE`

```jsonc
{
  "monument_subtype": "temple",                                // enum: monument_subtype
  "construction_start": "-447",                                // EDTF text
  "construction_end": "-432",                                  // EDTF text
  "commissioned_by": "uuid",                                   // → Person or Political Entity
  "architect_builder": "uuid",                                 // → Person
  "materials": ["marble", "limestone"],
  "dimensions": {"height_m": 13.7, "length_m": 69.5, "area_m2": null},
  "current_condition": "ruins",                                // extant, ruins, destroyed, rebuilt, submerged
  "destruction_date": null,                                    // EDTF text
  "destruction_cause": null,
  "unesco_status": "World Heritage Site",
  "city_id": "uuid"                                            // → City entity
}
```

**Key relationships:** `built_by` (Person, Political Entity), `located_at` (City), `destroyed_by` (Event, Person), `restored_by` (Person, Political Entity), `required` (Technology, Natural Resource)

**Design rationale:** Separating monuments from cities allows Civ-style "Wonder" display. The Colosseum, Great Wall, Hagia Sophia are some of the most visually compelling map features.

---

### 4.7 Religious / Ideological Movement

**entity_type:** `religious_movement` | **entity_group:** `CULTURE`

```jsonc
{
  "movement_subtype": "monotheism",                            // enum: religious_movement_subtype
  "founder_id": "uuid",                                        // → Person
  "core_doctrines": "str",
  "institutional_structure": "str",                            // church, temple network, decentralized
  "sacred_texts": [{"religious_text_id": "uuid", "role": "str"}],
  "spread_timeline": [{"region": "str", "date": 50, "method": "str"}],
  "schisms": [{"child_movement_id": "uuid", "date": 1054, "cause": "str"}],
  "persecution_periods": [{"political_entity_id": "uuid", "start": 64, "end": 313, "severity": "str"}]
}
```

**Key relationships:** `founded` (Person), `official_religion_of` (Political Entity), `schism_from` (Religious Movement), `persecuted_by` (Political Entity), `inspired` (Intellectual Movement)
**Geometry snapshots:** Yes — spread extent changes over time.

---

### 4.8 Trade Route / Network

**entity_type:** `trade_route` | **entity_group:** `ECONOMY`

```jsonc
{
  "route_subtype": "overland",                                 // enum: trade_route_subtype
  "transport_mode": ["camel_caravan", "sailing_vessel"],
  "risk_factors": ["piracy", "banditry"],
  "waypoints": [{"city_id": "uuid", "order": 1, "role": "str"}],
  "commodities": [{"resource_id": "uuid", "direction": "eastbound", "volume_estimate": "str"}],
  "controlling_entities": [{"political_entity_id": "uuid", "segment": "str", "start": -200, "end": 200}],
  "infrastructure": [{"type": "caravanserai", "description": "str", "segment": "str"}],
  "customs_taxation": [{"location": "str", "rate": "str", "entity_id": "uuid"}]
}
```

**Key relationships:** `connects` (City), `transports` (Natural Resource), `controlled_by` (Political Entity), `threatened_by` (Event War, Epidemic), `enabled_by` (Technology)
**Geometry snapshots:** Yes — route paths shift over centuries.

---

### 4.9 Natural Resource

**entity_type:** `natural_resource` | **entity_group:** `ECONOMY`

```jsonc
{
  "resource_category": "metal_precious",                       // enum: resource_category
  "renewability": "finite",                                    // enum: resource_renewability
  "is_tradeable": true,
  "substitutability": "str",
  "transport_difficulty": "str",
  "cultural_value": "str",
  "strategic_value_history": [{"value": "critical", "period": "str", "reason": "str"}],
  "extraction_tech_required": [{"technology_id": "uuid", "description": "str"}],
  "known_deposits": [{"location": "str", "quality": "str", "discovery_date": "str"}],
  "processed_forms": [{"raw": "tin ore", "processed": "bronze", "technology_required": "str"}],
  "price_history": [{"period": "str", "value": 100, "unit": "str", "source": "str"}]
}
```

**Key relationships:** `extracted_by` (Extraction Infrastructure), `transported_via` (Trade Route), `controlled_by` (Political Entity), `required_by` (Technology), `caused` (Event War — resource wars)

---

### 4.10 Extraction Infrastructure

**entity_type:** `extraction_infra` | **entity_group:** `PLACE`

```jsonc
{
  "infra_subtype": "mine",                                     // enum: extraction_infra_subtype
  "scale": "large",                                            // small, medium, large, industrial
  "resource_extracted": [{"resource_id": "uuid", "volume_estimate": "str", "unit": "str"}],
  "labor_force": {"size": 500, "type": "slave_soldier", "conditions": "str"},
  "technology_used": [{"technology_id": "uuid", "description": "str"}],
  "productivity_history": [{"period": "str", "output": 100, "unit": "str"}],
  "controlling_entity": [{"political_entity_id": "uuid", "start": -200, "end": 100}]
}
```

**Key relationships:** `extracts` (Natural Resource), `controlled_by` (Political Entity), `near` (City), `targeted_in` (Event War), `uses` (Technology)

---

### 4.11 Currency / Monetary System

**entity_type:** `currency_monetary_system` | **entity_group:** `ECONOMY`

```jsonc
{
  "currency_type": "coin_metal",                               // enum: currency_type
  "issuing_authority": "uuid",                                 // → Political Entity
  "denominations": [{"name": "denarius", "value": 1, "metal": "silver", "weight_g": 3.9}],
  "metal_composition_history": [{"period": "str", "metal": "silver", "purity_pct": 95}],
  "exchange_rates": [{"against_currency_id": "uuid", "rate": 1.5, "period": "str"}],
  "circulation_area": [{"region": "str", "period": "str"}]
}
```

**Key relationships:** `minted_by` (Political Entity), `used_currency` (Political Entity, Trade Route), `required` (Natural Resource — metal)

---

### 4.12 Technology / Innovation

**entity_type:** `technology` | **entity_group:** `CULTURE`

```jsonc
{
  "tech_domain": "military",                                   // enum: technology_domain
  "inventor_id": "uuid",                                       // → Person
  "origin_location": "uuid",                                   // → City
  "replaced_by": "uuid",                                       // → Technology
  "impact_description": "str",
  "prerequisites": [{"technology_id": "uuid"}],
  "adoption_timeline": [{"political_entity_id": "uuid", "date": 200, "method": "trade"}]
}
```

**Key relationships:** `invented` (Person), `adopted` (Political Entity), `enabled` (Military Unit, Extraction Infrastructure), `replaced_by` (Technology), `required_by` (Infrastructure Monument)

---

### 4.13 Educational / Knowledge Institution

**entity_type:** `educational_institution` | **entity_group:** `PLACE`

```jsonc
{
  "institution_type": "library",                               // academy, university, library, madrasa, etc.
  "founded_by": "uuid",                                        // → Person or Political Entity
  "city_id": "uuid",                                           // → City
  "destruction_event": "uuid",                                 // → Event (if destroyed)
  "subjects_taught": ["philosophy", "mathematics"],
  "library_holdings": "str",
  "notable_scholars": [{"person_id": "uuid", "period": "str", "role": "str"}]
}
```

**Key relationships:** `located_at` (City), `founded` (Person), `patron` (Political Entity), `taught_at` (Person), `influenced` (Intellectual Movement)

---

### 4.14 Event — War / Conflict

**entity_type:** `event_war` | **entity_group:** `EVENT`

```jsonc
{
  "war_subtype": "interstate_war",                             // enum: war_subtype
  "casus_belli": "str",
  "territorial_changes": "str",
  "ending_treaty": "uuid",                                     // → Event Treaty
  "belligerents": {"side_a": [{"entity_id": "uuid", "role": "str"}], "side_b": [{"entity_id": "uuid", "role": "str"}]},
  "key_commanders": [{"person_id": "uuid", "side": "side_a", "role": "str"}],
  "major_battles": [{"event_battle_id": "uuid"}],
  "casualties": {"side_a": {"killed": 10000}, "side_b": {"killed": 15000}, "civilian": 5000}
}
```

**Key relationships:** `between` (Political Entity), `commanded_by` (Person), `ended_by` (Event Treaty), `caused_by` (Event, Resource dispute), `resulted_in` (Territorial changes)

---

### 4.15 Event — Battle / Siege

**entity_type:** `event_battle` | **entity_group:** `EVENT`

```jsonc
{
  "battle_subtype": "siege",                                   // enum: battle_subtype
  "parent_war_id": "uuid",                                     // → Event War
  "outcome": "decisive_victory",                               // enum: battle_outcome
  "victor_side": "side_a",
  "tactical_notes": "str",
  "belligerents": {"side_a": [{"entity_id": "uuid", "role": "str"}], "side_b": [{"entity_id": "uuid", "role": "str"}]},
  "commanders": [{"person_id": "uuid", "side": "side_a", "survived": true}],
  "forces": {"side_a": {"count": 80000, "composition": "str"}, "side_b": {"count": 7000, "composition": "str"}},
  "casualties": {"side_a": {"killed": 5000}, "side_b": {"killed": 7000}}
}
```

**Key relationships:** `part_of` (Event War), `fought_at` (City/location), `commanded_by` (Person), `participated_in` (Military Unit)

---

### 4.16 Event — Treaty / Agreement

**entity_type:** `event_treaty` | **entity_group:** `EVENT`

```jsonc
{
  "treaty_subtype": "peace_treaty",                            // enum: treaty_subtype
  "key_provisions": "str",
  "duration": "str",
  "termination_date": null,                                    // EDTF text
  "termination_reason": null,
  "signatories": [{"political_entity_id": "uuid", "role": "str"}],
  "negotiators": [{"person_id": "uuid", "representing": "uuid"}],
  "territorial_terms": [{"region": "str", "from_entity": "uuid", "to_entity": "uuid"}],
  "compliance_history": [{"date": 200, "event": "str", "description": "str"}]
}
```

**Key relationships:** `signed_by` (Political Entity), `negotiated_by` (Person), `ended` (Event War), `violated_by` (Political Entity), `created` (Diplomatic Relationship)

---

### 4.17 Event — Revolution / Rebellion / Coup

**entity_type:** `event_rebellion` | **entity_group:** `EVENT`

```jsonc
{
  "rebellion_subtype": "revolution",                           // enum: rebellion_subtype
  "target_government": "uuid",                                 // → Political Entity
  "outcome": "success",                                        // success, failure, partial, ongoing
  "government_change": "str",
  "repression": "str",
  "causes": ["famine", "taxation"],
  "rebel_leaders": [{"person_id": "uuid", "role": "str"}],
  "factions": [{"name": "str", "composition": "str", "social_class_id": "uuid"}],
  "external_supporters": [{"political_entity_id": "uuid", "support_type": "str"}],
  "casualties": {"killed": 10000}
}
```

**Key relationships:** `within` (Political Entity), `led_by` (Person), `caused_by` (Famine, War, Reform failure), `resulted_in` (New Political Entity, Government change)

---

### 4.18 Event — Natural Disaster

**entity_type:** `event_natural_disaster` | **entity_group:** `EVENT`

```jsonc
{
  "disaster_subtype": "earthquake",                            // enum: disaster_subtype
  "economic_damage": "str",
  "societal_response": "str",
  "long_term_consequences": "str",
  "estimated_deaths": {"min": 10000, "max": 30000, "source": "str"},
  "affected_entities": [{"political_entity_id": "uuid", "severity": "str"}],
  "infrastructure_destroyed": [{"entity_id": "uuid", "damage_level": "str"}]
}
```

**Key relationships:** `affected` (Political Entity, City), `destroyed` (Infrastructure Monument), `caused` (Migration, Famine, Rebellion), `worsened_by` (pre-existing conditions)

---

### 4.19 Event — Technology Adoption

**entity_type:** `event_tech_adoption` | **entity_group:** `EVENT`

```jsonc
{
  "technology_id": "uuid",                                     // → Technology
  "adopting_entity": "uuid",                                   // → Political Entity
  "acquisition_method": "trade",                               // independent invention, trade, conquest, espionage
  "adaptation_notes": "str",
  "impact": "str",
  "diffusion_speed": "gradual"                                 // rapid, gradual, incomplete
}
```

---

### 4.20 Event — Legal / Institutional Reform

**entity_type:** `event_legal_reform` | **entity_group:** `EVENT`

```jsonc
{
  "reform_subtype": "land_reform",                             // enum: reform_subtype
  "enacting_entity": "uuid",                                   // → Political Entity
  "provisions": "str",
  "motivation": "str",
  "longevity": "str",
  "effects_intended": "str",
  "effects_unintended": "str",
  "reversal_date": null,                                       // EDTF text
  "key_figures": [{"person_id": "uuid", "role": "str"}]
}
```

---

### 4.21 Epidemic / Disease

**entity_type:** `epidemic_disease` | **entity_group:** `EVENT`

```jsonc
{
  "epidemic_subtype": "plague_bacterial",                      // enum: epidemic_subtype
  "severity": "pandemic",                                      // enum: epidemic_severity
  "spread_vector": "fleas/rats",
  "origin_location": "uuid",                                   // → City
  "societal_responses": "str",
  "economic_consequences": "str",
  "estimated_deaths": {"min": 25000000, "max": 50000000, "percentage_of_population": 30, "source": "str"},
  "spread_timeline": [{"region": "str", "arrival_date": 1347, "peak_date": 1349, "end_date": 1353}],
  "affected_trade_routes": [{"route_id": "uuid", "disruption_level": "str"}],
  "demographic_impact": [{"region": "str", "population_loss_pct": 30, "recovery_years": 150}],
  "recurrence_pattern": [{"date": 1361, "severity": "regional"}]
}
```

**Key relationships:** `spread_via` (Trade Route), `affected` (Political Entity, City), `caused` (Migration, Labor shortage → Reform), `worsened_by` (War, Famine)
**Geometry snapshots:** Yes — spread wavefront changes over time.

**Design rationale:** Epidemics spread geographically over time following trade and military networks. On the map, a natural disaster is a single marker; an epidemic is an animated wavefront.

---

### 4.22 Diplomatic Relationship / Alliance

**entity_type:** `diplomatic_relationship` | **entity_group:** `POLITY`

```jsonc
{
  "diplomatic_status": "alliance",                             // enum: diplomatic_status
  "party_a": "uuid",                                          // → Political Entity
  "party_b": "uuid",                                          // → Political Entity
  "originating_treaty": "uuid",                                // → Event Treaty
  "terms": "str",
  "power_asymmetry": "str",
  "military_obligations": "str",
  "termination_cause": "str",
  "tribute_details": {"direction": "b_to_a", "amount": "str", "commodity": "str", "frequency": "annual"},
  "violations": [{"date": 200, "violator": "uuid", "description": "str", "consequence": "str"}]
}
```

**Key relationships:** `between` (Political Entity), `created_by` (Event Treaty), `violated_by` (Political Entity), `terminated_by` (Event War), `mediated_by` (Person, Political Entity)

**Design rationale:** Captures the ongoing *state* of a diplomatic relationship, while Event Treaty captures the *moment of creation*.

---

### 4.23 Migration / Population Movement

**entity_type:** `migration` | **entity_group:** `EVENT`

```jsonc
{
  "migration_subtype": "invasion",                             // enum: migration_subtype
  "migrating_group": "str",
  "voluntary": false,
  "casualties_during": "str",
  "impact_origin": "str",
  "impact_destination": "str",
  "push_factors": ["invasion", "famine"],
  "pull_factors": ["empty land"],
  "origin_regions": [{"location": "str", "entity_id": "uuid"}],
  "destination_regions": [{"location": "str", "entity_id": "uuid"}],
  "population_estimate": {"min": 50000, "max": 200000, "source": "str"},
  "route": [{"waypoint": "str", "date": 375}]
}
```

**Geometry snapshots:** Yes — migration paths and wavefronts change over time.

---

### 4.24 Social Class / Group

**entity_type:** `social_class` | **entity_group:** `POLITY`

```jsonc
{
  "class_subtype": "nobility",                                 // enum: social_class_subtype
  "political_entity_id": "uuid",                               // → Political Entity
  "economic_role": "str",
  "legal_status": "str",
  "political_power": "str",
  "social_mobility": "str",
  "military_obligation": "str",
  "education_access": "str",
  "population_proportion": [{"percentage": 2, "year": 1400, "source": "str"}]
}
```

---

### 4.25 Cultural / Artistic Work

**entity_type:** `cultural_work` | **entity_group:** `CULTURE`

```jsonc
{
  "work_subtype": "literary_text",                             // enum: cultural_work_subtype
  "creator_id": "uuid",                                        // → Person
  "patron_id": "uuid",                                         // → Person or Political Entity
  "language_id": "uuid",                                       // → Language
  "style_genre": "str",
  "preservation_status": "extant",                             // extant, fragments, lost, reconstructed, copies_only
  "current_location": "str",
  "influence_description": "str",
  "medium_materials": ["papyrus", "ink"],
  "themes": ["war", "honor"]
}
```

---

### 4.26 Intellectual / Artistic Movement

**entity_type:** `intellectual_movement` | **entity_group:** `CULTURE`

```jsonc
{
  "movement_subtype": "philosophical_school",                  // enum: intellectual_movement_subtype
  "core_ideas": "str",
  "methodology": "str",
  "style_characteristics": "str",
  "founders": [{"person_id": "uuid"}],
  "geographic_centers": [{"city_id": "uuid", "period": "str"}],
  "major_works": [{"cultural_work_id": "uuid"}],
  "opposition": [{"movement_id": "uuid", "nature": "str"}]
}
```

---

### 4.27 Archaeological Culture

**entity_type:** `archaeological_culture` | **entity_group:** `CULTURE`

```jsonc
{
  "technology_level": "str",
  "economic_base": "str",
  "settlement_patterns": "str",
  "burial_practices": "str",
  "hypothesized_ethnicity": "str",
  "hypothesized_language": "uuid",                             // → Language (often uncertain)
  "evidence_quality": "str",
  "material_markers": ["pottery style X", "burial type Y"],
  "type_sites": [{"name": "str", "location": "str", "excavation_date": "str"}]
}
```

---

### 4.28 Language / Linguistic Group

**entity_type:** `language` | **entity_group:** `CULTURE`

```jsonc
{
  "language_family": "Indo-European",
  "language_status": "extinct",                                // enum: language_status
  "writing_system": "cuneiform",
  "descended_from": "uuid",                                    // → Language
  "iso_639_code": "lat",
  "speaker_estimates": [{"count": 10000000, "year": 100, "source": "str"}],
  "roles": [{"role": "administrative", "political_entity_id": "uuid", "period": "str"}]
}
```

---

### 4.29 Religious Text / Sacred Object

**entity_type:** `religious_text` | **entity_group:** `CULTURE`

```jsonc
{
  "text_type": "scripture",                                    // scripture, commentary, relic, artifact
  "composition_date": "-600",                                  // EDTF, often disputed
  "language_id": "uuid",                                       // → Language
  "genre": "law",                                              // mythology, law, prophecy, wisdom, history
  "material": "str",
  "authors": [{"person_id": "uuid", "role": "str"}],
  "canonical_status": [{"religious_movement_id": "uuid", "status": "canonical"}],
  "translation_history": [{"language_id": "uuid", "date": 250, "translator_id": "uuid"}],
  "veneration_sites": [{"city_id": "uuid", "description": "str"}]
}
```

---

### 4.30 Legal Code / Constitutional Document

**entity_type:** `legal_code` | **entity_group:** `CULTURE`

```jsonc
{
  "promulgation_date": "-450",                                 // EDTF text
  "promulgator_id": "uuid",                                    // → Person or Political Entity
  "governing_entity": "uuid",                                  // → Political Entity
  "language_id": "uuid",                                       // → Language
  "key_provisions": "str",
  "legal_philosophy": "str",
  "enforcement_duration": "str",
  "modern_significance": "str",
  "amendments": [{"date": -300, "description": "str"}],
  "influenced_by": [{"legal_code_id": "uuid", "description": "str"}],
  "influenced": [{"legal_code_id": "uuid", "description": "str"}]
}
```

---

## 5. Meta-Entity: Source

**entity_type:** N/A — stored in a separate `sources` table, not in the main entity table.

| Field | Type | Storage | Notes |
|-------|------|---------|-------|
| `source_id` | UUID | PG (PK) | |
| `title` | text | PG | |
| `source_type` | enum (`reliability_tier`) | PG | authoritative, scholarly, reference, user_contributed |
| `document_type` | text | PG | academic_paper, encyclopedia, primary_source, database_export, web_article |
| `author` | text | PG | |
| `date_created` | text | PG | When source was written |
| `date_discovered` | text | PG | If archaeological |
| `language` | text | PG | ISO 639-1 |
| `current_location` | text | PG | Archive, museum, URL |
| `source_url` | text | PG | Original retrieval URL |
| `content_hash` | text | PG | SHA-256 for dedup |
| `ingestion_date` | timestamp | PG | When entered pipeline |
| `geographic_scope` | text | PG | Rough region label |
| `temporal_scope` | text | PG | Rough date range |
| `contemporaneity` | text | PG | Written during events or later? |
| `author_bias` | text | PG | Perspective, agenda |
| `corroboration` | text | PG | Other sources confirm? |
| `scholarly_consensus` | text | PG | |
| `raw_file_path` | text | PG → **S3 reference** | `s3://bucket/sources/{source_id}.pdf` |
| `nlp_output_path` | text | PG → **S3 reference** | `s3://bucket/nlp/{source_id}.json` |
| `llm_log_path` | text | PG → **S3 reference** | `s3://bucket/llm-logs/{source_id}/` |

---

## 6. Relationship Types

Relationships are stored in a dedicated `relationships` table:

```sql
CREATE TABLE relationships (
  relationship_id   UUID PRIMARY KEY,
  source_entity_id  UUID NOT NULL REFERENCES entities(entity_id),
  target_entity_id  UUID NOT NULL REFERENCES entities(entity_id),
  relationship_type relationship_type NOT NULL,   -- enum from 2.13
  temporal_start    TEXT,                          -- Integer year string; negative = BCE
  temporal_end      TEXT,                          -- Integer year string; negative = BCE
  description       TEXT,
  confidence        confidence_level,
  source_citations  JSONB,
  created_at        TIMESTAMP DEFAULT now(),
  created_by        TEXT
);

-- Indexes
CREATE INDEX idx_rel_source ON relationships(source_entity_id);
CREATE INDEX idx_rel_target ON relationships(target_entity_id);
CREATE INDEX idx_rel_type   ON relationships(relationship_type);
```

Relationships are **directional**: `(Rome, vassal_of, Parthia)` is different from `(Parthia, suzerain_of, Rome)`. The pipeline should create both directions or the API should handle bidirectional lookup.

---

## 7. Storage Split: PostgreSQL vs S3

### 7.1 In PostgreSQL (PostGIS + pgvector)

Everything that gets queried, joined, filtered, or indexed:

- **Entity table** with all fields from Section 3 and type-specific JSONB attributes
- **Geometry snapshots table** for time-varying PostGIS geometries (empire borders, trade route shifts) — see `plans/attributes_and_geometry_snapshots.md`
- **Relationships table** (Section 6)
- **Sources metadata table** (Section 5, minus raw files)
- **PostGIS geometry columns** with GIST spatial indexes on `geom` and `territory_geom`
- **pgvector embedding column** with HNSW index for ANN search
- **Full-text search** via tsvector index on `name`, `alternative_names`, `summary`
- **GIN indexes** on `tags`, `source_citations`, and JSONB attribute fields
- **Review history** (audit trail of every status change and field edit)
- **User accounts and annotations** (bezier curves, labels, overlays)
- **Computed/cached fields** (confidence_breakdown, relationship_summary, etc.)

### 7.2 In S3-Compatible Object Storage

Everything referenced by URL, written once, read infrequently:

| Bucket / Prefix | Contents | Retention |
|-----------------|----------|-----------|
| `sources/{source_id}.*` | Raw PDFs, HTML, text files | Permanent |
| `nlp/{source_id}.json` | Full NLP extraction output from Stage 2 | Permanent (pipeline debug) |
| `llm-logs/{entity_id}/` | Prompt + response logs for each entity synthesis | Permanent (audit) |
| `exports/{user_id}/{export_id}.*` | GeoJSON, Shapefile, CSV user exports | 90 days or permanent |
| `media/{entity_id}/*` | Historical map images, archaeological photos, coin images | Permanent |
| `backups/{date}/` | PostgreSQL pg_dump snapshots | Rolling 30 days |
| `embeddings-archive/{version}/` | Full embedding dumps before model upgrades | Permanent |

### 7.3 Linking Pattern

Entity records in PG reference S3 via path strings:

```sql
-- source_citations JSONB contains:
[{
  "source_id": "abc-123",
  "page": 42,
  "quote": "Valerian was captured at Edessa...",
  "bucket_path": "sources/abc-123.pdf"   -- resolved to signed URL by API
}]

-- media_refs JSONB contains:
[{
  "type": "archaeological_photo",
  "url": "media/entity-456/ruins_01.jpg",  -- resolved to signed URL
  "caption": "Remains of the forum, excavated 1923",
  "date": "1923"
}]
```

The API generates time-limited signed URLs when a user requests the full document or image. No direct S3 access from the frontend.
