# OHM Subgraph Index Optimization Design

**Context**

The current OHM country subgraph extractor reads the full global `overpass.json` into memory, builds in-memory relation indexes, and then performs bounded BFS from a seed polity. That works functionally, but it performs poorly on the real OHM dump because the extractor pays the full JSON decode and indexing cost on every run. On a multi-gigabyte Overpass payload, this creates heavy RAM pressure, disk paging, and long startup times while leaving CPU underutilized.

The target use case is repeated country-centered extraction from the same global OHM dump. Operators should be able to build an index once, then extract Roman Empire, Byzantine Empire, Ottoman Empire, and other country subgraphs without reparsing the 4 GB source file every time.

**Goal**

Replace the monolithic in-memory subgraph lookup path with a streaming ingest plus persistent SQLite index so that repeated country subgraph extraction becomes disk-backed, memory-bounded, and fast enough for normal laptop use.

**Approach**

Use a compatibility-preserving index layer in front of the existing subgraph extraction outputs:

- add a new `build-index` command that streams a source `overpass.json` once into SQLite
- change `extract-subgraph` to resolve seeds and traverse the graph from SQLite instead of reparsing the full source payload
- preserve the current subset artifact contract: reduced `raw/overpass.json`, `raw/raw-*.jsonl`, `subgraph/seed.json`, `subgraph/graph_edges.jsonl`, and `subgraph/closure_report.json`
- preserve downstream parse, enrich, build, and relation stages unchanged
- add ranked seed suggestions using Python-side fuzzy search when exact seed lookup fails

The optimization should improve the hot path for repeated extractions without turning this into a graph-database project.

**Storage model**

The index uses plain SQLite with Python-side fuzzy search.

SQLite is the right first step because:

- it is available by default in Python and simple to operate locally
- it supports keyed lookup and adjacency traversal well enough for this workflow
- it keeps deployment and docs straightforward for a single-user/operator flow
- it avoids the operational overhead of Neo4j or another external graph database

Python-side fuzzy search should use a package such as `rapidfuzz` rather than SQLite FTS for the first optimization pass. The problem to solve is not full-text search quality across large corpora; it is practical operator seed resolution after exact lookup fails.

**Commands**

Add two related commands under the OHM borders CLI surface.

1. `build-index`

Purpose:
- stream the source `overpass.json` once
- extract the relation metadata and graph edges needed by the country-subgraph workflow
- write a reusable SQLite database

Expected inputs:
- `--input`: source `overpass.json`
- `--index-path`: explicit SQLite output path
- `--force`: rebuild the index even when it already exists

2. `extract-subgraph`

Purpose:
- resolve the seed from SQLite
- traverse the indexed OHM graph
- materialize only the required relation payloads into the current subset artifact layout

Expected inputs:
- existing seed and traversal flags stay: `--seed-qid`, `--seed-name`, `--max-depth`, `--max-nodes`, `--run-id`, `--artifact-dir`, `--raw-shard-size`, `--resume`, `--force`
- add `--index-path`
- add `--build-index-if-missing`

Behavior:
- if a matching index exists, extraction should prefer SQLite over direct raw-JSON scanning
- if the index is missing and `--build-index-if-missing` is set, build the index first and then continue extraction
- if no usable index exists and auto-build is not enabled, fail fast with guidance rather than silently falling back to the slow full-memory path

Explicit backward-compatibility rule:

- the optimized command path must not silently reintroduce the old full-memory extraction path
- indexed extraction is the only supported extraction mode after this optimization lands
- operators who do not have an index must either build one explicitly or opt into auto-build with `--build-index-if-missing`

Index discovery order when `--index-path` is omitted:

1. explicit `--index-path`
2. `OHM_SUBGRAPH_INDEX_PATH` environment variable
3. default sibling path next to the source payload: `<input directory>/overpass.sqlite3`
4. fail with guidance if no usable index exists and auto-build is disabled

**Index schema**

The schema should remain narrow and purpose-built for extraction.

Required tables:

- `index_metadata`
  - single-row metadata table
  - `schema_version`
  - `payload_format_version`
  - `source_fingerprint_sha256`
  - `source_path`
  - `source_size_bytes`
  - `source_mtime_epoch`
  - `build_completed_at`
  - `fuzzy_matcher_name`
  - `fuzzy_matcher_version`
  - `fuzzy_threshold`

