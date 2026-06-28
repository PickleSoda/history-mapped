# AI Sidebar Sessions + Proposal Lifecycle (Phase D) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the per-record "Ask AI" sidebar onto the session model so it resumes a record's latest session (replaying history + locked proposal cards), with a New-chat control and scoped badge, while keeping create-mode behavior; and label sessions Global/Entity/Chronicle on the `/ai` page.

**Architecture:** Frontend-only, reusing Phase A endpoints and Phase B/C pieces. `useSessionChat` gains a `mode` body field (so it can drive create-mode) and a `sessionId`-prop sync effect (so resets actually take). `AiChatPanel` gains a `proposalMode` prop. A new `useScopedSessionChat` hook resumes the record's most-recent session (`GET /ai/sessions?context_type&context_id` → `GET /ai/sessions/{id}` → `reconstructSessionMessages`) and wires `useSessionChat`. The sidebar is restructured to use them + `AiChatPanel`.

**Tech Stack:** React 19, `@ai-sdk/react` v3 / `ai` v6, Inertia, vitest. Admin JS in `api/resources/js`, run in the Docker `app` container.

## Global Constraints

- Frontend cmds in Docker: `docker compose -f docker/docker-compose.yml exec app <cmd>`. Tests: `... npx vitest run <file>`. Gates: `... npm run types:check` / `lint:check` / `build` — all clean. `lint:check` must be **0 errors** (a pre-existing `dashboard.tsx` WARNING is OK). Run `lint:check` per task, not just `types:check`.
- **Literal URLs, no Wayfinder** — `/ai/chat`, `/ai/sessions`, `/ai/sessions/${id}`. Do NOT import from `@/routes/ai`.
- **Backend is unchanged.** Endpoints consumed as-is: `GET /ai/sessions?context_type=&context_id=` (newest-first list), `GET /ai/sessions/{id}` (replay payload `{session, messages, proposals}`), `POST /ai/chat` (returns `X-Conversation-Id`), `/ai/proposals/.../apply|discard`.
- **Sidebar resumes in EDIT mode only.** Create-page mode (`ai_context = {type, id:null, mode:'create'}`) stays transient — no resume, and apply still redirects (create-mode `redirect_url`).
- **Apply keeps `router.reload()`** (record data refreshes). The resumed sidebar replays after reload, so the applied proposal card reappears locked (`ProposalCard` already seeds `applied`/`discarded` parts as locked from Phase C).
- **The AI panel stays open across `router.reload()`** (its open-state persists in `sessionStorage` via `ai-panel-context.tsx`), so the sidebar remounts and re-resumes.
- Type unions consistent: `kind`/context_type values are `'entity'|'chronicle'` for the sidebar (`'global'` only on the `/ai` page). `mode` is `'edit'|'create'`.
- TDD throughout. Vitest convention: per-file `// @vitest-environment jsdom`, explicit `import { describe, it, vi, expect } from 'vitest'`.

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `api/resources/js/hooks/use-session-chat.ts` | Modify | `mode` in transport body + sync `currentSessionId` to the `sessionId` prop |
| `api/resources/js/components/ai/ai-chat-panel.tsx` | Modify | `proposalMode?: 'edit'\|'create'` prop → ProposalCards |
| `api/resources/js/hooks/use-scoped-session-chat.ts` | Create | Resume a record's latest session + wire `useSessionChat`; `startNewChat` |
| `api/resources/js/components/ai/ai-sidebar.tsx` | Modify | Use the hook + `AiChatPanel`; New-chat control + scoped badge; keep chrome; create-mode unchanged |
| `api/resources/js/pages/ai/index.tsx` | Modify | Global/Entity/Chronicle badge in the session list |

---

## Task 1: `useSessionChat` — `mode` in body + sessionId-prop sync

**Files:**
- Modify: `api/resources/js/hooks/use-session-chat.ts`
- Test: `api/resources/js/hooks/__tests__/use-session-chat.test.ts` (extend)

