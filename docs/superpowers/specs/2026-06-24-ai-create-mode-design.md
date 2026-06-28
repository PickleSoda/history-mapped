# AI Agent on the Create Pages (+ Chronicle Entry Editing)

**Status:** design / awaiting approval
**Date:** 2026-06-24
**Builds on:** [2026-06-24-admin-ai-agent-design.md](2026-06-24-admin-ai-agent-design.md)

## 1. Problem

The admin AI sidebar is **inaccessible on the create pages** (`entities/create`,
`chronicles/create`). Three gaps in the create path:

1. The create pages don't expose `ai_context`, so `useAiContext()` returns null →
   the sidebar input is disabled.
2. The chat controller does `findOrFail($context_id)` — there is no record id on a
   create page, so it 404s.
3. The agents are constructed *from* an existing record
   (`EntityEditorAgent(Entity $entity, …)`) — nothing to bind to.

Goal: let users **create entities and chronicles via the AI** on the create pages,
reusing the existing chat/proposal/apply pipeline. Plus (Phase 2) let the AI
**create/edit chronicle entries** on the chronicle edit page.

## 2. Locked decisions

| Decision | Choice |
|---|---|
| Create scope | Create the record, then **hand off** to its edit page (enrichment continues there) |
| Post-apply | **Redirect** to the new record's edit page |
| Chronicle depth | Phase 2: add chronicle-entry create/edit (new Actions + tools) |
| Delivery | Phase 1 (create-page accessibility) **and** Phase 2 (entry editing) together |

## 3. Phase 1 — AI accessible on the create pages

### 3.1 "create mode" context (frontend)

Extend `ai_context` to `{ type: 'entity'|'chronicle', id: string|null, mode: 'edit'|'create' }`.
`mode` is optional and defaults to `'edit'` (existing detail/edit pages are
unaffected — they keep emitting `{type,id}`; the create pages emit
`{ type, id: null, mode: 'create' }`).

- `useAiContext` returns the validated context. In `edit` mode `id` must be a
  string; in `create` mode `id` is null. Malformed → null.
- `<AiSidebar>` enables its input whenever a context is present (either mode); the
  `useChat` transport body sends `context_type`, `context_id` (null in create), and
  `mode`.

### 3.2 Chat controller branch (backend)

`AiChatController::chat` validation gains `mode` (`in:edit,create`, default `edit`)
and relaxes `context_id` to required only in edit mode. Branch:

- **edit** → today's `EntityEditorAgent` / `ChronicleEditorAgent` (unchanged).
- **create** → new `EntityCreatorAgent` / `ChronicleCreatorAgent` — constructed with
  the `User` + context only, NO `findOrFail`.

The proposal-staging context: `ProposedChange.context_id` is NOT NULL, so create-mode
proposals stage under a sentinel `context_id = 'create'` (the apply endpoint
authorizes on `ProposedChange.user_id`, not `context_id`, so scoping/ownership still
holds).

### 3.3 Creator agents (creation-only tools)

Thin agents mirroring the editor agents but with no bound record and a
creation-focused toolset + instructions ("help the user create a new X; propose,
the operator applies"):

- **`EntityCreatorAgent`** — tools: `CreateEntity` (already accepts
  name/type/QID/coords/dates in one proposal) + read-only `VerifyWikidata`.
- **`ChronicleCreatorAgent`** — tools: new `CreateChronicle`. Its `instructions()`
  MUST tell the model: entries are **not** created here — if the user asks to add
  entries while creating the chronicle, create the chronicle shell first and tell the
  user that entries are added afterward on the chronicle's edit page (where the AI can
  create/edit them). Never silently drop an entry request.

Both call `->withContext($context)` on staging tools (context_type, sentinel
context_id, user_id, conversation_id) exactly as the editor agents do.

### 3.4 `CreateChronicle` tool (new)

Wraps the **existing `CreateChronicleAction(ChronicleData, ?createdBy)`** (same
pattern as `CreateEntity`).

- name `create_chronicle`; schema: `title` (required), `summary`, `status`,
  `start_year`, `end_year`, `source_reference` (optional).
- `buildParts` → one `chronicle` part with a human diff.
- `applyPart` builds `ChronicleData` and calls the Action with
  `createdBy = 'agent:'.$resolved['user_id']`; returns `result_id = chronicle_id`.

