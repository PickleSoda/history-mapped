# Admin AI Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A route-bound AI assistant in the Laravel admin: a nav button opens a left sidebar chat that knows the current entity/chronicle and proposes data edits (create entity, set location, link, edit fields) that a human applies per-part.

**Architecture:** Laravel AI SDK (`laravel/ai`) agents constructed with the bound record; tools never commit — they stage rows in `agent_proposed_changes(_parts)` and return a diff; a deterministic `/ai/proposals/.../apply` endpoint runs the existing Entity/Relationship Actions with `created_by="agent:{user}"`. Frontend is AI Elements (React+Tailwind+shadcn) `useChat` over a Vercel-protocol SSE stream.

**Tech Stack:** PHP 8.4 / Laravel 13, `laravel/ai` (OpenRouter), Inertia + React 19, `@ai-sdk/react`, AI Elements, Tailwind 4, PostgreSQL/PostGIS. Everything runs in Docker Compose (`docker compose -f docker/docker-compose.yml exec app …`).

## Global Constraints

- All backend commands run in the `app` container: `docker compose -f docker/docker-compose.yml exec app php artisan …`. Restart `app` after editing existing files (stale bind mount).
- Write logic lives in **Action classes**, never controllers/tools — tools call Actions.
- Provider: **OpenRouter**, default model `anthropic/claude-haiku-4.5`, configurable in `config/ai.php`; soft spend cap ~$20/mo.
- Write-safety: **propose → preview → confirm**, **partial apply** (per-part). No tool commits directly; the model can never call apply.
- Provenance: every applied change uses `createdBy = "agent:{user_id}"`.
- Auth: AI routes sit in the `['auth','verified']` group; the apply endpoint additionally requires `permission:entities.write` (admin bypasses via `Gate::before`).
- Retention (scheduler): pending/discarded parts pruned after 7 days; applied kept 1 year; chat history 90 days.
- Pint must pass (`./vendor/bin/pint --test`); admin JS uses `npm run lint`/`types:check` in `app`.
- **Verify SDK contracts first:** `laravel/ai` is new — before coding agents/tools, read the installed package's `Agent`/`Tool` contracts (`vendor/laravel/ai/src/Contracts`) and align method signatures. The documented shapes used here: `Agent::instructions()`, `Conversational::messages()`, `HasTools::tools()`, `->stream($p)->usingVercelDataProtocol()`.

---

## File Structure

**Backend (api/)**
- `config/ai.php` — provider/model config (published, then edited for OpenRouter).
- `app/Models/Ai/ProposedChange.php`, `ProposedChangePart.php` — staging + audit/undo.
- `database/migrations/*_create_agent_proposed_changes_tables.php`.
- `app/Ai/Tools/AgentTool.php` — abstract base: schema + `buildParts()` + `applyPart()` + `handle()` that stages a proposal.
- `app/Ai/Tools/{CreateEntity,SetEntityLocation,CreateRelationship,UpdateEntityFields,SetEntityWikidata,VerifyWikidata,MergeDuplicateEntities,GetEntityContext}.php`.
- `app/Ai/ToolRegistry.php` — maps tool name → class (for the apply endpoint).
- `app/Ai/ProposalApplier.php` — applies one part, resolving `depends_on`.
- `app/Ai/Agents/{EntityEditorAgent,ChronicleEditorAgent}.php`.
- `app/Services/WikidataService.php` — `Special:EntityData` lookups (P31/P625).
- `app/Http/Controllers/Admin/Ai/{AiChatController,AiProposalController}.php`.
- `resources/views/ai/instructions/entity-editor.blade.php` — agent system prompt.
- routes added to `routes/web.php`.

**Frontend (api/resources/js/)**
- `components/ui/ai/*` — AI Elements components (installed via shadcn registry).
- `components/ai/ai-sidebar.tsx` — the Sheet + `useChat` chat.
- `components/ai/proposal-card.tsx` — per-part Apply/Discard renderer.
- `hooks/use-ai-context.ts` — reads `ai_context` from Inertia page props.
- nav button added to `components/nav-main.tsx`; `ai_context` prop added to `EntityController`/`ChronicleController` Inertia renders.

---

## Task 1: Install & configure the Laravel AI SDK (OpenRouter)

**Files:**
- Modify: `api/composer.json` (via composer), `api/config/ai.php` (published), `api/.env.example`.

- [ ] **Step 1: Install the package**

```bash
docker compose -f docker/docker-compose.yml exec app composer require laravel/ai
docker compose -f docker/docker-compose.yml exec app php artisan vendor:publish --tag=ai-config
docker compose -f docker/docker-compose.yml exec app php artisan vendor:publish --tag=ai-migrations
docker compose -f docker/docker-compose.yml exec app php artisan migrate
```

- [ ] **Step 2: Read the installed contracts (no code yet)**

Run: `docker compose -f docker/docker-compose.yml exec app ls vendor/laravel/ai/src/Contracts`
Open `Agent.php`, `Conversational.php`, `HasTools.php`, and the Tool contract. Note exact method names/signatures; the tasks below assume the documented shapes — reconcile any differences before continuing.

- [ ] **Step 3: Configure OpenRouter default in `config/ai.php`**