**Interfaces:**
- Produces: `UseSessionChatOptions` gains `mode?: 'edit' | 'create'`. The transport `body` includes `mode` when set. A `useEffect` keyed on the `sessionId` prop syncs `currentSessionId` + `sessionIdRef.current` to it — so a parent changing `sessionId` (resume → an id, or New-chat → null) actually resets the hook. `mode` is added to the `useMemo` dep array.

**Why the sync effect:** today `currentSessionId` is initialised from `sessionId` only once; later prop changes are ignored, so "reset to a new session" silently keeps sending the old `conversation_id`. The effect fixes this for both the sidebar and the existing `/ai` page.

- [ ] **Step 1: Write the failing tests** (append)

```ts
    it('includes mode in the transport body when provided', () => {
        const transportMock = vi.mocked(DefaultChatTransport);

        renderHook(() =>
            useSessionChat({ sessionId: null, kind: 'entity', contextType: 'entity', contextId: 'e1', mode: 'edit' }),
        );

        const opts = transportMock.mock.calls[0][0] as { body: () => Record<string, unknown> };
        const body = opts.body();
        expect(body.mode).toBe('edit');
        expect(body.context_type).toBe('entity');
        expect(body.context_id).toBe('e1');
    });

    it('omits mode from the body when not provided', () => {
        const transportMock = vi.mocked(DefaultChatTransport);

        renderHook(() => useSessionChat({ sessionId: null, kind: 'global' }));

        const opts = transportMock.mock.calls.at(-1)![0] as { body: () => Record<string, unknown> };
        expect('mode' in opts.body()).toBe(false);
    });

    it('syncs the returned sessionId when the sessionId prop changes', () => {
        const { result, rerender } = renderHook(
            ({ sid }) => useSessionChat({ sessionId: sid, kind: 'entity', contextType: 'entity', contextId: 'e1' }),
            { initialProps: { sid: 's1' as string | null } },
        );

        expect(result.current.sessionId).toBe('s1');

        rerender({ sid: null });
        expect(result.current.sessionId).toBeNull();

        rerender({ sid: 's2' });
        expect(result.current.sessionId).toBe('s2');
    });
```

- [ ] **Step 2: Run-fail.** `docker compose -f docker/docker-compose.yml exec app npx vitest run resources/js/hooks/__tests__/use-session-chat.test.ts` → the mode + sync tests fail.

- [ ] **Step 3: Implement.** In `use-session-chat.ts`:

Add `useEffect` to the React import: `import { useCallback, useEffect, useMemo, useRef, useState } from 'react';`.

Add `mode` to the options type (after `contextId`):

```ts
    /** Drives create vs edit routing on the server; omitted ⇒ server default (edit). */
    mode?: 'edit' | 'create';
```

Destructure `mode` in the params (alongside the others).

Add the sync effect right after the `onNewSessionIdRef` lines:

```ts
    // Sync the internal session id when the parent changes the prop (resume → an id,
    // New chat → null). Without this, currentSessionId is frozen at its mount value.
    useEffect(() => {
        sessionIdRef.current = sessionId;
        setCurrentSessionId(sessionId);
    }, [sessionId]);
```

Add `mode` to the `body` function (before the context spread):

```ts
                    body: () => ({
                        kind,
                        conversation_id: sessionIdRef.current,
                        ...(mode ? { mode } : {}),
                        ...(kind !== 'global' && contextType
                            ? { context_type: contextType, context_id: contextId ?? null }
                            : {}),
                    }),
```

Add `mode` to the `useMemo` dep array: `[kind, contextType, contextId, mode, resetNonce]` (keep the existing eslint-disable).

- [ ] **Step 4: Run-pass** (all hook tests incl. the 4 existing). `npm run types:check` + `lint:check` (0 errors).

- [ ] **Step 5: Commit** `git commit -am "feat(ai): useSessionChat sends mode + syncs sessionId prop"`.

---

## Task 2: `AiChatPanel` — `proposalMode` prop

**Files:**
- Modify: `api/resources/js/components/ai/ai-chat-panel.tsx`
- Test: `api/resources/js/components/ai/__tests__/ai-chat-panel.test.tsx` (extend)