### 3.5 Redirect after Apply (create mode)

The apply endpoint already returns the new `result_id`. When `mode === 'create'` and
the applied part's tool is the record-creator (`create_entity` / `create_chronicle`),
the sidebar redirects (`router.visit`) to the new record's **edit** page
(`entities.edit` / `chronicles.edit` route with `result_id`) — where the full editor
agent takes over. (In edit mode, Apply keeps today's `router.reload()`.)

### 3.6 Create-page props

`Admin\EntityController::create` and `Web\ChronicleController::create` add
`'ai_context' => ['type' => '…', 'id' => null, 'mode' => 'create']` to their
`Inertia::render` props.

## 4. Phase 2 — chronicle entry create/edit

Entries belong to an existing chronicle, so these tools live on the **edit-mode**
`ChronicleEditorAgent` (not the create page). There are **no `ChronicleEntry` write
Actions today**, so this phase adds them.

`ChronicleEntry` shape (existing model): `chronicle_id`, `narrative_text`, `notes`,
`source_evidence`, `primary_relationship_id` (→ `EntityRelationship`), and
`secondaryEntities` (BelongsToMany via `chronicle_entry_entities`).

### 4.1 New Actions

- **`CreateChronicleEntryAction(string $chronicleId, ChronicleEntryData $data): ChronicleEntry`**
  — creates the entry (narrative_text, notes), syncs `secondaryEntities` from a list
  of entity ids, optionally sets `primary_relationship_id`, `generated_by='agent'`.
- **`UpdateChronicleEntryAction(ChronicleEntry $entry, ChronicleEntryData $data): ChronicleEntry`**
  — updates narrative/notes and re-syncs entity links.
- A small `ChronicleEntryData` DTO (narrative_text, notes?, entity_ids?,
  primary_relationship_id?).

### 4.2 New tools (on `ChronicleEditorAgent`)

- **`CreateChronicleEntry`** — args: `chronicle_id`, `narrative_text`,
  `entity_ids[]` (optional), `notes` (optional). `applyPart` → `CreateChronicleEntryAction`.
- **`UpdateChronicleEntry`** — args: `entry_id`, optional `narrative_text`/`notes`/`entity_ids`.
  `applyPart` → `UpdateChronicleEntryAction` (preserve unspecified fields, like
  `UpdateEntityFields`).

The `ChronicleEditorAgent`'s `instructions()` already lists the chronicle's entries
+ referenced entities; it gains these two staging tools (with `->withContext`).

## 5. Out of scope

- Deleting/reordering chronicle entries.
- Batch/multi-record creation in one apply.
- A global (non-page-bound) "create anything" entry point.
- Enriching the just-created record in the same create-mode conversation (deferred by
  the "create then hand off" decision — happens on the edit page).

## 6. Testing

**Phase 1:**
- `useAiContext` returns create-mode context; null on malformed.
- `AiChatController`: `mode=create` for entity and chronicle → 200 stream, no
  `findOrFail`; `entities.write` gate still applies; edit mode unchanged.
- `CreateChronicle` tool: `buildParts` one part; `applyPart` creates a chronicle with
  `created_by='agent:{user}'` (real `CreateChronicleAction`).
- Creator agents expose only creation tools, each staging tool has context injected.
- Create controllers expose `ai_context` with `mode='create'`, `id=null`.
- Redirect-after-apply in create mode (frontend test on the sidebar/proposal-card).

**Phase 2:**
- `CreateChronicleEntryAction` / `UpdateChronicleEntryAction`: real DB behavior —
  entry created/updated, `secondaryEntities` synced, fields preserved on partial update.
- `CreateChronicleEntry` / `UpdateChronicleEntry` tools: build + apply via the Actions.
- `ChronicleEditorAgent` exposes the entry tools with context.

## 7. Resolved decisions

- **Inline entries in `create_chronicle`: deferred.** The tool does NOT accept
  entries — entries are created/edited only via the Phase-2 tools on the edit page.
  **But the agent must communicate this**, not silently drop the request: if the user
  asks to add entries while creating a chronicle, the `ChronicleCreatorAgent` creates
  the shell and tells the user entries are added next on the chronicle's edit page
  (where the AI can do it). Encoded in the agent's instructions (§3.3) and covered by
  a test asserting the instruction text conveys the hand-off.
