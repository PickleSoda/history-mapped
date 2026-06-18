# Historical Entity Agentic Pipeline — Design Spec

> **Status:** Design approved — ready for implementation plan
> **Date:** 2026-06-09

---

## 1. Goal

Build an agentic enrichment system that accepts raw historical text (video transcripts, articles, book excerpts) and produces structured, validated entity and relation proposals that can be auto-committed or flagged for human review.

The system uses **LangGraph as the orchestrator** and **existing pipeline modules as deterministic tools**.

Core principle:

> LLMs propose. Code validates. Humans approve uncertain changes. The database only accepts structured, validated writes.

---

## 2. Context

The existing application already has a graph-like historical entity system:

- 30+ entity types (political_entity, person, event_battle, city, etc.)
- 76+ relation types (rules, participated_in, part_of, caused, etc.)
- Both entities and relations are temporal
- Entities have: `start_date`, `end_date`, point geometry, Wikidata ID, Wikipedia reference
- Import is file-based: Python writes JSONL artifacts, Laravel artisan commands import them

### Existing Pipeline Modules (Reused)

| Module | Purpose | Reused By Agentic Node |
|--------|---------|------------------------|
| `pipeline/wikidata/scraper/wikidata.py` | Batched SPARQL queries, QID enrichment | `resolve_wikidata` |
| `pipeline/wikidata/scraper/wikipedia.py` | Summary extraction, sitelink resolution | `resolve_wikidata` |
| `pipeline/wikidata/dedup/deduplicator.py` | QID match, fuzzy name + temporal dedup, DB check | `db_lookup` |
| `pipeline/ohm_collections/xml_lookup.py` | OHM SQLite index: search by name, QID, tags | `resolve_ohm` |
| `pipeline/ohm_collections/point_resolver.py` | Best-point geometry resolution | `resolve_ohm` |
| `pipeline/ohm_collections/entity_enricher.py` | Wikidata metadata merge, geo resolution | `resolve_wikidata`, `resolve_ohm` |
| `pipeline/wikidata/mapper/relationship_mapper.py` | Wikidata property → relationship_type mapping | `resolve_wikidata` |
| `pipeline/wikidata/mapper/type_configs.py` | Entity-type → Wikidata class mappings | `validate`, `extract_candidates` |
| `pipeline/config.py` | Settings, env loading | All nodes |

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Input: Raw historical text                                 │
│  e.g., video transcript, Wikipedia article, book excerpt    │
│       "In 1121, David IV of Georgia defeated Ilghazi..."    │
└─────────────────────────┬───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  LangGraph Orchestrator  (NEW: pipeline/agent/)             │
│  ─────────────────────                                     │
│  Nodes:                                                    │
│    1. parse_sequence     → raw text → structured events     │
│    2. extract_candidates → events → entities/relations      │
│    3. db_lookup          → check existing DB entities       │
│    4. resolve_wikidata   → enrich with QIDs/metadata        │
│    5. resolve_ohm        → geometry for place-like entities │
│    6. generate_content   → AI: summaries + descriptions     │
│                            from style guide                 │
│    7. validate           → policy + confidence scoring      │
│    8. build_diff         → structured proposed_diff.json    │
│    9. approval_gate      → auto-commit high-conf, flag rest │
│   10. commit_writer      → write to DB via artisan commands │
│   11. audit_logger       → run manifest with decisions      │
└─────────────────────────┬───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  Deterministic Tool Layer  (EXISTING pipeline modules)      │
│  ────────────────────────                                  │
│  • pipeline/wikidata/scraper/  → wikidata_search, enrich   │
│  • pipeline/wikidata/dedup/    → db_lookup, fuzzy_match    │
│  • pipeline/ohm_collections/   → xml_lookup, point_resolver│
│  • pipeline/wikidata/mapper/   → relationship_mapper       │
│  • pipeline/config.py          → settings, type configs    │
└─────────────────────────┬───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  Output Artifacts                                           │
│  output/agent_runs/<run_id>/                                │
│    ├── manifest.json           (run metadata + audit log)   │
│    ├── parsed_events.json      (intermediate, inspectable)  │
│    ├── proposed_diff.json      (create / review / blocked)  │
│    ├── entities_to_create.jsonl (importer-ready)            │
│    └── relations_to_create.jsonl                            │
└─────────────────────────────────────────────────────────────┘
```

**Key principle:** LangGraph never directly scrapes Wikidata or parses XML. It calls wrapped tool functions that delegate to existing, tested modules.

---

## 4. Node Descriptions

### 4.1 `parse_sequence`

**Purpose:** Convert raw historical text into structured event units.

**Input:** Raw text (transcript, article, etc.)

**Output:**
```json
{
  "events": [
    {
      "label": "Battle of Didgori",
      "description": "David IV defeats Ilghazi near Didgori.",
      "start_date": "1121-08-12",
      "end_date": "1121-08-12",
      "mentioned_entities": ["David IV", "Ilghazi", "Kingdom of Georgia", "Didgori"]
    }
  ]
}
```

**Rules:**
- Preserve dates when provided.
- Do not invent exact dates when the source is vague.
- Add uncertainty flags when dates are unclear.
- Events should be ordered sequentially as they appear in the text.

---

### 4.2 `extract_candidates`

**Purpose:** Extract candidate entities and relations from parsed events.

**Output:**
```json
{
  "candidate_entities": [
    {
      "label": "David IV of Georgia",
      "type": "person",
      "start_date": null,
      "end_date": null,
      "source_event": "Battle of Didgori"
    }
  ],
  "candidate_relations": [
    {
      "from": "David IV of Georgia",
      "to": "Battle of Didgori",
      "type": "participated_in",
      "start_date": "1121-08-12",
      "end_date": "1121-08-12"
    }
  ]
}
```

**Rules:**
- Output only allowed entity types (from `api/app/Enums/EntityType.php`). Use exact enum values: `political_entity`, `person`, `event_battle`, `city`, etc.
- Output only allowed relation types (from `api/app/Enums/RelationshipType.php`). Use exact enum values: `participated_in`, `rules`, `part_of`, etc.
- Mark uncertain types instead of forcing them.
- Do not write to DB.

---

### 4.3 `db_lookup`

**Purpose:** Check whether candidate entities and relations already exist.

**Checks:**
- Exact label match
- Alias match
- Wikidata ID match, if known
- Fuzzy match (via `Deduplicator`)
- Temporal overlap
- Duplicate candidates

**Output:** Candidates marked as `existing`, `missing`, `duplicate`, or `ambiguous`.

---

### 4.4 `resolve_wikidata`

**Purpose:** Resolve each candidate entity to a Wikidata ID.

**Required output:**
```json
{
  "candidate_label": "Kingdom of Georgia",
  "recommended_wikidata_id": "Q230",
  "wikidata_label": "Kingdom of Georgia",
  "description": "medieval Eurasian monarchy",
  "aliases": [],
  "coordinates": null,
  "start_date": "1008",
  "end_date": "1490",
  "confidence": 0.93,
  "alternatives": []
}
```

**Rules:**
- Every proposed entity must have a Wikidata ID unless marked as blocked/manual-review.
- Ambiguous matches are not auto-accepted.
- Entity type must be checked against Wikidata metadata where possible.

---

### 4.5 `resolve_ohm`

**Purpose:** Resolve geography and map display data.

**Rules:**
- For `political_entity`, `city`, `infrastructure_monument`, `event_battle`, `trade_route`, and other geography-sensitive types, check OHM first.
- Use local OHM index (`xml_lookup.py`, `point_resolver.py`).
- Match by Wikidata ID first when available.
- Match by name + temporal overlap second.
- Match by name only as a weak fallback.
- Use Wikidata coordinates only as fallback when OHM has no match.

**Output:** GeoJSON Point geometry stored as `fallback_geojson` (dict) in the candidate record. The existing Laravel `ImportEntityJob` attaches this via `EntityGeoRef` / `EntityLocation` related tables. The `Entity` model itself has no direct geometry column.

---

### 4.6 `generate_content`

**Purpose:** Generate flowing, narrative entity summaries and relation descriptions using a style guide.

**Input:** Event sequence context + entity metadata (name, type, dates, Wikidata description) + relation candidates

**Output:**
- Entity `summary`: flowing prose, e.g. *"David IV, known as the Builder, ruled the Kingdom of Georgia from 1089 to 1125 and led the decisive victory at the Battle of Didgori in 1121."*
- Relation `description`: directional and specific, e.g. *"David IV commanded the Georgian forces at the Battle of Didgori on August 12, 1121."*

**Style guide (`pipeline/agent/style_guide.md`):**
- Tone: encyclopedic but narrative
- Entity summaries: 1–2 sentences, include temporal scope and significance
- Relation descriptions: directional, include temporal qualifier, avoid passive voice
- Always mention the event/period when describing a relation
- Do not repeat the entity's own name in its summary
- Cross-reference style: mention connected entities naturally, not as dry links

---

### 4.7 `validate`

**Purpose:** Apply deterministic business rules before a diff can be created.

**Entity validation:**
- Allowed entity type
- Required Wikidata ID
- Date validity
- No duplicate entity
- Source confidence above threshold

**Relation validation:**
- Allowed relation type
- Valid source/target entities
- Temporal range valid (`start_date`/`end_date` as ISO strings, mapped to `temporal_start`/`temporal_end` DB columns; `start_year`/`end_year` derived as integers)
- No duplicate relation
- Relation direction valid

**Geometry validation:**
- Point geometry exists when required (for geography-sensitive types)
- Geometry source recorded
- OHM match checked for geography-sensitive types

---

### 4.8 `build_diff`

**Purpose:** Create a structured proposed change set.

**Output:**
```json
{
  "run_id": "run_123",
  "summary": {
    "entities_to_create": 3,
    "relations_to_create": 5,
    "entities_reused": 4,
    "requires_review": 2
  },
  "create_entities": [],
  "create_relations": [],
  "review_items": [],
  "blocked_items": []
}
```

---

### 4.9 `approval_gate`

**Purpose:** Decide whether changes can be committed.

**Modes:**
- `manual_only` — flag everything for review
- `semi_auto` — auto-commit high confidence, flag rest
- `auto_high_confidence_only` — auto-commit only if all criteria met

**Initial mode:** `semi_auto`

**Auto-commit rules:**
```
Auto-commit if:
  - confidence >= 0.95
  - all validators passed
  - entity type risk_level is low (per policy in §9)
  - relation type risk_level is low (per policy in §10)
  - confidence >= entity_type.auto_commit_threshold
  - confidence >= relation_type.auto_commit_threshold