**Interfaces:**
- Produces: `AiChatPanel` props gain `proposalMode?: 'edit' | 'create'` (default `'edit'`). Both `ProposalCard` render sites use `mode={proposalMode}` instead of the hardcoded `"edit"`. The `/ai` page passes nothing (defaults `'edit'`, relies on `onCreatedRef` for global). The sidebar passes `proposalMode={aiCtx.mode}` so create-mode applies redirect.

- [ ] **Step 1: Write the failing test** (append). Mock `ProposalCard` to expose its `mode`, and `useChat` to return one assistant message with a proposal tool part.

```tsx
    it('passes proposalMode through to ProposalCard', async () => {
        vi.resetModules();
        vi.doMock('@/components/ai/proposal-card', () => ({
            parseProposal: () => ({ proposal_id: 'p1', parts: [{ key: 'k', human_diff: { summary: 's' } }] }),
            ProposalCard: ({ mode }: { mode?: string }) => <div data-testid="pc" data-mode={mode} />,
        }));
        vi.doMock('@ai-sdk/react', () => ({
            useChat: () => ({
                messages: [
                    { id: 'm1', role: 'assistant', parts: [{ type: 'dynamic-tool', state: 'output-available', output: {} }] },
                ],
                sendMessage: vi.fn(), status: 'idle', stop: vi.fn(),
            }),
        }));
        const { AiChatPanel: Panel } = await import('../ai-chat-panel');

        render(<Panel chat={{} as never} kind="entity" sessionId={null} proposalMode="create" />);

        expect(screen.getByTestId('pc').getAttribute('data-mode')).toBe('create');
    });
```

> If the file's existing top-level `vi.mock('@ai-sdk/react', …)` conflicts with `vi.doMock` + dynamic import, instead add a dedicated mock of `@/components/ai/proposal-card` at the top of the file exposing `data-mode`, and assert against it in this test (the existing empty-state test renders no proposal, so it is unaffected). Use whichever the file's existing structure supports; the assertion (proposalMode reaches ProposalCard as `data-mode`) is the requirement.

- [ ] **Step 2: Run-fail.** `docker compose -f docker/docker-compose.yml exec app npx vitest run resources/js/components/ai/__tests__/ai-chat-panel.test.tsx`.

- [ ] **Step 3: Implement.** In `ai-chat-panel.tsx`:

Add to the `Props` type: `proposalMode?: 'edit' | 'create';`. Destructure with a default in the signature:

```tsx
export function AiChatPanel({ chat, kind, sessionId: _sessionId, onCreatedRef, proposalMode = 'edit', className }: Props) {
```

In BOTH `<ProposalCard … mode="edit" …>` render sites, change `mode="edit"` to `mode={proposalMode}`.

- [ ] **Step 4: Run-pass** (new + existing panel tests). `npm run types:check` + `lint:check` (0 errors).

- [ ] **Step 5: Commit** `git commit -am "feat(ai): AiChatPanel proposalMode prop"`.

---

## Task 3: `useScopedSessionChat` — resume the record's latest session

**Files:**
- Create: `api/resources/js/hooks/use-scoped-session-chat.ts`
- Test: `api/resources/js/hooks/__tests__/use-scoped-session-chat.test.ts`

**Interfaces:**
- Consumes: `useSessionChat` (Task 1 — incl. `mode` + sessionId sync), `reconstructSessionMessages` (`@/lib/reconstruct-session-messages`).
- Produces: `useScopedSessionChat({ type, id, mode }): { chat, sessionId, resolved, startNewChat }`. On mount / when `(type,id,mode)` changes: in edit mode with an `id`, fetches `GET /ai/sessions?context_type={type}&context_id={id}`, takes `data[0]` (most recent), fetches its replay, reconstructs → seeds `useSessionChat`'s `initialMessages` + `sessionId`, and bumps an internal reset nonce so the seeded Chat is built; `resolved` flips true when done (true immediately in create mode, with no resume). `startNewChat()` clears the seed (sessionId→null, messages→[]) and bumps the nonce.

- [ ] **Step 1: Write the failing test**

