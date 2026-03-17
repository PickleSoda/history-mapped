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

Every entity in PostgreSQL shares these columns. Type-specific fields are stored in a JSONB `attributes` column or in dedicated sub-tables depending on query needs.

| Field | Type | Storage | Source | Notes |
|-------|------|---------|--------|-------|
| `entity_id` | UUID | PG (PK) | Generated at Stage 6 | |
| `entity_type` | enum | PG (indexed) | LLM classification | One of 30 values |
| `entity_group` | enum | PG (indexed) | Derived from entity_type | Computed, not stored separately if using lookup |
| `name` | text | PG (indexed, tsvector) | NLP + LLM canonical form | Full-text searchable |
| `alternative_names` | text[] | PG | NLP extraction from all sources | |
| `wikidata_id` | text | PG (indexed) | Geocoding cascade | Nullable; stable cross-reference |
| `geom` | geometry | PG + PostGIS (GIST index) | Geocoding at Stage 3 | Point, Polygon, LineString, etc. |
| `territory_geom` | geometry | PG + PostGIS | Manual / LLM / import | Nullable; polygon extent for polities |
| `location_name` | text | PG | Geocoding cascade | Human-readable |
| `location_confidence` | enum | PG | Geocoding confidence | high/medium/low/unresolved |
| `location_method` | enum | PG | Which geocoder matched | |
| `temporal_start` | text (EDTF) | PG (indexed) | NLP Stage 4 | |
| `temporal_end` | text (EDTF) | PG (indexed) | NLP Stage 4 | |
| `date_raw` | text | PG | Original source text | |
| `date_method` | enum | PG | Resolution method | |
| `date_confidence` | enum | PG | Stage 4 assessment | |
| `duration_type` | enum | PG | LLM classification | point/period/ongoing/uncertain |
| `summary` | text | PG | LLM synthesis at Stage 6 | 500–3000 chars typical |
| `significance` | text | PG | LLM assessment | |
| `confidence_notes` | text | PG | LLM-identified uncertainties | |
| `tags` | text[] | PG (GIN index) | LLM + human tagging | Freeform categorical tags |
| `impact_score` | integer | PG (indexed) | LLM + editorial | 1–100 scale |
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
| `temporal_display_range` | text | Formatted from EDTF: "c. 260 CE", "3rd century BCE" |
| `nearby_entity_count` | integer | PostGIS + temporal proximity count (cached) |
| `cluster_id` | integer | HDBSCAN cluster from periodic embedding analysis |
| `era_label` | text | Mapped from temporal range via era reference table |

---

## 4. Entity Specifications

Below, each entity lists only its **type-specific fields** stored in the `attributes` JSONB column or in dedicated sub-tables. All entities also carry every field from Section 3.

---

### 4.1 Political Entity

**entity_type:** `political_entity`
**entity_group:** `POLITY`

| Field | Type | Notes |
|-------|------|-------|
| `political_subtype` | enum (`political_entity_subtype`) | empire, kingdom, republic, etc. |
| `government_type` | enum | Current/primary government form |
| `government_history` | JSONB | `[{type, start, end}]` — government changes over time |
| `capital_history` | JSONB | `[{city_entity_id, start, end}]` |
| `population_estimates` | JSONB | `[{value, year, source, confidence}]` |
| `territory_area_estimates` | JSONB | `[{km2, year, source}]` |
| `official_languages` | JSONB | `[{language_entity_id, start, end}]` |
| `official_religions` | JSONB | `[{religious_movement_id, start, end, status}]` |
| `succession_type` | enum | How leadership transfers |
| `administrative_divisions` | JSONB | `[{name, type, entity_id}]` — provinces, satrapies, etc. |

**Key relationships:** `rules/governed_by` (Person), `vassal_of/suzerain_of` (Political Entity), `capital_of` (City), `at_war_with` (Political Entity), `controls` (Trade Route, Resource)

---

### 4.2 Person

**entity_type:** `person`
**entity_group:** `POLITY`

| Field | Type | Notes |
|-------|------|-------|
| `gender` | enum | |
| `birth_date` | text (EDTF) | May differ from entity temporal_start |
| `death_date` | text (EDTF) | |
| `birth_place_id` | UUID (FK) | Link to City entity |
| `death_place_id` | UUID (FK) | Link to City entity |
| `roles` | JSONB | `[{role: enum, political_entity_id, start, end, title}]` |
| `dynasty_id` | UUID (FK) | Link to Dynasty entity |
| `ethnicity` | text | |
| `cause_of_death` | text | |
| `burial_place_id` | UUID (FK) | Link to City or Monument entity |

