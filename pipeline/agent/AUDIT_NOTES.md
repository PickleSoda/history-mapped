# Agent Integration Audit Notes

Generated: 2026-06-10
Purpose: Document actual method signatures, CLI structure, and DB interfaces before building the agentic pipeline.

---

## pipeline/wikidata/scraper/wikidata.py

**Class:** `WikidataScraper`

**Constructor:**
- `__init__(self)` → initializes `self.sparql` (SPARQLWrapper), `self.geoshapes` (GeoshapeResolver)

**Public Methods:**
- `query_entities(self, entity_type: str, limit: int = 100, start_year: int | None = None, end_year: int | None = None) -> list[dict[str, Any]]`
  - Returns raw Wikidata fields: `qid`, `label`, `description`, `aliases` (empty list, filled later), `coords`, `inception`, `dissolution`, `start_time`, `end_time`, `point_in_time`, `location_name`, `wikipedia_title`, `properties`
  - Internally calls `_build_query`, `_execute_query`, `_parse_binding`, `_enrich_properties`, `_enrich_geoshapes`

- `fetch_aliases(self, qids: list[str]) -> dict[str, list[str]]`
  - Batch-fetches Wikidata `skos:altLabel` aliases per QID
  - Returns mapping `qid -> [alias, ...]`

**Private Methods (notable for agent design):**
- `_execute_query(self, query: str) -> list[dict[str, Any]]` — rate-limited SPARQL execution via `@limits` + `@sleep_and_retry`
- `_build_query(self, config: dict, limit: int, start_year: int | None, end_year: int | None) -> str`
- `_parse_binding(self, binding: dict, config: dict) -> dict[str, Any] | None`
- `_parse_date(self, date_str: str | None) -> str | None` — parses `xsd:dateTime` into year string (negative for BCE)
- `_parse_point_wkt(point_wkt: str | None) -> dict[str, float] | None` — static, parses WKT Point to `{lon, lat}`
- `_enrich_properties(self, items: list[dict], config: dict) -> list[dict]` — batch-fetches P3896, P17, P131, P276, P36, P1376, P361, P527, P155, P156
- `_enrich_geoshapes(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]` — resolves Commons geoshapes via GeoshapeResolver
- `_extract_geoshape_from_properties(properties: dict) -> str | None` — static, extracts `Data:*.map` title from P3896

**Discrepancies / Assumptions Checked:**
- There is NO `search_entities` method. The only search path is via `TopicScraper.resolve_search()` (in `pipeline/wikidata/scraper/topic.py`)
- Aliases are NOT fetched by default in `query_entities`; the returned `aliases` field is always `[]`. `fetch_aliases` must be called separately if needed.
- Coordinates are parsed from WKT `Point(lon lat)` format, not lat/lon pairs.

---

## pipeline/wikidata/dedup/deduplicator.py

**Class:** `Deduplicator`

**Constructor:**
- `__init__(self, check_db: bool = False)` — `check_db` controls whether Phase 3 DB dedup runs

**Public Methods:**
- `deduplicate(self, entities: list[dict[str, Any]]) -> list[dict[str, Any]]`
  - Three-phase dedup:
    1. Exact QID match (`wikidata_id`) — first-seen wins, merges `alternative_names`
    2. Fuzzy name + temporal overlap (`thefuzz.token_sort_ratio >= 88` AND `_temporal_overlap` within same `entity_type`)
    3. DB dedup (optional, only if `check_db=True`) — checks PostgreSQL `entities` table by `wikidata_id` and fuzzy name via `pg_trgm` `similarity(name, %s) > 0.6`

**Private Methods:**
- `_fuzzy_dedup(self, entities: list[dict]) -> list[dict]`
- `_db_dedup(self, entities: list[dict]) -> list[dict]`
- `_merge_names(kept: dict, duplicate: dict)` — static, merges `alternative_names`, caps at 20
- `_parse_year(val) -> int | None` — static
- `_temporal_overlap(s1, e1, s2, e2) -> bool` — static, missing dates default to overlap

**DB Connection:**
- Uses `psycopg.connect(settings.database_url)` on-demand in `_db_dedup`
- Queries the `entities` table (Laravel DB) for:
  - `SELECT entity_id FROM entities WHERE wikidata_id = %s`
  - `SELECT entity_id, name FROM entities WHERE entity_type = %s AND similarity(name, %s) > 0.6`
- Connection is opened per `_db_dedup` call and closed at the end
- Depends on `pipeline.config.settings.database_url` being set

**Discrepancies / Assumptions Checked:**
- DB dedup requires `pg_trgm` extension for `similarity()` function
- `_merge_names` caps `alternative_names` at 20 items
- No persistent DB connection pooling; opens/closes per invocation

---

## pipeline/__main__.py

**CLI framework:** `click` (not argparse)

