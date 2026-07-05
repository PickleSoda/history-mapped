# AI Sessions — Phase A (Sessions Backbone) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every AI conversation a first-class, owner-scoped, listable **session** — tag conversations with their context, have the chat controller own session creation and return the id, and expose list / replay / delete endpoints.

**Architecture:** A "session" is one `agent_conversations` row (the `laravel/ai` SDK's conversation). We add `context_type`/`context_id` columns, and the controller **mints the conversation UUID itself**, creates the tagged row, calls `RemembersConversations::continue($id, $user)` (the SDK then writes messages under our row instead of generating its own), and returns the id via an `X-Conversation-Id` response header. New `AiSessionController` endpoints list a user's sessions, return a replay payload (messages + staged-proposal statuses joined by `conversation_id`), and delete a session (cascading messages + still-pending proposals). **Backend only** — frontend session-wiring is Phase B.

**Tech Stack:** PHP 8.4 / Laravel 13, `laravel/ai` v0.8.1, PostgreSQL. All backend cmds run in the Docker `app` container.

## Global Constraints

- Backend cmds: `docker compose -f docker/docker-compose.yml exec app <cmd>`. Restart `app` after editing existing PHP files if a test runs stale code: `docker compose -f docker/docker-compose.yml restart app`.
- A **session ≡ a conversation** = one `agent_conversations` row keyed by a string UUID. The HTTP/request field stays named `conversation_id` (the prior feature and its tests already use it); the response header is `X-Conversation-Id`.
- The SDK is authoritative and verified: `continue(string $conversationId, object $as)` only SETS the id (no DB lookup); `forUser($user)` sets it null (→ SDK generates one). The `RememberConversation` middleware creates a row via `Str::uuid7()` ONLY when `currentConversation()` is null. So calling `continue()` with our own pre-created id makes the SDK skip row creation and write messages under our row. (`api/vendor/laravel/ai/src/Concerns/RemembersConversations.php`, `.../Middleware/RememberConversation.php`, `.../Storage/DatabaseConversationStore.php`.)
- Vendored models (use directly; `$guarded=[]`, string PK, `$incrementing=false`): `Laravel\Ai\Models\Conversation` (table `agent_conversations`; `messages(): HasMany`) and `Laravel\Ai\Models\ConversationMessage` (table `agent_conversation_messages`; casts `tool_calls`/`tool_results`/`attachments`/`usage`/`meta` to array; `conversation(): BelongsTo`).
- `agent_conversation_messages` has NO FK to `agent_conversations` (plain indexed `conversation_id` string). Deletes must be explicit.
- Proposal staging (unchanged): `App\Models\Ai\ProposedChange` (table `agent_proposed_changes`, `HasUuids`, fillable `['user_id','conversation_id','context_type','context_id']`, `parts(): HasMany`) and `App\Models\Ai\ProposedChangePart` (table `agent_proposed_change_parts`, fillable incl. `status`; `status` ∈ `pending|applied|discarded`, default `pending`; `change(): BelongsTo`).
- All new routes live under the existing `Route::prefix('ai')->name('ai.')` group and are gated by `permission:entities.write` (admins bypass via `Gate::before`). Ownership is enforced in-controller on `agent_conversations.user_id === auth()->id()`.
- Pint clean (`./vendor/bin/pint --test`). TDD throughout. Test helpers that already exist on `Tests\TestCase`: `userWithPermissions(['entities.write'])`, `userWithRole('admin'|'user')`. Stub the AI provider with `EntityEditorAgent::fake(['…'])` (per-agent static fake) — never a real provider call.

## File Structure

- Create: `api/database/migrations/2026_06_25_000001_add_context_to_agent_conversations.php` — adds `context_type` + `context_id` to `agent_conversations`.
- Modify: `api/app/Http/Controllers/Admin/Ai/AiChatController.php` — own session creation, thread `conversation_id` into the proposal context, return `X-Conversation-Id`.
- Create: `api/app/Http/Controllers/Admin/Ai/AiSessionController.php` — `index` / `show` / `destroy`.
- Modify: `api/routes/web.php` — register the three session routes inside the `ai` group.
- Tests: `api/tests/Feature/Ai/AiChatStreamTest.php` (extend — Task 2), `api/tests/Feature/Ai/AiSessionEndpointTest.php` (create — Tasks 3-5), plus a tiny schema test in `AiSessionEndpointTest` (Task 1).

---

## Task 1: Migration — add `context_type` + `context_id` to `agent_conversations`

**Files:**
- Create: `api/database/migrations/2026_06_25_000001_add_context_to_agent_conversations.php`
- Test: `api/tests/Feature/Ai/AiSessionEndpointTest.php` (new file; one schema test for now)

**Interfaces:**
- Produces: `agent_conversations.context_type` (nullable string), `agent_conversations.context_id` (nullable string), composite index `[context_type, context_id]`.

- [ ] **Step 1: Write the failing test**

Create `api/tests/Feature/Ai/AiSessionEndpointTest.php`:

```php
<?php

namespace Tests\Feature\Ai;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Schema;
use Tests\TestCase;

class AiSessionEndpointTest extends TestCase
{
    use RefreshDatabase;

    public function test_agent_conversations_has_context_columns(): void
    {
        $this->assertTrue(Schema::hasColumn('agent_conversations', 'context_type'));
        $this->assertTrue(Schema::hasColumn('agent_conversations', 'context_id'));
    }
}
```

- [ ] **Step 2: Run it, expect failure.** `docker compose -f docker/docker-compose.yml exec app php artisan test --filter AiSessionEndpointTest` → FAIL (columns missing).

- [ ] **Step 3: Write the migration**

```php
<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('agent_conversations', function (Blueprint $table) {
            $table->string('context_type')->nullable()->after('user_id');
            $table->string('context_id')->nullable()->after('context_type');
            $table->index(['context_type', 'context_id']);
        });
    }

    public function down(): void
    {
        Schema::table('agent_conversations', function (Blueprint $table) {
            $table->dropIndex(['context_type', 'context_id']);
            $table->dropColumn(['context_type', 'context_id']);
        });
    }
};
```

- [ ] **Step 4: Run the test** → PASS (RefreshDatabase runs migrations). Then Pint:
`docker compose -f docker/docker-compose.yml exec app ./vendor/bin/pint database/migrations`

- [ ] **Step 5: Commit** `git commit -am "feat(ai): add context columns to agent_conversations"`.

---

## Task 2: Controller owns session creation + returns `X-Conversation-Id`

**Files:**
- Modify: `api/app/Http/Controllers/Admin/Ai/AiChatController.php`
- Test: `api/tests/Feature/Ai/AiChatStreamTest.php` (extend)

**Interfaces:**
- Consumes: `Laravel\Ai\Models\Conversation`, the context columns from Task 1.
- Produces: `/ai/chat` always resolves a session id (minting + creating a tagged `agent_conversations` row when no `conversation_id` is supplied; authorizing + reusing when one is), sets `$context['conversation_id']` to that id (so staged proposals tie to the session), and returns the streamed response with an `X-Conversation-Id` header. New return type: `\Symfony\Component\HttpFoundation\Response`.

**Behavior contract (read before editing):** Keep ALL existing logic — prompt extraction from `prompt`/`messages`, the `mode`/`context_id` 422 guard, the `match(true)` agent selection, and the `EntityCreatorAgent`/`ChronicleCreatorAgent` create-mode arms. Only the conversation-wiring tail and the return type change.

- [ ] **Step 1: Write the failing tests** (append to `AiChatStreamTest`)

```php
    public function test_chat_creates_and_returns_a_session_for_a_new_conversation(): void
    {
        $this->fakeWikidata();
        EntityEditorAgent::fake(['Hello from the fake agent.']);

        $user = $this->userWithPermissions(['entities.write']);
        $entity = $this->makeEntity();

        $response = $this->actingAs($user)->postJson('/ai/chat', [
            'context_type' => 'entity',
            'context_id' => $entity->entity_id,
            'prompt' => 'Tell me about this entity.',
        ]);

        $response->assertOk();
        $response->assertHeader('X-Conversation-Id');

        $sessionId = $response->headers->get('X-Conversation-Id');
        $this->assertNotEmpty($sessionId);
        $this->assertDatabaseHas('agent_conversations', [
            'id' => $sessionId,
            'user_id' => $user->id,
            'context_type' => 'entity',
            'context_id' => $entity->entity_id,
        ]);
    }

    public function test_chat_continues_a_session_the_user_owns_without_creating_a_new_row(): void
    {
        $this->fakeWikidata();
        EntityEditorAgent::fake(['Continuing.']);

        $user = $this->userWithPermissions(['entities.write']);
        $entity = $this->makeEntity();

        $existing = \Laravel\Ai\Models\Conversation::create([
            'id' => (string) \Illuminate\Support\Str::uuid7(),
            'user_id' => $user->id,
            'title' => 'Earlier chat',
            'context_type' => 'entity',
            'context_id' => $entity->entity_id,
        ]);

        $response = $this->actingAs($user)->postJson('/ai/chat', [
            'context_type' => 'entity',
            'context_id' => $entity->entity_id,
            'conversation_id' => $existing->id,
            'prompt' => 'Follow-up.',
        ]);

        $response->assertOk();
        $this->assertSame($existing->id, $response->headers->get('X-Conversation-Id'));
        $this->assertSame(1, \Laravel\Ai\Models\Conversation::query()->count());
    }

    public function test_chat_rejects_continuing_a_session_owned_by_another_user(): void
    {
        $this->fakeWikidata();
        EntityEditorAgent::fake(['nope']);

        $owner = $this->userWithPermissions(['entities.write']);
        $intruder = $this->userWithPermissions(['entities.write']);
        $entity = $this->makeEntity();

        $others = \Laravel\Ai\Models\Conversation::create([
            'id' => (string) \Illuminate\Support\Str::uuid7(),
            'user_id' => $owner->id,
            'title' => 'Owner chat',
            'context_type' => 'entity',
            'context_id' => $entity->entity_id,
        ]);

        $this->actingAs($intruder)->postJson('/ai/chat', [
            'context_type' => 'entity',
            'context_id' => $entity->entity_id,
            'conversation_id' => $others->id,
            'prompt' => 'let me in',
        ])->assertForbidden();
    }
```

- [ ] **Step 2: Run-fail.** `… php artisan test --filter AiChatStreamTest` → the three new tests FAIL (no header / row not tagged / no 403).

- [ ] **Step 3: Edit the controller.** Add imports and replace the conversation-wiring tail + return type.

Add to the `use` block:

```php
use Illuminate\Support\Str;
use Laravel\Ai\Models\Conversation;
use Symfony\Component\HttpFoundation\Response;
```

Change the method signature return type from `: StreamableAgentResponse` to `: Response` (and drop the now-unused `use Laravel\Ai\Responses\StreamableAgentResponse;` import).

Replace this existing block:

```php
        $context = [
            'user_id' => (string) $user->id,
            'context_type' => $data['context_type'],
            'context_id' => $contextId,
            'conversation_id' => $conversationId,
        ];
```

…and the existing tail (`$agent = match … ; if ($conversationId !== null) { $agent->continue(...) } else { $agent->forUser($user) } return $agent->stream(...)->usingVercelDataProtocol();`) with:

```php
        // Resolve the session (agent_conversations row). Either continue one the
        // user owns, or mint + create a fresh tagged row so proposals and message
        // persistence are tied to a real, listable session from the first message.
        if ($conversationId !== null) {
            $conversation = Conversation::find($conversationId);

            if ($conversation === null) {
                abort(404, 'Unknown conversation.');
            }

            if ((string) $conversation->user_id !== (string) $user->id) {
                abort(403, 'You do not own this conversation.');
            }
        } else {
            $conversationId = (string) Str::uuid7();

            Conversation::create([
                'id' => $conversationId,
                'user_id' => $user->id,
                'title' => Str::limit($promptText, 60, ''),
                'context_type' => $data['context_type'],
                'context_id' => $contextId,
            ]);
        }

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

        // We pre-created the row, so continue() makes the SDK persist messages
        // under our id instead of generating its own.
        $agent->continue($conversationId, $user);

        $response = $agent->stream($promptText)->usingVercelDataProtocol()->toResponse($request);
        $response->headers->set('X-Conversation-Id', $conversationId);

        return $response;
```

> Note: the `match` arms are unchanged from today — they are repeated here only because the surrounding block is replaced. Edit-mode `findOrFail` and create-mode sentinel `context_id='create'` behavior is preserved exactly.

- [ ] **Step 4: Run-pass.** `… php artisan test --filter AiChatStreamTest` → all pass (existing + 3 new). If stale, `docker compose -f docker/docker-compose.yml restart app` then re-run. Pint the controller.

- [ ] **Step 5: Commit** `git commit -am "feat(ai): chat controller owns session creation + returns X-Conversation-Id"`.

---

## Task 3: `GET /ai/sessions` — owner-scoped list with context label

**Files:**
- Create: `api/app/Http/Controllers/Admin/Ai/AiSessionController.php`
- Modify: `api/routes/web.php`
- Test: `api/tests/Feature/Ai/AiSessionEndpointTest.php` (extend)

**Interfaces:**
- Consumes: `Laravel\Ai\Models\Conversation`, `App\Models\Entity`, `App\Models\Chronicle`.
- Produces: `GET ai/sessions` (name `ai.sessions.index`) → `{ data: [{ id, kind, context_id, context_label, title, updated_at }] }` for the current user, newest first; optional `?context_type=&context_id=` filter. `kind` = the row's `context_type` (`entity`|`chronicle`; `global` arrives in Phase B). `AiSessionController::contextLabel(?string $type, ?string $id): string` is the shared label resolver reused by Task 4.

- [ ] **Step 1: Write the failing test** (append)

```php
    public function test_sessions_index_lists_only_the_callers_sessions_newest_first(): void
    {
        $user = $this->userWithPermissions(['entities.write']);
        $other = $this->userWithPermissions(['entities.write']);

        $entity = \App\Models\Entity::factory()->create(['name' => 'Rome']);

        $older = \Laravel\Ai\Models\Conversation::create([
            'id' => (string) \Illuminate\Support\Str::uuid7(),
            'user_id' => $user->id, 'title' => 'Older',
            'context_type' => 'entity', 'context_id' => $entity->entity_id,
            'updated_at' => now()->subHour(),
        ]);
        $newer = \Laravel\Ai\Models\Conversation::create([
            'id' => (string) \Illuminate\Support\Str::uuid7(),
            'user_id' => $user->id, 'title' => 'Newer',
            'context_type' => 'entity', 'context_id' => $entity->entity_id,
            'updated_at' => now(),
        ]);
        \Laravel\Ai\Models\Conversation::create([
            'id' => (string) \Illuminate\Support\Str::uuid7(),
            'user_id' => $other->id, 'title' => 'Not mine',
            'context_type' => 'entity', 'context_id' => $entity->entity_id,
        ]);

        $response = $this->actingAs($user)->getJson('/ai/sessions');

        $response->assertOk();
        $ids = array_column($response->json('data'), 'id');
        $this->assertSame([$newer->id, $older->id], $ids); // newest first, others excluded
        $this->assertSame('Entity: Rome', $response->json('data.0.context_label'));
    }

    public function test_sessions_index_filters_by_context(): void
    {
        $user = $this->userWithPermissions(['entities.write']);
        $e1 = \App\Models\Entity::factory()->create(['name' => 'Rome']);
        $e2 = \App\Models\Entity::factory()->create(['name' => 'Carthage']);

        foreach ([$e1, $e2] as $e) {
            \Laravel\Ai\Models\Conversation::create([
                'id' => (string) \Illuminate\Support\Str::uuid7(),
                'user_id' => $user->id, 'title' => 'c',
                'context_type' => 'entity', 'context_id' => $e->entity_id,
            ]);
        }

        $response = $this->actingAs($user)->getJson(
            '/ai/sessions?context_type=entity&context_id='.$e2->entity_id,
        );

        $response->assertOk()->assertJsonCount(1, 'data');
        $this->assertSame($e2->entity_id, $response->json('data.0.context_id'));
    }

    public function test_sessions_index_requires_entities_write(): void
    {
        $user = $this->userWithRole('user');
        $this->actingAs($user)->getJson('/ai/sessions')->assertForbidden();
    }
```

- [ ] **Step 2: Run-fail.** `… php artisan test --filter AiSessionEndpointTest` → new tests FAIL (route missing → 404/405).

- [ ] **Step 3: Create the controller**

```php
<?php

namespace App\Http\Controllers\Admin\Ai;

use App\Http\Controllers\Controller;
use App\Models\Chronicle;
use App\Models\Entity;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Laravel\Ai\Models\Conversation;

class AiSessionController extends Controller
{
    /**
     * List the current user's sessions, newest first.
     * Optional ?context_type=&context_id= narrows to one bound record.
     */
    public function index(Request $request): JsonResponse
    {
        $data = $request->validate([
            'context_type' => 'nullable|in:entity,chronicle,global',
            'context_id' => 'nullable|string',
        ]);

        $query = Conversation::query()
            ->where('user_id', $request->user()->id)
            ->orderByDesc('updated_at');

        if (! empty($data['context_type'])) {
            $query->where('context_type', $data['context_type']);
        }

        if (! empty($data['context_id'])) {
            $query->where('context_id', $data['context_id']);
        }

        $sessions = $query->get()->map(fn (Conversation $c) => [
            'id' => $c->id,
            'kind' => $c->context_type,
            'context_id' => $c->context_id,
            'context_label' => $this->contextLabel($c->context_type, $c->context_id),
            'title' => $c->title,
            'updated_at' => optional($c->updated_at)->toIso8601String(),
        ])->all();

        return response()->json(['data' => $sessions]);
    }

    /**
     * Human label for a session's bound context (e.g. "Entity: Rome").
     */
    public function contextLabel(?string $type, ?string $id): string
    {
        if ($type === 'global') {
            return 'Global';
        }

        if ($id === null || $id === 'create') {
            return $type === 'chronicle' ? 'New chronicle' : 'New entity';
        }

        if ($type === 'entity') {
            return 'Entity: '.(Entity::find($id)?->name ?? $id);
        }

        if ($type === 'chronicle') {
            return 'Chronicle: '.(Chronicle::find($id)?->title ?? $id);
        }

        return $id;
    }
}
```

- [ ] **Step 4: Register the route.** In `api/routes/web.php`, inside the existing `Route::prefix('ai')->name('ai.')->group(function () { … })`, add (import `use App\Http\Controllers\Admin\Ai\AiSessionController;` at the top):

```php
        Route::middleware('permission:entities.write')->group(function () {
            Route::get('sessions', [AiSessionController::class, 'index'])->name('sessions.index');
        });
```

- [ ] **Step 5: Run-pass.** `… php artisan test --filter AiSessionEndpointTest` → pass. Pint the controller + routes.

- [ ] **Step 6: Commit** `git commit -am "feat(ai): GET /ai/sessions session list"`.

---

## Task 4: `GET /ai/sessions/{conversation}` — replay payload

**Files:**
- Modify: `api/app/Http/Controllers/Admin/Ai/AiSessionController.php` (+`show`)
- Modify: `api/routes/web.php`
- Test: `api/tests/Feature/Ai/AiSessionEndpointTest.php` (extend)

**Interfaces:**
- Consumes: `Laravel\Ai\Models\Conversation` (+`messages()`), `App\Models\Ai\ProposedChange` (+`parts()`).
- Produces: `GET ai/sessions/{conversation}` (name `ai.sessions.show`) → `{ session: {id, kind, context_id, context_label, title}, messages: [{id, role, content, tool_calls, tool_results, created_at}], proposals: [{proposal_id, parts: [{key, tool, human_diff, status, result_id}]}] }`. 403 if not owner, 404 if missing. Messages ordered by `created_at` asc; proposals are those with `conversation_id === {conversation}`.

- [ ] **Step 1: Write the failing test** (append)

```php
    public function test_session_show_returns_messages_and_proposal_statuses(): void
    {
        $user = $this->userWithPermissions(['entities.write']);
        $entity = \App\Models\Entity::factory()->create(['name' => 'Rome']);

        $session = \Laravel\Ai\Models\Conversation::create([
            'id' => (string) \Illuminate\Support\Str::uuid7(),
            'user_id' => $user->id, 'title' => 'Chat',
            'context_type' => 'entity', 'context_id' => $entity->entity_id,
        ]);

        \Laravel\Ai\Models\ConversationMessage::create([
            'id' => (string) \Illuminate\Support\Str::uuid7(),
            'conversation_id' => $session->id, 'user_id' => $user->id,
            'agent' => 'X', 'role' => 'user', 'content' => 'hi',
            'created_at' => now()->subMinute(), 'updated_at' => now()->subMinute(),
        ]);
        \Laravel\Ai\Models\ConversationMessage::create([
            'id' => (string) \Illuminate\Support\Str::uuid7(),
            'conversation_id' => $session->id, 'user_id' => $user->id,
            'agent' => 'X', 'role' => 'assistant', 'content' => 'hello',
            'created_at' => now(), 'updated_at' => now(),
        ]);

        $change = \App\Models\Ai\ProposedChange::create([
            'user_id' => (string) $user->id,
            'conversation_id' => $session->id,
            'context_type' => 'entity', 'context_id' => $entity->entity_id,
        ]);
        $change->parts()->create([
            'key' => 'fields', 'tool' => 'update_entity_fields',
            'payload' => ['summary' => 'x'], 'human_diff' => ['summary' => 'set summary'],
            'status' => 'applied', 'result_id' => $entity->entity_id,
        ]);

        $response = $this->actingAs($user)->getJson('/ai/sessions/'.$session->id);

        $response->assertOk();
        $this->assertSame(['hi', 'hello'], array_column($response->json('messages'), 'content'));
        $this->assertSame('applied', $response->json('proposals.0.parts.0.status'));
        $this->assertSame('update_entity_fields', $response->json('proposals.0.parts.0.tool'));
    }

    public function test_session_show_forbids_non_owner(): void
    {
        $owner = $this->userWithPermissions(['entities.write']);
        $intruder = $this->userWithPermissions(['entities.write']);

        $session = \Laravel\Ai\Models\Conversation::create([
            'id' => (string) \Illuminate\Support\Str::uuid7(),
            'user_id' => $owner->id, 'title' => 'Chat',
            'context_type' => 'entity', 'context_id' => 'x',
        ]);

        $this->actingAs($intruder)->getJson('/ai/sessions/'.$session->id)->assertForbidden();
    }
```

- [ ] **Step 2: Run-fail.** → FAIL (route/method missing).

- [ ] **Step 3: Add `show` to `AiSessionController`** (add imports `use App\Models\Ai\ProposedChange;` and `use Laravel\Ai\Models\ConversationMessage;`):

```php
    public function show(Request $request, string $conversation): JsonResponse
    {
        $session = Conversation::find($conversation);

        if ($session === null) {
            abort(404);
        }

        if ((string) $session->user_id !== (string) $request->user()->id) {
            abort(403);
        }

        $messages = ConversationMessage::query()
            ->where('conversation_id', $session->id)
            ->orderBy('created_at')
            ->get()
            ->map(fn (ConversationMessage $m) => [
                'id' => $m->id,
                'role' => $m->role,
                'content' => $m->content,
                'tool_calls' => $m->tool_calls,     // array (model cast)
                'tool_results' => $m->tool_results, // array (model cast)
                'created_at' => optional($m->created_at)->toIso8601String(),
            ])->all();

        $proposals = ProposedChange::with('parts')
            ->where('conversation_id', $session->id)
            ->get()
            ->map(fn (ProposedChange $change) => [
                'proposal_id' => $change->id,
                'parts' => $change->parts->map(fn ($p) => [
                    'key' => $p->key,
                    'tool' => $p->tool,
                    'human_diff' => $p->human_diff,
                    'status' => $p->status,
                    'result_id' => $p->result_id,
                ])->all(),
            ])->all();

        return response()->json([
            'session' => [
                'id' => $session->id,
                'kind' => $session->context_type,
                'context_id' => $session->context_id,
                'context_label' => $this->contextLabel($session->context_type, $session->context_id),
                'title' => $session->title,
            ],
            'messages' => $messages,
            'proposals' => $proposals,
        ]);
    }
```

- [ ] **Step 4: Register the route** (inside the same gated group as Task 3):

```php
            Route::get('sessions/{conversation}', [AiSessionController::class, 'show'])->name('sessions.show');
```

- [ ] **Step 5: Run-pass + Pint. Step 6: Commit** `git commit -am "feat(ai): GET /ai/sessions/{id} replay payload"`.

---

## Task 5: `DELETE /ai/sessions/{conversation}` — owner-checked cascade

**Files:**
- Modify: `api/app/Http/Controllers/Admin/Ai/AiSessionController.php` (+`destroy`)
- Modify: `api/routes/web.php`
- Test: `api/tests/Feature/Ai/AiSessionEndpointTest.php` (extend)

**Interfaces:**
- Produces: `DELETE ai/sessions/{conversation}` (name `ai.sessions.destroy`) → 200 `{ deleted: true }`. Deletes the conversation row, its `agent_conversation_messages`, and any `agent_proposed_changes` for this conversation that have **no applied part** (still-pending/discarded proposals — nothing materialized) plus their parts. Proposals with ≥1 applied part are KEPT (audit trail). 403 non-owner (and nothing deleted), 404 missing.

- [ ] **Step 1: Write the failing test** (append)

```php
    public function test_session_destroy_removes_conversation_messages_and_pending_proposals_but_keeps_applied(): void
    {
        $user = $this->userWithPermissions(['entities.write']);
        $entity = \App\Models\Entity::factory()->create(['name' => 'Rome']);

        $session = \Laravel\Ai\Models\Conversation::create([
            'id' => (string) \Illuminate\Support\Str::uuid7(),
            'user_id' => $user->id, 'title' => 'Chat',
            'context_type' => 'entity', 'context_id' => $entity->entity_id,
        ]);
        \Laravel\Ai\Models\ConversationMessage::create([
            'id' => (string) \Illuminate\Support\Str::uuid7(),
            'conversation_id' => $session->id, 'user_id' => $user->id,
            'agent' => 'X', 'role' => 'user', 'content' => 'hi',
        ]);

        $pending = \App\Models\Ai\ProposedChange::create([
            'user_id' => (string) $user->id, 'conversation_id' => $session->id,
            'context_type' => 'entity', 'context_id' => $entity->entity_id,
        ]);
        $pendingPart = $pending->parts()->create([
            'key' => 'a', 'tool' => 'update_entity_fields',
            'payload' => [], 'human_diff' => [], 'status' => 'pending',
        ]);

        $applied = \App\Models\Ai\ProposedChange::create([
            'user_id' => (string) $user->id, 'conversation_id' => $session->id,
            'context_type' => 'entity', 'context_id' => $entity->entity_id,
        ]);
        $appliedPart = $applied->parts()->create([
            'key' => 'b', 'tool' => 'update_entity_fields',
            'payload' => [], 'human_diff' => [], 'status' => 'applied',
            'result_id' => $entity->entity_id,
        ]);

        $this->actingAs($user)->deleteJson('/ai/sessions/'.$session->id)
            ->assertOk()->assertJson(['deleted' => true]);

        $this->assertDatabaseMissing('agent_conversations', ['id' => $session->id]);
        $this->assertDatabaseMissing('agent_conversation_messages', ['conversation_id' => $session->id]);
        $this->assertDatabaseMissing('agent_proposed_changes', ['id' => $pending->id]);
        $this->assertDatabaseMissing('agent_proposed_change_parts', ['id' => $pendingPart->id]);
        $this->assertDatabaseHas('agent_proposed_changes', ['id' => $applied->id]);
        $this->assertDatabaseHas('agent_proposed_change_parts', ['id' => $appliedPart->id]);
    }

    public function test_session_destroy_forbids_non_owner_and_deletes_nothing(): void
    {
        $owner = $this->userWithPermissions(['entities.write']);
        $intruder = $this->userWithPermissions(['entities.write']);

        $session = \Laravel\Ai\Models\Conversation::create([
            'id' => (string) \Illuminate\Support\Str::uuid7(),
            'user_id' => $owner->id, 'title' => 'Chat',
            'context_type' => 'entity', 'context_id' => 'x',
        ]);

        $this->actingAs($intruder)->deleteJson('/ai/sessions/'.$session->id)->assertForbidden();
        $this->assertDatabaseHas('agent_conversations', ['id' => $session->id]);
    }
```

- [ ] **Step 2: Run-fail.** → FAIL (route/method missing).

- [ ] **Step 3: Add `destroy`** (add `use App\Models\Ai\ProposedChangePart;` and `use Illuminate\Support\Facades\DB;`):

```php
    public function destroy(Request $request, string $conversation): JsonResponse
    {
        $session = Conversation::find($conversation);

        if ($session === null) {
            abort(404);
        }

        if ((string) $session->user_id !== (string) $request->user()->id) {
            abort(403);
        }

        DB::transaction(function () use ($session) {
            // Proposals for this session with NO applied part are unmaterialized
            // → delete them and their parts. Keep any change with an applied part.
            $deletableChangeIds = ProposedChange::where('conversation_id', $session->id)
                ->whereDoesntHave('parts', fn ($q) => $q->where('status', 'applied'))
                ->pluck('id');

            ProposedChangePart::whereIn('change_id', $deletableChangeIds)->delete();
            ProposedChange::whereIn('id', $deletableChangeIds)->delete();

            ConversationMessage::where('conversation_id', $session->id)->delete();
            $session->delete();
        });

        return response()->json(['deleted' => true]);
    }
```

- [ ] **Step 4: Register the route** (same gated group):

```php
            Route::delete('sessions/{conversation}', [AiSessionController::class, 'destroy'])->name('sessions.destroy');
```

- [ ] **Step 5: Run-pass.** `… php artisan test --filter AiSessionEndpointTest` → all pass. Then a no-regressions run: `… php artisan test --filter "Ai"`. Pint.

- [ ] **Step 6: Commit** `git commit -am "feat(ai): DELETE /ai/sessions/{id} with cascade"`.

---

## Self-Review notes

- **Spec coverage (Phase A, spec §4/§5.2/§5.3):** context columns (T1); controller owns session creation + tags context + returns id (T2); `GET /ai/sessions` owner-scoped + label + filter (T3); `GET /ai/sessions/{id}` replay payload joining proposal status by `conversation_id` (T4); `DELETE /ai/sessions/{id}` owner-checked cascade incl. orphaned-pending proposals (T5). Gate `permission:entities.write` on every route.
- **Deliberate scope refinement vs spec:** the spec listed "resume-latest-scoped-session in the sidebar" under Phase A. Rendering a resumed conversation's history is the Phase C replay UI, so ALL frontend session-wiring (threading `conversation_id`, history list, resume, replay) is consolidated into Phase B/C. Phase A ships the fully-tested backend + the correctness fix that today every message starts a NEW server-side conversation (controller now threads one session per sitting). Flag this to the human at execution handoff.
- **SDK conversation-id mechanism (resolved):** controller mints `Str::uuid7()`, creates the tagged `Conversation` row, calls `continue($id,$user)` → SDK skips its own row creation and writes messages under our id; id returned via `X-Conversation-Id` (the id is not in the SSE body). Verified against vendored source.
- **Type/name consistency:** request field `conversation_id`; response header `X-Conversation-Id`; `contextLabel()` reused by T3+T4; proposal status strings `pending|applied|discarded`; `kind` == `context_type`. `Laravel\Ai\Models\Conversation`/`ConversationMessage` used verbatim across tasks.
- **No new migrations beyond T1.** `ConversationMessage::create()` in tests requires the model's timestamps default — set `created_at` explicitly where ordering matters (done in T4 test).