**Key relationships:** `rules` (Political Entity), `commanded` (Military Unit), `authored` (Cultural Work), `founded` (Dynasty, City, Religious Movement), `parent_of/child_of/married_to` (Person)

---

### 4.3 Dynasty / Ruling House

**entity_type:** `dynasty`
**entity_group:** `POLITY`

| Field | Type | Notes |
|-------|------|-------|
| `founding_event` | text | Description of dynasty origin |
| `ethnic_origin` | text | |
| `legitimacy_basis` | text | hereditary, divine right, mandate of heaven, etc. |
| `succession_type` | enum | |
| `cadet_branches` | JSONB | `[{name, entity_id, split_date}]` |
| `political_entities_ruled` | JSONB | `[{entity_id, start, end}]` — may rule multiple states |

**Key relationships:** `member_of_dynasty` (Person), `rules` (Political Entity), `preceded_by/succeeded_by` (Dynasty), `married_to` (Dynasty — alliance marriages)

---

### 4.4 Military Unit / Army

**entity_type:** `military_unit`
**entity_group:** `POLITY`

| Field | Type | Notes |
|-------|------|-------|
| `unit_subtype` | enum (`military_unit_subtype`) | legion, fleet, warband, etc. |
| `composition` | enum (`military_composition`) | professional, conscript, etc. |
| `size_estimates` | JSONB | `[{count, year, source}]` |
| `commanders` | JSONB | `[{person_id, start, end, rank}]` |
| `equipment_technology` | JSONB | `[{technology_id, description}]` |
| `stationed_locations` | JSONB | `[{city_id, start, end}]` |
| `notable_actions` | JSONB | `[{event_id, role, outcome}]` |

**Key relationships:** `part_of` (Political Entity), `commanded_by` (Person), `fought_at` (Event Battle), `stationed_at` (City)

---

### 4.5 City / Settlement

**entity_type:** `city`
**entity_group:** `PLACE`

| Field | Type | Notes |
|-------|------|-------|
| `settlement_subtype` | enum | capital, port, fortress, etc. |
| `population_estimates` | JSONB | `[{value, year, source, confidence}]` |
| `political_control` | JSONB | `[{political_entity_id, start, end}]` |
| `economic_roles` | JSONB | `[{role, start, end}]` — capital, trade hub, etc. |
| `infrastructure` | JSONB | `[{monument_id, built_date}]` |
| `founding_legend` | text | |
| `elevation_m` | numeric | Useful for defensive/geographic context |

**Key relationships:** `capital_of` (Political Entity), `connects` (Trade Route), `location_of` (Event), `birth/death place of` (Person), `contains` (Monument)

---

### 4.6 Infrastructure / Monument *(NEW)*

**entity_type:** `infrastructure_monument`
**entity_group:** `PLACE`

| Field | Type | Notes |
|-------|------|-------|
| `monument_subtype` | enum (`monument_subtype`) | temple, fortification, aqueduct, etc. |
| `construction_start` | text (EDTF) | |
| `construction_end` | text (EDTF) | |
| `commissioned_by` | UUID (FK) | Person or Political Entity |
| `architect_builder` | UUID (FK) | Person entity if known |
| `materials` | text[] | `['marble', 'limestone', 'concrete']` |
| `dimensions` | JSONB | `{height_m, length_m, area_m2}` — as known |
| `current_condition` | text | extant, ruins, destroyed, rebuilt, submerged |
| `destruction_date` | text (EDTF) | |
| `destruction_cause` | text | |
| `unesco_status` | text | If applicable |
| `city_id` | UUID (FK) | Parent city if applicable |

**Key relationships:** `built_by` (Person, Political Entity), `located_at` (City), `destroyed_by` (Event, Person), `restored_by` (Person, Political Entity), `required` (Technology, Natural Resource)

**Design rationale:** Separating monuments from cities allows Civ-style "Wonder" display. The Colosseum, Great Wall, Hagia Sophia are some of the most visually compelling map features. They have precise coordinates, clear construction timelines, and rich relationship networks.