**Structure:**
- Top-level `@click.group()` named `cli`
- Subcommands are registered via `.add_command()` — no automatic discovery

**Legacy Wikidata subcommands (re-exported from `pipeline.wikidata.__main__`):**
- `scrape` → `wikidata_scrape_impl`
- `dedup` → `wikidata_dedup_impl`
- `topic` → `wikidata_topic_impl`

**Legacy Borders subgroup:**
- `@cli.group(invoke_without_command=True)` named `borders`
- Has its own options: `--output`, `--run-id`, `--artifact-dir`, `--query-file`, `--raw-shard-size`, `--parsed-shard-size`, `--parse-workers`, `--build-workers`, `--enrich-batch-size`, `--enrich-workers`, `--resume`, `--force`
- Sub-subcommands: `extract-subgraph`, `build-index`, `fetch`, `parse`, `enrich`, `build`, `run`, `enrich-output-names`, `relations-scan`, `relations-enrich`, `relations-build`, `relations-run`

**Collections subcommand:**
- `collections` → `collections_cli` from `pipeline.ohm_collections.__main__`

**Entry points:**
- `python -m pipeline scrape ...`
- `python -m pipeline topic ...`
- `python -m pipeline borders ...`
- `python -m pipeline collections ...`
- `python -m pipeline wikidata ...` (alternative via submodule)
- `python -m pipeline ohm-borders ...` (alternative via submodule)

**Discrepancies / Assumptions Checked:**
- The `collections` command is a full click group (not a single command), registered at top level
- `borders` is a click group that can also run without a subcommand if `--output` is provided

---

## pipeline/wikidata/__main__.py

**CLI framework:** `click`

**Subcommands on `cli` group:**
- `scrape`
  - Options: `--type` / `--group`, `--start-year`, `--end-year`, `--limit`, `--skip-wikipedia`, `--output-dir`
  - Pipeline: query → Wikipedia enrich → EntityMapper.map → Deduplicator.deduplicate → geo-resolve → write JSONL

- `dedup`
  - Args: `jsonl_file`
  - Options: `--check-db`
  - Reads/writes JSONL in-place

- `topic`
  - Args: `query` (QID or free text)
  - Options: `--depth`, `--limit`, `--co-seed` (multiple), `--skip-wikipedia`, `--skip-untyped`, `--output-dir`
  - Pipeline: resolve search → graph walk → classify (typed/ref/untyped) → enrich → map → dedup → geo-resolve → write JSONL + ref JSONL + untyped JSONL

**Internal helpers:**
- `_configure_logging()` — idempotent basicConfig
- `_slugify(text: str) -> str` — safe filename slug

---

## pipeline/ohm_collections/__main__.py

**CLI framework:** `click` (partial, truncated in read)

**Key programmatic functions (not CLI commands, used by agent/build scripts):**
- `run_egypt_build(*, xml_index_path: Path, ohm_index_path: Path | None, run_id: str, output_root: Path | None, resume: bool, force: bool, candidate_enricher: Callable | None = None) -> dict[str, object]`
  - Returns `{"status": "skipped" | "completed", "output_root": ..., "manifest_path": ..., "manifest": ...}`

- `run_egypt_relations(*, run_id: str, output_root: Path | None, resume: bool, force: bool) -> dict[str, object]`
  - Returns `{"status": "skipped" | "completed", "entities_path": ..., "hints_path": ..., "entity_count": ..., "hint_count": ...}`

---

## pipeline/requirements.txt

**Existing dependencies:**
- `SPARQLWrapper>=2.0.0` — Wikidata SPARQL queries
- `requests>=2.31.0` — HTTP requests
- `python-dotenv>=1.0.0` — `.env` file loading
- `wptools>=0.4.17` — Wikipedia parsing
- `mwparserfromhell>=0.6.5` — MediaWiki markup parsing
- `pydantic>=2.5.0` — Data validation
- `orjson>=3.9.0` — Fast JSON serialization
- `thefuzz[speedup]>=0.22.0` — Fuzzy string matching
- `rapidfuzz>=3.9.0` — Faster fuzzy matching backend
- `openai>=1.12.0` — Embeddings (optional)
- `psycopg[binary]>=3.1.0` — PostgreSQL driver (optional, for DB dedup)
- `rich>=13.7.0` — CLI progress/output
- `click>=8.1.0` — CLI framework
- `shapely>=2.0.0` — Geometry assembly for OHM rings
- `ratelimit>=2.2.1` — Rate limiting decorators
- `ijson>=3.3.0` — Streaming JSON parsing

**Notable:** No `sqlalchemy`, no `httpx`, no `asyncio` libs. Blocking I/O throughout.

---

## api/app/Console/Commands/ImportEntitiesCommand.php

**Class:** `ImportEntitiesCommand extends Command`

