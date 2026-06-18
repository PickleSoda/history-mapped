# Chronicle ID Resolution Design

## Problem

The agent pipeline produces entities, relations, and a chronicle — but the chronicle references entities by **string labels** (e.g. `"Alexander the Great"`) instead of **database IDs** (e.g. `"ent_abc123"`). The import commands (`pipeline:import`) create entities in the DB, but `chronicle_builder` never queries the DB to get the real IDs back.

Additionally:
- Entities with `wikidata_id: null` skip import silently if `entity_group` is missing (fixed in previous session)
- The `died_in` relation with self-referencing source==target (e.g. "Alexander|died_in|Alexander") blocks validation
- Chronicled entries default to `"Alexander|fought_at|Darius III"` because `_find_primary_relationship` matched on **either** entity mentioned instead of **both**

## Solution

### Architecture

Insert a new `resolve_entity_ids` node between `commit_writer` and `chronicle_builder` that:

1. After entities/relations are committed to the DB, queries the DB to get back real `entity_id` and `relationship_id` values
2. Builds lookup maps: `label → entity_id` and `"src|type|tgt" → relationship_id`
3. `chronicle_builder` consumes these maps instead of relying on labels

### Data Flow

```
commit_writer → resolve_entity_ids → chronicle_builder → chronicle_writer
```

**commit_writer**: Writes JSONL files, runs artisan commands (no change to flow)
**resolve_entity_ids** (NEW): Queries committed entities and relations from DB, populates `entity_id_map` and `relation_id_map`
**chronicle_builder**: Uses maps to resolve labels to DB IDs before building chronicle entries
**chronicle_writer**: Writes chronicle JSON with real DB IDs (no change needed)

### State Changes

Two new fields in `AgentRunState`:
```python
entity_id_map: dict[str, str]    # label → DB entity_id (e.g. "Alexander the Great" → "ent_abc123")
relation_id_map: dict[str, str]  # "src|type|tgt" → DB relationship_id (e.g. "Alexander|fought_at|Darius" → "rel_xyz789")
```

### chronicle_builder Changes

- `_find_primary_relationship`: already requires BOTH entities mentioned (fixed). Now looks up `relation_id_map` instead of iterating `committed` list.
- `_collect_secondary_entities`: resolves `entity_id` through `entity_id_map` instead of using `e.candidate.label`.
- Falls back to label string if map lookup fails (graceful degradation).

### Relation Import

Currently relations go through `pipeline:import-borders` which creates border entities, not relationship records. Need to verify this is the correct command for the relationship types the agent produces. If not, may need to use `pipeline:import-border-relations` or create a new import path.

### Wikidata Handling

Wikidata SPARQL timeout/retry already fixed (30s timeout, exponential backoff). When Wikidata is unreachable, entities pass validation with base confidence 0.95 but lack `wikidata_id`. The DB import will skip these entities if `entity_group` is present (which is now fixed). No blocker.

### Geometry

OHM geometry resolution is best-effort. When OHM has a match, `geojson` is included in the entity record and imported. When no match, geometry field is null. The chronicle doesn't depend on geometry — it only needs entity IDs.

## Files to Modify

| File | Change |
|------|--------|
| `pipeline/agent/graph/state.py` | Add `entity_id_map`, `relation_id_map` fields |
| `pipeline/agent/graph/workflow.py` | Register `resolve_entity_ids` node, add edges |
| `pipeline/agent/graph/nodes/resolve_entity_ids.py` | CREATE: new node for DB ID lookup |
| `pipeline/agent/graph/nodes/chronicle_builder.py` | Use `entity_id_map`/`relation_id_map` instead of labels |
| `pipeline/agent/tools/db.py` | Add `search_relationship_by_labels()` function |
| `pipeline/agent/tests/test_graph.py` | Update e2e mock to include entity_id_map/relation_id_map |
| `pipeline/agent/tests/test_chronicle_builder.py` | Update state fixtures to include new fields |

## Success Criteria

1. Entities committed to DB have real `entity_id` that appears in chronicle
2. Relationship IDs in chronicle are real DB IDs, not synthetic strings
3. Orphan count drops (events with too-few mentioned entities still orphaned)
4. Self-referencing relations (source==target) are rejected at validation
5. All existing tests still pass