---

### 4.7 Religious / Ideological Movement

**entity_type:** `religious_movement`
**entity_group:** `CULTURE`

| Field | Type | Notes |
|-------|------|-------|
| `movement_subtype` | enum | monotheism, polytheism, sect, etc. |
| `founder_id` | UUID (FK) | Person entity |
| `core_doctrines` | text | |
| `institutional_structure` | text | church, temple network, decentralized |
| `sacred_texts` | JSONB | `[{religious_text_id, role}]` |
| `spread_timeline` | JSONB | `[{region, date, method}]` — geographic expansion |
| `schisms` | JSONB | `[{child_movement_id, date, cause}]` |
| `persecution_periods` | JSONB | `[{political_entity_id, start, end, severity}]` |

**Key relationships:** `founded` (Person), `official_religion_of` (Political Entity), `schism_from` (Religious Movement), `persecuted_by` (Political Entity), `inspired` (Intellectual Movement)

---

### 4.8 Trade Route / Network

**entity_type:** `trade_route`
**entity_group:** `ECONOMY`

| Field | Type | Notes |
|-------|------|-------|
| `route_subtype` | enum | overland, maritime, riverine, mixed |
| `waypoints` | JSONB | `[{city_id, order, role}]` — ordered stops |
| `commodities` | JSONB | `[{resource_id, direction, volume_estimate}]` |
| `controlling_entities` | JSONB | `[{political_entity_id, segment, start, end}]` |
| `infrastructure` | JSONB | `[{type, description, segment}]` — roads, ports, caravanserais |
| `transport_mode` | text[] | `['camel_caravan', 'sailing_vessel', 'cart']` |
| `risk_factors` | text[] | `['piracy', 'banditry', 'seasonal_storms']` |
| `customs_taxation` | JSONB | `[{location, rate, entity_id}]` |

**Key relationships:** `connects` (City), `transports` (Natural Resource), `controlled_by` (Political Entity), `threatened_by` (Event War, Epidemic), `enabled_by` (Technology)

---

### 4.9 Natural Resource

**entity_type:** `natural_resource`
**entity_group:** `ECONOMY`

> **v2.0 change:** Now includes former Economic/Trade Good entity. Trade-specific fields added below.

| Field | Type | Notes |
|-------|------|-------|
| `resource_category` | enum | grain, metal_precious, spice, etc. |
| `renewability` | enum | renewable, finite, cyclical |
| `strategic_value_history` | JSONB | `[{value: enum, period, reason}]` — changes over time |
| `substitutability` | text | What alternatives exist |
| `transport_difficulty` | text | perishability, bulk, fragility |
| `extraction_tech_required` | JSONB | `[{technology_id, description}]` |
| `known_deposits` | JSONB | `[{location, quality, discovery_date}]` |
| `is_tradeable` | boolean | Whether this resource enters trade networks |
| `processed_forms` | JSONB | `[{raw, processed, technology_required}]` — tin ore → bronze |
| `price_history` | JSONB | `[{period, value, unit, source}]` — when documented |
| `cultural_value` | text | Prestige, religious significance |

**Key relationships:** `extracted_by` (Extraction Infrastructure), `transported_via` (Trade Route), `controlled_by` (Political Entity), `required_by` (Technology), `caused` (Event War — resource wars)

---

### 4.10 Extraction Infrastructure

**entity_type:** `extraction_infra`
**entity_group:** `PLACE`

| Field | Type | Notes |
|-------|------|-------|
| `infra_subtype` | enum | mine, quarry, farm, shipyard, etc. |
| `resource_extracted` | JSONB | `[{resource_id, volume_estimate, unit}]` |
| `scale` | text | small, medium, large, industrial |
| `labor_force` | JSONB | `{size, type: enum, conditions}` |
| `technology_used` | JSONB | `[{technology_id, description}]` |
| `productivity_history` | JSONB | `[{period, output, unit}]` |
| `controlling_entity` | JSONB | `[{political_entity_id, start, end}]` |

**Key relationships:** `extracts` (Natural Resource), `controlled_by` (Political Entity), `near` (City), `targeted_in` (Event War), `uses` (Technology)

---

### 4.11 Currency / Monetary System

**entity_type:** `currency_monetary_system`
**entity_group:** `ECONOMY`

