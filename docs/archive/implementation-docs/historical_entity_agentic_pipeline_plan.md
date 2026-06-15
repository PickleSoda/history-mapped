# Historical Entity Graph Agentic Pipeline — High-Level Implementation Plan

## 1. Goal

Build an agentic enrichment system that maps over a historical event sequence, checks whether all required historical entities and relations exist in the application database, and proposes or creates missing data in a controlled, auditable way.

The system should use **LangGraph as the main orchestrator** and use **DeepAgents only for messy/ambiguous research tasks** where deterministic logic and simple tool calls are not enough.

The core principle is:

> LLMs propose. Code validates. Humans approve uncertain changes. The database only accepts structured, validated writes.

---

## 2. Context

The existing application already has a graph-like historical entity system.

Current domain characteristics:

- Entities represent historical concepts such as:
  - person
  - country
  - city
  - event
  - war
  - battle
  - culture
  - polity
  - economy
  - place
  - and many others
- There are 70+ entity types.
- There are 30+ relation types.
- Both entities and relations are temporal.
- Entities may have:
  - `start_date`
  - `end_date`
  - point geometry for map display
  - Wikidata ID
  - Wikipedia article reference
- Some entities require special validation before creation.
  - Example: countries and cities should first be checked against an OpenHistoricalMap `map.xml` or indexed OHM source.
- The main app can expose either CLI commands or API endpoints for checking and creating data.

---

## 3. Recommended Architecture

```text
Historical event sequence input
        ↓
LangGraph orchestration workflow
        ↓
Candidate extraction
        ↓
Existing DB lookup
        ↓
Wikidata resolution
        ↓
Wikipedia resolution
        ↓
OpenHistoricalMap / geometry resolution
        ↓
Validation and confidence scoring
        ↓
Diff generation
        ↓
Human approval or auto-approval gate
        ↓
Controlled DB write
        ↓
Audit log and run summary
```

LangGraph should be responsible for the full workflow state and routing.

DeepAgents should only be called from specific LangGraph nodes when the workflow enters an ambiguous research path.

---

## 4. Core Design Decision

### Use LangGraph as the orchestrator

LangGraph should coordinate the full pipeline because the process needs:

- explicit workflow state
- predictable step order
- retries
- conditional branching
- approval gates
- clear tool boundaries
- structured outputs
- deterministic validation
- auditable results

### Use DeepAgents only for messy research

DeepAgents should be used only for tasks such as:

- disambiguating historical entities with similar names
- comparing multiple possible Wikidata matches
- resolving unclear historical polity/country/city identity
- researching uncertain relations between entities
- finding the best Wikipedia article when multiple candidates exist
- explaining why a proposed match is likely or unlikely

DeepAgents must **not** directly mutate the database.

DeepAgents should return structured JSON proposals back to LangGraph.

---

## 5. Main Services

### 5.1 Main Application API / CLI

The existing application should expose tools for the agent system.

Recommended API/CLI operations:

```text
search_entity
search_relation
get_entity_by_id
get_entity_by_wikidata_id
get_relations_for_entity
check_temporal_overlap
propose_entity
propose_relation
commit_entity
commit_relation
commit_approved_diff
reject_proposal
log_agent_run
```

The first version can expose these as CLI commands if API work is not ready.

Preferred long-term option: expose a secure internal HTTP API.

---

### 5.2 Python Agent Worker

Create a separate Python service responsible for:

- LangGraph workflow execution
- DeepAgents invocation for messy research
- Wikidata lookup
- Wikipedia lookup
- OpenHistoricalMap matching
- validation
- confidence scoring
- diff generation

Suggested structure:

```text
agent-worker/
  app/
    main.py
    graph/
      state.py
      workflow.py
      nodes/
        parse_sequence.py
        extract_candidates.py
        db_lookup.py
        wikidata_resolver.py
        wikipedia_resolver.py
        ohm_resolver.py
        validator.py
        diff_builder.py
        approval_gate.py
        commit_writer.py
        messy_research.py
    tools/
      app_api.py
      wikidata.py
      wikipedia.py
      ohm.py
    schemas/
      entities.py
      relations.py
      proposals.py
      validation.py
    deepagents/
      entity_disambiguation_agent.py
      relation_research_agent.py
      article_resolution_agent.py
    config.py
    logging.py
  tests/
```

---

### 5.3 OpenHistoricalMap Index Service

Do not make the agent parse raw `map.xml` during every run.

Instead, create an indexed representation of the OHM XML.

Recommended table or index:

```text
ohm_features
- id
- osm_type
- osm_id
- name
- alternative_names
- wikidata_id
- geometry
- start_date
- end_date
- tags_json
- source_file
- imported_at
```

Recommended operations:

```text
search_ohm_feature_by_name
search_ohm_feature_by_wikidata_id
search_ohm_feature_by_name_and_date
search_ohm_feature_by_bbox
get_ohm_feature_geometry
```

For the first version, this can be a PostGIS table populated from `map.xml`.

---

## 6. Workflow State

Define a strict LangGraph state object.

Example high-level state:

```python
class HistoricalPipelineState(TypedDict):
    run_id: str
    input_sequence: str
    parsed_events: list[ParsedEvent]
    candidate_entities: list[CandidateEntity]
    candidate_relations: list[CandidateRelation]
    existing_entities: list[ExistingEntityMatch]
    existing_relations: list[ExistingRelationMatch]
    wikidata_matches: list[WikidataMatch]
    wikipedia_matches: list[WikipediaMatch]
    ohm_matches: list[OHMMatch]
    validation_results: list[ValidationResult]
    proposed_diff: ProposedDiff
    approval_status: Literal["pending", "approved", "rejected", "partial"]
    committed_changes: list[CommittedChange]
    errors: list[PipelineError]
    audit_log: list[AuditEvent]
```

The state should be serializable.

Avoid storing huge raw documents directly in state. Store references, IDs, and compact summaries.

---

## 7. Workflow Nodes

### 7.1 `parse_sequence`

Purpose:

Convert the input historical sequence into structured event units.

Input:

```text
Historical narrative, list, timeline, markdown, JSON, or admin-provided event sequence.
```

Output:

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

Acceptance criteria:

- Produces structured events.
- Preserves dates when provided.
- Does not invent exact dates when the source is vague.
- Adds uncertainty flags when dates are unclear.

---

### 7.2 `extract_candidates`

Purpose:

Extract candidate entities and relations from parsed events.

Output should include:

- candidate entity label
- proposed entity type
- aliases
- temporal range
- source event reference
- candidate relation type
- relation direction
- relation temporal range

