# Agentic Pipeline — Write-Path & Reliability — Implementation Plan

> **Status: 🟡 Partial** — verified 2026-06-15; remaining work tracked in [STATUS.md](../../plans/STATUS.md).
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the LangGraph agent actually persist entities, relations, and chronicles to Postgres (today it writes nothing while reporting success), and make runs observable, idempotent, resumable, and crash-tolerant.

**Architecture:** Keep the 15-node linear graph. Fix the I/O seams (`commit_writer`, `chronicle_writer`, `tools/app_api.py`, `tools/db.py`), add a node-wrapper decorator + `SqliteSaver` checkpointer + `Annotated` state reducers in `graph/workflow.py`/`graph/state.py`, and harden LLM parsing in `llm.py`/the LLM nodes.

**Tech Stack:** Python 3.11+, LangGraph, langchain-openai, psycopg, pytest. Laravel artisan importers are invoked via `docker compose exec`.

**Spec:** [../specs/2026-06-12-agentic-pipeline-write-path-design.md](../specs/2026-06-12-agentic-pipeline-write-path-design.md)

---

## File structure

| File | Responsibility | Change |
|------|----------------|--------|
| `pipeline/agent/config.py` | `AgentConfig`, output dir, model registry | Modify: container-visible output dir default; env-driven model ids |
| `pipeline/agent/tools/app_api.py` | artisan shell-out | Modify: timeout, surface returncode/stderr |
| `pipeline/agent/tools/db.py` | psycopg queries | Modify: distinguish error vs empty; schema check |
| `pipeline/agent/graph/nodes/commit_writer.py` | write JSONL + import | Modify: container paths, returncode gate, relation hints, natural keys |
| `pipeline/agent/graph/nodes/chronicle_writer.py` | write + import chronicle | Modify: invoke `chronicles:import`, returncode gate |
| `pipeline/agent/graph/nodes/resolve_entity_ids.py` | map names→ids | Modify: read natural keys from committed records |
| `pipeline/agent/graph/nodes/resolve_wikidata.py` | enrich + dedup flag | Modify: preserve `existing_entity` |
| `pipeline/agent/graph/nodes/approval_gate.py` | confidence gate | Modify: append `PipelineError` not dict |
| `pipeline/agent/graph/state.py` | `AgentRunState` | Modify: `Annotated` reducers |
| `pipeline/agent/graph/workflow.py` | graph build | Modify: node wrapper, error edge, checkpointer, idempotency guard |
| `pipeline/agent/schemas/entities.py` | `EnrichedCandidate` | Modify: add `existing_entity` field |
| `pipeline/agent/llm.py` | LLM factory | Modify: structured output, retryable-vs-fatal |
| `pipeline/agent/logging.py` | `log_node_start_end` | Apply across nodes |
| Delete | `graph/nodes/messy_research.py`, `deepagents/`, `tools/wikipedia.py`, `style_validator.py` | Remove dead code |

---

## Phase 1 — Write-path correctness (unblocks everything)

### Task 1: Container-visible output directory

**Files:**
- Modify: `pipeline/agent/config.py` (`output_dir` default)
- Test: `pipeline/agent/tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
def test_output_dir_is_container_visible():
    cfg = AgentConfig()
    # Must resolve under the mounted api/storage path so `docker compose exec app` can see it.
    assert cfg.output_dir.endswith("storage/app/pipeline/agent_runs")
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `py -m pytest pipeline/agent/tests/test_config.py::test_output_dir_is_container_visible -v`
Expected: FAIL (current default is `output/agent_runs`).

- [ ] **Step 3: Change the default**

In `config.py`, set `output_dir: str = "api/storage/app/pipeline/agent_runs"` (host side) and add a `container_output_dir` property returning `/var/www/html/storage/app/pipeline/agent_runs/<...>` for arguments passed to artisan. Read an optional `AGENT_OUTPUT_DIR` env override in `__post_init__`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `py -m pytest pipeline/agent/tests/test_config.py -v` → PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/agent/config.py pipeline/agent/tests/test_config.py
git commit -m "fix(agent): write artifacts under container-visible api/storage path"
```

### Task 2: `app_api.py` returns timeout + returncode, never silently swallows

**Files:**
- Modify: `pipeline/agent/tools/app_api.py`
- Test: `pipeline/agent/tests/test_tools.py`

- [ ] **Step 1: Write the failing test** — assert `run_artisan_command` passes a `timeout` to `subprocess.run` and that a non-zero exit is returned (not raised) with `stderr` populated. Use `unittest.mock.patch` on `subprocess.run`.