| Field | Type | Notes |
|-------|------|-------|
| `currency_type` | enum | coin_metal, paper, commodity_money, etc. |
| `denominations` | JSONB | `[{name, value, metal, weight_g}]` |
| `issuing_authority` | UUID (FK) | Political Entity |
| `metal_composition_history` | JSONB | `[{period, metal, purity_pct}]` — debasement tracking |
| `exchange_rates` | JSONB | `[{against_currency_id, rate, period}]` |
| `circulation_area` | JSONB | `[{region, period}]` |

**Key relationships:** `minted_by` (Political Entity), `used_currency` (Political Entity, Trade Route), `required` (Natural Resource — metal)

---

### 4.12 Technology / Innovation

**entity_type:** `technology`
**entity_group:** `CULTURE`

| Field | Type | Notes |
|-------|------|-------|
| `tech_domain` | enum | military, agricultural, navigation, etc. |
| `inventor_id` | UUID (FK) | Person if known |
| `origin_location` | UUID (FK) | City where invented/first documented |
| `prerequisites` | JSONB | `[{technology_id}]` — tech tree dependencies |
| `adoption_timeline` | JSONB | `[{political_entity_id, date, method}]` |
| `impact_description` | text | |
| `replaced_by` | UUID (FK) | Successor technology |

**Key relationships:** `invented` (Person), `adopted` (Political Entity), `enabled` (Military Unit, Extraction Infrastructure), `replaced_by` (Technology), `required_by` (Infrastructure Monument)

---

### 4.13 Educational / Knowledge Institution

**entity_type:** `educational_institution`
**entity_group:** `PLACE`

| Field | Type | Notes |
|-------|------|-------|
| `institution_type` | text | academy, university, library, madrasa, monastery school |
| `founded_by` | UUID (FK) | Person or Political Entity |
| `city_id` | UUID (FK) | |
| `subjects_taught` | text[] | |
| `notable_scholars` | JSONB | `[{person_id, period, role}]` |
| `library_holdings` | text | Description of collection if known |
| `destruction_event` | UUID (FK) | If destroyed (Library of Alexandria) |

**Key relationships:** `located_at` (City), `founded` (Person), `patron` (Political Entity), `taught_at` (Person), `influenced` (Intellectual Movement)

---

### 4.14 Event — War / Conflict

**entity_type:** `event_war`
**entity_group:** `EVENT`

| Field | Type | Notes |
|-------|------|-------|
| `war_subtype` | enum | interstate, civil, religious, colonial, etc. |
| `belligerents` | JSONB | `{side_a: [{entity_id, role}], side_b: [{entity_id, role}]}` |
| `key_commanders` | JSONB | `[{person_id, side, role}]` |
| `major_battles` | JSONB | `[{event_battle_id}]` — links to child battle entities |
| `casualties` | JSONB | `{side_a: {killed, wounded, captured}, side_b: {...}, civilian}` |
| `territorial_changes` | text | |
| `ending_treaty` | UUID (FK) | Link to Event Treaty entity |
| `casus_belli` | text | Stated cause of war |

**Key relationships:** `between` (Political Entity), `commanded_by` (Person), `ended_by` (Event Treaty), `caused_by` (Event, Resource dispute), `resulted_in` (Territorial changes, Political Entity changes)

---

### 4.15 Event — Battle / Siege

**entity_type:** `event_battle`
**entity_group:** `EVENT`

| Field | Type | Notes |
|-------|------|-------|
| `battle_subtype` | enum | pitched_battle, siege, naval, ambush, etc. |
| `parent_war_id` | UUID (FK) | Link to Event War entity |
| `belligerents` | JSONB | Same structure as war |
| `commanders` | JSONB | `[{person_id, side, survived}]` |
| `forces` | JSONB | `{side_a: {count, composition}, side_b: {...}}` |
| `outcome` | enum (`battle_outcome`) | decisive_victory, pyrrhic, draw, etc. |
| `victor_side` | text | 'side_a' or 'side_b' |
| `casualties` | JSONB | Per-side breakdown |
| `tactical_notes` | text | Notable tactics, terrain factors |

**Key relationships:** `part_of` (Event War), `fought_at` (City/location), `commanded_by` (Person), `participated_in` (Military Unit)

---

### 4.16 Event — Treaty / Agreement

