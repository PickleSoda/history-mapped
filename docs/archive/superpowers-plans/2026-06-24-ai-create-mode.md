# AI on Create Pages + Chronicle Entry Editing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the admin AI sidebar usable on the create pages (create entities & chronicles via AI), and add AI create/edit of chronicle entries on the chronicle edit page.

**Architecture:** Extend `ai_context` with a `mode: 'edit'|'create'`; the chat controller branches to new record-less `EntityCreatorAgent`/`ChronicleCreatorAgent` whose only tools create records (new `CreateChronicle` wraps the existing `CreateChronicleAction`). Apply returns a server-computed `redirect_url` so create-mode lands on the new record's edit page. Phase 2 adds `ChronicleEntry` Actions + tools to the existing edit-mode `ChronicleEditorAgent`. Reuses the merged AI pipeline (AgentTool base, propose→confirm→partial-apply, gated endpoints).

**Tech Stack:** PHP 8.4 / Laravel 13, `laravel/ai`, Inertia + React 19, `@ai-sdk/react`. All backend cmds run in the Docker `app` container.

## Global Constraints

- Backend cmds: `docker compose -f docker/docker-compose.yml exec app <cmd>`. Restart `app` after editing existing files.
- Write logic lives in **Action classes**; tools wrap Actions. Tools stage proposals via `AgentTool` base — they never mutate domain data; only `/ai/proposals/.../apply` does.
- Provenance: applied creates use `createdBy = 'agent:'.$resolved['user_id']`.
- `/ai/chat` and `/ai/proposals/.../apply` are gated by `permission:entities.write` (admin bypasses via `Gate::before`). Unchanged here.
- `ai_context` shape: `{ type: 'entity'|'chronicle', id: string|null, mode: 'edit'|'create' }`; `mode` defaults to `'edit'` (existing pages unaffected).
- Create-mode proposals stage under sentinel `context_id = 'create'` (apply authorizes on `ProposedChange.user_id`, not `context_id`).
- `chronicles.edit` route binds by **slug**; `entities.edit` binds by **id** — compute chronicle redirect via the new chronicle's `slug` server-side.
- ChronicleCreatorAgent must NOT silently drop entry requests — its instructions tell the user entries are added on the edit page.
- Pint clean (`./vendor/bin/pint --test`); admin JS: `npm run lint:check`, `npm run types:check`, `npm run build` clean. TDD throughout.

## AgentTool contract (from the merged feature)

Concrete tools extend `App\Ai\Tools\AgentTool` and implement: `static name(): string`, `description(): Stringable|string`, `schema(JsonSchema $schema): array`, `buildParts(array $args): array` (each part `{key, tool, payload, human_diff, depends_on?}`), `applyPart(array $payload, array $resolved): array` (returns `{result_id, summary}`, reads `$resolved['user_id']`). Base provides `handle()` (stages a `ProposedChange`) + `withContext(array): static`. Register each tool in `app/Providers/AppServiceProvider.php` `boot()` via `app(ToolRegistry::class)->register(Tool::name(), Tool::class)`.

---

## File Structure

**Phase 1**
- Create: `api/app/Ai/Tools/CreateChronicle.php`
- Create: `api/app/Ai/Agents/EntityCreatorAgent.php`, `ChronicleCreatorAgent.php`
- Create: `api/resources/views/ai/instructions/entity-creator.blade.php`, `chronicle-creator.blade.php`
- Modify: `api/app/Http/Controllers/Admin/Ai/AiChatController.php` (mode branch)
- Modify: `api/app/Http/Controllers/Admin/Ai/AiProposalController.php` (redirect_url)
- Modify: `api/app/Http/Controllers/Admin/EntityController.php`, `api/app/Http/Controllers/Web/ChronicleController.php` (create() ai_context)
- Modify: `api/resources/js/hooks/use-ai-context.ts`, `components/ai/ai-sidebar.tsx`, `components/ai/proposal-card.tsx`
- Modify: `api/app/Providers/AppServiceProvider.php` (register CreateChronicle)

**Phase 2**
- Create: `api/app/DTOs/ChronicleEntryData.php`
- Create: `api/app/Actions/Chronicle/CreateChronicleEntryAction.php`, `UpdateChronicleEntryAction.php`
- Create: `api/app/Ai/Tools/CreateChronicleEntry.php`, `UpdateChronicleEntry.php`
- Modify: `api/app/Ai/Agents/ChronicleEditorAgent.php` (+ tools), its Blade instructions
- Modify: `api/app/Providers/AppServiceProvider.php` (register the two entry tools)

