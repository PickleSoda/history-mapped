# Create with AI Page — Phase B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `GlobalAgent` (full-toolset AI backend), a `kind=global` branch in the chat controller, a `created_ref` on global-mode applies, a new two-pane "Create with AI" Inertia page, and a nav entry — so users can open a persistent global session and create/edit any record without being on a record page.

**Architecture:** Phase A landed the sessions backbone (context columns, `X-Conversation-Id`, `AiSessionController` list/show/destroy). Phase B adds the global surface on top of it. `GlobalAgent` mirrors the existing editor-agent pattern (implements `Agent, Conversational, HasTools`; full registered toolset + `withContext()`). The chat controller gains a `kind=global` input that bypasses the `context_type`/`context_id` validation and routes to `GlobalAgent`. The apply endpoint gains a `created_ref` field (used in the new page instead of `redirect_url`). The page is a React two-pane layout: a left session-list (all user sessions from `GET /ai/sessions`) plus a right chat panel that reuses the sidebar's `Chat`/`useChat`/`ProposalCard` primitives — no sidebar on this page. A nav entry in `app-sidebar.tsx` links to `/ai` (route `ai.index`).

**Phase B builds on (must be complete):**
- Phase A: `agent_conversations.context_type` / `context_id` columns; `AiChatController` threading `X-Conversation-Id`; `GET/DELETE /ai/sessions`; `AiSessionController`. Confirmed present at `/home/pickle/code/history-mapped/api/app/Http/Controllers/Admin/Ai/AiChatController.php` and `AiSessionController.php`, routes in `api/routes/web.php:85-88`.
- Phase 1 (create-mode): `GlobalAgent` full toolset can overlap (all 11 tools registered in `AppServiceProvider`).

**Tech Stack:** PHP 8.4 / Laravel 13, `laravel/ai`, Inertia + React 19, `@ai-sdk/react` v3 / `ai` v6, Tailwind 4, shadcn/ui. Backend in Docker `app` container.

## Global Constraints

