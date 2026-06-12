# Entity Model — Current Diagrams

> Status: current live model.
> This file replaces older diagrams that mixed historical planning material with removed columns such as direct entity-level temporal/location fields and `geometry_snapshots`.

Visual diagrams below are intentionally simplified to the live canonical structures that matter today.

---

## 1. Canonical Write Model

```mermaid
erDiagram
    entities {
        uuid entity_id PK
        text name
        entity_type entity_type
        entity_group entity_group
        text wikidata_id
        text summary
        text significance
        integer impact_score
        jsonb attributes
        verification_status verification_status
        confidence_level confidence
        date_resolution_method date_method
        confidence_level date_confidence
        duration_type duration_type
        location_resolution_method location_method
        confidence_level location_confidence
        icon_class icon_class
        integer display_priority
        jsonb source_citations
        vector embedding
        uuid primary_geo_ref_id FK
        bigint reviewer_id FK
        timestamp review_date
        text created_by
        timestamp created_at
        timestamp updated_at
    }

    entity_aliases {
        uuid alias_id PK
        uuid entity_id FK
        text name
        text language
        text source
        boolean is_primary
    }

    entity_tags {
        uuid entity_tag_id PK
        uuid entity_id FK
        text tag
    }

    entity_temporal_ranges {
        uuid temporal_range_id PK
        uuid entity_id FK
        text range_type
        integer start_year
        integer end_year
        text start_date
        text end_date
        text duration_type
        text date_method
        text date_confidence
        boolean is_primary
        text notes
    }

    entity_locations {
        uuid location_id PK
        uuid entity_id FK
        text location_name
        geometry geom
        geometry territory_geom
        text location_method
        text location_confidence
        boolean is_primary
        text notes
    }

    entity_geo_refs {
        uuid geo_ref_id PK
        uuid entity_id FK
        geo_ref_provider provider
        geo_ref_external_type external_type
        text external_id
        geo_ref_match_role match_role
        geo_ref_retrieval_method retrieval_method
        text temporal_start
        text temporal_end
        integer temporal_start_year
        integer temporal_end_year
        jsonb external_tags
        jsonb source_meta
        decimal match_score
        boolean is_active
    }

    relationships {
        uuid relationship_id PK
        uuid source_entity_id FK
        uuid target_entity_id FK
        relationship_type relationship_type
        text temporal_start
        text temporal_end
        integer start_year
        integer end_year
        text description
        confidence_level confidence
        jsonb source_citations
        boolean derive_geometry_period
        text created_by
        timestamp created_at
    }

    geometry_periods {
        uuid geometry_period_id PK
        uuid entity_id FK
        text period_type
        integer start_year
        integer end_year
        geometry geom
        geometry territory_geom
        text description
        text provenance_mode
        uuid relationship_id FK
        uuid source_event_id FK
        confidence_level confidence
        text created_by
        timestamp created_at
        timestamp updated_at
    }

    entities ||--o{ entity_aliases : aliases
    entities ||--o{ entity_tags : tags
    entities ||--o{ entity_temporal_ranges : temporal_ranges
    entities ||--o{ entity_locations : locations
    entities ||--o{ entity_geo_refs : geo_refs
    entities ||--o{ geometry_periods : geometry_periods
    entities ||--o{ relationships : outgoing
    entities ||--o{ relationships : incoming
    entities ||--o| entity_geo_refs : primary_geo_ref_id
    relationships ||--o{ geometry_periods : derived_presence_source
    entities ||--o{ geometry_periods : source_event_id
```

### Notes

- `entities` is intentionally lean compared with earlier drafts.
- Aliases, tags, dates, and base locations are normalized into their own tables.
- `geometry_periods` is the live time-varying geometry table.
- `geometry_snapshots` is not part of the current model.
- `provenance_mode` in the live database includes `manual`, `derived`, and `ohm_import`.

---

## 2. Read Model and Timeline Projection

```mermaid
erDiagram
    entity_timeline_entries {
        uuid timeline_entry_id PK
        uuid entity_id FK
        text entry_kind
        integer start_year
        integer end_year
        text title
        text description
        uuid location_entity_id FK
        geometry geom
        geometry territory_geom
        text source_table
        uuid source_id
        text relationship_type
        uuid related_entity_id FK
        text related_entity_name
        timestamp derived_at
    }

    entities ||--o{ entity_timeline_entries : timeline_entries
```

