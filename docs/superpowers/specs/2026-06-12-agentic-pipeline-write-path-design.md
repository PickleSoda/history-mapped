# Agentic Pipeline — Write-Path & Reliability — Design Spec

> **Date:** 2026-06-12
> **Status:** Design (approved) — ready for implementation planning
> **Area:** `pipeline/agent/`
> **Source:** Audit [../../plans/12-bug-report.md](../../plans/12-bug-report.md) (PP-1…PP-12) and plan
> [../../plans/11-agentic-pipeline-improvements.md](../../plans/11-agentic-pipeline-improvements.md).
> **Sub-project:** B of the audit-remediation set (critical-first).

## 1. Problem

The LangGraph agentic pipeline (`langgraph.json` → `build_workflow`, a strictly linear 15-node graph) produces correct
JSONL/manifest artifacts but, **on any real run, persists nothing to the database while reporting success.** Three
confirmed critical defects in `commit_writer` combine with several reliability gaps:

- **PP-1 (critical):** JSONL is written to a host path the `app` container cannot see; artisan import finds no files.
- **PP-2 (critical):** the artisan return code is never checked; failures are recorded as successful commits.
- **PP-3 (critical):** relations are sent to `pipeline:import-borders` with a directory argument and an incompatible schema.
- **PP-4 (high):** `chronicle.json` is written but `chronicles:import` is never invoked.
- **PP-7 (high):** `resolve_entity_ids` reads a `record['name']` that `commit_writer` never sets → id resolution no-ops even on success.
- **PP-5 (high):** confidence floor of 0.95 makes the approval gate a rubber-stamp *(covered separately in sub-project C; out of scope here except where the write path depends on it)*.
- **PP-8 (medium):** a schema-invalid LLM item crashes the whole run; prose-wrapped JSON silently empties a list.
- **PP-9 (medium):** no graph-level error routing or checkpointing — one node failure aborts the run with no resume.
- **PP-10 (low):** `approval_gate` appends a plain dict where a `PipelineError` is expected.
- **PP-11 (low):** `resolve_wikidata` overwrites `wikidata_match`, dropping the `existing_entity` dedup flag.
- **PP-12 (low):** in-place mutation of shared state lists under a no-reducer `TypedDict`.

CI is green throughout because the test suite mocks `run_artisan_command`.

## 2. Goals / Non-goals

**Goals**
- Agent-produced entities, relations, and chronicles actually reach Postgres on a real run.
- Failures are visible (manifest + logs) and never silently recorded as success.
- Runs are idempotent (safe to retry a `run_id`) and resumable (survive a transient crash).
- One malformed LLM item degrades gracefully instead of aborting the run.

**Non-goals (handled elsewhere or deferred)**
- Evidence-based confidence scoring → **sub-project C**.
- Temporal-bound semantics → **sub-project E**.
- Implementing DeepAgent disambiguation / style enforcement as *features* — here we only **remove** the dead stubs (the accepted decision); building them is a separate future project.

## 3. Accepted decisions (from the audit Q&A)

- **Artifact location:** write under `api/storage/app/pipeline/agent_runs/<run_id>` (already container-visible via the
  existing `../api:/var/www/html` mount), not a newly-mounted repo `output/`.
- **Relations importer:** reuse the relationship-hint flow (`pipeline:import-border-relations` / `resolve-relationships`)
  by emitting hint records, rather than `import-borders`.
- **Chronicle import:** run `chronicles:import` automatically after `chronicle_writer`, with `--sync` and return-code checking.
- **State model:** convert append-style fields to `Annotated` reducers as part of the checkpointing work.
- **Dead code:** delete `messy_research`, `deepagents/`, the unused `wikipedia` tool, and `style_validator` (unless style
  enforcement is in scope — default: delete), and the no-op `create_chronicle` flag.
- **`db.py`:** distinguish "no rows" from "query failed" (log the latter) and add a startup schema check.

## 4. Architecture

The 15-node linear graph is preserved. Changes are localized to four seams:

```
                         ┌─────────────────────── graph/workflow.py ───────────────────────┐
                         │  + node-wrapper decorator (exception → PipelineError → error edge) │
                         │  + SqliteSaver checkpointer (thread_id = run_id)                   │
   AgentRunState  ───────│  + Annotated reducers for errors/audit_log/committed              │──→ terminal audit sink
   (state.py: reducers)  └───────────────────────────────────────────────────────────────────┘
                                   │                         │                    │
                          commit_writer            chronicle_writer        resolve_entity_ids
                          (container path,         (chronicles:import,     (reads natural keys
                           returncode gate,         returncode gate)        from committed records)
                           hint-schema relations)
                                   │                         │
                              tools/app_api.py  (timeout, returncode surfaced)
                              tools/db.py        (error vs empty distinction, schema check)
                              config.py / llm.py (env model registry, structured output)
```

### 4.1 Components

**`commit_writer` (the core fix).**
- Resolve `output_root` to the container-visible storage path; pass **in-container absolute** paths to artisan.
- For entities: invoke `pipeline:import <path> --sync`; **check `result['returncode']`**; on non-zero, append a
  `PipelineError(node='commit_writer', …)` and record **no** `CommittedChange` for that batch.
- For relations: emit relationship-**hint** JSONL matching the `resolve-relationships` schema, write it to the directory
  layout `import-border-relations` expects, and invoke that command (file/dir per its contract) with returncode checking.
