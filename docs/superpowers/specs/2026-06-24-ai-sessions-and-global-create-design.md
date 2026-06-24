# AI Sessions: Chat History + Global "Create with AI" Workspace

**Status:** design / awaiting review
**Date:** 2026-06-24
**Builds on:**
- [2026-06-24-admin-ai-agent-design.md](2026-06-24-admin-ai-agent-design.md) (the propose→confirm→partial-apply pipeline, `AgentTool` base, gated `/ai/chat` + `/ai/proposals` endpoints, `agent_conversations`/`agent_conversation_messages` persistence)
- [2026-06-24-ai-create-mode-design.md](2026-06-24-ai-create-mode-design.md) (create-mode `ai_context`, creator agents, redirect-after-apply)

## 1. Problem

Two gaps remain after the create-mode work shipped:

1. **No chat history / resume.** Every conversation is already persisted by the
   `laravel/ai` SDK into `agent_conversations` + `agent_conversation_messages`,
   but `AiChatController` never returns the `conversation_id` and the frontend
   never sends one back — so each page load starts a *fresh* conversation and
   there is no UI to reopen a past one. The data is on disk and unreachable.
2. **AI is only reachable from a record's page.** You can create/edit via the
   sidebar on an entity/chronicle page, or create a single record on a create
   page. There is no dedicated, non-page-bound place to "just talk to the AI"
   and build several records across types in one sitting.

Goal: introduce a first-class **session** concept (a session = one
`agent_conversations` row), make every session **listable and resumable**, and
add a dedicated **"Create with AI"** workspace page driven by a **global**
session that can create and edit anything.

## 2. Locked decisions

| Decision | Choice |
|---|---|
| Two session kinds | **Global** (not bound to a record) and **Scoped** (bound to an entity or chronicle) |
| Global session toolset | **Full toolset** — create + edit entities, relationships, chronicles, chronicle entries, plus read/lookup (`get_entity_context`, `verify_wikidata`). The "do anything by id" workspace. |
| After a create inside a global session | **Stay in the session.** The created record appears as a clickable link; the conversation continues. No redirect. |
| History scope | **All sessions, both kinds**, appear in the history list, each labeled by context. Scoped sessions reopen into their record's editor agent. The per-record sidebar resumes its latest session instead of always starting fresh. |
| A session's identity | The `agent_conversations.id` (UUID). "Session" and "conversation" are the same row. |

## 3. Architecture overview

```
                       ┌──────────────────────────────────────┐
   "Create with AI"    │  Session list (all kinds, by user)    │
   page (new route) ──▶│  ─ Global · New session               │
                       │  ─ Entity: Rome        ↺ resume       │
                       │  ─ Chronicle: Punic Wars  ↺ resume    │
                       └───────────────┬──────────────────────┘
                                       │ open / new
                                       ▼
   GET /ai/sessions            ┌───────────────┐   POST /ai/chat {session_id, kind, …}
   GET /ai/sessions/{id} ──────│  Chat panel   │──────────────────────────────────────▶ AiChatController
   DELETE /ai/sessions/{id}    └───────────────┘                                            │
                                                                          kind=global ▶ GlobalAgent (full tools)
   Record page sidebar ── resume latest scoped session ──▶ /ai/chat       kind=entity ▶ EntityEditorAgent
                                                                          kind=chronicle ▶ ChronicleEditorAgent
                                                                                            │
                                  proposals carry conversation_id ──▶ /ai/proposals/.../apply
                                                                       (global: no redirect; returns created_ref)
```

Everything reuses the existing pipeline: agents stage `ProposedChange`/
`ProposedChangePart` rows via the `AgentTool` base; only the gated apply
endpoint runs Actions; provenance stays `createdBy='agent:'.$userId`.

## 4. Data model

`agent_conversations` (vendor table: `id`, `user_id`, `title`, timestamps)
gains two nullable columns via **our own** migration (we populate them; the SDK
ignores them):

- `context_type` — `'global' | 'entity' | 'chronicle'` (string, nullable).
- `context_id` — the bound record id for scoped sessions, `null` for global
  (string, nullable).

A session's `title` is auto-derived from the first user message (truncated);
renaming is out of scope (§9).