Flag for review if:
  - confidence < 0.95
  - entity type risk_level is high or medium
  - relation type risk_level is high or medium
  - confidence < entity_type.auto_commit_threshold
  - confidence < relation_type.auto_commit_threshold
  - any validator flagged a warning
```

> The approval gate loads risk policies from §9 and §10 at runtime. No hardcoded type lists.

---

### 4.10 `commit_writer`

**Purpose:** Commit approved diff to the database.

**Rules:**
- Writes must be idempotent.
- Writes must check for duplicates again before insert.
- Each write must include provenance metadata.
- The agent writes approved entities and relations to temporary JSONL files, then invokes existing Laravel artisan batch commands:
  - `php artisan pipeline:import <entities.jsonl> --sync --batch-id=<run_id>`
  - `php artisan pipeline:import-border-relations <relations_dir> --sync --batch-id=<run_id>`
  - `php artisan pipeline:resolve-relationships <run_id> --sync`
- This preserves the existing file-based import pattern and keeps the Python agent decoupled from DB writes.

**Provenance metadata:**
```json
{
  "created_by": "historical-agent-pipeline",
  "run_id": "run_123",
  "source_sequence_id": "seq_456",
  "wikidata_id": "Q230",
  "wikipedia_url": "...",
  "geometry_source": "openhistoricalmap",
  "confidence": 0.96,
  "approval_user_id": "admin_1"
}
```

> **Note:** Provenance fields (`run_id`, `source_sequence_id`) are stored inside the `source_citations` JSONB column on the `Entity` and `EntityRelationship` models. The existing schema does not require migration.

---

### 4.11 `messy_research` (conditional node) — Post-MVP

**Purpose:** Invoke a DeepAgent only when deterministic resolution is uncertain.

**Status:** Deferred to post-MVP. The MVP handles ambiguity by routing to `approval_gate` review items.

**Trigger examples (for future implementation):**
- Multiple Wikidata candidates with similar confidence
- No Wikidata match found
- OHM match conflicts with Wikidata
- Entity type is uncertain
- Relation direction is uncertain

**Invocation mechanism (future):**
- Implemented as a separate LangGraph subgraph with a restricted tool list (read-only).
- The subgraph receives the ambiguous candidate + context, calls safe tools (search only), and returns structured JSON.
- The parent graph validates the output schema before accepting the recommendation.

**DeepAgent output:**
```json
{
  "task_type": "entity_disambiguation",
  "original_candidate": "Georgia",
  "recommended_result": {
    "label": "Kingdom of Georgia",
    "wikidata_id": "Q230",
    "type": "political_entity",
    "confidence": 0.91
  },
  "alternatives": [
    {
      "label": "Georgia",
      "wikidata_id": "Q230",
      "reason_rejected": "Modern country, not correct for the provided medieval date range."
    }
  ],
  "reasoning_summary": "The input date range and event context point to the medieval Kingdom of Georgia rather than the modern state.",
  "requires_human_review": false
}
```

**Rules:**
- DeepAgents cannot call write tools.
- DeepAgents cannot directly commit entities or relations.
- DeepAgents must return JSON matching schema.
- LangGraph must validate DeepAgent output before using it.
- Sets `deep_agent_invoked: true` in state when triggered.

---

### 4.12 `audit_logger`

**Purpose:** Produce an audit log for every run.

**Minimum audit fields:**
- `run_id`
- `timestamp`
- `input_sequence_hash`
- `workflow_version`
- `model_name`
- `node_name`
- `tool_called`
- `tool_input_summary`
- `tool_output_summary`
- `proposal_id`
- `validation_status`
- `approval_status`
- `committed_entity_ids`
- `committed_relation_ids`
- `errors`

---

## 5. State Model

```python
class AgentRunState(TypedDict):
    run_id: str
    raw_input: str
    parsed_events: list[ParsedEvent]
    candidates: list[Candidate]
    existing_matches: list[ExistingMatch]
    enriched: list[EnrichedCandidate]
    validation_results: list[ValidationResult]
    proposed_diff: ProposedDiff
    committed: list[CommittedChange]
    audit_log: list[AuditEvent]
    errors: list[PipelineError]
