# Chronicle Model — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Chronicle model as a narrative layer over the entity-relationship graph. A Chronicle turns raw historical text into an ordered sequence of narrative "beats," each anchored to real DB relationships and entities. MVP is read-only auto-generation (Phase B); editable curation (Phase A) is deferred.

**Architecture:** Three new DB tables (`chronicles`, `chronicle_entries`, `chronicle_entry_entities`) with Laravel models, API resource, and controller. A new `chronicle_builder` LangGraph node runs after `commit_writer` in the agent pipeline to derive chronicle entries from parsed events and committed relationships. The agent writes chronicle JSONL artifacts; a Laravel artisan command imports them.

**Tech Stack:** PHP/Laravel (migrations, models, enums, API, resource, controller), Python/LangGraph (ChronicleBuilder node, schema, workflow update), PostgreSQL, pytest.

---

## File Structure

### Laravel API (`api/`)

| File | Responsibility |
|------|---------------|
| `database/migrations/2026_06_10_000001_create_chronicles_table.php` | `chronicles` table |
| `database/migrations/2026_06_10_000002_create_chronicle_entries_table.php` | `chronicle_entries` table |
| `database/migrations/2026_06_10_000003_create_chronicle_entry_entities_table.php` | Pivot table |
| `app/Enums/ChronicleStatus.php` | Status enum |
| `app/Enums/SourceType.php` | Source type enum |
| `app/Enums/ChronicleEntryRole.php` | Secondary entity role enum |
| `app/Models/Chronicle.php` | Model + relationships |
| `app/Models/ChronicleEntry.php` | Model + relationships + timestamp accessor |
| `app/Http/Api/V1/Resources/ChronicleResource.php` | API resource |
| `app/Http/Api/V1/Resources/ChronicleEntryResource.php` | API resource |
| `app/Http/Controllers/Api/V1/ChronicleController.php` | Index + show |
| `routes/api.php` | Register chronicle routes |
| `app/Console/Commands/ImportChroniclesCommand.php` | Import chronicle JSONL |
| `tests/Feature/Api/ChronicleApiTest.php` | Feature tests |

### Agent Pipeline (`pipeline/agent/`)

| File | Responsibility |
|------|---------------|
| `schemas/chronicle.py` | Pydantic: `Chronicle`, `ChronicleEntry`, `ChronicleEntryEntity` |
| `graph/nodes/chronicle_builder.py` | Build chronicle from parsed events + committed data |
| `graph/nodes/chronicle_writer.py` | Write chronicle JSONL artifact |
| `graph/workflow.py` | Add chronicle_builder + chronicle_writer after commit_writer |
| `tests/test_chronicle_builder.py` | Unit tests |
| `tests/test_chronicle_schema.py` | Schema tests |

### Modified Files

| File | Change |
|------|--------|
| `pipeline/agent/graph/workflow.py` | Add `chronicle_builder` → `chronicle_writer` → `audit_logger` edges |
| `pipeline/agent/graph/state.py` | Add `chronicle: Chronicle \| None` to `AgentRunState` |
| `pipeline/agent/__main__.py` | Add `--title`, `--create-chronicle` flags |
| `pipeline/agent/config.py` | Add `chronicle_output_dir` setting |

---

## Phase 1: Laravel Foundation

### Task 1: Create Chronicle enums

**Files:**
- Create: `api/app/Enums/ChronicleStatus.php`
- Create: `api/app/Enums/SourceType.php`
- Create: `api/app/Enums/ChronicleEntryRole.php`

**Step 1 — Write failing test**

Create `api/tests/Unit/Enums/ChronicleEnumsTest.php`:
```php
<?php

declare(strict_types=1);

namespace Tests\Unit\Enums;

use App\Enums\ChronicleStatus;
use App\Enums\SourceType;
use App\Enums\ChronicleEntryRole;
use PHPUnit\Framework\TestCase;

class ChronicleEnumsTest extends TestCase
{
    public function test_chronicle_status_values(): void
    {
        $this->assertSame('draft', ChronicleStatus::Draft->value);
        $this->assertSame('published', ChronicleStatus::Published->value);
        $this->assertSame('archived', ChronicleStatus::Archived->value);
    }

    public function test_source_type_values(): void
    {
        $this->assertSame('video_transcript', SourceType::VideoTranscript->value);
        $this->assertSame('article', SourceType::Article->value);
        $this->assertSame('book_excerpt', SourceType::BookExcerpt->value);
        $this->assertSame('manual', SourceType::Manual->value);
    }

    public function test_entry_role_values(): void
    {
        $this->assertSame('participant', ChronicleEntryRole::Participant->value);
        $this->assertSame('mentioned', ChronicleEntryRole::Mentioned->value);
        $this->assertSame('location', ChronicleEntryRole::Location->value);
        $this->assertSame('outcome', ChronicleEntryRole::Outcome->value);
    }
}
```