- Record the natural keys (`name`, `entity_type`, and resolved `wikidata_id` where known) inside each `CommittedChange.record`.

**`chronicle_writer`.**
- After writing `chronicle.json`, invoke `chronicles:import <container-path> --sync` (no `--batch-id`; dedup is slug +
  `--force`), with returncode checking and the same failure-recording discipline.

**`resolve_entity_ids`.**
- Read the natural keys `commit_writer` now records (not a missing `record['name']`), so id resolution works on a real import.

**`tools/app_api.py`.**
- Add a timeout to `subprocess.run`; surface `returncode`/`stderr` to callers; never silently swallow a non-zero exit.

**`tools/db.py`.**
- Catch *connection/driver* errors distinctly from "no rows" — log a warning (or raise a typed error) on real failures
  instead of returning `[]` for both. Add a one-time schema check that the assumed columns
  (`entities.entity_id`, `relationships.source_id/target_id/relationship_type`) exist; fail fast with a clear message.

**`graph/workflow.py` + `graph/state.py`.**
- A node-wrapper decorator wraps each node body: on exception, append a `PipelineError` and route via a conditional
  error edge to a terminal audit node (so the manifest is always written). Standardize **all** error appends to
  `PipelineError` (fixes `approval_gate`'s dict — PP-10).
- Compile the graph with a `SqliteSaver` checkpointer keyed by `thread_id = run_id`.
- Convert `errors`, `audit_log`, `committed` in `AgentRunState` to `Annotated[..., operator.add]` (or a custom merger);
  nodes return **partial updates** rather than mutating shared lists and returning the whole state (PP-12). Required for
  safe checkpoint serialization.

**Idempotency.**
- Treat `batch_id = run_id` as the idempotency key end-to-end. Before running, if `manifest.json` for `run_id` exists and
  records success, short-circuit. Preserve `existing_entity` in a dedicated `EnrichedCandidate` field so `resolve_wikidata`
  no longer drops it (PP-11). (The Laravel importers already dedup, so this prevents redundant work, not corruption.)

**Observability.**
- Apply the existing `log_node_start_end` decorator to every node. Record per-node timing, token usage, the model actually
  used, external-call counts, and import returncodes/stderr into `manifest.json`. Optional LangSmith tracing behind an env flag.

**LLM I/O hardening (PP-8).**
- Use provider JSON/tool-calling mode where available; add tolerant extraction (locate the first/last JSON object, strip
  arbitrary fences); validate list items **individually** so one bad record is dropped with a warning, not a crash; move
  model ids + fallback chains to validated env-driven config; fix the bare `gpt-4o*` primaries that OpenRouter rejects;
  add a bounded re-ask on parse failure. `FallbackLLM` distinguishes retryable vs fatal errors.

**Dead-code cleanup.**
- Delete `messy_research`, `deepagents/`, the `wikipedia` tool, `style_validator` (default; or wire it if style
  enforcement is in scope), and the no-op `create_chronicle` flag. Update the runbook to match.

## 5. Data flow

Graph order is unchanged. The differences: `commit_writer`/`chronicle_writer` write to mounted paths and verify return
codes; the chronicle reaches the DB; `resolve_entity_ids` maps real ids; node exceptions route to the terminal audit sink
instead of crashing `invoke()`; the checkpointer persists state between nodes so a crash resumes from the last completed node.

## 6. Error handling

- **Import failures:** non-zero returncode or timeout → `PipelineError` + no `CommittedChange`; surfaced in the manifest.
- **Node exceptions:** caught by the wrapper → `PipelineError` → error edge → terminal audit node (manifest still written).
- **LLM parse failures:** whole-document → one `PipelineError`; per-item → drop the item with a warning, keep the rest.
- **DB driver errors:** logged/typed, not masked as empty results.

## 7. Testing

- A `returncode != 0` test asserting **no** `CommittedChange` is recorded and a `PipelineError` is present.
- A realistic committed-record test driving `resolve_entity_ids` (with the natural keys) → non-empty id maps.
- At least one **integration** test that runs the commit path against a real test Postgres (artisan not mocked) and asserts
  rows land in `entities`/`relationships`/`chronicles`.
- A per-item-validation test: one invalid item among valid ones is dropped, the run continues, the manifest notes it.
- A resumability smoke test: kill after node N, resume, assert no double-write.
- Keep the existing mocked unit tests; add the failure-branch coverage they currently skip.

## 8. Implementation sequencing (feeds the plan)

1. Write-path correctness (paths, returncode gating, relations hints, `resolve_entity_ids` keys, chronicle import) — unblocks everything.
2. Observability (makes the rest visible) + `db.py` error distinction.
3. State reducers → error routing → checkpointer (in that order — reducers first so checkpointing is safe).
4. Idempotency (run-level short-circuit, `existing_entity` preservation).
5. LLM I/O hardening.
6. Dead-code cleanup + runbook sync.

## 9. Risks & mitigations

- **Container path assumptions** — verify the `storage/app` mount in `docker/docker-compose.yml` before relying on it; the
  integration test catches regressions.
- **Reducer migration** — converting to partial-update returns touches every node; do it in one focused pass with the e2e
  test as the guardrail.
- **Relations hint schema** — confirm the exact `resolve-relationships` hint record shape before emitting; if it's heavy,
  a dedicated `agent:import-relations` command is an acceptable fallback (noted as an open decision).