```

The state is serializable to JSON for audit and resumability.

---

## 6. Confidence Scoring

Create confidence scores from deterministic signals, not only LLM opinions.

**Scoring signals:**
```
+ exact Wikidata label match
+ alias match
+ Wikipedia sitelink exists
+ entity type matches expected type
+ date range overlaps event date
+ OHM feature has matching Wikidata ID
+ OHM feature has temporal overlap
+ existing DB duplicate not found
- multiple Wikidata candidates
- no Wikipedia article
- no geometry for geography-sensitive entity
- temporal conflict
- label is ambiguous
- DeepAgent required
```

**Stored scores:**
- `llm_confidence` — LLM's self-reported confidence (float, 0.0–1.0)
- `system_confidence` — computed from signals above (float, 0.0–1.0)
- `final_confidence` — weighted combination, used for approval decisions (float, 0.0–1.0)

**Database mapping:** The existing `Entity` and `EntityRelationship` models use a `ConfidenceLevel` enum (`very_low`, `low`, `medium`, `high`, `very_high`). The agent stores the float `final_confidence` inside the `source_citations` JSONB provenance field. The Laravel import layer maps the float to the enum when creating the record. This avoids a DB schema migration for the MVP.

Example mapping:
| float range | ConfidenceLevel |
|---|---|
| 0.00–0.20 | very_low |
| 0.21–0.40 | low |
| 0.41–0.60 | medium |
| 0.61–0.80 | high |
| 0.81–1.00 | very_high |

---

## 7. Tool Safety Levels

### Safe tools (LangGraph + DeepAgents)
- `search_entity`
- `search_relation`
- `search_wikidata`
- `search_wikipedia`
- `search_ohm`
- `get_entity`
- `get_relation`
- `check_temporal_overlap`
- `build_candidate_summary`

### Dangerous tools (LangGraph commit node only)
- `create_entity`
- `update_entity`
- `create_relation`
- `update_relation`
- `merge_entities`
- `delete_entity`
- `delete_relation`
- `commit_approved_diff`

DeepAgents must not receive dangerous tools.

---

## 8. File Structure (New)

```
pipeline/agent/
├── __init__.py
├── __main__.py              # CLI entry: py -m pipeline agent
├── config.py                # Agent-specific settings (models, thresholds)
├── style_guide.md           # Content generation style guide (deliverable)
├── graph/
│   ├── __init__.py
│   ├── state.py             # TypedDict state definitions
│   ├── workflow.py          # LangGraph workflow builder
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
│       └── messy_research.py   # stub for post-MVP
├── tools/
│   ├── __init__.py
│   ├── app_api.py           # Laravel artisan command wrappers
│   ├── wikidata.py          # Wraps existing scraper modules
│   ├── wikipedia.py         # Wraps existing scraper modules
│   ├── ohm.py               # Wraps xml_lookup, point_resolver
│   └── db.py                # DB search, dedup wrappers
├── schemas/
│   ├── __init__.py
│   ├── entities.py          # Pydantic: ParsedEvent, Candidate, EnrichedCandidate
│   ├── relations.py         # Pydantic: CandidateRelation, CommittedChange
│   ├── proposals.py         # Pydantic: ProposedDiff, ApprovalDecision
│   └── validation.py        # Pydantic: ValidationResult, PipelineError
├── deepagents/
│   ├── __init__.py
│   ├── entity_disambiguation_agent.py   # stub for post-MVP
│   └── relation_research_agent.py       # stub for post-MVP
└── tests/
    ├── __init__.py
    ├── test_graph.py
    ├── test_nodes.py
    └── test_tools.py
