# Agentic Pipeline Improvement Plan

> **Status: 🟡 Partial** — verified 2026-06-15; remaining work tracked in [STATUS.md](STATUS.md).
> **Date:** 2026-06-12
> **Scope:** `pipeline/agent/` — the LangGraph entity/relation/chronicle pipeline (`langgraph.json` → `build_workflow`).
> **Audit basis:** Read-only GitNexus-guided audit of `graph/workflow.py`, `graph/state.py`, all `graph/nodes/*`,
> `tools/*`, `schemas/*`, `llm.py`, `config.py`, and the test suite. Every bug cited here was adversarially verified;
> see [12-bug-report.md](12-bug-report.md) for the full evidence.

---

## 1. Current state (as built, not as documented)

The compiled graph is a **strictly linear 15-node chain** (`workflow.py:48-63`), no conditional edges, no interrupts,
no checkpointer:

```
preprocess_transcript → parse_sequence → extract_candidates → db_lookup → resolve_wikidata
  → resolve_ohm → generate_content → validate → build_diff → approval_gate
  → commit_writer → resolve_entity_ids → chronicle_builder → chronicle_writer → audit_logger → END
```

- **LLM nodes:** `preprocess_transcript` uses `create_llm`; `parse_sequence`/`extract_candidates`/`generate_content`
  use `create_llm_with_fallbacks` (`FallbackLLM`). Primary models `gpt-4o-mini`/`gpt-4o`; fallback chains are real
  OpenRouter models. Only `OPENAI_API_KEY` and `LLM_BASE_URL` are read from env — model names are **not** env-overridable.
- **Deterministic nodes:** `db_lookup` (psycopg), `resolve_wikidata` (Wikidata **REST** `wbsearchentities` + `Special:EntityData`,
  not SPARQL), `resolve_ohm` (OHM SQLite + point resolver), `validate`, `build_diff`, `approval_gate`, `resolve_entity_ids`,
  `chronicle_builder`.
- **I/O nodes:** `commit_writer` (shells out to `php artisan pipeline:import` / `pipeline:import-borders` via
  `docker compose exec`), `chronicle_writer` (writes `chronicle.json` — **does not import it**), `audit_logger` (`manifest.json`).
- **State:** `AgentRunState` is a plain `TypedDict` with **no `Annotated` reducers**; nodes mutate shared lists in place
  and `return state`.