- Backend commands: `docker compose -f docker/docker-compose.yml exec app <cmd>`. Restart `app` after editing existing PHP files: `docker compose -f docker/docker-compose.yml restart app`.
- Write logic lives in **Action classes** — tools wrap Actions; tools stage proposals. `GlobalAgent` follows the exact same pattern as `ChronicleEditorAgent` (implements `Agent, Conversational, HasTools`; uses `Promptable, RemembersConversations`).
- All 11 tools are already registered in `AppServiceProvider::boot()`. `GlobalAgent` instantiates them from the container — no new registrations needed.
- Gate: `permission:entities.write` on all AI routes (already set at route level; `admin` bypasses via `Gate::before`).
- Global sessions: `context_type='global'`, `context_id=null` in `agent_conversations`. Proposals stage under `context_type='global'`, `context_id=$sessionId` (the session's UUID is the anchor — not a sentinel string like `'create'`).
- **Global apply stays in session** — no `redirect_url`. Instead, return `created_ref: {type, id, url, label}` so the page renders a link. Scoped-edit and create-page modes keep today's `router.reload()` / `redirect_url` behavior (the `mode` and `redirect_url` paths in `ProposalCard` are unchanged).
- `DefaultChatTransport.body` accepts a `Resolvable<object>` (can be a function); `headers` is already a function in the sidebar. Both patterns are confirmed by the installed `ai` package types.
- Pint clean (`./vendor/bin/pint --test`). Frontend: `npm run lint:check`, `npm run types:check`, `npm run build`. TDD throughout. Frontend tests: vitest, `@testing-library/react`, test env set per-file with `// @vitest-environment jsdom`, globals imported explicitly.
- **This feature uses literal URL strings on the frontend** (`/ai`, `/ai/chat`, `/ai/sessions`) — matching the existing AI sidebar (`api: '/ai/chat'`). Do NOT regenerate Wayfinder and do NOT import from `@/routes/ai`. (Avoids root-owned-file and closure-route generation issues; Phase A also did not regenerate Wayfinder.) Never hand-edit `api/resources/js/routes/**` or `api/resources/js/actions/**`.

---

## File Structure

**Backend (api/)**

| File | Action | Responsibility |
|---|---|---|
| `app/Ai/Agents/GlobalAgent.php` | **Create** | Full-toolset agent — no bound record; `kind=global` |
| `resources/views/ai/instructions/global.blade.php` | **Create** | System prompt: global workspace, propose-only, no redirect after create |
| `app/Http/Controllers/Admin/Ai/AiChatController.php` | **Modify** | Accept `kind` input; `kind=global` branch to `GlobalAgent`; skip record lookup |
| `app/Http/Controllers/Admin/Ai/AiProposalController.php` | **Modify** | Add `created_ref` to apply response for global sessions |
| `routes/web.php` | **Modify** | Add `GET ai` → `ai.index` Inertia route |

**Frontend (api/resources/js/)**

| File | Action | Responsibility |
|---|---|---|
| `pages/ai/index.tsx` | **Create** | Two-pane "Create with AI" page — session list + chat |
| `components/ai/ai-chat-panel.tsx` | **Create** | Extracted chat UI (messages list + input) reusable without the right-dock wrapper |
| `components/ai/proposal-card.tsx` | **Modify** | Accept optional `created_ref` on apply response; render as inline record link |
| `components/app-sidebar.tsx` | **Modify** | Add "Create with AI" nav entry |
| `hooks/use-session-chat.ts` | **Create** | `Chat` factory that takes `sessionId: string | null` + `kind: 'global'|'entity'|'chronicle'` — returns a `Chat` instance with the right transport body and captures `X-Conversation-Id` from the first response |

---

## Task 1: `GlobalAgent` + Blade instructions

**Files:**
- Create: `api/app/Ai/Agents/GlobalAgent.php`
- Create: `api/resources/views/ai/instructions/global.blade.php`
- Test: `api/tests/Feature/Ai/GlobalAgentTest.php`

**Interfaces:**
- Consumes: all 11 tools already registered — `CreateEntity`, `CreateChronicle`, `CreateRelationship`, `SetEntityLocation`, `UpdateEntityFields`, `GetEntityContext`, `VerifyWikidata`, `SetEntityWikidata`, `MergeDuplicateEntities`, `CreateChronicleEntry`, `UpdateChronicleEntry`.
- Produces: `GlobalAgent(User $user, array $context)` — `Agent, Conversational, HasTools`; `tools()` returns all 11 tools with `->withContext()` on staging tools; `instructions()` renders `ai.instructions.global`.

- [ ] **Step 1: Write the failing test**

Create `api/tests/Feature/Ai/GlobalAgentTest.php`:

```php
<?php

namespace Tests\Feature\Ai;

use App\Ai\Agents\GlobalAgent;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class GlobalAgentTest extends TestCase
{
    use RefreshDatabase;

    private function ctx(): array
    {
        return [
            'user_id' => 'u1',
            'context_type' => 'global',
            'context_id' => 'some-session-uuid',
            'conversation_id' => 'some-session-uuid',
        ];
    }

    public function test_global_agent_exposes_all_eleven_tools_with_context(): void
    {
        $user = User::factory()->create();
        $agent = new GlobalAgent($user, $this->ctx());

        $tools = iterator_to_array($agent->tools());
        $names = array_map(fn ($t) => $t::name(), $tools);

        // Create tools
        $this->assertContains('create_entity', $names);
        $this->assertContains('create_chronicle', $names);
        $this->assertContains('create_chronicle_entry', $names);

        // Edit tools
        $this->assertContains('update_entity_fields', $names);
        $this->assertContains('set_entity_location', $names);
        $this->assertContains('set_entity_wikidata', $names);
        $this->assertContains('create_relationship', $names);
        $this->assertContains('update_chronicle_entry', $names);
        $this->assertContains('merge_duplicate_entities', $names);

        // Read-only (no context needed)
        $this->assertContains('get_entity_context', $names);
        $this->assertContains('verify_wikidata', $names);

        $this->assertCount(11, $tools);
    }

    public function test_global_agent_injects_context_on_staging_tools(): void
    {
        $user = User::factory()->create();
        $agent = new GlobalAgent($user, $this->ctx());

        $createEntity = collect($agent->tools())
            ->first(fn ($t) => $t::name() === 'create_entity');

        // The context is stored in a protected/private property — reflect to verify.
        $ref = new \ReflectionProperty($createEntity, 'context');
        $ref->setAccessible(true);

        $this->assertSame('u1', $ref->getValue($createEntity)['user_id']);
        $this->assertSame('global', $ref->getValue($createEntity)['context_type']);
    }

    public function test_global_agent_instructions_mention_proposal_workflow_and_no_redirect(): void
    {
        $user = User::factory()->create();
        $agent = new GlobalAgent($user, $this->ctx());
        $instructions = $agent->instructions();

        $this->assertStringContainsStringIgnoringCase('propose', $instructions);
        // Should tell the model the conversation continues (stay-in-session), not
        // that it hands off / navigates away after creating a record.
        $this->assertStringContainsStringIgnoringCase('continue', $instructions);
        // Should mention it can work on any record type
        $this->assertStringContainsStringIgnoringCase('entity', $instructions);
        $this->assertStringContainsStringIgnoringCase('chronicle', $instructions);
    }
}
```

- [ ] **Step 2: Run it, expect failure**

```bash
docker compose -f docker/docker-compose.yml exec app php artisan test --filter GlobalAgentTest
```

Expected: FAIL — class `App\Ai\Agents\GlobalAgent` not found.

- [ ] **Step 3: Implement the agent**

Create `api/app/Ai/Agents/GlobalAgent.php`:

```php
<?php

namespace App\Ai\Agents;

use App\Ai\Tools\CreateChronicle;
use App\Ai\Tools\CreateChronicleEntry;
use App\Ai\Tools\CreateEntity;
use App\Ai\Tools\CreateRelationship;
use App\Ai\Tools\GetEntityContext;
use App\Ai\Tools\MergeDuplicateEntities;
use App\Ai\Tools\SetEntityLocation;
use App\Ai\Tools\SetEntityWikidata;
use App\Ai\Tools\UpdateChronicleEntry;
use App\Ai\Tools\UpdateEntityFields;
use App\Ai\Tools\VerifyWikidata;
use App\Models\User;
use Laravel\Ai\Concerns\RemembersConversations;
use Laravel\Ai\Contracts\Agent;
use Laravel\Ai\Contracts\Conversational;
use Laravel\Ai\Contracts\HasTools;
use Laravel\Ai\Promptable;

class GlobalAgent implements Agent, Conversational, HasTools
{
    use Promptable, RemembersConversations;

    /**
     * @param  array{user_id:string,context_type:string,context_id:string,conversation_id:?string}  $context
     */
    public function __construct(
        public User $user,
        public array $context = [],
    ) {}

    public function instructions(): string
    {
        return view('ai.instructions.global')->render();
    }

    /**
     * Full registered toolset.
     *
     * Read-only tools (VerifyWikidata, GetEntityContext) need no context — they
     * never stage proposals. Staging tools receive $this->context so ProposedChange
     * rows carry the correct user, conversation, and global context.
     */
    public function tools(): iterable
    {
        return [
            // Read-only / lookup
            app(VerifyWikidata::class),
            app(GetEntityContext::class),

            // Staging — create
            app(CreateEntity::class)->withContext($this->context),
            app(CreateChronicle::class)->withContext($this->context),
            app(CreateChronicleEntry::class)->withContext($this->context),

            // Staging — edit
            app(UpdateEntityFields::class)->withContext($this->context),
            app(SetEntityLocation::class)->withContext($this->context),
            app(SetEntityWikidata::class)->withContext($this->context),
            app(CreateRelationship::class)->withContext($this->context),
            app(UpdateChronicleEntry::class)->withContext($this->context),
            app(MergeDuplicateEntities::class)->withContext($this->context),
        ];
    }
}
```

- [ ] **Step 4: Create the Blade instructions template**

Create `api/resources/views/ai/instructions/global.blade.php`:

```blade
You are a global AI workspace assistant for a historical atlas admin.

You can create and edit any record type — entities, chronicles, chronicle entries,
relationships, locations, Wikidata links — by proposing changes that the operator
reviews and applies. You are NOT restricted to a single entity or chronicle.

Rules:
- You PROPOSE changes; the operator clicks Apply. You never commit data directly.
- Use verify_wikidata or get_entity_context to look up information before mutating records.
- When you create a record (create_entity, create_chronicle), the conversation
  CONTINUES — you are NOT redirected. The operator stays here and you can create
  or edit additional records in the same session.
- If the operator asks to add entries to a chronicle that does not exist yet,
  create the chronicle first with create_chronicle, then add entries with
  create_chronicle_entry (pass the new chronicle's id from the Apply result).
- When editing existing records, ask the operator to provide the record id, or use
  get_entity_context to resolve a name to an id.
- Be concise. Summarise what each proposal will do before calling the staging tool.
```

- [ ] **Step 5: Run the test, expect PASS**

```bash
docker compose -f docker/docker-compose.yml exec app php artisan test --filter GlobalAgentTest
```

Expected: all 3 tests PASS.

- [ ] **Step 6: Pint**

```bash
docker compose -f docker/docker-compose.yml exec app ./vendor/bin/pint app/Ai/Agents/GlobalAgent.php
```

- [ ] **Step 7: Commit**

```bash
git add api/app/Ai/Agents/GlobalAgent.php api/resources/views/ai/instructions/global.blade.php api/tests/Feature/Ai/GlobalAgentTest.php
git commit -m "feat(ai): GlobalAgent with full toolset + global workspace instructions"
```

---

## Task 2: Chat controller `kind=global` branch

**Files:**
- Modify: `api/app/Http/Controllers/Admin/Ai/AiChatController.php`
- Test: `api/tests/Feature/Ai/AiChatStreamTest.php` (extend)

**Interfaces:**
- Consumes: `GlobalAgent(User $user, array $context)`.
- Produces: `/ai/chat` accepts optional `kind` (`'global'|'entity'|'chronicle'`, default derived from `context_type`). When `kind=global`, `context_type` and `context_id` are optional (no record lookup), session is tagged `context_type='global'`, `context_id=null`, and `GlobalAgent` is used. All existing branches (`kind=entity`, `kind=chronicle`, and the create-mode arms) are UNCHANGED.

**Behavior contract:** The existing `match(true)` dispatch block is extended with a new top-priority arm. The `context_type` validator is relaxed to `nullable` when `kind=global`. The session creation block gains `context_type='global'` / `context_id=null` for global sessions.

- [ ] **Step 1: Write the failing tests**

Append to `api/tests/Feature/Ai/AiChatStreamTest.php`:

```php
    public function test_kind_global_routes_to_global_agent_without_context_fields(): void
    {
        GlobalAgent::fake(['Hello from GlobalAgent.']);

        $user = $this->userWithPermissions(['entities.write']);

        $response = $this->actingAs($user)->postJson('/ai/chat', [
            'kind' => 'global',
            'prompt' => 'Tell me about the Roman Empire.',
        ]);

        $response->assertOk();
        $response->assertHeader('X-Conversation-Id');

        $sessionId = $response->headers->get('X-Conversation-Id');
        $this->assertDatabaseHas('agent_conversations', [
            'id' => $sessionId,
            'user_id' => $user->id,
            'context_type' => 'global',
            'context_id' => null,
        ]);
    }

    public function test_kind_global_with_session_id_continues_global_session(): void
    {
        GlobalAgent::fake(['Continuing global session.']);

        $user = $this->userWithPermissions(['entities.write']);

        $existing = \Laravel\Ai\Models\Conversation::create([
            'id' => (string) \Illuminate\Support\Str::uuid7(),
            'user_id' => $user->id,
            'title' => 'Earlier global chat',
            'context_type' => 'global',
            'context_id' => null,
        ]);

        $response = $this->actingAs($user)->postJson('/ai/chat', [
            'kind' => 'global',
            'conversation_id' => $existing->id,
            'prompt' => 'Follow-up.',
        ]);

        $response->assertOk();
        $this->assertSame($existing->id, $response->headers->get('X-Conversation-Id'));
        $this->assertSame(1, \Laravel\Ai\Models\Conversation::query()->count());
    }

    public function test_existing_entity_edit_mode_still_works_when_kind_omitted(): void
    {
        \App\Ai\Agents\EntityEditorAgent::fake(['Edit mode fine.']);

        $user = $this->userWithPermissions(['entities.write']);
        $entity = $this->makeEntity();

        $this->actingAs($user)->postJson('/ai/chat', [
            'context_type' => 'entity',
            'context_id' => $entity->entity_id,
            'prompt' => 'Update this entity.',
        ])->assertOk();
    }
```

- [ ] **Step 2: Run-fail**

```bash
docker compose -f docker/docker-compose.yml exec app php artisan test --filter AiChatStreamTest
```

Expected: the two new `kind=global` tests FAIL (validation 422 or class not found). The existing test passes.

- [ ] **Step 3: Edit the controller**

Open `api/app/Http/Controllers/Admin/Ai/AiChatController.php`.

Add to the `use` block at the top (after the existing agent imports):

```php
use App\Ai\Agents\GlobalAgent;
```

In the `$data = $request->validate([...])` block, add the `kind` field AND relax `context_type` so global requests (which send no `context_type`) are not rejected. Change the existing line:

```php
            'context_type' => 'required|in:entity,chronicle',
```

to:

```php
            'context_type' => ['nullable', 'required_unless:kind,global', 'in:entity,chronicle'],
            'kind' => 'nullable|in:global,entity,chronicle',
```

(`required_unless:kind,global` keeps `context_type` mandatory for the existing entity/chronicle flows but optional when `kind=global`.)

After the line `$mode = $data['mode'] ?? 'edit';`, add:

```php
        $kind = $data['kind'] ?? null;

        // Global sessions have no bound record and no context_type/context_id.
        $isGlobal = $kind === 'global';
```

Replace the existing guard:

```php
        if ($mode === 'edit' && empty($data['context_id'])) {
            abort(422, 'context_id is required in edit mode.');
        }

        $contextId = $mode === 'create' ? 'create' : $data['context_id'];
```

with:

```php
        if (! $isGlobal && $mode === 'edit' && empty($data['context_id'])) {
            abort(422, 'context_id is required in edit mode.');
        }

        $contextId = $isGlobal ? null : ($mode === 'create' ? 'create' : ($data['context_id'] ?? null));
```

In the new-session creation block, replace:

```php
            Conversation::create([
                'id' => $conversationId,
                'user_id' => $user->id,
                'title' => Str::limit($promptText, 60, ''),
                'context_type' => $data['context_type'],
                'context_id' => $contextId,
            ]);
```

with:

```php
            Conversation::create([
                'id' => $conversationId,
                'user_id' => $user->id,
                'title' => Str::limit($promptText, 60, ''),
                'context_type' => $isGlobal ? 'global' : $data['context_type'],
                'context_id' => $contextId,
            ]);
```

In the `$context = [...]` block, replace:

```php
        $context = [
            'user_id' => (string) $user->id,
            'context_type' => $data['context_type'],
            'context_id' => $contextId,
            'conversation_id' => $conversationId,
        ];
```

with:

```php
        $context = [
            'user_id' => (string) $user->id,
            'context_type' => $isGlobal ? 'global' : $data['context_type'],
            'context_id' => $contextId ?? $conversationId, // global: use session id as context_id for proposal staging
            'conversation_id' => $conversationId,
        ];
```

Add the global arm as the **first** arm in the `match(true)` block:

```php
        $agent = match (true) {
            $isGlobal => new GlobalAgent($user, $context),
            $mode === 'create' && $data['context_type'] === 'entity' => new EntityCreatorAgent($user, $context),
            $mode === 'create' && $data['context_type'] === 'chronicle' => new ChronicleCreatorAgent($user, $context),
            $data['context_type'] === 'entity' => new EntityEditorAgent(Entity::findOrFail($contextId), $user, $context),
            $data['context_type'] === 'chronicle' => new ChronicleEditorAgent(Chronicle::findOrFail($contextId), $user, $context),
        };
```

Also update the UUID guard so it only runs for edit mode with a real context id:

```php
        if (! $isGlobal && $mode === 'edit' && ! Str::isUuid($contextId)) {
            abort(404, 'Record not found.');
        }
```

- [ ] **Step 4: Run-pass**

```bash
docker compose -f docker/docker-compose.yml exec app php artisan test --filter AiChatStreamTest
```

If stale: `docker compose -f docker/docker-compose.yml restart app` then re-run.
Expected: all tests PASS.

- [ ] **Step 5: Pint**

```bash
docker compose -f docker/docker-compose.yml exec app ./vendor/bin/pint app/Http/Controllers/Admin/Ai/AiChatController.php
```

- [ ] **Step 6: Commit**

```bash
git add api/app/Http/Controllers/Admin/Ai/AiChatController.php api/tests/Feature/Ai/AiChatStreamTest.php
git commit -m "feat(ai): chat controller kind=global branch routes to GlobalAgent"
```

---

## Task 3: Apply endpoint `created_ref` for global sessions

**Files:**
- Modify: `api/app/Http/Controllers/Admin/Ai/AiProposalController.php`
- Test: `api/tests/Feature/Ai/AiProposalEndpointTest.php` (extend)

**Interfaces:**
- Produces: `apply` JSON response gains a `created_ref` field (nullable) alongside the existing `status`, `result_id`, `redirect_url`. `created_ref` is non-null only when the applied part created a record (tools `create_entity` or `create_chronicle`) AND the parent `ProposedChange.context_type` is `'global'`. Shape: `{ type: 'entity'|'chronicle', id: string, url: string, label: string }`. When `context_type` is NOT `'global'`, `redirect_url` still works as today (`create_entity` → `entities.edit` url, `create_chronicle` → `chronicles.edit` url) and `created_ref` is null.

**Behavior contract:** Scoped-edit pages (non-global) are UNAFFECTED: `redirect_url` keeps appearing for record-creating tools; `ProposalCard` in `mode='edit'` does `router.reload()`. The new `created_ref` is consumed only by the new global chat panel (Task 6).

- [ ] **Step 1: Write the failing tests**

**Exercise the REAL apply path — do not mock `ProposalApplier`.** This file already has tests `test_apply_create_entity_returns_redirect_url` and `test_apply_create_chronicle_returns_redirect_url` (from the create-mode feature) that stage a real `create_entity`/`create_chronicle` `ProposedChange` + part and POST to the apply endpoint, letting the real `CreateEntity`/`CreateChronicle` tool run. READ those two tests first and mirror their exact staging (the payload shape the real tools accept, and any `$this->fakeWikidata()` / helper they use). The only differences in the new tests: set `context_type => 'global'` on the `ProposedChange`, and assert `created_ref` (not `redirect_url`). Append:

```php
    public function test_apply_returns_created_ref_for_global_session_create_entity(): void
    {
        // Mirror test_apply_create_entity_returns_redirect_url's staging EXACTLY
        // (same payload the real CreateEntity tool accepts, same fakeWikidata if used),
        // changing only context_type to 'global'.
        $user = $this->userWithPermissions(['entities.write']);

        $change = \App\Models\Ai\ProposedChange::create([
            'user_id' => (string) $user->id,
            'conversation_id' => 'global-session-uuid',
            'context_type' => 'global',
            'context_id' => 'global-session-uuid',
        ]);

        // Use the SAME create_entity payload the existing redirect_url test stages.
        $part = $change->parts()->create([
            'key' => 'entity',
            'tool' => 'create_entity',
            'payload' => [/* copy from the existing create_entity redirect test */],
            'human_diff' => ['summary' => 'Create Rome'],
            'status' => 'pending',
            'result_id' => null,
        ]);

        $response = $this->actingAs($user)
            ->postJson("/ai/proposals/{$change->id}/parts/entity/apply");

        $response->assertOk();
        $this->assertSame('applied', $response->json('status'));
        $this->assertNull($response->json('redirect_url'));
        $this->assertSame('entity', $response->json('created_ref.type'));
        $this->assertSame($response->json('result_id'), $response->json('created_ref.id'));
        $this->assertStringContainsString('entities', $response->json('created_ref.url'));
        $this->assertNotEmpty($response->json('created_ref.label'));
    }

    public function test_apply_returns_redirect_url_not_created_ref_for_scoped_session(): void
    {
        // Same as the existing test_apply_create_entity_returns_redirect_url, but
        // also assert created_ref is null (proving global vs scoped branching).
        $user = $this->userWithPermissions(['entities.write']);

        $change = \App\Models\Ai\ProposedChange::create([
            'user_id' => (string) $user->id,
            'conversation_id' => 'scoped-session-uuid',
            'context_type' => 'entity',
            'context_id' => 'some-entity-id',
        ]);

        $part = $change->parts()->create([
            'key' => 'entity',
            'tool' => 'create_entity',
            'payload' => [/* copy from the existing create_entity redirect test */],
            'human_diff' => ['summary' => 'Create Carthage'],
            'status' => 'pending',
            'result_id' => null,
        ]);

        $response = $this->actingAs($user)
            ->postJson("/ai/proposals/{$change->id}/parts/entity/apply");

        $response->assertOk();
        $this->assertNotNull($response->json('redirect_url'));
        $this->assertNull($response->json('created_ref'));
    }
```

> The `payload` placeholders above MUST be filled from the existing redirect_url tests' real `create_entity` payload before running — these tests run the real tool, so the payload must be valid. Do not mock the applier.

- [ ] **Step 2: Run-fail**

```bash
docker compose -f docker/docker-compose.yml exec app php artisan test --filter AiProposalEndpointTest
```

Expected: the two new tests FAIL (`created_ref` key missing / wrong).

- [ ] **Step 3: Edit the apply method**

Open `api/app/Http/Controllers/Admin/Ai/AiProposalController.php`.

Add to imports:

```php
use App\Models\Entity;
```

(Chronicle is already imported.)

Replace the current `apply` method body after `$applied = $applier->applyPart($part);`:

```php
        $isGlobalSession = $part->change->context_type === 'global';

        // For global sessions: no redirect. Return a created_ref link so the chat
        // panel can render the new record as an inline link without navigating away.
        // For scoped sessions (entity/chronicle/create): keep existing redirect_url behavior.
        $redirectUrl = null;
        $createdRef = null;

        if ($isGlobalSession && in_array($applied->tool, ['create_entity', 'create_chronicle'], true)) {
            if ($applied->tool === 'create_entity') {
                $entity = Entity::find($applied->result_id);
                $createdRef = $entity ? [
                    'type' => 'entity',
                    'id' => $applied->result_id,
                    'url' => route('entities.edit', $applied->result_id),
                    'label' => $entity->name,
                ] : null;
            } elseif ($applied->tool === 'create_chronicle') {
                $chronicle = Chronicle::find($applied->result_id);
                $createdRef = $chronicle ? [
                    'type' => 'chronicle',
                    'id' => $applied->result_id,
                    'url' => route('chronicles.edit', $chronicle->slug),
                    'label' => $chronicle->title,
                ] : null;
            }
        } elseif (! $isGlobalSession) {
            $redirectUrl = match ($applied->tool) {
                'create_entity' => route('entities.edit', $applied->result_id),
                'create_chronicle' => route('chronicles.edit', Chronicle::findOrFail($applied->result_id)->slug),
                default => null,
            };
        }

        return response()->json([
            'status' => $applied->status,
            'result_id' => $applied->result_id,
            'redirect_url' => $redirectUrl,
            'created_ref' => $createdRef,
        ]);
```

- [ ] **Step 4: Run-pass**

```bash
docker compose -f docker/docker-compose.yml exec app php artisan test --filter AiProposalEndpointTest
```

Expected: all pass. Then no-regressions sweep:

```bash
docker compose -f docker/docker-compose.yml exec app php artisan test --filter "Ai"
```

- [ ] **Step 5: Pint**

```bash
docker compose -f docker/docker-compose.yml exec app ./vendor/bin/pint app/Http/Controllers/Admin/Ai/AiProposalController.php
```

- [ ] **Step 6: Commit**

```bash
git add api/app/Http/Controllers/Admin/Ai/AiProposalController.php api/tests/Feature/Ai/AiProposalEndpointTest.php
git commit -m "feat(ai): apply returns created_ref for global sessions (no redirect)"
```

---

## Task 4: Backend route `ai.index`

**Files:**
- Modify: `api/routes/web.php`

**Interfaces:**
- Produces: `GET /ai` → route name `ai.index`, renders Inertia page `'ai/index'`. Gated by `auth + verified` (already in the outer group).

> **No Wayfinder regeneration.** This feature uses **literal** URL strings on the frontend (`/ai`, `/ai/chat`, `/ai/sessions`) — matching the existing AI sidebar, which already hardcodes `api: '/ai/chat'`. We do NOT depend on `@/routes/ai` helpers (Phase A did not regenerate Wayfinder either). This avoids the root-owned-file / closure-route generation pitfalls.

- [ ] **Step 1: Write the failing test**

Append to `api/tests/Feature/Ai/AiSessionEndpointTest.php`:

```php
    public function test_ai_index_page_is_accessible_to_authenticated_users(): void
    {
        $user = $this->userWithPermissions(['entities.write']);

        $response = $this->actingAs($user)->get('/ai');

        $response->assertOk();
        $response->assertInertia(fn ($page) => $page->component('ai/index'));
    }
```

- [ ] **Step 2: Run-fail**

```bash
docker compose -f docker/docker-compose.yml exec app php artisan test --filter "test_ai_index_page_is_accessible"
```

Expected: FAIL (404, route not registered).

- [ ] **Step 3: Add the route**

In `api/routes/web.php`, inside the `Route::middleware(['auth', 'verified'])->group(function () {` block, after the AI session routes (around line 89), add:

```php
    // ── Create with AI page ───────────────────────────────────────────────────
    Route::get('ai', fn () => \Inertia\Inertia::render('ai/index'))->name('ai.index');
```

- [ ] **Step 4: Run-pass**

```bash
docker compose -f docker/docker-compose.yml exec app php artisan test --filter "test_ai_index_page_is_accessible"
```

Expected: PASS. `assertInertia(fn ($page) => $page->component('ai/index'))` checks the component NAME in the Inertia response payload — it does NOT require the React file to exist (that resolves client-side). So the test passes as soon as the route returns `Inertia::render('ai/index')`, even before Task 8 creates the page component.

- [ ] **Step 5: Commit**

```bash
git add api/routes/web.php
git commit -m "feat(ai): register GET /ai route (ai.index)"
```

---

## Task 5: `ProposalCard` — render `created_ref` as inline record link

**Files:**
- Modify: `api/resources/js/components/ai/proposal-card.tsx`
- Test: `api/resources/js/components/ai/__tests__/proposal-card.test.tsx` (extend or create)

**Interfaces:**
- Consumes: `apply` JSON response now may include `created_ref: { type, id, url, label } | null`.
- Produces: when the apply response has `created_ref` and the part is in a global chat (indicated by a new optional prop `onCreatedRef?: (ref: CreatedRef) => void`), the card renders an anchor link instead of calling `router.visit`. The `mode='create'` → `router.visit(redirect_url)` path is preserved exactly. The `mode='edit'` → `router.reload()` path is preserved exactly. This keeps `ProposalCard` a pure presentational component with a clear prop interface — the page passes `onCreatedRef` to receive the ref.

**Design decision:** `ProposalCard` should NOT know whether it is on the global page or the sidebar — it gets `onCreatedRef` from the parent. If `onCreatedRef` is provided AND `created_ref` is present in the response, call `onCreatedRef(created_ref)` instead of navigating. If neither `onCreatedRef` nor `redirect_url` applies, fall back to `router.reload()`.

- [ ] **Step 1: Write the failing test**

Create (or append to) `api/resources/js/components/ai/__tests__/proposal-card.test.tsx`:

```tsx
// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { describe, expect, it, vi } from 'vitest';
import { ProposalCard } from '../proposal-card';

vi.mock('@inertiajs/react', () => ({
    router: { visit: vi.fn(), reload: vi.fn() },
}));

vi.mock('@/lib/ai-events', () => ({ emitAiApplied: vi.fn() }));

const { router } = await import('@inertiajs/react');

function mockFetch(json: object, ok = true) {
    global.fetch = vi.fn().mockResolvedValue({
        ok,
        json: async () => json,
    } as Response);
}

const proposal = {
    proposal_id: 'prop-1',
    parts: [{ key: 'entity', human_diff: { summary: 'Create Rome' } }],
};

describe('ProposalCard', () => {
    it('calls onCreatedRef when apply returns created_ref', async () => {
        const onCreatedRef = vi.fn();
        mockFetch({
            status: 'applied',
            result_id: 'entity-uuid',
            redirect_url: null,
            created_ref: { type: 'entity', id: 'entity-uuid', url: '/entities/entity-uuid/edit', label: 'Rome' },
        });

        render(
            <ProposalCard
                proposal={proposal}
                mode="edit"
                onCreatedRef={onCreatedRef}
            />,
        );

        fireEvent.click(screen.getByRole('button', { name: /apply/i }));

        await waitFor(() => {
            expect(onCreatedRef).toHaveBeenCalledWith({
                type: 'entity',
                id: 'entity-uuid',
                url: '/entities/entity-uuid/edit',
                label: 'Rome',
            });
        });
        expect(router.visit).not.toHaveBeenCalled();
        expect(router.reload).not.toHaveBeenCalled();
    });

    it('calls router.reload when no created_ref and no redirect_url', async () => {
        const { emitAiApplied } = await import('@/lib/ai-events');
        mockFetch({ status: 'applied', result_id: 'x', redirect_url: null, created_ref: null });

        render(<ProposalCard proposal={proposal} mode="edit" />);

        fireEvent.click(screen.getByRole('button', { name: /apply/i }));

        await waitFor(() => {
            expect(router.reload).toHaveBeenCalled();
            expect(emitAiApplied).toHaveBeenCalled();
        });
    });

    it('calls router.visit with redirect_url in create mode', async () => {
        mockFetch({
            status: 'applied',
            result_id: 'x',
            redirect_url: '/entities/x/edit',
            created_ref: null,
        });

        render(<ProposalCard proposal={proposal} mode="create" />);

        fireEvent.click(screen.getByRole('button', { name: /apply/i }));

        await waitFor(() => {
            expect(router.visit).toHaveBeenCalledWith('/entities/x/edit');
        });
    });
});
```

- [ ] **Step 2: Run-fail**

```bash
docker compose -f docker/docker-compose.yml exec app npx vitest run resources/js/components/ai/__tests__/proposal-card.test.tsx
```

Expected: type errors or test failures on `onCreatedRef` prop not existing.

- [ ] **Step 3: Update `proposal-card.tsx`**

Add the `CreatedRef` type and `onCreatedRef` prop:

```tsx
export type CreatedRef = {
    type: 'entity' | 'chronicle';
    id: string;
    url: string;
    label: string;
};
```

Update the component signature:

```tsx
export function ProposalCard({
    proposal,
    mode = 'edit',
    onCreatedRef,
}: {
    proposal: Proposal;
    mode?: 'edit' | 'create';
    onCreatedRef?: (ref: CreatedRef) => void;
}) {
```

In the `act` function, update the response type and handling after `setPartStatus`:

```tsx
            const json = (await res.json()) as {
                status: string;
                redirect_url?: string | null;
                created_ref?: CreatedRef | null;
            };
```

Replace the existing `if (status === 'applied')` block:

```tsx
            if (status === 'applied') {
                if (json.created_ref && onCreatedRef) {
                    // Global session: surface the created record to the parent
                    // chat panel as an inline link — do NOT navigate away.
                    onCreatedRef(json.created_ref);
                } else if (mode === 'create' && typeof json.redirect_url === 'string') {
                    router.visit(json.redirect_url);
                } else {
                    router.reload();
                    emitAiApplied();
                }
            }
```

- [ ] **Step 4: Run-pass**

```bash
docker compose -f docker/docker-compose.yml exec app npx vitest run resources/js/components/ai/__tests__/proposal-card.test.tsx
```

Expected: all 3 tests PASS. Then type check:

```bash
docker compose -f docker/docker-compose.yml exec app npm run types:check
```

- [ ] **Step 5: Commit**

```bash
git add api/resources/js/components/ai/proposal-card.tsx api/resources/js/components/ai/__tests__/proposal-card.test.tsx
git commit -m "feat(ai): ProposalCard accepts onCreatedRef for global session stay-in-session"
```

---

## Task 6: `useSessionChat` hook

**Files:**
- Create: `api/resources/js/hooks/use-session-chat.ts`
- Test: `api/resources/js/hooks/__tests__/use-session-chat.test.ts`

**Interfaces:**
- Produces: `useSessionChat({ sessionId: string | null, kind: 'global' | 'entity' | 'chronicle', contextType?: string, contextId?: string | null })` → `{ chat: Chat, sessionId: string | null, setSessionId: (id: string) => void }`. The hook creates a `Chat` instance via `useMemo`. Transport `body` is a **function** (re-evaluated per request) so the `sessionId` ref is always fresh without needing to recreate the `Chat`. The hook provides a `setSessionId` callback for the page to call after reading `X-Conversation-Id` from the first response.

**Design note on `X-Conversation-Id` capture:** `DefaultChatTransport` has no `onResponse` hook. Instead, we supply a custom `fetch` function via the `fetch` option. The custom fetch calls `window.fetch`, reads `X-Conversation-Id` from the response headers, and calls `onNewSessionId` (a callback from the page). This is the only reliable interception point available in the installed SDK (`DefaultChatTransport` constructor at `api/node_modules/ai/dist/index.d.ts:4064`: `fetch?: FetchFunction`).

- [ ] **Step 1: Write the failing test**

Create `api/resources/js/hooks/__tests__/use-session-chat.test.ts`:

```tsx
// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { DefaultChatTransport } from 'ai';
import { useSessionChat } from '../use-session-chat';

vi.mock('@ai-sdk/react', () => ({
    Chat: vi.fn().mockImplementation(() => ({ id: 'mock-chat' })),
}));

vi.mock('ai', () => ({
    DefaultChatTransport: vi.fn().mockImplementation((opts: unknown) => ({
        _opts: opts,
    })),
}));

describe('useSessionChat', () => {
    it('creates a Chat with the correct kind in the transport body function', () => {
        const transportMock = vi.mocked(DefaultChatTransport);

        renderHook(() => useSessionChat({ sessionId: null, kind: 'global' }));

        expect(transportMock).toHaveBeenCalled();
        // The transport options object is the first arg of the constructor call.
        const transportOpts = transportMock.mock.calls[0][0] as {
            body: () => { kind: string; conversation_id: string | null };
        };

        expect(typeof transportOpts.body).toBe('function');

        const body = transportOpts.body();
        expect(body.kind).toBe('global');
        expect(body.conversation_id).toBeNull();
    });

    it('setSessionId updates the session id returned by the hook', () => {
        const { result } = renderHook(() =>
            useSessionChat({ sessionId: null, kind: 'global' }),
        );

        expect(result.current.sessionId).toBeNull();

        act(() => {
            result.current.setSessionId('new-uuid');
        });

        expect(result.current.sessionId).toBe('new-uuid');
    });
});
```

- [ ] **Step 2: Run-fail**

```bash
docker compose -f docker/docker-compose.yml exec app npx vitest run resources/js/hooks/__tests__/use-session-chat.test.ts
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement the hook**

Create `api/resources/js/hooks/use-session-chat.ts`:

```ts
import { Chat } from '@ai-sdk/react';
import { DefaultChatTransport } from 'ai';
import { useMemo, useRef, useState } from 'react';

function getCsrfToken(): string {
    return (
        document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')
            ?.content ?? ''
    );
}

type UseSessionChatOptions = {
    /** Ongoing session id (null = new session, id is set after first response). */
    sessionId: string | null;
    kind: 'global' | 'entity' | 'chronicle';
    /** Required for entity/chronicle kinds. */
    contextType?: string;
    /** Nullable for global / create-mode sessions. */
    contextId?: string | null;
    /** Called when the first response returns a new X-Conversation-Id header. */
    onNewSessionId?: (id: string) => void;
    /** Bump to force a fresh Chat instance (e.g. "New session" button). */
    resetNonce?: number;
};

export function useSessionChat({
    sessionId,
    kind,
    contextType,
    contextId,
    onNewSessionId,
    resetNonce = 0,
}: UseSessionChatOptions) {
    const [currentSessionId, setCurrentSessionId] = useState<string | null>(
        sessionId,
    );

    // Keep a ref so the body function closure always reads the latest session id
    // without needing to recreate the Chat instance.
    const sessionIdRef = useRef<string | null>(currentSessionId);
    sessionIdRef.current = currentSessionId;

    const onNewSessionIdRef = useRef(onNewSessionId);
    onNewSessionIdRef.current = onNewSessionId;

    // The Chat instance is stable for the lifetime of this session (kind + context
    // do not change mid-session). It is only recreated if the page mounts a
    // fundamentally different session type — which triggers a React remount anyway.
    const chat = useMemo(
        () =>
            new Chat({
                transport: new DefaultChatTransport({
                    api: '/ai/chat',
                    headers: () => ({
                        'X-CSRF-TOKEN': getCsrfToken(),
                        'X-Requested-With': 'XMLHttpRequest',
                    }),
                    // body is a FUNCTION so session_id is read from the ref on
                    // every send (stale-closure-safe).
                    body: () => ({
                        kind,
                        conversation_id: sessionIdRef.current,
                        ...(kind !== 'global' && contextType
                            ? { context_type: contextType, context_id: contextId ?? null }
                            : {}),
                    }),
                    // Intercept responses to capture X-Conversation-Id from the
                    // first turn (DefaultChatTransport has no onResponse hook; the
                    // `fetch` override is the only available interception point).
                    fetch: async (input, init) => {
                        const res = await window.fetch(input, init);
                        const newId = res.headers.get('X-Conversation-Id');
                        if (newId && !sessionIdRef.current) {
                            sessionIdRef.current = newId;
                            setCurrentSessionId(newId);
                            onNewSessionIdRef.current?.(newId);
                        }
                        return res;
                    },
                }),
            }),
        // Recreate when the session identity changes OR resetNonce bumps (New session).
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [kind, contextType, contextId, resetNonce],
    );

    function setSessionId(id: string) {
        sessionIdRef.current = id;
        setCurrentSessionId(id);
    }

    return { chat, sessionId: currentSessionId, setSessionId };
}
```

- [ ] **Step 4: Run-pass + type check**

```bash
docker compose -f docker/docker-compose.yml exec app npx vitest run resources/js/hooks/__tests__/use-session-chat.test.ts
docker compose -f docker/docker-compose.yml exec app npm run types:check
```

- [ ] **Step 5: Commit**

```bash
git add api/resources/js/hooks/use-session-chat.ts api/resources/js/hooks/__tests__/use-session-chat.test.ts
git commit -m "feat(ai): useSessionChat hook with dynamic body + X-Conversation-Id capture"
```

---

## Task 7: `AiChatPanel` extracted component

**Files:**
- Create: `api/resources/js/components/ai/ai-chat-panel.tsx`
- Test: `api/resources/js/components/ai/__tests__/ai-chat-panel.test.tsx`

**Interfaces:**
- Consumes: `useChat`, `Chat` (from `@ai-sdk/react`), `ProposalCard`, `CreatedRef` (from `proposal-card.tsx`), `parseProposal` (extracted from `ai-sidebar.tsx`).
- Produces: `AiChatPanel({ chat: Chat, kind: 'global'|'entity'|'chronicle', sessionId: string | null, onCreatedRef?: (ref: CreatedRef) => void, className?: string })` — the message list + input area, no sidebar wrapper. Renders `ProposalCard` for tool outputs; passes `onCreatedRef` through.

**Design note:** `parseProposal` is currently a module-level function inside `ai-sidebar.tsx`. Move it to its own export inside `proposal-card.tsx` (it's a helper for the same data type) so both `AiSidebar` and `AiChatPanel` import it from one place without circular deps.

- [ ] **Step 1: Extract `parseProposal` to `proposal-card.tsx`**

In `api/resources/js/components/ai/proposal-card.tsx`, add the function before the `ProposalCard` component (it was already in `ai-sidebar.tsx`):

```tsx
/**
 * Parse a raw tool output value into a Proposal, or return null if the
 * shape doesn't match. The AI agent returns a JSON string so we handle
 * both a string and a pre-parsed object.
 */
export function parseProposal(output: unknown): Proposal | null {
    try {
        const obj: unknown =
            typeof output === 'string' ? JSON.parse(output) : output;

        if (
            obj !== null &&
            typeof obj === 'object' &&
            'proposal_id' in obj &&
            'parts' in obj
        ) {
            return obj as Proposal;
        }
    } catch {
        /* ignore */
    }

    return null;
}
```

In `api/resources/js/components/ai/ai-sidebar.tsx`, remove the local `parseProposal` definition and import it from `proposal-card.tsx`:

```tsx
import { ProposalCard, parseProposal } from '@/components/ai/proposal-card';
import type { Proposal } from '@/components/ai/proposal-card';
```

(Remove the `type` re-export since it is now exported from `proposal-card`.)

Verify `npm run types:check` still passes after this refactor.

- [ ] **Step 2: Write a smoke test for `AiChatPanel`**

Create `api/resources/js/components/ai/__tests__/ai-chat-panel.test.tsx`:

```tsx
// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { describe, expect, it, vi } from 'vitest';
import { AiChatPanel } from '../ai-chat-panel';

vi.mock('@ai-sdk/react', () => ({
    useChat: () => ({
        messages: [],
        sendMessage: vi.fn(),
        status: 'idle',
        stop: vi.fn(),
    }),
}));

vi.mock('@/components/ui/ai/conversation', () => ({
    Conversation: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    ConversationContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    ConversationEmptyState: ({ title }: { title: string }) => <div>{title}</div>,
    ConversationScrollButton: () => null,
}));

vi.mock('@/components/ui/ai/message', () => ({
    Message: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    MessageContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    MessageResponse: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock('@/components/ui/button', () => ({
    Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { children: React.ReactNode }) => (
        <button {...props}>{children}</button>
    ),
}));

vi.mock('@/components/ui/textarea', () => ({
    Textarea: (props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) => <textarea {...props} />,
}));

describe('AiChatPanel', () => {
    it('renders the empty state for a global session', () => {
        const mockChat = {} as import('@ai-sdk/react').Chat;
        render(
            <AiChatPanel chat={mockChat} kind="global" sessionId={null} />,
        );

        expect(
            screen.getByText(/ask anything/i),
        ).toBeInTheDocument();
    });
});
```

- [ ] **Step 3: Run-fail**

```bash
docker compose -f docker/docker-compose.yml exec app npx vitest run resources/js/components/ai/__tests__/ai-chat-panel.test.tsx
```

Expected: FAIL — module not found.

- [ ] **Step 4: Implement `AiChatPanel`**

Create `api/resources/js/components/ai/ai-chat-panel.tsx`:

```tsx
import { useChat } from '@ai-sdk/react';
import type { Chat } from '@ai-sdk/react';
import { SendHorizonal, Square } from 'lucide-react';
import { useRef, useState } from 'react';
import { parseProposal, ProposalCard } from '@/components/ai/proposal-card';
import type { CreatedRef } from '@/components/ai/proposal-card';
import {
    Conversation,
    ConversationContent,
    ConversationEmptyState,
    ConversationScrollButton,
} from '@/components/ui/ai/conversation';
import {
    Message,
    MessageContent,
    MessageResponse,
} from '@/components/ui/ai/message';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';

type Props = {
    chat: Chat;
    kind: 'global' | 'entity' | 'chronicle';
    sessionId: string | null;
    onCreatedRef?: (ref: CreatedRef) => void;
    className?: string;
};

/**
 * Reusable chat panel: message list + input.
 *
 * Used both by AiSidebar (wrapped in a docked aside) and the Create with AI
 * page (rendered as a full-height column). Does NOT include the sidebar wrapper,
 * header, or close button — those are concerns of the parent.
 */
export function AiChatPanel({ chat, kind, sessionId: _sessionId, onCreatedRef, className }: Props) {
    const { messages, sendMessage, status, stop } = useChat({ chat });
    const [input, setInput] = useState('');
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const isStreaming = status === 'streaming' || status === 'submitted';
    const canSend = !isStreaming && input.trim().length > 0;

    function handleSubmit() {
        if (!canSend) return;
        const text = input.trim();
        setInput('');
        void sendMessage({ text });
        setTimeout(() => textareaRef.current?.focus(), 0);
    }

    function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
        }
    }

    const emptyTitle =
        kind === 'global'
            ? 'Ask anything — create or edit any record'
            : 'Ask anything about this record';

    const emptyDescription =
        kind === 'global'
            ? 'The assistant can create entities, chronicles, and relationships. Changes are proposed for your review before anything is saved.'
            : 'The assistant can read and update this entity or chronicle.';

    return (
        <div className={cn('flex flex-col', className)}>
            <Conversation className="flex-1 overflow-y-auto">
                <ConversationContent>
                    {messages.length === 0 && (
                        <ConversationEmptyState
                            title={emptyTitle}
                            description={emptyDescription}
                        />
                    )}

                    {messages.map((m) => (
                        <Message key={m.id} from={m.role}>
                            <MessageContent>
                                {m.parts.map((part, idx) => {
                                    if (part.type === 'text') {
                                        return (
                                            <MessageResponse
                                                key={idx}
                                                isAnimating={isStreaming}
                                            >
                                                {part.text}
                                            </MessageResponse>
                                        );
                                    }

                                    if (
                                        part.type === 'dynamic-tool' &&
                                        part.state === 'output-available'
                                    ) {
                                        const proposal = parseProposal(part.output);
                                        if (proposal) {
                                            return (
                                                <ProposalCard
                                                    key={idx}
                                                    proposal={proposal}
                                                    mode="edit"
                                                    onCreatedRef={onCreatedRef}
                                                />
                                            );
                                        }
                                    }

                                    if (
                                        part.type.startsWith('tool-') &&
                                        'state' in part &&
                                        part.state === 'output-available' &&
                                        'output' in part
                                    ) {
                                        const proposal = parseProposal(
                                            (part as { output: unknown }).output,
                                        );
                                        if (proposal) {
                                            return (
                                                <ProposalCard
                                                    key={idx}
                                                    proposal={proposal}
                                                    mode="edit"
                                                    onCreatedRef={onCreatedRef}
                                                />
                                            );
                                        }
                                    }

                                    return null;
                                })}
                            </MessageContent>
                        </Message>
                    ))}
                </ConversationContent>
                <ConversationScrollButton />
            </Conversation>

            <div className="border-t p-3">
                <div className="flex items-end gap-2">
                    <Textarea
                        ref={textareaRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Ask a question or request a change… (Enter to send, Shift+Enter for newline)"
                        rows={2}
                        className="min-h-0 flex-1 resize-none text-sm"
                    />
                    {isStreaming ? (
                        <Button
                            size="icon"
                            variant="outline"
                            onClick={stop}
                            title="Stop"
                            className="shrink-0"
                        >
                            <Square className="size-4" />
                        </Button>
                    ) : (
                        <Button
                            size="icon"
                            onClick={handleSubmit}
                            disabled={!canSend}
                            title="Send"
                            className="shrink-0"
                        >
                            <SendHorizonal className="size-4" />
                        </Button>
                    )}
                </div>
            </div>
        </div>
    );
}
```

- [ ] **Step 5: Run-pass + type check + lint**

```bash
docker compose -f docker/docker-compose.yml exec app npx vitest run resources/js/components/ai/__tests__/
docker compose -f docker/docker-compose.yml exec app npm run types:check
docker compose -f docker/docker-compose.yml exec app npm run lint:check
```

- [ ] **Step 6: Commit**

```bash
git add api/resources/js/components/ai/ai-chat-panel.tsx \
        api/resources/js/components/ai/ai-sidebar.tsx \
        api/resources/js/components/ai/proposal-card.tsx \
        api/resources/js/components/ai/__tests__/ai-chat-panel.test.tsx
git commit -m "feat(ai): AiChatPanel extracted component; parseProposal moved to proposal-card"
```

---

## Task 8: "Create with AI" page (`pages/ai/index.tsx`)

**Files:**
- Create: `api/resources/js/pages/ai/index.tsx`
- Test: `api/resources/js/pages/ai/__tests__/index.test.tsx`

**Interfaces:**
- Consumes: `AiChatPanel`, `useSessionChat`, `GET /ai/sessions` (`index` from `@/routes/ai/sessions`), `CreatedRef`.
- Produces: Default export `CreateWithAi` — Inertia page component. No server props needed (`{}` props, page is self-fetching). Two-column layout: left pane lists sessions; right pane is `AiChatPanel` for the selected/active session.

**Behavior:**
- On mount, fetch `GET /ai/sessions` → render a list ordered newest-first with `context_label` and `title`.
- "New session" button starts a fresh session. **Reset semantics (important):** the `Chat` instance lives in `useSessionChat` and is memoised, so bumping `chatKey` only remounts `AiChatPanel` — it does NOT by itself clear the underlying `Chat`/messages or the captured session id. To truly reset, pass `chatKey` (the new-session nonce) INTO `useSessionChat` so its `useMemo` deps include it and a fresh `Chat` is created, and reset `currentSessionId` to `null` there. Add `chatKey` (or a `resetNonce`) as a `useSessionChat` option and include it in the hook's `useMemo` dep array. (The same `key={chatKey}` on `AiChatPanel` then clears the `useChat` view.)
- Clicking a session from the list sets `activeSessionId` to that session's id — the `useSessionChat` hook receives the existing id, and the transport body will send `conversation_id` so the backend continues the conversation. (Rendering that session's prior messages on open is Phase C — in Phase B, selecting a session continues it; the message history is not replayed yet.)
- When a send completes and `useSessionChat.setSessionId` is called (after capturing `X-Conversation-Id`), refresh the session list via `refetch()`.
- When the apply response returns `created_ref`, render a dismissible banner/chip at the top of the right pane: `"Created: [label] — Open →"` linking to `created_ref.url` via `<Link>`.

- [ ] **Step 1: Write a smoke test**

Create `api/resources/js/pages/ai/__tests__/index.test.tsx`:

```tsx
// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { describe, expect, it, vi } from 'vitest';
import CreateWithAi from '../index';

vi.mock('@inertiajs/react', () => ({
    Head: () => null,
    Link: ({ children, href }: { children: React.ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
    usePage: () => ({ props: {} }),
}));

vi.mock('@/layouts/app-layout', () => ({
    default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock('@/components/ai/ai-chat-panel', () => ({
    AiChatPanel: () => <div data-testid="chat-panel" />,
}));

vi.mock('@/hooks/use-session-chat', () => ({
    useSessionChat: () => ({
        chat: {},
        sessionId: null,
        setSessionId: vi.fn(),
    }),
}));

let fetchMock: ReturnType<typeof vi.fn>;

beforeAll(() => {
    fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ data: [] }),
    } as unknown as Response);
    global.fetch = fetchMock;
});

afterEach(() => fetchMock.mockClear());

function renderPage() {
    const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
    });
    return render(
        <QueryClientProvider client={queryClient}>
            <CreateWithAi />
        </QueryClientProvider>,
    );
}

describe('Create with AI page', () => {
    it('renders the chat panel and a new session button', async () => {
        renderPage();

        await waitFor(() => {
            expect(screen.getByTestId('chat-panel')).toBeInTheDocument();
        });

        expect(screen.getByRole('button', { name: /new session/i })).toBeInTheDocument();
    });

    it('shows session list items when sessions are returned', async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                data: [
                    {
                        id: 'sess-1',
                        kind: 'entity',
                        context_label: 'Entity: Rome',
                        title: 'Edit Rome',
                        updated_at: '2026-06-25T10:00:00Z',
                    },
                ],
            }),
        } as unknown as Response);

        renderPage();

        await waitFor(() => {
            expect(screen.getByText('Edit Rome')).toBeInTheDocument();
        });
    });
});
```

- [ ] **Step 2: Run-fail**

```bash
docker compose -f docker/docker-compose.yml exec app npx vitest run resources/js/pages/ai/__tests__/index.test.tsx
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement the page**