```

**CLI integration:** Register the `agent` subcommand in the root `pipeline/__main__.py` CLI dispatcher alongside existing `wikidata`, `ohm_borders`, and `ohm_collections` subcommands.

---

## 9. Entity-Type Risk Policy

Derived from existing `api/app/Enums/EntityType.php`. Loaded by the validator, not hardcoded in prompts.

```yaml
person:
  risk_level: high
  requires_wikidata: true
  requires_geometry: false
  auto_commit_threshold: 0.97

political_entity:
  risk_level: high
  requires_wikidata: true
  requires_geometry: true
  preferred_geometry_source: openhistoricalmap
  auto_commit_threshold: 0.97

city:
  risk_level: medium
  requires_wikidata: true
  requires_geometry: true
  preferred_geometry_source: openhistoricalmap_then_wikidata
  auto_commit_threshold: 0.94

event_battle:
  risk_level: low
  requires_wikidata: true
  requires_geometry: true
  preferred_geometry_source: wikidata_or_related_place
  auto_commit_threshold: 0.90
```

---

## 10. Relation-Type Risk Policy

Derived from existing `api/app/Enums/RelationshipType.php`.

```yaml
participated_in:
  risk_level: low
  from_types: [person, political_entity, military_unit]
  to_types: [event_battle, event_war, event_treaty]
  auto_commit_threshold: 0.90

