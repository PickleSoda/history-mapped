# Historical Entity Agentic Pipeline — Implementation Plan

> **Status: ✅ Executed** — verified 2026-06-15 against the codebase. See [STATUS.md](../../plans/STATUS.md).
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a LangGraph-based agentic pipeline inside `pipeline/agent/` that accepts raw historical text, extracts entities and relations, resolves them via Wikidata/OHM, generates flowing descriptions, validates proposals, and produces importer-ready JSONL artifacts.

**Architecture:** LangGraph orchestrates 11 workflow nodes. Existing `pipeline/` modules (Wikidata scrapers, OHM lookup, dedup, relationship mapper) are wrapped as deterministic tool functions. The agent never writes directly to the DB — it writes JSONL files and invokes existing Laravel artisan batch commands. LLM-dependent nodes use OpenAI via LangChain.

**Tech Stack:** Python, LangGraph, LangChain, OpenAI, Pydantic, pytest. Existing Laravel/PHP import layer unchanged.

---

## File Structure

### New files (`pipeline/agent/`)

| File | Responsibility |
|------|---------------|
| `__init__.py` | Package init |
| `__main__.py` | CLI: `py -m pipeline agent --input transcript.txt` |
| `config.py` | Agent settings: model names, thresholds, risk policies |
| `style_guide.md` | Content generation style guide (prose rules) |
| `graph/state.py` | TypedDict state definitions (`AgentRunState`, etc.) |
| `graph/workflow.py` | LangGraph workflow builder and compile |
| `graph/nodes/parse_sequence.py` | LLM: raw text → `ParsedEvent[]` |
| `graph/nodes/extract_candidates.py` | LLM: events → `CandidateEntity[]` + `CandidateRelation[]` |
| `graph/nodes/db_lookup.py` | Check existing DB entities via `Deduplicator` |
| `graph/nodes/resolve_wikidata.py` | Resolve QIDs, metadata, Wikipedia sitelinks |
| `graph/nodes/resolve_ohm.py` | Resolve geometry via OHM SQLite index |
| `graph/nodes/generate_content.py` | LLM: write entity summaries + relation descriptions |
| `graph/nodes/validate.py` | Policy-based validation + confidence scoring |
| `graph/nodes/build_diff.py` | Build `ProposedDiff` with create/review/blocked buckets |
| `graph/nodes/approval_gate.py` | Auto-commit high-confidence, flag rest for review |
| `graph/nodes/commit_writer.py` | Write JSONL artifacts, invoke artisan commands |
| `graph/nodes/audit_logger.py` | Write `manifest.json` with full audit trail |
| `graph/nodes/messy_research.py` | Stub for post-MVP DeepAgent node |
| `tools/wikidata.py` | Wrap `scraper/wikidata.py` for agent consumption |
| `tools/wikipedia.py` | Wrap `scraper/wikipedia.py` for agent consumption |
| `tools/ohm.py` | Wrap `xml_lookup.py` + `point_resolver.py` |
| `tools/db.py` | Wrap `deduplicator.py` + direct DB search queries |
| `tools/app_api.py` | Shell out to Laravel artisan commands |
| `schemas/entities.py` | Pydantic: `ParsedEvent`, `CandidateEntity`, `EnrichedCandidate` |
| `schemas/relations.py` | Pydantic: `CandidateRelation`, `CommittedChange` |
| `schemas/proposals.py` | Pydantic: `ProposedDiff`, `ApprovalDecision` |
| `schemas/validation.py` | Pydantic: `ValidationResult`, `PipelineError`, `AuditEvent` |
| `deepagents/__init__.py` | Stub |
| `deepagents/entity_disambiguation_agent.py` | Stub |
| `deepagents/relation_research_agent.py` | Stub |
| `tests/test_graph.py` | End-to-end graph test with mocked LLM |
| `tests/test_nodes.py` | Unit tests for deterministic nodes |
| `tests/test_tools.py` | Unit tests for tool wrappers |
| `tests/fixtures/llm_responses/parse_sequence.json` | Mock LLM response for parse_sequence |
| `tests/fixtures/llm_responses/extract_candidates.json` | Mock LLM response for extract_candidates |
| `tests/fixtures/llm_responses/generate_content.json` | Mock LLM response for generate_content |

### Modified files

| File | Change |
|------|--------|
| `pipeline/requirements.txt` | Add `langgraph>=0.2.0`, `langchain>=0.2.0`, `langchain-openai>=0.1.0` |
| `pipeline/__main__.py` | Register `agent` subcommand |

---

## Phase 0: Audit Existing Codebase

### Task 0: Audit existing signatures and CLI structure

**Files:**
- Read: `pipeline/wikidata/scraper/wikidata.py`
- Read: `pipeline/wikidata/dedup/deduplicator.py`
- Read: `pipeline/__main__.py`
- Read: `pipeline/requirements.txt`
- Read: `api/app/Console/Commands/ImportEntitiesCommand.php`
- Read: `api/app/Console/Commands/ImportBordersCommand.php`

- [ ] **Step 1: Document actual scraper signatures**

Run: `grep -n "def " pipeline/wikidata/scraper/wikidata.py`
Document: available methods, their signatures, and what they return.

- [ ] **Step 2: Document deduplicator internals**

Run: `grep -n "def \|class " pipeline/wikidata/dedup/deduplicator.py`
Document: How `Deduplicator` connects to the DB, what methods exist.

- [ ] **Step 3: Document CLI structure**

Run: `cat pipeline/__main__.py`
Document: Is it `click`, `argparse`, or something else? How are subcommands registered?

- [ ] **Step 4: Document artisan command names**

Run: `grep -n "protected \$signature" api/app/Console/Commands/*.php`
Document: Exact command names (e.g., `pipeline:import`, `pipeline:import-borders`, etc.).

- [ ] **Step 5: Commit audit notes**

Write findings to `pipeline/agent/AUDIT_NOTES.md` (temporary, delete before merge).

```bash
git add pipeline/agent/AUDIT_NOTES.md
git commit -m "docs(agent): audit existing signatures for agent integration"
```

---

## Phase 1: Foundations

### Task 1: Add dependencies

**Files:**
- Modify: `pipeline/requirements.txt`

- [ ] **Step 1: Add langgraph dependencies**

Add these lines to the end of `pipeline/requirements.txt`:
```
langgraph>=0.2.0
langchain>=0.2.0
langchain-openai>=0.1.0
responses>=0.25.0
```

- [ ] **Step 2: Verify current deps**

Run: `cat pipeline/requirements.txt`
Expected: existing deps listed, new lines at bottom

- [ ] **Step 3: Commit**

```bash
git add pipeline/requirements.txt
git commit -m "deps: add langgraph, langchain, langchain-openai for agentic pipeline"
```

---

### Task 2: Create package scaffold

**Files:**
- Create: `pipeline/agent/__init__.py`
- Create: `pipeline/agent/graph/__init__.py`
- Create: `pipeline/agent/graph/nodes/__init__.py`
- Create: `pipeline/agent/tools/__init__.py`
- Create: `pipeline/agent/schemas/__init__.py`
- Create: `pipeline/agent/deepagents/__init__.py`
- Create: `pipeline/agent/tests/__init__.py`

- [ ] **Step 1: Create package inits**

All files empty (just package markers):
```python
"""Agentic pipeline for historical entity enrichment."""
```

- [ ] **Step 2: Commit**

```bash
git add pipeline/agent/
git commit -m "chore: create pipeline/agent package scaffold"
```

---

### Task 3: Create schemas

**Files:**
- Create: `pipeline/agent/schemas/entities.py`
- Create: `pipeline/agent/schemas/relations.py`
- Create: `pipeline/agent/schemas/proposals.py`
- Create: `pipeline/agent/schemas/validation.py`

- [ ] **Step 1: Write `entities.py` — failing test first**

Create `pipeline/agent/tests/test_schemas.py`:
```python
from pipeline.agent.schemas.entities import ParsedEvent, CandidateEntity

def test_parsed_event_schema():
    event = ParsedEvent(
        label="Battle of Didgori",
        description="David IV defeats Ilghazi.",
        start_date="1121-08-12",
        end_date="1121-08-12",
        mentioned_entities=["David IV", "Ilghazi"],
    )
    assert event.label == "Battle of Didgori"
    assert event.mentioned_entities == ["David IV", "Ilghazi"]
```

Run: `py -m pytest pipeline/agent/tests/test_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError: pipeline.agent.schemas.entities`

- [ ] **Step 2: Implement `entities.py`**

Create `pipeline/agent/schemas/entities.py`:
```python
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any


class ParsedEvent(BaseModel):
    label: str
    description: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    mentioned_entities: list[str] = Field(default_factory=list)
    date_uncertain: bool = False


class CandidateEntity(BaseModel):
    label: str
    entity_type: str
    start_date: str | None = None
    end_date: str | None = None
    source_event: str | None = None
    aliases: list[str] = Field(default_factory=list)
    wikidata_id: str | None = None
    confidence: float = 0.0


class EnrichedCandidate(BaseModel):
    candidate: CandidateEntity
    wikidata_match: dict[str, Any] | None = None
    wikipedia_url: str | None = None
    ohm_match: dict[str, Any] | None = None
    geometry: dict[str, Any] | None = None
    summary: str | None = None
    system_confidence: float = 0.0
    final_confidence: float = 0.0
    validation_errors: list[str] = Field(default_factory=list)
```

- [ ] **Step 3: Implement `relations.py`**

Create `pipeline/agent/schemas/relations.py`:
```python
from __future__ import annotations

from pydantic import BaseModel, Field


class CandidateRelation(BaseModel):
    source_label: str
    target_label: str
    relationship_type: str
    start_date: str | None = None
    end_date: str | None = None
    source_event: str | None = None
    description: str | None = None
    confidence: float = 0.0


class CommittedChange(BaseModel):
    change_type: str  # "entity" | "relation"
    record: dict
    committed_at: str
    batch_id: str
```

- [ ] **Step 4: Implement `proposals.py`**

Create `pipeline/agent/schemas/proposals.py`:
```python
from __future__ import annotations

from pydantic import BaseModel, Field

from pipeline.agent.schemas.entities import EnrichedCandidate
from pipeline.agent.schemas.relations import CandidateRelation


class ProposedDiff(BaseModel):
    run_id: str
    summary: dict[str, int] = Field(default_factory=dict)
    create_entities: list[EnrichedCandidate] = Field(default_factory=list)
    create_relations: list[CandidateRelation] = Field(default_factory=list)
    review_items: list[dict] = Field(default_factory=list)
    blocked_items: list[dict] = Field(default_factory=list)


class ApprovalDecision(BaseModel):
    auto_committed_entities: list[str] = Field(default_factory=list)
    auto_committed_relations: list[str] = Field(default_factory=list)
    flagged_for_review: list[dict] = Field(default_factory=list)
```

- [ ] **Step 5: Implement `validation.py`**

Create `pipeline/agent/schemas/validation.py`:
```python
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any


class ValidationResult(BaseModel):
    candidate_id: str
    passed: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence_override: float | None = None


class PipelineError(BaseModel):
    node: str
    error_type: str
    message: str
    context: dict[str, Any] | None = None


class AuditEvent(BaseModel):
    timestamp: str
    node: str
    action: str
    input_summary: str | None = None
    output_summary: str | None = None
    proposal_id: str | None = None
    validation_status: str | None = None
    approval_status: str | None = None
```