- **Dead / unwired:** `messy_research` (stub, not registered in the graph), `style_validator` (never imported by any node),
  the `wikipedia` tool (unused), `deepagents/` (only `__init__.py` — the referenced agent stubs don't exist), the
  `log_node_start_end` decorator (unused), and the `create_chronicle` state flag (`--no-create-chronicle` has no effect
  because no node reads it).
- **Output:** `output/agent_runs/<run_id>/` → `manifest.json`, `entities_to_create.jsonl`
  (keys `temporal_start`/`temporal_end`/`alternative_names`/`geojson`), `relations_to_create.jsonl`, `chronicle.json`.

### The load-bearing problem
**On any real (non-mocked) run, the pipeline persists nothing to the database while reporting success.** Three confirmed
**critical** bugs in `commit_writer` combine: the JSONL is written to a host path the app container can't see (PP-1),
the artisan return code is never checked (PP-2), and relations are sent to the wrong importer with a directory argument
(PP-3). Chronicles aren't imported at all (PP-4). Downstream, id resolution no-ops (PP-7) and the chronicle gets synthetic
non-UUID ids (PP-6). The test suite mocks `run_artisan_command`, so CI is green throughout.

---

## 2. Reliability gaps → bug map

| Gap | Bugs (see bug report) |
|---|---|
| Write path doesn't reach the DB | PP-1, PP-2, PP-3, PP-4 (all critical/high) |
| Id resolution silently empty | PP-7, PP-6 |
| Approval gate is a rubber stamp | PP-5 |
| One bad LLM item / transient failure kills the run | PP-8, PP-9 |
| No idempotency / run-level guard | (refuted as data-dup, but the missing short-circuit is real) |
| State model blocks parallelism/checkpointing | PP-12 |
| Error-object type inconsistency | PP-10 |
| Dedup flag dropped | PP-11 |

---

## 3. Prioritized improvement backlog (no code)

Ordering: **restore correctness first** (a pipeline that writes nothing is the top priority), then graceful failure,
then trust (confidence), then robustness, then resumability, then observability/cost, then dead-code cleanup. Each item
is the auditor's plan with verified bug references. Blast radii are LOW in the static call graph because every node is
string-wired (`add_node('name', fn)`), so `impact()` shows 0 callers; the **runtime** blast radius is the whole write
half of the linear graph — noted per item.

### P1 — Fix the write path end-to-end · effort M · runtime-critical
Make `commit_writer`/`chronicle_writer` write to a **container-mounted** location and pass in-container **absolute**
paths; route relations to a real relationship importer with a **file** (not directory) argument; invoke
`chronicles:import` for `chronicle.json`; **check `result['returncode']`** on every artisan call and convert failures
into a `PipelineError` without recording a successful `CommittedChange`; add a timeout to `run_artisan_command`. Also fix
`resolve_entity_ids` reading a `record['name']` that `commit_writer` never sets (PP-7).
**Fixes:** PP-1, PP-2, PP-3, PP-4, PP-7.
**Impact:** turns "writes nothing while reporting success" into a pipeline that actually persists entities, relations, and
chronicles and surfaces real import failures.
**Prereqs:** decide the volume strategy (mount repo `output/` into `app`, or write under `api/storage/app/pipeline`);
confirm the correct relations command + JSONL schema (`import-border-relations`/`resolve-relationships`) and `chronicles:import`. See open questions 8a–c.

### P2 — Standardize error objects + per-node failure routing · effort M
Make every node append a `PipelineError` (never a raw dict — fixes PP-10), wrap node bodies in a decorator that captures
exceptions into state and routes to a terminal audit node via an error edge, so a single node failure yields an
inspectable `manifest.json` instead of a crash.
**Fixes:** PP-10; mitigates PP-8/PP-9 blast.
**Impact:** eliminates the guaranteed-`AttributeError` path and makes runs degrade gracefully.
**Prereqs:** decide terminal-vs-skip semantics; make `audit_logger` the safe sink.

### P3 — Evidence-based confidence scoring + recalibrated thresholds · effort M
Compute `final_confidence` from deterministic signals (exact Wikidata label/description match, OHM geometry presence, DB
corroboration, date overlap, ambiguity penalties) per the design; stop seeding at 0.95; separate
`llm_confidence`/`system_confidence`/`final_confidence`; retune `ENTITY_RISK_POLICIES`/relation thresholds against the new
scale; decide whether missing-Wikidata should hard-block high-risk types (the `requires_wikidata` penalty is currently
**dead code** — no policy sets the key).
**Fixes:** PP-5.
**Impact:** restores the auto-commit vs human-review distinction so only corroborated items auto-commit.
**Prereqs:** agreement on the formula + per-type thresholds; the write-path fix so committed items are real. See open question 9.

### P4 — Harden LLM I/O: structured output, tolerant parsing, per-item validation · effort M
Use provider JSON/tool-calling mode where available; add robust extraction (first/last JSON object, arbitrary fence
stripping); validate list items **individually** so one bad record is dropped, not the whole batch (and a schema-invalid
item no longer crashes the run — PP-8); move model ids + fallback chains to validated **env-driven** config and fix the
mis-prefixed `gpt-4o*` primaries that OpenRouter rejects; add a bounded re-ask on parse failure.
**Fixes:** PP-8; the residual real issue from the refuted "hallucinated models" item.
**Impact:** sharply reduces silent empty-output runs (especially with free/non-tool fallback models) and makes provider
switching reliable.
**Prereqs:** know the targeted providers/models; `FallbackLLM` should distinguish retryable vs fatal errors.

### P5 — Idempotent writes with natural keys + run-level guard · effort L
Dedup entities by `wikidata_id`/normalized name within `batch_id`; upsert-on-conflict in the importer; gate chronicle
import by slug+run_id; short-circuit a run whose `run_id` already has a successful manifest; treat `batch_id=run_id` as
the idempotency key consistently; fix `resolve_wikidata` dropping the `existing_entity` flag (PP-11).
**Fixes:** PP-11; the missing run-level short-circuit (the refuted non-idempotency item's real residual).
**Impact:** safe retries — re-running a `run_id` doesn't redo all work or risk double-writes; correct reuse-vs-create.
**Prereqs:** coordinated change with the Laravel importers; **P1 landed first**. (Note: the Laravel importers already
dedup, so this is mostly about avoiding redundant work and making reuse decisions correct, not preventing corruption.)

### P6 — Checkpointing + resumability · effort M
Compile the graph with a persistent checkpointer (e.g. `SqliteSaver`) keyed by `run_id`/`thread_id` so partial progress
survives a crash and resumes from the last completed node; treat the on-disk artifacts as durable checkpoints.
**Fixes:** PP-9 (resumability half); requires PP-12 (reducers) to be safe.
**Impact:** long multi-entity runs survive transient LLM/Docker/DB failures without redoing prior LLM/network work.
**Prereqs:** P2 (error routing) + P5 (idempotency) so resume doesn't double-write; **PP-12 reducers** so checkpoint
serialization doesn't break the in-place-mutation accumulation.

### P7 — Observability: structured logs, run metrics, tracing · effort S
Apply the existing (unused) `log_node_start_end` decorator to all nodes; emit per-node timing, token usage, the LLM model
actually used, external-call counts, and import return codes/stderr summaries into `manifest.json`; add optional LangSmith
tracing.
**Impact:** makes the silent-failure modes above observable; surfaces cost per node/run.
**Prereqs:** none (decorator + manifest already exist).

### P8 — Cost & latency: cache/batch external calls, model tiering, token budgets · effort M
Cache Wikidata search/enrich (and DB lookups) within and across runs; batch `enrich_wikidata_entities` instead of one HTTP
GET per QID; keep cheap models for parse/extract and reserve the expensive model for `generate`; cap prompt sizes / add
chunking for large transcripts.
**Impact:** lower per-run cost and wall time, fewer rate-limit-induced fallbacks, bounded cost on large inputs.
**Prereqs:** P4 (model registry); a cache layer (filesystem or Redis) + TTL decisions.

### P9 — Resolve the dead code: implement or delete · effort S
Either wire in `style_validator.validate_all` in `generate_content` (writing the `style_validation.json` the docs promise,
with a bounded self-correction re-ask) and implement/route `messy_research`/DeepAgent disambiguation for ambiguous Wikidata
matches as the design intends — **or** delete `style_validator`, `messy_research`, `deepagents/`, and the `wikipedia` tool
and update the docs. Also decide whether `create_chronicle` should actually gate chronicle building (today `--no-create-chronicle`
does nothing).
**Impact:** removes misleading orphaned paths and either delivers or stops promising the documented quality/disambiguation features.
**Prereqs:** a product decision on whether style enforcement + DeepAgent disambiguation are in scope. See open question 11.

---

## 4. Observability & cost (summary)
- **Observability (P7)** is cheap and unblocks everything else — without per-node returncode/error visibility, the
  critical write-path failures look like green runs. Do it early even though it's ranked after the correctness fixes.
- **Cost (P8)** is real but secondary; the biggest current waste is the mis-prefixed primary model causing ~2 failed
  attempts per LLM node before falling back (fixed in P4), and one HTTP GET per QID in Wikidata enrichment.

## 5. Open questions for the owner
(Consolidated with the cross-workstream list in the final summary; pipeline-specific ones:)
1. **Write target (8a):** mount repo `output/` into the `app` container, or have the agent write under
   `api/storage/app/pipeline` so `pipeline:import` can see it?
2. **Relations import (8b):** the agent uses `pipeline:import-borders`; the relationship-hint flow
   (`import-border-relations`/`resolve-relationships`) looks correct — confirm the target command + JSONL schema.
3. **Chronicle import (8c):** should `chronicles:import` run automatically after `chronicle.json` is written, or is it a
   deliberate manual step?
4. **Confidence (9):** agree the evidence-based scoring formula + per-type auto-commit thresholds, and whether
   missing-Wikidata hard-blocks high-risk types.
5. **State model:** is the no-reducer `TypedDict` + in-place mutation an intentional MVP simplification, or should it move
   to `Annotated` reducers before any parallelism/checkpointing (prerequisite for P6)?
6. **Scope (11):** implement `style_validator` + `messy_research`/DeepAgent + the `wikipedia` tool, or delete them as dead
   code and correct the docs?
7. **Schema reality check:** does the live Postgres actually expose the column names `tools/db.py` assumes
   (`entities.entity_id`, `relationships.source_id/target_id/relationship_type`)? A mismatch is silently swallowed
   (`except: return []`), making `db_lookup`/`resolve_entity_ids` no-op without error.