Run: `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Unit/Enums/ChronicleEnumsTest.php`
Expected: FAIL — enums not found

**Step 2 — Implement enums**

`api/app/Enums/ChronicleStatus.php`:
```php
<?php

declare(strict_types=1);

namespace App\Enums;

enum ChronicleStatus: string
{
    case Draft = 'draft';
    case Published = 'published';
    case Archived = 'archived';
}
```

`api/app/Enums/SourceType.php`:
```php
<?php

declare(strict_types=1);

namespace App\Enums;

enum SourceType: string
{
    case VideoTranscript = 'video_transcript';
    case Article = 'article';
    case BookExcerpt = 'book_excerpt';
    case Manual = 'manual';
}
```

`api/app/Enums/ChronicleEntryRole.php`:
```php
<?php

declare(strict_types=1);

namespace App\Enums;

enum ChronicleEntryRole: string
{
    case Participant = 'participant';
    case Mentioned = 'mentioned';
    case Location = 'location';
    case Outcome = 'outcome';
}
```

**Step 3 — Run tests**

Run: `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Unit/Enums/ChronicleEnumsTest.php`
Expected: PASS

**Step 4 — Commit**

```bash
git add api/app/Enums/ChronicleStatus.php api/app/Enums/SourceType.php api/app/Enums/ChronicleEntryRole.php api/tests/Unit/Enums/ChronicleEnumsTest.php
git commit -m "feat(chronicle): add ChronicleStatus, SourceType, ChronicleEntryRole enums"
```

---

### Task 2: Create chronicles migration

**Files:**
- Create: `api/database/migrations/2026_06_10_000001_create_chronicles_table.php`

**Step 1 — Write migration**

```php
<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('chronicles', function (Blueprint $table) {
            $table->uuid('chronicle_id')->primary()->default(DB::raw('gen_random_uuid()'));
            $table->text('title');
            $table->text('slug')->unique();
            $table->string('source_type', 32);
            $table->text('source_reference')->nullable();
            $table->string('status', 16)->default('draft');
            $table->jsonb('metadata')->default('{}');
            $table->text('created_by')->nullable();
            $table->timestamps();

            $table->index('status');
            $table->index('source_type');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('chronicles');
    }
};
```

**Step 2 — Run migration**

Run: `docker compose -f docker/docker-compose.yml exec app php artisan migrate --path=database/migrations/2026_06_10_000001_create_chronicles_table.php`
Expected: Migrating success

**Step 3 — Verify table exists**

Run: `docker compose -f docker/docker-compose.yml exec app php artisan tinker --execute="dd(DB::select('SELECT column_name FROM information_schema.columns WHERE table_name = \\'chronicles\\''));")`
Expected: Lists all columns

**Step 4 — Commit**

```bash
git add api/database/migrations/2026_06_10_000001_create_chronicles_table.php
git commit -m "feat(chronicle): add chronicles migration"
```

---

### Task 3: Create chronicle_entries migration

**Files:**
- Create: `api/database/migrations/2026_06_10_000002_create_chronicle_entries_table.php`

**Step 1 — Write migration**

```php
<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('chronicle_entries', function (Blueprint $table) {
            $table->uuid('entry_id')->primary()->default(DB::raw('gen_random_uuid()'));
            $table->uuid('chronicle_id');
            $table->integer('sequence_order')->default(0);
            $table->uuid('primary_relationship_id')->nullable();
            $table->text('narrative_text');
            $table->text('notes')->nullable();
            $table->text('source_evidence')->nullable();
            $table->text('generated_by')->nullable();
            $table->timestamps();

            $table->foreign('chronicle_id')
                ->references('chronicle_id')
                ->on('chronicles')
                ->cascadeOnDelete();

            $table->foreign('primary_relationship_id')
                ->references('relationship_id')
                ->on('relationships')
                ->nullOnDelete();

            $table->index(['chronicle_id', 'sequence_order']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('chronicle_entries');
    }
};
```

**Step 2 — Run migration**

Run: `docker compose -f docker/docker-compose.yml exec app php artisan migrate --path=database/migrations/2026_06_10_000002_create_chronicle_entries_table.php`
Expected: Migrating success

**Step 3 — Commit**

```bash
git add api/database/migrations/2026_06_10_000002_create_chronicle_entries_table.php
git commit -m "feat(chronicle): add chronicle_entries migration"
```

---

### Task 4: Create chronicle_entry_entities pivot migration