- [ ] **Step 6: Run schema tests**

Run: `py -m pytest pipeline/agent/tests/test_schemas.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add pipeline/agent/schemas/ pipeline/agent/tests/test_schemas.py
git commit -m "feat(agent): add pydantic schemas for events, relations, proposals, validation"
```

---

### Task 4: Create state definitions

**Files:**
- Create: `pipeline/agent/graph/state.py`
- Test: `pipeline/agent/tests/test_state.py`

- [ ] **Step 1: Write failing test**

Create `pipeline/agent/tests/test_state.py`:
```python
from pipeline.agent.graph.state import AgentRunState

def test_state_is_typed_dict():
    from typing import get_type_hints
    hints = get_type_hints(AgentRunState)
    assert "run_id" in hints
    assert "raw_input" in hints
```

Run: `py -m pytest pipeline/agent/tests/test_state.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 2: Implement `state.py`**

Create `pipeline/agent/graph/state.py`:
```python
from __future__ import annotations

from typing import TypedDict, Any

from pipeline.agent.schemas.entities import ParsedEvent, CandidateEntity, EnrichedCandidate
from pipeline.agent.schemas.relations import CandidateRelation, CommittedChange
from pipeline.agent.schemas.proposals import ProposedDiff
from pipeline.agent.schemas.validation import ValidationResult, PipelineError, AuditEvent


class AgentRunState(TypedDict):
    run_id: str
    raw_input: str
    parsed_events: list[ParsedEvent]
    candidate_entities: list[CandidateEntity]
    candidate_relations: list[CandidateRelation]
    enriched_entities: list[EnrichedCandidate]
    validation_results: list[ValidationResult]
    proposed_diff: ProposedDiff | None
    committed: list[CommittedChange]
    audit_log: list[AuditEvent]
    errors: list[PipelineError]
```

- [ ] **Step 3: Run tests**

Run: `py -m pytest pipeline/agent/tests/test_state.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add pipeline/agent/graph/state.py pipeline/agent/tests/test_state.py
git commit -m "feat(agent): add AgentRunState TypedDict"
```

---

### Task 5: Create agent config

**Files:**
- Create: `pipeline/agent/config.py`
- Test: `pipeline/agent/tests/test_config.py`

- [ ] **Step 1: Write failing test**

Create `pipeline/agent/tests/test_config.py`:
```python
from pipeline.agent.config import AgentConfig, ENTITY_RISK_POLICIES

def test_config_loads_defaults():
    cfg = AgentConfig()
    assert cfg.parse_model == "gpt-4o-mini"
    assert "political_entity" in ENTITY_RISK_POLICIES
```

Run: `py -m pytest pipeline/agent/tests/test_config.py -v`
Expected: FAIL

- [ ] **Step 2: Implement `config.py`**

Create `pipeline/agent/config.py`:
```python
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class AgentConfig:
    parse_model: str = "gpt-4o-mini"
    extract_model: str = "gpt-4o-mini"
    generate_model: str = "gpt-4o"
    openai_api_key: str | None = None
    auto_commit_threshold: float = 0.95
    output_dir: str = "output/agent_runs"
    ohm_index_path: str = "output/ohm_collections/global/index.db"

    def __post_init__(self):
        if self.openai_api_key is None:
            self.openai_api_key = os.getenv("OPENAI_API_KEY")


ENTITY_RISK_POLICIES: dict[str, dict] = {
    "person": {"risk_level": "high", "auto_commit_threshold": 0.97},
    "political_entity": {"risk_level": "high", "auto_commit_threshold": 0.97},
    "dynasty": {"risk_level": "high", "auto_commit_threshold": 0.97},
    "city": {"risk_level": "medium", "auto_commit_threshold": 0.94},
    "event_battle": {"risk_level": "low", "auto_commit_threshold": 0.90},
    "event_war": {"risk_level": "low", "auto_commit_threshold": 0.90},
    "event_treaty": {"risk_level": "low", "auto_commit_threshold": 0.90},
    "trade_route": {"risk_level": "low", "auto_commit_threshold": 0.90},
    "cultural_work": {"risk_level": "low", "auto_commit_threshold": 0.90},
    "archaeological_culture": {"risk_level": "medium", "auto_commit_threshold": 0.92},
}

RELATION_RISK_POLICIES: dict[str, dict] = {
    "participated_in": {"risk_level": "low", "auto_commit_threshold": 0.90},
    "fought_at": {"risk_level": "low", "auto_commit_threshold": 0.90},
    "born_in": {"risk_level": "low", "auto_commit_threshold": 0.90},
    "died_in": {"risk_level": "low", "auto_commit_threshold": 0.90},
    "rules": {"risk_level": "high", "auto_commit_threshold": 0.97},
    "governed_by": {"risk_level": "high", "auto_commit_threshold": 0.97},
    "at_war_with": {"risk_level": "high", "auto_commit_threshold": 0.95},
    "part_of": {"risk_level": "medium", "auto_commit_threshold": 0.93},
    "succeeded_by": {"risk_level": "medium", "auto_commit_threshold": 0.93},
    "preceded_by": {"risk_level": "medium", "auto_commit_threshold": 0.93},
}
```

- [ ] **Step 3: Run tests**

Run: `py -m pytest pipeline/agent/tests/test_config.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add pipeline/agent/config.py pipeline/agent/tests/test_config.py
git commit -m "feat(agent): add AgentConfig and risk policies"
```

---

### Task 6: Create style guide

**Files:**
- Create: `pipeline/agent/style_guide.md`

- [ ] **Step 1: Write style guide**

Create `pipeline/agent/style_guide.md`:
```markdown
# Historical Entity Content Style Guide

## Entity Summaries
- 1–2 sentences maximum.
- Include temporal scope (start–end dates or era).
- Include significance or key achievement.
- Do not repeat the entity's own name.
- Mention connected entities naturally, not as dry links.
- Tone: encyclopedic but narrative.

## Relation Descriptions
- Directional and specific.
- Include temporal qualifier (date, year, or era).
- Avoid passive voice.
- Always mention the event or period.

## Examples

Entity summary (good):
> "Ruled the Kingdom of Georgia from 1089 to 1125 and led the decisive victory at the Battle of Didgori in 1121."

Entity summary (bad):
> "David IV was a king of Georgia."

Relation description (good):
> "Commanded the Georgian forces at the Battle of Didgori on August 12, 1121."

Relation description (bad):
> "Was involved in the battle."
```

- [ ] **Step 2: Commit**

```bash
git add pipeline/agent/style_guide.md
git commit -m "docs(agent): add content generation style guide"
```

---

## Phase 2: Tool Layer

### Task 7: Create DB tool wrapper

**Files:**
- Create: `pipeline/agent/tools/db.py`
- Test: `pipeline/agent/tests/test_tools.py` (add `test_db_search`)

- [ ] **Step 1: Write failing test**

Add to `pipeline/agent/tests/test_tools.py`:
```python
import pytest
from unittest.mock import patch, MagicMock

from pipeline.agent.tools.db import search_entity_by_name

@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")
def test_db_search_returns_list():
    results = search_entity_by_name("David IV", entity_type="person")
    assert isinstance(results, list)
```

Run: `py -m pytest pipeline/agent/tests/test_tools.py::test_db_search -v`
Expected: FAIL

- [ ] **Step 2: Implement `db.py`**

Create `pipeline/agent/tools/db.py`:
```python
from __future__ import annotations

import os
from typing import Any

try:
    import psycopg
    HAS_PSYCOPG = True
except ImportError:
    HAS_PSYCOPG = False


def _get_db_connection():
    """Get a direct DB connection using DATABASE_URL from env."""
    if not HAS_PSYCOPG:
        return None
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        return None
    try:
        return psycopg.connect(db_url)
    except Exception:
        return None


def search_entity_by_name(
    name: str,
    entity_type: str | None = None,
) -> list[dict[str, Any]]:
    """Search for existing entities by name, optionally filtering by type."""
    conn = _get_db_connection()
    if conn is None:
        return []

    try:
        with conn.cursor() as cursor:
            if entity_type:
                cursor.execute(
                    """
                    SELECT entity_id, name, entity_type, wikidata_id
                    FROM entities
                    WHERE name ILIKE %s AND entity_type = %s
                    LIMIT 10
                    """,
                    (f"%{name}%", entity_type),
                )
            else:
                cursor.execute(
                    """
                    SELECT entity_id, name, entity_type, wikidata_id
                    FROM entities
                    WHERE name ILIKE %s
                    LIMIT 10
                    """,
                    (f"%{name}%",),
                )
            rows = cursor.fetchall()
            return [
                {
                    "entity_id": row[0],
                    "name": row[1],
                    "entity_type": row[2],
                    "wikidata_id": row[3],
                }
                for row in rows
            ]
    except Exception:
        return []
    finally:
        conn.close()


