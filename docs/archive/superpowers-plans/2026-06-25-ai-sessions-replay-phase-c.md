# AI Sessions — Phase C (Replay + Resume + Delete) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On the "Create with AI" page, opening a past session replays its stored messages + proposal cards (with applied/pending/discarded status), rebinds the chat to that session's kind/context (entity/chronicle/global), and a delete control removes a session.

**Architecture:** All backend endpoints already exist (Phase A: `GET /ai/sessions/{id}` returns `{session, messages, proposals}`; `DELETE /ai/sessions/{id}`). This is frontend-only. A pure `reconstructSessionMessages(payload)` builds `UIMessage[]` (text parts + `dynamic-tool` output-available parts whose `output` is the proposal, with per-part `status` merged from `proposals[]`). `useSessionChat` gains an `initialMessages` option so the `Chat` is seeded with history on (re)creation. `ProposalCard` seeds its `partStatus` from `part.status` (applied/discarded → locked; pending/absent → actionable). The page lifts `kind`/`contextType`/`contextId` into state and `handleSelectSession` async-fetches history, reconstructs it, and recreates the scoped Chat.

**Tech Stack:** React 19, `@ai-sdk/react` v3 / `ai` v6, Inertia, TanStack Query, vitest. Admin JS in `api/resources/js`, run in the Docker `app` container.

## Global Constraints

- Frontend cmds in Docker: `docker compose -f docker/docker-compose.yml exec app <cmd>`. Tests: `... npx vitest run <file>`. Gates: `... npm run types:check` / `lint:check` / `build` — all clean (a pre-existing `dashboard.tsx` lint WARNING is OK; there must be 0 errors).
- **Literal URLs, no Wayfinder.** Use literal `/ai/sessions`, `/ai/sessions/${id}`, `/ai/chat` — matching the existing page/hook. Do NOT import from `@/routes/ai` or regenerate Wayfinder.
- **Backend is unchanged.** This phase adds NO backend code. The `GET /ai/sessions/{id}` payload is `{ session:{id,kind,context_id,context_label,title}, messages:[{id,role,content,tool_calls,tool_results,created_at}], proposals:[{proposal_id, parts:[{key,tool,human_diff,status,result_id}]}] }`. `messages[].tool_results` is an array of `{id, result}` where `result` is the proposal JSON string `{proposal_id, parts:[{key,tool,human_diff}]}` (NO status — status lives only in `proposals[]`). `DELETE /ai/sessions/{id}` returns `{deleted:true}`, owner-checked.
- **Proposal status values:** `pending | applied | discarded`. In `ProposalCard`'s internal `PartStatus` (`'applied'|'discarded'|'error'|'loading'`), `pending` = key ABSENT from the map (actionable). So only `applied`/`discarded` are seeded.
- **Replay is display-only; backend history comes from `continue()`.** The chat controller derives the prompt from the LAST user message in the request `messages[]` and loads real history via `RemembersConversations::continue($sessionId)`. So seeding the frontend `Chat` with historical messages does NOT double history server-side — historical messages in the request body are ignored except for locating the last user message. Do not change the controller.
- **Pending historical proposals stay actionable** (Apply/Discard still POST to the real `/ai/proposals/{id}/parts/{key}/apply|discard`); applied/discarded render read-only. (Spec §10 Q2.)
- TDD throughout. Vitest convention: per-file `// @vitest-environment jsdom`, explicit `import { describe, it, vi, expect } from 'vitest'`.

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `api/resources/js/lib/reconstruct-session-messages.ts` | Create | Pure: `show()` payload → `UIMessage[]` (text + proposal parts w/ merged status) |
| `api/resources/js/components/ai/proposal-card.tsx` | Modify | `ProposalPart.status?`; seed `partStatus` state from it (locked for applied/discarded) |
| `api/resources/js/hooks/use-session-chat.ts` | Modify | `initialMessages?` option → `new Chat({ messages })` |
| `api/resources/js/pages/ai/index.tsx` | Modify | Lift kind/context to state; async select → fetch+reconstruct+seed+rebind; delete control |

---

## Task 1: `ProposalPart.status` + seed `ProposalCard` part status

