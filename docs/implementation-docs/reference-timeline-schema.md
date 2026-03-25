# Reference Timeline Implementation Schema

## 1. Purpose
Enable timeline construction for abstract concepts (e.g., religious traditions, historical periods) using reference tables as anchors and linked entities/events as timeline nodes.

---

## 2. Database Schema

### a. Bridge Table: `entity_ref_links`
- **Purpose:** Link entities/events to reference table rows (e.g., a battle to a religious tradition or period).
- **Fields:**
  - `id` (PK)
  - `entity_id` (FK → entities)
  - `ref_type` (enum: 'religious_tradition', 'historical_period', etc.)
  - `ref_id` (FK → ref table, e.g., `religious_tradition_id`)
  - `link_type` (optional: 'primary', 'related', etc.)
  - `created_at`, `updated_at`

### b. Indexes
- Composite index on (`ref_type`, `ref_id`)
- Index on `entity_id`

---

## 3. API Contract

### Endpoint
- `GET /reference/{ref_type}/{id}/timeline`

### Response
```json
{
  "ref": { /* reference table row */ },
  "timeline": [
    {
      "entity_id": 123,
      "title": "Council of Nicaea",
      "date": "0325-06-19",
      "impact_score": 0.98,
      "summary": "...",
      "geometry": { /* optional, if spatial */ },
      "links": [ /* related entities/events */ ]
    }
    // ...
  ]
}
```

### Query Params
- `?min_impact=0.5` (filter by impact score)
- `?verified=true` (filter by verification status)
- `?limit=100` (pagination)

---

## 4. Timeline Construction Logic
- Select all `entity_id`s linked to the given `ref_type`/`ref_id` via `entity_ref_links`.
- Join with `entities` table for metadata, impact score, and verification.
- Order by date (or impact score, as needed).
- Optionally, include related entities/events for richer context.

---

## 5. Editorial Policy
- Reference timelines are editorially-light: inclusion is based on explicit links and impact score, not manual curation.
- No direct timeline linkage in refs; all timeline nodes are entities/events.