Create `api/resources/js/pages/ai/index.tsx`:

```tsx
import { Head, Link } from '@inertiajs/react';
import { useQuery } from '@tanstack/react-query';
import { BotMessageSquare, Plus } from 'lucide-react';
import { useCallback, useState } from 'react';
import { AiChatPanel } from '@/components/ai/ai-chat-panel';
import type { CreatedRef } from '@/components/ai/proposal-card';
import { Button } from '@/components/ui/button';
import { useSessionChat } from '@/hooks/use-session-chat';
import AppLayout from '@/layouts/app-layout';
import type { BreadcrumbItem } from '@/types';

const breadcrumbs: BreadcrumbItem[] = [
    { title: 'Dashboard', href: '/dashboard' },
    { title: 'Create with AI', href: '/ai' },
];

type Session = {
    id: string;
    kind: string | null;
    context_id: string | null;
    context_label: string;
    title: string;
    updated_at: string | null;
};

type SessionsResponse = { data: Session[] };

export default function CreateWithAi() {
    // The id of the session open in the right pane. null = blank new session.
    const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
    // Incremented when "New session" is clicked — changes the key on the chat
    // to force a fresh Chat instance.
    const [chatKey, setChatKey] = useState(0);
    // Created-record links to display above the chat.
    const [createdRefs, setCreatedRefs] = useState<CreatedRef[]>([]);

    const {
        data: sessionsData,
        refetch: refetchSessions,
    } = useQuery<SessionsResponse>({
        queryKey: ['ai-sessions'],
        queryFn: async () => {
            const res = await fetch('/ai/sessions', {
                headers: { Accept: 'application/json' },
            });
            if (!res.ok) throw new Error('Failed to load sessions');
            return res.json() as Promise<SessionsResponse>;
        },
    });

    const sessions = sessionsData?.data ?? [];

    const { chat, setSessionId } = useSessionChat({
        sessionId: activeSessionId,
        kind: 'global',
        onNewSessionId: useCallback(
            (id: string) => {
                setActiveSessionId(id);
                void refetchSessions();
            },
            [refetchSessions],
        ),
    });

    function handleNewSession() {
        setChatKey((k) => k + 1);
        setActiveSessionId(null);
        setCreatedRefs([]);
    }

    function handleSelectSession(session: Session) {
        if (session.id === activeSessionId) return;
        setChatKey((k) => k + 1);
        setActiveSessionId(session.id);
        setSessionId(session.id);
        setCreatedRefs([]);
    }

    function handleCreatedRef(ref: CreatedRef) {
        setCreatedRefs((prev) => [...prev, ref]);
        void refetchSessions();
    }

    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title="Create with AI" />

            <div className="flex h-[calc(100svh-4rem)] gap-0">
                {/* ── Left: session list ────────────────────────────────── */}
                <aside className="flex w-64 shrink-0 flex-col border-r">
                    <div className="flex items-center justify-between border-b px-4 py-3">
                        <span className="text-sm font-semibold">Sessions</span>
                        <Button
                            size="sm"
                            variant="outline"
                            className="gap-1"
                            onClick={handleNewSession}
                        >
                            <Plus className="size-3.5" />
                            New session
                        </Button>
                    </div>

                    <ul className="flex-1 overflow-y-auto py-1">
                        {sessions.length === 0 && (
                            <li className="px-4 py-8 text-center text-xs text-muted-foreground">
                                No sessions yet. Start a conversation.
                            </li>
                        )}
                        {sessions.map((s) => (
                            <li key={s.id}>
                                <button
                                    type="button"
                                    onClick={() => handleSelectSession(s)}
                                    className={`w-full px-4 py-2 text-left text-sm transition-colors hover:bg-muted ${
                                        activeSessionId === s.id
                                            ? 'bg-muted font-medium'
                                            : ''
                                    }`}
                                >
                                    <div className="truncate font-medium">
                                        {s.title || '(untitled)'}
                                    </div>
                                    <div className="truncate text-xs text-muted-foreground">
                                        {s.context_label}
                                    </div>
                                </button>
                            </li>
                        ))}
                    </ul>
                </aside>

                {/* ── Right: chat panel ─────────────────────────────────── */}
                <div className="flex min-w-0 flex-1 flex-col">
                    {/* Created-record chips */}
                    {createdRefs.length > 0 && (
                        <div className="flex flex-wrap gap-2 border-b px-4 py-2">
                            {createdRefs.map((ref) => (
                                <Link
                                    key={ref.id}
                                    href={ref.url}
                                    className="inline-flex items-center gap-1 rounded-full border border-green-300 bg-green-50 px-3 py-1 text-xs font-medium text-green-800 hover:bg-green-100 dark:border-green-700 dark:bg-green-950/30 dark:text-green-300"
                                >
                                    <span className="capitalize">{ref.type}:</span>
                                    {ref.label}
                                    <span className="ml-1 opacity-60">→</span>
                                </Link>
                            ))}
                        </div>
                    )}

                    {activeSessionId === null && chatKey === 0 && sessions.length === 0 ? (
                        /* First-run empty state */
                        <div className="flex flex-1 flex-col items-center justify-center gap-3 text-muted-foreground">
                            <BotMessageSquare className="size-10 opacity-40" />
                            <p className="text-sm">
                                Start a new session to create or edit records with AI.
                            </p>
                            <Button onClick={handleNewSession} variant="outline" size="sm">
                                <Plus className="mr-1 size-3.5" />
                                New session
                            </Button>
                        </div>
                    ) : (
                        <AiChatPanel
                            key={chatKey}
                            chat={chat}
                            kind="global"
                            sessionId={activeSessionId}
                            onCreatedRef={handleCreatedRef}
                            className="flex-1"
                        />
                    )}
                </div>
            </div>
        </AppLayout>
    );
}
```

