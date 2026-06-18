# Agentic Pipeline Commands

All commands run from the repository root.

## Quick Start

```powershell
# Run the agent on a transcript or historical text
py -m pipeline agent --input output/transctipts/History of Alexander the Great Conquering the World .txt --run-id alexander-great-run

# With a custom title
py -m pipeline agent --input transcript.txt --run-id my-run --title "Alexander's Conquests"

# Skip chronicle generation (entities/relations only)
py -m pipeline agent --input transcript.txt --run-id my-run --no-create-chronicle
```

## Command Reference

### `pipeline agent`

Run the historical entity agentic pipeline on raw text input.

```powershell
py -m pipeline agent --input <PATH> --run-id <ID> [OPTIONS]
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--input PATH` | Yes | — | Path to raw historical text file (transcript, article, book excerpt) |
| `--run-id TEXT` | No | `agent_<filename>` | Deterministic ID for the artifact directory |
| `--title TEXT` | No | Derived from input | Optional chronicle title |
| `--create-chronicle/--no-create-chronicle` | No | True | Whether to build a chronicle from extracted events |

**Output:** `output/agent_runs/<run_id>/`

```text
├── manifest.json              # Full audit trail with counts and errors
├── entities_to_create.jsonl   # Importer-ready entity records
├── relations_to_create.jsonl  # Importer-ready relation records
├── chronicle.json             # Chronological event sequence (if created)
└── style_validation.json      # Style check results (if generated)
```

---

## LLM Provider Configuration

The agent supports any OpenAI-compatible API endpoint.

### Environment Variables

Add to `pipeline/.env`:

```dotenv
# OpenAI (default)
OPENAI_API_KEY=sk-...

# Or OpenRouter
LLM_BASE_URL=https://openrouter.ai/api/v1
OPENAI_API_KEY=sk-or-v1-...

# Or Ollama (local)
LLM_BASE_URL=http://localhost:11434/v1
OPENAI_API_KEY=ollama
```

### Model Selection

Edit `pipeline/agent/config.py` to change model names:

```python
@dataclass
class AgentConfig:
    parse_model: str = "gpt-4o-mini"           # Event parsing
    extract_model: str = "gpt-4o-mini"           # Entity/relation extraction
    generate_model: str = "gpt-4o"               # Content generation
```

**OpenRouter examples:**
```python
parse_model: str = "anthropic/claude-3.5-sonnet"
extract_model: str = "anthropic/claude-3.5-sonnet"
generate_model: str = "anthropic/claude-3-opus"
```

**Ollama examples:**
```python
parse_model: str = "llama3.1"
extract_model: str = "llama3.1"
generate_model: str = "llama3.1"
```

---

## Testing

```powershell
# All agent tests
py -m pytest pipeline/agent/tests/ -v

# Style validator tests
py -m pytest pipeline/agent/tests/test_style_validator.py -v

# Graph compilation and end-to-end
py -m pytest pipeline/agent/tests/test_graph.py -v

# LLM node tests (mocked)
py -m pytest pipeline/agent/tests/test_nodes_llm.py -v
```

---

## LangGraph Development UI

For local development with visual debugging and hot reloading, use the LangGraph CLI.

### Installation

```powershell
# Install langgraph-cli with in-memory server support
py -m pip install "langgraph-cli[inmem]"

# Or with uv (recommended for faster installs)
uv pip install "langgraph-cli[inmem]"
```

> **Note:** The in-mem server requires Python 3.11 or higher. If you're on Python 3.10, either upgrade Python or use Docker mode below.

### Running the Development Server

```powershell
# Start the local LangGraph server (hot reloading enabled)
langgraph dev
```

The server runs on `http://localhost:2024` with no Docker required.

### Docker Mode (Python 3.10 Compatible)

If you're on Python 3.10, use Docker mode instead:

```powershell
# Requires Docker Desktop
langgraph dev --wait
```

This runs the server in a container with Python 3.11+.

### Opening Studio

Navigate to LangSmith Studio with your local server as the backend:

```
https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
```

**Features:**
- Visual workflow graph with node execution tracing
- Real-time state inspection during runs
- Hot reloading when code changes
- Local state storage (no external dependencies)

---

## Workflow Overview

```text
Raw historical text
        ↓
┌─────────────────────────────────────────────────────────────┐
│  LangGraph Orchestrator  (pipeline/agent/graph/)            │
│  ─────────────────────                                     │
│  preprocess_transcript → LLM: clean transcripts, fix OCR     │
│  parse_sequence      → LLM: raw text → structured events    │
│  extract_candidates  → LLM: events → entities/relations     │
│  db_lookup           → Check existing PostgreSQL entities   │
│  resolve_wikidata    → SPARQL: QIDs, metadata, dates        │
│  resolve_ohm         → SQLite index: geometry resolution    │
│  generate_content    → LLM: summaries + descriptions        │
│  validate            → Policy: type checks, confidence       │
│  build_diff          → Sort into create/review/blocked      │
│  approval_gate       → Risk-based auto-commit threshold      │
│  commit_writer       → JSONL + artisan pipeline:import      │
│  chronicle_builder   → Build chronological event sequence     │
│  chronicle_writer    → Write chronicle.json                 │
│  audit_logger        → manifest.json with full trace          │
└─────────────────────────────────────────────────────────────┘
        ↓
  output/agent_runs/<run_id>/
```

---

## Related Documentation

- [Agentic Pipeline Runbook](../../implementation-docs/agentic-pipeline-runbook.md) — Full architecture, node reference, risk policies
- [Data Contributor Guide](../../implementation-docs/data-contributor-guide.md) — Wikidata scraping, OHM borders, Laravel import
- [Style Guide](../../implementation-docs/agentic-pipeline-runbook.md#style-guide) — Content generation rules