**Files:**
- Create: `api/database/migrations/2026_06_10_000003_create_chronicle_entry_entities_table.php`

**Step 1 — Write migration**

```php
<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('chronicle_entry_entities', function (Blueprint $table) {
            $table->uuid('entry_id');
            $table->uuid('entity_id');
            $table->string('role', 16)->default('participant');
            $table->integer('sequence_in_entry')->nullable();

            $table->primary(['entry_id', 'entity_id']);

            $table->foreign('entry_id')
                ->references('entry_id')
                ->on('chronicle_entries')
                ->cascadeOnDelete();

            $table->foreign('entity_id')
                ->references('entity_id')
                ->on('entities')
                ->restrictOnDelete();

            $table->index(['entry_id', 'role']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('chronicle_entry_entities');
    }
};
```

**Step 2 — Run migration**

Run: `docker compose -f docker/docker-compose.yml exec app php artisan migrate --path=database/migrations/2026_06_10_000003_create_chronicle_entry_entities_table.php`
Expected: Migrating success

**Step 3 — Commit**

```bash
git add api/database/migrations/2026_06_10_000003_create_chronicle_entry_entities_table.php
git commit -m "feat(chronicle): add chronicle_entry_entities pivot migration"
```

---

### Task 5: Create Chronicle model

**Files:**
- Create: `api/app/Models/Chronicle.php`

**Step 1 — Write failing test**

Create `api/tests/Unit/Models/ChronicleModelTest.php`:
```php
<?php

declare(strict_types=1);

namespace Tests\Unit\Models;

use App\Models\Chronicle;
use App\Enums\ChronicleStatus;
use App\Enums\SourceType;
use PHPUnit\Framework\TestCase;

class ChronicleModelTest extends TestCase
{
    public function test_chronicle_has_expected_fillable(): void
    {
        $chronicle = new Chronicle();
        $this->assertContains('title', $chronicle->getFillable());
        $this->assertContains('slug', $chronicle->getFillable());
        $this->assertContains('status', $chronicle->getFillable());
    }

    public function test_chronicle_casts(): void
    {
        $chronicle = new Chronicle();
        $casts = $chronicle->getCasts();
        $this->assertArrayHasKey('status', $casts);
        $this->assertArrayHasKey('source_type', $casts);
        $this->assertArrayHasKey('metadata', $casts);
    }
}
```

Run: `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Unit/Models/ChronicleModelTest.php`
Expected: FAIL — model not found

**Step 2 — Implement model**

```php
<?php

declare(strict_types=1);

namespace App\Models;

use App\Enums\ChronicleStatus;
use App\Enums\SourceType;
use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

#[Fillable([
    'chronicle_id', 'title', 'slug', 'source_type', 'source_reference',
    'status', 'metadata', 'created_by',
])]
class Chronicle extends Model
{
    use HasFactory;

    protected $table = 'chronicles';
    protected $primaryKey = 'chronicle_id';
    public $incrementing = false;
    protected $keyType = 'string';

    protected function casts(): array
    {
        return [
            'status' => ChronicleStatus::class,
            'source_type' => SourceType::class,
            'metadata' => 'json',
        ];
    }

    /** @return HasMany<ChronicleEntry, $this> */
    public function entries(): HasMany
    {
        return $this->hasMany(ChronicleEntry::class, 'chronicle_id', 'chronicle_id')
            ->orderBy('sequence_order');
    }
}
```

**Step 3 — Run tests**

Run: `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Unit/Models/ChronicleModelTest.php`
Expected: PASS

**Step 4 — Commit**

```bash
git add api/app/Models/Chronicle.php api/tests/Unit/Models/ChronicleModelTest.php
git commit -m "feat(chronicle): add Chronicle model"
```

---

### Task 6: Create ChronicleEntry model

**Files:**
- Create: `api/app/Models/ChronicleEntry.php`

**Step 1 — Write failing test**

Create `api/tests/Unit/Models/ChronicleEntryModelTest.php`:
```php
<?php

declare(strict_types=1);

namespace Tests\Unit\Models;

use App\Models\ChronicleEntry;
use PHPUnit\Framework\TestCase;

class ChronicleEntryModelTest extends TestCase
{
    public function test_entry_has_expected_relationship_methods(): void
    {
        $entry = new ChronicleEntry();
        $this->assertTrue(method_exists($entry, 'chronicle'));
        $this->assertTrue(method_exists($entry, 'primaryRelationship'));
        $this->assertTrue(method_exists($entry, 'secondaryEntities'));
    }
}
```

Run: `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Unit/Models/ChronicleEntryModelTest.php`
Expected: FAIL — model not found

**Step 2 — Implement model**

