# Historical Entity Agentic Pipeline — Runbook

> **Status:** MVP — **15-node** LangGraph workflow with mocked-LLM test coverage
> **Date (this revision):** 2026-06-12
> **Package:** `pipeline/agent/`

> ⚠️ **Known critical issues (read before relying on this).** On a real (non-mocked) run the pipeline currently
> **persists nothing to the database while reporting success**: `commit_writer` writes JSONL to a host path the app
> container cannot see, never checks the artisan return code, and sends relations to the wrong importer with a directory
> argument; chronicles are written to disk but never imported. See [../plans/bug-report.md](../plans/bug-report.md)
> (PP-1…PP-7) and the improvement plan [../plans/agentic-pipeline-improvements.md](../plans/agentic-pipeline-improvements.md).
> The MVP is useful today as an **artifact generator** (the JSONL/manifest are correct); the DB-commit half is not yet working.

---

## What It Does

The agentic pipeline accepts raw historical text (video transcripts, articles, book excerpts) and produces structured, validated entity, relation, and **chronicle** proposals. It can auto-commit high-confidence items and flag the rest for human review.

**Example input:**

```text
In 1121, David IV of Georgia defeated Ilghazi at the Battle of Didgori.
```

**Pipeline steps (the compiled linear graph, `graph/workflow.py:48-63`):**

1. **Preprocess** — LLM clean-up/normalization of the raw transcript
2. **Parse** the text into structured events
3. **Extract** candidate entities and relations
4. **Lookup** existing DB entities (deduplication)
5. **Resolve Wikidata** IDs and metadata (Wikidata **REST** API, not SPARQL)
6. **Resolve OHM** geometry
7. **Generate** flowing summaries and relation descriptions
8. **Validate** against type policies and confidence thresholds
9. **Build diff** — sort into create / review / blocked buckets
10. **Approval gate** — auto-commit items above the per-type confidence threshold
11. **Commit** — write entity/relation JSONL and invoke Laravel artisan importers
12. **Resolve entity IDs** — map committed names back to DB ids for chronicle linking
13. **Build chronicle** — assemble the chronicle and its entries from committed items
14. **Write chronicle** — write `chronicle.json` (does **not** import it — see known issues)
15. **Audit** — write a manifest with the full decision trace

> The graph is strictly linear with no conditional edges, interrupts, or checkpointer. `messy_research` exists as an
> unregistered stub and is **not** in the graph; `style_validator`, the `wikipedia` tool, and `deepagents/` are present but
> unused. The `--no-create-chronicle` flag is plumbed into state but read by no node, so it currently has no effect.

---

## Quick Start

```powershell
py -m pipeline agent --input docs/example_transcript.txt --run-id demo_001
```

Output lands in `output/agent_runs/<run_id>/`:

```text
output/agent_runs/demo_001/
├── manifest.json              # Full audit trail
├── entities_to_create.jsonl   # Importer-ready entity records
├── relations_to_create.jsonl  # Importer-ready relation records
└── chronicle.json             # Chronicle + entries (written to disk only; not auto-imported)
```

---

## Commands

### Run the agent on a text file

```powershell
py -m pipeline agent --input transcript.txt --run-id my_run
```

Options:
- `--input PATH` — path to raw historical text (required)
- `--run-id TEXT` — deterministic ID for the artifact directory; defaults to `agent_<filename>`
- `--title TEXT` — optional chronicle title
- `--create-chronicle` / `--no-create-chronicle` — toggle chronicle building (⚠️ currently a no-op: the flag is stored in state but read by no node)

### Run the full test suite

```powershell
py -m pytest pipeline/agent/tests/ -v
```

The suite covers schemas (incl. chronicle), state, config, tools, the graph nodes, workflow compilation, and end-to-end
execution. Note the LLM and artisan calls are **mocked**, so the green suite does not exercise the live DB-commit path —
the known write-path defects are invisible to CI.

---

## Architecture

```text
Raw historical text
        ↓
┌─────────────────────────────────────────────────────────────┐
│  LangGraph Orchestrator  (pipeline/agent/graph/)            │
│  ─────────────────────  (strictly linear, no checkpointer)  │
│  preprocess_transcript → LLM: clean/normalize raw text      │
│  parse_sequence      → LLM: raw text → structured events    │
│  extract_candidates  → LLM: events → entities/relations     │
│  db_lookup           → Check existing PostgreSQL entities   │
│  resolve_wikidata    → Wikidata REST API: QIDs, metadata    │
│  resolve_ohm         → SQLite index: geometry resolution    │
│  generate_content    → LLM: summaries + descriptions        │
│  validate            → Policy: type checks, confidence      │
│  build_diff          → Sort into create/review/blocked      │
│  approval_gate       → Confidence-threshold auto-commit     │
│  commit_writer       → JSONL + artisan pipeline:import*     │
│  resolve_entity_ids  → Map committed names → DB ids         │
│  chronicle_builder   → Assemble chronicle + entries         │
│  chronicle_writer    → Write chronicle.json (no DB import)  │
│  audit_logger        → manifest.json with full trace        │
└─────────────────────────────────────────────────────────────┘
        ↓
  output/agent_runs/<run_id>/
  (* commit_writer's DB import does not currently succeed — see known issues)
```