```ts
// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';

const setSessionId = vi.fn();
vi.mock('@/hooks/use-session-chat', () => ({
    useSessionChat: vi.fn((opts: { sessionId: string | null }) => ({
        chat: { _opts: opts },
        sessionId: opts.sessionId,
        setSessionId,
    })),
}));
vi.mock('@/lib/reconstruct-session-messages', () => ({
    reconstructSessionMessages: () => [{ id: 'm1', role: 'user', parts: [{ type: 'text', text: 'hi' }] }],
}));

import { useScopedSessionChat } from '../use-scoped-session-chat';
import { useSessionChat } from '@/hooks/use-session-chat';

beforeEach(() => vi.clearAllMocks());

describe('useScopedSessionChat', () => {
    it('resumes the most-recent session in edit mode', async () => {
        const fetchMock = vi.fn()
            .mockResolvedValueOnce({ ok: true, json: async () => ({ data: [{ id: 'sess-1', kind: 'entity', context_id: 'e1' }] }) })
            .mockResolvedValueOnce({ ok: true, json: async () => ({ session: {}, messages: [], proposals: [] }) });
        vi.stubGlobal('fetch', fetchMock);

        const { result } = renderHook(() => useScopedSessionChat({ type: 'entity', id: 'e1', mode: 'edit' }));

        await waitFor(() => expect(result.current.resolved).toBe(true));

        expect(fetchMock).toHaveBeenNthCalledWith(1, '/ai/sessions?context_type=entity&context_id=e1', expect.anything());
        expect(fetchMock).toHaveBeenNthCalledWith(2, '/ai/sessions/sess-1', expect.anything());
        // useSessionChat got the resumed session id + seeded messages
        const lastCall = vi.mocked(useSessionChat).mock.calls.at(-1)![0];
        expect(lastCall.sessionId).toBe('sess-1');
        expect(lastCall.initialMessages).toHaveLength(1);

        vi.unstubAllGlobals();
    });

    it('does not resume in create mode (resolves immediately, no fetch)', async () => {
        const fetchMock = vi.fn();
        vi.stubGlobal('fetch', fetchMock);

        const { result } = renderHook(() => useScopedSessionChat({ type: 'entity', id: null, mode: 'create' }));

        await waitFor(() => expect(result.current.resolved).toBe(true));
        expect(fetchMock).not.toHaveBeenCalled();

        vi.unstubAllGlobals();
    });

    it('startNewChat clears the seeded session', async () => {
        const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ data: [] }) });
        vi.stubGlobal('fetch', fetchMock);

        const { result } = renderHook(() => useScopedSessionChat({ type: 'entity', id: 'e1', mode: 'edit' }));
        await waitFor(() => expect(result.current.resolved).toBe(true));

        act(() => result.current.startNewChat());

        const lastCall = vi.mocked(useSessionChat).mock.calls.at(-1)![0];
        expect(lastCall.sessionId).toBeNull();
        expect(lastCall.initialMessages).toEqual([]);

        vi.unstubAllGlobals();
    });
});
```

- [ ] **Step 2: Run-fail.** `docker compose -f docker/docker-compose.yml exec app npx vitest run resources/js/hooks/__tests__/use-scoped-session-chat.test.ts` → module missing.

- [ ] **Step 3: Implement** `api/resources/js/hooks/use-scoped-session-chat.ts`:

```ts
import type { Chat, UIMessage } from '@ai-sdk/react';
import { useCallback, useEffect, useState } from 'react';
import { useSessionChat } from '@/hooks/use-session-chat';
import { reconstructSessionMessages } from '@/lib/reconstruct-session-messages';

type Args = { type: 'entity' | 'chronicle'; id: string | null; mode: 'edit' | 'create' };

type Result = {
    chat: Chat<UIMessage>;
    sessionId: string | null;
    /** False while the resume fetch is in flight; true once seeded (or immediately in create mode). */
    resolved: boolean;
    /** Start a fresh scoped session (clears replayed history + session id). */
    startNewChat: () => void;
};

/**
 * Binds a chat to a record and, in edit mode, resumes that record's most-recent
 * session (replaying its history + proposal cards). Create mode is transient — no
 * resume. Reuses useSessionChat for transport + X-Conversation-Id capture.
 */
export function useScopedSessionChat({ type, id, mode }: Args): Result {
    const [resetNonce, setResetNonce] = useState(0);
    const [resolved, setResolved] = useState(false);
    const [seedMessages, setSeedMessages] = useState<UIMessage[]>([]);
    const [seedSessionId, setSeedSessionId] = useState<string | null>(null);

    const { chat, sessionId } = useSessionChat({
        sessionId: seedSessionId,
        kind: type,
        contextType: type,
        contextId: id,
        mode,
        initialMessages: seedMessages,
        resetNonce,
    });

    useEffect(() => {
        let cancelled = false;
        setResolved(false);

        const seed = (messages: UIMessage[], sid: string | null) => {
            if (cancelled) {
                return;
            }
            setSeedMessages(messages);
            setSeedSessionId(sid);
            setResetNonce((n) => n + 1);
            setResolved(true);
        };

        async function resume() {
            if (mode !== 'edit' || !id) {
                seed([], null); // create mode (or no id) is transient — no resume
                return;
            }
            try {
                const listRes = await fetch(
                    `/ai/sessions?context_type=${type}&context_id=${encodeURIComponent(id)}`,
                    { headers: { Accept: 'application/json' } },
                );
                const latest = listRes.ok ? (await listRes.json()).data?.[0] : undefined;
                if (!latest) {
                    seed([], null);
                    return;
                }
                const showRes = await fetch(`/ai/sessions/${latest.id}`, {
                    headers: { Accept: 'application/json' },
                });
                if (!showRes.ok) {
                    seed([], null);
                    return;
                }
                seed(reconstructSessionMessages(await showRes.json()), latest.id);
            } catch {
                seed([], null); // open empty on any failure rather than break
            }
        }

        void resume();
        return () => {
            cancelled = true;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [type, id, mode]);

    const startNewChat = useCallback(() => {
        setSeedMessages([]);
        setSeedSessionId(null);
        setResetNonce((n) => n + 1);
        setResolved(true);
    }, []);

    return { chat, sessionId, resolved, startNewChat };
}
```

- [ ] **Step 4: Run-pass** + `npm run types:check` + `lint:check` (0 errors).

- [ ] **Step 5: Commit** `git commit -am "feat(ai): useScopedSessionChat resumes a record's latest session"`.

---

## Task 4: Migrate `ai-sidebar.tsx` to the session model

**Files:**
- Modify: `api/resources/js/components/ai/ai-sidebar.tsx`
- Test: `api/resources/js/components/ai/__tests__/ai-sidebar.test.tsx` (create)

**Interfaces:**
- Consumes: `useScopedSessionChat` (Task 3), `AiChatPanel` (Task 2 — with `proposalMode`), `useAiContext`, `useAiPanel`.
- Produces: the sidebar renders, when a record context exists, an inner `ScopedSidebarBody` (keyed by record identity so switching records remounts it cleanly) that resumes the session and renders `AiChatPanel`; header shows a scoped badge + a "New chat" button (`startNewChat`) + close; a loading state shows until `resolved`. No record context → the existing disabled/empty state. The sidebar no longer hand-rolls the message loop or builds a Chat directly.

- [ ] **Step 1: Write the failing test** Create `api/resources/js/components/ai/__tests__/ai-sidebar.test.tsx`:

```tsx
// @vitest-environment jsdom
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { describe, expect, it, vi } from 'vitest';

const startNewChat = vi.fn();
vi.mock('@/hooks/use-scoped-session-chat', () => ({
    useScopedSessionChat: () => ({ chat: {}, sessionId: 's1', resolved: true, startNewChat }),
}));
vi.mock('@/components/ai/ai-chat-panel', () => ({
    AiChatPanel: ({ proposalMode }: { proposalMode?: string }) => (
        <div data-testid="panel" data-proposalmode={proposalMode} />
    ),
}));
vi.mock('@/components/ai/ai-panel-context', () => ({
    useAiPanel: () => ({ open: true, setOpen: vi.fn() }),
}));
const mockCtx = vi.fn();
vi.mock('@/hooks/use-ai-context', () => ({ useAiContext: () => mockCtx() }));

import { AiSidebar } from '../ai-sidebar';

describe('AiSidebar', () => {
    it('renders the scoped chat panel + New chat + scoped badge for a record', () => {
        mockCtx.mockReturnValue({ type: 'entity', id: 'e1', mode: 'edit' });
        render(<AiSidebar />);

        expect(screen.getByTestId('panel')).toBeInTheDocument();
        expect(screen.getByTestId('panel').getAttribute('data-proposalmode')).toBe('edit');
        expect(screen.getByRole('button', { name: /new chat/i })).toBeInTheDocument();
        expect(screen.getByText(/entity/i)).toBeInTheDocument(); // scoped badge

        fireEvent.click(screen.getByRole('button', { name: /new chat/i }));
        expect(startNewChat).toHaveBeenCalled();
    });

    it('shows the empty state with no record context', () => {
        mockCtx.mockReturnValue(null);
        render(<AiSidebar />);

        expect(screen.queryByTestId('panel')).not.toBeInTheDocument();
        expect(screen.getByText(/navigate to an entity or chronicle/i)).toBeInTheDocument();
    });
});
```

- [ ] **Step 2: Run-fail.** `docker compose -f docker/docker-compose.yml exec app npx vitest run resources/js/components/ai/__tests__/ai-sidebar.test.tsx`.

- [ ] **Step 3: Rewrite `ai-sidebar.tsx`.** Replace the file with:

```tsx
import { BotMessageSquare, Plus, X } from 'lucide-react';
import { useAiPanel } from '@/components/ai/ai-panel-context';
import { AiChatPanel } from '@/components/ai/ai-chat-panel';
import { Button } from '@/components/ui/button';
import type { AiContext } from '@/hooks/use-ai-context';
import { useAiContext } from '@/hooks/use-ai-context';
import { useScopedSessionChat } from '@/hooks/use-scoped-session-chat';
import { cn } from '@/lib/utils';

/**
 * AI chat sidebar for the admin (right-docked, non-modal).
 *
 * Bound to the current entity/chronicle via useAiContext. In edit mode it resumes
 * that record's most-recent session (replaying history + proposal cards) through
 * useScopedSessionChat; create-page mode is transient. The chat UI is the shared
 * AiChatPanel; a "New chat" control starts a fresh scoped session.
 */
export function AiSidebar() {
    const { open, setOpen } = useAiPanel();
    const aiCtx = useAiContext();

    return (
        <aside
            aria-hidden={!open}
            className={cn(
                'z-30 border-l border-sidebar-border bg-sidebar text-sidebar-foreground',
                'fixed inset-y-0 right-0 w-110 max-w-full shadow-lg transition-transform duration-200 ease-in-out',
                open ? 'translate-x-0' : 'pointer-events-none translate-x-full',
                'md:sticky md:top-0 md:h-svh md:max-w-none md:shrink-0 md:translate-x-0 md:self-start md:overflow-hidden md:shadow-none md:transition-[width] md:duration-200',
                open ? 'md:w-110' : 'md:pointer-events-none md:w-0',
            )}
        >
            <div className="flex h-full w-110 max-w-full flex-col md:max-w-none">
                {aiCtx ? (
                    <ScopedSidebarBody
                        key={`${aiCtx.type}:${aiCtx.id}:${aiCtx.mode}`}
                        aiCtx={aiCtx}
                        onClose={() => setOpen(false)}
                    />
                ) : (
                    <EmptySidebarBody onClose={() => setOpen(false)} />
                )}
            </div>
        </aside>
    );
}

function ScopedSidebarBody({ aiCtx, onClose }: { aiCtx: AiContext; onClose: () => void }) {
    const { chat, sessionId, resolved, startNewChat } = useScopedSessionChat({
        type: aiCtx.type,
        id: aiCtx.id,
        mode: aiCtx.mode,
    });

    return (
        <>
            <div className="flex items-center gap-2 border-b px-4 py-3 text-sm font-semibold">
                <BotMessageSquare className="size-4 text-primary" />
                Ask AI
                <span className="ml-auto rounded-full bg-muted px-2 py-0.5 text-xs font-normal capitalize text-muted-foreground">
                    {aiCtx.mode === 'create' ? `New ${aiCtx.type}` : `Scoped: ${aiCtx.type}`}
                </span>
                <Button
                    variant="ghost"
                    size="icon"
                    className="size-7"
                    onClick={startNewChat}
                    title="New chat"
                    aria-label="New chat"
                >
                    <Plus className="size-4" />
                </Button>
                <Button variant="ghost" size="icon" className="size-7" onClick={onClose} title="Close">
                    <X className="size-4" />
                </Button>
            </div>

            {resolved ? (
                <AiChatPanel
                    chat={chat}
                    kind={aiCtx.type}
                    sessionId={sessionId}
                    proposalMode={aiCtx.mode}
                    className="min-h-0 flex-1"
                />
            ) : (
                <div className="flex flex-1 items-center justify-center text-xs text-muted-foreground">
                    Loading session…
                </div>
            )}
        </>
    );
}

function EmptySidebarBody({ onClose }: { onClose: () => void }) {
    return (
        <>
            <div className="flex items-center gap-2 border-b px-4 py-3 text-sm font-semibold">
                <BotMessageSquare className="size-4 text-primary" />
                Ask AI
                <Button variant="ghost" size="icon" className="ml-auto size-7" onClick={onClose} title="Close">
                    <X className="size-4" />
                </Button>
            </div>
            <div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 text-center text-muted-foreground">
                <BotMessageSquare className="size-8" />
                <p className="text-sm">Navigate to an entity or chronicle to use the AI assistant.</p>
            </div>
        </>
    );
}
```

