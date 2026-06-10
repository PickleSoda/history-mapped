# Historical Entity Agentic Pipeline — Runbook

> **Status:** MVP complete — 11-node LangGraph workflow with mocked-LLM test coverage  
> **Date:** 2026-06-10  
> **Package:** `pipeline/agent/`

---

## What It Does

The agentic pipeline accepts raw historical text (video transcripts, articles, book excerpts) and produces structured, validated entity and relation proposals. It can auto-commit high-confidence items and flag the rest for human review.

**Example input:**

```text
In 1121, David IV of Georgia defeated Ilghazi at the Battle of Didgori.
```

**Pipeline steps:**

1. **Parse** the text into structured events
2. **Extract** candidate entities and relations
3. **Lookup** existing DB entities (deduplication)
4. **Resolve** Wikidata IDs and metadata
5. **Resolve** OpenHistoricalMap geometry
6. **Generate** flowing summaries and relation descriptions
7. **Validate** against type policies and confidence thresholds
8. **Build diff** — sort into create / review / blocked buckets
9. **Approval gate** — auto-commit low-risk, high-confidence items
10. **Commit** — write JSONL artifacts and invoke Laravel artisan commands
11. **Audit** — write a manifest with full decision trace

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
└── relations_to_create.jsonl  # Importer-ready relation records
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

### Run the full test suite

```powershell
py -m pytest pipeline/agent/tests/ -v
```

31 tests covering schemas, state, config, tools, all 12 nodes, workflow compilation, and end-to-end execution.

---

## Architecture

```text
Raw historical text
        ↓
┌─────────────────────────────────────────────────────────────┐
│  LangGraph Orchestrator  (pipeline/agent/graph/)            │
│  ─────────────────────                                     │
│  parse_sequence      → LLM: raw text → structured events    │
│  extract_candidates  → LLM: events → entities/relations     │
│  db_lookup           → Check existing PostgreSQL entities   │
│  resolve_wikidata    → SPARQL: QIDs, metadata, dates        │
│  resolve_ohm         → SQLite index: geometry resolution    │
│  generate_content    → LLM: summaries + descriptions        │
│  validate            → Policy: type checks, confidence      │
│  build_diff          → Sort into create/review/blocked      │
│  approval_gate       → Risk-based auto-commit threshold     │
│  commit_writer       → JSONL + artisan pipeline:import      │
│  audit_logger        → manifest.json with full trace        │
└─────────────────────────────────────────────────────────────┘
        ↓
  output/agent_runs/<run_id>/
```

### Tool Layer

Deterministic wrappers around existing pipeline modules:

| Tool | File | Wraps |
|------|------|-------|
| DB search | `tools/db.py` | `psycopg` direct queries |
| Wikidata | `tools/wikidata.py` | SPARQL via `requests` |
| Wikipedia | `tools/wikipedia.py` | Wikipedia REST API |
| OHM | `tools/ohm.py` | `xml_lookup.py`, `point_resolver.py` |
| App API | `tools/app_api.py` | `docker compose exec app php artisan …` |

---

## Node Reference

| # | Node | Type | Description |
|---|------|------|-------------|
| 1 | `parse_sequence` | LLM (via `create_llm()`) | Converts raw text into `ParsedEvent[]` with labels, dates, and mentioned entities |
| 2 | `extract_candidates` | LLM (via `create_llm()`) | Extracts `CandidateEntity[]` and `CandidateRelation[]` from parsed events |
| 3 | `db_lookup` | Deterministic | Queries PostgreSQL for existing entities by name, alias, or Wikidata ID |
| 4 | `resolve_wikidata` | Deterministic | Searches Wikidata via SPARQL and enriches candidates with QIDs, dates, coordinates |
| 5 | `resolve_ohm` | Deterministic | Searches the OHM SQLite index by QID or name; resolves best-point geometry |
| 6 | `generate_content` | LLM (via `create_llm()`) | Writes 1–2 sentence summaries and directional relation descriptions from `style_guide.md` |
| 7 | `validate` | Deterministic | Checks entity/relation types against allow-lists, applies confidence penalties for missing geometry or Wikidata |
| 8 | `build_diff` | Deterministic | Sorts validated candidates into `create_entities`, `create_relations`, `review_items`, `blocked_items` |
| 9 | `approval_gate` | Deterministic | Auto-commits items above risk-level-specific thresholds; flags everything else for review |
| 10 | `commit_writer` | I/O | Writes `entities_to_create.jsonl` and `relations_to_create.jsonl`; invokes `pipeline:import` and `pipeline:import-borders` |
| 11 | `audit_logger` | I/O | Writes `manifest.json` with run metadata, counts, audit log, and error list |

---

## Risk Policies

Each entity and relation type has a risk level and auto-commit threshold:

| Risk Level | Types (examples) | Threshold | Auto-commit? |
|------------|------------------|-----------|--------------|
| High | `person`, `political_entity`, `dynasty` | 0.97 | Only if confidence ≥ 0.97 |
| Medium | `city`, `archaeological_culture` | 0.94 | Only if confidence ≥ 0.94 |
| Low | `event_battle`, `event_war`, `trade_route` | 0.90 | Only if confidence ≥ 0.90 |

Configured in `pipeline/agent/config.py`.

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
{"name": "David IV of Georgia", "entity_type": "person", "summary": "Ruled the Kingdom of Georgia from 1089 to 1125...", "wikidata_id": "Q405", "start_date": null, "end_date": null, "alternative_names": ["David IV"], "geometry": null, "source_citations": {"created_by": "historical-agent-pipeline", "confidence": 0.98}}
```

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
│       ├── audit_logger.py
│       └── messy_research.py    # Stub for post-MVP DeepAgent
├── tools/
│   ├── db.py                # PostgreSQL search wrapper
│   ├── wikidata.py          # SPARQL search/enrich
│   ├── wikipedia.py         # Wikipedia API summary
│   ├── ohm.py               # OHM SQLite + geometry
│   └── app_api.py           # Laravel artisan shell-out
├── schemas/
│   ├── entities.py          # ParsedEvent, CandidateEntity, EnrichedCandidate
│   ├── relations.py         # CandidateRelation, CommittedChange
│   ├── proposals.py         # ProposedDiff, ApprovalDecision
│   └── validation.py        # ValidationResult, PipelineError, AuditEvent
├── deepagents/
│   ├── __init__.py
│   ├── entity_disambiguation_agent.py    # Stub
│   └── relation_research_agent.py        # Stub
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

- **Design spec:** [`docs/superpowers/specs/2026-06-09-historical-entity-agentic-pipeline-design.md`](../../superpowers/specs/2026-06-09-historical-entity-agentic-pipeline-design.md)
- **Implementation plan:** [`docs/superpowers/plans/2026-06-09-historical-entity-agentic-pipeline.md`](../../superpowers/plans/2026-06-09-historical-entity-agentic-pipeline.md)