- [ ] **Step 4: Run-pass + full check**

```bash
docker compose -f docker/docker-compose.yml exec app npx vitest run resources/js/pages/ai/__tests__/index.test.tsx
docker compose -f docker/docker-compose.yml exec app npm run types:check
docker compose -f docker/docker-compose.yml exec app npm run lint:check
docker compose -f docker/docker-compose.yml exec app npm run build
```

All must pass.

- [ ] **Step 5: Commit**

```bash
git add api/resources/js/pages/ai/ 
git commit -m "feat(ai): Create with AI two-pane page (session list + global chat)"
```

---

## Task 9: Nav entry in `app-sidebar.tsx`

**Files:**
- Modify: `api/resources/js/components/app-sidebar.tsx`
- Test: none needed (nav items are static data; types:check + build cover it)

**Interfaces:**
- Produces: a "Create with AI" nav item in `mainNavItems` above "Entities", linking to the literal path `/ai` (no Wayfinder helper).

- [ ] **Step 1: Read `app-sidebar.tsx` to match the existing nav-item convention**

READ `api/resources/js/components/app-sidebar.tsx` and look at how the existing `mainNavItems` entries declare `href` (literal string like `'/dashboard'` vs a Wayfinder helper call) and which Lucide icons are imported. Match whatever the existing items do. The `NavItem['href']` type accepts a string, so a literal `'/ai'` is valid.