Set the default provider to `openrouter` and default model `anthropic/claude-haiku-4.5` (edit the published config's `default`/`providers` keys to match the installed schema). Add to `.env.example`:

```ini
OPENROUTER_API_KEY=
AI_DEFAULT_PROVIDER=openrouter
AI_DEFAULT_MODEL=anthropic/claude-haiku-4.5
```

- [ ] **Step 4: Smoke-test config loads**

Run: `docker compose -f docker/docker-compose.yml exec app php artisan config:show ai`
Expected: prints the `ai` config with `openrouter` present. (`OPENROUTER_API_KEY` already exists in the pipeline env; mirror it into `api/.env`.)

- [ ] **Step 5: Commit**

```bash
git add api/composer.json api/composer.lock api/config/ai.php api/.env.example api/database/migrations
git commit -m "feat(ai): install & configure Laravel AI SDK for OpenRouter"
```

---

## Task 2: Proposal staging tables & models

**Files:**
- Create: `api/database/migrations/2026_06_24_000001_create_agent_proposed_changes_tables.php`
- Create: `api/app/Models/Ai/ProposedChange.php`, `api/app/Models/Ai/ProposedChangePart.php`
- Test: `api/tests/Feature/Ai/ProposedChangeModelTest.php`

**Interfaces:**
- Produces: `ProposedChange` (hasMany `parts`), `ProposedChangePart` with `status` in {pending,applied,discarded}, `payload`/`human_diff` casts to array, `depends_on` (nullable part key), `result_id` (nullable string), `applyApplied(string $resultId)` and `markDiscarded()` helpers.

- [ ] **Step 1: Write the failing test**

```php
<?php
namespace Tests\Feature\Ai;

use App\Models\Ai\ProposedChange;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ProposedChangeModelTest extends TestCase
{
    use RefreshDatabase;

    public function test_a_change_has_parts_with_pending_status_and_array_casts(): void
    {
        $user = User::factory()->create();
        $change = ProposedChange::create([
            'user_id' => $user->id, 'context_type' => 'entity', 'context_id' => 'e-1',
        ]);
        $part = $change->parts()->create([
            'key' => 'a', 'tool' => 'create_entity',
            'payload' => ['name' => 'Tikal'], 'human_diff' => ['summary' => 'Create Tikal'],
        ]);

        $this->assertSame('pending', $part->fresh()->status);
        $this->assertSame('Tikal', $part->fresh()->payload['name']);
        $this->assertTrue($change->parts()->whereKey($part->id)->exists());

        $part->applyApplied('new-entity-id');
        $this->assertSame('applied', $part->fresh()->status);
        $this->assertSame('new-entity-id', $part->fresh()->result_id);
    }
}
```

- [ ] **Step 2: Run it, expect failure**

Run: `docker compose -f docker/docker-compose.yml exec app php artisan test --filter ProposedChangeModelTest`
Expected: FAIL (no migration/model).

- [ ] **Step 3: Write the migration**

```php
<?php
use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        Schema::create('agent_proposed_changes', function (Blueprint $t) {
            $t->uuid('id')->primary();
            $t->foreignId('user_id')->constrained()->cascadeOnDelete();
            $t->string('conversation_id')->nullable();
            $t->string('context_type');           // 'entity' | 'chronicle'
            $t->string('context_id');
            $t->timestamps();
            $t->index(['context_type', 'context_id']);
        });

        Schema::create('agent_proposed_change_parts', function (Blueprint $t) {
            $t->uuid('id')->primary();
            $t->foreignUuid('change_id')->constrained('agent_proposed_changes')->cascadeOnDelete();
            $t->string('key');                    // unique within a change
            $t->string('tool');
            $t->json('payload');
            $t->json('human_diff');
            $t->string('status')->default('pending'); // pending|applied|discarded
            $t->string('depends_on')->nullable();     // another part's key
            $t->string('result_id')->nullable();      // entity/relationship id once applied
            $t->timestamp('applied_at')->nullable();
            $t->timestamps();
            $t->index(['change_id', 'status']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('agent_proposed_change_parts');
        Schema::dropIfExists('agent_proposed_changes');
    }
};
```

- [ ] **Step 4: Write the models**

```php
// app/Models/Ai/ProposedChange.php
<?php
namespace App\Models\Ai;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class ProposedChange extends Model
{
    use HasUuids;

    protected $table = 'agent_proposed_changes';
    protected $fillable = ['user_id', 'conversation_id', 'context_type', 'context_id'];

    public function parts(): HasMany
    {
        return $this->hasMany(ProposedChangePart::class, 'change_id');
    }
}
```

```php
// app/Models/Ai/ProposedChangePart.php
<?php
namespace App\Models\Ai;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class ProposedChangePart extends Model
{
    use HasUuids;

    protected $table = 'agent_proposed_change_parts';
    protected $fillable = ['change_id', 'key', 'tool', 'payload', 'human_diff', 'status', 'depends_on', 'result_id', 'applied_at'];
    protected $casts = ['payload' => 'array', 'human_diff' => 'array', 'applied_at' => 'datetime'];

    public function change(): BelongsTo
    {
        return $this->belongsTo(ProposedChange::class, 'change_id');
    }

    public function applyApplied(string $resultId): void
    {
        $this->update(['status' => 'applied', 'result_id' => $resultId, 'applied_at' => now()]);
    }

    public function markDiscarded(): void
    {
        $this->update(['status' => 'discarded']);
    }
}
```

- [ ] **Step 5: Migrate & run the test**

Run: `docker compose -f docker/docker-compose.yml exec app php artisan migrate && docker compose -f docker/docker-compose.yml exec app php artisan test --filter ProposedChangeModelTest`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add api/database/migrations api/app/Models/Ai api/tests/Feature/Ai/ProposedChangeModelTest.php
git commit -m "feat(ai): proposed-change staging tables & models"
```

---

## Task 3: WikidataService (namesake guard)

**Files:**
- Create: `api/app/Services/WikidataService.php`
- Test: `api/tests/Feature/Ai/WikidataServiceTest.php`

**Interfaces:**
- Produces: `WikidataService::fetch(string $qid): ?array` returning `['label'=>?string,'description'=>?string,'p31'=>string[],'coord'=>?array{lon,lat}]` (null on 404); uses `Http::get("https://www.wikidata.org/wiki/Special:EntityData/{$qid}.json")`.

- [ ] **Step 1: Write the failing test (HTTP faked)**

```php
<?php
namespace Tests\Feature\Ai;

use App\Services\WikidataService;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class WikidataServiceTest extends TestCase
{
    public function test_it_parses_label_p31_and_coordinate(): void
    {
        Http::fake(['*' => Http::response(['entities' => ['Q522862' => [
            'labels' => ['en' => ['value' => 'Karnak Temple Complex']],
            'descriptions' => ['en' => ['value' => 'ancient Egyptian temple complex']],
            'claims' => [
                'P31' => [['mainsnak' => ['datavalue' => ['value' => ['id' => 'Q839954']]]]],
                'P625' => [['mainsnak' => ['datavalue' => ['value' => ['longitude' => 32.6583, 'latitude' => 25.7183]]]]],
            ],
        ]]]])]);

        $meta = app(WikidataService::class)->fetch('Q522862');

        $this->assertSame('Karnak Temple Complex', $meta['label']);
        $this->assertContains('Q839954', $meta['p31']);
        $this->assertEqualsWithDelta(32.6583, $meta['coord']['lon'], 0.001);
    }

    public function test_it_returns_null_for_missing_entity(): void
    {
        Http::fake(['*' => Http::response(['entities' => []], 200)]);
        $this->assertNull(app(WikidataService::class)->fetch('Q0'));
    }
}
```

- [ ] **Step 2: Run it, expect failure.** `… php artisan test --filter WikidataServiceTest` → FAIL.

- [ ] **Step 3: Implement**

```php
<?php
namespace App\Services;