---

## Task 1: `CreateChronicle` tool

**Files:**
- Create: `api/app/Ai/Tools/CreateChronicle.php`
- Modify: `api/app/Providers/AppServiceProvider.php`
- Test: `api/tests/Feature/Ai/CreateChronicleToolTest.php`

**Interfaces:**
- Consumes: `AgentTool`, `App\Actions\Chronicle\CreateChronicleAction::__invoke(ChronicleData, ?string $createdBy): Chronicle`, `App\DTOs\ChronicleData(title, slug?, sourceType?, sourceReference?, status=ChronicleStatus::Draft, startYear?, endYear?, …)`, `App\Enums\ChronicleStatus`.
- Produces: tool name `create_chronicle`; `applyPart` returns `result_id = chronicle_id`.

- [ ] **Step 1: Write the failing test**

```php
<?php
namespace Tests\Feature\Ai;

use App\Ai\Tools\CreateChronicle;
use App\Models\Chronicle;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class CreateChronicleToolTest extends TestCase
{
    use RefreshDatabase;

    public function test_build_then_apply_creates_a_chronicle_with_agent_provenance(): void
    {
        $tool = app(CreateChronicle::class);

        $parts = $tool->buildParts([
            'title' => 'The Punic Wars', 'summary' => 'Rome vs Carthage',
            'start_year' => -264, 'end_year' => -146,
        ]);
        $this->assertCount(1, $parts);
        $this->assertSame('create_chronicle', $parts[0]['tool']);

        $result = $tool->applyPart($parts[0]['payload'], ['user_id' => 'u1']);
        $chronicle = Chronicle::findOrFail($result['result_id']);

        $this->assertSame('The Punic Wars', $chronicle->title);
        $this->assertSame(-264, $chronicle->start_year);
        $this->assertSame('agent:u1', $chronicle->created_by);
    }
}
```

- [ ] **Step 2: Run it, expect failure.** `… php artisan test --filter CreateChronicleToolTest` → FAIL (class missing).

- [ ] **Step 3: Implement the tool**

```php
<?php
namespace App\Ai\Tools;

use App\Actions\Chronicle\CreateChronicleAction;
use App\DTOs\ChronicleData;
use App\Enums\ChronicleStatus;
use App\Models\Chronicle;
use Illuminate\Contracts\JsonSchema\JsonSchema;

class CreateChronicle extends AgentTool
{
    public function __construct(private CreateChronicleAction $create) {}

    public static function name(): string
    {
        return 'create_chronicle';
    }

    public function description(): string
    {
        return 'Create a new chronicle (a narrative timeline). Sets title, summary, status and an optional year range. Entries are added afterward on the chronicle edit page — do NOT attempt to add entries here.';
    }

    public function schema(JsonSchema $schema): array
    {
        return [
            'title' => $schema->string()->description('Chronicle title')->required(),
            'summary' => $schema->string()->description('Short description / narrative summary'),
            'start_year' => $schema->integer()->description('Signed year, BCE negative'),
            'end_year' => $schema->integer(),
            'source_reference' => $schema->string()->description('Optional source citation'),
        ];
    }

    public function buildParts(array $args): array
    {
        return [[
            'key' => 'chronicle',
            'tool' => self::name(),
            'payload' => $args,
            'human_diff' => [
                'summary' => "Create chronicle “{$args['title']}”".(isset($args['start_year']) ? " ({$args['start_year']}–".($args['end_year'] ?? '…').')' : ''),
                'fields' => $args,
            ],
        ]];
    }

    public function applyPart(array $payload, array $resolved): array
    {
        $data = new ChronicleData(
            title: $payload['title'],
            sourceReference: $payload['source_reference'] ?? null,
            status: ChronicleStatus::Draft,
            startYear: $payload['start_year'] ?? null,
            endYear: $payload['end_year'] ?? null,
            metadata: isset($payload['summary']) ? ['summary' => $payload['summary']] : null,
        );

        /** @var Chronicle $chronicle */
        $chronicle = ($this->create)($data, createdBy: 'agent:'.$resolved['user_id']);

        return ['result_id' => $chronicle->chronicle_id, 'summary' => "Created chronicle {$chronicle->title}"];
    }
}
```