- [ ] **Step 2: Edit `app-sidebar.tsx`**

Add to `mainNavItems` as the first item after `Dashboard` and before `Entities`, using a literal href:

```tsx
    {
        title: 'Create with AI',
        href: '/ai',
        icon: BotMessageSquare,
    },
```

`BotMessageSquare` is already used by `ai-sidebar.tsx`, so it is available in the installed `lucide-react`. Add it to the existing `lucide-react` import in `app-sidebar.tsx` (keep imports alphabetised if the file is). If for any reason it is not resolvable, use `Sparkles` (already used in the admin) — but `BotMessageSquare` should work since the sidebar uses it.

- [ ] **Step 3: Type check + build**

```bash
docker compose -f docker/docker-compose.yml exec app npm run types:check
docker compose -f docker/docker-compose.yml exec app npm run build
```

- [ ] **Step 4: Commit**

```bash
git add api/resources/js/components/app-sidebar.tsx
git commit -m "feat(ai): add Create with AI nav entry in admin sidebar"
```

---

## Task 10: Full integration smoke — backend + frontend regression

**Files:** No new files — this is a verification pass.

- [ ] **Step 1: Full Laravel test suite (AI-related)**

```bash
docker compose -f docker/docker-compose.yml exec app php artisan test --filter "Ai|Global|Chronicle|Entity" 2>&1 | tail -30
```

