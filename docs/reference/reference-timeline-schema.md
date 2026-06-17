# Reference Timeline Schema

> Status: proposed, not implemented.

Current live state:

- The repo has reference-table listing endpoints under admin web routes and a generic `GET /api/v1/reference/{table}` endpoint.
- The repo does not currently have an `entity_ref_links` table.
- The repo does not currently expose `GET /reference/{ref_type}/{id}/timeline`.
- There is no reference-specific timeline projection in the live codebase.

Use this file as a design note for a future reference-timeline feature, not as a description of working schema or API.

---

## 1. Intended Purpose

If implemented, this feature would allow abstract reference rows such as religious traditions or historical periods to gather linked entities and events into a lightweight timeline view.

---

## 2. Proposed Data Model

### Bridge table: `entity_ref_links`

Proposed responsibilities:

- link entities or events to a reference-table row
- support multiple reference domains through `ref_type`
- provide optional link semantics such as `primary` or `related`

Proposed fields:

- `id`
- `entity_id`
- `ref_type`
- `ref_id`
- `link_type`
- `created_at`
- `updated_at`

Proposed indexes:

- composite index on (`ref_type`, `ref_id`)
- index on `entity_id`

---

## 3. Proposed API

### Endpoint

- `GET /reference/{ref_type}/{id}/timeline`

### Expected response shape

```json
{
  "ref": {},
  "timeline": [
    {
      "entity_id": "uuid",
      "title": "Council of Nicaea",
      "date": "0325-06-19",
      "impact_score": 98,
      "summary": "...",
      "geometry": null,
      "links": []
    }
  ]
}
```

Possible query parameters if this is built:

- `min_impact`
- `verified`
- `limit`

---

## 4. Proposed Construction Logic

1. Resolve all linked entity IDs from `entity_ref_links`.
2. Join against canonical entity read data.
3. Order by date or impact.
4. Optionally enrich with related links and geometry.

---

## 5. Editorial Intent

The original idea here was an editorially light timeline built from explicit links rather than a second curated reference narrative layer.

That idea is still reasonable, but it remains future work until the backing table and endpoint exist.