rules:
  risk_level: high
  from_types: [person]
  to_types: [political_entity, dynasty]
  auto_commit_threshold: 0.97

at_war_with:
  risk_level: high
  from_types: [political_entity]
  to_types: [political_entity]
  auto_commit_threshold: 0.95
```

---

## 11. MVP Scope

### Included
- One input historical text
- LLM-powered event parsing
- Candidate entity and relation extraction
- Existing DB lookup
- Wikidata resolution
- Wikipedia sitelink resolution
- Basic OHM lookup for place-like entities
- AI-generated descriptions (style guide)
- Validation rules
- Confidence scoring
- Proposed diff output
- Semi-auto approval gate
- Controlled commit via artisan commands
- Audit log

### Excluded (future work)
- Fully automatic creation
- Complex relation inference beyond explicit mentions
- Bulk ingestion
- UI approval panel
- Vector memory
- Multi-language Wikipedia support
- Advanced temporal uncertainty modeling
- Automatic entity merging

---

## 12. Example End-to-End Flow

**Input:**
```
In 1121, David IV of Georgia defeated Ilghazi at the Battle of Didgori,
strengthening the Kingdom of Georgia.
```

**Expected workflow result:**
```
Entities:
- David IV of Georgia: check DB, resolve Wikidata, generate summary, reuse or create
- Ilghazi: check DB, resolve Wikidata, generate summary, reuse or create
- Battle of Didgori: check DB, resolve Wikidata/Wikipedia, generate summary, create if missing
- Kingdom of Georgia: check DB, resolve Wikidata, check OHM, generate summary, create/reuse
- Didgori: check DB, resolve geometry, create/reuse