- `relations`
  - `relation_id`
  - `name`
  - `normalized_name`
  - `wikidata_id`
  - `is_chronology`
  - stored relation JSON blob or compact payload sufficient to reconstruct the reduced Overpass output

- `chronology_edges`
  - chronology relation id
  - member/stage relation id
  - unique on `(chronology_relation_id, member_relation_id)`

- `qid_edges`
  - source relation id
  - edge kind for predecessor/successor/start/end tag origin
  - linked target Wikidata id

- `qid_to_relations`
  - Wikidata id
  - eligible OHM relation id

Recommended indexes:

- relation id
- Wikidata id
- normalized name
- chronology member lookup columns
- source relation id on `qid_edges`

Required relational constraints:

- foreign keys from `chronology_edges` and `qid_edges` source relation ids back to `relations.relation_id`
- non-null constraints on all ids used for traversal

Edge kind taxonomy:

- `predecessor_wikidata`
- `preceded_by_wikidata`
- `successor_wikidata`
- `succeeded_by_wikidata`
- `start_event_wikidata`
- `end_event_wikidata`

These edge kinds are auditable metadata describing the origin OHM tag. Chronology traversal remains represented by the dedicated `chronology_edges` table rather than overloading `qid_edges`.

Relations payload contract:

- store the full relation JSON object required to reconstruct both the reduced `raw/overpass.json` and the derived `raw/raw-*.jsonl` shards without rereading the source payload
- payload reconstruction must preserve compatibility with the current `parse_elements()` and relation subset parsing helpers
- schema versioning must cover payload format changes so older indexes are not reused incorrectly

Optional but useful metadata:

- source file fingerprint
- source file size
- source modified timestamp
- schema version
- build timestamp

Metadata storage rule:

- index compatibility values must live in the dedicated `index_metadata` table rather than being inferred from relation rows
- extraction must read `schema_version`, `payload_format_version`, and `source_fingerprint_sha256` from `index_metadata` before issuing traversal queries

Fingerprint contract:

- use SHA256 of file content as the canonical source fingerprint
- file path alone is not sufficient to identify index compatibility
- if the user points a different path at identical content, the index is still reusable
- if the content fingerprint differs, the index must be treated as incompatible unless rebuilt explicitly

**Streaming ingest contract**

The index builder must avoid loading the full Overpass payload into memory.

Requirements:

- parse `elements` incrementally from the source file
- process only relation elements relevant to the OHM country-subgraph workflow
- write rows incrementally into SQLite in batches
- keep memory bounded regardless of source payload size
- support BOM-prefixed UTF-8 input files because Windows-authored files and copied dumps may include a BOM

The builder may use a streaming JSON parser package if needed. The design assumes a package such as `ijson` is acceptable.

Partial-failure recovery contract:

- build the index into a temporary SQLite file first, then atomically replace the target index path on success
- record schema version and source fingerprint only after ingest completes successfully
- `--force` must replace any existing target index with a clean rebuild rather than attempting an in-place salvage
- if a prior build left a partial temporary file, the next run may delete it safely and restart
- builders must use a lock file or equivalent single-writer guard so only one `build-index` process owns a target index path at a time
- temporary index files must use unique process-specific names so concurrent builders cannot collide accidentally

Lock-file contract:

- lock path is `<index-path>.lock`
- lock contents must include PID, hostname, started timestamp, and target source path
- builders acquire the lock with exclusive create semantics
- if a lock exists and the owning process is still alive, the new builder must fail fast with a clear "index build already running" message
- if a lock exists but the owning process is not alive and the lock is older than the configured stale timeout, the next builder may remove it and continue
- stale-timeout cleanup must be logged explicitly so operators can diagnose recovery after crashes

SQLite access contract:

- use WAL mode for normal indexed reads after build completion
- concurrent extraction reads from an already built index are allowed
- do not support concurrent writes to the same index during build; a running builder owns the target path until the atomic replace step finishes
- on Windows, if the existing index file cannot be replaced because active readers still hold it, the builder must fail with a clear retry message rather than attempting an unsafe overwrite
- extraction processes should open the index read-only where practical

Unknown edge handling rule:

- ingest must reject or log-and-skip any unexpected traversal edge kind explicitly; it must not silently invent new kinds
- tests must assert the supported edge taxonomy matches the current OHM traversal contract

**Seed lookup behavior**

Seed lookup should become more operator-friendly while staying deterministic.

Lookup order:

1. explicit `--seed-qid`
2. exact `--seed-name`
3. normalized exact name
4. fuzzy ranked suggestions using Python-side matching

