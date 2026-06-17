# Chronicle Model — Design Specification

> **Status:** Design approved  
> **Date:** 2026-06-10  
> **Scope:** MVP (Phase B — read-only auto-generated chronicles). Phase A (editable curation) is deferred.

---

## 1. Goal

Introduce a **Chronicle** as a first-class narrative layer over the entity-relationship graph. A Chronicle turns a video transcript, article, or book excerpt into an ordered sequence of narrative "beats," each anchored to real database relationships and entities.

**Example:**

> **Chronicle:** *History of Alexander the Great: Conquering the World*
>
> **Beat 3 (334 BCE):** "In 334 BCE, Alexander led his army across the Hellespont into Asia Minor, fulfilling his father's dream of Persian conquest."
> - **Primary relationship:** `Alexander III → crossed → Hellespont`
> - **Secondary entities:** `Macedonia` (participant), `Asia Minor` (location), `Philip II` (mentioned)
> - **Notes:** "Arrian says 32,000 infantry; modern estimates closer to 40,000"

Core principle:

> Chronicle entries are **annotations** pinned to real database objects. Every timestamp, entity, and relationship is a reference — not a string.

---

## 2. Context

The existing Laravel API has:

- **`entities`** table: 30+ types, temporal ranges, locations, Wikidata IDs
- **`relationships`** table: 50+ directed relation types with `temporal_start`/`temporal_end`
- **`entity_timeline_entries`**: derived per-entity chronology (auto-generated)
- **No narrative/grouping model** — no `Collection`, `Topic`, or `Story` abstraction
- **Agentic pipeline**: already generates `ParsedEvent[]`, `CandidateEntity[]`, `CandidateRelation[]` from raw text

The Chronicle bridges the gap between raw pipeline output and human-readable narrative.

---

## 3. Data Model

### 3.1 `chronicles`

A Chronicle is a narrative sequence (e.g. "Alexander the Great").

| Column | Type | Notes |
|--------|------|-------|
| `chronicle_id` | UUID PK | |
| `title` | text | Human-readable title. Auto-generated from first event label if not provided; CLI `--title` overrides. |
| `slug` | text | URL-safe, unique. Generated from title via `Str::slug` + numeric suffix on collision (e.g. `alexander-the-great-2`). |
| `source_type` | enum | `video_transcript`, `article`, `book_excerpt`, `manual` |
| `source_reference` | text | File path, URL, YouTube ID, etc. Not unique — multiple chronicles may reference the same source. |
| `status` | enum | `draft`, `published`, `archived` |
| `metadata` | jsonb | Duration, word count, language, orphan_entry_count, etc. |
| `created_by` | text | `agent_pipeline` or user ID |
| `timestamps` | | `created_at`, `updated_at` |

### 3.2 `chronicle_entries`

Each entry is one "beat" in the narrative sequence.

| Column | Type | Notes |
|--------|------|-------|
| `entry_id` | UUID PK | |
| `chronicle_id` | UUID FK → `chronicles` | Cascade delete |
| `sequence_order` | int | Display order within the chronicle |
| `primary_relationship_id` | UUID FK → `relationships` | Nullable. The central action of this beat. |
| `narrative_text` | text | LLM-generated prose |
| `notes` | text | Optional editorial / research notes |
| `source_evidence` | text | Transcript line ref, timestamp, etc. |
| `generated_by` | text | `agent_pipeline` or user ID |
| `timestamps` | | `created_at`, `updated_at` |

### 3.3 `chronicle_entry_entities` (pivot)

Secondary entities mentioned in this beat.

| Column | Type | Notes |
|--------|------|-------|
| `entry_id` | UUID FK → `chronicle_entries` | |
| `entity_id` | UUID FK → `entities` | |
| `role` | enum | `participant`, `mentioned`, `location`, `outcome` |
| `sequence_in_entry` | int | Optional display order within the entry |

### 3.4 Timestamp Derivation

The entry's display timestamp is **derived at query time**, not stored:

1. `primary_relationship.temporal_start`
2. If no relationship: earliest `entity_temporal_ranges.start_year` of secondary entities
3. If neither: `null` (orphan entry, flagged for review)

