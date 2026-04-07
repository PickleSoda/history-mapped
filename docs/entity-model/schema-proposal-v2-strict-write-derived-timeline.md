# Entity Model V2 Proposal — Strict Write Model + Derived Timeline

Status: Proposal
Date: 2026-04-06

## Why This Proposal

Current modeling mixes two concerns:
- historical facts (authoritative)
- presentation-oriented timeline rendering for maps/timelines

This proposal separates them.

- Write model is strict and normalized.
- Timeline is derived and non-authoritative.
- Manual geometry periods are explicitly constrained.

---

## 1. Strict Normalized Write Model

### 1.1 Design Principles

1. Store each historical fact once.
2. Do not allow independently authored presentation-only geometry records.
3. Keep `entities` lean and query-critical.
4. Move multi-valued and fast-changing fields to dedicated tables.
5. Keep JSONB only for type-specific spillover, not core filters.

### 1.2 Canonical Tables

### `entities` (lean, canonical identity)

Required core columns:
- `entity_id uuid pk`
- `entity_type entity_type not null`
- `entity_group entity_group not null`
- `name text not null`
- `wikidata_id text null`
- `summary text null`
- `significance text null`
- `verification_status verification_status not null default 'pipeline_draft'`
- `confidence confidence_level null`
- `confidence_notes text null`
- `parent_entity_id uuid null`
- `successor_entity_id uuid null`
- `reviewer_id bigint null`
- `review_date timestamp null`
- `created_by text null`
- `created_at timestamp not null`
- `updated_at timestamp not null`

Optional but controlled JSONB:
- `attributes jsonb not null default '{}'`

Rule for `attributes`:
- Allowed only for type-specific fields not worth first-class columns yet.
- Disallowed for core filter/sort fields (time, space, confidence, verification, names, relationship semantics).

### `entity_aliases` (normalized multi-name support)

- `alias_id uuid pk`
- `entity_id uuid fk -> entities`
- `name text not null`
- `language_code text null`
- `script text null`
- `is_primary boolean not null default false`
- `source_citation_id uuid null`
- unique constraint recommendation: `(entity_id, name)`

### `entity_tags`

- `entity_id uuid fk -> entities`
- `tag text not null`
- pk `(entity_id, tag)`

### `entity_temporal_ranges`

- `range_id uuid pk`
- `entity_id uuid fk -> entities`
- `start_year int null`
- `end_year int null`
- `duration_type duration_type null`
- `date_raw text null`
- `date_method date_resolution_method null`
- `date_confidence confidence_level null`
- `era_label text null`
- `is_primary boolean not null default true`
- check: `start_year is null or end_year is null or start_year <= end_year`

### `entity_locations` (base non-period location facts)

- `location_id uuid pk`
- `entity_id uuid fk -> entities`
- `location_name text null`
- `geom geometry null`
- `territory_geom geometry null`
- `location_method location_resolution_method null`
- `location_confidence confidence_level null`
- `is_primary boolean not null default true`
- check: `geom is not null or territory_geom is not null`

### `relationships` (already canonical edge model)

Keep as canonical relation fact table (current design direction is correct).

### `geometry_periods` (time-varying geometry facts only)

This replaces broad legacy temporal-geometry usage with stricter semantics.

- `geometry_period_id uuid pk`
- `entity_id uuid fk -> entities`
- `period_type text not null`  
  allowed values recommendation: `territory`, `route`, `spread_zone`, `movement_path`, `presence`
- `start_year int not null`
- `end_year int not null`
- `geom geometry null`
- `territory_geom geometry null`
- `confidence confidence_level null`
- `description text null`
- `provenance_mode text not null`  
  allowed values: `derived`, `manual`
- `relationship_id uuid null fk -> relationships`
- `source_event_id uuid null fk -> entities`
- `created_by text null`
- `created_at timestamp not null`
- `updated_at timestamp not null`

Hard checks:
- `start_year <= end_year`
- `geom is not null or territory_geom is not null`
- `provenance_mode in ('derived','manual')`
- if `provenance_mode='derived'` then at least one of `relationship_id`, `source_event_id` is required
- if `period_type='presence'` then `relationship_id` is required
- if `period_type='territory'` then `source_event_id` is recommended; allow null only with explicit manual justification

### `citations` + link tables

Normalize citations so facts can be cited independently:
- `citations`
- `entity_citations`
- `relationship_citations`
- `geometry_period_citations`

This removes heavy `source_citations` JSONB from high-write tables.

### 1.3 JSONB On `entities` vs Separate Tables

Your intuition is right: JSONB directly on `entities` is convenient but becomes expensive for filtering, constraints, and indexes.

Recommendation:
- Keep exactly one controlled JSONB (`attributes`) for type-specific long-tail fields.
- Everything frequently queried should be relational columns/tables.
- Use generated/materialized helpers only for read-side acceleration.