use Illuminate\Support\Facades\Http;

class WikidataService
{
    public function fetch(string $qid): ?array
    {
        $res = Http::acceptJson()->get("https://www.wikidata.org/wiki/Special:EntityData/{$qid}.json");
        $entity = $res->json("entities.{$qid}");
        if (! is_array($entity)) {
            return null;
        }

        $claims = $entity['claims'] ?? [];
        $coordVal = data_get($claims, 'P625.0.mainsnak.datavalue.value');

        return [
            'label' => data_get($entity, 'labels.en.value'),
            'description' => data_get($entity, 'descriptions.en.value'),
            'p31' => collect($claims['P31'] ?? [])
                ->map(fn ($c) => data_get($c, 'mainsnak.datavalue.value.id'))
                ->filter()->values()->all(),
            'coord' => $coordVal ? ['lon' => $coordVal['longitude'], 'lat' => $coordVal['latitude']] : null,
        ];
    }
}
```

- [ ] **Step 4: Run the test** → PASS.
- [ ] **Step 5: Commit** `git commit -am "feat(ai): WikidataService for QID verification"`.

---

## Task 4: Tool base, registry & applier (the spine)

**Files:**
- Create: `api/app/Ai/Tools/AgentTool.php`, `api/app/Ai/ToolRegistry.php`, `api/app/Ai/ProposalApplier.php`
- Test: `api/tests/Feature/Ai/ProposalApplierTest.php`

**Interfaces:**
- Produces:
  - `abstract class AgentTool` with: `abstract public static function name(): string`; `abstract public function schema(JsonSchema $schema): array`; `abstract public function buildParts(array $args): array` (each: `['key'=>string,'tool'=>string,'payload'=>array,'human_diff'=>array,'depends_on'=>?string]`); `abstract public function applyPart(array $payload, array $resolved): array` (returns `['result_id'=>string,'summary'=>string]`); plus `handle()` (model-facing) that stages a `ProposedChange`.
  - `ToolRegistry::resolve(string $name): AgentTool` (maps `name()` → instance via container).
  - `ProposalApplier::applyPart(ProposedChangePart $part): ProposedChangePart` — guards `depends_on` (the dependency must be `applied`; substitutes its `result_id` into `$resolved['depends']`), calls the tool's `applyPart`, records `result_id`, returns the part.

- [ ] **Step 1: Write the failing test (a fake tool through the applier)**

```php
<?php
namespace Tests\Feature\Ai;

use App\Ai\ProposalApplier;
use App\Ai\ToolRegistry;
use App\Models\Ai\ProposedChange;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ProposalApplierTest extends TestCase
{
    use RefreshDatabase;

    public function test_dependent_part_waits_for_its_dependency_then_substitutes_result_id(): void
    {
        // register a fake tool that echoes payload + injected dependency id
        app()->bind('ai.tool.fake', fn () => new class extends \App\Ai\Tools\AgentTool {
            public static function name(): string { return 'fake'; }
            public function description(): string { return 'fake tool'; }
            public function schema(\Illuminate\Contracts\JsonSchema\JsonSchema $s): array { return []; }
            public function buildParts(array $args): array { return []; }
            public function applyPart(array $payload, array $resolved): array {
                return ['result_id' => ($resolved['depends'] ?? 'X').':'.$payload['v'], 'summary' => 'ok'];
            }
        });
        app(ToolRegistry::class)->register('fake', 'ai.tool.fake');

        $user = User::factory()->create();
        $change = ProposedChange::create(['user_id' => $user->id, 'context_type' => 'entity', 'context_id' => 'e1']);
        $a = $change->parts()->create(['key' => 'a', 'tool' => 'fake', 'payload' => ['v' => 'A'], 'human_diff' => []]);
        $b = $change->parts()->create(['key' => 'b', 'tool' => 'fake', 'payload' => ['v' => 'B'], 'human_diff' => [], 'depends_on' => 'a']);

        $applier = app(ProposalApplier::class);

        // applying B before A throws (dependency not applied)
        $this->expectExceptionMessage('depends_on');
        $applier->applyPart($b);
        $this->assertSame('pending', $b->fresh()->status);

        // apply A, then B substitutes A's result_id
        $applier->applyPart($a);
        $this->assertSame('X:A', $a->fresh()->result_id);
        $applier->applyPart($b->fresh());
        $this->assertSame('X:A:B', $b->fresh()->result_id);
    }
}
```

- [ ] **Step 2: Run it, expect failure.**

- [ ] **Step 3: Implement the base, registry, applier**

> **Aligned to the installed `laravel/ai` v0.8.1 `Contracts\Tool` (Task 1 findings):**
> `description(): Stringable|string`, `handle(Laravel\Ai\Tools\Request $request): Stringable|string` (returns a **string**; args via `$request->all()`), `schema(JsonSchema $schema): array`. The Tool interface has **no `name()`** and `handle()` receives only the model's args — so route/conversation context is injected by the agent via a `withContext()` setter, and `name()` is kept solely for our registry.

```php
// app/Ai/Tools/AgentTool.php
<?php
namespace App\Ai\Tools;

