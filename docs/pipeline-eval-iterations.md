# Agentic Pipeline — Hardening & Quality Iterations

A record of taking the historical-entity agent pipeline from *silently failing
every database write* to persisting a coherent knowledge graph per transcript,
measured by a reproducible evaluation harness.

## How to reproduce

```bash
# 1. blank slate (roles + users + reference tables only; no entity/rel/chronicle fixtures)
docker compose -f docker/docker-compose.yml exec app php artisan migrate:fresh \
  --seeder='Database\Seeders\BaselineSeeder' --force

# 2. run + evaluate all transcripts in output/transctipts/ (resets first by default)
py -m pipeline.agent.eval --label myrun

# 3. diff two iterations
py -m pipeline.agent.eval.compare iter3_disambig iter4_dates
```

Reports land in `output/eval_runs/<label>/report.{md,json}`. See
`pipeline/agent/eval/README.md` for details.

## Before → after

| | Before (as found) | After (iter4) |
|---|---|---|
| Audit log per run | **65,534** entries, 11 MB manifest (exponential reducer bug) | ~14 entries, small manifest |
| Reported vs actual | `committed=548`, **0 actually persisted** (false success) | exit code + `IMPORT_SUMMARY` reflect reality |
| Entities persisted / run | 0 (all writes failed) | ~100–120 |
| Relationships / run | 0 | ~37–46 (real rows, typed) |
| Chronicles / run | 0 | 7 (≈120 entries, ≈90 secondary links) |
| DB connection | `wikiglobe` auth failure | `history-mapped`, connects |
| Cross-transcript dedup | n/a | consistent (no duplicate identities) |

## The harness

- `Database\Seeders\BaselineSeeder` — blank-slate seed (no entity/rel/chronicle fixtures).
- `py -m pipeline.agent.eval` — reset → run each transcript (fresh subprocess) →
  probe the DB → quality heuristics → `report.{md,json}`.
- `py -m pipeline.agent.eval.compare A B` — metric-delta table with `[better]`/`[worse]`.
- Metrics: per-run health (exit code, committed, errors, audit length, reducer
  sanity), persisted counts, event-range violations, duplicate/self-loop
  relations, ≤2-char names, chronicle orphans, and cross-transcript overlap
  consistency.

## Iteration log

### Iteration 1 — write-path correctness
The pipeline ran green but persisted nothing. Fixes:
- **Reducer duplication** (`state.py`): three accumulator channels used
  `operator.add` while every node returns the full state → the list doubled per
  node (≈2¹⁶). Switched to replace semantics (the graph is strictly linear).
- **DB credentials**: `pipeline/.env` pointed at a nonexistent `wikiglobe` db.
- **geojson**: wrote the point-resolver wrapper instead of the bare geometry
  (PostGIS "unknown GeoJSON").
- **Relations**: the agent has no QIDs, but the import path was QID-keyed and
  dropped every relation. Added name-keyed `pipeline:import-relations`.
- **Synthetic id**: stopped writing `src|type|tgt` into the chronicle's
  `primary_relationship_id` (a UUID column → 22P02).
- **Honest reporting**: `pipeline:import` / `chronicles:import` now exit non-zero
  on per-record failure and emit `IMPORT_SUMMARY`.

Result: **123 entities / 46 relationships / 7 chronicles** persisted (from 0).

### Iteration 2 — BCE dates + relationship directionality
- **Relationship modeling**: the extractor pointed `defeated_at`/`victorious_at`
  at the *opponent* (a person/army). Rewrote the prompt to create
  `event_battle`/`event_war` entities and anchor outcomes to them (winner
  `victorious_at` EVENT, loser `defeated_at` EVENT). `event_battle` entities went
  1 → 7; event-range violations 13 → 7.
- **Overlap consistency**: False → **True** (the `rome ×2` duplicate cleared).

### Iteration 3 — era-aware disambiguation + chronicle re-linking
- **Disambiguation**: ranking was era-blind ("Philip II of Macedon" vs "Philip
  II of Spain" scored equally → picked the 16th-c. Spaniard). Added era-aware
  reranking (`tools/disambiguation.py`): for ambiguous candidates, enrich their
  dates and prefer the one nearest the entity's era (own date, else the
  transcript's median). `Philip II` is no longer Philip-of-Spain.
- **Chronicle re-linking**: event-anchoring (iter2) orphaned entries whose battle
  event wasn't named in `mentioned_entities`. `chronicle_builder` now falls back
  to source-grounded relations → orphans 95 → 79, secondary links 45 → 96.

### Iteration 4 — date robustness
iter3's "signed integer" prompt made the LLM emit **CE** dates as negative
(`-527` for 527 CE) → wrong era and `start_year > end_year` crashes
(`Justinian`, `Opium War`). Fixes:
- Prompt now requires explicit **BCE/CE markers** (LLMs sign reliably with words,
  not minus signs).
- `commit_writer._consistent_dates` drops an end that precedes the start, at the
  single choke point feeding both Laravel temporal-range inserts.

Result: **all 7 transcripts now exit `rc=0`** (both remaining import failures —
Sumerians and Biggest Empires — cleared). Final capstone run (`iter4_dates`):
126 entities, 45 relationships, 7 chronicles, 0 failed runs, overlap consistent.
BCE entities with markers store correctly (`Uruk -3200`, `Lagash -2500..-2000`).

## Known limitations / follow-ups

- **Unmarked deep-BCE dates**: when the LLM emits a bare `2100` (no "BCE"),
  deterministic code can't infer the era, so it stores positive (wrong era). The
  entity still imports; precision needs a dedicated date-resolution step or
  context-era sign inference.
- **Name truncation**: the LLM occasionally truncates ("Ty" for "Tyre") despite
  the full-name instruction; a resolution-time sanity check would help.
- **Event-range violations** (~7–11): the LLM still sometimes targets a person
  instead of the battle event. A validation pass could drop/flag these.
- **Disambiguation latency**: era reranking adds Wikidata enrichment calls; one
  large transcript (Byzantine) ran slow. Consider caching / a tighter ambiguity
  gate.
- **LLM run-to-run variance**: entity/relation counts swing ±15% between runs at
  temperature > 0; trust directional deltas, not single-run absolutes.

## Commits

`b5c9bb3` reducer + seeder · `21e3d40` write-path · `1df1f52` harness + 2 fixes ·
`887a42e` README + relation test · `fc93f0f` iter2 · `7ae7db2` iter3 ·
`c5476a4` iter3 hotfix · `ef7c2ef` iter4 · plus `disambiguation` + `compare`.