def search_entity_by_wikidata_id(wikidata_id: str) -> list[dict[str, Any]]:
    """Search for existing entity by Wikidata QID."""
    conn = _get_db_connection()
    if conn is None:
        return []

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT entity_id, name, entity_type, wikidata_id
                FROM entities
                WHERE wikidata_id = %s
                LIMIT 1
                """,
                (wikidata_id,),
            )
            row = cursor.fetchone()
            if row:
                return [{"entity_id": row[0], "name": row[1], "entity_type": row[2], "wikidata_id": row[3]}]
            return []
    except Exception:
        return []
    finally:
        conn.close()
```

> **Note:** Uses `psycopg` directly rather than relying on `Deduplicator` internals. The `Deduplicator` is still used for batch dedup in `pipeline/wikidata/dedup/`, but agent DB queries use a clean connection wrapper.

- [ ] **Step 3: Run tests**

Run: `py -m pytest pipeline/agent/tests/test_tools.py::test_db_search -v`
Expected: PASS (skipped if no DB)

- [ ] **Step 4: Commit**

```bash
git add pipeline/agent/tools/db.py pipeline/agent/tests/test_tools.py
git commit -m "feat(agent): add DB search tool wrapper with psycopg"
```

---

### Task 8: Create Wikidata tool wrapper

**Files:**
- Create: `pipeline/agent/tools/wikidata.py`
- Test: `pipeline/agent/tests/test_tools.py` (add `test_wikidata_search`)

> **Prerequisite:** Task 0 audit must confirm actual scraper signatures. If `search_by_label` doesn't exist, implement it as a SPARQL wrapper in this task.

- [ ] **Step 1: Write failing test**

Add to `pipeline/agent/tests/test_tools.py`:
```python
from unittest.mock import patch, MagicMock
from pipeline.agent.tools.wikidata import search_wikidata_by_name

@patch("pipeline.agent.tools.wikidata._query_sparql")
def test_wikidata_search_returns_list(mock_query):
    mock_query.return_value = {
        "results": {
            "bindings": [
                {"item": {"value": "http://www.wikidata.org/entity/Q405"}, "itemLabel": {"value": "David IV of Georgia"}}
            ]
        }
    }
    results = search_wikidata_by_name("David IV of Georgia")
    assert isinstance(results, list)
    assert results[0]["qid"] == "Q405"
```

Run: `py -m pytest pipeline/agent/tests/test_tools.py::test_wikidata_search -v`
Expected: FAIL

- [ ] **Step 2: Implement `wikidata.py`**

Create `pipeline/agent/tools/wikidata.py`:
```python
from __future__ import annotations

from typing import Any

import requests

from pipeline.config import settings


def _query_sparql(query: str) -> dict[str, Any]:
    """Run a SPARQL query against Wikidata."""
    response = requests.get(
        settings.wikidata_endpoint,
        params={"query": query, "format": "json"},
        headers={"User-Agent": settings.wikidata_user_agent},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def search_wikidata_by_name(name: str, limit: int = 5) -> list[dict[str, Any]]:
    """Search Wikidata by label, return candidate matches.

    Each match contains: qid, label, description.
    """
    query = f"""
    SELECT ?item ?itemLabel ?itemDescription WHERE {{
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
      ?item rdfs:label ?itemLabel.
      FILTER(CONTAINS(LCASE(?itemLabel), LCASE("{name}")))
    }}
    LIMIT {limit}
    """
    data = _query_sparql(query)
    results = []
    for binding in data.get("results", {}).get("bindings", []):
        item_url = binding.get("item", {}).get("value", "")
        qid = item_url.split("/")[-1] if "/entity/" in item_url else ""
        results.append({
            "qid": qid,
            "label": binding.get("itemLabel", {}).get("value", ""),
            "description": binding.get("itemDescription", {}).get("value", ""),
        })
    return results


def enrich_wikidata_entities(qids: list[str]) -> dict[str, dict[str, Any]]:
    """Fetch basic Wikidata records for a list of QIDs.

    Returns a dict mapping qid → {label, description, aliases, coordinates, start_date, end_date}.
    """
    if not qids:
        return {}

    qid_values = " ".join(f"wd:{q}" for q in qids)
    query = f"""
    SELECT ?item ?itemLabel ?itemDescription ?coord ?inception ?dissolved WHERE {{
      VALUES ?item {{ {qid_values} }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
      OPTIONAL {{ ?item wdt:P625 ?coord. }}
      OPTIONAL {{ ?item wdt:P571 ?inception. }}
      OPTIONAL {{ ?item wdt:P576 ?dissolved. }}
    }}
    """
    data = _query_sparql(query)
    results = {}
    for binding in data.get("results", {}).get("bindings", []):
        item_url = binding.get("item", {}).get("value", "")
        qid = item_url.split("/")[-1] if "/entity/" in item_url else ""
        if qid:
            results[qid] = {
                "label": binding.get("itemLabel", {}).get("value", ""),
                "description": binding.get("itemDescription", {}).get("value", ""),
                "coordinates": binding.get("coord", {}).get("value"),
                "start_date": binding.get("inception", {}).get("value"),
                "end_date": binding.get("dissolved", {}).get("value"),
            }
    return results
```

> **Note:** Uses direct SPARQL queries rather than assuming non-existent `WikidataScraper.search_entities`/`fetch_entities` methods. The `pipeline/wikidata/scraper/wikidata.py` is still used for batch scraping workflows; the agent uses lightweight SPARQL for single-entity lookups.

- [ ] **Step 3: Run tests**

Run: `py -m pytest pipeline/agent/tests/test_tools.py::test_wikidata_search -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add pipeline/agent/tools/wikidata.py
git commit -m "feat(agent): add Wikidata SPARQL search/enrich tool wrapper"
```

---

### Task 8.5: Create Wikipedia tool wrapper

**Files:**
- Create: `pipeline/agent/tools/wikipedia.py`
- Test: `pipeline/agent/tests/test_tools.py` (add `test_wikipedia_search`)

- [ ] **Step 1: Write failing test**

Add to `pipeline/agent/tests/test_tools.py`:
```python
from unittest.mock import patch, MagicMock
from pipeline.agent.tools.wikipedia import fetch_wikipedia_summary

@patch("pipeline.agent.tools.wikipedia.requests.get")
def test_wikipedia_fetch(mock_get):
    mock_get.return_value = MagicMock(json=lambda: {
        "query": {"pages": {"1": {"extract": "David IV was a king.", "title": "David IV of Georgia"}}}
    })
    result = fetch_wikipedia_summary("David IV of Georgia")
    assert result is not None
    assert "king" in result.get("extract", "").lower()
```

Run: `py -m pytest pipeline/agent/tests/test_tools.py::test_wikipedia_fetch -v`
Expected: FAIL

- [ ] **Step 2: Implement `wikipedia.py`**

Create `pipeline/agent/tools/wikipedia.py`:
```python
from __future__ import annotations

from typing import Any

import requests

from pipeline.config import settings


def fetch_wikipedia_summary(title: str, language: str | None = None) -> dict[str, Any] | None:
    """Fetch Wikipedia article summary for a given title.

    Returns dict with: title, extract, url, or None if not found.
    """
    lang = language or settings.wikipedia_language
    url = f"https://{lang}.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "titles": title,
        "prop": "extracts",
        "explaintext": True,
        "exintro": True,
        "exlimit": 1,
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        pages = data.get("query", {}).get("pages", {})
        for page_id, page_data in pages.items():
            if page_id == "-1":
                return None
            return {
                "title": page_data.get("title"),
                "extract": page_data.get("extract"),
                "url": f"https://{lang}.wikipedia.org/wiki/{page_data.get('title', '').replace(' ', '_')}",
            }
    except Exception:
        return None
    return None
```

- [ ] **Step 3: Run tests**

Run: `py -m pytest pipeline/agent/tests/test_tools.py::test_wikipedia_fetch -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add pipeline/agent/tools/wikipedia.py
git commit -m "feat(agent): add Wikipedia summary fetch tool wrapper"
```

---

### Task 9: Create OHM tool wrapper

**Files:**
- Create: `pipeline/agent/tools/ohm.py`
- Test: `pipeline/agent/tests/test_tools.py` (add `test_ohm_search`)

- [ ] **Step 1: Write failing test**

Add to `pipeline/agent/tests/test_tools.py`:
```python
from pipeline.agent.tools.ohm import search_ohm_by_name

def test_ohm_search_returns_list():
    results = search_ohm_by_name("Didgori", index_path="nonexistent.db")
    assert isinstance(results, list)
```

Run: `py -m pytest pipeline/agent/tests/test_tools.py::test_ohm_search -v`
Expected: FAIL

- [ ] **Step 2: Implement `ohm.py`**

Create `pipeline/agent/tools/ohm.py`:
```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.ohm_collections.xml_lookup import find_objects_by_name, find_objects_by_wikidata_id
from pipeline.ohm_collections.point_resolver import resolve_best_point


def search_ohm_by_name(name: str, index_path: str | Path) -> list[dict[str, Any]]:
    """Search OHM SQLite index by name."""
    return find_objects_by_name(index_path, name)


def search_ohm_by_wikidata_id(wikidata_id: str, index_path: str | Path) -> list[dict[str, Any]]:
    """Search OHM SQLite index by Wikidata QID."""
    return find_objects_by_wikidata_id(index_path, wikidata_id)


def resolve_ohm_geometry(index_path: str | Path, object_type: str, object_id: int) -> dict[str, Any] | None:
    """Resolve the best point geometry for an OHM object."""
    return resolve_best_point(index_path, object_type=object_type, object_id=object_id)
```

- [ ] **Step 3: Run tests**

Run: `py -m pytest pipeline/agent/tests/test_tools.py::test_ohm_search -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add pipeline/agent/tools/ohm.py
git commit -m "feat(agent): add OHM search/geometry tool wrapper"
```

---

### Task 10: Create app API tool wrapper

**Files:**
- Create: `pipeline/agent/tools/app_api.py`
- Test: `pipeline/agent/tests/test_tools.py` (add `test_app_api_command`)

- [ ] **Step 1: Write failing test**

Add to `pipeline/agent/tests/test_tools.py`:
```python
from pipeline.agent.tools.app_api import build_artisan_command

def test_build_import_command():
    cmd = build_artisan_command("pipeline:import", "/tmp/test.jsonl", sync=True)
    assert "pipeline:import" in cmd
    assert "--sync" in cmd
```

Run: `py -m pytest pipeline/agent/tests/test_tools.py::test_app_api_command -v`
Expected: FAIL

- [ ] **Step 2: Implement `app_api.py`**

Create `pipeline/agent/tools/app_api.py`:
```python
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def build_artisan_command(
    command: str,
    *args: str,
    sync: bool = False,
    batch_id: str | None = None,
) -> list[str]:
    """Build a Laravel artisan command as a list of strings for subprocess.

    Example:
        build_artisan_command("pipeline:import", "/tmp/ents.jsonl", sync=True, batch_id="run_123")
        → ["docker", "compose", "-f", "docker/docker-compose.yml", "exec", "app", "php", "artisan", "pipeline:import", "/tmp/ents.jsonl", "--sync", "--batch-id=run_123"]
    """
    cmd = [
        "docker", "compose", "-f", "docker/docker-compose.yml",
        "exec", "app", "php", "artisan",
        command,
    ]
    cmd.extend(args)
    if sync:
        cmd.append("--sync")
    if batch_id:
        cmd.append(f"--batch-id={batch_id}")
    return cmd


def run_artisan_command(cmd: list[str]) -> dict[str, Any]:
    """Run an artisan command and capture output."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
```

- [ ] **Step 3: Run tests**

Run: `py -m pytest pipeline/agent/tests/test_tools.py::test_app_api_command -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add pipeline/agent/tools/app_api.py
git commit -m "feat(agent): add Laravel artisan command wrapper"
```

---

## Phase 3: Graph Nodes

### Task 11: Implement `parse_sequence` node

**Files:**
- Create: `pipeline/agent/graph/nodes/parse_sequence.py`
- Test: `pipeline/agent/tests/test_nodes.py` (add `test_parse_sequence`)
- Create: `pipeline/agent/tests/fixtures/llm_responses/parse_sequence.json`

- [ ] **Step 1: Create mock fixture**

Create `pipeline/agent/tests/fixtures/llm_responses/parse_sequence.json`:
```json
{
  "events": [
    {
      "label": "Battle of Didgori",
      "description": "David IV defeats Ilghazi near Didgori.",
      "start_date": "1121-08-12",
      "end_date": "1121-08-12",
      "mentioned_entities": ["David IV", "Ilghazi", "Kingdom of Georgia", "Didgori"],
      "date_uncertain": false
    }
  ]
}
```

- [ ] **Step 2: Write failing test**

Add to `pipeline/agent/tests/test_nodes.py`:
```python
from pipeline.agent.graph.nodes.parse_sequence import parse_sequence
from pipeline.agent.graph.state import AgentRunState

def test_parse_sequence_returns_events():
    state: AgentRunState = {
        "run_id": "test_1",
        "raw_input": "In 1121, David IV defeated Ilghazi at Didgori.",
        "parsed_events": [],
        "candidate_entities": [],
        "candidate_relations": [],
        "enriched_entities": [],
        "validation_results": [],
        "proposed_diff": None,
        "committed": [],
        "audit_log": [],
        "errors": [],
    }
    # We'll mock the LLM in the actual test
    new_state = parse_sequence(state)
    assert len(new_state["parsed_events"]) > 0
    assert new_state["parsed_events"][0].label == "Battle of Didgori"
```

Run: `py -m pytest pipeline/agent/tests/test_nodes.py::test_parse_sequence -v`
Expected: FAIL

- [ ] **Step 3: Implement `parse_sequence.py`**

Create `pipeline/agent/graph/nodes/parse_sequence.py`:
```python
from __future__ import annotations

import json
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from pipeline.agent.config import AgentConfig
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.entities import ParsedEvent
from pipeline.agent.schemas.validation import AuditEvent

_PROMPT = """You are a historical event parser. Convert the provided historical text into a structured list of events.

For each event, extract:
- label: a concise title
- description: a 1-sentence summary
- start_date: ISO date if known, else null
- end_date: ISO date if known, else null
- mentioned_entities: list of named entities mentioned
- date_uncertain: true if the date is vague or estimated

Output strictly as JSON matching this schema:
{"events": [{"label": "...", "description": "...", "start_date": "...", "end_date": "...", "mentioned_entities": [...], "date_uncertain": false}]}
"""


def parse_sequence(state: AgentRunState) -> AgentRunState:
    cfg = AgentConfig()
    llm = ChatOpenAI(model=cfg.parse_model, api_key=cfg.openai_api_key)

    messages = [
        SystemMessage(content=_PROMPT),
        HumanMessage(content=state["raw_input"]),
    ]

    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)

    # Parse JSON from LLM response
    try:
        data = json.loads(content)
        events = [ParsedEvent(**e) for e in data.get("events", [])]
    except (json.JSONDecodeError, TypeError) as exc:
        state["errors"].append({
            "node": "parse_sequence",
            "error_type": "json_parse",
            "message": str(exc),
            "context": {"raw_response": content},
        })
        events = []

    state["parsed_events"] = events
    state["audit_log"].append(AuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        node="parse_sequence",
        action="parsed_events",
        input_summary=state["raw_input"][:100],
        output_summary=f"{len(events)} events extracted",
    ))
    return state