### Tool Layer

Deterministic wrappers around existing pipeline modules:

| Tool | File | Wraps |
|------|------|-------|
| DB search | `tools/db.py` | `psycopg` direct queries (swallows errors → `[]`) |
| Wikidata | `tools/wikidata.py` | Wikidata **REST** action API (`wbsearchentities` + `Special:EntityData`), via `requests` — not SPARQL |
| Wikipedia | `tools/wikipedia.py` | Wikipedia REST API (**currently unused** by the graph) |
| OHM | `tools/ohm.py` | `xml_lookup.py`, `point_resolver.py` |
| App API | `tools/app_api.py` | `docker compose exec app php artisan …` (no return-code check, no timeout) |

---

## Node Reference

| # | Node | Type | Description |
|---|------|------|-------------|
| 1 | `preprocess_transcript` | LLM (via `create_llm()`) | Cleans/normalizes the raw transcript before parsing |
| 2 | `parse_sequence` | LLM (via `create_llm_with_fallbacks()`) | Converts raw text into `ParsedEvent[]` with labels, dates, and mentioned entities |
| 3 | `extract_candidates` | LLM (via `create_llm_with_fallbacks()`) | Extracts `CandidateEntity[]` and `CandidateRelation[]` from parsed events |
| 4 | `db_lookup` | Deterministic | Queries PostgreSQL for existing entities by name, alias, or Wikidata ID (stores the existing-entity marker in `wikidata_match`) |
| 5 | `resolve_wikidata` | Deterministic | Searches Wikidata via the **REST** action API and enriches candidates with QIDs, dates, coordinates |
| 6 | `resolve_ohm` | Deterministic | Searches the OHM SQLite index by QID or name; resolves best-point geometry |
| 7 | `generate_content` | LLM (via `create_llm_with_fallbacks()`) | Writes 1–2 sentence summaries and directional relation descriptions (note: `style_validator` is **not** invoked — no style enforcement) |
| 8 | `validate` | Deterministic | Checks entity/relation types against allow-lists; seeds confidence at a flat **0.95** + enrichment bonuses (see Risk Policies caveat) |
| 9 | `build_diff` | Deterministic | Sorts validated candidates into `create_entities`, `create_relations`, `review_items`, `blocked_items` |
| 10 | `approval_gate` | Deterministic | Auto-commits items at/above the per-type confidence threshold; flags everything else for review |
| 11 | `commit_writer` | I/O | Writes `entities_to_create.jsonl`/`relations_to_create.jsonl`; invokes `pipeline:import` and `pipeline:import-borders` (⚠️ see known issues — these currently fail silently) |
| 12 | `resolve_entity_ids` | Deterministic | Maps committed entity/relation names back to DB ids for chronicle linking |
| 13 | `chronicle_builder` | Deterministic | Assembles the `Chronicle` and its entries from committed items + resolved ids |
| 14 | `chronicle_writer` | I/O | Writes `chronicle.json` (⚠️ does **not** call `chronicles:import` — the chronicle never reaches the DB) |
| 15 | `audit_logger` | I/O | Writes `manifest.json` with run metadata, counts, audit log, and error list |

---

## Risk Policies

Each entity and relation type has a risk level and auto-commit threshold:

| Risk Level | Types (examples) | Threshold | Auto-commit? |
|------------|------------------|-----------|--------------|
| High | `person`, `political_entity`, `dynasty` | 0.97 | Only if confidence ≥ 0.97 |
| Medium | `city`, `archaeological_culture` | 0.94 | Only if confidence ≥ 0.94 |
| Low | `event_battle`, `event_war`, `trade_route` | 0.90 | Only if confidence ≥ 0.90 |

Configured in `pipeline/agent/config.py`.