> Verify `ChronicleData`'s field for the summary text (the DTO has `metadata` + `title`; confirm whether there's a dedicated `summary`/`description` column on `chronicles` and map accordingly — adjust the `ChronicleData` args to the real columns. Read `ChronicleData` + the chronicles migration before finalizing). Use the real `ChronicleStatus` case for a draft.

- [ ] **Step 4: Register in `AppServiceProvider::boot()`**

```php
app(\App\Ai\ToolRegistry::class)->register(\App\Ai\Tools\CreateChronicle::name(), \App\Ai\Tools\CreateChronicle::class);
```

- [ ] **Step 5: Run the test** → PASS. Run `./vendor/bin/pint`.
- [ ] **Step 6: Commit** `git commit -am "feat(ai): CreateChronicle tool"`.

---

## Task 2: Creator agents

**Files:**
- Create: `api/app/Ai/Agents/EntityCreatorAgent.php`, `ChronicleCreatorAgent.php`
- Create: `api/resources/views/ai/instructions/entity-creator.blade.php`, `chronicle-creator.blade.php`
- Test: `api/tests/Feature/Ai/CreatorAgentsTest.php`

**Interfaces:**
- Consumes: `CreateEntity`, `VerifyWikidata`, `CreateChronicle` tools; `AgentTool::withContext()`.
- Produces: `EntityCreatorAgent(User $user, array $context)`, `ChronicleCreatorAgent(User $user, array $context)` — both implement `Agent, Conversational, HasTools` with `Promptable, RemembersConversations`; `tools()` returns creation-only tools each `->withContext($this->context)`.

- [ ] **Step 1: Write the failing test**

```php
<?php
namespace Tests\Feature\Ai;

use App\Ai\Agents\ChronicleCreatorAgent;
use App\Ai\Agents\EntityCreatorAgent;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class CreatorAgentsTest extends TestCase
{
    use RefreshDatabase;

    private function ctx(): array
    {
        return ['user_id' => 'u1', 'context_type' => 'entity', 'context_id' => 'create', 'conversation_id' => null];
    }

    public function test_entity_creator_exposes_only_creation_tools_with_context(): void
    {
        $agent = new EntityCreatorAgent(User::factory()->create(), $this->ctx());
        $names = array_map(fn ($t) => $t::name(), array_filter(
            iterator_to_array((function () use ($agent) { yield from $agent->tools(); })()),
            fn ($t) => method_exists($t, 'name'),
        ));
        $this->assertContains('create_entity', $names);
        $this->assertContains('verify_wikidata', $names);
        $this->assertNotContains('merge_duplicate_entities', $names);

        // context injected on the staging tool
        $createEntity = collect($agent->tools())->first(fn ($t) => $t::name() === 'create_entity');
        $ref = new \ReflectionProperty($createEntity, 'context');
        $ref->setAccessible(true);
        $this->assertSame('u1', $ref->getValue($createEntity)['user_id']);
    }

    public function test_chronicle_creator_instructions_explain_entry_handoff(): void
    {
        $agent = new ChronicleCreatorAgent(User::factory()->create(), ['user_id' => 'u1', 'context_type' => 'chronicle', 'context_id' => 'create', 'conversation_id' => null]);
        $instructions = $agent->instructions();
        $this->assertStringContainsStringIgnoringCase('entr', $instructions); // mentions entries
        $this->assertStringContainsStringIgnoringCase('edit', $instructions);  // points to the edit page
        $names = array_map(fn ($t) => $t::name(), iterator_to_array((function () use ($agent) { yield from $agent->tools(); })()));
        $this->assertContains('create_chronicle', $names);
    }
}
```

- [ ] **Step 2: Run it, expect failure.**

- [ ] **Step 3: Implement the agents + Blade templates**

```php
// app/Ai/Agents/EntityCreatorAgent.php
<?php
namespace App\Ai\Agents;

use App\Ai\Tools\CreateEntity;
use App\Ai\Tools\VerifyWikidata;
use App\Models\User;
use Laravel\Ai\Concerns\RemembersConversations;
use Laravel\Ai\Contracts\Agent;
use Laravel\Ai\Contracts\Conversational;
use Laravel\Ai\Contracts\HasTools;
use Laravel\Ai\Promptable;

class EntityCreatorAgent implements Agent, Conversational, HasTools
{
    use Promptable, RemembersConversations;

    /** @param array{user_id:string,context_type:string,context_id:string,conversation_id:?string} $context */
    public function __construct(public User $user, public array $context = []) {}

    public function instructions(): string
    {
        return view('ai.instructions.entity-creator')->render();
    }

    public function tools(): iterable
    {
        return [
            app(CreateEntity::class)->withContext($this->context),
            app(VerifyWikidata::class),
        ];
    }
}
```