```

- [ ] **Step 4: Run tests with mock**

Update the test to patch the LLM:
```python
from unittest.mock import patch, MagicMock
import json

@patch("pipeline.agent.graph.nodes.parse_sequence.ChatOpenAI")
def test_parse_sequence_returns_events(mock_chat):
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content=json.dumps({
        "events": [{
            "label": "Battle of Didgori",
            "description": "David IV defeats Ilghazi.",
            "start_date": "1121-08-12",
            "end_date": "1121-08-12",
            "mentioned_entities": ["David IV", "Ilghazi"],
            "date_uncertain": False,
        }]
    }))
    mock_chat.return_value = mock_llm

    state: AgentRunState = {
        "run_id": "test_1",
        "raw_input": "In 1121, David IV defeated Ilghazi at Didgori.",
        "parsed_events": [],
        "candidate_entities": [],
        "candidate_relations": [],
        "enriched_entities": [],
        "validation_results": [],
        "proposed_diff": None,
        "committed": [],
        "audit_log": [],
        "errors": [],
    }
    new_state = parse_sequence(state)
    assert len(new_state["parsed_events"]) == 1
    assert new_state["parsed_events"][0].label == "Battle of Didgori"
```

Run: `py -m pytest pipeline/agent/tests/test_nodes.py::test_parse_sequence -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/agent/graph/nodes/parse_sequence.py pipeline/agent/tests/test_nodes.py pipeline/agent/tests/fixtures/
git commit -m "feat(agent): add parse_sequence node with mocked LLM test"
```

---

### Task 12: Implement `extract_candidates` node

**Files:**
- Create: `pipeline/agent/graph/nodes/extract_candidates.py`
- Test: `pipeline/agent/tests/test_nodes.py` (add `test_extract_candidates`)
- Create: `pipeline/agent/tests/fixtures/llm_responses/extract_candidates.json`

- [ ] **Step 1: Create mock fixture**

Create `pipeline/agent/tests/fixtures/llm_responses/extract_candidates.json`:
```json
{
  "candidate_entities": [
    {"label": "David IV of Georgia", "entity_type": "person", "start_date": null, "end_date": null, "aliases": ["David IV"]},
    {"label": "Ilghazi", "entity_type": "person", "start_date": null, "end_date": null, "aliases": []},
    {"label": "Battle of Didgori", "entity_type": "event_battle", "start_date": "1121-08-12", "end_date": "1121-08-12", "aliases": []},
    {"label": "Kingdom of Georgia", "entity_type": "political_entity", "start_date": null, "end_date": null, "aliases": []}
  ],
  "candidate_relations": [
    {"source_label": "David IV of Georgia", "target_label": "Battle of Didgori", "relationship_type": "participated_in", "start_date": "1121-08-12", "end_date": "1121-08-12"},
    {"source_label": "Ilghazi", "target_label": "Battle of Didgori", "relationship_type": "participated_in", "start_date": "1121-08-12", "end_date": "1121-08-12"}
  ]
}
```

- [ ] **Step 2: Write failing test**

Add to `pipeline/agent/tests/test_nodes.py`:
```python
from pipeline.agent.graph.nodes.extract_candidates import extract_candidates

@patch("pipeline.agent.graph.nodes.extract_candidates.ChatOpenAI")
def test_extract_candidates(mock_chat):
    mock_llm = MagicMock()
    with open("pipeline/agent/tests/fixtures/llm_responses/extract_candidates.json") as f:
        mock_llm.invoke.return_value = MagicMock(content=f.read())
    mock_chat.return_value = mock_llm

    state: AgentRunState = {
        "run_id": "test_1",
        "raw_input": "...",
        "parsed_events": [ParsedEvent(label="Battle of Didgori", description="...", start_date="1121-08-12", mentioned_entities=["David IV", "Ilghazi"])],
        "candidate_entities": [],
        "candidate_relations": [],
        "enriched_entities": [],
        "validation_results": [],
        "proposed_diff": None,
        "committed": [],
        "audit_log": [],
        "errors": [],
    }
    new_state = extract_candidates(state)
    assert len(new_state["candidate_entities"]) == 4
    assert len(new_state["candidate_relations"]) == 2
```

Run: `py -m pytest pipeline/agent/tests/test_nodes.py::test_extract_candidates -v`
Expected: FAIL

- [ ] **Step 3: Implement `extract_candidates.py`**

Create `pipeline/agent/graph/nodes/extract_candidates.py`:
```python
from __future__ import annotations

import json
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from pipeline.agent.config import AgentConfig
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.entities import CandidateEntity
from pipeline.agent.schemas.relations import CandidateRelation
from pipeline.agent.schemas.validation import AuditEvent

_PROMPT = """You are a historical entity extractor. Given a list of events, extract all candidate entities and relations.

Allowed entity types: person, political_entity, dynasty, city, event_battle, event_war, event_treaty, trade_route, cultural_work, archaeological_culture, language, religious_movement, infrastructure_monument, currency_monetary_system, natural_resource.

Allowed relation types: participated_in, fought_at, rules, governed_by, part_of, contains, capital_of, born_in, died_in, preceded_by, succeeded_by, caused, resulted_from, at_war_with, allied_with, trades_with.

Output strictly as JSON:
{"candidate_entities": [{"label": "...", "entity_type": "...", "start_date": "...", "end_date": "...", "source_event": "...", "aliases": []}], "candidate_relations": [{"source_label": "...", "target_label": "...", "relationship_type": "...", "start_date": "...", "end_date": "...", "source_event": "..."}]}
"""


def extract_candidates(state: AgentRunState) -> AgentRunState:
    cfg = AgentConfig()
    llm = ChatOpenAI(model=cfg.extract_model, api_key=cfg.openai_api_key)

    events_json = json.dumps([e.model_dump() for e in state["parsed_events"]], default=str)
    messages = [
        SystemMessage(content=_PROMPT),
        HumanMessage(content=events_json),
    ]

    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)

    try:
        data = json.loads(content)
        entities = [CandidateEntity(**e) for e in data.get("candidate_entities", [])]
        relations = [CandidateRelation(**r) for r in data.get("candidate_relations", [])]
    except (json.JSONDecodeError, TypeError) as exc:
        state["errors"].append({
            "node": "extract_candidates",
            "error_type": "json_parse",
            "message": str(exc),
            "context": {"raw_response": content},
        })
        entities = []
        relations = []

    state["candidate_entities"] = entities
    state["candidate_relations"] = relations
    state["audit_log"].append(AuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        node="extract_candidates",
        action="extracted_candidates",
        output_summary=f"{len(entities)} entities, {len(relations)} relations",
    ))
    return state
```

- [ ] **Step 4: Run tests**

Run: `py -m pytest pipeline/agent/tests/test_nodes.py::test_extract_candidates -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/agent/graph/nodes/extract_candidates.py pipeline/agent/tests/test_nodes.py pipeline/agent/tests/fixtures/llm_responses/extract_candidates.json
git commit -m "feat(agent): add extract_candidates node with mocked LLM test"
```

---

### Task 13: Implement `db_lookup` node

**Files:**
- Create: `pipeline/agent/graph/nodes/db_lookup.py`
- Test: `pipeline/agent/tests/test_nodes.py` (add `test_db_lookup`)

- [ ] **Step 1: Write failing test**

Add to `pipeline/agent/tests/test_nodes.py`:
```python
from pipeline.agent.graph.nodes.db_lookup import db_lookup
from unittest.mock import patch

@patch("pipeline.agent.graph.nodes.db_lookup.search_entity_by_name")
def test_db_lookup_flags_existing(mock_search):
    mock_search.return_value = [{"entity_id": "E123", "name": "David IV of Georgia", "entity_type": "person", "wikidata_id": "Q405"}]

    state: AgentRunState = {
        "run_id": "test_1",
        "raw_input": "...",
        "parsed_events": [],
        "candidate_entities": [CandidateEntity(label="David IV of Georgia", entity_type="person")],
        "candidate_relations": [],
        "enriched_entities": [],
        "validation_results": [],
        "proposed_diff": None,
        "committed": [],
        "audit_log": [],
        "errors": [],
    }
    new_state = db_lookup(state)
    assert len(new_state["enriched_entities"]) == 1
    assert new_state["enriched_entities"][0].wikidata_match is not None
```

Run: `py -m pytest pipeline/agent/tests/test_nodes.py::test_db_lookup -v`
Expected: FAIL

- [ ] **Step 2: Implement `db_lookup.py`**

Create `pipeline/agent/graph/nodes/db_lookup.py`:
```python
from __future__ import annotations

from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.entities import EnrichedCandidate
from pipeline.agent.schemas.validation import AuditEvent
from pipeline.agent.tools.db import search_entity_by_name, search_entity_by_wikidata_id


def db_lookup(state: AgentRunState) -> AgentRunState:
    enriched: list[EnrichedCandidate] = []

    for candidate in state["candidate_entities"]:
        # Search by name
        matches = search_entity_by_name(candidate.label, entity_type=candidate.entity_type)
        existing = matches[0] if matches else None

        # Also search by QID if already known
        if candidate.wikidata_id and not existing:
            qid_matches = search_entity_by_wikidata_id(candidate.wikidata_id)
            existing = qid_matches[0] if qid_matches else None

        enriched.append(EnrichedCandidate(
            candidate=candidate,
            wikidata_match={"existing_entity": existing} if existing else None,
        ))

    state["enriched_entities"] = enriched
    existing_count = sum(1 for e in enriched if e.wikidata_match and e.wikidata_match.get("existing_entity"))
    state["audit_log"].append(AuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        node="db_lookup",
        action="db_lookup_complete",
        output_summary=f"{existing_count}/{len(enriched)} candidates already exist in DB",
    ))
    return state
