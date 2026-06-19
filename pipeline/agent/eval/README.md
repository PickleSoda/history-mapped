# Agentic Pipeline Evaluation Harness

A reproducible loop for evaluating the historical-entity agent end-to-end:
reset the database to a blank slate, run the pipeline over a set of transcripts,
read back what actually persisted, apply quality heuristics, and emit a report
you can diff across iterations.

## Prerequisites

1. **Docker stack up** (Postgres + app):
   ```bash
   docker compose -f docker/docker-compose.yml up -d
   ```
2. **Host Python** (`py` launcher, Python 3.10) with the pipeline deps and
   `pytest` installed. The Linux `pipeline/.venv` is for containers and is not
   used by the harness.
3. **`pipeline/.env`** (gitignored) must contain, at minimum:
   ```dotenv
   # Must match docker/docker-compose.yml (POSTGRES_USER/DB = history-mapped, password secret)
   DATABASE_URL=postgresql://history-mapped:secret@localhost:5432/history-mapped
   # LLM provider (OpenRouter-style); used by the extraction/generation nodes
   LLM_BASE_URL=...
   OPENAI_API_KEY=...
   ```
   > The pipeline loads this file via `pipeline/config.py` (`load_dotenv`). If
   > `DATABASE_URL` points at the wrong user/db (a stale `wikiglobe` value was the
   > original bug), entity-id resolution silently finds nothing and chronicles
   > orphan.

## Running

```bash
# Full pass: reset to blank baseline, run all transcripts, label the report "iter1"
py -m pipeline.agent.eval --label iter1

# Fast iteration loop on just the two overlapping Alexander transcripts, no reset
py -m pipeline.agent.eval --label alex --no-reset --only alexander

# First two transcripts only (smoke)
py -m pipeline.agent.eval --label smoke --limit 2
```

Transcripts are read from `output/transctipts/*.txt` by default
(`--transcripts-dir` to override).

## Output

Each run writes to `output/eval_runs/<label>/`:

- **`report.md`** — human-readable: per-run health table (rc, committed,
  errors, audit-log length + reducer-sanity), persisted DB counts, quality
  flags, overlap-consistency, and a chronicles table.
- **`report.json`** — the same data as structured JSON for diffing/automation.

## What the report checks

| Section | Catches |
|---|---|
| Runs table | reducer blow-up (`audit_len`), false success (`committed` vs DB), per-run errors |
| DB state | what actually persisted (entities/relations/chronicles, geometry, wikidata coverage) |
| Quality flags | `defeated_at → non-event` range violations, duplicate/self-loop relations, ≤2-char names, missing temporal/geometry |
| Overlap consistency | the same identity (e.g. "Alexander the Great") duplicated across overlapping transcripts instead of deduped |
| Chronicles | entry counts, orphan (null `primary_relationship_id`) entries, resolved secondary-entity links |

## Blank-slate seeding

`--reset` runs:
```bash
php artisan migrate:fresh --seeder=Database\\Seeders\\DatabaseSeeder --force
```
The default `DatabaseSeeder` seeds roles, permissions, dev users, and reference
tables **only** — the `entities`, `relationships`, and `chronicles` tables start
empty so the pipeline is the sole author of that content. (For a populated demo
dataset instead, seed `DemoSeeder`, which loads the entity/relationship/chronicle
fixtures on top of this base.)

## Iteration workflow

1. Run `--label iterN`, read `report.md`.
2. Apply a focused change (e.g. disambiguation, relationship semantics).
3. Re-run `--label iterN+1`.
4. Diff the two iterations:
   ```bash
   py -m pipeline.agent.eval.compare iterN iterN+1
   ```
   prints a metric-delta table (entities, relationships, event-range violations,
   orphans, overlap consistency, …) with `[better]`/`[worse]` markers and writes
   `comparison_vs_<iterN>.md` under the newer run's folder.

> Don't edit pipeline node modules while a run is in flight — the harness spawns
> a fresh `py -m pipeline agent` subprocess per transcript, so mid-run edits make
> the batch inconsistent.
