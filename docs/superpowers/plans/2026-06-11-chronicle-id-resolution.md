# Chronicle ID Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the agent pipeline so entities/relations are committed to the DB before the chronicle is built, and chronicle entries reference real DB entity IDs instead of string labels.

**Architecture:** Insert a new `resolve_entity_ids` node between `commit_writer` and `chronicle_builder`. This node queries the DB for committed entities/relations and builds lookup maps (`entity_id_map`, `relation_id_map`) consumed by `chronicle_builder`. The result is a chronicle with real DB IDs, ready for downstream import.

**Tech Stack:** Python 3.10+, LangGraph, PostgreSQL (via psycopg), Pydantic

**Design Doc:** `docs/superpowers/specs/2026-06-11-chronicle-id-resolution-design.md`

---

## File Structure

| File | Role |
|------|------|
| `pipeline/agent/graph/state.py` | Add `entity_id_map`, `relation_id_map` to `AgentRunState` |
| `pipeline/agent/graph/nodes/resolve_entity_ids.py` | **CREATE** — new node: query DB for committed IDs, populate maps |
| `pipeline/agent/graph/workflow.py` | Register new node, wire edges between `commit_writer` → `resolve_entity_ids` → `chronicle_builder` |
| `pipeline/agent/graph/nodes/chronicle_builder.py` | Update to consume `entity_id_map`/`relation_id_map` |
| `pipeline/agent/tools/db.py` | Add `search_relationship_by_labels()` helper |
| `pipeline/agent/tests/test_chronicle_builder.py` | Update fixtures with new state fields |
| `pipeline/agent/tests/test_nodes_chronicle_ids.py` | **CREATE** — tests for `resolve_entity_ids` node |
| `pipeline/agent/tests/test_graph.py` | Update e2e mock to populate `entity_id_map` in expected result |

## Task Breakdown

### Task 1: Add DB helper for relationship lookup

**Files:**
- Modify: `pipeline/agent/tools/db.py:75-120`
- Test: `pipeline/agent/tests/test_tools.py`

- [ ] **Step 1: Write the failing test**

```python
# In pipeline/agent/tests/test_tools.py
from pipeline.agent.tools.db import search_relationship_by_labels


def test_search_relationship_by_labels_returns_empty_on_no_db():
    """Should return [] when DATABASE_URL is not set."""
    result = search_relationship_by_labels("Alexander", "Darius", "fought_at")
    assert result == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest pipeline/agent/tests/test_tools.py::test_search_relationship_by_labels_returns_empty_on_no_db -v`
Expected: FAIL with `ModuleNotFoundError` or `AttributeError`

- [ ] **Step 3: Implement `search_relationship_by_labels`**

Append to `pipeline/agent/tools/db.py`:

```python
def search_relationship_by_labels(
    source_label: str,
    target_label: str,
    relationship_type: str,
) -> list[dict[str, Any]]:
    """Search for a relationship by source/target labels and type.
    
    Returns list with relationship_id if found, or empty list.
    """
    conn = _get_db_connection()
    if conn is None:
        return []

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.id, r.source_id, r.target_id, r.relationship_type
                FROM relationships r
                JOIN entities src ON r.source_id = src.entity_id
                JOIN entities tgt ON r.target_id = tgt.entity_id
                WHERE src.name = %s AND tgt.name = %s AND r.relationship_type = %s
                LIMIT 1
                """,
                (source_label, target_label, relationship_type),
            )
            row = cursor.fetchone()
            if row:
                return [{
                    "relationship_id": row[0],
                    "source_id": row[1],
                    "target_id": row[2],
                    "relationship_type": row[3],
                }]
            return []
    except Exception:
        return []
    finally:
        conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest pipeline/agent/tests/test_tools.py::test_search_relationship_by_labels_returns_empty_on_no_db -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/agent/tools/db.py pipeline/agent/tests/test_tools.py
git commit -m "feat(agent): add search_relationship_by_labels DB helper"
```

---

### Task 2: Add new state fields

**Files:**
- Modify: `pipeline/agent/graph/state.py`

- [ ] **Step 1: Add `entity_id_map` and `relation_id_map` to AgentRunState**

