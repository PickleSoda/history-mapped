// @vitest-environment jsdom
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useSessionChat } from '@/hooks/use-session-chat';

import { useScopedSessionChat } from '../use-scoped-session-chat';

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
