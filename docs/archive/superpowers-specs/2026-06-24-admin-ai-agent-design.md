# Admin AI Agent — Route-Bound Data-Editing Assistant

**Status:** design / awaiting approval
**Date:** 2026-06-24
**Stack:** Laravel AI SDK (`laravel/ai`), Laravel 13 + Inertia/React admin, OpenRouter

## 1. Goal

A per-route AI assistant in the Laravel admin. A nav button opens a left sidebar
chat that is **bound to the record on the current route** (an entity or a
chronicle) — it already "knows" that record the way this CLI knows attached files.
The operator types natural language ("this is in Luxor, not the Netherlands";
"link this to the Roman Republic as part_of from 509 BCE"; "create the Maya
civilization") and the agent proposes a concrete change. **The primary use is
creating entities** — including auto-creating the far side of a relationship when
the target doesn't exist yet.

Every write the agent can make corresponds to a data-quality problem we fixed by
hand this cycle (see §3), and every tool wraps an **existing Action class**, so the
agent uses the same validated write path as the admin UI.

## 2. Core decisions (locked)

| Decision | Choice | Rationale |
|---|---|---|
| Write-safety model | **Propose → preview → confirm** | We spent a full cycle cleaning bad auto-generated data; no LLM write commits without a human clicking Apply. |
| v1 tools | Create entity, Set location, Create relationship, Update fields, Wikidata verify/set, Merge duplicates | Covers every recurring issue class. |
| Relationship to missing target | Agent **creates the new entity first**, then links | "first use should be to create entities". |
| Multi-part proposals | **Partial apply** — each part (e.g. new entity, then the link) is individually applicable | Operator can accept the entity but reject the link. |
| Provider | **OpenRouter** | Already wired in the pipeline (`OPENROUTER_API_KEY`); cheap, model-flexible. |
| Default model | `anthropic/claude-haiku-4.5` via OpenRouter (configurable) | Strong, cheap tool-use; ~$20/mo soft spend cap. |
| Chat UI | **AI Elements** (`elements.ai-sdk.dev`) | Prebuilt React+Tailwind+shadcn chat components; admin already has all prereqs. |

## 3. Issue classes → tools (why these tools)

| Recurring issue (this cycle) | Hand-fix | Agent tool → Action |
|---|---|---|
| Entity missing entirely / far side of a relation absent | manual create + resolve | **`CreateEntity`** → `CreateEntityAction` + `BackfillEntityAction` |
| Wrong location / continent (Karnak→NL, Maya→Sahara) | set `entity_locations.geom` + backfill | `SetEntityLocation` → `EntityGeoRef` Action + `BackfillEntityAction` |
| Wrong/namesake QID (Karnak=NL street, Egypt=song) | verify P31+coords, re-resolve, cascade QID | `SetEntityWikidata` + read-only `VerifyWikidata` |
| Duplicate / split entity (two Egypts) | merge, re-point rels/chronicle/timeline | `MergeDuplicateEntities` |
| Wrong dates (−753 cascade; century→year) | normalize temporal ranges | `UpdateEntityFields` (dates) |
| Missing relationship | — | `CreateRelationship` → `CreateRelationshipAction` |
| Stale description / malformed name | rename / re-type / edit summary | `UpdateEntityFields` |
| (grounding) inspect before acting | DB queries | read-only `GetEntityContext` |

## 4. Backend architecture (Laravel AI SDK)

### 4.1 Agents

Two thin agent classes, each **constructed with the bound record** (mirrors the
SDK's `SalesCoach(User $user)` pattern):

```php
// app/Ai/Agents/EntityEditorAgent.php
class EntityEditorAgent implements Agent, Conversational, HasTools
{
    use Promptable, RemembersConversations;

    public function __construct(public Entity $entity, public User $user) {}

    public function instructions(): string
    {
        // Embeds the entity's LIVE state — name, type, QID, location, dates,
        // relationships, periods — this is the "attached context".
        return view('ai.instructions.entity-editor', [
            'entity' => $this->entity->loadMissing(['primaryLocation', 'primaryTemporalRange', 'relationships']),
        ])->render();
    }

    public function tools(): iterable
    {
        return [
            new GetEntityContext($this->entity),
            new CreateEntity($this->user),
            new SetEntityLocation($this->entity, $this->user),
            new CreateRelationship($this->entity, $this->user),
            new UpdateEntityFields($this->entity, $this->user),
            new SetEntityWikidata($this->entity, $this->user),
            new VerifyWikidata,                 // read-only
            new MergeDuplicateEntities($this->user),
        ];
    }
}
```

`ChronicleEditorAgent` is the analogous class for `/admin/chronicles/{id}`, with a
chronicle-focused toolset (entry CRUD, entity-linking) — same patterns, deferred
detail.

- **Memory**: `RemembersConversations` persists history. We scope a thread per
  `(user, agent_class, context_id)` so each route's chat is its own conversation.
  Requires publishing + running the AI SDK migrations.
- **Streaming**: the controller returns
  `$agent->stream($prompt)->usingVercelDataProtocol()` → SSE consumed by React
  `useChat`.

### 4.2 The propose → preview → confirm mechanism

The crux. **Write tools never commit.** Instead:

1. A write tool's `handle()` validates input, **builds the change**, and persists a
   row to a new **`agent_proposed_changes`** staging table:
   `{id, user_id, conversation_id, context_type, context_id, tool, payload (json),
   human_diff (json), status: pending|applied|discarded, applied_at, created_by}`.
2. The tool returns the proposal id + a human-readable diff to the model, which
   surfaces it in chat. The frontend renders a **confirm card** ([Apply] /
   [Discard]) from `human_diff`.
3. **Apply is deterministic and out of the model's control**: clicking Apply POSTs
   to `POST /admin/ai/proposals/{id}/apply`, which loads the staged payload and
   executes the **real Action** (`CreateEntityAction`, `EntityGeoRef` Action,
   `CreateRelationshipAction`, …) with `createdBy = "agent:{user_id}"`, then runs
   `BackfillEntityAction` where geometry/temporal changed. The model can *propose*
   but never *commit*.

This table doubles as an **audit + undo log** (status + payload of every applied
change). `discarded`/`pending` proposals are swept by a scheduled prune.

Each tool implements a small contract:

```php
interface ProposesChange {
    public function build(array $args): ProposedChange;   // validate + stage, no commit
    public function apply(ProposedChange $c): Model;       // run the Action (called by the apply endpoint)
}
```

`CreateEntity.apply()` chains: resolve/verify QID (optional) → `CreateEntityAction`
→ `BackfillEntityAction`. `CreateRelationship.build()` detects a missing target and
**nests a `CreateEntity` proposal** so the operator confirms the new entity and the
link together.

**Partial apply.** A proposal may carry **multiple parts** (`parts: [{key, tool,
payload, human_diff, status, depends_on}]`) — e.g. part A = create "Roman Republic",
part B = link `part_of` A. Each part has its own [Apply]/[Discard] and status;
`POST /admin/ai/proposals/{id}/parts/{key}/apply` commits one part. `depends_on`
enforces order (the link won't apply until its new entity is applied, and the
applied entity's real id is substituted into the dependent part's payload). The
operator can accept the entity but discard the link.

### 4.3 Wikidata grounding

A small **`WikidataService`** (HTTP to `Special:EntityData/{qid}.json`) provides the
exact checks I ran by hand all cycle: label/description, `P31` type, `P625`
coordinate. `VerifyWikidata` (read-only) and `SetEntityWikidata`/`CreateEntity` use
it to reject namesakes (Karnak-the-NL-street, Egypt-the-song) before proposing.

### 4.4 Provider config

OpenRouter via `config/ai.php` + existing `OPENROUTER_API_KEY`. Default model
configurable; a cheap tool-capable model for routing, with optional failover array
later.

### 4.5 Auth & safety

- Endpoints behind the admin auth middleware; the apply endpoint additionally
  checks the operator's edit/geometry-write permission (the same gate
  `entity:backfill` respects).
- Tools authorize against the bound record's policy in `build()`.
- Rate limiting on `/admin/ai/chat`; OpenRouter spend cap.
- All applied changes carry `created_by="agent:{user_id}"` provenance, so agent
  edits are filterable/revertable like the `backfill:*` / `pipeline:*` tiers.

## 5. Frontend (Inertia / React admin) — built on AI Elements

The admin already has every AI Elements prerequisite — **React 19, Tailwind 4, and
shadcn/ui** (`resources/js/components/ui/`: button, card, dialog, sheet, …). AI
Elements' docs assume Next.js, but the components are plain React+Tailwind+shadcn,
so we install them via the **shadcn registry CLI** (`npx shadcn@latest add
@ai-elements/<component>`) into `components/ui/ai/`, not the Next-centric AI
Elements CLI. Add `@ai-sdk/react` (the `useChat` hook) to the admin `package.json`.

- **Nav button** "✨ Ask AI" (in `nav-main.tsx`) toggles `<AiSidebar>` — a left
  `Sheet` (already in the kit).
- **Chat** uses AI Elements primitives: `Conversation` + `Message` for the thread,
  `PromptInput` for the composer, `Response` for streamed markdown, and `Tool` to
  render tool-call activity. `useChat` posts to `/admin/ai/chat`; the controller
  streams via `usingVercelDataProtocol()`, which `useChat` consumes natively.
- **Context** comes from Inertia page props: detail pages expose
  `{ai_context: {type:'entity'|'chronicle', id}}`, sent with each chat request so
  the server constructs the right route-bound agent.
- **Confirm cards**: a custom renderer turns a `proposal` tool-result into a card
  with **one [Apply]/[Discard] per part** (§4.2). Apply calls the part endpoint,
  then `router.reload({only:[...]})` so the edit shows immediately on the page.
- Sidebar is self-contained; the only per-page change is adding `ai_context` to the
  detail controllers' Inertia props (the model is already loaded there).

## 6. Data model additions

1. AI SDK conversation/message tables (published migrations) — chat memory.
2. **`agent_proposed_changes`** (§4.2) — staging + audit/undo.

No changes to `entities` / `geometry_periods` / etc. — the agent goes through
existing Actions.

## 7. Out of scope (v1)

- Bulk / multi-entity batch operations from one prompt.
- Autonomous (no-confirm) writes.
- Chronicle agent depth (entry-level editing) — scaffold the class, defer rich tools.
- Map-canvas "click to place" integration (sidebar is text-first).

## 8. Testing

- **Tool unit tests**: each `build()` stages the right proposal; each `apply()`
  invokes the correct Action with `agent:` provenance (feature tests, no live LLM).
- **Apply endpoint**: permission gate, pending→applied transition, backfill runs.
- **Namesake rejection**: `WikidataService` flags wrong P31 / missing coord.
- **Streaming/chat**: contract test that the controller returns a Vercel-protocol
  stream; the LLM call itself is mocked.
- LLM-in-the-loop behavior is **not** unit-tested; correctness is gated by the
  human confirm step.

## 9. Resolved decisions

- **Partial apply**: yes — per-part Apply/Discard (§4.2, §5).
- **Default model**: `anthropic/claude-haiku-4.5` via OpenRouter, overridable in
  `config/ai.php`; ~$20/mo soft spend cap (alert, not hard cutoff).
- **Retention** (scheduled prune in the `scheduler` container):
  - `pending` / `discarded` proposals → pruned after **7 days**.
  - `applied` proposals (the audit/undo log) → kept **1 year**.
  - chat conversation history → kept **90 days**, then pruned per conversation.