Good JSONB use:
- rare, type-specific payloads
- descriptive metadata not used in WHERE/JOIN heavily

Bad JSONB use:
- year filters
- map/time queries
- confidence/status filters
- relationship semantics

---

## 2. Derived Timeline Model (Read Model)

### 2.1 Purpose

Provide fast timeline playback and UI display without weakening write-model strictness.

### 2.2 `entity_timeline_entries` (projection table or materialized view)

- `timeline_entry_id uuid pk`
- `entity_id uuid not null`
- `entry_kind text not null`  
  examples: `relationship_presence`, `territory_phase`, `event_phase`, `residence`, `campaign_step`
- `start_year int not null`
- `end_year int not null`
- `title text not null`
- `description text null`
- `location_entity_id uuid null`
- `geom geometry null`
- `territory_geom geometry null`
- `source_table text not null`  
  values: `relationships`, `geometry_periods`, `entity_temporal_ranges`
- `source_id uuid not null`
- `derived_at timestamp not null`

Rules:
- No direct manual writes from admin UI.
- Rebuilt by projection job/command.
- Safe to truncate and regenerate.

### 2.3 Projection Inputs

Timeline entries are generated from:
- `relationships` (especially participation/presence edges)
- `geometry_periods` (territory/route/spread changes)
- `entity_temporal_ranges` (fallback life span or period spans)

This keeps timeline expressive while preserving normalization.

---

## 3. Manual Geometry Period Rules

## 3.1 Allowed (manual entry permitted)

Manual `geometry_periods` are allowed when all conditions hold:

1. Geometry is a first-class historical fact (not just a display note).
2. No reliable machine-derivable source exists from relationships alone.
3. Period has explicit time bounds (`start_year`, `end_year`).
4. At least one citation is attached.
5. `description` explains what changed and why this period exists.

Typical allowed cases:
- polity border change after conquest/treaty
- trade route path shift by era
- epidemic spread zone by period
- migration corridor by period
- archaeological culture extent by period

## 3.2 Forbidden (manual entry must be rejected)

Manual `geometry_periods` are forbidden when any of these are true:

1. Entry has no geometry (`geom` and `territory_geom` both null).
2. Fact is already representable by a relationship and should be derived.
3. Entry is only narrative text with no spatial meaning.
4. Entry duplicates an existing period with materially same geometry and years.
5. Presence-type period lacks a backing relationship.

Typical forbidden cases:
- "Person attended treaty" entered manually as a free geometry row without relationship.
- "Battle happened" as timeline-only text in geometry table.
- arbitrary map markers for storytelling convenience.

## 3.3 Enforcement (DB + app)

Enforce at two layers:

DB constraints:
- geometry required
- temporal validity
- provenance constraints by `period_type`

Application policy checks:
- block forbidden scenarios with explicit validation messages
- require citation count >= 1 for manual periods
- require justification text for manual entries not tied to event/relationship

---

## 4. Revised Entity Columns (Lean vs Move vs Drop)

This maps current `entities` columns to V2 decisions.

## Keep in `entities`

- `entity_id`, `entity_type`, `entity_group`, `name`, `wikidata_id`
- `summary`, `significance`
- `verification_status`, `confidence`, `confidence_notes`
- `parent_entity_id`, `successor_entity_id`
- `reviewer_id`, `review_date`, `created_by`, `created_at`, `updated_at`
- `attributes` (strictly controlled JSONB)

## Move out of `entities` (normalize)

- `alternative_names` -> `entity_aliases`
- `tags` -> `entity_tags`
- `temporal_start`, `temporal_end`, `date_raw`, `date_method`, `date_confidence`, `duration_type`, `era_label` -> `entity_temporal_ranges`
- `geom`, `territory_geom`, `location_name`, `location_confidence`, `location_method` -> `entity_locations` and `geometry_periods`
- `source_citations` -> citation link tables
- `validation_flags` -> `entity_flags` (optional table)
- `media_refs` -> `entity_media_refs` (optional table)
- `embedding`, `embedding_version` -> `entity_embeddings`

## Drop from write-model core (derive instead)

- `relationship_summary`
- `nearby_entity_count`
- `cluster_id`
- `source_diversity_score`
- `confidence_breakdown`
- `temporal_display_range`

Note:
- `impact_score`, `display_priority`, `icon_class`, `entity_color` are presentation/ranking concerns.
- Keep them in a dedicated read/presentation table if still needed for UI.

---

## 5. ACID and Normalization Outcome

With this split:
- Write transactions remain ACID on canonical facts.
- Timeline data becomes rebuildable projection data.
- Update anomalies from dual fact storage are removed.
- Query performance improves by indexing normalized columns/tables and keeping JSONB limited.

In short: strict source-of-truth on write side, flexible timeline UX on read side.