**Files:**
- Modify: `api/resources/js/components/ai/proposal-card.tsx`
- Test: `api/resources/js/components/__tests__/proposal-card.test.tsx` (extend — this is the REAL test file location)

**Interfaces:**
- Produces: `ProposalPart` gains optional `status?: 'pending'|'applied'|'discarded'` and `result_id?: string | null`. `ProposalCard` initializes its `partStatus` state so a part with `status==='applied'|'discarded'` renders locked (no Apply/Discard buttons); `pending`/absent stays actionable. Live proposals (no `status` on parts) are unchanged.

- [ ] **Step 1: Write the failing test** (append to the existing describe block)

```tsx
    it('renders applied historical part as locked (no Apply/Discard buttons)', () => {
        const historical = {
            proposal_id: 'prop-h',
            parts: [
                { key: 'k1', human_diff: { summary: 'Did a thing' }, status: 'applied' as const },
            ],
        };
        render(<ProposalCard proposal={historical} mode="edit" />);

        expect(screen.getByText('Did a thing')).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /apply/i })).not.toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /discard/i })).not.toBeInTheDocument();
    });

    it('renders pending historical part as actionable (Apply present)', () => {
        const historical = {
            proposal_id: 'prop-p',
            parts: [
                { key: 'k1', human_diff: { summary: 'Awaiting' }, status: 'pending' as const },
            ],
        };
        render(<ProposalCard proposal={historical} mode="edit" />);

        expect(screen.getByRole('button', { name: /apply/i })).toBeInTheDocument();
    });
```