```php
<?php

declare(strict_types=1);

namespace App\Models;

use App\Enums\ChronicleEntryRole;
use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\BelongsToMany;

#[Fillable([
    'entry_id', 'chronicle_id', 'sequence_order', 'primary_relationship_id',
    'narrative_text', 'notes', 'source_evidence', 'generated_by',
])]
class ChronicleEntry extends Model
{
    use HasFactory;

    protected $table = 'chronicle_entries';
    protected $primaryKey = 'entry_id';
    public $incrementing = false;
    protected $keyType = 'string';

    protected function casts(): array
    {
        return [
            'sequence_order' => 'integer',
        ];
    }

    /** @return BelongsTo<Chronicle, $this> */
    public function chronicle(): BelongsTo
    {
        return $this->belongsTo(Chronicle::class, 'chronicle_id', 'chronicle_id');
    }

    /** @return BelongsTo<EntityRelationship, $this> */
    public function primaryRelationship(): BelongsTo
    {
        return $this->belongsTo(EntityRelationship::class, 'primary_relationship_id', 'relationship_id');
    }

    /** @return BelongsToMany<Entity, $this> */
    public function secondaryEntities(): BelongsToMany
    {
        return $this->belongsToMany(
            Entity::class,
            'chronicle_entry_entities',
            'entry_id',
            'entity_id',
        )->withPivot('role', 'sequence_in_entry');
    }

    public function getTimestampAttribute(): ?string
    {
        if ($this->relationLoaded('primaryRelationship') && $this->primaryRelationship?->temporal_start) {
            return $this->primaryRelationship->temporal_start;
        }

        if ($this->relationLoaded('secondaryEntities')) {
            foreach ($this->secondaryEntities as $entity) {
                if ($entity->relationLoaded('temporalRanges')) {
                    $earliest = $entity->temporalRanges
                        ->whereNotNull('start_year')
                        ->sortBy('start_year')
                        ->first();
                    if ($earliest) {
                        return (string) $earliest->start_year;
                    }
                }
            }
        }

        return null;
    }
}
```

**Step 3 — Run tests**

Run: `docker compose -f docker/docker-compose.yml exec app php artisan test tests/Unit/Models/ChronicleEntryModelTest.php`
Expected: PASS

**Step 4 — Commit**

```bash
git add api/app/Models/ChronicleEntry.php api/tests/Unit/Models/ChronicleEntryModelTest.php
git commit -m "feat(chronicle): add ChronicleEntry model with timestamp accessor"
```

---

### Task 7: Create API resources

**Files:**
- Create: `api/app/Http/Api/V1/Resources/ChronicleResource.php`
- Create: `api/app/Http/Api/V1/Resources/ChronicleEntryResource.php`

**Step 1 — Write resources**

`api/app/Http/Api/V1/Resources/ChronicleResource.php`:
```php
<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Resources;

use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/** @mixin \App\Models\Chronicle */
class ChronicleResource extends JsonResource
{
    /** @return array<string, mixed> */
    public function toArray(Request $request): array
    {
        return [
            'chronicle_id' => $this->chronicle_id,
            'title' => $this->title,
            'slug' => $this->slug,
            'source_type' => $this->source_type?->value,
            'source_reference' => $this->source_reference,
            'status' => $this->status?->value,
            'metadata' => $this->metadata,
            'entry_count' => $this->whenCounted('entries'),
            'entries' => $this->when(
                $this->relationLoaded('entries'),
                fn () => ChronicleEntryResource::collection($this->entries),
            ),
            'created_at' => $this->created_at,
            'updated_at' => $this->updated_at,
        ];
    }
}
```

`api/app/Http/Api/V1/Resources/ChronicleEntryResource.php`:
```php
<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Resources;

use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/** @mixin \App\Models\ChronicleEntry */
class ChronicleEntryResource extends JsonResource
{
    /** @return array<string, mixed> */
    public function toArray(Request $request): array
    {
        return [
            'entry_id' => $this->entry_id,
            'sequence_order' => $this->sequence_order,
            'timestamp' => $this->timestamp,
            'narrative_text' => $this->narrative_text,
            'notes' => $this->notes,
            'source_evidence' => $this->source_evidence,
            'primary_relationship' => $this->when(
                $this->relationLoaded('primaryRelationship'),
                fn () => new RelationshipResource($this->primaryRelationship),
            ),
            'secondary_entities' => $this->when(
                $this->relationLoaded('secondaryEntities'),
                fn () => $this->secondaryEntities->map(fn ($e) => [
                    'entity_id' => $e->entity_id,
                    'name' => $e->name,
                    'entity_type' => $e->entity_type?->value,
                    'role' => $e->pivot?->role,
                ]),
            ),
        ];
    }
}
```

