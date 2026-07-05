# AI Sidebar Sessions + Proposal Lifecycle (Phase D)

**Status:** design / awaiting approval
**Date:** 2026-06-25
**Builds on:** [2026-06-24-ai-sessions-and-global-create-design.md](2026-06-24-ai-sessions-and-global-create-design.md) (Phases A/B/C — sessions backbone, the `/ai` Create-with-AI page, replay/resume/delete). All of those shipped to `develop`.

## 1. Problem

Two reported gaps, both rooted in the same cause: the **per-record sidebar** (the "Ask AI" panel on an entity/chronicle page) was never migrated to the session model that the `/ai` page now uses.

1. **The sidebar does not resume a record's session.** It uses raw `useChat` keyed on the record, sends no `conversation_id`, and never captures the `X-Conversation-Id` the server returns — so reopening the same entity starts blank, and even within one sitting each message mints a fresh server-side conversation.
2. **Proposal cards don't disable coherently.** On the `/ai` page an applied part locks in place; in the sidebar, Apply calls `router.reload()` and the whole chat (card included) vanishes. And a proposal from a conversation you've left can still be applied.

## 2. Locked decisions

| Decision | Choice |
|---|---|
| Sidebar resume | On open for a record, the sidebar **resumes that record's most-recent session** (replays its history) and continues it; a "New chat" control starts a fresh scoped session. (Edit mode only — create-page mode stays transient.) |
| Apply UX | **Keep `router.reload()`** on apply (so the record's data refreshes). Because the sidebar now resumes+replays after the reload, the applied card **comes back showing "Applied"/disabled** rather than disappearing. |
| "Session quits" → disable | A pending card becomes inert **when you leave its conversation** (start New chat, switch record, or navigate away). Mechanically this falls out of the session model: only the *active* conversation's messages are shown, so a left conversation's cards aren't rendered; reopening that session **replays** them with their stored status (applied/discarded locked, pending actionable). |
| Global vs scoped indication | The `/ai` page session list **labels each session Global vs scoped** (entity/chronicle), and the sidebar header indicates it is a **scoped** chat for the open record. Sidebar-created (scoped) sessions appear in the `/ai` list (they already do — this makes the distinction explicit). |

## 3. Architecture

Reuse the Phase B/C building blocks — no new backend:
- `useSessionChat` (kind/context + `conversation_id` threading + `X-Conversation-Id` capture + `initialMessages` + `resetNonce`).
- `reconstructSessionMessages` (replay payload → `UIMessage[]`, applied/discarded statuses merged).
- `AiChatPanel` (reusable message list + input) and `ProposalCard` (seeds locked status from `part.status`).
- Endpoints (Phase A): `GET /ai/sessions?context_type=&context_id=` (per-record lookup, ordered newest-first), `GET /ai/sessions/{id}` (replay), `DELETE /ai/sessions/{id}`.

### 3.1 Sidebar migration (`ai-sidebar.tsx`)

The sidebar becomes a single-session view bound to the current record:
- **Edit mode** (record page, `ai_context = {type, id}`): on open / when the bound record changes, fetch `GET /ai/sessions?context_type={type}&context_id={id}`; if a session exists, take the most recent, fetch its replay payload, `reconstructSessionMessages`, and pass as `initialMessages` to `useSessionChat({ sessionId, kind: type, contextType: type, contextId: id, initialMessages })`; if none, start fresh (a session is minted on first send and captured via `X-Conversation-Id`).
- Render the chat via the existing `AiChatPanel` (replacing the sidebar's hand-rolled message loop) so replay + proposal-card status come for free, while keeping the sidebar's aside/header/close chrome.
- A **"New chat"** control bumps `resetNonce`, clears `initialMessages`, and clears `activeSessionId` → a fresh scoped session.
- **Create mode** (create pages, `id: null, mode: 'create'`): unchanged — no resume (transient); uses the creator agents as today.

### 3.2 Proposal card lifecycle

No new card states are needed — the Phase C `ProposalCard` already locks parts whose `status` is `applied`/`discarded`. The coherent lifecycle emerges from the sidebar using sessions:
- Apply → `router.reload()` → sidebar re-mounts → resumes the record's session → replay renders the proposal card with the now-`applied` part **locked and visible**.
- Leaving the conversation (New chat / switch record / navigate) shows a different (or empty) active chat, so the prior card isn't rendered; reopening replays it with stored status.

### 3.3 Global vs scoped indication

- `/ai` page session list: add a compact kind badge (`Global` / `Entity` / `Chronicle`) alongside the existing `context_label`, derived from `session.kind`.
- Sidebar header: a small "Scoped: {Entity|Chronicle} #id" indicator (the header already shows the type+id; formalize it as a scoped badge) so it's clear the sidebar chat is record-bound vs the global `/ai` workspace.

## 4. Out of scope

- Server-side enforcement that a proposal can only be applied from its live session (the lifecycle is handled at the display layer via replay; a stale proposal is simply not shown). A backend guard could be a later hardening.
- Time-based proposal expiry.
- Changing the create-page (create-mode) sidebar behavior.
- Any backend changes — Phase A endpoints are consumed as-is.

## 5. Testing

- `useSessionChat`/sidebar: on open with an existing record session, fetches the list + replay and seeds `initialMessages`; with no session, starts empty; "New chat" resets.
- The sidebar resumes only in edit mode (create mode unchanged).
- After an apply+reload, the resumed sidebar shows the applied part locked (replay path — covered by `reconstructSessionMessages` + `ProposalCard` status seed; add a sidebar-level test that the panel renders a replayed applied card as locked).
- `/ai` list shows a Global/Entity/Chronicle badge per session; sidebar header shows the scoped indicator.

## 6. Open questions

1. **"New chat" placement in the sidebar** — a header button (next to close), or a small link above the input? (Assumed: a header icon button.)
2. **Multiple prior sessions for one record** — resume only the single most-recent one (assumed), with older ones reachable from the `/ai` page; or add a per-record session switcher in the sidebar later (out of scope now).