This avoids duplicating temporal data and ensures consistency when relationships/entities are updated.

---

## 4. Chronicle Entry: Example

**Beat:** "Alexander crosses the Hellespont"

| Field | Value |
|-------|-------|
| `sequence_order` | 3 |
| `primary_relationship_id` | `Alexander III → crossed → Hellespont` |
| `narrative_text` | "In 334 BCE, Alexander led his army across the Hellespont into Asia Minor, fulfilling his father's dream of Persian conquest." |
| `notes` | "Arrian says 32,000 infantry; modern estimates closer to 40,000" |
| `source_evidence` | `transcript.txt:78` |

**Secondary entities:**

| Entity | Role |
|--------|------|
| `Macedonia` | participant |
| `Asia Minor` | location |
| `Philip II` | mentioned |

---

## 5. Generation Flow (Phase B — Read-Only)

```
Video transcript
  ↓
Agent pipeline (existing 11-node graph)
  ↓
ParsedEvent[] + CandidateEntity[] + CandidateRelation[]
  ↓
NEW: ChronicleBuilder node (pipeline/agent/graph/nodes/chronicle_builder.py)
  ↓
For each ParsedEvent:
  1. Find the "central" relationship
     - Highest confidence, most participants
     - Fallback: create a relationship from the event if none exists
  2. Resolve relationship ID from DB (or from newly created entities)
  3. Collect secondary entities (mentioned in event but not in primary relationship)
  4. Generate narrative_text via LLM (relationship + entities + style guide)
  5. Assign sequence_order by event temporal_start
  ↓
Write Chronicle + ChronicleEntry[] to DB
  (Duplicate chronicles allowed — `source_reference` is not unique)
  ↓
API serves chronicle with resolved relationships + entities
```

### ChronicleBuilder Node

A new LangGraph node that runs after `commit_writer`:

```python
def chronicle_builder(state: AgentRunState) -> AgentRunState:
    """Build a Chronicle from parsed events and committed entities/relations.

    Reads state["parsed_events"], state["enriched_entities"],
    state["candidate_relations"], state["committed"].
    Writes Chronicle + ChronicleEntry records to DB.
    """
```

Responsibilities:
1. Create `Chronicle` record (title from first event or user input)
2. For each `ParsedEvent`, create one `ChronicleEntry`
3. Resolve `primary_relationship_id` by matching event entities to committed relationships
4. Map secondary entities via `ChronicleEntryEntity` pivot
5. Generate `narrative_text` via LLM (prompt includes style guide + event context)

---

## 6. API Design

### REST Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/chronicles` | List chronicles (title, slug, entry count, status) |
| `GET` | `/api/v1/chronicles/{slug}` | Detail with entries ordered by `sequence_order` |
| `GET` | `/api/v1/chronicles/{slug}/entries` | Paginated entries with `primary_relationship` + `secondary_entities` eager-loaded |
| `POST` | `/api/v1/agent/chronicles` | Trigger agent pipeline + chronicle generation from transcript |

### Response Format

```json
{
  "chronicle_id": "uuid",
  "title": "History of Alexander the Great: Conquering the World",
  "slug": "alexander-the-great-conquering-the-world",
  "source_type": "video_transcript",
  "source_reference": "s3://transcripts/alexander_01.txt",
  "status": "published",
  "metadata": { "duration_seconds": 1842, "word_count": 3420 },
  "entry_count": 12,
  "entries": [
    {
      "entry_id": "uuid",
      "sequence_order": 3,
      "timestamp": "334 BCE",
      "narrative_text": "In 334 BCE, Alexander led his army across the Hellespont...",
      "notes": "Arrian says 32,000 infantry...",
      "primary_relationship": {
        "source_entity": { "entity_id": "uuid", "name": "Alexander III", "entity_type": "person" },
        "relationship_type": "crossed",
        "target_entity": { "entity_id": "uuid", "name": "Hellespont", "entity_type": "infrastructure_monument" },
        "temporal_start": "334 BCE",
        "temporal_end": null
      },
      "secondary_entities": [
        { "entity_id": "uuid", "name": "Macedonia", "entity_type": "political_entity", "role": "participant" },
        { "entity_id": "uuid", "name": "Asia Minor", "entity_type": "political_entity", "role": "location" },
        { "entity_id": "uuid", "name": "Philip II", "entity_type": "person", "role": "mentioned" }
      ]
    }
  ]
}
```