> ⚠️ **Caveat — the gate is currently a near-rubber-stamp.** `validate.py` seeds entity confidence at a flat `0.95`
> plus enrichment bonuses (Wikidata/OHM only *add*), so a validated entity with zero external corroboration already sits
> at 0.95. The five low-risk types and every valid relation therefore auto-commit unconditionally; only
> `person`/`political_entity`/`dynasty` (0.97) need a bonus. Confidence is decoupled from evidence quality, and the
> `requires_wikidata` blocking penalty is dead code (no policy sets it). See PP-5 in the bug report and the evidence-based
> rescoring item in the improvement plan.

---

## Output Artifacts

### `manifest.json`

```json
{
  "run_id": "demo_001",
  "timestamp": "2026-06-10T14:32:00+00:00",
  "input_preview": "In 1121, David IV defeated...",
  "parsed_events_count": 1,
  "candidate_entities_count": 4,
  "candidate_relations_count": 2,
  "enriched_entities_count": 4,
  "validation_results_count": 6,
  "committed_count": 1,
  "errors_count": 0,
  "audit_log": [...],
  "errors": []
}
```

### `entities_to_create.jsonl`

```json
{"name": "David IV of Georgia", "entity_type": "person", "summary": "Ruled the Kingdom of Georgia from 1089 to 1125...", "wikidata_id": "Q405", "temporal_start": null, "temporal_end": null, "alternative_names": ["David IV"], "geojson": null, "source_citations": {"created_by": "historical-agent-pipeline", "confidence": 0.98}}
```

> The entity JSONL keys are `temporal_start`/`temporal_end` and `geojson` (not `start_date`/`end_date`/`geometry`),
> matching what `pipeline:import` expects.

### `relations_to_create.jsonl`

```json
{"source_name": "David IV of Georgia", "target_name": "Battle of Didgori", "relationship_type": "participated_in", "start_date": "1121-08-12", "end_date": "1121-08-12", "description": "Commanded the Georgian forces at the Battle of Didgori on August 12, 1121.", "source_citations": {"created_by": "historical-agent-pipeline"}}
```

---

## Environment Variables

Add to `pipeline/.env`:

```dotenv
# OpenAI (default)
OPENAI_API_KEY=sk-...

# Or OpenRouter / any OpenAI-compatible provider
LLM_BASE_URL=https://openrouter.ai/api/v1
OPENAI_API_KEY=sk-or-v1-...
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | — | API key for the LLM provider |
| `LLM_BASE_URL` | No | OpenAI default | Custom base URL for OpenAI-compatible endpoints |

### Provider examples

**OpenRouter** — access 100+ models through a single endpoint:
```dotenv
LLM_BASE_URL=https://openrouter.ai/api/v1
OPENAI_API_KEY=sk-or-v1-...
```
Then override model names in `pipeline/agent/config.py`:
```python
parse_model: str = "anthropic/claude-3.5-sonnet"
extract_model: str = "anthropic/claude-3.5-sonnet"
generate_model: str = "anthropic/claude-3-opus"
```

**Ollama (local)**:
```dotenv
LLM_BASE_URL=http://localhost:11434/v1
OPENAI_API_KEY=ollama  # Ollama ignores this, but LangChain requires a non-empty string
```
```python
parse_model: str = "llama3.1"
extract_model: str = "llama3.1"
generate_model: str = "llama3.1"
```

**vLLM / LM Studio / other local servers**:
```dotenv
LLM_BASE_URL=http://localhost:8000/v1
OPENAI_API_KEY=not-needed
```

The LLM layer is provider-agnostic via `pipeline/agent/llm.py:create_llm()`, which wraps `langchain_openai.ChatOpenAI` with configurable `base_url`, `model`, and `api_key`.

### Model Fallback Chains

Each LLM node has a primary model and an ordered fallback chain. If the primary model fails (rate limit, timeout, 5xx, etc.), the pipeline automatically retries and then falls back to the next model in the chain.

**Default fallback chains** (configured in `pipeline/agent/config.py`):

| Node | Primary | Fallback 1 | Fallback 2 | Fallback 3 |
|------|---------|------------|------------|------------|
| `parse_sequence` | `gpt-4o-mini` | `openai/gpt-oss-20b:free` | `google/gemma-4-26b-a4b-it:free` | `deepseek/deepseek-v3.1-terminus` |
| `extract_candidates` | `gpt-4o-mini` | `google/gemma-4-31b-it:free` | `openai/gpt-oss-120b:free` | `deepseek/deepseek-v3.1-terminus` |
| `generate_content` | `gpt-4o` | `deepseek/deepseek-v3.1-terminus` | `google/gemini-2.5-flash` | `x-ai/grok-4.20` |

Customize by editing `MODEL_FALLBACKS` in `pipeline/agent/config.py`:

```python
MODEL_FALLBACKS: dict[str, list[str]] = {
    "parse_model": [
        "openai/gpt-oss-20b:free",
        "google/gemma-4-26b-a4b-it:free",
        "deepseek/deepseek-v3.1-terminus",
    ],
    "extract_model": [...],
    "generate_model": [...],
}
```

To disable fallbacks, pass an empty dict or set `model_fallbacks={}` when constructing `AgentConfig`.

---

## Testing

```powershell
# All agent tests
py -m pytest pipeline/agent/tests/ -v