```mermaid
flowchart TD
    A[Canonical tables] --> B[ProjectEntityTimelineAction]
    A1[geometry_periods] --> B
    A2[relationships] --> B
    A3[entity_temporal_ranges] --> B
    B --> C[entity_timeline_entries]
    C --> D[Entity history panel]
    C --> E[Timeline/map read models]
```

### Projection behavior

- `geometry_periods` is the preferred source for time-scoped spatial timeline rows.
- `relationships` can contribute timeline rows even when no geometry period exists.
- `entity_temporal_ranges` is the fallback source when richer timeline inputs are absent.
- `entity_timeline_entries` is rebuildable derived data, not hand-authored truth.

---

## 3. Base Geometry vs Time-Varying Geometry

```mermaid
flowchart TD
    A[Entity] --> B[Primary entity_locations row]
    A --> C[Zero or more geometry_periods rows]
    B --> D[Default map placement]
    C --> E[Year-specific map geometry]
    E --> F{Matching requested year?}
    F -- yes --> G[Use geometry_period]
    F -- no --> H[Fallback to primary location]
```

### Practical rule

- `entity_locations` answers: where is this entity by default?
- `geometry_periods` answers: where was this entity during a specific period, and why?

---

## 4. Georef Attachment Model

```mermaid
flowchart TD
    A[Entity created or edited] --> B{Resolvable external geography?}
    B -- yes --> C[Attach entity_geo_ref]
    C --> D[Mark one active primary georef]
    D --> E[Hydrate primary entity_locations geometry]
    E --> F[Optional manual refinement in map editor]
    B -- no --> G[Leave geometry unresolved or enter manually]
```

### Georef notes

- `entity_geo_refs` stores provider-native identifiers and match metadata.
- `entities.primary_geo_ref_id` points to the default active external anchor.
- Base geometry hydration flows into `entity_locations`, not a legacy entity-level geometry column.

---

## 5. Relationship-Derived Presence Periods

```mermaid
flowchart TD
    A[Relationship saved] --> B{derive_geometry_period = true?}
    B -- no --> C[No derived geometry period]
    B -- yes --> D{Supported relationship type?}
    D -- no --> C
    D -- yes --> E[Resolve source or target location geometry]
    E --> F[Create or update presence geometry_period]
    F --> G[Link row back to relationship_id]
```

Current supported auto-presence relationship types are implemented in `CreateDerivedPresencePeriodAction`.
They currently include:

- `FoughtAt`
- `SignedBy`
- `BornIn`
- `DiedIn`
- `ResidedIn`

---

## 6. Chronicle Subsystem

Chronicles (added June 2026) are an ordered narrative layer over entities and relationships. They live in their own
tables and are not part of the `entities` row. See [attributes.md](./attributes.md) §6 for field-level detail.

```mermaid
erDiagram
    chronicles {
        uuid chronicle_id PK
        text title
        text slug
        source_type source_type
        text source_reference
        chronicle_status status
        integer start_year
        integer end_year
        integer impact_score
        jsonb approximate_location
        jsonb metadata
    }

    chronicle_entries {
        uuid entry_id PK
        uuid chronicle_id FK
        integer sequence_order
        text narrative_text
        text notes
        text source_evidence
        uuid primary_relationship_id FK
        integer start_year
        integer end_year
        integer impact_score
        jsonb approximate_location
    }

    chronicle_entry_entities {
        uuid entry_id PK,FK
        uuid entity_id PK,FK
        text role
        integer sequence_in_entry
    }

    chronicles ||--o{ chronicle_entries : entries
    chronicle_entries ||--o{ chronicle_entry_entities : secondary_entities
    chronicle_entries ||--o| relationships : primary_relationship
    chronicle_entry_entities }o--|| entities : references
```

### Notes

- `chronicle_entries.primary_relationship_id` is a `uuid` FK to `relationships`.
- `chronicle_entry_entities` is the many-to-many pivot (composite PK), with a `role` (default `mentioned`).
- There is no `chronicles.description` column.

---

## 7. What Changed From Older Diagrams

The following older ideas are not part of the live canonical schema and should not be copied into new docs:

- direct `alternative_names` and `tags` arrays on `entities`
- direct canonical `temporal_start`, `temporal_end`, `geom`, and `territory_geom` columns on `entities`
- `parent_entity_id` and `successor_entity_id` as active live entity columns
- `confidence_breakdown`, `relationship_summary`, `nearby_entity_count`, `cluster_id`, and `embedding_version`
- `geometry_snapshots`

If a payload still exposes helper names like `temporal_start`, `location_name`, or `geojson`, treat those as controller-level conveniences backed by normalized tables.
