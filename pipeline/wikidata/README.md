# Wikidata / Wikipedia Scraper

Scrapes entities from Wikidata, enriches them with Wikipedia summaries, and writes JSONL files ready for Laravel import.

Can be run as a standalone CLI (`python -m pipeline.wikidata`) or via the top-level dispatcher (`python -m pipeline scrape / topic`).

## Commands

### `scrape` — scrape by type or group

```bash
# Single entity type
python -m pipeline scrape --type political_entity --limit 100

# All types in a group (POLITY, PLACE, EVENT, ECONOMY, CULTURE)
python -m pipeline scrape --group POLITY --limit 50

# Time range filter (negative = BCE)
python -m pipeline scrape --type event_battle --start-year -500 --end-year 1500

# Skip Wikipedia enrichment for a faster run
python -m pipeline scrape --type political_entity --skip-wikipedia

# Custom output directory
python -m pipeline scrape --type political_entity --output-dir /tmp/out
```

### `topic` — graph-walk from a seed entity

Starts from a seed and follows linked Wikidata properties (participants, locations, causes, effects, parts, etc.) via BFS across all entity types.

```bash
# Resolve by name — finds the Wikidata QID automatically
python -m pipeline topic "Late Bronze Age Collapse"

# Pass a QID directly
python -m pipeline topic Q484954

# Control walk depth and entity cap
python -m pipeline topic "Roman Empire" --depth 3 --limit 500

# Provide a co-seed for sparse Wikidata graphs
python -m pipeline topic "Silk Road" --co-seed Q25307

# Skip Wikipedia enrichment
python -m pipeline topic "Silk Road" --skip-wikipedia

# Skip entities that don't map to any of the 30 WikiGlobe types
python -m pipeline topic Q484954 --skip-untyped
```

**Output buckets**

| File | Contents |
|---|---|
| `output/topic_<slug>.jsonl` | Regular entities (30 WikiGlobe types) |
| `output/topic_<slug>_ref.jsonl` | Reference-table items (eras, broad regions, seas, …) |
| `output/topic_<slug>_untyped.jsonl` | Truly unclassified items (manual review) |

Laravel's `pipeline:import --all` skips `*_ref.jsonl` and `*_untyped.jsonl` automatically.

### `dedup` — deduplicate a JSONL file in-place

```bash
python -m pipeline dedup output/political_entity.jsonl

# Also check against existing DB records
python -m pipeline dedup output/political_entity.jsonl --check-db
```

## Importing into Laravel

```bash
# Copy output to api storage
cp output/*.jsonl ../api/storage/app/pipeline/

# Import a single file
docker compose -f docker/docker-compose.yml exec app \
  php artisan pipeline:import storage/app/pipeline/political_entity.jsonl

# Import all files (skips *_ref and *_untyped)
docker compose -f docker/docker-compose.yml exec app \
  php artisan pipeline:import storage/app/pipeline/ --all
```

## Module structure

```text
wikidata/
├── __main__.py           # CLI entry point (scrape / topic / dedup)
├── scraper/
│   ├── wikidata.py       # SPARQL queries against Wikidata
│   ├── wikipedia.py      # Wikipedia API content extraction
│   ├── topic.py          # BFS graph-walk scraper from a seed QID
│   └── geoshape.py       # OHM geoshape resolver used during scrape
├── mapper/
│   ├── entity_mapper.py        # Raw wiki data → entity schema
│   ├── relationship_mapper.py  # Wikidata properties → 76 relationship types
│   └── type_configs.py         # Per-entity-type field mappings
├── dedup/
│   └── deduplicator.py   # Wikidata ID + fuzzy name deduplicator
├── resolver/
│   ├── geo_resolver.py   # Bulk geo-resolution via OHM
│   └── ohm_client.py     # Low-level OHM Nominatim client
├── embeddings/
│   └── generator.py      # Standalone embedding generator (optional)
└── queries/
    ├── polity.sparql
    ├── place.sparql
    ├── event.sparql
    ├── economy.sparql
    └── culture.sparql
```