### Inertia Page — `/chronicles/{slug}`

- **Header:** title, source info, unique entity chips (all entities across entries)
- **Timeline:** vertical timeline, each entry is a card
- **Entry card:**
  - Left: derived timestamp (e.g., "334 BCE")
  - Center: narrative text
  - Right: expandable "Details" → relationship card + secondary entity chips
  - Bottom: notes (if present), source evidence tag

---

## 7. Database Migrations

Three migrations needed:

1. `create_chronicles_table`
2. `create_chronicle_entries_table`
3. `create_chronicle_entry_entities_table` (pivot)

All UUID primary keys, foreign keys with `onDelete('cascade')` or `restrict`, composite indexes on `(chronicle_id, sequence_order)` and `(entry_id, entity_id, role)`.

---

## 8. Laravel Models

### `App\Models\Chronicle`

```php
class Chronicle extends Model
{
    protected $primaryKey = 'chronicle_id';
    public $incrementing = false;
    protected $keyType = 'string';

    protected $casts = [
        'metadata' => 'array',
        'status' => ChronicleStatus::class,
        'source_type' => SourceType::class,
    ];

    public function entries(): HasMany
    {
        return $this->hasMany(ChronicleEntry::class, 'chronicle_id');
    }
}
```

### `App\Models\ChronicleEntry`

```php
class ChronicleEntry extends Model
{
    protected $primaryKey = 'entry_id';
    public $incrementing = false;
    protected $keyType = 'string';

    public function chronicle(): BelongsTo
    {
        return $this->belongsTo(Chronicle::class, 'chronicle_id');
    }

    public function primaryRelationship(): BelongsTo
    {
        return $this->belongsTo(Relationship::class, 'primary_relationship_id');
    }

    public function secondaryEntities(): BelongsToMany
    {
        return $this->belongsToMany(Entity::class, 'chronicle_entry_entities', 'entry_id', 'entity_id')
            ->withPivot('role', 'sequence_in_entry');
    }

    public function getTimestampAttribute(): ?string
    {
        // Derive from primary_relationship.temporal_start,
        // then secondary entities' earliest temporal range,
        // then null
    }
}
```

---

## 9. Phase A: Editable Chronicles (Deferred)

When ready to add curation:

- `PUT /api/v1/chronicles/{slug}/entries/{entry}/reorder` — drag-and-drop
- `PUT /api/v1/chronicles/{slug}/entries/{entry}` — edit narrative_text, notes
- `POST /api/v1/chronicles/{slug}/entries` — manually add entry
- `DELETE /api/v1/chronicles/{slug}/entries/{entry}` — remove from chronicle (doesn't delete entity/relationship)
- `chronicle_entries.edited_by`, `chronicle_entries.edited_at` fields

---

## 10. Resolved Decisions

1. **Chronicle title generation:** Auto-generate from the first event label by default. CLI `--title` overrides. If first event has no label, use the source filename.
2. **Event-to-relationship matching heuristic:**
   - Prefer relationships with types in this order: `participated_in`, `fought_at`, `caused`, `resulted_from`, `rules`, `governed_by`, `allied_with`, `at_war_with`
   - Tie-breaker: highest `confidence` value on the relationship
   - Second tie-breaker: relationship with the most participant entities
   - Fallback: temporal-nearest relationship (smallest year distance to event date)
   - If still tied, pick the first committed relationship in the batch
3. **Orphan entries:** Create with `null` timestamp. Increment `metadata.orphan_entry_count` on the Chronicle. Do not skip — the narrative may still be valuable even if temporal anchors are missing.
4. **Duplicate chronicles:** `source_reference` is **not unique**. Re-running the same transcript creates a new Chronicle. Future: add deduplication by hash of normalized transcript content.