```

- [ ] **Step 3: Run tests**

Run: `py -m pytest pipeline/agent/tests/test_nodes.py::test_db_lookup -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add pipeline/agent/graph/nodes/db_lookup.py
git commit -m "feat(agent): add db_lookup node"
```

---

### Task 14: Implement `resolve_wikidata` node

**Files:**
- Create: `pipeline/agent/graph/nodes/resolve_wikidata.py`
- Test: `pipeline/agent/tests/test_nodes.py` (add `test_resolve_wikidata`)

- [ ] **Step 1: Write failing test**

Add to `pipeline/agent/tests/test_nodes.py`:
```python
from pipeline.agent.graph.nodes.resolve_wikidata import resolve_wikidata
from unittest.mock import patch

@patch("pipeline.agent.graph.nodes.resolve_wikidata.search_wikidata_by_name")
def test_resolve_wikidata(mock_search):
    mock_search.return_value = [{"qid": "Q405", "label": "David IV of Georgia", "description": "King of Georgia"}]

    state: AgentRunState = {
        "run_id": "test_1",
        "raw_input": "...",
        "parsed_events": [],
        "candidate_entities": [],
        "candidate_relations": [],
        "enriched_entities": [EnrichedCandidate(candidate=CandidateEntity(label="David IV of Georgia", entity_type="person"))],
        "validation_results": [],
        "proposed_diff": None,
        "committed": [],
        "audit_log": [],
        "errors": [],
    }
    new_state = resolve_wikidata(state)
    assert new_state["enriched_entities"][0].wikidata_match is not None
```

Run: `py -m pytest pipeline/agent/tests/test_nodes.py::test_resolve_wikidata -v`
Expected: FAIL

- [ ] **Step 2: Implement `resolve_wikidata.py`**

Create `pipeline/agent/graph/nodes/resolve_wikidata.py`:
```python
from __future__ import annotations

from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.entities import EnrichedCandidate
from pipeline.agent.schemas.validation import AuditEvent
from pipeline.agent.tools.wikidata import search_wikidata_by_name, enrich_wikidata_entities


def resolve_wikidata(state: AgentRunState) -> AgentRunState:
    for enriched in state["enriched_entities"]:
        # Skip if already matched in DB with a QID
        if enriched.candidate.wikidata_id:
            qid = enriched.candidate.wikidata_id
        else:
            # Search by name
            results = search_wikidata_by_name(enriched.candidate.label, enriched.candidate.entity_type)
            if not results:
                continue
            qid = results[0].get("qid")
            if not qid:
                continue

        # Enrich with full Wikidata record
        full = enrich_wikidata_entities([qid])
        enriched.wikidata_match = full.get(qid, {})
        enriched.wikidata_match["qid"] = qid

        # Simple confidence scoring
        if enriched.wikidata_match.get("label", "").lower() == enriched.candidate.label.lower():
            enriched.system_confidence += 0.3
        if enriched.wikidata_match.get("description"):
            enriched.system_confidence += 0.1

    state["audit_log"].append(AuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        node="resolve_wikidata",
        action="wikidata_resolved",
        output_summary=f"Resolved {sum(1 for e in state['enriched_entities'] if e.wikidata_match)} entities",
    ))
    return state
```

- [ ] **Step 3: Run tests**

Run: `py -m pytest pipeline/agent/tests/test_nodes.py::test_resolve_wikidata -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add pipeline/agent/graph/nodes/resolve_wikidata.py
git commit -m "feat(agent): add resolve_wikidata node"
```

---

### Task 15: Implement `resolve_ohm` node

**Files:**
- Create: `pipeline/agent/graph/nodes/resolve_ohm.py`
- Test: `pipeline/agent/tests/test_nodes.py` (add `test_resolve_ohm`)

> **Note:** LangGraph `StateGraph.add_node()` expects callables that take **only** the state dict. Extra args must be bound with `functools.partial` in `workflow.py` or read from `AgentConfig`. This node reads `ohm_index_path` from `AgentConfig`.

- [ ] **Step 1: Write failing test**

Add to `pipeline/agent/tests/test_nodes.py`:
```python
from pipeline.agent.graph.nodes.resolve_ohm import resolve_ohm
from unittest.mock import patch

@patch("pipeline.agent.graph.nodes.resolve_ohm.search_ohm_by_wikidata_id")
def test_resolve_ohm(mock_search):
    mock_search.return_value = [{"object_type": "node", "object_id": 123, "name": "Didgori"}]

    state: AgentRunState = {
        "run_id": "test_1",
        "raw_input": "...",
        "parsed_events": [],
        "candidate_entities": [],
        "candidate_relations": [],
        "enriched_entities": [EnrichedCandidate(
            candidate=CandidateEntity(label="Didgori", entity_type="infrastructure_monument"),
            wikidata_match={"qid": "Q12345"},
        )],
        "validation_results": [],
        "proposed_diff": None,
        "committed": [],
        "audit_log": [],
        "errors": [],
    }
    new_state = resolve_ohm(state)
    assert new_state["enriched_entities"][0].ohm_match is not None
```

Run: `py -m pytest pipeline/agent/tests/test_nodes.py::test_resolve_ohm -v`
Expected: FAIL

- [ ] **Step 2: Implement `resolve_ohm.py`**

Create `pipeline/agent/graph/nodes/resolve_ohm.py`:
```python
from __future__ import annotations

from pipeline.agent.config import AgentConfig
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.validation import AuditEvent
from pipeline.agent.tools.ohm import search_ohm_by_wikidata_id, search_ohm_by_name, resolve_ohm_geometry


def resolve_ohm(state: AgentRunState) -> AgentRunState:
    cfg = AgentConfig()
    ohm_index_path = cfg.ohm_index_path

    for enriched in state["enriched_entities"]:
        match = None

        # Try by Wikidata ID first
        qid = enriched.wikidata_match.get("qid") if enriched.wikidata_match else None
        if qid:
            match = search_ohm_by_wikidata_id(qid, ohm_index_path)

        # Fallback to name search
        if not match:
            match = search_ohm_by_name(enriched.candidate.label, ohm_index_path)

        if match:
            enriched.ohm_match = match[0]
            # Resolve geometry
            geo = resolve_ohm_geometry(
                ohm_index_path,
                enriched.ohm_match["object_type"],
                enriched.ohm_match["object_id"],
            )
            if geo:
                enriched.geometry = geo
                enriched.system_confidence += 0.2

    state["audit_log"].append(AuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        node="resolve_ohm",
        action="ohm_resolved",
        output_summary=f"Resolved {sum(1 for e in state['enriched_entities'] if e.ohm_match)} geometries",
    ))
    return state
```

> **Note:** `ohm_index_path` is read from `AgentConfig.ohm_index_path` (add to `config.py` in Task 5). No extra positional args.

- [ ] **Step 3: Run tests**

Run: `py -m pytest pipeline/agent/tests/test_nodes.py::test_resolve_ohm -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add pipeline/agent/graph/nodes/resolve_ohm.py
git commit -m "feat(agent): add resolve_ohm node"
```

---

### Task 16: Implement `generate_content` node

**Files:**
- Create: `pipeline/agent/graph/nodes/generate_content.py`
- Test: `pipeline/agent/tests/test_nodes.py` (add `test_generate_content`)
- Create: `pipeline/agent/tests/fixtures/llm_responses/generate_content.json`

- [ ] **Step 1: Create mock fixture**

Create `pipeline/agent/tests/fixtures/llm_responses/generate_content.json`:
```json
{
  "summaries": {
    "David IV of Georgia": "Ruled the Kingdom of Georgia from 1089 to 1125 and led the decisive victory at the Battle of Didgori in 1121."
  },
  "relation_descriptions": {
    "David IV of Georgia|participated_in|Battle of Didgori": "Commanded the Georgian forces at the Battle of Didgori on August 12, 1121."
  }
}
```

- [ ] **Step 2: Write failing test**

Add to `pipeline/agent/tests/test_nodes.py`:
```python
from pipeline.agent.graph.nodes.generate_content import generate_content
from unittest.mock import patch
import json

@patch("pipeline.agent.graph.nodes.generate_content.ChatOpenAI")
def test_generate_content(mock_chat):
    mock_llm = MagicMock()
    with open("pipeline/agent/tests/fixtures/llm_responses/generate_content.json") as f:
        mock_llm.invoke.return_value = MagicMock(content=f.read())
    mock_chat.return_value = mock_llm

    state: AgentRunState = {
        "run_id": "test_1",
        "raw_input": "...",
        "parsed_events": [],
        "candidate_entities": [],
        "candidate_relations": [CandidateRelation(source_label="David IV of Georgia", target_label="Battle of Didgori", relationship_type="participated_in")],
        "enriched_entities": [EnrichedCandidate(candidate=CandidateEntity(label="David IV of Georgia", entity_type="person"))],
        "validation_results": [],
        "proposed_diff": None,
        "committed": [],
        "audit_log": [],
        "errors": [],
    }
    new_state = generate_content(state)
    assert new_state["enriched_entities"][0].summary is not None
```

Run: `py -m pytest pipeline/agent/tests/test_nodes.py::test_generate_content -v`
Expected: FAIL

- [ ] **Step 3: Implement `generate_content.py`**

Create `pipeline/agent/graph/nodes/generate_content.py`:
```python
from __future__ import annotations

import json
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from pipeline.agent.config import AgentConfig
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.validation import AuditEvent
from datetime import datetime, timezone

_STYLE_GUIDE_PATH = Path(__file__).parent.parent.parent / "style_guide.md"


def _load_style_guide() -> str:
    if _STYLE_GUIDE_PATH.exists():
        return _STYLE_GUIDE_PATH.read_text(encoding="utf-8")
    return ""


def generate_content(state: AgentRunState) -> AgentRunState:
    cfg = AgentConfig()
    llm = ChatOpenAI(model=cfg.generate_model, api_key=cfg.openai_api_key)
    style_guide = _load_style_guide()

    # Build context: all entities and relations
    entities_context = json.dumps([
        {
            "label": e.candidate.label,
            "type": e.candidate.entity_type,
            "wikidata_description": e.wikidata_match.get("description") if e.wikidata_match else None,
            "dates": {"start": e.candidate.start_date, "end": e.candidate.end_date},
        }
        for e in state["enriched_entities"]
    ], default=str)

    relations_context = json.dumps([
        {
            "source": r.source_label,
            "target": r.target_label,
            "type": r.relationship_type,
            "dates": {"start": r.start_date, "end": r.end_date},
        }
        for r in state["candidate_relations"]
    ], default=str)

    prompt = f"""You are a historical content writer. Write concise, flowing summaries and descriptions.

Style Guide:
{style_guide}

Entities:
{entities_context}

Relations:
{relations_context}

Output strictly as JSON:
{{"summaries": {{"Entity Label": "Summary text...", ...}}, "relation_descriptions": {{"Source Label|relationship_type|Target Label": "Description text...", ...}}}}
"""

    response = llm.invoke([HumanMessage(content=prompt)])
    content = response.content if hasattr(response, "content") else str(response)

    try:
        data = json.loads(content)
        summaries = data.get("summaries", {})
        rel_descs = data.get("relation_descriptions", {})

        for enriched in state["enriched_entities"]:
            enriched.summary = summaries.get(enriched.candidate.label)

        for relation in state["candidate_relations"]:
            key = f"{relation.source_label}|{relation.relationship_type}|{relation.target_label}"
            relation.description = rel_descs.get(key)
    except (json.JSONDecodeError, TypeError) as exc:
        state["errors"].append({
            "node": "generate_content",
            "error_type": "json_parse",
            "message": str(exc),
            "context": {"raw_response": content},
        })

    state["audit_log"].append(AuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        node="generate_content",
        action="content_generated",
        output_summary=f"Generated {len(summaries)} summaries, {len(rel_descs)} relation descriptions",
    ))
    return state