```python
def test_run_artisan_command_uses_timeout_and_surfaces_returncode(monkeypatch):
    calls = {}
    def fake_run(cmd, **kw):
        calls.update(kw)
        class R: returncode = 1; stdout = ""; stderr = "boom"
        return R()
    monkeypatch.setattr("pipeline.agent.tools.app_api.subprocess.run", fake_run)
    out = run_artisan_command(["pipeline:import", "x"])
    assert calls.get("timeout") is not None
    assert out["returncode"] == 1 and out["stderr"] == "boom"
```

- [ ] **Step 2: Run → FAIL.** `py -m pytest pipeline/agent/tests/test_tools.py -k run_artisan -v`
- [ ] **Step 3: Implement** — add `timeout=cfg.artisan_timeout` (default 300s) to `subprocess.run`; wrap in `try/except subprocess.TimeoutExpired` returning `{"returncode": 124, "stdout": "", "stderr": "timeout"}`.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `fix(agent): add timeout and surface returncode in run_artisan_command`

### Task 3: `commit_writer` gates on returncode and records natural keys

**Files:**
- Modify: `pipeline/agent/graph/nodes/commit_writer.py`
- Test: `pipeline/agent/tests/test_nodes_io.py`

- [ ] **Step 1: Write the failing test** — patch `run_artisan_command` to return `returncode: 1`; assert the node appends a `PipelineError(node="commit_writer")` and records **no** entity `CommittedChange`.

```python
def test_commit_writer_failed_import_records_error_not_commit(monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "run_artisan_command", lambda *a, **k: {"returncode":1,"stdout":"","stderr":"x"})
    state = make_state_with_one_entity(tmp_path)
    out = commit_writer(state)
    assert any(e.node == "commit_writer" for e in out["errors"])
    assert all(c.change_type != "entity" for c in out["committed"])
```

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — after `result = run_artisan_command(cmd)`, branch on `result["returncode"]`; on non-zero append `PipelineError` and `continue` without appending the `CommittedChange`. In the success branch, set `record={"path":..., "count":..., "name": entity["name"], "entity_type": entity["entity_type"], "wikidata_id": entity.get("wikidata_id")}`. Pass `cfg.container_output_dir`-based absolute paths to `build_artisan_command`.
- [ ] **Step 4: Run → PASS** (`test_nodes_io.py` full file).
- [ ] **Step 5: Commit** `fix(agent): gate commit_writer on artisan returncode and record natural keys`

### Task 4: Route relations to the relationship-hint importer

**Files:**
- Modify: `pipeline/agent/graph/nodes/commit_writer.py` (relation branch)
- Test: `pipeline/agent/tests/test_nodes_io.py`

- [ ] **Step 1: Write the failing test** — assert the relation branch writes `ohm_relation_hints.jsonl` (hint schema) into a `relations_final/` dir and calls `pipeline:import-border-relations` with that **directory** path (its documented contract), not `pipeline:import-borders` with `output_root`.

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — replace `_relation_to_jsonl_record` output with the hint record shape `ResolveRelationshipsJob` consumes (confirm exact keys against `api/app/Jobs/ResolveRelationshipsJob.php` and `ImportBorderRelationsCommand.php`); write to `relations_final/ohm_relation_hints.jsonl`; call `pipeline:import-border-relations <relations_final dir> --sync --batch-id=<run_id>`.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `fix(agent): import agent relations via relationship-hint flow, not import-borders`

> **Decision dependency:** if the hint schema proves too heavy to emit, fall back to a dedicated `agent:import-relations` Laravel command (out of scope for this plan; raise it before implementing this task).

### Task 5: `resolve_entity_ids` reads the recorded natural keys

**Files:**
- Modify: `pipeline/agent/graph/nodes/resolve_entity_ids.py`
- Test: `pipeline/agent/tests/test_nodes_chronicle_ids.py`