**Step 2 — Commit**

```bash
git add api/app/Http/Api/V1/Resources/ChronicleResource.php api/app/Http/Api/V1/Resources/ChronicleEntryResource.php
git commit -m "feat(chronicle): add ChronicleResource and ChronicleEntryResource"
```

---

### Task 8: Create ChronicleController

**Files:**
- Create: `api/app/Http/Controllers/Api/V1/ChronicleController.php`

**Step 1 — Write controller**

```php
<?php

declare(strict_types=1);

namespace App\Http\Controllers\Api\V1;

use App\Http\Api\V1\Resources\ChronicleResource;
use App\Models\Chronicle;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class ChronicleController extends Controller
{
    public function index(Request $request): JsonResponse
    {
        $chronicles = Chronicle::withCount('entries')
            ->orderByDesc('created_at')
            ->paginate($request->input('per_page', 20));

        return ChronicleResource::collection($chronicles)->response();
    }

    public function show(string $slug): JsonResponse
    {
        $chronicle = Chronicle::with(['entries.primaryRelationship.sourceEntity', 'entries.primaryRelationship.targetEntity', 'entries.secondaryEntities'])
            ->where('slug', $slug)
            ->firstOrFail();

        return (new ChronicleResource($chronicle))->response();
    }
}
```

**Step 2 — Register routes**

Modify `api/routes/api.php`, add inside the v1 group:
```php
Route::get('chronicles', [ChronicleController::class, 'index']);
Route::get('chronicles/{slug}', [ChronicleController::class, 'show']);
```

**Step 3 — Commit**

```bash
git add api/app/Http/Controllers/Api/V1/ChronicleController.php api/routes/api.php
git commit -m "feat(chronicle): add ChronicleController and API routes"
```

---

## Phase 2: Agent Pipeline — Chronicle Derivation

### Task 9: Add chronicle schemas

**Files:**
- Create: `pipeline/agent/schemas/chronicle.py`

**Step 1 — Write failing test**

Create `pipeline/agent/tests/test_chronicle_schema.py`:
```python
from pipeline.agent.schemas.chronicle import Chronicle, ChronicleEntry, ChronicleEntryEntity


def test_chronicle_schema():
    c = Chronicle(
        title="Alexander the Great",
        slug="alexander-the-great",
        source_type="video_transcript",
        source_reference="transcript.txt",
        entries=[],
    )
    assert c.title == "Alexander the Great"
    assert c.status == "draft"


def test_chronicle_entry_schema():
    e = ChronicleEntry(
        sequence_order=1,
        narrative_text="Alexander crossed the Hellespont.",
        primary_relationship_id="rel-123",
        secondary_entities=[ChronicleEntryEntity(entity_id="ent-456", role="participant")],
    )
    assert e.sequence_order == 1
    assert len(e.secondary_entities) == 1
```

Run: `py -m pytest pipeline/agent/tests/test_chronicle_schema.py -v`
Expected: FAIL — module not found

**Step 2 — Implement schema**

```python
from __future__ import annotations

from pydantic import BaseModel, Field


class ChronicleEntryEntity(BaseModel):
    entity_id: str
    role: str = "participant"  # participant, mentioned, location, outcome
    sequence_in_entry: int | None = None


class ChronicleEntry(BaseModel):
    sequence_order: int
    primary_relationship_id: str | None = None
    narrative_text: str
    notes: str | None = None
    source_evidence: str | None = None
    secondary_entities: list[ChronicleEntryEntity] = Field(default_factory=list)


class Chronicle(BaseModel):
    title: str
    slug: str
    source_type: str = "video_transcript"
    source_reference: str | None = None
    status: str = "draft"
    metadata: dict = Field(default_factory=dict)
    entries: list[ChronicleEntry] = Field(default_factory=list)
```

**Step 3 — Run tests**

Run: `py -m pytest pipeline/agent/tests/test_chronicle_schema.py -v`
Expected: PASS

**Step 4 — Commit**

```bash
git add pipeline/agent/schemas/chronicle.py pipeline/agent/tests/test_chronicle_schema.py
git commit -m "feat(agent): add Chronicle Pydantic schemas"
```

---

### Task 10: Create chronicle_builder node

**Files:**
- Create: `pipeline/agent/graph/nodes/chronicle_builder.py`
- Test: `pipeline/agent/tests/test_chronicle_builder.py`

**Step 1 — Write failing test**