- [ ] **Step 2: Run-fail.** `docker compose -f docker/docker-compose.yml exec app npx vitest run resources/js/components/__tests__/proposal-card.test.tsx` → the "applied … locked" test fails (buttons still render because status isn't seeded).

- [ ] **Step 3: Implement.** In `proposal-card.tsx`:

Extend the `ProposalPart` type (add the two optional fields):

```ts
export type ProposalPart = {
    key: string;
    human_diff: { summary: string };
    status?: 'pending' | 'applied' | 'discarded';
    result_id?: string | null;
};
```

Change the `partStatus` state initializer to seed from the parts' stored status (read the current line `const [partStatus, setPartStatus] = useState<Record<string, PartStatus>>({});` and replace it with):

```ts
    const [partStatus, setPartStatus] = useState<Record<string, PartStatus>>(() => {
        // Seed from any stored status on historical (replayed) parts so applied /
        // discarded parts render locked. Live proposals carry no status → actionable.
        const seed: Record<string, PartStatus> = {};
        for (const part of proposal.parts) {
            if (part.status === 'applied' || part.status === 'discarded') {
                seed[part.key] = part.status;
            }
        }
        return seed;
    });
```

(No other change — the existing button-rendering already hides Apply/Discard when `partStatus[key]` is set, and `act()` already early-returns for `applied`/`discarded`.)

- [ ] **Step 4: Run-pass** (both new tests + the existing 12). Then `docker compose -f docker/docker-compose.yml exec app npm run types:check`.

- [ ] **Step 5: Commit** `git commit -am "feat(ai): ProposalCard seeds part status from stored status (replay)"`.

---

## Task 2: `reconstructSessionMessages` pure helper

**Files:**
- Create: `api/resources/js/lib/reconstruct-session-messages.ts`
- Test: `api/resources/js/lib/__tests__/reconstruct-session-messages.test.ts`

**Interfaces:**
- Consumes: `parseProposal` + `Proposal`/`ProposalPart` from `@/components/ai/proposal-card`.
- Produces: `reconstructSessionMessages(payload: SessionShowPayload): UIMessage[]`. `SessionShowPayload` = `{ messages: SessionMessage[]; proposals: SessionProposal[] }`. A user message → one `text` part. An assistant message → an optional `text` part (when `content` non-empty) followed by one `dynamic-tool` part (`state:'output-available'`, `output: <proposal>`) per parseable `tool_results[].result`, with each proposal's parts' `status`/`result_id` merged from the matching `proposals[]` entry (by `proposal_id`, then by part `key`).

- [ ] **Step 1: Write the failing test**

```ts
// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { reconstructSessionMessages } from '../reconstruct-session-messages';

describe('reconstructSessionMessages', () => {
    it('builds text + proposal parts and merges per-part status', () => {
        const proposalJson = JSON.stringify({
            proposal_id: 'prop-1',
            parts: [{ key: 'entity', tool: 'create_entity', human_diff: { summary: 'Create Rome' } }],
        });

        const messages = reconstructSessionMessages({
            messages: [
                { id: 'm1', role: 'user', content: 'make rome', tool_results: [], created_at: null },
                {
                    id: 'm2', role: 'assistant', content: 'Proposing.',
                    tool_results: [{ id: 'call-1', result: proposalJson }],
                    created_at: null,
                },
            ],
            proposals: [
                { proposal_id: 'prop-1', parts: [{ key: 'entity', tool: 'create_entity', human_diff: { summary: 'Create Rome' }, status: 'applied', result_id: 'e-9' }] },
            ],
        });

        // user message
        expect(messages[0]).toMatchObject({ id: 'm1', role: 'user' });
        expect(messages[0].parts[0]).toMatchObject({ type: 'text', text: 'make rome' });

        // assistant message: text + proposal part
        expect(messages[1]).toMatchObject({ id: 'm2', role: 'assistant' });
        const parts = messages[1].parts;
        expect(parts[0]).toMatchObject({ type: 'text', text: 'Proposing.' });
        const toolPart = parts[1] as { type: string; state: string; output: { proposal_id: string; parts: Array<{ key: string; status?: string }> } };
        expect(toolPart.type).toBe('dynamic-tool');
        expect(toolPart.state).toBe('output-available');
        expect(toolPart.output.proposal_id).toBe('prop-1');
        // status merged from proposals[]
        expect(toolPart.output.parts[0].status).toBe('applied');
    });

    it('omits the text part when assistant content is empty and handles no tool_results', () => {
        const messages = reconstructSessionMessages({
            messages: [{ id: 'm1', role: 'assistant', content: '', tool_results: [], created_at: null }],
            proposals: [],
        });
        expect(messages[0].parts).toHaveLength(0);
    });
});
```

- [ ] **Step 2: Run-fail.** `docker compose -f docker/docker-compose.yml exec app npx vitest run resources/js/lib/__tests__/reconstruct-session-messages.test.ts` → module missing.

- [ ] **Step 3: Implement** `api/resources/js/lib/reconstruct-session-messages.ts`:

```ts
import type { UIMessage } from 'ai';
import { parseProposal } from '@/components/ai/proposal-card';

export type SessionMessage = {
    id: string;
    role: string;
    content: string | null;
    tool_results?: Array<{ id: string; result: unknown }> | unknown;
    created_at: string | null;
};

export type SessionProposal = {
    proposal_id: string;
    parts: Array<{ key: string; tool: string; human_diff: { summary: string }; status?: string; result_id?: string | null }>;
};

export type SessionShowPayload = {
    messages: SessionMessage[];
    proposals: SessionProposal[];
};

/**
 * Reconstruct a session's stored messages into the UIMessage[] shape the chat
 * panel renders. Assistant tool results are parsed back into Proposal objects
 * (via parseProposal) and surfaced as `dynamic-tool` output-available parts, with
 * each proposal's per-part status merged from the `proposals[]` audit list so the
 * replayed ProposalCards render applied/discarded locked and pending actionable.
 */
export function reconstructSessionMessages(payload: SessionShowPayload): UIMessage[] {
    // proposal_id -> (part key -> {status, result_id})
    const statusByProposal = new Map<string, Map<string, { status?: string; result_id?: string | null }>>();
    for (const p of payload.proposals ?? []) {
        const byKey = new Map<string, { status?: string; result_id?: string | null }>();
        for (const part of p.parts) {
            byKey.set(part.key, { status: part.status, result_id: part.result_id });
        }
        statusByProposal.set(p.proposal_id, byKey);
    }

    return (payload.messages ?? []).map((msg, i): UIMessage => {
        const parts: UIMessage['parts'] = [];

        if (msg.content) {
            parts.push({ type: 'text', text: msg.content } as UIMessage['parts'][number]);
        }

        const toolResults = Array.isArray(msg.tool_results) ? msg.tool_results : [];
        toolResults.forEach((tr, j) => {
            const proposal = parseProposal((tr as { result?: unknown }).result);
            if (!proposal) {
                return;
            }

            const byKey = statusByProposal.get(proposal.proposal_id);
            if (byKey) {
                proposal.parts = proposal.parts.map((pt) => {
                    const stored = byKey.get(pt.key);
                    return stored ? { ...pt, status: stored.status as ProposalStatus, result_id: stored.result_id } : pt;
                });
            }

            parts.push({
                type: 'dynamic-tool',
                toolName: 'proposal',
                toolCallId: (tr as { id?: string }).id ?? `tr-${i}-${j}`,
                state: 'output-available',
                output: proposal,
            } as UIMessage['parts'][number]);
        });

        return {
            id: msg.id,
            role: msg.role === 'user' ? 'user' : 'assistant',
            parts,
        };
    });
}

type ProposalStatus = 'pending' | 'applied' | 'discarded';
```

> The `as UIMessage['parts'][number]` casts are needed because the `dynamic-tool`/`text` part unions are wide; the runtime shape matches what `ai-chat-panel.tsx` reads (`part.type`, `part.state`, `part.output`). If `types:check` complains about `ProposalStatus`, import the part's status type or inline the union — keep it a real union, not `any`.

- [ ] **Step 4: Run-pass + `npm run types:check`.**

- [ ] **Step 5: Commit** `git commit -am "feat(ai): reconstructSessionMessages helper for replay"`.

---

## Task 3: `useSessionChat` seeds `initialMessages`

**Files:**
- Modify: `api/resources/js/hooks/use-session-chat.ts`
- Test: `api/resources/js/hooks/__tests__/use-session-chat.test.ts` (extend)

**Interfaces:**
- Produces: `useSessionChat` options gain `initialMessages?: UIMessage[]`. The memoised `new Chat(...)` passes `messages: initialMessages ?? []`. `initialMessages` is read inside the `useMemo` but is NOT added to its dependency array (recreation is still driven by `resetNonce`/kind/context — the page bumps `resetNonce` after setting `initialMessages`, so the new Chat picks them up without recreating on every render).

- [ ] **Step 1: Write the failing test** (append)

```ts
    it('seeds the Chat with initialMessages', () => {
        const chatMock = vi.mocked(Chat);
        const initial = [{ id: 'm1', role: 'user', parts: [{ type: 'text', text: 'hi' }] }];

        renderHook(() =>
            useSessionChat({
                sessionId: 's1',
                kind: 'global',
                // @ts-expect-error minimal UIMessage stub for the mock
                initialMessages: initial,
            }),
        );

        const initArg = chatMock.mock.calls[0][0] as { messages?: unknown };
        expect(initArg.messages).toEqual(initial);
    });
```

(`Chat` is already mocked at the top of this file as `vi.fn(function(){...})`; add `import { Chat } from '@ai-sdk/react'` to the test imports if not present, and use `vi.mocked(Chat)`.)

- [ ] **Step 2: Run-fail.** `docker compose -f docker/docker-compose.yml exec app npx vitest run resources/js/hooks/__tests__/use-session-chat.test.ts` → `messages` undefined on the init arg.

- [ ] **Step 3: Implement.** In `use-session-chat.ts`:

Add `initialMessages` to the options type and destructure it:

```ts
import type { UIMessage } from 'ai';
```

```ts
type UseSessionChatOptions = {
    sessionId: string | null;
    kind: 'global' | 'entity' | 'chronicle';
    contextType?: string;
    contextId?: string | null;
    onNewSessionId?: (id: string) => void;
    resetNonce?: number;
    initialMessages?: UIMessage[];
};
```

Destructure `initialMessages` in the function params, then pass it into the `new Chat({...})` call as the first option:

```ts
            new Chat({
                messages: initialMessages ?? [],
                transport: new DefaultChatTransport({
                    // ...unchanged...
                }),
            }),
```

Leave the `useMemo` dependency array as `[kind, contextType, contextId, resetNonce]` (do NOT add `initialMessages` — keep the existing `// eslint-disable-next-line react-hooks/exhaustive-deps`).

- [ ] **Step 4: Run-pass + `npm run types:check`.**

- [ ] **Step 5: Commit** `git commit -am "feat(ai): useSessionChat seeds Chat with initialMessages"`.

---

## Task 4: Page — resume-into-scoped-agent + replay on select

**Files:**
- Modify: `api/resources/js/pages/ai/index.tsx`
- Test: `api/resources/js/pages/ai/__tests__/index.test.tsx` (extend)

**Interfaces:**
- Consumes: `reconstructSessionMessages` (`@/lib/reconstruct-session-messages`), `useSessionChat`'s new `initialMessages`, the existing `Session` type (`{id, kind, context_id, context_label, title, updated_at}`).
- Produces: the page holds `activeKind`/`activeContextType`/`activeContextId`/`initialMessages` state; `handleSelectSession(session)` becomes async — it fetches `GET /ai/sessions/${id}`, reconstructs messages, and sets the scoped kind/context + seeded messages, then bumps `chatKey`. `handleNewSession` resets kind to `'global'`, clears context + `initialMessages`. `useSessionChat` is called with the state-driven `kind`/`contextType`/`contextId`/`initialMessages` (not hardcoded `'global'`).

- [ ] **Step 1: Write the failing test** (append; follows the file's existing mock pattern — `AiChatPanel` and `useSessionChat` are stub-mocked, `fetch` mocked)

```tsx
    it('fetches and rebinds when a scoped session is selected', async () => {
        // First call: session list; second call: the show() payload.
        fetchMock
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    data: [{ id: 'sess-e', kind: 'entity', context_id: 'ent-1', context_label: 'Entity: Rome', title: 'Edit Rome', updated_at: null }],
                }),
            } as unknown as Response)
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    session: { id: 'sess-e', kind: 'entity', context_id: 'ent-1', context_label: 'Entity: Rome', title: 'Edit Rome' },
                    messages: [{ id: 'm1', role: 'user', content: 'hi', tool_results: [], created_at: null }],
                    proposals: [],
                }),
            } as unknown as Response);

        renderPage();

        await waitFor(() => expect(screen.getByText('Edit Rome')).toBeInTheDocument());

        fireEvent.click(screen.getByText('Edit Rome'));

        await waitFor(() =>
            expect(fetchMock).toHaveBeenCalledWith('/ai/sessions/sess-e', expect.anything()),
        );
    });
```

(Import `fireEvent` + `waitFor` from `@testing-library/react` in the test if not already imported.)

- [ ] **Step 2: Run-fail.** `docker compose -f docker/docker-compose.yml exec app npx vitest run resources/js/pages/ai/__tests__/index.test.tsx` → no `/ai/sessions/sess-e` fetch (select handler doesn't fetch yet).

- [ ] **Step 3: Implement.** In `pages/ai/index.tsx`:

Add imports:

```tsx
import { reconstructSessionMessages } from '@/lib/reconstruct-session-messages';
import type { UIMessage } from 'ai';
```

Add state (next to the existing `activeSessionId`/`chatKey`/`createdRefs`):

```tsx
    const [activeKind, setActiveKind] = useState<'global' | 'entity' | 'chronicle'>('global');
    const [activeContextType, setActiveContextType] = useState<string | undefined>(undefined);
    const [activeContextId, setActiveContextId] = useState<string | null>(null);
    const [initialMessages, setInitialMessages] = useState<UIMessage[]>([]);
```

Change the `useSessionChat` call to be state-driven:

```tsx
    const { chat, setSessionId } = useSessionChat({
        sessionId: activeSessionId,
        kind: activeKind,
        contextType: activeContextType,
        contextId: activeContextId,
        initialMessages,
        resetNonce: chatKey,
        onNewSessionId: useCallback(
            (id: string) => {
                setActiveSessionId(id);
                void refetchSessions();
            },
            [refetchSessions],
        ),
    });
```

Replace `handleNewSession` with a version that resets the scope + history:

```tsx
    function handleNewSession() {
        setActiveKind('global');
        setActiveContextType(undefined);
        setActiveContextId(null);
        setInitialMessages([]);
        setActiveSessionId(null);
        setCreatedRefs([]);
        setChatKey((k) => k + 1);
    }
```

Replace `handleSelectSession` with the async fetch + reconstruct + rebind version:

```tsx
    async function handleSelectSession(session: Session) {
        if (session.id === activeSessionId) {
            return;
        }

        const kind = (session.kind ?? 'global') as 'global' | 'entity' | 'chronicle';

        let messages: UIMessage[] = [];
        try {
            const res = await fetch(`/ai/sessions/${session.id}`, {
                headers: { Accept: 'application/json' },
            });
            if (res.ok) {
                const payload = await res.json();
                messages = reconstructSessionMessages(payload);
            }
        } catch {
            // On a failed history load, open the session empty rather than break.
            messages = [];
        }

        setActiveKind(kind);
        setActiveContextType(kind === 'global' ? undefined : kind);
        setActiveContextId(kind === 'global' ? null : session.context_id);
        setInitialMessages(messages);
        setActiveSessionId(session.id);
        setSessionId(session.id);
        setCreatedRefs([]);
        setChatKey((k) => k + 1);
    }
```

Update the session-list `<button onClick=...>` to handle the now-async function: change `onClick={() => handleSelectSession(s)}` to `onClick={() => void handleSelectSession(s)}`.

- [ ] **Step 4: Run-pass** the page test. Then `npm run types:check` + `lint:check` (0 errors) + `build`.

- [ ] **Step 5: Commit** `git commit -am "feat(ai): replay history + rebind kind/context on session select"`.

---

## Task 5: Page — session delete control

**Files:**
- Modify: `api/resources/js/pages/ai/index.tsx`
- Test: `api/resources/js/pages/ai/__tests__/index.test.tsx` (extend)

**Interfaces:**
- Produces: each session row has a delete control that calls `DELETE /ai/sessions/${id}` (with CSRF + `X-Requested-With` headers), then `refetchSessions()` and — if the deleted session was active — resets to a fresh new session (`handleNewSession`).

- [ ] **Step 1: Write the failing test** (append)

```tsx
    it('deletes a session and refetches the list', async () => {
        fetchMock
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    data: [{ id: 'sess-x', kind: 'global', context_id: null, context_label: 'Global', title: 'Chat X', updated_at: null }],
                }),
            } as unknown as Response)
            .mockResolvedValueOnce({ ok: true, json: async () => ({ deleted: true }) } as unknown as Response)
            .mockResolvedValueOnce({ ok: true, json: async () => ({ data: [] }) } as unknown as Response);

        renderPage();
        await waitFor(() => expect(screen.getByText('Chat X')).toBeInTheDocument());

        fireEvent.click(screen.getByRole('button', { name: /delete session/i }));

        await waitFor(() =>
            expect(fetchMock).toHaveBeenCalledWith(
                '/ai/sessions/sess-x',
                expect.objectContaining({ method: 'DELETE' }),
            ),
        );
    });
```

- [ ] **Step 2: Run-fail.** → no delete button / no DELETE fetch.

- [ ] **Step 3: Implement.** In `pages/ai/index.tsx`:

Add a CSRF helper near the top of the module (if not already present):

```tsx
function getCsrfToken(): string {
    return document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content ?? '';
}
```

Add a delete handler inside the component:

```tsx
    async function handleDeleteSession(session: Session, e: React.MouseEvent) {
        e.stopPropagation();
        const res = await fetch(`/ai/sessions/${session.id}`, {
            method: 'DELETE',
            headers: {
                'X-CSRF-TOKEN': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest',
                Accept: 'application/json',
            },
        });
        if (res.ok) {
            if (session.id === activeSessionId) {
                handleNewSession();
            }
            void refetchSessions();
        }
    }
```

In the session-list `<li>`, wrap the existing select `<button>` and a new delete control in a flex row so the delete button sits at the right. Replace the `<li>` body markup with:

```tsx
                            <li key={s.id} className="group relative flex items-center">
                                <button
                                    type="button"
                                    onClick={() => void handleSelectSession(s)}
                                    className={cn(
                                        'min-w-0 flex-1 px-4 py-2 text-left text-sm transition-colors hover:bg-muted',
                                        activeSessionId === s.id && 'bg-muted font-medium',
                                    )}
                                >
                                    <div className="truncate font-medium">
                                        {s.title || '(untitled)'}
                                    </div>
                                    <div className="truncate text-xs text-muted-foreground">
                                        {s.context_label}
                                    </div>
                                </button>
                                <button
                                    type="button"
                                    aria-label="Delete session"
                                    title="Delete session"
                                    onClick={(e) => void handleDeleteSession(s, e)}
                                    className="absolute right-1 rounded p-1 text-muted-foreground opacity-0 transition-opacity hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100"
                                >
                                    <Trash2 className="size-3.5" />
                                </button>
                            </li>
```

Add the icon import: `import { Plus, Trash2 } from 'lucide-react';` (merge with the existing lucide import — keep alphabetical), and ensure `cn` is imported from `@/lib/utils` (add if missing).

- [ ] **Step 4: Run-pass** the page test (all of it). Then `npm run types:check` + `lint:check` (0 errors) + `build`.

- [ ] **Step 5: Commit** `git commit -am "feat(ai): delete session control on the Create with AI page"`.

---

## Task 6: Integration smoke

**Files:** No new files — verification pass.

- [ ] **Step 1:** Full frontend test suite: `docker compose -f docker/docker-compose.yml exec app npx vitest run` → all green.
- [ ] **Step 2:** `docker compose -f docker/docker-compose.yml exec app npm run types:check` → clean.
- [ ] **Step 3:** `docker compose -f docker/docker-compose.yml exec app npm run lint:check` → 0 errors (the pre-existing `dashboard.tsx` warning is OK).
- [ ] **Step 4:** `docker compose -f docker/docker-compose.yml exec app npm run build` → succeeds.
- [ ] **Step 5:** Backend untouched, but confirm no regression in the AI suite: `docker compose -f docker/docker-compose.yml exec app php artisan test --filter "Ai"` → green.
- [ ] **Step 6:** If anything was left uncommitted, commit `chore(ai): Phase C replay/resume/delete integration`.

---

## Self-Review

### Spec coverage (spec §6.2 replay, §6.3 scoped resume, §5.3 delete, §7C)
| Requirement | Task |
|---|---|
| Open a session → replay its messages + proposal cards with status (§6.2) | T1 (status seed) + T2 (reconstruct) + T3 (seed Chat) + T4 (wire on select) |
| Reopen a scoped session → rebinds to its editor agent (§6.3) | T4 (state-driven kind/context) |
| Applied/discarded render read-only; pending stays actionable (§10 Q2) | T1 |
| Session delete (§5.3) | T5 |
| History list across both kinds | already present (page lists all sessions from `GET /ai/sessions`) |

### Placeholder scan
No TBD/TODO. Every code step has complete code. The `reconstructSessionMessages` casts are explained (wide part union; runtime shape verified against `ai-chat-panel.tsx`).

### Type consistency
- `ProposalPart.status?` (T1) is read by `reconstructSessionMessages` merge (T2) and seeded into `ProposalCard.partStatus` (T1).
- `SessionShowPayload`/`SessionMessage`/`SessionProposal` (T2) match the Phase A `show()` JSON exactly.
- `useSessionChat` `initialMessages?: UIMessage[]` (T3) consumed by the page (T4) with the `reconstructSessionMessages` return type (`UIMessage[]`).
- `kind` union `'global'|'entity'|'chronicle'` consistent across page state (T4) and the hook.
- Literal URLs (`/ai/sessions`, `/ai/sessions/${id}`) consistent with the existing page/hook; no Wayfinder.

### Notes / risks
- Replay is display-only; the controller ignores body history except the last user message and loads real history via `continue()` — no server-side doubling (stated in Global Constraints; backend unchanged).
- The `as UIMessage['parts'][number]` casts are the one place TS strictness is relaxed; if `types:check` fails, the implementer keeps the union real (no `any`) per the brief.