- [ ] **Step 1: Write the failing test** — build a committed entity record with `{"name": "...", "entity_type": "..."}` (as Task 3 now produces) and assert `entity_id_map` is populated via `search_entity_by_name`.
- [ ] **Step 2: Run → FAIL** (today it reads a `record["name"]` that doesn't exist).
- [ ] **Step 3: Implement** — read `record.get("name")`/`record.get("entity_type")` exactly as Task 3 writes them; keep the DB lookup.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `fix(agent): resolve_entity_ids reads natural keys recorded by commit_writer`

### Task 6: `chronicle_writer` imports the chronicle

**Files:**
- Modify: `pipeline/agent/graph/nodes/chronicle_writer.py`
- Test: `pipeline/agent/tests/test_chronicle_writer.py`

- [ ] **Step 1: Write the failing test** — patch `run_artisan_command`; assert after writing `chronicle.json` the node calls `chronicles:import <container path> --sync` and gates on returncode.
- [ ] **Step 2: Run → FAIL** (no import call today).
- [ ] **Step 3: Implement** — import `build_artisan_command`/`run_artisan_command`; after the file write, invoke `chronicles:import` with the container path and `--sync`; on non-zero returncode append a `PipelineError` and do not mark the chronicle committed. Note: `chronicles:import` takes no `--batch-id`.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `feat(agent): import chronicle.json via chronicles:import after writing`

### Task 7: Integration test — real artisan import against a test DB

**Files:**
- Test: `pipeline/agent/tests/test_commit_integration.py` (new, marked `@pytest.mark.integration`)

- [ ] **Step 1: Write the test** — given a seeded test Postgres and a one-entity state, run the real `commit_writer` (artisan **not** mocked) and assert a row appears in `entities` with the expected `wikidata_id`.
- [ ] **Step 2: Run → FAIL** until Tasks 1–3 land; then PASS.
- [ ] **Step 3: Document** the `pytest -m integration` invocation + required env (`DATABASE_URL`, docker compose up) in the runbook.
- [ ] **Step 4: Commit** `test(agent): integration test for real DB commit path`

---

## Phase 2 — Observability + db.py error distinction

### Task 8: `db.py` distinguishes query failure from empty result + schema check

**Files:**
- Modify: `pipeline/agent/tools/db.py`
- Test: `pipeline/agent/tests/test_tools.py`

- [ ] **Step 1: Write failing tests** — (a) a forced `psycopg.Error` is logged/raised (not returned as `[]`); (b) `ensure_schema()` raises a clear error when a required column is absent.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — catch `psycopg.Error` separately from a normal empty cursor; `logger.warning` (or raise a typed `DbUnavailable`) on real errors; add `ensure_schema()` checking `entities.entity_id` and `relationships.source_id/target_id/relationship_type` via `information_schema.columns`, called once at run start.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `fix(agent): distinguish DB errors from empty results; add schema check`

### Task 9: Apply `log_node_start_end` + per-node metrics into the manifest

**Files:**
- Modify: `pipeline/agent/logging.py`, each node, `pipeline/agent/graph/nodes/audit_logger.py`
- Test: `pipeline/agent/tests/test_nodes_io.py`

- [ ] **Step 1: Write failing test** — assert `manifest.json` includes a `node_metrics` array with `{node, duration_ms, model, external_calls}` entries.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — decorate node functions with `log_node_start_end`; accumulate timing/model/external-call counts into `state["audit_log"]`/a `metrics` field; have `audit_logger` serialize them. Also record each artisan `returncode`/`stderr` summary.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `feat(agent): structured per-node metrics in manifest`

---

## Phase 3 — State reducers → error routing → checkpointer (order matters)

### Task 10: `Annotated` reducers + partial-update returns

**Files:**
- Modify: `pipeline/agent/graph/state.py` and every node's `return`
- Test: `pipeline/agent/tests/test_state.py`, `test_graph.py`

- [ ] **Step 1: Write failing test** — assert `AgentRunState.__annotations__["errors"]` is an `Annotated` type with an `operator.add` reducer; assert the e2e graph still accumulates `audit_log` correctly when nodes return partial updates.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — annotate `errors`, `audit_log`, `committed` with `Annotated[list[...], operator.add]`; change nodes to `return {"errors": [err]}` style partial updates rather than mutating shared lists and returning the whole dict.
- [ ] **Step 4: Run → PASS** (`test_graph.py` e2e).
- [ ] **Step 5: Commit** `refactor(agent): Annotated reducers + partial-update node returns`

### Task 11: Node-wrapper decorator → `PipelineError` + error edge

**Files:**
- Create: `pipeline/agent/graph/node_wrapper.py`
- Modify: `pipeline/agent/graph/workflow.py`, `approval_gate.py`
- Test: `pipeline/agent/tests/test_graph.py`

- [ ] **Step 1: Write failing test** — a node that raises routes to a terminal audit node and the manifest is still written with the error recorded (run does not crash).
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — `with_error_capture(fn)` wraps each node; on exception returns `{"errors":[PipelineError(node=fn.__name__, ...)], "_failed": True}`; add a conditional edge routing `_failed` to `audit_logger`/END. Fix `approval_gate` to append a `PipelineError` (not a dict).
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `feat(agent): per-node error capture and error-routing edge`

### Task 12: `SqliteSaver` checkpointer + resumability

**Files:**
- Modify: `pipeline/agent/graph/workflow.py`, `__main__.py`
- Test: `pipeline/agent/tests/test_graph.py`

- [ ] **Step 1: Write failing test** — compile with a checkpointer and `thread_id=run_id`; assert state persists across an interrupted/resumed `invoke`.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — `workflow.compile(checkpointer=SqliteSaver.from_conn_string(...))`; pass `config={"configurable":{"thread_id":run_id}}` to `invoke`.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `feat(agent): SqliteSaver checkpointer keyed by run_id`

---

## Phase 4 — Idempotency

### Task 13: Run-level short-circuit + preserve `existing_entity`

**Files:**
- Modify: `pipeline/agent/graph/workflow.py` (or `__main__.py`), `resolve_wikidata.py`, `schemas/entities.py`
- Test: `pipeline/agent/tests/test_nodes_lookup.py`, `test_graph.py`

- [ ] **Step 1: Write failing tests** — (a) re-running a `run_id` whose manifest records success short-circuits; (b) a candidate carrying both `existing_entity` and `wikidata_id` keeps `existing_entity` after `resolve_wikidata`.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — add `EnrichedCandidate.existing_entity` field; in `resolve_wikidata` write the QID into a sub-key without clobbering `existing_entity` (or move the marker to the new field); in run entry, if `manifest.json` for `run_id` exists with no errors, return early.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `feat(agent): run-level idempotency guard; preserve existing_entity dedup flag`

---

## Phase 5 — LLM I/O hardening

### Task 14: Tolerant parsing + per-item validation

**Files:**
- Modify: `pipeline/agent/graph/nodes/parse_sequence.py`, `extract_candidates.py`, `generate_content.py`; add a shared `pipeline/agent/graph/nodes/_json.py`
- Test: `pipeline/agent/tests/test_nodes_llm.py`

- [ ] **Step 1: Write failing tests** — (a) prose-wrapped JSON is still extracted; (b) a list with one schema-invalid item drops that item with a warning and keeps the valid ones (no crash).
- [ ] **Step 2: Run → FAIL** (today a `ValidationError` propagates uncaught).
- [ ] **Step 3: Implement** — `extract_json_object(text)` locating the first balanced `{...}`/`[...]`; build models in a per-item loop catching `pydantic.ValidationError` and appending a `PipelineError`/warning per bad item; keep valid items.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `fix(agent): tolerant JSON extraction and per-item validation in LLM nodes`

### Task 15: Env-driven model registry + correct OpenRouter prefixes

**Files:**
- Modify: `pipeline/agent/config.py`, `pipeline/agent/llm.py`
- Test: `pipeline/agent/tests/test_llm.py`, `test_config.py`

- [ ] **Step 1: Write failing test** — primary model ids resolve to provider-correct names (e.g. `openai/gpt-4o-mini` under an OpenRouter base URL) and are overridable via env.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — read `PARSE_MODEL`/`EXTRACT_MODEL`/`GENERATE_MODEL` (and fallback chains) from env in `__post_init__`; when `LLM_BASE_URL` is OpenRouter, prefix bare OpenAI names with `openai/`. Have `FallbackLLM` treat 4xx model-not-found as fatal (skip to next) and 429/5xx as retryable.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `fix(agent): env-driven model registry and OpenRouter-correct primary ids`

---

## Phase 6 — Dead-code cleanup + docs

### Task 16: Remove dead modules and the no-op flag

**Files:**
- Delete: `pipeline/agent/graph/nodes/messy_research.py`, `pipeline/agent/deepagents/`, `pipeline/agent/tools/wikipedia.py`, `pipeline/agent/style_validator.py` (+ their tests)
- Modify: `pipeline/agent/__main__.py` (remove `--create-chronicle` no-op or wire it), `docs/implementation-docs/agentic-pipeline-runbook.md`

- [ ] **Step 1:** Grep to confirm zero non-test importers: `rg "messy_research|deepagents|wikipedia|style_validator" pipeline/agent --glob '!**/tests/**'`. Expected: no hits.
- [ ] **Step 2:** Delete the modules + their tests; remove the `--create-chronicle` flag (or make a node read it).
- [ ] **Step 3:** Run the full suite: `py -m pytest pipeline/agent/tests -v` → PASS.
- [ ] **Step 4:** Update the runbook module-layout/dead-code notes to match.
- [ ] **Step 5: Commit** `chore(agent): remove dead modules and no-op create_chronicle flag`

---

## Self-review (coverage)

- PP-1 → Task 1, 3 (paths). PP-2 → Task 2, 3 (returncode). PP-3 → Task 4 (relation hints). PP-4 → Task 6. PP-7 → Task 3, 5. PP-8 → Task 14. PP-9 → Task 11, 12. PP-10 → Task 11. PP-11 → Task 13. PP-12 → Task 10. Observability → Task 9. db.py → Task 8. Dead code → Task 16. Integration coverage → Task 7. **No spec requirement is unmapped.**
- Confidence floor (PP-5) is intentionally **out of scope** here — sub-project C.

## Execution handoff

Two execution options when you're ready: **(1) Subagent-driven** (fresh subagent per task, review between tasks — recommended) or **(2) Inline** (batched with checkpoints). Phase 1 must land and stay green before Phase 3's reducer refactor.