Example:

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
      "type": "participant_or_commander",
      "start_date": "1121-08-12",
      "end_date": "1121-08-12"
    }
  ]
}
```

Acceptance criteria:

- Outputs only allowed entity types.
- Outputs only allowed relation types.
- Marks uncertain types instead of forcing them.
- Does not write to DB.

---

### 7.3 `db_lookup`

Purpose:

Check whether candidate entities and relations already exist.

Checks:

- exact label match
- alias match
- Wikidata ID match, if known
- fuzzy match
- temporal overlap
- duplicate candidates
- relation already exists

Acceptance criteria:

- Existing entities are reused.
- Obvious duplicates are not proposed for creation.
- Ambiguous matches are routed to messy research.

---

### 7.4 `wikidata_resolver`

Purpose:

Resolve each candidate entity to a Wikidata ID.

Required output:

```json
{
  "candidate_label": "Kingdom of Georgia",
  "recommended_wikidata_id": "Q230",
  "wikidata_label": "Kingdom of Georgia",
  "description": "medieval Eurasian monarchy",
  "aliases": [],
  "instance_of": [],
  "coordinates": null,
  "start_date": "1008",
  "end_date": "1490",
  "confidence": 0.93,
  "alternatives": []
}
```

Acceptance criteria:

- Every proposed entity must have a Wikidata ID unless marked as blocked/manual-review.
- Ambiguous matches are not auto-accepted.
- Entity type must be checked against Wikidata metadata where possible.

---

### 7.5 `wikipedia_resolver`

Purpose:

Resolve Wikipedia articles for text-generation references.

Checks:

- Wikipedia sitelink from Wikidata
- preferred language article
- fallback language article
- article exists
- article title and summary match the entity

Acceptance criteria:

- Each proposed entity should have at least one Wikipedia article reference if available.
- Missing article should not always block creation, but should reduce confidence or require review depending on entity type.

---

### 7.6 `ohm_resolver`

Purpose:

Resolve geography and map display data.

Rules:

- For country, city, settlement, region, place, battlefield, route, river, or boundary-like entities, check OHM first.
- Use local OHM index generated from `map.xml`.
- Match by Wikidata ID first when available.
- Match by name + temporal overlap second.
- Match by name only as a weak fallback.
- Use Wikidata coordinates only as fallback when OHM has no match.

Acceptance criteria:

- Country/city/place-like entities should not be auto-created without geometry or a clear manual-review reason.
- OHM match confidence should account for date overlap.
- Geometry source must be stored.

---

### 7.7 `messy_research`

Purpose:

Invoke a DeepAgent only when deterministic resolution is uncertain.

Trigger examples:

- multiple Wikidata candidates with similar confidence
- no Wikidata match found
- OHM match conflicts with Wikidata
- entity type is uncertain
- relation direction is uncertain
- temporal ranges conflict
- historical naming ambiguity

DeepAgent output must be structured:

```json
{
  "task_type": "entity_disambiguation",
  "original_candidate": "Georgia",
  "recommended_result": {
    "label": "Kingdom of Georgia",
    "wikidata_id": "Q230",
    "type": "country",
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

Rules:

- DeepAgents cannot call write tools.
- DeepAgents cannot directly commit entities or relations.
- DeepAgents must return JSON matching schema.
- LangGraph must validate DeepAgent output before using it.

Acceptance criteria:

- Ambiguous cases receive a clear recommendation or are marked for human review.
- The workflow does not continue with invalid DeepAgent output.

---

### 7.8 `validator`

Purpose:

Apply deterministic business rules before a diff can be created.

Validation categories:

#### Entity validation

- allowed entity type
- required Wikidata ID
- Wikipedia article present or missing with reason
- geometry requirements by entity type
- date validity
- no duplicate entity
- source confidence above threshold

#### Relation validation

- allowed relation type
- valid source entity
- valid target entity
- temporal range valid
- temporal range compatible with both entities
- no duplicate relation
- relation direction valid

#### Geometry validation

- point geometry exists when required
- geometry source recorded
- OHM match checked for geography-sensitive types
- geometry date is compatible with entity date when available

Acceptance criteria:

- Invalid proposals are blocked.
- Uncertain proposals are routed to human review.
- Valid proposals can be included in the generated diff.

---

### 7.9 `diff_builder`

Purpose:

Create a structured proposed change set.

Example:

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

Acceptance criteria:

- Diff is human-readable and machine-readable.
- Each change includes evidence.
- Each change includes confidence and validation status.
- Diff can be committed later without rerunning the whole pipeline.

---

### 7.10 `approval_gate`

Purpose:

Decide whether changes can be committed.

Modes:

```text
manual_only
semi_auto
auto_high_confidence_only
```

Recommended initial mode:

```text
manual_only
```

Later mode:

```text
auto_high_confidence_only
```

Example rule:

```text
Auto-commit only if:
- confidence >= 0.95
- all required validators passed
- no messy research was needed
- entity type is low-risk
- relation type is low-risk
```

Acceptance criteria:

- First version does not auto-mutate DB without explicit approval.
- Approval decisions are logged.
- Rejected proposals are stored for debugging.

---

### 7.11 `commit_writer`

Purpose:

Commit approved diff to the main database using controlled API/CLI calls.

Rules:

- Writes must be idempotent.
- Writes must use DB transactions where possible.
- Writes must check for duplicates again before insert.
- Each write must include provenance metadata.

Recommended metadata:

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

Acceptance criteria:

- Approved entities and relations are created correctly.
- Duplicate inserts are prevented.
- Commit result is logged.
- Partial failures can be retried safely.

---

## 8. Entity-Type Creation Policy

Create a central policy file for entity type rules.

Example:

```yaml
person:
  requires_wikidata: true
  requires_wikipedia: true
  requires_geometry: false
  preferred_geometry_source: null
  auto_create_threshold: 0.90
  requires_human_review: false

country:
  requires_wikidata: true
  requires_wikipedia: true
  requires_geometry: true
  preferred_geometry_source: openhistoricalmap
  auto_create_threshold: 0.97
  requires_human_review: true

city:
  requires_wikidata: true
  requires_wikipedia: false
  requires_geometry: true
  preferred_geometry_source: openhistoricalmap_then_wikidata
  auto_create_threshold: 0.94
  requires_human_review: false

battle:
  requires_wikidata: true
  requires_wikipedia: true
  requires_geometry: true
  preferred_geometry_source: wikidata_or_related_place
  auto_create_threshold: 0.90
  requires_human_review: false

culture:
  requires_wikidata: true
  requires_wikipedia: true
  requires_geometry: false
  preferred_geometry_source: null
  auto_create_threshold: 0.86
  requires_human_review: true
```

This policy should be loaded by the validator, not hardcoded inside prompts.

---

## 9. Relation-Type Creation Policy

Create a central policy for relation types.

Example:

```yaml
occurred_at:
  from_types: [event, battle, war]
  to_types: [place, city, region, country]
  requires_temporal_overlap: true
  direction_locked: true
  auto_create_threshold: 0.92

participant_in:
  from_types: [person, country, army, organization]
  to_types: [event, battle, war]
  requires_temporal_overlap: true
  direction_locked: true
  auto_create_threshold: 0.90

ruler_of:
  from_types: [person]
  to_types: [country, polity, kingdom, empire]
  requires_temporal_overlap: true
  direction_locked: true
  auto_create_threshold: 0.95
  requires_human_review: true

part_of:
  from_types: [place, city, region, polity]
  to_types: [country, empire, region]
  requires_temporal_overlap: true
  direction_locked: true
  auto_create_threshold: 0.93
```

---

## 10. Tool Safety Levels

Classify tools into safe and dangerous tools.

### Safe tools

These can be called freely by LangGraph or DeepAgents:

```text
search_entity
search_relation
search_wikidata
search_wikipedia
search_ohm
get_entity
get_relation
check_temporal_overlap
build_candidate_summary
```

### Dangerous tools

These should only be called by LangGraph after validation and approval:

```text
create_entity
update_entity
create_relation
update_relation
merge_entities
delete_entity
delete_relation
commit_approved_diff
```

DeepAgents must not receive dangerous tools.

---

## 11. Data Schemas

Use strict schemas for all LLM outputs.

Recommended Python options:

- Pydantic models
- TypedDict for LangGraph state
- JSON schema validation for tool outputs

Core schemas:

```text
ParsedEvent
CandidateEntity
CandidateRelation
ExistingEntityMatch
WikidataMatch
WikipediaMatch
OHMMatch
ValidationResult
ProposedEntityCreate
ProposedRelationCreate
ProposedDiff
ApprovalDecision
CommitResult
```

---

## 12. Confidence Scoring

Create confidence scores from deterministic signals, not only LLM opinions.

Example scoring signals:

```text
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

Store both:

```text
llm_confidence
system_confidence
final_confidence
```

Use `final_confidence` for approval decisions.

---

## 13. Audit Log

Every run should produce an audit log.

Minimum audit fields:

```text
run_id
timestamp
input_sequence_hash
workflow_version
model_name
node_name
tool_called
tool_input_summary
tool_output_summary
proposal_id
validation_status
approval_status
committed_entity_ids
committed_relation_ids
errors
```

The audit log should make it possible to answer:

- Why was this entity created?
- Which source justified it?
- Which model proposed it?
- Which validators passed?
- Who approved it?
- What was the confidence score?

---

## 14. MVP Scope

The MVP should avoid overengineering.

### MVP should support

- One input historical sequence
- Candidate entity extraction
- Candidate relation extraction
- Existing DB lookup
- Wikidata resolution
- Wikipedia sitelink resolution
- Basic OHM lookup for place-like entities
- Validation rules
- Proposed diff output
- Manual approval
- Controlled commit
- Audit log

### MVP can skip

- Fully automatic creation
- complex relation inference
- bulk ingestion
- UI approval panel
- vector memory
- multi-language Wikipedia support
- advanced temporal uncertainty modeling
- automatic entity merging

---

## 15. Suggested Implementation Phases

### Phase 1 — Foundations

Tasks:

- Create Python agent worker project.
- Define Pydantic schemas.
- Define LangGraph state.
- Define entity and relation policy files.
- Create mock app API client.
- Create basic LangGraph workflow skeleton.

Deliverable:

```text
A runnable workflow that accepts a historical sequence and returns an empty structured run result.
```

---

### Phase 2 — Candidate Extraction

Tasks:

- Implement `parse_sequence` node.
- Implement `extract_candidates` node.
- Add strict structured output validation.
- Add tests with 5 historical sample sequences.

Deliverable:

```text
Input text produces candidate entities and candidate relations in valid schema.
```

---

### Phase 3 — DB Lookup Integration

Tasks:

- Expose app API or CLI for entity/relation search.
- Implement `db_lookup` node.
- Add duplicate detection.
- Add existing entity reuse logic.

Deliverable:

```text
Candidates are marked as existing, missing, duplicate, or ambiguous.
```

---

### Phase 4 — Wikidata and Wikipedia Resolution

Tasks:

- Implement Wikidata search tool.
- Implement Wikidata entity detail fetch.
- Implement Wikipedia sitelink resolver.
- Add confidence scoring from Wikidata/Wikipedia signals.

Deliverable:

```text
Missing entities are enriched with Wikidata IDs and Wikipedia article references.
```

---

### Phase 5 — OHM Index and Geometry Resolution

Tasks:

- Parse provided OHM `map.xml`.
- Import OHM features into PostGIS or local searchable index.
- Implement OHM search by Wikidata ID.
- Implement OHM search by name + date.
- Implement `ohm_resolver` node.

Deliverable:

```text
Place-like entities receive geometry candidates and geometry source metadata.
```

---

### Phase 6 — Validation and Diff Builder

Tasks:

- Implement entity validation rules.
- Implement relation validation rules.
- Implement geometry validation rules.
- Implement confidence scoring.
- Implement `diff_builder` node.

Deliverable:

```text
Workflow produces a proposed diff with create/reuse/review/blocked sections.
```

---

### Phase 7 — DeepAgents for Messy Research

Tasks:

- Create DeepAgent for entity disambiguation.
- Create DeepAgent for relation uncertainty.
- Create DeepAgent for Wikipedia/Wikidata conflict resolution.
- Add LangGraph routing to `messy_research` node.
- Ensure DeepAgent output is schema-validated.

Deliverable:

```text
Ambiguous cases are routed to DeepAgents and return structured recommendations.
```

---

### Phase 8 — Approval and Commit

Tasks:

- Implement manual approval format.
- Implement `approval_gate` node.
- Implement `commit_writer` node.
- Expose app API/CLI commit endpoint.
- Add transaction/idempotency handling.

Deliverable:

```text
Approved diffs can be committed safely to the database.
```

---

### Phase 9 — Observability and Deployment

Tasks:

- Add structured logging.
- Add run IDs.
- Add audit log storage.
- Add error and retry handling.
- Add Dockerfile.
- Deploy worker to cloud.
- Add queue/job trigger.

Deliverable:

```text
Pipeline can run as a cloud worker with observable run history.
```

---

## 16. Deployment Plan

### Simple MVP deployment

```text
Laravel app
Postgres/PostGIS
Python LangGraph worker
Redis queue
Object storage for run artifacts
```

Possible hosts:

```text
Railway
Render
Fly.io
GCP Cloud Run
AWS ECS/Fargate
```

### More robust production deployment

```text
Laravel app
Postgres/PostGIS
Python LangGraph worker
Temporal or Prefect orchestration
Object storage
OpenTelemetry logs/traces
Admin approval UI
```

Recommended production direction:

```text
LangGraph worker + Temporal + Postgres/PostGIS + Laravel internal API
```

---

## 17. Example End-to-End Flow

Input:

```text
In 1121, David IV of Georgia defeated Ilghazi at the Battle of Didgori, strengthening the Kingdom of Georgia.
```

Expected workflow result:

```text
Entities:
- David IV of Georgia: check DB, resolve Wikidata, reuse or create
- Ilghazi: check DB, resolve Wikidata, reuse or create
- Battle of Didgori: check DB, resolve Wikidata/Wikipedia, create if missing
- Kingdom of Georgia: check DB, resolve Wikidata, check OHM, create/reuse
- Didgori: check DB, resolve geometry, create/reuse

Relations:
- David IV participated_in / commanded Battle of Didgori
- Ilghazi participated_in / commanded opposing side in Battle of Didgori
- Battle of Didgori occurred_at Didgori
- Battle of Didgori involved Kingdom of Georgia
```

Expected output:

```text
Proposed diff:
- reused existing entities
- entities to create
- relations to create
- uncertain items requiring review
- blocked items with reasons
```

---

## 18. Rules for the Coding Agent

The implementation agent should follow these rules:

1. Do not let any LLM or DeepAgent directly write to the database.
2. All LLM outputs must be validated against schemas.
3. All creation should go through a proposed diff first.
4. Dangerous write tools should only be available to the LangGraph commit node.
5. DeepAgents should only be used for ambiguous research.
6. Every proposed entity should have a Wikidata ID unless blocked/manual-review.
7. Geography-sensitive entities should check OHM before falling back to Wikidata coordinates.
8. Every proposed change should include evidence and confidence score.
9. Every workflow run should produce an audit log.
10. The MVP should prioritize correctness and inspectability over full automation.

---

## 19. Acceptance Criteria for First Working Version

The first working version is complete when:

- A historical sequence can be submitted.
- LangGraph executes the full pipeline.
- Candidate entities and relations are extracted.
- Existing DB entities/relations are checked.
- Missing entities are resolved through Wikidata.
- Wikipedia article references are attached where available.
- Place-like entities are checked against OHM index.
- A structured diff is produced.
- Invalid proposals are blocked.
- Ambiguous proposals are marked for review or routed to DeepAgents.
- Approved proposals can be committed through controlled app API/CLI calls.
- Every run has an audit log.

---

## 20. Non-Goals for First Version

Do not implement these in the first version unless required:

- fully autonomous bulk ingestion
- automatic entity merging
- automatic deletion
- complex geopolitical boundary reconstruction
- full admin UI
- multi-agent debate
- vector memory
- self-improving agent behavior
- model fine-tuning
- multilingual article generation

---

## 21. Final Recommended Implementation Direction

Build this as:

```text
LangGraph = workflow orchestrator
DeepAgents = optional messy research helpers
Laravel API/CLI = source of truth and write boundary
Postgres/PostGIS = entity graph and OHM geometry index
Wikidata/Wikipedia/OHM = external evidence sources
Human approval = safety gate for uncertain history
```

The system should behave less like an autonomous chatbot and more like a controlled historical data-enrichment pipeline.

The ideal outcome is not that the agent creates everything automatically. The ideal outcome is that it produces a clean, explainable, reviewable diff that makes historical graph expansion much faster while keeping the database trustworthy.