Relations:
- David IV participated_in Battle of Didgori
- Ilghazi participated_in Battle of Didgori
- Battle of Didgori fought_at Didgori
- Kingdom of Georgia participated_in Battle of Didgori
```

**Expected output:**
```
Proposed diff:
- reused existing entities: 2
- entities to create: 3
- relations to create: 4
- uncertain items requiring review: 1 (Ilghazi — ambiguous Wikidata match)
- blocked items: 0
```

---

## 13. Non-Goals

Do not implement in the first version:
- Fully autonomous bulk ingestion
- Automatic entity merging
- Automatic deletion
- Complex geopolitical boundary reconstruction
- Full admin UI
- Multi-agent debate
- Vector memory
- Self-improving agent behavior
- Model fine-tuning
- Multilingual article generation

---

## 14. Acceptance Criteria

The first working version is complete when:
- A historical text can be submitted.
- LangGraph executes the full pipeline.
- Candidate entities and relations are extracted.
- Existing DB entities/relations are checked.
- Missing entities are resolved through Wikidata.
- Wikipedia article references are attached where available.
- Place-like entities are checked against OHM index.
- AI-generated summaries and descriptions follow the style guide.
- A structured diff is produced.
- Invalid proposals are blocked.
- Ambiguous proposals are marked for review or routed to DeepAgents.
- Approved proposals can be committed through controlled artisan commands.
- Every run has an audit log.

---

## 15. Dependencies

Add to `pipeline/requirements.txt`:
```
langgraph>=0.2.0
langchain>=0.2.0
langchain-openai>=0.1.0
```

These are new dependencies. The existing `openai` package (used by `scraper/wikipedia.py` for summaries) remains separate.

---

## 16. Testing Strategy

### LLM-dependent nodes (`parse_sequence`, `extract_candidates`, `generate_content`)
- Mock LLM responses using `unittest.mock.patch` on the LangGraph node's LLM client.
- Store realistic mock responses in `tests/fixtures/llm_responses/` as JSON files.
- Each node test loads the fixture, patches the LLM call, and asserts the output schema is correct.
- Do not hit live LLM APIs in CI.

### Deterministic nodes (`db_lookup`, `resolve_wikidata`, `resolve_ohm`, `validate`, `build_diff`)
- Standard pytest unit tests with real tool calls where feasible (local SQLite OHM index, test DB).
- Use `pytest-vcr` or `responses` library to record Wikidata/Wikipedia HTTP calls.

### Integration tests
- End-to-end: run the full graph with mocked LLM on a sample transcript, assert the final `proposed_diff` matches expected shape.

---

## 17. Open Questions

1. Should `generate_content` use the same OpenAI model as `parse_sequence`/`extract_candidates`, or a different one optimized for prose?
2. Should the style guide be editable per-project or per-run, or is a single repo-level guide sufficient?
3. Should flagged-for-review items be stored in a new DB table (`agent_review_queue`) or remain file-only?
4. In `semi_auto` mode, what user ID should be attributed to auto-committed records? Use a system user (e.g., `user_id: "agent-pipeline"`) or require an admin config.