> `AiChatPanel` provides the empty state ("Ask anything about this record") and the input, so the sidebar no longer needs its own message loop / textarea. `proposalMode={aiCtx.mode}` makes create-mode apply redirect and edit-mode apply reload (default in `ProposalCard`). The `key` on `ScopedSidebarBody` forces a clean remount when the bound record changes.

- [ ] **Step 4: Run-pass** the sidebar test. Then `npm run types:check` + `lint:check` (0 errors) + `build`.

- [ ] **Step 5: Commit** `git commit -am "feat(ai): sidebar resumes record sessions via AiChatPanel + New chat"`.

---

## Task 5: `/ai` session list — Global/Entity/Chronicle badge

**Files:**
- Modify: `api/resources/js/pages/ai/index.tsx`
- Test: `api/resources/js/pages/ai/__tests__/index.test.tsx` (extend)

**Interfaces:**
- Produces: each session row shows a compact badge with its kind (`Global` / `Entity` / `Chronicle`) derived from `session.kind`.

- [ ] **Step 1: Write the failing test** (append). The existing "shows session list items" test returns a session with `kind: 'entity'`; add an assertion (or a new test) that the kind badge renders.

```tsx
    it('shows a kind badge for each session', async () => {
        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                data: [{ id: 'sess-1', kind: 'entity', context_id: 'ent-1', context_label: 'Entity: Rome', title: 'Edit Rome', updated_at: null }],
            }),
        } as unknown as Response);

        renderPage();

        await waitFor(() => expect(screen.getByText('Edit Rome')).toBeInTheDocument());
        expect(screen.getByText('Entity')).toBeInTheDocument(); // kind badge
    });
```

- [ ] **Step 2: Run-fail.** `docker compose -f docker/docker-compose.yml exec app npx vitest run resources/js/pages/ai/__tests__/index.test.tsx`.

- [ ] **Step 3: Implement.** In `pages/ai/index.tsx`, add a label helper near the top of the module:

```tsx
function kindLabel(kind: string | null): string {
    if (kind === 'global') return 'Global';
    if (kind === 'chronicle') return 'Chronicle';
    if (kind === 'entity') return 'Entity';
    return 'Session';
}
```

In the session-list `<li>` select `<button>`, add the badge above (or beside) the title. Replace the inner `<div className="truncate font-medium">…</div>` block with:

```tsx
                                    <div className="flex items-center gap-1.5">
                                        <span className="shrink-0 rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                                            {kindLabel(s.kind)}
                                        </span>
                                        <span className="truncate font-medium">
                                            {s.title || '(untitled)'}
                                        </span>
                                    </div>
```

(Keep the existing `context_label` line below it.)

- [ ] **Step 4: Run-pass** + `npm run types:check` + `lint:check` (0 errors) + `build`.

- [ ] **Step 5: Commit** `git commit -am "feat(ai): kind badge on the Create with AI session list"`.

---

## Task 6: Integration smoke

**Files:** No new files — verification pass.

- [ ] **Step 1:** Full frontend suite: `docker compose -f docker/docker-compose.yml exec app npx vitest run` → all green.
- [ ] **Step 2:** `docker compose -f docker/docker-compose.yml exec app npm run types:check` → clean.
- [ ] **Step 3:** `docker compose -f docker/docker-compose.yml exec app npm run lint:check` → 0 errors (pre-existing `dashboard.tsx` warning OK).
- [ ] **Step 4:** `docker compose -f docker/docker-compose.yml exec app npm run build` → succeeds.
- [ ] **Step 5:** Backend untouched, but confirm no AI regression: `docker compose -f docker/docker-compose.yml exec app php artisan test --filter "Ai"` → green.
- [ ] **Step 6:** Commit anything uncommitted `chore(ai): Phase D sidebar sessions integration`.

---

## Self-Review

### Spec coverage (spec §3.1 sidebar migration, §3.2 lifecycle, §3.3 indication)
| Requirement | Task |
|---|---|
| Sidebar resumes record's latest session (replay) (§3.1) | T3 (hook) + T4 (sidebar) |
| Sidebar uses AiChatPanel; New chat control; scoped badge (§3.1) | T4 |
| Create mode unchanged — no resume, redirect-after-apply (§3.1) | T1 (mode in body) + T2 (proposalMode) + T3 (no resume in create) + T4 (proposalMode=mode) |
| Applied card reappears locked after apply+reload (§3.2) | Falls out of T3 resume + Phase C `ProposalCard` status seed; sidebar remounts on reload (panel stays open via sessionStorage) |
| Leaving a conversation hides its cards; reopening replays with status (§3.2) | T3/T4 (only the active session is shown; New chat / record switch remounts) |
| Global/Entity/Chronicle badge on `/ai` list (§3.3) | T5 |
| Sidebar scoped badge (§3.3) | T4 |

### Placeholder scan
No TBD/TODO. Every code step has complete code. The T2 test note offers a concrete fallback (mock ProposalCard with `data-mode`) if the file's existing mock structure conflicts with `vi.doMock`.

### Type consistency
- `useSessionChat` `mode?: 'edit'|'create'` (T1) consumed by `useScopedSessionChat` (T3) and indirectly the sidebar (T4).
- `AiChatPanel` `proposalMode?: 'edit'|'create'` (T2) passed by the sidebar (T4) as `aiCtx.mode`.
- `useScopedSessionChat({type,id,mode}) → {chat, sessionId, resolved, startNewChat}` (T3) consumed verbatim by the sidebar (T4).
- `AiContext = {type:'entity'|'chronicle', id:string|null, mode:'edit'|'create'}` (existing) drives T4.
- Literal URLs `/ai/sessions?...`, `/ai/sessions/${id}` (T3) — no Wayfinder.

### Notes / risks
- **Latent fix:** T1's sessionId-sync effect also fixes the `/ai` page "New session" (which previously kept the old `conversation_id` because `currentSessionId` was frozen at mount). The `/ai` page tests stub `useSessionChat`, so they're unaffected; the fix is verified by the new T1 sync test.
- The sidebar no longer renders its own message loop — `AiChatPanel` owns the empty state, input, and proposal rendering. The empty-state copy changes from the sidebar's old text to `AiChatPanel`'s "Ask anything about this record" (scoped kind), which is acceptable and consistent with the `/ai` page.
- Apply in the sidebar keeps `router.reload()` (via `ProposalCard` edit-mode default); the panel stays open across reload (`sessionStorage`) and re-resumes, so the applied card returns locked.