use App\Models\Ai\ProposedChange;
use Illuminate\Contracts\JsonSchema\JsonSchema;
use Laravel\Ai\Contracts\Tool;
use Laravel\Ai\Tools\Request;
use Stringable;

abstract class AgentTool implements Tool
{
    /** Route/conversation context injected by the agent (user_id, context_type, context_id, conversation_id). */
    protected array $context = [];

    /** Registry key — NOT part of the SDK Tool contract. */
    abstract public static function name(): string;

    abstract public function description(): Stringable|string;

    /** @return array<string,\Illuminate\JsonSchema\Types\Type> */
    abstract public function schema(JsonSchema $schema): array;

    /** @return list<array{key:string,tool:string,payload:array,human_diff:array,depends_on?:?string}> */
    abstract public function buildParts(array $args): array;

    /** @return array{result_id:string,summary:string} */
    abstract public function applyPart(array $payload, array $resolved): array;

    public function withContext(array $context): static
    {
        $this->context = $context;

        return $this;
    }

    /**
     * Model-facing entry point (laravel/ai Tool contract). Stages a
     * ProposedChange from the model's args + injected context and returns a
     * JSON summary STRING the model relays. The model never applies.
     */
    public function handle(Request $request): Stringable|string
    {
        $change = ProposedChange::create([
            'user_id' => $this->context['user_id'],
            'conversation_id' => $this->context['conversation_id'] ?? null,
            'context_type' => $this->context['context_type'],
            'context_id' => $this->context['context_id'],
        ]);
        foreach ($this->buildParts($request->all()) as $part) {
            $change->parts()->create([
                'key' => $part['key'], 'tool' => $part['tool'],
                'payload' => $part['payload'], 'human_diff' => $part['human_diff'],
                'depends_on' => $part['depends_on'] ?? null,
            ]);
        }

        return json_encode([
            'proposal_id' => $change->id,
            'parts' => $change->parts()->get(['key', 'tool', 'human_diff'])->toArray(),
            'note' => 'Proposed. Awaiting the operator to Apply each part.',
        ], JSON_THROW_ON_ERROR);
    }
}
```

```php
// app/Ai/ToolRegistry.php
<?php
namespace App\Ai;

use App\Ai\Tools\AgentTool;

class ToolRegistry
{
    /** @var array<string,string> name => container binding/class */
    private array $map = [];

    public function register(string $name, string $binding): void
    {
        $this->map[$name] = $binding;
    }

    public function resolve(string $name): AgentTool
    {
        abort_unless(isset($this->map[$name]), 422, "Unknown tool: {$name}");

        return app($this->map[$name]);
    }
}
```

```php
// app/Ai/ProposalApplier.php
<?php
namespace App\Ai;

use App\Models\Ai\ProposedChangePart;
use RuntimeException;

class ProposalApplier
{
    public function __construct(private ToolRegistry $registry) {}

    public function applyPart(ProposedChangePart $part): ProposedChangePart
    {
        if ($part->status === 'applied') {
            return $part;
        }

        $resolved = [];
        if ($part->depends_on) {
            $dep = $part->change->parts()->where('key', $part->depends_on)->first();
            if (! $dep || $dep->status !== 'applied') {
                throw new RuntimeException("Cannot apply: depends_on '{$part->depends_on}' is not applied yet.");
            }
            $resolved['depends'] = $dep->result_id;
        }

        $result = $this->registry->resolve($part->tool)->applyPart($part->payload, $resolved);
        $part->applyApplied($result['result_id']);

        return $part->fresh();
    }
}
```

Register the registry as a singleton in `AppServiceProvider::register()`:

```php
$this->app->singleton(\App\Ai\ToolRegistry::class);
```

- [ ] **Step 4: Run the test** → PASS.
- [ ] **Step 5: Commit** `git commit -am "feat(ai): tool base, registry & partial-apply applier"`.

---

## Task 5: CreateEntity tool (the primary tool)

**Files:**
- Create: `api/app/Ai/Tools/CreateEntity.php`
- Test: `api/tests/Feature/Ai/CreateEntityToolTest.php`
- Modify: `api/app/Providers/AppServiceProvider.php` (register the tool)

**Interfaces:**
- Consumes: `AgentTool`, `CreateEntityAction`, `BackfillEntityAction`, `WikidataService`, `EntityData`.
- Produces: tool name `create_entity`; `buildParts` returns one part `{key:'entity', tool:'create_entity', payload:{name,entity_type,wikidata_id?,lon?,lat?,summary?,start_year?,end_year?}, human_diff:{summary}}`; `applyPart` creates the entity (+backfill) and returns its `entity_id`.

- [ ] **Step 1: Write the failing test**

```php
<?php
namespace Tests\Feature\Ai;

use App\Ai\Tools\CreateEntity;
use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class CreateEntityToolTest extends TestCase
{
    use RefreshDatabase;

    public function test_build_then_apply_creates_a_located_entity_with_agent_provenance(): void
    {
        Http::fake(['*' => Http::response(['entities' => ['Q28567' => [
            'labels' => ['en' => ['value' => 'Maya civilization']],
            'claims' => ['P31' => [['mainsnak' => ['datavalue' => ['value' => ['id' => 'Q11514315']]]]]],
        ]]]])]);

        $tool = app(CreateEntity::class);
        $parts = $tool->buildParts([
            'name' => 'Maya civilization', 'entity_type' => 'political_entity',
            'wikidata_id' => 'Q28567', 'lon' => -89.6, 'lat' => 17.2,
        ]);
        $this->assertCount(1, $parts);
        $this->assertSame('create_entity', $parts[0]['tool']);

        $result = $tool->applyPart($parts[0]['payload'], ['user_id' => 'u1']);
        $entity = Entity::findOrFail($result['result_id']);

        $this->assertSame('Maya civilization', $entity->name);
        $this->assertSame('political_entity', $entity->entity_type->value);
        $this->assertSame('agent:u1', $entity->created_by);
        $this->assertNotNull($entity->primaryLocation);
    }
}
```

- [ ] **Step 2: Run it, expect failure.**

- [ ] **Step 3: Implement the tool**

```php
<?php
namespace App\Ai\Tools;