```python
class AgentRunState(TypedDict):
    run_id: str
    raw_input: str
    date_hints: list[dict[str, str]]
    parsed_events: list[ParsedEvent]
    candidate_entities: list[CandidateEntity]
    candidate_relations: list[CandidateRelation]
    enriched_entities: list[EnrichedCandidate]
    validation_results: list[ValidationResult]
    proposed_diff: ProposedDiff | None
    committed: list[CommittedChange]
    chronicle: Chronicle | None
    title: str | None
    create_chronicle: bool
    entity_id_map: dict[str, str]        # label → DB entity_id
    relation_id_map: dict[str, str]      # "src|type|tgt" → DB relationship_id
```

- [ ] **Step 2: Update all state initializations in workflow.py**

In `pipeline/agent/graph/workflow.py::run_agent()`, add the two new fields with empty dict defaults:

```python
initial_state: AgentRunState = {
    "run_id": run_id,
    "raw_input": raw_input,
    # ...existing fields...
    "entity_id_map": {},
    "relation_id_map": {},
}
```

- [ ] **Step 3: Update all test fixtures that create AgentRunState**

The following files create AgentRunState dicts directly and need the new fields:
- `pipeline/agent/tests/test_chronicle_builder.py` (2 fixtures)
- `pipeline/agent/tests/test_graph.py` (state built by run_agent, no change needed since run_agent sets defaults)

Add `"entity_id_map": {}, "relation_id_map": {},` to each fixture.

- [ ] **Step 4: Run tests to verify**

Run: `py -m pytest pipeline/agent/tests/ -q`
Expected: all pass (the new fields are optional in the TypedDict at runtime)

- [ ] **Step 5: Commit**

```bash
git add pipeline/agent/graph/state.py pipeline/agent/graph/workflow.py pipeline/agent/tests/test_chronicle_builder.py
git commit -m "feat(agent): add entity_id_map and relation_id_map to AgentRunState"
```

---

### Task 3: Create `resolve_entity_ids` node

**Files:**
- Create: `pipeline/agent/graph/nodes/resolve_entity_ids.py`
- Test: `pipeline/agent/tests/test_nodes_chronicle_ids.py`

- [ ] **Step 1: Write the falling test**

```python
# pipeline/agent/tests/test_nodes_chronicle_ids.py
from pipeline.agent.graph.nodes.resolve_entity_ids import resolve_entity_ids
from pipeline.agent.graph.state import AgentRunState


def test_resolve_entity_ids_returns_empty_maps_on_no_commits():
    """When nothing is committed, maps should be empty."""
    state: AgentRunState = {
        "run_id": "test",
        "raw_input": "",
        "date_hints": [],
        "parsed_events": [],
        "candidate_entities": [],
        "candidate_relations": [],
        "enriched_entities": [],
        "validation_results": [],
        "proposed_diff": None,
        "committed": [],
        "audit_log": [],
        "errors": [],
        "entity_id_map": {},
        "relation_id_map": {},
    }
    result = resolve_entity_ids(state)
    assert result["entity_id_map"] == {}
    assert result["relation_id_map"] == {}
```

- [ ] **Step 2: Run to verify it fails**

Run: `py -m pytest pipeline/agent/tests/test_nodes_chronicle_ids.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `resolve_entity_ids` node**

Create `pipeline/agent/graph/nodes/resolve_entity_ids.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone

from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.validation import AuditEvent
from pipeline.agent.tools.db import search_entity_by_name, search_relationship_by_labels