```

- [ ] **Step 4: Run tests**

Run: `py -m pytest pipeline/agent/tests/test_nodes.py::test_generate_content -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/agent/graph/nodes/generate_content.py pipeline/agent/tests/fixtures/llm_responses/generate_content.json
git commit -m "feat(agent): add generate_content node with style guide"
```

---

### Task 17: Implement `validate` node

**Files:**
- Create: `pipeline/agent/graph/nodes/validate.py`
- Test: `pipeline/agent/tests/test_nodes.py` (add `test_validate`)

- [ ] **Step 1: Write failing test**

Add to `pipeline/agent/tests/test_nodes.py`:
```python
from pipeline.agent.graph.nodes.validate import validate

def test_validate_blocks_invalid_type():
    state: AgentRunState = {
        "run_id": "test_1",
        "raw_input": "...",
        "parsed_events": [],
        "candidate_entities": [],
        "candidate_relations": [],
        "enriched_entities": [EnrichedCandidate(
            candidate=CandidateEntity(label="X", entity_type="invalid_type"),
            wikidata_match={"qid": "Q1"},
        )],
        "validation_results": [],
        "proposed_diff": None,
        "committed": [],
        "audit_log": [],
        "errors": [],
    }
    new_state = validate(state)
    assert not new_state["validation_results"][0].passed
```

Run: `py -m pytest pipeline/agent/tests/test_nodes.py::test_validate -v`
Expected: FAIL

- [ ] **Step 2: Implement `validate.py`**

Create `pipeline/agent/graph/nodes/validate.py`:
```python
from __future__ import annotations

from pipeline.agent.config import ENTITY_RISK_POLICIES, RELATION_RISK_POLICIES
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.validation import ValidationResult, AuditEvent

# Allowed types from existing PHP enums
ALLOWED_ENTITY_TYPES = set(ENTITY_RISK_POLICIES.keys()) | {
    "military_unit", "diplomatic_relationship", "social_class",
    "extraction_infra", "educational_institution", "event_rebellion",
    "event_natural_disaster", "event_tech_adoption", "event_legal_reform",
    "migration", "epidemic_disease", "natural_resource",
    "intellectual_movement", "religious_text", "legal_code", "technology",
}

ALLOWED_RELATION_TYPES = set(RELATION_RISK_POLICIES.keys()) | {
    "contains", "capital_of", "split_from", "merged_into",
    "resided_in", "founded", "authored", "commissioned",
    "married_to", "parent_of", "child_of", "sibling_of",
    "mentor_of", "student_of", "assassinated_by", "member_of_dynasty", "patron_of",
    "defeated_at", "victorious_at", "stationed_at", "recruited_from", "commanded_by",
    "connects", "produces", "extracts", "supplies", "controlled_by",
    "passes_through", "minted_by", "used_currency",
    "adheres_to", "official_religion_of", "persecuted_by",
    "influenced_by", "inspired", "schism_from", "translated_into",
    "located_at", "built_by", "destroyed_by", "restored_by",
    "contributed_to", "enabled", "prevented",
}


def validate(state: AgentRunState) -> AgentRunState:
    results = []

    for enriched in state["enriched_entities"]:
        errors = []
        warnings = []
        confidence = enriched.system_confidence

        # Entity type validation
        if enriched.candidate.entity_type not in ALLOWED_ENTITY_TYPES:
            errors.append(f"Invalid entity type: {enriched.candidate.entity_type}")

        # Wikidata validation
        policy = ENTITY_RISK_POLICIES.get(enriched.candidate.entity_type, {})
        if policy.get("requires_wikidata") and not enriched.wikidata_match:
            errors.append("Missing Wikidata ID")
            confidence -= 0.3

        # Geometry validation for geography-sensitive types
        geo_sensitive = {"political_entity", "city", "infrastructure_monument", "event_battle", "trade_route"}
        if enriched.candidate.entity_type in geo_sensitive and not enriched.geometry:
            warnings.append("Missing geometry for geography-sensitive entity")
            confidence -= 0.15

        # Confidence bounds
        confidence = max(0.0, min(1.0, confidence))
        enriched.final_confidence = confidence

        results.append(ValidationResult(
            candidate_id=enriched.candidate.label,
            passed=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        ))

    # Relation validation
    for relation in state["candidate_relations"]:
        errors = []
        if relation.relationship_type not in ALLOWED_RELATION_TYPES:
            errors.append(f"Invalid relation type: {relation.relationship_type}")

        # Check source/target exist in enriched entities
        entity_labels = {e.candidate.label for e in state["enriched_entities"]}
        if relation.source_label not in entity_labels:
            errors.append(f"Source entity not found: {relation.source_label}")
        if relation.target_label not in entity_labels:
            errors.append(f"Target entity not found: {relation.target_label}")

        results.append(ValidationResult(
            candidate_id=f"{relation.source_label}|{relation.relationship_type}|{relation.target_label}",
            passed=len(errors) == 0,
            errors=errors,
        ))

    state["validation_results"] = results
    passed_count = sum(1 for r in results if r.passed)
    state["audit_log"].append(AuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        node="validate",
        action="validation_complete",
        output_summary=f"{passed_count}/{len(results)} candidates passed validation",
    ))
    return state
```

- [ ] **Step 3: Run tests**

Run: `py -m pytest pipeline/agent/tests/test_nodes.py::test_validate -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add pipeline/agent/graph/nodes/validate.py
git commit -m "feat(agent): add validate node with policy-based scoring"
```

---

### Task 18: Implement `build_diff` node

**Files:**
- Create: `pipeline/agent/graph/nodes/build_diff.py`
- Test: `pipeline/agent/tests/test_nodes.py` (add `test_build_diff`)

- [ ] **Step 1: Write failing test**

Add to `pipeline/agent/tests/test_nodes.py`:
```python
from pipeline.agent.graph.nodes.build_diff import build_diff

def test_build_diff_sorts_into_buckets():
    state: AgentRunState = {
        "run_id": "test_1",
        "raw_input": "...",
        "parsed_events": [],
        "candidate_entities": [],
        "candidate_relations": [],
        "enriched_entities": [EnrichedCandidate(
            candidate=CandidateEntity(label="Battle X", entity_type="event_battle"),
            final_confidence=0.98,
        )],
        "validation_results": [ValidationResult(candidate_id="Battle X", passed=True)],
        "proposed_diff": None,
        "committed": [],
        "audit_log": [],
        "errors": [],
    }
    new_state = build_diff(state)
    assert new_state["proposed_diff"] is not None
    assert len(new_state["proposed_diff"].create_entities) == 1
```

Run: `py -m pytest pipeline/agent/tests/test_nodes.py::test_build_diff -v`
Expected: FAIL

- [ ] **Step 2: Implement `build_diff.py`**

Create `pipeline/agent/graph/nodes/build_diff.py`:
```python
from __future__ import annotations

from pipeline.agent.config import ENTITY_RISK_POLICIES, RELATION_RISK_POLICIES
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.proposals import ProposedDiff
from pipeline.agent.schemas.validation import AuditEvent


def build_diff(state: AgentRunState) -> AgentRunState:
    create_entities = []
    create_relations = []
    review_items = []
    blocked_items = []

    # Map validation results by candidate ID
    validation_map = {v.candidate_id: v for v in state["validation_results"]}

    for enriched in state["enriched_entities"]:
        val = validation_map.get(enriched.candidate.label)
        if not val or not val.passed:
            blocked_items.append({
                "type": "entity",
                "label": enriched.candidate.label,
                "reason": val.errors if val else ["No validation result"],
            })
            continue

        # Check if already exists in DB
        existing = enriched.wikidata_match and enriched.wikidata_match.get("existing_entity")
        if existing:
            continue  # Reuse existing — not in diff

        create_entities.append(enriched)

    for relation in state["candidate_relations"]:
        rel_id = f"{relation.source_label}|{relation.relationship_type}|{relation.target_label}"
        val = validation_map.get(rel_id)
        if not val or not val.passed:
            blocked_items.append({
                "type": "relation",
                "relation_id": rel_id,
                "reason": val.errors if val else ["No validation result"],
            })
            continue
        create_relations.append(relation)

    diff = ProposedDiff(
        run_id=state["run_id"],
        summary={
            "entities_to_create": len(create_entities),
            "relations_to_create": len(create_relations),
            "entities_reused": len(state["enriched_entities"]) - len(create_entities) - len([b for b in blocked_items if b["type"] == "entity"]),
            "requires_review": len(review_items),
            "blocked": len(blocked_items),
        },
        create_entities=create_entities,
        create_relations=create_relations,
        review_items=review_items,
        blocked_items=blocked_items,
    )

    state["proposed_diff"] = diff
    state["audit_log"].append(AuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        node="build_diff",
        action="diff_built",
        output_summary=f"Create {len(create_entities)} entities, {len(create_relations)} relations; {len(blocked_items)} blocked",
    ))
    return state
```

- [ ] **Step 3: Run tests**

Run: `py -m pytest pipeline/agent/tests/test_nodes.py::test_build_diff -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add pipeline/agent/graph/nodes/build_diff.py
git commit -m "feat(agent): add build_diff node"
```

---

### Task 19: Implement `approval_gate` node

**Files:**
- Create: `pipeline/agent/graph/nodes/approval_gate.py`
- Test: `pipeline/agent/tests/test_nodes.py` (add `test_approval_gate`)

- [ ] **Step 1: Write failing test**

Add to `pipeline/agent/tests/test_nodes.py`:
```python
from pipeline.agent.graph.nodes.approval_gate import approval_gate

def test_approval_gate_auto_commits_high_conf():
    state: AgentRunState = {
        "run_id": "test_1",
        "raw_input": "...",
        "parsed_events": [],
        "candidate_entities": [],
        "candidate_relations": [],
        "enriched_entities": [EnrichedCandidate(
            candidate=CandidateEntity(label="Battle X", entity_type="event_battle"),
            final_confidence=0.98,
        )],
        "validation_results": [ValidationResult(candidate_id="Battle X", passed=True)],
        "proposed_diff": ProposedDiff(
            run_id="test_1",
            create_entities=[EnrichedCandidate(
                candidate=CandidateEntity(label="Battle X", entity_type="event_battle"),
                final_confidence=0.98,
            )],
            create_relations=[],
        ),
        "committed": [],
        "audit_log": [],
        "errors": [],
    }
    new_state = approval_gate(state)
    assert len(new_state["proposed_diff"].create_entities) == 1