**entity_type:** `event_treaty`
**entity_group:** `EVENT`

| Field | Type | Notes |
|-------|------|-------|
| `treaty_subtype` | enum | peace, alliance, trade, marriage, etc. |
| `signatories` | JSONB | `[{political_entity_id, role}]` |
| `negotiators` | JSONB | `[{person_id, representing}]` |
| `key_provisions` | text | |
| `territorial_terms` | JSONB | `[{region, from_entity, to_entity}]` |
| `duration` | text | If temporary |
| `compliance_history` | JSONB | `[{date, event, description}]` |
| `termination_date` | text (EDTF) | |
| `termination_reason` | text | |

**Key relationships:** `signed_by` (Political Entity), `negotiated_by` (Person), `ended` (Event War), `violated_by` (Political Entity), `created` (Diplomatic Relationship)

---

### 4.17 Event — Revolution / Rebellion / Coup

**entity_type:** `event_rebellion`
**entity_group:** `EVENT`

| Field | Type | Notes |
|-------|------|-------|
| `rebellion_subtype` | enum | revolution, coup, peasant uprising, etc. |
| `target_government` | UUID (FK) | Political Entity being challenged |
| `rebel_leaders` | JSONB | `[{person_id, role}]` |
| `factions` | JSONB | `[{name, composition, social_class_id}]` |
| `external_supporters` | JSONB | `[{political_entity_id, support_type}]` |
| `causes` | text[] | Grievances and triggers |
| `outcome` | text | success, failure, partial, ongoing |
| `government_change` | text | New regime type if successful |
| `casualties` | JSONB | |
| `repression` | text | Post-event reprisals |

**Key relationships:** `within` (Political Entity), `led_by` (Person), `caused_by` (Famine, War, Reform failure), `resulted_in` (New Political Entity, Government change)

---

### 4.18 Event — Natural Disaster

**entity_type:** `event_natural_disaster`
**entity_group:** `EVENT`

| Field | Type | Notes |
|-------|------|-------|
| `disaster_subtype` | enum | earthquake, volcanic, flood, drought, etc. |
| `estimated_deaths` | JSONB | `{min, max, source}` |
| `economic_damage` | text | |
| `affected_entities` | JSONB | `[{political_entity_id, severity}]` |
| `infrastructure_destroyed` | JSONB | `[{entity_id, damage_level}]` |
| `societal_response` | text | |
| `long_term_consequences` | text | |

**Key relationships:** `affected` (Political Entity, City), `destroyed` (Infrastructure Monument), `caused` (Migration, Famine, Rebellion), `worsened_by` (pre-existing conditions)

---

### 4.19 Event — Technology Adoption

**entity_type:** `event_tech_adoption`
**entity_group:** `EVENT`

| Field | Type | Notes |
|-------|------|-------|
| `technology_id` | UUID (FK) | Link to Technology entity |
| `adopting_entity` | UUID (FK) | Political Entity |
| `acquisition_method` | text | independent invention, trade, conquest, espionage |
| `adaptation_notes` | text | Local modifications |
| `impact` | text | Military, economic, social effects |
| `diffusion_speed` | text | rapid, gradual, incomplete |

---

### 4.20 Event — Legal / Institutional Reform

**entity_type:** `event_legal_reform`
**entity_group:** `EVENT`

| Field | Type | Notes |
|-------|------|-------|
| `reform_subtype` | enum | legal_code, taxation, military, land, etc. |
| `enacting_entity` | UUID (FK) | Political Entity |
| `key_figures` | JSONB | `[{person_id, role}]` |
| `provisions` | text | Content of reform |
| `motivation` | text | Crisis response, ideology, external pressure |
| `longevity` | text | How long it lasted |
| `effects_intended` | text | |
| `effects_unintended` | text | |
| `reversal_date` | text (EDTF) | If later reversed |

---

### 4.21 Epidemic / Disease *(NEW)*

**entity_type:** `epidemic_disease`
**entity_group:** `EVENT`