```php
// app/Ai/Agents/ChronicleCreatorAgent.php
<?php
namespace App\Ai\Agents;

use App\Ai\Tools\CreateChronicle;
use App\Models\User;
use Laravel\Ai\Concerns\RemembersConversations;
use Laravel\Ai\Contracts\Agent;
use Laravel\Ai\Contracts\Conversational;
use Laravel\Ai\Contracts\HasTools;
use Laravel\Ai\Promptable;

class ChronicleCreatorAgent implements Agent, Conversational, HasTools
{
    use Promptable, RemembersConversations;

    /** @param array{user_id:string,context_type:string,context_id:string,conversation_id:?string} $context */
    public function __construct(public User $user, public array $context = []) {}

    public function instructions(): string
    {
        return view('ai.instructions.chronicle-creator')->render();
    }

    public function tools(): iterable
    {
        return [
            app(CreateChronicle::class)->withContext($this->context),
        ];
    }
}
```

`resources/views/ai/instructions/entity-creator.blade.php`:

```blade
You help the operator create a NEW historical entity in this atlas.

Rules:
- You PROPOSE a change; the operator clicks Apply to create it. You never create directly.
- Gather a name and entity_type. Use verify_wikidata to confirm a QID before passing wikidata_id (reject wrong namesakes — songs, streets, etc.).
- You may include a representative location (lon/lat) and a year range in the same create_entity proposal.
- After the entity is created the operator is taken to its edit page, where further changes (relationships, precise location) are made. Do not attempt those here.
```

`resources/views/ai/instructions/chronicle-creator.blade.php`:

```blade
You help the operator create a NEW chronicle (a narrative timeline) in this atlas.

Rules:
- You PROPOSE a change; the operator clicks Apply to create it. You never create directly.
- Gather a title, an optional summary, and an optional year range, then use create_chronicle.
- IMPORTANT: chronicle ENTRIES are not created here. If the operator asks to add entries while creating the chronicle, create the chronicle first with create_chronicle, then tell them the entries can be added next on the chronicle's edit page (where the AI can create and edit entries). Never silently ignore an entry request.
```

- [ ] **Step 4: Run the test** → PASS. Pint.
- [ ] **Step 5: Commit** `git commit -am "feat(ai): entity & chronicle creator agents"`.

---

## Task 3: Chat controller create-mode branch

**Files:**
- Modify: `api/app/Http/Controllers/Admin/Ai/AiChatController.php`
- Test: `api/tests/Feature/Ai/AiChatStreamTest.php` (extend)

**Interfaces:**
- Consumes: `EntityCreatorAgent`, `ChronicleCreatorAgent`.
- Produces: `/ai/chat` accepts `mode` (`edit`|`create`, default `edit`); create mode builds a creator agent with sentinel `context_id='create'`, no `findOrFail`.

- [ ] **Step 1: Failing test** — as an `entities.write` user, POST `/ai/chat` with `{context_type:'entity', mode:'create', messages:[{role:'user',parts:[{type:'text',text:'create the Maya civilization'}]}]}` (NO context_id) → assert 200 stream. Same for `context_type:'chronicle'`. And edit mode without context_id → 422.

- [ ] **Step 2: Run-fail. Step 3: implement the branch**

Add to the validator: `'mode' => 'nullable|in:edit,create'`. After deriving `$promptText` and `$user`:

```php
$mode = $data['mode'] ?? 'edit';

if ($mode === 'edit' && empty($data['context_id'])) {
    abort(422, 'context_id is required in edit mode.');
}

$contextId = $mode === 'create' ? 'create' : $data['context_id'];

$context = [
    'user_id' => (string) $user->id,
    'context_type' => $data['context_type'],
    'context_id' => $contextId,
    'conversation_id' => $conversationId,
];

$agent = match (true) {
    $mode === 'create' && $data['context_type'] === 'entity' => new EntityCreatorAgent($user, $context),
    $mode === 'create' && $data['context_type'] === 'chronicle' => new ChronicleCreatorAgent($user, $context),
    $data['context_type'] === 'entity' => new EntityEditorAgent(Entity::findOrFail($contextId), $user, $context),
    $data['context_type'] === 'chronicle' => new ChronicleEditorAgent(Chronicle::findOrFail($contextId), $user, $context),
};
```