```

Run: `py -m pytest pipeline/agent/tests/test_nodes.py::test_approval_gate -v`
Expected: FAIL

- [ ] **Step 2: Implement `approval_gate.py`**

Create `pipeline/agent/graph/nodes/approval_gate.py`:
```python
from __future__ import annotations

from pipeline.agent.config import ENTITY_RISK_POLICIES, RELATION_RISK_POLICIES, AgentConfig
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.proposals import ApprovalDecision
from pipeline.agent.schemas.validation import AuditEvent


def approval_gate(state: AgentRunState) -> AgentRunState:
    cfg = AgentConfig()
    diff = state["proposed_diff"]
    if diff is None:
        state["errors"].append({
            "node": "approval_gate",
            "error_type": "missing_diff",
            "message": "No proposed diff available",
        })
        return state

    auto_entities = []
    auto_relations = []
    flagged = []

    for enriched in diff.create_entities:
        policy = ENTITY_RISK_POLICIES.get(enriched.candidate.entity_type, {})
        threshold = policy.get("auto_commit_threshold", cfg.auto_commit_threshold)

        if enriched.final_confidence >= threshold and policy.get("risk_level") == "low":
            auto_entities.append(enriched.candidate.label)
        else:
            flagged.append({
                "type": "entity",
                "label": enriched.candidate.label,
                "reason": f"confidence {enriched.final_confidence:.2f} < threshold {threshold} or risk level not low",
            })

    for relation in diff.create_relations:
        policy = RELATION_RISK_POLICIES.get(relation.relationship_type, {})
        threshold = policy.get("auto_commit_threshold", cfg.auto_commit_threshold)
        # Relations need confidence from their connected entities
        # For MVP, use a default check
        if policy.get("risk_level") == "low":
            auto_relations.append(f"{relation.source_label}|{relation.relationship_type}|{relation.target_label}")
        else:
            flagged.append({
                "type": "relation",
                "relation_id": f"{relation.source_label}|{relation.relationship_type}|{relation.target_label}",
                "reason": f"risk level {policy.get('risk_level')} not eligible for auto-commit",
            })

    # Move flagged items to review_items
    diff.review_items = flagged
    diff.create_entities = [e for e in diff.create_entities if e.candidate.label in auto_entities]
    diff.create_relations = [r for r in diff.create_relations if f"{r.source_label}|{r.relationship_type}|{r.target_label}" in auto_relations]

    state["audit_log"].append(AuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        node="approval_gate",
        action="approval_decision",
        output_summary=f"Auto-commit: {len(auto_entities)} entities, {len(auto_relations)} relations; Flagged: {len(flagged)}",
    ))
    return state
```

- [ ] **Step 3: Run tests**

Run: `py -m pytest pipeline/agent/tests/test_nodes.py::test_approval_gate -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add pipeline/agent/graph/nodes/approval_gate.py
git commit -m "feat(agent): add approval_gate node with risk-based auto-commit"
```

---

### Task 20: Implement `commit_writer` node

**Files:**
- Create: `pipeline/agent/graph/nodes/commit_writer.py`
- Test: `pipeline/agent/tests/test_nodes.py` (add `test_commit_writer`)

- [ ] **Step 1: Write failing test**

Add to `pipeline/agent/tests/test_nodes.py`:
```python
from pipeline.agent.graph.nodes.commit_writer import commit_writer
from unittest.mock import patch

@patch("pipeline.agent.graph.nodes.commit_writer.run_artisan_command")
def test_commit_writer_writes_jsonl(mock_run):
    mock_run.return_value = {"returncode": 0, "stdout": "Imported 1", "stderr": ""}

    state: AgentRunState = {
        "run_id": "test_1",
        "raw_input": "...",
        "parsed_events": [],
        "candidate_entities": [],
        "candidate_relations": [],
        "enriched_entities": [EnrichedCandidate(
            candidate=CandidateEntity(label="Battle X", entity_type="event_battle"),
            final_confidence=0.98,
            summary="A battle.",
            wikidata_match={"qid": "Q999"},
        )],
        "validation_results": [],
        "proposed_diff": ProposedDiff(
            run_id="test_1",
            create_entities=[EnrichedCandidate(
                candidate=CandidateEntity(label="Battle X", entity_type="event_battle"),
                final_confidence=0.98,
                summary="A battle.",
                wikidata_match={"qid": "Q999"},
            )],
            create_relations=[],
        ),
        "committed": [],
        "audit_log": [],
        "errors": [],
    }
    new_state = commit_writer(state, output_root="/tmp/test_agent")
    assert len(new_state["committed"]) > 0
```

Run: `py -m pytest pipeline/agent/tests/test_nodes.py::test_commit_writer -v`
Expected: FAIL

- [ ] **Step 2: Implement `commit_writer.py`**

Create `pipeline/agent/graph/nodes/commit_writer.py`:
```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.relations import CommittedChange
from pipeline.agent.schemas.validation import AuditEvent
from pipeline.agent.tools.app_api import build_artisan_command, run_artisan_command


def _entity_to_jsonl_record(enriched) -> dict[str, Any]:
    """Convert an EnrichedCandidate to a JSONL record matching pipeline:import format."""
    return {
        "name": enriched.candidate.label,
        "entity_type": enriched.candidate.entity_type,
        "summary": enriched.summary or "",
        "wikidata_id": enriched.wikidata_match.get("qid") if enriched.wikidata_match else None,
        "start_date": enriched.candidate.start_date,
        "end_date": enriched.candidate.end_date,
        "alternative_names": enriched.candidate.aliases,
        "geometry": enriched.geometry,
        "source_citations": {
            "created_by": "historical-agent-pipeline",
            "confidence": enriched.final_confidence,
        },
    }


def _relation_to_jsonl_record(relation) -> dict[str, Any]:
    """Convert a CandidateRelation to a JSONL record."""
    return {
        "source_name": relation.source_label,
        "target_name": relation.target_label,
        "relationship_type": relation.relationship_type,
        "start_date": relation.start_date,
        "end_date": relation.end_date,
        "description": relation.description,
        "source_citations": {
            "created_by": "historical-agent-pipeline",
        },
    }


def commit_writer(state: AgentRunState) -> AgentRunState:
    from pipeline.agent.config import AgentConfig
    from datetime import datetime
    cfg = AgentConfig()
    output_root = Path(cfg.output_dir) / state["run_id"]

    output_root.mkdir(parents=True, exist_ok=True)
    diff = state["proposed_diff"]
    if diff is None:
        return state

    # Write entities JSONL
    entity_records = [_entity_to_jsonl_record(e) for e in diff.create_entities]
    entity_path = output_root / "entities_to_create.jsonl"
    with entity_path.open("w", encoding="utf-8") as f:
        for record in entity_records:
            f.write(json.dumps(record, default=str) + "\n")

    # Write relations JSONL
    relation_records = [_relation_to_jsonl_record(r) for r in diff.create_relations]
    relation_path = output_root / "relations_to_create.jsonl"
    with relation_path.open("w", encoding="utf-8") as f:
        for record in relation_records:
            f.write(json.dumps(record, default=str) + "\n")

    # Invoke artisan commands
    if entity_records:
        cmd = build_artisan_command("pipeline:import", str(entity_path), sync=True, batch_id=state["run_id"])
        result = run_artisan_command(cmd)
        state["committed"].append(CommittedChange(
            change_type="entity",
            record={"path": str(entity_path), "count": len(entity_records), "result": result},
            committed_at=datetime.now(timezone.utc).isoformat(),
            batch_id=state["run_id"],
        ))

    if relation_records:
        # Relations are imported via the hint pipeline
        rel_dir = output_root
        cmd = build_artisan_command("pipeline:import-borders", str(rel_dir), sync=True, batch_id=state["run_id"])
        result = run_artisan_command(cmd)
        state["committed"].append(CommittedChange(
            change_type="relation",
            record={"path": str(relation_path), "count": len(relation_records), "result": result},
            committed_at=datetime.now(timezone.utc).isoformat(),
            batch_id=state["run_id"],
        ))

    state["audit_log"].append(AuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        node="commit_writer",
        action="committed",
        output_summary=f"Wrote {len(entity_records)} entities, {len(relation_records)} relations",
    ))
    return state
```

- [ ] **Step 3: Run tests**

Run: `py -m pytest pipeline/agent/tests/test_nodes.py::test_commit_writer -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add pipeline/agent/graph/nodes/commit_writer.py
git commit -m "feat(agent): add commit_writer node with JSONL artifact generation"
```

---

### Task 21: Implement `audit_logger` node

**Files:**
- Create: `pipeline/agent/graph/nodes/audit_logger.py`
- Test: `pipeline/agent/tests/test_nodes.py` (add `test_audit_logger`)

- [ ] **Step 1: Write failing test**

Add to `pipeline/agent/tests/test_nodes.py`:
```python
from pipeline.agent.graph.nodes.audit_logger import audit_logger
from pathlib import Path

def test_audit_logger_writes_manifest(tmp_path):
    state: AgentRunState = {
        "run_id": "test_1",
        "raw_input": "Test input",
        "parsed_events": [],
        "candidate_entities": [],
        "candidate_relations": [],
        "enriched_entities": [],
        "validation_results": [],
        "proposed_diff": None,
        "committed": [],
        "audit_log": [AuditEvent(timestamp="2026-01-01T00:00:00", node="test", action="start")],
        "errors": [],
    }
    new_state = audit_logger(state, output_root=str(tmp_path))
    manifest_path = tmp_path / "manifest.json"
    assert manifest_path.exists()
```

Run: `py -m pytest pipeline/agent/tests/test_nodes.py::test_audit_logger -v`
Expected: FAIL

- [ ] **Step 2: Implement `audit_logger.py`**

Create `pipeline/agent/graph/nodes/audit_logger.py`:
```python
from __future__ import annotations

import json
from pathlib import Path

from pipeline.agent.config import AgentConfig
from pipeline.agent.graph.state import AgentRunState


def audit_logger(state: AgentRunState) -> AgentRunState:
    cfg = AgentConfig()
    output_root = Path(cfg.output_dir) / state["run_id"]

    output_root.mkdir(parents=True, exist_ok=True)

    manifest = {
        "run_id": state["run_id"],
        "input_hash": hash(state["raw_input"]) & 0xFFFFFFFF,
        "parsed_event_count": len(state["parsed_events"]),
        "candidate_entity_count": len(state["candidate_entities"]),
        "candidate_relation_count": len(state["candidate_relations"]),
        "enriched_count": len(state["enriched_entities"]),
        "validation_passed": sum(1 for v in state["validation_results"] if v.passed),
        "validation_failed": sum(1 for v in state["validation_results"] if not v.passed),
        "committed_count": len(state["committed"]),
        "error_count": len(state["errors"]),
        "audit_log": [a.model_dump() for a in state["audit_log"]],
        "errors": [e.model_dump() for e in state["errors"]],
    }

    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    return state
