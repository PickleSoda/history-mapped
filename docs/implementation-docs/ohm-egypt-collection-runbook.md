# OHM Egypt Collection Runbook

This workflow builds an Egypt-focused historical collection from the local OHM XML export without loading the whole XML document into memory.

## Why the XML is streamed

`output/map.xml` is large enough that it must be treated as a streamed input. The XML indexer uses `xml.etree.ElementTree.iterparse` and a disk-backed SQLite index. Do not open the full file into memory or try to hand-inspect it wholesale.

## Command flow

Run all commands from the repository root.

### 1. Build the reusable XML index

```powershell
py -m pipeline collections build-xml-index \
  --input output/map.xml \
  --index-path output/ohm_collections/map.sqlite3 \
  --force
```

This produces a reusable SQLite index of OHM nodes, ways, relations, aliases, and member references.

### 2. Build the Egypt collection artifacts

```powershell
py -m pipeline collections egypt-build \
  --xml-index-path output/ohm_collections/map.sqlite3 \
  --ohm-index-path output/ohm_borders/indexes/global-2026-04-14.sqlite3 \
  --run-id egypt-historical-collection \
  --force
```

By default the run writes to `output/ohm_collections/<run_id>/`. Use `--output-root` if you need an explicit override.

Use `--resume` on reruns when the existing manifest and output files are still compatible.

### 3. Build relation entity and hint artifacts

```powershell
py -m pipeline collections egypt-relations-run \
  --run-id egypt-historical-collection \
  --resume
```

This writes the Laravel-facing relation files under `relations_final/`:

- `ohm_relation_entities.jsonl`
- `ohm_relation_hints.jsonl`

## Output layout

Each run writes under `output/ohm_collections/<run_id>/`:

- `reports/included.jsonl`
- `reports/excluded.jsonl`
- `borders_final/ohm_borders.jsonl`
- `entities_final/egypt_collection.jsonl`
- `relations_final/ohm_relation_entities.jsonl`
- `relations_final/ohm_relation_hints.jsonl`
- `manifest.json`

## Point precedence

The collection builder records geometry provenance in this order:

1. `ohm_point`
2. `ohm_representative_point`
3. `pipeline_geojson`
4. `none`

Use OHM-native points when they exist, fall back to representative points for ways and relations when local geometry is sufficient, then fall back to generic pipeline coordinates, and keep the entity even when no geometry is available.

## Laravel import flow

Start the application stack first:

```powershell
docker compose -f docker/docker-compose.yml up -d
```

Then import the three artifact groups:

```powershell
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:import-borders /var/www/html/storage/app/imports/egypt-historical-collection/borders_final/ohm_borders.jsonl --sync --force --batch-id=egypt-historical-collection-borders

docker compose -f docker/docker-compose.yml exec app php artisan pipeline:import /var/www/html/storage/app/imports/egypt-historical-collection/entities_final --all --sync --force --batch-id=egypt-historical-collection-entities

docker compose -f docker/docker-compose.yml exec app php artisan pipeline:import-border-relations /var/www/html/storage/app/imports/egypt-historical-collection/relations_final --sync --force --batch-id=egypt-historical-collection-relations
```

## Verification

After a successful run, check:

- `manifest.json` for included/excluded counts and geometry-source totals
- `reports/included.jsonl` for inclusion reasons and geometry provenance
- `reports/excluded.jsonl` for exclusion reasons and ambiguity markers
