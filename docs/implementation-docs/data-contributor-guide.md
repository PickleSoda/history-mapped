# Data Contributor Guide

> For operators and contributors who run the pipeline, import data into Laravel, and debug issues.
>
> **Related docs:**
> - `docs/schemas/pipeline-entity-record.md` — canonical JSONL schema
> - `docs/architecture/data-pipeline.md` — pipeline architecture
> - `docs/architecture/ohm-integration.md` — OHM map integration
> - `docs/entity-model/for-geodata-contributors.md` — geodata authoring guide
> - `pipeline/README.md` — pipeline quick start
> - `pipeline/ohm_borders/README.md` — OHM borders runbook
> - `docs/implementation-docs/ohm-egypt-collection-runbook.md` — Egypt collection runbook
> - `docs/implementation-docs/ohm-country-subgraph-runbook.md` — country subgraph runbook

---

## Table of Contents

1. [Entity JSONL Schema](#1-entity-jsonl-schema)
2. [Python Pipeline Commands](#2-python-pipeline-commands)
3. [Laravel Import Commands](#3-laravel-import-commands)
4. [Standard Workflows](#4-standard-workflows)
5. [Debugging and Troubleshooting](#5-debugging-and-troubleshooting)
6. [Quick Reference](#6-quick-reference)

---

## 1. Entity JSONL Schema

Each `.jsonl` file contains one entity per line. The importer skips records missing `name`, `entity_type`, or `entity_group`.

### Minimal record

```json
{
  "name": "Roman Empire",
  "entity_type": "political_entity",
  "entity_group": "POLITY"
}
```

### Full record

```json
{
  "name": "Roman Empire",
  "entity_type": "political_entity",
  "entity_group": "POLITY",
  "wikidata_id": "Q2277",
  "summary": "An imperial polity.",
  "alternative_names": ["Imperium Romanum"],
  "temporal_start": "-0027",
  "temporal_end": "0476",
  "duration_type": "period",
  "geojson": {
    "type": "Point",
    "coordinates": [12.5, 41.9]
  },
  "territory_geojson": {
    "type": "Polygon",
    "coordinates": [[[12.0, 41.0], [13.0, 41.0], [13.0, 42.0], [12.0, 42.0], [12.0, 41.0]]]
  },
  "source_citations": [
    {
      "source_type": "reference",
      "title": "Wikidata:Q2277",
      "url": "https://www.wikidata.org/wiki/Q2277",
      "reliability": "reference"
    }
  ],
  "_relationship_hints": [
    {
      "target_wikidata_id": "Q2277",
      "relationship_type": "preceded_by",
      "temporal_start": "-0027",
      "temporal_end": "0476"
    }
  ],
  "_geo_resolution": {
    "source": "wikidata",
    "lat": 41.9,
    "lon": 12.5
  }
}
```

### Field reference

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Primary display name |
| `entity_type` | Yes | One of the 30 canonical types — see [entity-model/entity-specification.md](../entity-model/entity-specification.md) |
| `entity_group` | Yes | `POLITY`, `PLACE`, `EVENT`, `ECONOMY`, `CULTURE` (the 5 canonical groups) |
| `wikidata_id` | Recommended | `Q12345` format |
| `summary` | Recommended | Short description |
| `alternative_names` | Optional | Array of aliases |
| `temporal_start` / `temporal_end` | Optional | ISO-like strings or signed years |
| `geojson` | Optional | Point GeoJSON for map placement |
| `territory_geojson` | Optional | Polygon/line GeoJSON for territory |
| `source_citations` | Optional | Provenance array |
| `_relationship_hints` | Internal | Staged for relationship resolution |
| `_geo_resolution` | Internal | Pipeline geo metadata |

### Entity types

The 30 canonical `entity_type` values (grouped under the 5 groups above) are defined and kept
current in [entity-model/entity-specification.md](../entity-model/entity-specification.md) §4 — treat
that spec as the single source of truth rather than re-listing them here. Common examples:
`political_entity` / `person` / `dynasty` / `military_unit` (POLITY); `city` / `infrastructure_monument`
(PLACE); `event_war` / `event_battle` / `event_treaty` / `migration` / `epidemic_disease` (EVENT);
`trade_route` / `natural_resource` / `currency_monetary_system` (ECONOMY); and `cultural_work` /
`intellectual_movement` / `religious_movement` / `technology` (CULTURE).

> Historical periods, geographic regions, and bodies of water are **reference-table** records, not
> entities — see [entity-model/reference-tables.md](../entity-model/reference-tables.md). Records the
> pipeline marks as reference data are skipped by the entity importer.

---

## 2. Python Pipeline Commands

All commands run from the repository root.

### Wikidata scraping

```powershell
# Scrape by type
py -m pipeline scrape --type political_entity --limit 100

# Topic BFS walk from a seed
py -m pipeline topic "Late Bronze Age Collapse"

# Deduplicate against DB
py -m pipeline dedup output/political_entity.jsonl --check-db
```

### OHM borders

```powershell
# Full staged run
py -m pipeline borders fetch  --run-id global-2026-04-15
py -m pipeline borders parse  --run-id global-2026-04-15 --resume
py -m pipeline borders enrich --run-id global-2026-04-15 --enrich-names
py -m pipeline borders build  --run-id global-2026-04-15 --resume
py -m pipeline borders relations-run --run-id global-2026-04-15 --resume

# Subgraph extraction (index-first)
py -m pipeline borders build-index --input output/ohm_borders/global-2026-04-15/raw/overpass.json --index-path output/ohm_borders/indexes/global-2026-04-15.sqlite3
py -m pipeline borders extract-subgraph --input output/ohm_borders/global-2026-04-15/raw/overpass.json --index-path output/ohm_borders/indexes/global-2026-04-15.sqlite3 --seed-qid Q2277 --run-id roman-empire --max-depth 3
```

### Egypt historical collection

```powershell
py -m pipeline collections build-xml-index --input output/map.xml --index-path output/ohm_collections/map.sqlite3 --force
py -m pipeline collections egypt-build --xml-index-path output/ohm_collections/map.sqlite3 --ohm-index-path output/ohm_borders/indexes/global-2026-04-14.sqlite3 --run-id egypt-collection --force
py -m pipeline collections egypt-relations-run --run-id egypt-collection --resume
```

---

## 3. Laravel Import Commands

All commands run inside the Docker app container.

### Entity import

```powershell
# Import one file
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:import storage/app/pipeline/political_entity.jsonl --sync --batch-id=my-batch

# Import a directory
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:import storage/app/pipeline/ --all --sync --batch-id=my-batch

# Skip relationship resolution (resolve later)
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:import storage/app/pipeline/ --all --sync --skip-relationships --batch-id=my-batch

# Force overwrite existing entities
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:import storage/app/pipeline/ --all --sync --force --batch-id=my-batch
```

### OHM border import

```powershell
# Import border entities + geometry periods
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:import-borders storage/app/pipeline/ohm_borders.jsonl --sync --batch-id=ohm-borders
```

### OHM relation import

```powershell
# Import relation entities + stage hints + resolve
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:import-border-relations storage/app/pipeline/relations/ --sync --batch-id=ohm-relations

# Skip resolution (resolve later)
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:import-border-relations storage/app/pipeline/relations/ --sync --skip-resolve --batch-id=ohm-relations
```

### Relationship resolution

```powershell
# Resolve all unresolved hints across all batches
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:resolve-relationships

# Resolve one batch
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:resolve-relationships my-batch-id

# Dry-run (preview only)
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:resolve-relationships --dry-run

# Report hint status
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:report-relationship-hints
```

### Embeddings

```powershell
# Generate embeddings for pending entities
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:embeddings --pending --chunk=50
```

### Backfill and rebuild

```powershell
# Backfill canonical tables from legacy columns
docker compose -f docker/docker-compose.yml exec app php artisan entity:backfill

# Rebuild timeline entries
docker compose -f docker/docker-compose.yml exec app php artisan timeline:rebuild
```

---

## 4. Standard Workflows

### Workflow A: Wikidata scrape → import

```powershell
# 1. Scrape
py -m pipeline scrape --type political_entity --limit 500

# 2. Copy artifacts into Laravel storage
Copy-Item output/political_entity.jsonl api/storage/app/pipeline/

# 3. Import
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:import storage/app/pipeline/political_entity.jsonl --sync --batch-id=political-20260602

# 4. Resolve relationships
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:resolve-relationships political-20260602

# 5. Report
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:report-relationship-hints political-20260602
```

### Workflow B: OHM borders → import

```powershell
# 1. Build OHM index
py -m pipeline borders build-index --input output/ohm_borders/global-2026-04-15/raw/overpass.json --index-path output/ohm_borders/indexes/global-2026-04-15.sqlite3

# 2. Extract subgraph
py -m pipeline borders extract-subgraph --index-path output/ohm_borders/indexes/global-2026-04-15.sqlite3 --seed-qid Q2277 --run-id roman-empire

# 3. Run staged pipeline
py -m pipeline borders parse  --run-id roman-empire --resume
py -m pipeline borders enrich --run-id roman-empire --resume
py -m pipeline borders build  --run-id roman-empire --resume
py -m pipeline borders relations-run --run-id roman-empire --resume

# 4. Copy artifacts
New-Item -ItemType Directory -Force api/storage/app/pipeline/roman-empire
Copy-Item output/ohm_borders/roman-empire/borders_final/ohm_borders.jsonl api/storage/app/pipeline/roman-empire/
Copy-Item output/ohm_borders/roman-empire/relations_final/ohm_relation_entities.jsonl api/storage/app/pipeline/roman-empire/
Copy-Item output/ohm_borders/roman-empire/relations_final/ohm_relation_hints.jsonl api/storage/app/pipeline/roman-empire/

# 5. Import borders
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:import-borders storage/app/pipeline/roman-empire/ohm_borders.jsonl --sync --batch-id=roman-borders

# 6. Import relations
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:import-border-relations storage/app/pipeline/roman-empire/ --sync --batch-id=roman-relations
```

### Workflow C: Egypt collection → import

```powershell
# 1. Build XML index
py -m pipeline collections build-xml-index --input output/map.xml --index-path output/ohm_collections/map.sqlite3 --force

# 2. Build Egypt collection
py -m pipeline collections egypt-build --xml-index-path output/ohm_collections/map.sqlite3 --ohm-index-path output/ohm_borders/indexes/global-2026-04-14.sqlite3 --run-id egypt-2026 --force

# 3. Build relations
py -m pipeline collections egypt-relations-run --run-id egypt-2026 --resume

# 4. Copy artifacts
New-Item -ItemType Directory -Force api/storage/app/pipeline/egypt-2026
Copy-Item output/ohm_collections/egypt-2026/entities_final/egypt_collection.jsonl api/storage/app/pipeline/egypt-2026/
Copy-Item output/ohm_collections/egypt-2026/relations_final/ohm_relation_entities.jsonl api/storage/app/pipeline/egypt-2026/
Copy-Item output/ohm_collections/egypt-2026/relations_final/ohm_relation_hints.jsonl api/storage/app/pipeline/egypt-2026/

# 5. Import entities
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:import storage/app/pipeline/egypt-2026/egypt_collection.jsonl --sync --batch-id=egypt-2026 --skip-relationships

# 6. Import relations
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:import-border-relations storage/app/pipeline/egypt-2026/ --sync --batch-id=egypt-relations

# 7. Resolve any remaining hints
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:resolve-relationships
```

---

## 5. Debugging and Troubleshooting

### Check import counts

```powershell
docker compose -f docker/docker-compose.yml exec app php artisan tinker --execute "echo DB::table('entities')->where('batch_id', 'my-batch')->count();"
```

### Check unresolved hints

```powershell
# By batch
docker compose -f docker/docker-compose.yml exec app php artisan tinker --execute "echo json_encode(DB::table('pipeline_relationship_hints')->where('batch_id', 'my-batch')->where('resolved', false)->get());"

# Use the report command
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:report-relationship-hints my-batch
```

### Check relationship counts

```powershell
docker compose -f docker/docker-compose.yml exec app php artisan tinker --execute "echo DB::table('relationships')->count();"
```

### Re-run relationship resolution after importing missing targets

```powershell
# 1. Import the missing entities
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:import storage/app/pipeline/missing.jsonl --sync --batch-id=missing-targets

# 2. Re-resolve the original batch
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:resolve-relationships original-batch-id
```

### Check geometry periods

```powershell
docker compose -f docker/docker-compose.yml exec app php artisan tinker --execute "echo DB::table('geometry_periods')->where('provenance_mode', 'ohm_import')->count();"
```

### Check timeline entries

```powershell
docker compose -f docker/docker-compose.yml exec app php artisan tinker --execute "echo DB::table('entity_timeline_entries')->count();"
```

### Reset a batch

```powershell
# Delete entities for a batch (DANGER — test first)
docker compose -f docker/docker-compose.yml exec app php artisan tinker --execute "DB::table('entities')->where('batch_id', 'my-batch')->delete();"
```

### Common issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `No .jsonl files found` | Wrong path or missing `--all` | Check path; use `--all` for directories |
| `target_not_found` hints | Target entity not imported yet | Import missing targets, then re-run `pipeline:resolve-relationships` |
| Duplicate relationships | Re-importing same batch | Use `--force` only when needed; dedup is automatic |
| Empty map after import | No `geojson` on entities | Check pipeline output; verify `geojson` field exists |
| Staging table missing | Migration not run | `docker compose exec app php artisan migrate` |

---

## 6. Quick Reference

### All Python commands

| Command | Purpose |
|---------|---------|
| `py -m pipeline scrape` | Scrape Wikidata by type |
| `py -m pipeline topic` | BFS topic walk |
| `py -m pipeline dedup` | Deduplicate JSONL |
| `py -m pipeline borders fetch` | OHM Overpass fetch |
| `py -m pipeline borders parse` | Parse raw OHM elements |
| `py -m pipeline borders enrich` | Wikidata enrichment |
| `py -m pipeline borders build` | Build final JSONL |
| `py -m pipeline borders relations-run` | Extract + enrich + build relations |
| `py -m pipeline borders build-index` | Build SQLite OHM index |
| `py -m pipeline borders extract-subgraph` | Country subgraph extraction |
| `py -m pipeline collections build-xml-index` | Stream XML into SQLite |
| `py -m pipeline collections egypt-build` | Assemble Egypt collection |
| `py -m pipeline collections egypt-relations-run` | Egypt relation generation |

### All Laravel commands

| Command | Purpose |
|---------|---------|
| `pipeline:import` | Import entity JSONL |
| `pipeline:import-borders` | Import OHM border JSONL |
| `pipeline:import-border-relations` | Import relation entities + hints |
| `pipeline:resolve-relationships` | Resolve relationship hints |
| `pipeline:report-relationship-hints` | Audit hint status |
| `pipeline:embeddings` | Generate entity embeddings |
| `entity:backfill` | Backfill canonical tables |
| `timeline:rebuild` | Rebuild timeline entries |

### Import order (critical)

1. Import main entities (`pipeline:import`)
2. Import border entities (`pipeline:import-borders`) — if using OHM borders
3. Import relation entities (`pipeline:import-border-relations`) — if using relations
4. Resolve relationships (`pipeline:resolve-relationships`)
5. Generate embeddings (`pipeline:embeddings`) — optional
6. Rebuild timelines (`timeline:rebuild`) — if geometry periods changed