| Field | Type | Notes |
|-------|------|-------|
| `epidemic_subtype` | enum | plague_bacterial, smallpox, cholera, etc. |
| `severity` | enum | local, regional, pandemic |
| `estimated_deaths` | JSONB | `{min, max, percentage_of_population, source}` |
| `spread_timeline` | JSONB | `[{region, arrival_date, peak_date, end_date}]` — wavefront |
| `spread_vector` | text | trade routes, military campaigns, fleas/rats, waterborne |
| `origin_location` | UUID (FK) | City or region of first outbreak |
| `affected_trade_routes` | JSONB | `[{route_id, disruption_level}]` |
| `demographic_impact` | JSONB | `[{region, population_loss_pct, recovery_years}]` |
| `societal_responses` | text | quarantine, scapegoating, religious interpretation |
| `economic_consequences` | text | labor shortages, price changes, land redistribution |
| `recurrence_pattern` | JSONB | `[{date, severity}]` — plague often returned in waves |

**Key relationships:** `spread_via` (Trade Route), `affected` (Political Entity, City), `caused` (Migration, Labor shortage → Reform), `worsened_by` (War, Famine)

**Design rationale:** Epidemics differ fundamentally from natural disasters in that they spread geographically over time following trade and military networks. On the map, a natural disaster is a single marker; an epidemic is an animated wavefront. The Justinianic Plague, Black Death, and Columbian Exchange diseases are among the most historically consequential phenomena the atlas could visualize.

---

### 4.22 Diplomatic Relationship / Alliance *(NEW)*

**entity_type:** `diplomatic_relationship`
**entity_group:** `POLITY`

| Field | Type | Notes |
|-------|------|-------|
| `diplomatic_status` | enum | alliance, vassalage, tributary, trade_agreement, etc. |
| `party_a` | UUID (FK) | Political Entity |
| `party_b` | UUID (FK) | Political Entity |
| `terms` | text | Key provisions |
| `originating_treaty` | UUID (FK) | Event Treaty that established this relationship |
| `power_asymmetry` | text | Which party dominates, if any |
| `tribute_details` | JSONB | `{direction, amount, commodity, frequency}` |
| `military_obligations` | text | Mutual defense, troop contribution, etc. |
| `violations` | JSONB | `[{date, violator, description, consequence}]` |
| `termination_cause` | text | War, treaty revision, political collapse |

**Key relationships:** `between` (Political Entity, Political Entity), `created_by` (Event Treaty), `violated_by` (Political Entity), `terminated_by` (Event War), `mediated_by` (Person, Political Entity)

**Design rationale:** Rome II's diplomacy panel tracks ongoing relationships (allied, at war, trade agreement, vassal) as persistent states, not just the treaty event that created them. This entity captures the *state* while Event Treaty captures the *moment of creation*. A user clicking on the Roman-Parthian relationship sees: formed by Treaty of X, terms included Y, violated in Z CE, dissolved when war broke out.

---

### 4.23 Migration / Population Movement

**entity_type:** `migration`
**entity_group:** `EVENT`

| Field | Type | Notes |
|-------|------|-------|
| `migration_subtype` | enum | invasion, colonization, refugee, economic, etc. |
| `origin_regions` | JSONB | `[{location, entity_id}]` |
| `destination_regions` | JSONB | `[{location, entity_id}]` |
| `migrating_group` | text | Ethnic/tribal group, social class, etc. |
| `population_estimate` | JSONB | `{min, max, source}` |
| `route` | JSONB | `[{waypoint, date}]` — migration path |
| `push_factors` | text[] | invasion, famine, persecution, etc. |
| `pull_factors` | text[] | economic opportunity, empty land, invitation |
| `voluntary` | boolean | |
| `casualties_during` | text | Losses during migration |
| `impact_origin` | text | Depopulation, power vacuum |
| `impact_destination` | text | Displacement, cultural mixing, new polities |

---

### 4.24 Social Class / Group

**entity_type:** `social_class`
**entity_group:** `POLITY`

| Field | Type | Notes |
|-------|------|-------|
| `class_subtype` | enum | nobility, clergy, peasantry, slave, etc. |
| `political_entity_id` | UUID (FK) | Which polity this class exists in |
| `population_proportion` | JSONB | `[{percentage, year, source}]` |
| `economic_role` | text | |
| `legal_status` | text | Rights, restrictions |
| `political_power` | text | Access to governance |
| `social_mobility` | text | Can members rise/fall? |
| `military_obligation` | text | Required, forbidden, optional |
| `education_access` | text | |

---

### 4.25 Cultural / Artistic Work