Keep the existing `continue`/`forUser` + `stream()->usingVercelDataProtocol()`. Add `use` imports for the creator agents.

- [ ] **Step 4: Run-pass. Step 5: commit** `feat(ai): chat controller create-mode branch`.

---

## Task 4: Create-page `ai_context` props

**Files:**
- Modify: `api/app/Http/Controllers/Admin/EntityController.php` (`create`)
- Modify: `api/app/Http/Controllers/Web/ChronicleController.php` (`create`)
- Test: `api/tests/Feature/Ai/AiContextPropTest.php` (extend)

- [ ] **Step 1: Failing test** — `GET` the entities.create route → Inertia prop `ai_context = ['type'=>'entity','id'=>null,'mode'=>'create']`; chronicles.create → `['type'=>'chronicle','id'=>null,'mode'=>'create']`.

- [ ] **Step 2–3:** add to each `create()` `Inertia::render(...)` props:

```php
'ai_context' => ['type' => 'entity', 'id' => null, 'mode' => 'create'],
```

(and `['type' => 'chronicle', 'id' => null, 'mode' => 'create']`).

- [ ] **Step 4: Run-pass. Step 5: commit** `feat(ai): expose create-mode ai_context on create pages`.

---

## Task 5: Apply endpoint `redirect_url` for record-creator parts

**Files:**
- Modify: `api/app/Http/Controllers/Admin/Ai/AiProposalController.php`
- Test: `api/tests/Feature/Ai/AiProposalEndpointTest.php` (extend)

**Interfaces:**
- Produces: apply response JSON gains `redirect_url` (string|null) when the applied part's tool created a top-level record.

- [ ] **Step 1: Failing test** — stage+apply a `create_chronicle` proposal (owned by an `entities.write` user) → response `redirect_url` equals `route('chronicles.edit', <new chronicle slug>)`. Stage+apply a `create_entity` proposal → `redirect_url` equals `route('entities.edit', <new entity id>)`. A non-creator part (e.g. set_entity_location) → `redirect_url` is null.

- [ ] **Step 2: Run-fail. Step 3: implement** — after `$applied = $applier->applyPart($part);` in `apply()`:

```php
$redirectUrl = match ($applied->tool) {
    'create_entity' => route('entities.edit', $applied->result_id),
    'create_chronicle' => route('chronicles.edit', \App\Models\Chronicle::findOrFail($applied->result_id)->slug),
    default => null,
};

return response()->json([
    'status' => $applied->status,
    'result_id' => $applied->result_id,
    'redirect_url' => $redirectUrl,
]);
```

- [ ] **Step 4: Run-pass. Step 5: commit** `feat(ai): apply returns redirect_url for created records`.

---

## Task 6: Frontend create-mode (context, sidebar, redirect)

**Files:**
- Modify: `api/resources/js/hooks/use-ai-context.ts`
- Modify: `api/resources/js/components/ai/ai-sidebar.tsx`
- Modify: `api/resources/js/components/ai/proposal-card.tsx`
- Test: `api/resources/js/hooks/__tests__/use-ai-context.test.tsx`, `components/__tests__/proposal-card.test.tsx` (extend)

**Interfaces:**
- Produces: `AiContext = { type:'entity'|'chronicle'; id: string|null; mode: 'edit'|'create' }`.

- [ ] **Step 1: Failing tests** — `useAiContext` returns `{type,id:null,mode:'create'}` when the prop has `mode:'create'` and null id; defaults `mode` to `'edit'` when absent; still null on unknown type. `ProposalCard`: when `mode==='create'` and the apply response has `redirect_url`, it calls `router.visit(redirect_url)` (not `router.reload()`).

- [ ] **Step 2: Run-fail. Step 3: implement**

`use-ai-context.ts`:

```ts
import { usePage } from '@inertiajs/react';

export type AiContext = { type: 'entity' | 'chronicle'; id: string | null; mode: 'edit' | 'create' };

export function useAiContext(): AiContext | null {
    const ctx = (usePage().props as { ai_context?: { type?: unknown; id?: unknown; mode?: unknown } }).ai_context;
    if (!ctx || (ctx.type !== 'entity' && ctx.type !== 'chronicle')) {
        return null;
    }
    const mode = ctx.mode === 'create' ? 'create' : 'edit';
    if (mode === 'edit' && typeof ctx.id !== 'string') {
        return null;
    }
    return { type: ctx.type, id: typeof ctx.id === 'string' ? ctx.id : null, mode };
}
```