use App\Actions\Entity\BackfillEntityAction;
use App\Actions\Entity\CreateEntityAction;
use App\DTOs\EntityData;
use App\Enums\EntityType;
use App\Enums\LocationResolutionMethod;
use App\Models\Entity;
use App\Services\WikidataService;
use Illuminate\Contracts\JsonSchema\JsonSchema;

class CreateEntity extends AgentTool
{
    public function __construct(
        private CreateEntityAction $create,
        private BackfillEntityAction $backfill,
        private WikidataService $wikidata,
    ) {}

    public static function name(): string
    {
        return 'create_entity';
    }

    public function description(): string
    {
        return 'Create a new historical entity (the primary tool). Verify any wikidata_id first; pass a representative lon/lat when known.';
    }

    // NOTE: align the fluent builder calls with the INSTALLED Illuminate JsonSchema
    // API (Laravel AI confirmed `$schema->string('description')` style). Use
    // whatever the installed `Illuminate\JsonSchema\Types` exposes for description /
    // required / number / integer — adjust the calls below to match if they differ.
    public function schema(JsonSchema $schema): array
    {
        return [
            'name' => $schema->string()->description('Entity name')->required(),
            'entity_type' => $schema->string()->description('One of the 30 EntityType values, e.g. political_entity, infrastructure_monument, event_battle')->required(),
            'wikidata_id' => $schema->string()->description('QID, verified against Wikidata; omit if none'),
            'summary' => $schema->string()->description('Short description'),
            'lon' => $schema->number()->description('Longitude of a representative location'),
            'lat' => $schema->number()->description('Latitude'),
            'start_year' => $schema->integer()->description('Signed year, BCE negative'),
            'end_year' => $schema->integer(),
        ];
    }

    public function buildParts(array $args): array
    {
        $note = '';
        if (! empty($args['wikidata_id'])) {
            $meta = $this->wikidata->fetch($args['wikidata_id']);
            $note = $meta
                ? " — verified Wikidata: {$meta['label']}"
                : ' — WARNING: Wikidata QID not found';
        }

        return [[
            'key' => 'entity',
            'tool' => self::name(),
            'payload' => $args,
            'human_diff' => [
                'summary' => "Create entity “{$args['name']}” ({$args['entity_type']})".$note,
                'fields' => $args,
            ],
        ]];
    }

    public function applyPart(array $payload, array $resolved): array
    {
        $type = EntityType::from($payload['entity_type']);
        $hasCoord = isset($payload['lon'], $payload['lat']);

        $data = new EntityData(
            name: $payload['name'],
            entityType: $type,
            entityGroup: $type->group(),
            summary: $payload['summary'] ?? null,
            wikidataId: $payload['wikidata_id'] ?? null,
            temporalStart: isset($payload['start_year']) ? (string) $payload['start_year'] : null,
            temporalEnd: isset($payload['end_year']) ? (string) $payload['end_year'] : null,
            locationMethod: $hasCoord ? LocationResolutionMethod::Wikidata : null,
            geojson: $hasCoord ? ['type' => 'Point', 'coordinates' => [$payload['lon'], $payload['lat']]] : null,
        );

        /** @var Entity $entity */
        $entity = ($this->create)($data, createdBy: 'agent:'.$resolved['user_id']);
        ($this->backfill)($entity);

        return ['result_id' => $entity->entity_id, 'summary' => "Created {$entity->name}"];
    }
}
```

Register in `AppServiceProvider::boot()`:

```php
app(\App\Ai\ToolRegistry::class)->register(\App\Ai\Tools\CreateEntity::name(), \App\Ai\Tools\CreateEntity::class);
```

> Note: `applyPart` reads `$resolved['user_id']`; `ProposalApplier` must merge the acting user into `$resolved` (Task 7 adds `$resolved['user_id']`). For this unit test we pass it directly.

- [ ] **Step 4: Run the test** → PASS. (Adjust `EntityType` value strings if the enum differs.)
- [ ] **Step 5: Commit** `git commit -am "feat(ai): CreateEntity tool (primary)"`.

---

## Task 6: Remaining write tools

Each sub-task follows the same TDD shape as Task 5 (write a `buildParts`+`applyPart` test, run-fail, implement, run-pass, commit). Full `applyPart` bodies below; register each in `AppServiceProvider::boot()` like Task 5.

**Files (create one tool + one test each):**
`SetEntityLocation.php`, `CreateRelationship.php`, `UpdateEntityFields.php`, `SetEntityWikidata.php`, `MergeDuplicateEntities.php`, `GetEntityContext.php`, `VerifyWikidata.php` under `app/Ai/Tools/`, with matching tests under `tests/Feature/Ai/`.

- [ ] **Task 6a: `SetEntityLocation`** — wraps `UpdateEntityAction` + backfill.

```php
public static function name(): string { return 'set_entity_location'; }

public function buildParts(array $args): array
{
    $e = Entity::with('primaryLocation')->findOrFail($args['entity_id']);
    $from = $e->primaryLocation?->geom; // [lon,lat] or null
    return [[
        'key' => 'location', 'tool' => self::name(), 'payload' => $args,
        'human_diff' => ['summary' => "Move {$e->name} → ({$args['lon']}, {$args['lat']})",
                         'from' => $from, 'to' => [$args['lon'], $args['lat']]],
    ]];
}