**Signature:**
```
pipeline:import
    {path : Path to a JSONL file or directory}
    {--all : Import all .jsonl files in the directory}
    {--sync : Process synchronously instead of dispatching jobs}
    {--force : Overwrite existing entities instead of skipping duplicates}
    {--skip-dedup : Skip database deduplication check}
    {--skip-relationships : Skip relationship resolution after import}
    {--batch-id= : Custom batch identifier (default: auto-generated)}
    {--chunk=100 : Number of records per job dispatch}
```

**Options:**
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `path` | positional | required | JSONL file or directory |
| `--all` | flag | false | Import all `.jsonl` in directory |
| `--sync` | flag | false | Run synchronously (no queue jobs) |
| `--force` | flag | false | Overwrite existing entities by `wikidata_id` |
| `--skip-dedup` | flag | false | Skip `isDuplicate()` check |
| `--skip-relationships` | flag | false | Skip `ResolveRelationshipsJob` dispatch |
| `--batch-id` | string | `pipeline-Ymd-His` | Custom batch ID |
| `--chunk` | int | `100` | Records per job chunk |

**Behavior:**
- Skips files ending in `*_ref.jsonl` and `*_untyped.jsonl` when `--all` is used
- Skips records with `_ref_type` in `REF_TYPES` (reference table items: eras, regions, bodies of water, etc.)
- Pre-import dedup checks `wikidata_id` (or exact `name` + `entity_type` fallback) against `entities` table
- Dispatches `ImportEntityJob` per record (or per chunk in sync mode)
- After all files, dispatches `ResolveRelationshipsJob` (unless `--skip-relationships`)
- Ref types silently skipped: `ref_historical_period`, `ref_geographic_region`, `ref_body_of_water`, `ref_calendar_system`, `ref_writing_system`, `ref_measurement_unit`

**Private Methods:**
- `resolveFiles(string $path, bool $all): array` — resolves path to JSONL file list
- `readJsonl(string $file): array` — reads JSONL into decoded arrays
- `isDuplicate(array $record): bool` — checks DB for existing `wikidata_id` or `name`+`entity_type`
- `isRefTableItem(array $record): bool` — checks `_ref_type` marker
- `importSync(array $record, string $batchId, bool $force = false): void` — sync import wrapper

---

## api/app/Console/Commands/ImportBordersCommand.php

**Class:** `ImportBordersCommand extends Command`

**Signature:**
```
pipeline:import-borders
    {path : Path to JSONL file generated by python -m pipeline borders}
    {--sync : Process synchronously instead of dispatching jobs}
    {--force : Overwrite existing entities}
    {--batch-id= : Custom batch identifier (default: auto-generated)}
```

**Options:**
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `path` | positional | required | Single JSONL file path |
| `--sync` | flag | false | Run synchronously |
| `--force` | flag | false | Overwrite existing border entities |
| `--batch-id` | string | `borders-Ymd-His` | Custom batch ID |

**Behavior:**
- Reads a single JSONL file line-by-line (streaming, not loading all into memory)
- Skips empty lines and malformed JSON lines
- Dispatches `ImportBorderEntityJob` per record (or calls `.handle()` in sync mode)
- No directory/batch mode — single file only
- No dedup logic (relies on `--force` or job-level handling)
- No relationship resolution (borders are standalone entities)

---

## Summary for Agent Design

### Python-side interfaces to call:
1. `WikidataScraper().query_entities(entity_type, limit, start_year, end_year)` → raw items
2. `WikidataScraper().fetch_aliases(qids)` → alias map
3. `Deduplicator(check_db=False).deduplicate(entities)` → deduplicated list
4. `EntityMapper().map(raw_item, entity_type)` → schema-compliant entity dict
5. `TopicScraper(max_depth, max_entities).walk(seed_qid, co_seed_qids)` → topic graph (from `pipeline/wikidata/scraper/topic.py`)
6. `run_egypt_build(...)` / `run_egypt_relations(...)` — collection builder functions

### CLI entry points:
- `python -m pipeline scrape --type <type> --limit N`
- `python -m pipeline topic "<query>" --depth D --limit N`
- `python -m pipeline collections <subcommand>`
- `python -m pipeline borders <subcommand>`

### Laravel-side interfaces to call:
- `php artisan pipeline:import <path> --all [--sync] [--force] [--skip-dedup] [--skip-relationships] [--batch-id=...] [--chunk=...]`
- `php artisan pipeline:import-borders <path> [--sync] [--force] [--batch-id=...]`

### Data flow assumption check:
- Pipeline writes `.jsonl` files → Laravel reads `.jsonl` files
- Pipeline does NOT write directly to Laravel DB (except optional dedup check)
- Entity schema fields expected by Laravel: `wikidata_id`, `name`, `entity_type`, `alternative_names`, `description`, `latitude`, `longitude`, `temporal_start`, `temporal_end`, `location_name`, `wikipedia_title`, `properties`, `_relationship_hints`, `_ref_type`