**Proposals already carry `conversation_id`** in the `AgentTool` context array,
so a session's proposals (and their applied/pending status) can be joined back
by `conversation_id` for replay — no schema change needed on the proposal
tables.

> **Design-time check (resolve in the plan):** the SDK generates the
> conversation id internally during `stream()`. We must surface it. Verify
> whether `RemembersConversations::continue($id, $user)` will *start* a new
> conversation with a caller-supplied id (preferred: the controller mints the
> UUID, tags context columns, then both persists and returns it), or whether we
> must let the SDK create it via `forUser()` and read the id back afterward. The
> chosen mechanism is an implementation detail; the contract below (controller
> owns session creation + returns `session_id`) holds either way.

## 5. Backend

### 5.1 `GlobalAgent`

`App\Ai\Agents\GlobalAgent` — implements `Agent, Conversational, HasTools` with
`Promptable, RemembersConversations`; constructed `(User $user, array $context)`
with no bound record. `tools()` returns the **full** registered toolset, each
`->withContext($this->context)`:

- create: `create_entity`, `create_chronicle`, `create_chronicle_entry`
- edit: `update_entity_fields`, `set_entity_location`, `set_entity_wikidata`,
  `create_relationship`, `update_chronicle_entry`, `merge_duplicate_entities`
- lookup (no context needed): `get_entity_context`, `verify_wikidata`

`instructions()` renders a new `ai/instructions/global.blade.php`: a global
workspace; you PROPOSE, the operator applies; you can create and edit any record
by id; use lookups before mutating; created records stay in the conversation as
links (you are not redirected away).

> The existing per-create-page `EntityCreatorAgent`/`ChronicleCreatorAgent`
> remain for the contextual quick-create on the create pages. `GlobalAgent` is a
> superset surface, not a replacement; keep both. (Possible later
> consolidation noted in §9.)

### 5.2 `AiChatController`