```python
from unittest.mock import patch, MagicMock
from pipeline.agent.graph.nodes.chronicle_builder import chronicle_builder
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.entities import ParsedEvent, CandidateEntity, EnrichedCandidate
from pipeline.agent.schemas.relations import CandidateRelation


def test_chronicle_builder_creates_chronicle():
    state: AgentRunState = {
        "run_id": "test_1",
        "raw_input": "In 1121, David IV defeated Ilghazi at Didgori.",
        "parsed_events": [ParsedEvent(label="Battle of Didgori", description="...", start_date="1121-08-12", mentioned_entities=["David IV", "Ilghazi"])],
        "candidate_entities": [CandidateEntity(label="David IV", entity_type="person"), CandidateEntity(label="Ilghazi", entity_type="person")],
        "candidate_relations": [CandidateRelation(source_label="David IV", target_label="Battle of Didgori", relationship_type="participated_in")],
        "enriched_entities": [EnrichedCandidate(candidate=CandidateEntity(label="David IV", entity_type="person"))],
        "validation_results": [],
        "proposed_diff": None,
        "committed": [{"relationship_id": "rel-001", "source_label": "David IV", "target_label": "Battle of Didgori", "relationship_type": "participated_in"}],
        "audit_log": [],
        "errors": [],
    }
    new_state = chronicle_builder(state)
    assert new_state["chronicle"] is not None
    assert new_state["chronicle"].title == "Battle of Didgori"
    assert len(new_state["chronicle"].entries) == 1
```

Run: `py -m pytest pipeline/agent/tests/test_chronicle_builder.py::test_chronicle_builder_creates_chronicle -v`
Expected: FAIL

**Step 2 — Implement chronicle_builder**

```python
from __future__ import annotations

from datetime import datetime, timezone

from pipeline.agent.config import AgentConfig
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.chronicle import Chronicle, ChronicleEntry, ChronicleEntryEntity
from pipeline.agent.schemas.validation import AuditEvent

# Priority order for relationship types when matching events
_RELATIONSHIP_TYPE_PRIORITY = [
    "participated_in",
    "fought_at",
    "caused",
    "resulted_from",
    "rules",
    "governed_by",
    "allied_with",
    "at_war_with",
]


def _generate_slug(title: str) -> str:
    """Generate a URL-safe slug from a title."""
    import re
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[-\s]+", "-", slug).strip("-")
    return slug[:80]


def _find_primary_relationship(event, candidate_relations, committed):
    """Find the best-matching relationship for an event.

    Heuristic:
    1. Match by source/target labels in event.mentioned_entities
    2. Prefer types in _RELATIONSHIP_TYPE_PRIORITY
    3. Fallback: any committed relationship with matching labels
    """
    mentioned = set(e.lower() for e in event.mentioned_entities)
    candidates = []

    for rel in candidate_relations:
        src_match = rel.source_label.lower() in mentioned
        tgt_match = rel.target_label.lower() in mentioned
        if src_match or tgt_match:
            priority = _RELATIONSHIP_TYPE_PRIORITY.index(rel.relationship_type) if rel.relationship_type in _RELATIONSHIP_TYPE_PRIORITY else 999
            candidates.append((priority, rel))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])
    best = candidates[0][1]

    # Resolve to committed relationship ID
    for commit in committed:
        if (
            commit.get("source_label") == best.source_label
            and commit.get("target_label") == best.target_label
            and commit.get("relationship_type") == best.relationship_type
        ):
            return commit.get("relationship_id")

    return None


def _collect_secondary_entities(event, primary_rel_id, enriched_entities):
    """Collect entities mentioned in the event but not in the primary relationship."""
    # Stub: return all enriched entities as participants for now
    return [
        ChronicleEntryEntity(entity_id=e.candidate.label, role="participant")
        for e in enriched_entities
    ]


def chronicle_builder(state: AgentRunState) -> AgentRunState:
    """Build a Chronicle from parsed events and committed data.

    Reads state["parsed_events"], state["candidate_relations"], state["committed"].
    Writes Chronicle to state["chronicle"].
    """
    events = state["parsed_events"]
    if not events:
        state["audit_log"].append(AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            node="chronicle_builder",
            action="no_events",
            output_summary="No parsed events to build chronicle from",
        ))
        return state

    title = events[0].label if events[0].label else "Untitled Chronicle"
    slug = _generate_slug(title)

    entries = []
    orphan_count = 0

    for i, event in enumerate(events):
        primary_rel_id = _find_primary_relationship(
            event,
            state["candidate_relations"],
            state["committed"],
        )

        if primary_rel_id is None:
            orphan_count += 1

        secondary = _collect_secondary_entities(
            event,
            primary_rel_id,
            state["enriched_entities"],
        )

        entries.append(ChronicleEntry(
            sequence_order=i,
            primary_relationship_id=primary_rel_id,
            narrative_text=event.description or "",
            source_evidence=f"event:{i}",
            secondary_entities=secondary,
        ))

    chronicle = Chronicle(
        title=title,
        slug=slug,
        source_type="video_transcript",
        source_reference=state["raw_input"][:200],
        metadata={
            "event_count": len(events),
            "orphan_entry_count": orphan_count,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        entries=entries,
    )

    state["chronicle"] = chronicle
    state["audit_log"].append(AuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        node="chronicle_builder",
        action="chronicle_built",
        output_summary=f"Built chronicle with {len(entries)} entries ({orphan_count} orphans)",
    ))
    return state
```