public function applyPart(array $payload, array $resolved): array
{
    $e = Entity::findOrFail($payload['entity_id']);
    $data = new EntityData(
        name: $e->name, entityType: $e->entity_type, entityGroup: $e->entity_group,
        locationMethod: LocationResolutionMethod::HumanAssigned,
        geojson: ['type' => 'Point', 'coordinates' => [$payload['lon'], $payload['lat']]],
    );
    $e = ($this->update)($e, $data);
    ($this->backfill)($e);
    return ['result_id' => $e->entity_id, 'summary' => 'Location updated'];
}
```

- [ ] **Task 6b: `CreateRelationship`** — wraps `CreateRelationshipAction`; **nests a CreateEntity part** when the target is unknown.

```php
public static function name(): string { return 'create_relationship'; }

// args: {source_entity_id, relationship_type, target_entity_id?, new_target?:{name,entity_type,...}, start_year?, end_year?}
public function buildParts(array $args): array
{
    $parts = [];
    $targetRef = $args['target_entity_id'] ?? null;

    if (! $targetRef && ! empty($args['new_target'])) {
        // far side missing → propose creating it first (CreateEntity), link depends on it
        $parts[] = [
            'key' => 'target', 'tool' => 'create_entity', 'payload' => $args['new_target'],
            'human_diff' => ['summary' => "Create new entity “{$args['new_target']['name']}” (relationship target)"],
        ];
    }

    $parts[] = [
        'key' => 'relationship', 'tool' => self::name(),
        'payload' => ['source_entity_id' => $args['source_entity_id'],
                      'target_entity_id' => $targetRef, // null → resolved from depends
                      'relationship_type' => $args['relationship_type'],
                      'start_year' => $args['start_year'] ?? null, 'end_year' => $args['end_year'] ?? null],
        'human_diff' => ['summary' => "Link {$args['relationship_type']} → ".($targetRef ?? $args['new_target']['name'] ?? '?')],
        'depends_on' => $targetRef ? null : 'target',
    ];
    return $parts;
}

public function applyPart(array $payload, array $resolved): array
{
    $targetId = $payload['target_entity_id'] ?? $resolved['depends']; // substituted new entity id
    $data = new RelationshipData(
        sourceEntityId: $payload['source_entity_id'],
        targetEntityId: $targetId,
        relationshipType: RelationshipType::from($payload['relationship_type']),
        temporalStart: isset($payload['start_year']) ? (string) $payload['start_year'] : null,
        temporalEnd: isset($payload['end_year']) ? (string) $payload['end_year'] : null,
    );
    $rel = ($this->create)($data, createdBy: 'agent:'.$resolved['user_id']);
    return ['result_id' => $rel->relationship_id, 'summary' => 'Relationship created'];
}
```

The CreateEntity part is applied by the **already-registered `create_entity` tool** via the registry — no duplication.

- [ ] **Task 6c: `UpdateEntityFields`** — wraps `UpdateEntityAction` (name/summary/significance/type/dates). `buildParts` diffs old→new; `applyPart` builds `EntityData` from the changed fields + existing values and calls `($this->update)($e,$data)` then backfill if dates changed.

- [ ] **Task 6d: `SetEntityWikidata`** — `buildParts` calls `WikidataService::fetch`, **rejects** when P31 looks creative/bogus or label mismatches (namesake guard); `applyPart` updates `wikidata_id` and cascades it into `source_citations`/`entity_geo_refs` (the cleanup we did by hand), then backfill.

- [ ] **Task 6e: `MergeDuplicateEntities`** — `applyPart` ports `pipeline/merge_entities.py` logic into a `MergeEntitiesAction` (re-point relationships with dedup + self-loop removal, `chronicle_entry_entities`, `entity_timeline_entries`, delete loser) and calls it. Create `app/Actions/Entity/MergeEntitiesAction.php` first (with its own test mirroring the Python behavior), then the tool wraps it.

- [ ] **Task 6f: `GetEntityContext` (read-only)** — no proposal; `handle` returns the entity's live name/type/QID/location/dates/relationships so the model grounds itself. `VerifyWikidata` (read-only) returns `WikidataService::fetch($qid)`.

- [ ] **Commit after each sub-task**, e.g. `git commit -am "feat(ai): SetEntityLocation tool"`.

---

## Task 7: Apply/discard endpoints

**Files:**
- Create: `api/app/Http/Controllers/Admin/Ai/AiProposalController.php`
- Modify: `api/routes/web.php`
- Modify: `api/app/Ai/ProposalApplier.php` (inject acting user into `$resolved`)
- Test: `api/tests/Feature/Ai/AiProposalEndpointTest.php`

**Interfaces:**
- Consumes: `ProposalApplier`, `ProposedChangePart`.
- Produces: `POST /ai/proposals/{change}/parts/{key}/apply` and `…/discard`; both return JSON `{status, result_id}`; apply is gated by `permission:entities.write`.

- [ ] **Step 1: Failing feature test**

```php
public function test_applying_a_part_runs_the_action_and_marks_applied(): void
{
    $user = User::factory()->create();              // grant entities.write in the factory/helper
    $change = /* stage a create_entity proposal for $user */;
    $part = $change->parts()->first();

    $this->actingAs($user)
        ->postJson("/ai/proposals/{$change->id}/parts/{$part->key}/apply")
        ->assertOk()->assertJsonPath('status', 'applied');

    $this->assertDatabaseHas('entities', ['entity_id' => $part->fresh()->result_id]);
}
```

- [ ] **Step 2: Run-fail. Step 3: implement controller + routes**

```php
// AiProposalController.php
public function apply(ProposalApplier $applier, string $change, string $key)
{
    $part = ProposedChangePart::where('change_id', $change)->where('key', $key)->firstOrFail();
    $this->authorizeContext($part);             // ensure caller owns the conversation/context
    $applied = $applier->applyPart($part);      // ProposalApplier merges auth()->id() into $resolved['user_id']
    return response()->json(['status' => $applied->status, 'result_id' => $applied->result_id]);
}