def resolve_entity_ids(state: AgentRunState) -> AgentRunState:
    """Query DB for committed entity and relation IDs after import.
    
    Populates entity_id_map (label → DB entity_id) and relation_id_map
    ("src|type|tgt" → DB relationship_id) for chronicle_builder to consume.
    """
    entity_id_map: dict[str, str] = {}
    relation_id_map: dict[str, str] = {}

    for commit in state["committed"]:
        if commit.change_type == "entity":
            # Try to find each label in the DB by exact name match
            name = commit.record.get("name", "").strip()
            if name:
                matches = search_entity_by_name(name)
                for match in matches:
                    if match.get("name", "").lower() == name.lower():
                        entity_id_map[name] = match["entity_id"]
                        break
        elif commit.change_type == "relation":
            src = commit.record.get("source_label", "").strip()
            tgt = commit.record.get("target_label", "").strip()
            rtype = commit.record.get("relationship_type", "").strip()
            if src and tgt and rtype:
                rel_key = f"{src}|{rtype}|{tgt}"
                matches = search_relationship_by_labels(src, tgt, rtype)
                for match in matches:
                    relation_id_map[rel_key] = match["relationship_id"]
                    break

    state["entity_id_map"] = entity_id_map
    state["relation_id_map"] = relation_id_map

    state["audit_log"].append(AuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        node="resolve_entity_ids",
        action="ids_resolved",
        output_summary=f"Resolved {len(entity_id_map)} entity IDs, {len(relation_id_map)} relation IDs",
    ))
    return state
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -m pytest pipeline/agent/tests/test_nodes_chronicle_ids.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/agent/graph/nodes/resolve_entity_ids.py pipeline/agent/tests/test_nodes_chronicle_ids.py
git commit -m "feat(agent): add resolve_entity_ids node for DB ID lookup"
```

---

### Task 4: Wire new node into workflow

**Files:**
- Modify: `pipeline/agent/graph/workflow.py`

- [ ] **Step 1: Add import and registration**

In `pipeline/agent/graph/workflow.py`, add the import:

```python
from pipeline.agent.graph.nodes.resolve_entity_ids import resolve_entity_ids
```

In `build_workflow()`, register node:

```python
workflow.add_node("resolve_entity_ids", resolve_entity_ids)
```

- [ ] **Step 2: Rewire edges**

Change the edge from `commit_writer → chronicle_builder` to:

```python
workflow.add_edge("commit_writer", "resolve_entity_ids")
workflow.add_edge("resolve_entity_ids", "chronicle_builder")
```

- [ ] **Step 3: Run tests to verify**

Run: `py -m pytest pipeline/agent/tests/ -q`
Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add pipeline/agent/graph/workflow.py
git commit -m "feat(agent): wire resolve_entity_ids node between commit_writer and chronicle_builder"
```

---

### Task 5: Update chronicle_builder to use DB IDs

**Files:**
- Modify: `pipeline/agent/graph/nodes/chronicle_builder.py`
- Test: `pipeline/agent/tests/test_chronicle_builder.py`

- [ ] **Step 1: Write failing test for entity_id resolution**

```python
# In test_chronicle_builder.py
def test_chronicle_builder_uses_entity_id_map():
    """Secondary entities should use DB IDs from entity_id_map."""
    state: AgentRunState = {
        "run_id": "test_3",
        "raw_input": "David IV defeated Ilghazi at Didgori.",
        "parsed_events": [
            ParsedEvent(
                label="Battle of Didgori",
                description="David IV defeated Ilghazi at Didgori.",
                start_date="1121-08-12",
                mentioned_entities=["David IV", "Ilghazi"],
            )
        ],
        "candidate_entities": [
            CandidateEntity(label="David IV", entity_type="person"),
            CandidateEntity(label="Ilghazi", entity_type="person"),
        ],
        "candidate_relations": [
            CandidateRelation(
                source_label="David IV",
                target_label="Battle of Didgori",
                relationship_type="participated_in",
            )
        ],
        "enriched_entities": [
            EnrichedCandidate(candidate=CandidateEntity(label="David IV", entity_type="person")),
            EnrichedCandidate(candidate=CandidateEntity(label="Ilghazi", entity_type="person")),
        ],
        "validation_results": [],
        "proposed_diff": None,
        "committed": [],
        "audit_log": [],
        "errors": [],
        "entity_id_map": {"David IV": "ent_david_001", "Ilghazi": "ent_ilghazi_001"},
        "relation_id_map": {},
    }
    result = chronicle_builder(state)
    entry = result["chronicle"].entries[0]
    entity_ids = [e.entity_id for e in entry.secondary_entities]
    assert "ent_david_001" in entity_ids
    assert "ent_ilghazi_001" in entity_ids
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest pipeline/agent/tests/test_chronicle_builder.py::test_chronicle_builder_uses_entity_id_map -v`
Expected: FAIL (chronicle sets entity_id=e.candidate.label, not from map)

- [ ] **Step 3: Modify `_collect_secondary_entities`**

Change function to accept `entity_id_map` and use it for resolution:

```python
def _collect_secondary_entities(event, primary_rel_id, enriched_entities, entity_id_map):
    """Collect entities mentioned in the event, resolved to DB IDs."""
    mentioned = set(e.lower() for e in event.mentioned_entities)
    return [
        ChronicleEntryEntity(
            entity_id=entity_id_map.get(e.candidate.label, e.candidate.label),
            role="participant",
        )
        for e in enriched_entities
        if e.candidate.label.lower() in mentioned
    ]
```

- [ ] **Step 4: Modify `_find_primary_relationship`**