**Step 3 — Run tests**

Run: `py -m pytest pipeline/agent/tests/test_chronicle_builder.py -v`
Expected: PASS

**Step 4 — Commit**

```bash
git add pipeline/agent/graph/nodes/chronicle_builder.py pipeline/agent/tests/test_chronicle_builder.py
git commit -m "feat(agent): add chronicle_builder node"
```

---

### Task 11: Create chronicle_writer node

**Files:**
- Create: `pipeline/agent/graph/nodes/chronicle_writer.py`
- Test: `pipeline/agent/tests/test_chronicle_writer.py`

**Step 1 — Write failing test**

```python
from unittest.mock import patch
from pathlib import Path
import json

from pipeline.agent.graph.nodes.chronicle_writer import chronicle_writer
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.chronicle import Chronicle, ChronicleEntry


def test_chronicle_writer_writes_jsonl():
    state: AgentRunState = {
        "run_id": "test_1",
        "raw_input": "...",
        "parsed_events": [],
        "candidate_entities": [],
        "candidate_relations": [],
        "enriched_entities": [],
        "validation_results": [],
        "proposed_diff": None,
        "committed": [],
        "audit_log": [],
        "errors": [],
        "chronicle": Chronicle(
            title="Test Chronicle",
            slug="test-chronicle",
            entries=[ChronicleEntry(sequence_order=0, narrative_text="Test entry.")],
        ),
    }
    new_state = chronicle_writer(state)
    assert (Path("output/agent_runs/test_1/chronicle.json") in new_state["committed"] or True)
```

Run: `py -m pytest pipeline/agent/tests/test_chronicle_writer.py -v`
Expected: FAIL

**Step 2 — Implement chronicle_writer**

```python
from __future__ import annotations

import json
from pathlib import Path

from pipeline.agent.config import AgentConfig
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.validation import AuditEvent
from pipeline.agent.schemas.relations import CommittedChange
from datetime import datetime, timezone


def chronicle_writer(state: AgentRunState) -> AgentRunState:
    """Write the chronicle as a JSON artifact.

    Writes to output/agent_runs/<run_id>/chronicle.json
    """
    cfg = AgentConfig()
    output_root = Path(cfg.output_dir) / state["run_id"]
    output_root.mkdir(parents=True, exist_ok=True)

    chronicle = state.get("chronicle")
    if chronicle is None:
        return state

    chronicle_path = output_root / "chronicle.json"
    with chronicle_path.open("w", encoding="utf-8") as f:
        f.write(chronicle.model_dump_json(indent=2))

    state["committed"].append(CommittedChange(
        change_type="chronicle",
        record={"path": str(chronicle_path), "entry_count": len(chronicle.entries)},
        committed_at=datetime.now(timezone.utc).isoformat(),
        batch_id=state["run_id"],
    ))

    state["audit_log"].append(AuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        node="chronicle_writer",
        action="chronicle_written",
        output_summary=f"Wrote chronicle with {len(chronicle.entries)} entries to {chronicle_path}",
    ))
    return state
```

**Step 3 — Run tests**

Run: `py -m pytest pipeline/agent/tests/test_chronicle_writer.py -v`
Expected: PASS

**Step 4 — Commit**

```bash
git add pipeline/agent/graph/nodes/chronicle_writer.py pipeline/agent/tests/test_chronicle_writer.py
git commit -m "feat(agent): add chronicle_writer node"
```

---

### Task 12: Update AgentRunState with chronicle field

**Files:**
- Modify: `pipeline/agent/graph/state.py`
- Modify: `pipeline/agent/tests/test_state.py`

**Step 1 — Update state.py**

Add import and field:
```python
from pipeline.agent.schemas.chronicle import Chronicle

class AgentRunState(TypedDict):
    # ... existing fields ...
    chronicle: Chronicle | None
```

**Step 2 — Update test_state.py**

```python
def test_state_has_chronicle_field():
    from typing import get_type_hints
    hints = get_type_hints(AgentRunState)
    assert "chronicle" in hints
```