public function discard(string $change, string $key)
{
    $part = ProposedChangePart::where('change_id', $change)->where('key', $key)->firstOrFail();
    $part->markDiscarded();
    return response()->json(['status' => 'discarded']);
}
```

```php
// routes/web.php — inside the ['auth','verified'] group
Route::prefix('ai')->name('ai.')->group(function () {
    Route::post('proposals/{change}/parts/{key}/discard', [AiProposalController::class, 'discard'])->name('proposals.discard');
    Route::middleware('permission:entities.write')->group(function () {
        Route::post('proposals/{change}/parts/{key}/apply', [AiProposalController::class, 'apply'])->name('proposals.apply');
    });
});
```

Update `ProposalApplier::applyPart` to set `$resolved['user_id'] = (string) auth()->id();` before calling the tool.

- [ ] **Step 4: Run-pass. Step 5: commit** `feat(ai): proposal apply/discard endpoints`.

---

## Task 8: EntityEditorAgent + chat streaming endpoint

**Files:**
- Create: `api/app/Ai/Agents/EntityEditorAgent.php`, `api/resources/views/ai/instructions/entity-editor.blade.php`
- Create: `api/app/Http/Controllers/Admin/Ai/AiChatController.php`
- Modify: `api/routes/web.php`
- Test: `api/tests/Feature/Ai/AiChatStreamTest.php`

**Interfaces:**
- Consumes: tools from Tasks 5–6, `RemembersConversations`.
- Produces: `POST /ai/chat` → streaming (Vercel protocol) response; resolves `EntityEditorAgent($entity, $user)` for `context_type=entity`.

- [ ] **Step 1: Failing contract test** (mock the LLM call; assert the route returns a streamed response and 200, and that an unknown `context_type` 422s). Keep this a thin contract test — no real provider call.

- [ ] **Step 2–3: implement agent + controller**

```php
// EntityEditorAgent.php — align contract names with installed laravel/ai (Task 1)
class EntityEditorAgent implements Agent, Conversational, HasTools
{
    use Promptable, RemembersConversations;

    public function __construct(public Entity $entity, public User $user) {}

    public function instructions(): string
    {
        return view('ai.instructions.entity-editor', [
            'entity' => $this->entity->loadMissing(['primaryLocation', 'primaryTemporalRange', 'relationships']),
        ])->render();
    }

    public function tools(): iterable
    {
        return [
            app(GetEntityContext::class)->forEntity($this->entity),
            app(CreateEntity::class),
            app(SetEntityLocation::class)->forEntity($this->entity),
            app(CreateRelationship::class)->forEntity($this->entity),
            app(UpdateEntityFields::class)->forEntity($this->entity),
            app(SetEntityWikidata::class)->forEntity($this->entity),
            app(VerifyWikidata::class),
            app(MergeDuplicateEntities::class),
        ];
    }
}
```

```php
// AiChatController.php
public function chat(Request $request)
{
    $data = $request->validate([
        'context_type' => 'required|in:entity,chronicle',
        'context_id' => 'required|string',
        'prompt' => 'required|string',
    ]);

    $agent = match ($data['context_type']) {
        'entity' => new EntityEditorAgent(Entity::findOrFail($data['context_id']), $request->user()),
        'chronicle' => new ChronicleEditorAgent(Chronicle::findOrFail($data['context_id']), $request->user()),
    };

    return $agent->stream($data['prompt'])->usingVercelDataProtocol();
}
```

The Blade instructions template embeds the entity's live state and the rules ("propose, never assert; verify QIDs; use set_entity_location for coordinates; to link to a non-existent entity, pass `new_target`").

Route (in the auth group): `Route::post('ai/chat', [AiChatController::class, 'chat'])->name('ai.chat');`

> The tools' `handle()` needs the conversation context (`user_id`, `context_type`, `context_id`, `conversation_id`). Wire these via the agent (pass context into each tool in `tools()`), or have `handle()` read them from the agent/request. Confirm how `laravel/ai` passes per-call context to a tool's handler (Task 1) and adapt `AgentTool::handle` accordingly.

- [ ] **Step 4–5: run-pass, commit** `feat(ai): EntityEditorAgent + streaming chat endpoint`.

---

## Task 9: ChronicleEditorAgent (scaffold)

- [ ] Create `app/Ai/Agents/ChronicleEditorAgent.php` constructed with `Chronicle`, instructions embedding the chronicle + its entries, tools limited to `GetEntityContext`-equivalent (read) + `CreateRelationship`/`UpdateEntityFields` against linked entities. Mirror Task 8's structure; defer entry-level editing tools (out of scope §7). One contract test, commit.

---

## Task 10: Expose `ai_context` to detail pages

**Files:**
- Modify: `api/app/Http/Controllers/Admin/EntityController.php` (`show`, `edit`), `…/Web/ChronicleController.php`
- Test: `api/tests/Feature/Ai/AiContextPropTest.php`

- [ ] **Step 1: Failing test** — `GET /entities/{id}` Inertia response has prop `ai_context = ['type'=>'entity','id'=>$id]`.

- [ ] **Step 2–3:** add to each `Inertia::render(...)` array:

```php
'ai_context' => ['type' => 'entity', 'id' => $entity->entity_id],
```

(and `['type'=>'chronicle','id'=>$chronicle->id]` in the chronicle controller).

- [ ] **Step 4–5: run-pass, commit** `feat(ai): expose ai_context on detail pages`.

---

## Task 11: Frontend — AI Elements install & chat sidebar

**Files:**
- Modify: `api/package.json` (add `@ai-sdk/react`), install AI Elements components into `resources/js/components/ui/ai/`
- Create: `resources/js/hooks/use-ai-context.ts`, `resources/js/components/ai/ai-sidebar.tsx`, `resources/js/components/ai/proposal-card.tsx`
- Modify: `resources/js/components/nav-main.tsx`

- [ ] **Step 1: Install deps & components**

```bash
docker compose -f docker/docker-compose.yml exec app npm i @ai-sdk/react
# install AI Elements via the shadcn registry (admin already has shadcn + Tailwind 4 + React 19)
docker compose -f docker/docker-compose.yml exec app npx shadcn@latest add @ai-elements/conversation @ai-elements/message @ai-elements/prompt-input @ai-elements/response @ai-elements/tool
```

(If the registry namespace differs, copy components per `elements.ai-sdk.dev/docs`; they're plain React+Tailwind.)

- [ ] **Step 2: `use-ai-context.ts`** — read Inertia props:

```tsx
import { usePage } from '@inertiajs/react';
export type AiContext = { type: 'entity' | 'chronicle'; id: string };
export function useAiContext(): AiContext | null {
  return (usePage().props as { ai_context?: AiContext }).ai_context ?? null;
}
```

- [ ] **Step 3: `ai-sidebar.tsx`** — a `Sheet` (left) hosting `useChat`:

```tsx
import { useChat } from '@ai-sdk/react';
import { Sheet, SheetContent } from '@/components/ui/sheet';
import { Conversation, Message } from '@/components/ui/ai/conversation';
import { PromptInput } from '@/components/ui/ai/prompt-input';
import { ProposalCard } from '@/components/ai/proposal-card';
import { useAiContext } from '@/hooks/use-ai-context';