Expected: all green. If stale: `docker compose -f docker/docker-compose.yml restart app` then re-run.

- [ ] **Step 2: Full frontend test suite**

```bash
docker compose -f docker/docker-compose.yml exec app npx vitest run
```

Expected: all green.

- [ ] **Step 3: Full build**

```bash
docker compose -f docker/docker-compose.yml exec app npm run types:check
docker compose -f docker/docker-compose.yml exec app npm run lint:check
docker compose -f docker/docker-compose.yml exec app npm run build
```

- [ ] **Step 4: Pint clean**

```bash
docker compose -f docker/docker-compose.yml exec app ./vendor/bin/pint --test
```

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore(ai): Phase B integration — GlobalAgent + Create with AI page complete"
```

---

## Self-Review

### Spec coverage check (spec §5.1/§5.2/§5.4/§6.1/§6.2/§6.4)

| Spec requirement | Covered by |
|---|---|
| `GlobalAgent` full toolset (§5.1) | Task 1 |
| `instructions()` global Blade template, no redirect (§5.1) | Task 1 |
| Chat controller `kind=global` → GlobalAgent (§5.2) | Task 2 |
| Chat controller skip record lookup for global (§5.2) | Task 2 |
| Session tagged `context_type='global'`, `context_id=null` (§5.2) | Task 2 |
| Apply: global → `created_ref` not `redirect_url` (§5.4) | Task 3 |
| Apply: scoped → `redirect_url` unchanged (§5.4) | Task 3 (test) |
| `GET /ai` Inertia page + route `ai.index` (§6.1) | Task 4 |
| Two-pane page: left session list + right chat (§6.1) | Task 8 |
| New session button starts blank global session (§6.1) | Task 8 |
| Global apply stays in session; created record as inline link (§6.1) | Tasks 5 + 8 |
| Transport sends `kind` + `session_id` (§6.4) | Task 6 |
| Nav entry for the page (§6.1) | Task 9 |
| Phase A preconditions: migration, `X-Conversation-Id`, session endpoints | Verified present (existing code) |

**Spec items intentionally excluded (Phase C):**
- Session list shows "all kinds" with resume-into-record-agent (Phase C).
- Message + proposal-card replay on session open (Phase C — the page loads sessions as a list but clicking a session continues from the last message, not replaying history).
- Session delete from the page (Phase C).

The page resolves the spec's Phase B: "global session → `GlobalAgent`; stay-in-session; created-record links; page + nav."

### Placeholder scan

No TBD, TODO, or "fill in details" language. All code steps include complete code. Exact commands included throughout.

### Type consistency

- `CreatedRef` exported from `proposal-card.tsx`, consumed by `AiChatPanel` and `pages/ai/index.tsx`.
- `useSessionChat` returns `{ chat: Chat, sessionId: string | null, setSessionId: (id: string) => void }` — consumed in Task 8 with those exact names.
- `parseProposal` moved to `proposal-card.tsx` and re-imported in `ai-sidebar.tsx` — same function, same signature.
- `kind` string union `'global'|'entity'|'chronicle'` consistent across `useSessionChat`, `AiChatPanel`, and the controller validator.
- `context_type='global'` stored in the DB, sent in session-list responses as `kind` — consistent with Phase A `AiSessionController.index` which already accepts `context_type=global` in its filter.