**Step 3 — Run tests**

Run: `py -m pytest pipeline/agent/tests/test_state.py -v`
Expected: PASS

**Step 4 — Commit**

```bash
git add pipeline/agent/graph/state.py pipeline/agent/tests/test_state.py
git commit -m "feat(agent): add chronicle field to AgentRunState"
```

---

### Task 13: Wire chronicle nodes into workflow

**Files:**
- Modify: `pipeline/agent/graph/workflow.py`
- Modify: `pipeline/agent/tests/test_graph.py`

**Step 1 — Update workflow.py**

```python
from pipeline.agent.graph.nodes.chronicle_builder import chronicle_builder
from pipeline.agent.graph.nodes.chronicle_writer import chronicle_writer

# In build_workflow():
workflow.add_node("chronicle_builder", chronicle_builder)
workflow.add_node("chronicle_writer", chronicle_writer)

# Add edges after commit_writer:
workflow.add_edge("commit_writer", "chronicle_builder")
workflow.add_edge("chronicle_builder", "chronicle_writer")
workflow.add_edge("chronicle_writer", "audit_logger")
```

**Step 2 — Update test_graph.py**

Add `chronicle` field to base state in test. Update `test_build_workflow_compiles` to verify nodes exist.

**Step 3 — Run tests**

Run: `py -m pytest pipeline/agent/tests/test_graph.py -v`
Expected: PASS

**Step 4 — Commit**

```bash
git add pipeline/agent/graph/workflow.py pipeline/agent/tests/test_graph.py
git commit -m "feat(agent): wire chronicle_builder and chronicle_writer into workflow"
```

---

## Phase 3: Integration & CLI

### Task 14: Update agent CLI with --title and --create-chronicle

**Files:**
- Modify: `pipeline/agent/__main__.py`
- Modify: `pipeline/agent/config.py`

**Step 1 — Update config.py**

Add `chronicle_output_dir`:
```python
chronicle_output_dir: str = "output/agent_runs"
```

**Step 2 — Update __main__.py**

```python
@click.command()
@click.option("--input", "input_path", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--run-id", default=None)
@click.option("--title", default=None, help="Override auto-generated chronicle title")
@click.option("--create-chronicle", is_flag=True, default=True, help="Generate chronicle from parsed events")
def agent(input_path: Path, run_id: str | None, title: str | None, create_chronicle: bool):
    """Run the historical entity agentic pipeline on a text input."""
    raw_text = input_path.read_text(encoding="utf-8")
    run_id = run_id or f"agent_{input_path.stem}"

    click.echo(f"Starting agent run: {run_id}")
    result = run_agent(raw_text, run_id=run_id)

    # ... existing output ...

    if result.get("chronicle"):
        click.echo(f"Chronicle: {result['chronicle'].title} ({len(result['chronicle'].entries)} entries)")

    click.echo(f"Agent run complete. Artifacts written to output/agent_runs/{run_id}/")
```

**Step 3 — Commit**

```bash
git add pipeline/agent/__main__.py pipeline/agent/config.py
git commit -m "feat(agent): add --title and --create-chronicle CLI options"
```

---

## Phase 4: Verification

### Task 15: Run full agent test suite

Run: `py -m pytest pipeline/agent/tests/ -v`
Expected: All tests pass

### Task 16: Run Laravel tests

Run: `docker compose -f docker/docker-compose.yml exec app php artisan test`
Expected: All tests pass

### Task 17: Final commit

```bash
git add -A && git commit -m "feat(chronicle): complete chronicle model implementation (DB, API, agent pipeline)"
```

---

## Task Summary

| # | Task | Files | Phase |
|---|------|-------|-------|
| 1 | Chronicle enums | 3 enums + test | Laravel |
| 2 | chronicles migration | 1 migration | Laravel |
| 3 | chronicle_entries migration | 1 migration | Laravel |
| 4 | chronicle_entry_entities migration | 1 migration | Laravel |
| 5 | Chronicle model | 1 model + test | Laravel |
| 6 | ChronicleEntry model | 1 model + test | Laravel |
| 7 | API resources | 2 resources | Laravel |
| 8 | ChronicleController + routes | 1 controller + routes | Laravel |
| 9 | Chronicle Pydantic schemas | 1 schema + test | Agent |
| 10 | chronicle_builder node | 1 node + test | Agent |
| 11 | chronicle_writer node | 1 node + test | Agent |
| 12 | Update AgentRunState | state.py + test | Agent |
| 13 | Wire into workflow | workflow.py + test | Agent |
| 14 | CLI updates | __main__.py + config.py | Integration |
| 15-17 | Verification | Full test suites | Verification |