export function AiSidebar({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const ctx = useAiContext();
  const { messages, sendMessage, status } = useChat({
    api: '/ai/chat',
    body: { context_type: ctx?.type, context_id: ctx?.id },
  });
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="left" className="w-[420px] flex flex-col">
        <Conversation>
          {messages.map((m) => (
            <Message key={m.id} from={m.role}>
              {m.parts.map((p, i) =>
                p.type === 'tool-result' && p.result?.proposal_id
                  ? <ProposalCard key={i} proposal={p.result} />
                  : <span key={i}>{p.type === 'text' ? p.text : null}</span>,
              )}
            </Message>
          ))}
        </Conversation>
        <PromptInput onSubmit={(text) => sendMessage({ text })} disabled={!ctx || status !== 'ready'} />
      </SheetContent>
    </Sheet>
  );
}
```

(Adjust `useChat`/message-part field names to the installed `@ai-sdk/react` version.)

- [ ] **Step 4: `proposal-card.tsx`** — per-part Apply/Discard:

```tsx
import { useState } from 'react';
import { router } from '@inertiajs/react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

export function ProposalCard({ proposal }: { proposal: { proposal_id: string; parts: { key: string; human_diff: { summary: string } }[] } }) {
  const [done, setDone] = useState<Record<string, string>>({});
  async function act(key: string, verb: 'apply' | 'discard') {
    const res = await fetch(`/ai/proposals/${proposal.proposal_id}/parts/${key}/${verb}`, {
      method: 'POST', headers: { 'X-Requested-With': 'XMLHttpRequest' },
    });
    const json = await res.json();
    setDone((d) => ({ ...d, [key]: json.status }));
    if (json.status === 'applied') router.reload();   // refresh the page's Inertia data
  }
  return (
    <Card className="p-3 space-y-2">
      {proposal.parts.map((p) => (
        <div key={p.key} className="flex items-center justify-between gap-2">
          <span className="text-sm">{p.human_diff.summary}</span>
          {done[p.key] ? <span className="text-xs text-muted-foreground">{done[p.key]}</span> : (
            <span className="flex gap-1">
              <Button size="sm" onClick={() => act(p.key, 'apply')}>Apply</Button>
              <Button size="sm" variant="ghost" onClick={() => act(p.key, 'discard')}>Discard</Button>
            </span>
          )}
        </div>
      ))}
    </Card>
  );
}
```

- [ ] **Step 5: nav button** — in `nav-main.tsx`, add a "✨ Ask AI" button that toggles sidebar state (lift state to the layout or a context). Render `<AiSidebar>` once in the admin layout.

- [ ] **Step 6: Lint/types & manual smoke**

Run: `docker compose -f docker/docker-compose.yml exec app npm run lint && docker compose -f docker/docker-compose.yml exec app npm run types:check`
Manual: open an entity page → Ask AI → "this is in Luxor not the Netherlands" → confirm a `set_entity_location` proposal card appears → Apply → page reloads with the new location.

- [ ] **Step 7: Commit** `feat(ai): admin AI chat sidebar with AI Elements + proposal cards`.

---

## Task 12: Retention prune & docs

**Files:**
- Create: `api/app/Console/Commands/PruneAgentProposals.php`
- Modify: `api/routes/console.php` (schedule), `docs/implementation-docs/README.md`, new `docs/implementation-docs/admin-ai-agent.md`

- [ ] **Step 1:** Command deletes `pending|discarded` parts/changes older than 7 days, `applied` older than 1 year, chat conversations older than 90 days. Test it with seeded timestamps.
- [ ] **Step 2:** Schedule daily in `routes/console.php`: `Schedule::command('ai:prune-proposals')->daily();`
- [ ] **Step 3:** Write `admin-ai-agent.md` (operator guide: how to use, the propose→apply flow, the tool list, provenance `agent:*`, spend cap) and index it in the implementation-docs README.
- [ ] **Step 4: commit** `chore(ai): retention prune + operator docs`.

---

## Self-Review notes

- **Spec coverage:** agents (T8/9), tools incl. CreateEntity-primary (T5/6), propose→confirm + partial apply (T2/4/7/11), WikidataService namesake guard (T3/6d), OpenRouter+model (T1), AI Elements UI (T11), auth gate (T7), retention (T12), audit/undo via the parts table (T2). Merge ported to a real Action (T6e).
- **Provenance** `agent:{user_id}` threaded from `auth()->id()` (T7) into every `applyPart` (T5/6).
- **SDK-contract risk** is called out in T1/T4/T8 — verify `laravel/ai`'s exact `Tool`/`Agent` method names against the installed version and adapt the two seams (`AgentTool::handle` signature, how per-call context reaches the tool).