```

- [ ] **Step 3: Run tests**

Run: `py -m pytest pipeline/agent/tests/test_nodes.py::test_audit_logger -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add pipeline/agent/graph/nodes/audit_logger.py
git commit -m "feat(agent): add audit_logger node"
```

---

### Task 22: Create `messy_research` stub

**Files:**
- Create: `pipeline/agent/graph/nodes/messy_research.py`

- [ ] **Step 1: Implement stub**

Create `pipeline/agent/graph/nodes/messy_research.py`:
```python
from __future__ import annotations

from pipeline.agent.graph.state import AgentRunState


def messy_research(state: AgentRunState) -> AgentRunState:
    """Stub for post-MVP DeepAgent node.

    This node would be invoked conditionally when deterministic resolution fails.
    For MVP, ambiguity is handled by routing to approval_gate review items.
    """
    state["audit_log"].append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "node": "messy_research",
        "action": "skipped_stub",
        "output_summary": "DeepAgents deferred to post-MVP",
    })
    return state
```

- [ ] **Step 2: Commit**

```bash
git add pipeline/agent/graph/nodes/messy_research.py
git commit -m "feat(agent): add messy_research node stub (post-MVP)"
```

---

## Phase 4: Graph Wiring

### Task 23: Implement workflow builder

**Files:**
- Create: `pipeline/agent/graph/workflow.py`
- Test: `pipeline/agent/tests/test_graph.py`

- [ ] **Step 1: Write failing integration test**

Create `pipeline/agent/tests/test_graph.py`:
```python
from unittest.mock import patch, MagicMock
import json

from pipeline.agent.graph.workflow import build_agent_workflow
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.entities import ParsedEvent, CandidateEntity, EnrichedCandidate
from pipeline.agent.schemas.relations import CandidateRelation


def _mock_llm_response(content: dict):
    mock = MagicMock()
    mock.invoke.return_value = MagicMock(content=json.dumps(content))
    return mock


@patch("pipeline.agent.graph.nodes.parse_sequence.ChatOpenAI")
@patch("pipeline.agent.graph.nodes.extract_candidates.ChatOpenAI")
@patch("pipeline.agent.graph.nodes.generate_content.ChatOpenAI")
@patch("pipeline.agent.graph.nodes.db_lookup.search_entity_by_name")
@patch("pipeline.agent.graph.nodes.resolve_wikidata.search_wikidata_by_name")
@patch("pipeline.agent.graph.nodes.resolve_ohm.search_ohm_by_wikidata_id")
def test_full_graph_runs(mock_ohm, mock_wd, mock_db, mock_gen, mock_ext, mock_parse):
    mock_parse.return_value = _mock_llm_response({
        "events": [{"label": "Battle X", "description": "...", "start_date": "1121-08-12", "end_date": "1121-08-12", "mentioned_entities": ["David"], "date_uncertain": False}]
    })
    mock_ext.return_value = _mock_llm_response({
        "candidate_entities": [{"label": "David", "entity_type": "person", "aliases": []}],
        "candidate_relations": [],
    })
    mock_gen.return_value = _mock_llm_response({"summaries": {"David": "A king."}, "relation_descriptions": {}})
    mock_db.return_value = []
    mock_wd.return_value = [{"qid": "Q405", "label": "David", "description": "King"}]
    mock_ohm.return_value = []

    graph = build_agent_workflow()
    state: AgentRunState = {
        "run_id": "test_graph_1",
        "raw_input": "In 1121, David fought at Battle X.",
        "parsed_events": [],
        "candidate_entities": [],
        "candidate_relations": [],
        "enriched_entities": [],
        "validation_results": [],
        "proposed_diff": None,
        "committed": [],
        "audit_log": [],
        "errors": [],
    }
    final_state = graph.invoke(state)
    assert final_state["proposed_diff"] is not None
```

Run: `py -m pytest pipeline/agent/tests/test_graph.py -v`
Expected: FAIL

- [ ] **Step 2: Implement `workflow.py`**

Create `pipeline/agent/graph/workflow.py`:
```python
from __future__ import annotations

from langgraph.graph import StateGraph, END

from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.graph.nodes.parse_sequence import parse_sequence
from pipeline.agent.graph.nodes.extract_candidates import extract_candidates
from pipeline.agent.graph.nodes.db_lookup import db_lookup
from pipeline.agent.graph.nodes.resolve_wikidata import resolve_wikidata
from pipeline.agent.graph.nodes.resolve_ohm import resolve_ohm
from pipeline.agent.graph.nodes.generate_content import generate_content
from pipeline.agent.graph.nodes.validate import validate
from pipeline.agent.graph.nodes.build_diff import build_diff
from pipeline.agent.graph.nodes.approval_gate import approval_gate
from pipeline.agent.graph.nodes.commit_writer import commit_writer
from pipeline.agent.graph.nodes.audit_logger import audit_logger
from pipeline.agent.graph.nodes.messy_research import messy_research


def build_agent_workflow():
    """Build and compile the LangGraph workflow."""
    builder = StateGraph(AgentRunState)

    # Add nodes
    builder.add_node("parse_sequence", parse_sequence)
    builder.add_node("extract_candidates", extract_candidates)
    builder.add_node("db_lookup", db_lookup)
    builder.add_node("resolve_wikidata", resolve_wikidata)
    builder.add_node("resolve_ohm", resolve_ohm)
    builder.add_node("generate_content", generate_content)
    builder.add_node("validate", validate)
    builder.add_node("build_diff", build_diff)
    builder.add_node("approval_gate", approval_gate)
    builder.add_node("commit_writer", commit_writer)
    builder.add_node("audit_logger", audit_logger)
    builder.add_node("messy_research", messy_research)

    # Define edges (linear for MVP)
    builder.set_entry_point("parse_sequence")
    builder.add_edge("parse_sequence", "extract_candidates")
    builder.add_edge("extract_candidates", "db_lookup")
    builder.add_edge("db_lookup", "resolve_wikidata")
    builder.add_edge("resolve_wikidata", "resolve_ohm")
    builder.add_edge("resolve_ohm", "generate_content")
    builder.add_edge("generate_content", "validate")
    builder.add_edge("validate", "build_diff")
    builder.add_edge("build_diff", "approval_gate")
    builder.add_edge("approval_gate", "commit_writer")
    builder.add_edge("commit_writer", "audit_logger")
    builder.add_edge("audit_logger", END)

    # Conditional edge from validate to messy_research if needed (post-MVP)
    # For now, always go to build_diff

    return builder.compile()
```

- [ ] **Step 3: Run tests**

Run: `py -m pytest pipeline/agent/tests/test_graph.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add pipeline/agent/graph/workflow.py pipeline/agent/tests/test_graph.py
git commit -m "feat(agent): wire LangGraph workflow with all nodes"
```

---

## Phase 5: CLI Integration

### Task 24: Create agent CLI entry point

**Files:**
- Create: `pipeline/agent/__main__.py`
- Modify: `pipeline/__main__.py` (add `agent` subcommand)

- [ ] **Step 1: Implement agent CLI using click**

Create `pipeline/agent/__main__.py`:
```python
from __future__ import annotations

import uuid
from pathlib import Path

import click

from pipeline.agent.config import AgentConfig
from pipeline.agent.graph.workflow import build_agent_workflow
from pipeline.agent.graph.state import AgentRunState


@click.command(name="agent")
@click.option("--input", "-i", required=True, type=click.Path(exists=True, path_type=Path), help="Path to raw text file")
@click.option("--output-dir", "-o", default="output/agent_runs", type=click.Path(path_type=Path), help="Output directory")
@click.option("--run-id", default=None, help="Run ID (default: auto-generated)")
@click.option("--ohm-index", default=None, type=click.Path(path_type=Path), help="Path to OHM SQLite index")
def agent_cli(input: Path, output_dir: Path, run_id: str | None, ohm_index: Path | None):
    """Run the historical entity agentic pipeline on a raw text input."""
    raw_input = input.read_text(encoding="utf-8")
    run_id = run_id or f"agent-{uuid.uuid4().hex[:8]}"

    # Override OHM index if provided
    if ohm_index:
        cfg = AgentConfig()
        cfg.ohm_index_path = str(ohm_index)

    state: AgentRunState = {
        "run_id": run_id,
        "raw_input": raw_input,
        "parsed_events": [],
        "candidate_entities": [],
        "candidate_relations": [],
        "enriched_entities": [],
        "validation_results": [],
        "proposed_diff": None,
        "committed": [],
        "audit_log": [],
        "errors": [],
    }

    graph = build_agent_workflow()
    final_state = graph.invoke(state)

    click.echo(f"Run complete: {run_id}")
    click.echo(f"Output: {output_dir / run_id}")
    if final_state["proposed_diff"]:
        click.echo(f"Entities to create: {final_state['proposed_diff'].summary.get('entities_to_create', 0)}")
        click.echo(f"Relations to create: {final_state['proposed_diff'].summary.get('relations_to_create', 0)}")
        click.echo(f"Flagged for review: {len(final_state['proposed_diff'].review_items)}")
        click.echo(f"Blocked: {len(final_state['proposed_diff'].blocked_items)}")

    if final_state["errors"]:
        click.echo(f"Errors: {len(final_state['errors'])}")


# Export for root CLI registration
cli = agent_cli
```

- [ ] **Step 2: Register subcommand in root CLI**

Modify `pipeline/__main__.py`. After the existing `cli.add_command(...)` lines, add:
```python
from pipeline.agent.__main__ import cli as agent_cli
cli.add_command(agent_cli, name="agent")
```

> **Note:** The root CLI uses `click.Group`. Commands are registered via `cli.add_command()`. This matches the existing pattern for wikidata, borders, and collections subcommands.

- [ ] **Step 3: Test CLI**

Create a test input file:
```bash
echo "In 1121, David IV of Georgia defeated Ilghazi at the Battle of Didgori." > /tmp/test_input.txt
```

Run: `py -m pipeline agent --input /tmp/test_input.txt --run-id test_cli_1`
Expected: Runs through the graph, outputs results to `output/agent_runs/test_cli_1/`

- [ ] **Step 4: Commit**

```bash
git add pipeline/agent/__main__.py pipeline/__main__.py
git commit -m "feat(agent): add CLI entry point and register agent subcommand"
```

---

## Phase 6: Final Verification

### Task 25: Run full test suite

- [ ] **Step 1: Run all agent tests**

Run: `py -m pytest pipeline/agent/tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Verify no regressions in existing pipeline**

Run: `py -m pytest pipeline/tests/ -v`
Expected: All existing tests still PASS

- [ ] **Step 3: Lint check**

Run: `ruff check pipeline/agent/` (or equivalent linter)
Expected: No errors

- [ ] **Step 4: Final commit**

```bash
git add docs/superpowers/plans/2026-06-09-historical-entity-agentic-pipeline.md
git commit -m "docs: add historical entity agentic pipeline implementation plan"
```

---

## Summary

| Phase | Tasks | Files Created | Files Modified |
|-------|-------|---------------|----------------|
| 1: Foundations | 1–6 | 25+ | `requirements.txt` |
| 2: Tool Layer | 7–10 | 4 | — |
| 3: Graph Nodes | 11–22 | 11 | — |
| 4: Graph Wiring | 23 | 2 | — |
| 5: CLI Integration | 24 | 1 | `pipeline/__main__.py` |
| 6: Verification | 25 | — | — |