- Validation gains session fields: `kind` (`nullable|in:global,entity,chronicle`;
  default derives from today's `mode`/`context_type` for back-compat) and
  `session_id` (`nullable|string`, the conversation to continue).
- Branch by kind: `global → GlobalAgent`; `entity → EntityEditorAgent`;
  `chronicle → ChronicleEditorAgent` (the create-mode creator-agent branch from
  the prior feature is unchanged).
- **Session lifecycle:** the controller owns it. On a request with no
  `session_id`, create/mint a session, set `context_type`+`context_id`+`title`,
  and use it for conversation persistence. On a request with `session_id`,
  authorize ownership (`agent_conversations.user_id === auth()->id()`) then
  continue it. Either way, **return the `session_id`** to the client (response
  header or initial stream event) so the frontend can persist and resume.
- Gate unchanged: `permission:entities.write`.
- Global proposals stage under `context_type='global'` / `context_id = session_id`
  (replaces the `'create'` sentinel for this surface); apply still authorizes on
  `ProposedChange.user_id`.

### 5.3 Session endpoints (new `AiSessionController`, gated `permission:entities.write`)

- `GET /ai/sessions` — the current user's sessions ordered by `updated_at` desc:
  `{ id, kind, context_id, context_label, title, updated_at }`. `context_label`
  is resolved server-side (e.g. `"Entity: Rome"`, `"Chronicle: The Punic Wars"`,
  or `"Global"`). Supports an optional `?context_type=&context_id=` filter so the
  scoped sidebar can fetch only that record's sessions.
- `GET /ai/sessions/{conversation}` — ownership-checked; returns the ordered
  messages for replay: `role`, text content, and for assistant tool turns the
  staged proposal(s) joined by `conversation_id` with their current
  `applied|pending|discarded` status (so replay shows what was done, not raw
  tool JSON).
- `DELETE /ai/sessions/{conversation}` — ownership-checked; deletes the
  conversation + its messages (and orphaned pending proposals for that session).

### 5.4 Apply endpoint (`AiProposalController`)

In **global** sessions, apply does **not** redirect. Alongside the existing
`status`/`result_id`, return a `created_ref` for record-creating tools:
`{ type, id, url, label }` (e.g. entity → `entities.edit` by id; chronicle →
`chronicles.edit` by slug) so the chat can render the created record as an
inline link. Scoped-edit and create-page modes keep today's behavior
(`router.reload()` / `redirect_url`).

## 6. Frontend

### 6.1 "Create with AI" page (new admin route + nav entry)

A two-pane Inertia page:
- **Left — session history:** the `GET /ai/sessions` list, all kinds, labeled by
  context; a **New session** button starts a blank **global** session (the row is
  created lazily on first send). Clicking a session opens it.
- **Right — chat panel:** the existing AI chat UI rendered full-height (reuse the
  sidebar's chat internals). For a global session the input is always enabled;
  applied creates render as inline record links and the conversation continues.

### 6.2 Resume

Opening any session calls `GET /ai/sessions/{id}`, hydrates the message list
(text + proposal cards reconstructed with their stored status), and sets the
chat transport's `session_id` so the next message continues that conversation.

### 6.3 Record-scoped sidebar (existing)

On open, the sidebar fetches that record's sessions
(`GET /ai/sessions?context_type=…&context_id=…`) and **resumes the most recent
one** (sending its `session_id`); a **New chat** control starts a fresh scoped
session. Reopening a scoped session from the history page restores the same
record-scoped editor agent.

### 6.4 `ai_context` / transport

`ai_context` is unchanged for record pages. The chat transport body gains
`kind` and `session_id` (nullable). The history page supplies `kind:'global'`,
no record context.

## 7. Phasing (each phase is its own implementation plan)

This spec spans three independently shippable phases; decompose into three
plans:

- **Phase A — Sessions backbone.** Migration (context columns), controller
  session lifecycle + return `session_id`, `GET/DELETE /ai/sessions` and
  `GET /ai/sessions/{id}` (list + replay payload), ownership authorization.
  Deliverable: conversations are tagged, listable, and fetchable; the existing
  sidebar can resume the latest scoped session. *(Resolves the SDK
  conversation-id design-time check.)*
- **Phase B — Global "Create with AI" page.** `GlobalAgent` (full toolset) +
  blade instructions, chat-controller `kind=global` branch, apply `created_ref`
  for global mode, the new two-pane page + nav entry, stay-in-session +
  created-record links.
- **Phase C — Full history & replay UX.** History list across both kinds,
  resume-into-scoped-agent from the list, message + proposal-card replay
  rendering (joining proposal status), session delete.

## 8. Testing (per phase)

- **A:** migration adds nullable columns; a new conversation is tagged with the
  right `context_type`/`context_id`/`title`; `/ai/chat` returns a `session_id`;
  continuing a `session_id` you don't own → 403; `GET /ai/sessions` lists only
  your sessions ordered by `updated_at`; replay payload returns messages +
  proposal statuses; gate still applies.
- **B:** `GlobalAgent::tools()` exposes the full toolset with context injected;
  `kind=global` streams 200 with no record; global apply returns `created_ref`
  and **no** `redirect_url`; the page renders the list + chat and the input is
  enabled with no record context.
- **C:** history lists both kinds with correct `context_label`; opening a scoped
  session rebinds the editor agent; replay renders an applied proposal as
  applied and a pending one as actionable; delete removes the conversation +
  messages + orphaned pending proposals (and is ownership-checked).

## 9. Out of scope

- Renaming sessions (titles are auto-derived); pinning/archiving/search over
  history.
- Sharing a session between users; any cross-user visibility (sessions are
  strictly per-owner).
- Streaming-cost/token budgeting or per-session model selection.
- Consolidating the per-create-page creator agents into `GlobalAgent` (kept
  separate for now; revisit once the global workspace is in use).
- Deleting/reordering chronicle entries via AI (already out of scope upstream).

## 10. Open questions for review

1. **Route/nav placement** of the "Create with AI" page — top-level admin nav
   item ("AI"), or nested under an existing section? (Assumed: top-level nav
   entry, route `ai.index`.)
2. **Replay fidelity in Phase C** — is showing past proposals as read-only
   status enough, or must a *pending* historical proposal remain
   apply/discard-able on reopen? (Assumed: pending proposals stay actionable on
   reopen; applied/discarded render read-only.)
3. **Scoped resume default** — auto-resume the most recent scoped session
   silently, or show a small "resume / new" choice when prior sessions exist?
   (Assumed: auto-resume most recent, with a New chat control.)