**entity_type:** `cultural_work`
**entity_group:** `CULTURE`

| Field | Type | Notes |
|-------|------|-------|
| `work_subtype` | enum | literary_text, building, sculpture, mosaic, etc. |
| `creator_id` | UUID (FK) | Person |
| `patron_id` | UUID (FK) | Person or Political Entity who commissioned it |
| `language_id` | UUID (FK) | If textual |
| `medium_materials` | text[] | |
| `themes` | text[] | |
| `style_genre` | text | |
| `preservation_status` | text | extant, fragments, lost, reconstructed, copies_only |
| `current_location` | text | Museum, archive, in situ |
| `influence_description` | text | How it influenced later works |

---

### 4.26 Intellectual / Artistic Movement

**entity_type:** `intellectual_movement`
**entity_group:** `CULTURE`

| Field | Type | Notes |
|-------|------|-------|
| `movement_subtype` | enum | philosophical, artistic, literary, scientific, etc. |
| `founders` | JSONB | `[{person_id}]` |
| `core_ideas` | text | |
| `methodology` | text | If intellectual |
| `style_characteristics` | text | If artistic |
| `geographic_centers` | JSONB | `[{city_id, period}]` |
| `major_works` | JSONB | `[{cultural_work_id}]` |
| `opposition` | JSONB | `[{movement_id, nature}]` — competing movements |

---

### 4.27 Archaeological Culture

**entity_type:** `archaeological_culture`
**entity_group:** `CULTURE`

| Field | Type | Notes |
|-------|------|-------|
| `material_markers` | text[] | pottery styles, burial practices, building types |
| `technology_level` | text | |
| `economic_base` | text | |
| `settlement_patterns` | text | |
| `burial_practices` | text | |
| `type_sites` | JSONB | `[{name, location, excavation_date}]` |
| `hypothesized_ethnicity` | text | Often debated |
| `hypothesized_language` | UUID (FK) | Often uncertain |
| `evidence_quality` | text | |

---

### 4.28 Language / Linguistic Group

**entity_type:** `language`
**entity_group:** `CULTURE`

| Field | Type | Notes |
|-------|------|-------|
| `language_family` | text | Indo-European, Semitic, Sino-Tibetan, etc. |
| `language_status` | enum | living, extinct, liturgical_only, etc. |
| `writing_system` | text | |
| `speaker_estimates` | JSONB | `[{count, year, source}]` |
| `roles` | JSONB | `[{role: enum, political_entity_id, period}]` — vernacular, admin, liturgical |
| `descended_from` | UUID (FK) | Parent language |
| `iso_639_code` | text | If standardized |

---

### 4.29 Religious Text / Sacred Object

**entity_type:** `religious_text`
**entity_group:** `CULTURE`

| Field | Type | Notes |
|-------|------|-------|
| `text_type` | text | scripture, commentary, relic, artifact |
| `composition_date` | text (EDTF) | Often disputed |
| `authors` | JSONB | `[{person_id, role}]` — if known |
| `language_id` | UUID (FK) | |
| `canonical_status` | JSONB | `[{religious_movement_id, status}]` — canonical, apocryphal, etc. |
| `genre` | text | mythology, law, prophecy, wisdom, history |
| `translation_history` | JSONB | `[{language_id, date, translator_id}]` |
| `material` | text | If physical object |
| `veneration_sites` | JSONB | `[{city_id, description}]` |

---

### 4.30 Legal Code / Constitutional Document

**entity_type:** `legal_code`
**entity_group:** `CULTURE`

| Field | Type | Notes |
|-------|------|-------|
| `promulgation_date` | text (EDTF) | |
| `promulgator_id` | UUID (FK) | Person or Political Entity |
| `governing_entity` | UUID (FK) | Political Entity it applied to |
| `language_id` | UUID (FK) | |
| `key_provisions` | text | property, criminal, family, constitutional |
| `legal_philosophy` | text | |
| `enforcement_duration` | text | |
| `amendments` | JSONB | `[{date, description}]` |
| `influenced_by` | JSONB | `[{legal_code_id, description}]` — legal reception |
| `influenced` | JSONB | `[{legal_code_id, description}]` |
| `modern_significance` | text | |

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
  temporal_start    TEXT,                          -- EDTF
  temporal_end      TEXT,                          -- EDTF
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