Change to accept and use `relation_id_map`:

```python
def _find_primary_relationship(event, candidate_relations, committed, relation_id_map):
    """Find the best-matching relationship for an event.
    
    Requires BOTH source and target entities to be mentioned in the event.
    Uses relation_id_map to return real DB IDs.
    """
    mentioned = set(e.lower() for e in event.mentioned_entities)
    candidates = []

    for rel in candidate_relations:
        src_match = rel.source_label.lower() in mentioned
        tgt_match = rel.target_label.lower() in mentioned
        if src_match and tgt_match:
            priority = (
                _RELATIONSHIP_TYPE_PRIORITY.index(rel.relationship_type)
                if rel.relationship_type in _RELATIONSHIP_TYPE_PRIORITY
                else 999
            )
            candidates.append((priority, rel))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])
    best = candidates[0][1]
    rel_key = f"{best.source_label}|{best.relationship_type}|{best.target_label}"

    # Use relation_id_map first, then fall back to iterating committed
    db_id = relation_id_map.get(rel_key)
    if db_id:
        return db_id

    for commit in committed:
        commit_record = commit.record if hasattr(commit, "record") else commit
        if (
            commit_record.get("source_label") == best.source_label
            and commit_record.get("target_label") == best.target_label
            and commit_record.get("relationship_type") == best.relationship_type
        ):
            return commit_record.get("relationship_id")

    # Fallback: return the synthetic key
    return rel_key
```

- [ ] **Step 5: Update `chronicle_builder` function to pass new args**

In `chronicle_builder()`, pass the maps to both helpers:

```python
for i, event in enumerate(events):
    primary_rel_id = _find_primary_relationship(
        event,
        state["candidate_relations"],
        state["committed"],
        state["relation_id_map"],
    )
    ...
    secondary = _collect_secondary_entities(
        event,
        primary_rel_id,
        state["enriched_entities"],
        state["entity_id_map"],
    )
```

- [ ] **Step 6: Run all tests**

Run: `py -m pytest pipeline/agent/tests/ -q`
Expected: all pass (including new test)

- [ ] **Step 7: Commit**

```bash
git add pipeline/agent/graph/nodes/chronicle_builder.py pipeline/agent/tests/test_chronicle_builder.py
git commit -m "feat(agent): chronicle_builder uses DB IDs from entity_id_map/relation_id_map"
```

---

### Task 6: Verify e2e test still passes

**Files:**
- Modify: `pipeline/agent/tests/test_graph.py`

- [ ] **Step 1: Update e2e test expected result assertions**

The `test_run_agent_end_to_end` mocks the DB calls so `search_entity_by_name` returns `[]` — which means `entity_id_map` will be empty in the result. The test should still pass because `chronicle_builder` falls back to label strings. Just verify the state shape includes the new fields.

Add assertions at the end of the e2e test:

```python
assert "entity_id_map" in result
assert "relation_id_map" in result
assert isinstance(result["entity_id_map"], dict)
assert isinstance(result["relation_id_map"], dict)
```

- [ ] **Step 2: Run e2e test specifically**

Run: `py -m pytest pipeline/agent/tests/test_graph.py::test_run_agent_end_to_end -v`
Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `py -m pytest pipeline/agent/tests/ -q`
Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add pipeline/agent/tests/test_graph.py
git commit -m "test(agent): add e2e assertions for entity_id_map and relation_id_map"
```

---

### Task 7: Quick integration smoke test

- [ ] **Step 1: Run agent with the short test input**

```bash
echo "In 334 BCE, Alexander crossed into Asia Minor and defeated the Persians at the Battle of Granicus." > test_smoke.txt
py -m pipeline agent --input test_smoke.txt --run-id smoke-test-id-resolution --no-create-chronicle
```

Expected:  
- `Parsed events: 1`  
- `Committed: N` (entities + relations written to JSONL)  
- no errors  

- [ ] **Step 2: Check chronicle for DB IDs**

Read `output/agent_runs/smoke-test-id-resolution/chronicle.json` and verify:
- `primary_relationship_id` is set (not null)
- `secondary_entities.entity_id` values are meaningful

- [ ] **Step 3: Clean up**

```bash
rm test_smoke.txt
rm -rf output/agent_runs/smoke-test-id-resolution
```

- [ ] **Step 4: Run full test suite**

```bash
py -m pytest pipeline/agent/tests/ -q
```

Expected: all pass

---