Normalization contract:

- normalize candidate names and query names with `unicodedata.normalize("NFC", value)`
- apply `.casefold()` for case-insensitive matching
- trim leading and trailing whitespace
- collapse internal runs of whitespace to a single space
- store both raw `name` and normalized `normalized_name` in SQLite so build-time and query-time behavior stay identical

Requirements:

- fuzzy search should not silently pick an uncertain result
- when exact lookup fails, the command should return ranked candidate suggestions with names, QIDs, and relation ids
- if a single clear best match exists above the configured threshold, it may be selected automatically only when the operator passes an explicit `--auto-select-fuzzy` flag; otherwise suggestions should be presented and the command should fail with guidance
- exact and normalized lookup must remain stable and preferred over fuzzy results
- the command must not pause for interactive input; ambiguous fuzzy results are reported non-interactively and the command exits with actionable suggestions

Recommended implementation:

- normalize names consistently during index build and query time
- use `rapidfuzz` scoring on candidate names loaded from SQLite
- cap returned suggestions to a small operator-friendly list
- use a documented default threshold of `0.85` for normalized fuzzy score acceptance
- return the top 5 candidate suggestions when fuzzy search does not auto-select a result
- bound fuzzy-search memory by querying a narrowed candidate set from SQLite first, for example by normalized prefix, capped exact-substring candidates, or another deterministic prefilter, before applying Python-side scoring

Determinism contract:

- record `fuzzy_matcher_name`, `fuzzy_matcher_version`, and `fuzzy_threshold` in `index_metadata`
- also record the resolved seed relation ids and fuzzy-selection inputs in `subgraph/seed.json` for subset runs that used name-based lookup
- extraction must treat fuzzy configuration drift the same way it treats schema drift when resume would otherwise reuse prior outputs

Bounded fuzzy prefilter rule:

- first query SQLite for normalized exact matches
- if none exist, fetch candidates sharing the first 3 normalized characters, capped at 1000 rows
- if that set is empty, fall back once to candidates sharing the first 2 normalized characters, capped at 1000 rows
- only that bounded candidate set may be passed into Python-side `rapidfuzz` scoring
- if the bounded candidate query still returns zero rows, fail with a no-candidate message rather than widening to an unbounded table scan

**Extraction behavior**

The extraction semantics remain the same as the current design:

- traversal is bounded by `max_depth` and `max_nodes`
- graph expansion uses chronology membership and Wikidata-linked predecessor/successor/start/end edges
- outputs remain the same so downstream stages do not need a format change

The implementation changes where the data comes from:

- seed resolution comes from SQLite
- BFS neighbor expansion comes from SQLite edge tables
- relation payload reconstruction comes from SQLite-stored blobs or compact payload rows

The extractor should no longer require full-file JSON loading for normal indexed runs.

**Rerun behavior**

The workflow must be safe and predictable for repeated runs.

`build-index` rules:

- skip work when the existing index matches the same source file and schema version unless `--force` is supplied
- fail fast or rebuild explicitly when the source fingerprint differs

Explicit `build-index` behavior:

- if target index exists and both schema version and source SHA256 fingerprint match, report `skipped`
- if target index exists and either schema version or source fingerprint differs, report an incompatibility message and require `--force` to replace it
- if `extract-subgraph --build-index-if-missing --force` is used, `--force` applies only to subset artifact rebuilding; it must not implicitly replace an existing incompatible index
- replacing an existing index remains an explicit `build-index --force` operation

`extract-subgraph` rules:

- continue to support `--resume` for subset artifact reuse
- compare the current extraction inputs against the manifest summary as today for seed identity, traversal limits, and shard size
- also compare the requested input source against the indexed source fingerprint
- compare the index schema version against the extractor's expected schema version
- fail fast when the index points at a different source file unless the user explicitly rebuilds or selects a different index

Resume mismatch rule:

- if resume artifacts exist but the chosen index fingerprint or schema version is incompatible with the requested source payload, fail fast with guidance to rebuild the index or start a new run id
- do not silently discard resume artifacts or silently rebuild the index inside a `--resume` extraction run
- if the index schema version differs from the extractor's expected schema version, extraction must hard-fail with guidance to rebuild the index; no backward-compatibility fallback is attempted

Auto-build inheritance rule:

- `extract-subgraph --build-index-if-missing` must use only the source payload and the chosen index path
- extraction-only flags such as `--raw-shard-size`, `--max-depth`, and `--max-nodes` must not alter index-build semantics
- build-index defaults remain independent from extraction defaults
- if `--build-index-if-missing` is used and an existing index is present but incompatible, extraction must fail with guidance rather than treating that state as "missing"

Auto-build incompatibility rule:

- `--build-index-if-missing` only applies when no index exists at the resolved path
- if an index exists but is incompatible, the command must hard-fail with guidance to run `build-index --force`
- `extract-subgraph --force` must not be interpreted as permission to replace the index automatically

Seed equivalence rule for resume comparison:

- compare resume compatibility using the resolved seed identity stored in `subgraph/seed.json`, not only the raw CLI flags
- if a prior run resolved to the same seed relation ids and the same indexed source fingerprint, `--seed-qid` and `--seed-name` inputs may be treated as equivalent
- if the new invocation resolves to a different seed relation set, resume must fail fast with guidance to use `--force` or a new run id

This keeps second-run country extraction cheap while preventing accidental drift between source dumps and derived subset runs.

**Import integrity**

The existing strict import-order assumptions remain in place.

Operational rule:

1. import main OHM border entities
2. import relation entities
3. resolve relation hints

Bundle-closure validation remains part of the subset workflow and should stay unchanged conceptually. The optimization changes the extraction source, not the import-readiness contract.

**Components**

- `pipeline/ohm_borders/index_builder.py`
  Streaming ingest from `overpass.json` into SQLite.

- `pipeline/ohm_borders/index_store.py`
  SQLite schema management, inserts, lookups, and source-fingerprint helpers.

- `pipeline/ohm_borders/subgraph_extractor.py`
  Refactor extraction logic to operate on an indexed backend rather than a full in-memory payload.

- `pipeline/ohm_borders/stage_extract_subgraph.py`
  Orchestrate extraction with index selection and optional auto-build.

- `pipeline/ohm_borders/__main__.py`
  Add `build-index` and extend `extract-subgraph` flags.

- `pipeline/__main__.py`
  Re-export the new command in the top-level legacy dispatcher.

- `pipeline/tests/...`
  Add index-build, fuzzy-lookup, and index-backed extraction coverage.

- `docs/implementation-docs/...`
  Update the operator runbook for first index build, second-run reuse, and seed suggestion handling.

**Validation and testing strategy**

The optimization must be validated in three layers.

1. Index-build tests

- streaming ingest writes expected rows
- chronology and QID edge extraction is correct
- source fingerprint and rebuild rules are correct
- BOM-prefixed input is accepted
- partial-build cleanup and replace behavior is correct
- index discovery order is correct when `--index-path` is omitted
- identical-content inputs at different paths reuse the same index compatibility contract, while one-byte-different inputs are rejected as incompatible
- `index_metadata` is populated only after successful build completion
- stale lock detection and active-lock failure behavior are correct

2. Extractor tests

- exact lookup by QID and exact name
- normalized lookup
- fuzzy suggestion ranking and failure messages
- explicit `--auto-select-fuzzy` behavior at the configured threshold
- indexed BFS produces the same included relation ids and edge outputs as the current logic on fixture data
- ambiguous fuzzy results fail non-interactively with ranked suggestions
- resume compatibility treats equivalent resolved seeds as compatible even when one run used `--seed-name` and the next used `--seed-qid`
- bounded fuzzy candidate prefilter does not widen into an unbounded full-table scan
- fuzzy matcher version or threshold drift is surfaced as incompatible for resume-sensitive runs

3. Operator and compatibility tests

- `build-index` command creates a reusable SQLite database
- `extract-subgraph --build-index-if-missing` works on a fresh machine path
- second-run extraction reuses the index without reparsing the raw 4 GB JSON
- subset artifacts remain compatible with parse, relation, and closure-validation stages
- resume plus incompatible-index mismatch fails with a clear operator message
- concurrent reader plus `build-index --force` replacement failure on Windows is surfaced with a clear operator error
- incompatible existing index plus `--build-index-if-missing` fails with guidance rather than rebuilding implicitly

Success criteria should include operational behavior, not just correctness:

- first index build may still take time, but should keep memory bounded
- second and later country extractions should avoid full raw JSON parsing entirely
- laptop memory consumption during extraction should be dramatically lower than the current implementation

**Non-goals**

- No external graph database in this plan
- No SQLite FTS requirement in the first optimization pass
- No Laravel retry mechanism changes
- No thematic Wikidata relevance-ranking work yet