`ai-sidebar.tsx` — send `mode` and (nullable) `context_id` in the transport body, and pass `mode` to `ProposalCard`. The transport `body` becomes:

```ts
body: aiCtx ? { context_type: aiCtx.type, context_id: aiCtx.id, mode: aiCtx.mode } : {},
```

and where `<ProposalCard>` is rendered, pass `mode={aiCtx?.mode ?? 'edit'}`.

`proposal-card.tsx` — accept a `mode` prop; in `act()` on apply success:

```ts
const json = await res.json();
setPartStatus((s) => ({ ...s, [key]: json.status }));
if (json.status === 'applied') {
    if (mode === 'create' && typeof json.redirect_url === 'string') {
        router.visit(json.redirect_url);
    } else {
        router.reload();
    }
}
```

(Add `mode: 'edit' | 'create'` to the component's props type; default `'edit'`.)

- [ ] **Step 4: Run-pass** (`npx vitest run` the two files). Then `npm run lint:check`, `npm run types:check`, `npm run build` — all clean.
- [ ] **Step 5: Commit** `feat(ai): create-mode sidebar context + redirect-after-create`.

---

## Task 7: `ChronicleEntryData` DTO + `CreateChronicleEntryAction`

**Files:**
- Create: `api/app/DTOs/ChronicleEntryData.php`
- Create: `api/app/Actions/Chronicle/CreateChronicleEntryAction.php`
- Test: `api/tests/Feature/Chronicle/CreateChronicleEntryActionTest.php`

**Interfaces:**
- Produces: `ChronicleEntryData(?string $narrativeText, ?string $notes = null, ?array $entityIds = null, ?string $primaryRelationshipId = null)`; `CreateChronicleEntryAction::__invoke(string $chronicleId, ChronicleEntryData $data, ?string $createdBy = null): ChronicleEntry`.

- [ ] **Step 1: Failing test**

```php
<?php
namespace Tests\Feature\Chronicle;

use App\Actions\Chronicle\CreateChronicleEntryAction;
use App\DTOs\ChronicleEntryData;
use App\Models\Chronicle;
use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class CreateChronicleEntryActionTest extends TestCase
{
    use RefreshDatabase;

    public function test_creates_entry_with_narrative_and_linked_entities(): void
    {
        $chronicle = Chronicle::factory()->create();
        $e1 = Entity::factory()->create();
        $e2 = Entity::factory()->create();

        $entry = app(CreateChronicleEntryAction::class)(
            $chronicle->chronicle_id,
            new ChronicleEntryData(narrativeText: 'Rome defeats Carthage.', entityIds: [$e1->entity_id, $e2->entity_id]),
            createdBy: 'agent:u1',
        );

        $this->assertSame('Rome defeats Carthage.', $entry->narrative_text);
        $this->assertSame($chronicle->chronicle_id, $entry->chronicle_id);
        $this->assertEqualsCanonicalizing(
            [$e1->entity_id, $e2->entity_id],
            $entry->secondaryEntities()->pluck('entities.entity_id')->all(),
        );
    }
}
```

- [ ] **Step 2: Run-fail. Step 3: implement the DTO + Action**

```php
// app/DTOs/ChronicleEntryData.php
<?php
declare(strict_types=1);
namespace App\DTOs;

readonly class ChronicleEntryData
{
    /** @param list<string>|null $entityIds */
    public function __construct(
        public ?string $narrativeText = null,
        public ?string $notes = null,
        public ?array $entityIds = null,
        public ?string $primaryRelationshipId = null,
    ) {}
}
```

```php
// app/Actions/Chronicle/CreateChronicleEntryAction.php
<?php
declare(strict_types=1);
namespace App\Actions\Chronicle;

use App\DTOs\ChronicleEntryData;
use App\Models\ChronicleEntry;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

class CreateChronicleEntryAction
{
    public function __invoke(string $chronicleId, ChronicleEntryData $data, ?string $createdBy = null): ChronicleEntry
    {
        return DB::transaction(function () use ($chronicleId, $data, $createdBy): ChronicleEntry {
            $entry = ChronicleEntry::create([
                'entry_id' => (string) Str::uuid(),
                'chronicle_id' => $chronicleId,
                'narrative_text' => $data->narrativeText,
                'notes' => $data->notes,
                'primary_relationship_id' => $data->primaryRelationshipId,
                'generated_by' => $createdBy ?? 'agent',
            ]);

            if ($data->entityIds !== null) {
                $entry->secondaryEntities()->sync($data->entityIds);
            }

            return $entry;
        });
    }
}
```

> Verify the `chronicle_entries` columns and the `secondaryEntities` pivot name before finalizing (read the model + migration); `generated_by` is the entry's provenance column.

- [ ] **Step 4: Run-pass. Step 5: commit** `feat(chronicle): CreateChronicleEntryAction + ChronicleEntryData`.

---

## Task 8: `UpdateChronicleEntryAction`

**Files:**
- Create: `api/app/Actions/Chronicle/UpdateChronicleEntryAction.php`
- Test: `api/tests/Feature/Chronicle/UpdateChronicleEntryActionTest.php`

**Interfaces:**
- Produces: `UpdateChronicleEntryAction::__invoke(ChronicleEntry $entry, ChronicleEntryData $data): ChronicleEntry` — updates only supplied fields; re-syncs entity links only when `entityIds` is provided.

- [ ] **Step 1: Failing test** — create an entry with narrative "A" + entity e1; update with `new ChronicleEntryData(narrativeText: 'B')` (no entityIds) → narrative is "B" AND e1 still linked (links preserved when entityIds null). Then update with `entityIds: [e2]` → links become exactly [e2].

- [ ] **Step 2: Run-fail. Step 3: implement**

```php
<?php
declare(strict_types=1);
namespace App\Actions\Chronicle;

use App\DTOs\ChronicleEntryData;
use App\Models\ChronicleEntry;
use Illuminate\Support\Facades\DB;

class UpdateChronicleEntryAction
{
    public function __invoke(ChronicleEntry $entry, ChronicleEntryData $data): ChronicleEntry
    {
        return DB::transaction(function () use ($entry, $data): ChronicleEntry {
            $entry->fill(array_filter([
                'narrative_text' => $data->narrativeText,
                'notes' => $data->notes,
                'primary_relationship_id' => $data->primaryRelationshipId,
            ], fn ($v) => $v !== null));
            $entry->save();

            if ($data->entityIds !== null) {
                $entry->secondaryEntities()->sync($data->entityIds);
            }

            return $entry->refresh();
        });
    }
}
```

- [ ] **Step 4: Run-pass. Step 5: commit** `feat(chronicle): UpdateChronicleEntryAction`.

---

## Task 9: Entry tools on the edit-mode `ChronicleEditorAgent`

**Files:**
- Create: `api/app/Ai/Tools/CreateChronicleEntry.php`, `UpdateChronicleEntry.php`
- Modify: `api/app/Ai/Agents/ChronicleEditorAgent.php`, `api/resources/views/ai/instructions/chronicle-editor.blade.php`
- Modify: `api/app/Providers/AppServiceProvider.php`
- Test: `api/tests/Feature/Ai/ChronicleEntryToolsTest.php`

**Interfaces:**
- Consumes: `CreateChronicleEntryAction`, `UpdateChronicleEntryAction`, `ChronicleEntryData`.
- Produces: tools `create_chronicle_entry`, `update_chronicle_entry`.

- [ ] **Step 1: Failing test** — `CreateChronicleEntry`: `buildParts({chronicle_id, narrative_text, entity_ids})` → one part; `applyPart` creates an entry on that chronicle linked to the entities, returns `result_id = entry_id`. `UpdateChronicleEntry`: `applyPart({entry_id, narrative_text})` updates the entry, links preserved. And assert `ChronicleEditorAgent::tools()` now includes `create_chronicle_entry`/`update_chronicle_entry` with context injected.

- [ ] **Step 2: Run-fail. Step 3: implement the two tools**

```php
// app/Ai/Tools/CreateChronicleEntry.php
<?php
namespace App\Ai\Tools;

use App\Actions\Chronicle\CreateChronicleEntryAction;
use App\DTOs\ChronicleEntryData;
use Illuminate\Contracts\JsonSchema\JsonSchema;

class CreateChronicleEntry extends AgentTool
{
    public function __construct(private CreateChronicleEntryAction $create) {}

    public static function name(): string { return 'create_chronicle_entry'; }

    public function description(): string
    {
        return 'Add a narrative entry to a chronicle, optionally linking the entities it concerns.';
    }

    public function schema(JsonSchema $schema): array
    {
        return [
            'chronicle_id' => $schema->string()->description('Chronicle to add the entry to')->required(),
            'narrative_text' => $schema->string()->description('The entry narrative')->required(),
            'entity_ids' => $schema->array()->description('Entity ids this entry concerns'),
            'notes' => $schema->string(),
        ];
    }

    public function buildParts(array $args): array
    {
        return [[
            'key' => 'entry',
            'tool' => self::name(),
            'payload' => $args,
            'human_diff' => ['summary' => 'Add chronicle entry: '.\Illuminate\Support\Str::limit($args['narrative_text'], 60)],
        ]];
    }

    public function applyPart(array $payload, array $resolved): array
    {
        $entry = ($this->create)(
            $payload['chronicle_id'],
            new ChronicleEntryData(
                narrativeText: $payload['narrative_text'],
                notes: $payload['notes'] ?? null,
                entityIds: $payload['entity_ids'] ?? null,
            ),
            createdBy: 'agent:'.$resolved['user_id'],
        );

        return ['result_id' => $entry->entry_id, 'summary' => 'Entry added'];
    }
}
```

```php
// app/Ai/Tools/UpdateChronicleEntry.php
<?php
namespace App\Ai\Tools;

use App\Actions\Chronicle\UpdateChronicleEntryAction;
use App\DTOs\ChronicleEntryData;
use App\Models\ChronicleEntry;
use Illuminate\Contracts\JsonSchema\JsonSchema;

class UpdateChronicleEntry extends AgentTool
{
    public function __construct(private UpdateChronicleEntryAction $update) {}

    public static function name(): string { return 'update_chronicle_entry'; }

    public function description(): string
    {
        return 'Edit an existing chronicle entry: narrative, notes, or which entities it links.';
    }

    public function schema(JsonSchema $schema): array
    {
        return [
            'entry_id' => $schema->string()->description('The chronicle entry to edit')->required(),
            'narrative_text' => $schema->string(),
            'notes' => $schema->string(),
            'entity_ids' => $schema->array()->description('Replaces the linked entities when provided'),
        ];
    }

    public function buildParts(array $args): array
    {
        return [[
            'key' => 'entry',
            'tool' => self::name(),
            'payload' => $args,
            'human_diff' => ['summary' => 'Edit chronicle entry '.$args['entry_id'], 'fields' => $args],
        ]];
    }

    public function applyPart(array $payload, array $resolved): array
    {
        $entry = ChronicleEntry::findOrFail($payload['entry_id']);
        ($this->update)($entry, new ChronicleEntryData(
            narrativeText: $payload['narrative_text'] ?? null,
            notes: $payload['notes'] ?? null,
            entityIds: $payload['entity_ids'] ?? null,
        ));

        return ['result_id' => $entry->entry_id, 'summary' => 'Entry updated'];
    }
}
```

- [ ] **Step 4: Register both in `AppServiceProvider::boot()`** and add to `ChronicleEditorAgent::tools()` each `->withContext($this->context)`. Add one line to `chronicle-editor.blade.php` instructions: "You can add entries with create_chronicle_entry and edit them with update_chronicle_entry (link the entities each entry concerns by id)."

- [ ] **Step 5: Run-pass.** Pint. `… php artisan test --filter "Ai|Chronicle"` → no regressions.
- [ ] **Step 6: Commit** `feat(ai): chronicle entry create/edit tools on the editor agent`.

---

## Self-Review notes

- **Spec coverage:** create-mode context (T6), chat branch (T3), creator agents incl. entry-handoff communication (T2, instructions + test), CreateChronicle (T1), redirect-after-apply with slug resolution (T5+T6), create-page props (T4); Phase 2 entry Actions (T7/T8) + tools on edit agent (T9). Deferred-inline-entries decision honored (CreateChronicle has no entries field; ChronicleCreatorAgent communicates the hand-off).
- **Verify-before-finalize flags:** T1 (ChronicleData summary column mapping + ChronicleStatus case), T7 (chronicle_entries columns + secondaryEntities pivot). These read existing code; adjust to real names.
- **Type consistency:** `ai_context` `{type,id,mode}` consistent across T4/T6; sentinel `context_id='create'` (T3) matches `ProposedChange` NOT NULL; `redirect_url` (T5) consumed in T6; `ChronicleEntryData` signature identical across T7/T8/T9.
