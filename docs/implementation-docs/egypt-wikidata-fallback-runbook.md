# Egypt Wikidata Fallback Runbook

## Purpose

Build a curated-seed Wikidata fallback for Egypt that bypasses OHM discovery, emits generic importer-ready entities, and coexists with the existing OHM collection workflow.

## When to use

- OHM data for Egypt is incomplete or missing
- You need a quick, high-confidence Egypt entity set for testing or staging
- You want to supplement (not replace) the OHM-based Egypt collection

## Prerequisites

- Python 3.10+ with pipeline dependencies installed
- `pipeline/.env` configured (or default settings acceptable)
- Docker Compose running for Laravel import

## Workflow

### 1. Build the collection

```powershell
py -m pipeline collections egypt-wikidata-build --run-id egypt-wikidata-2026 --force
```

This:
1. Loads the curated seed set from `pipeline/wikidata/collections/seed_sets/egypt.json`
2. Fetches full Wikidata metadata for each seed QID
3. Maps through `EntityMapper` to history-mapped schema
4. Applies bounded expansion via relationship hints (unless `--no-expansion`)
5. Deduplicates and writes artifacts

### 2. Verify output layout

```powershell
Get-ChildItem output/wikidata_collections/egypt-wikidata-2026/ -Recurse
```

Expected:
- `entities_final/egypt_collection.jsonl` — importer-ready entities
- `reports/included.jsonl` — inclusion audit trail
- `reports/excluded.jsonl` — excluded items (usually empty for seed-only)
- `manifest.json` — run metadata

No `borders_final/` directory is created.

### 3. Import into Laravel

```bash
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:import /var/www/html/storage/app/imports/egypt-wikidata-2026/entities_final/egypt_collection.jsonl --sync --force --batch-id=egypt-wikidata-2026
```

The generic importer accepts these records without OHM border metadata.

### 4. Resolve relationships

```bash
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:resolve-relationships egypt-wikidata-2026 --sync
```

### 5. Verify

```bash
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:report-relationship-hints egypt-wikidata-2026
```

## Seed set curation

The default seed set lives at `pipeline/wikidata/collections/seed_sets/egypt.json`. Each entry:

```json
{
  "qid": "Q79",
  "category": "modern_state",
  "label": "Egypt",
  "notes": "Modern Arab Republic of Egypt",
  "expand": true
}
```

- `qid` — Wikidata QID (required)
- `category` — maps to entity_type via `CATEGORY_TO_ENTITY_TYPE`
- `label` — human-readable label for audit
- `notes` — optional operator notes
- `expand` — whether to follow relationship hints from this seed

To use a custom seed file:

```powershell
py -m pipeline collections egypt-wikidata-build --run-id my-egypt --seed-file my_seeds.json --no-expansion
```

## Bounded expansion

By default, the pipeline collects `target_wikidata_id` values from `_relationship_hints` of fetched seeds and attempts to fetch them. Only entities linked to Egypt (via P17/P30/P131/P276) are included. This prevents "British Empire" or "France" from leaking into the collection.

Use `--no-expansion` to skip this step and import only the exact seed set.

## Troubleshooting

### "No entities fetched"
- Check internet connectivity
- Verify QIDs in seed set are valid
- Check `pipeline/.env` for Wikidata API rate limits

### "Expansion included non-Egypt entities"
- The Egypt domain filter checks P17/P30/P131/P276. Some entities may slip through if Wikidata claims are sparse.
- Review `reports/included.jsonl` and add unwanted QIDs to an exclusion list (future enhancement).

### Import fails with schema errors
- Ensure Laravel is on the latest migration
- Check that `entities_final/egypt_collection.jsonl` contains valid JSON lines

## Coexistence with OHM workflow

The Wikidata fallback output goes to `output/wikidata_collections/<run_id>/`, separate from `output/ohm_collections/<run_id>/`. You can import both and deduplicate at the database level.

## See also

- [data_pipeline_architecture.md](../../docs/implementation-docs/data_pipeline_architecture.md)
- [data-contributor-guide.md](../../docs/implementation-docs/data-contributor-guide.md)