# Specific test files
py -m pytest pipeline/agent/tests/test_graph.py -v
py -m pytest pipeline/agent/tests/test_nodes_llm.py -v
py -m pytest pipeline/agent/tests/test_nodes_lookup.py -v
py -m pytest pipeline/agent/tests/test_nodes_proposal.py -v
py -m pytest pipeline/agent/tests/test_nodes_io.py -v
py -m pytest pipeline/agent/tests/test_tools.py -v
```

---

## LangGraph Development UI

For local development with a visual graph, node-execution tracing, and hot reloading, run the
graph under the LangGraph CLI and attach LangSmith Studio.

```powershell
# Install the in-memory dev server (requires Python 3.11+)
py -m pip install "langgraph-cli[inmem]"   # or: uv pip install "langgraph-cli[inmem]"

# Start the local server (hot reload, no Docker)
langgraph dev                              # serves http://localhost:2024

# On Python 3.10, run the server in a container instead:
langgraph dev --wait                       # requires Docker Desktop
```

Open Studio against the local server:

```
https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
```

Studio gives you the workflow graph with per-node execution tracing, real-time state inspection,
and hot reload on code changes — all backed by local state storage.

---

## Module Layout

```text
pipeline/agent/
├── __init__.py
├── __main__.py              # CLI: py -m pipeline agent --input …
├── config.py                # AgentConfig + risk policies
├── llm.py                   # Provider-agnostic LLM factory (OpenAI, OpenRouter, Ollama, etc.)
├── style_guide.md           # Content generation prose rules
├── graph/
│   ├── __init__.py
│   ├── state.py             # AgentRunState TypedDict
│   ├── workflow.py          # StateGraph builder + run_agent()
│   └── nodes/
│       ├── preprocess_transcript.py  # node 1 (LLM clean-up)
│       ├── parse_sequence.py
│       ├── extract_candidates.py
│       ├── db_lookup.py
│       ├── resolve_wikidata.py
│       ├── resolve_ohm.py
│       ├── generate_content.py
│       ├── validate.py
│       ├── build_diff.py
│       ├── approval_gate.py
│       ├── commit_writer.py
│       ├── resolve_entity_ids.py     # maps committed names → DB ids
│       ├── chronicle_builder.py
│       ├── chronicle_writer.py
│       ├── audit_logger.py
│       └── messy_research.py    # Stub — NOT registered in the graph
├── style_validator.py       # Present but NOT invoked by any node
├── tools/
│   ├── db.py                # PostgreSQL search wrapper (errors → [])
│   ├── wikidata.py          # Wikidata REST action API search/enrich (not SPARQL)
│   ├── wikipedia.py         # Wikipedia API summary (unused by the graph)
│   ├── ohm.py               # OHM SQLite + geometry
│   └── app_api.py           # Laravel artisan shell-out
├── schemas/
│   ├── entities.py          # ParsedEvent, CandidateEntity, EnrichedCandidate
│   ├── relations.py         # CandidateRelation, CommittedChange
│   ├── proposals.py         # ProposedDiff, ApprovalDecision
│   ├── validation.py        # ValidationResult, PipelineError, AuditEvent
│   └── chronicle.py         # Chronicle, ChronicleEntry, ChronicleEntryEntity
├── deepagents/
│   └── __init__.py          # package only — the referenced agent stub files do NOT exist
└── tests/
    ├── test_schemas.py
    ├── test_state.py
    ├── test_config.py
    ├── test_llm.py           # LLM factory + fallback chain tests
    ├── test_tools.py
    ├── test_nodes_llm.py
    ├── test_nodes_lookup.py
    ├── test_nodes_proposal.py
    ├── test_nodes_io.py
    └── test_graph.py
```

---

## Design Documents

- **Design spec:** [`docs/archive/superpowers-specs/2026-06-09-historical-entity-agentic-pipeline-design.md`](../archive/superpowers-specs/2026-06-09-historical-entity-agentic-pipeline-design.md)
- **Implementation plan:** [`docs/archive/superpowers-plans/2026-06-09-historical-entity-agentic-pipeline.md`](../archive/superpowers-plans/2026-06-09-historical-entity-agentic-pipeline.md)
