// @vitest-environment jsdom
import { Chat } from '@ai-sdk/react';
import { renderHook, act } from '@testing-library/react';
import { DefaultChatTransport } from 'ai';
import { describe, afterEach, expect, it, vi } from 'vitest';
import { useSessionChat } from '../use-session-chat';

vi.mock('@ai-sdk/react', () => ({
    Chat: vi.fn(function () {
        return { id: 'mock-chat' };
    }),
}));

vi.mock('ai', () => ({
    DefaultChatTransport: vi.fn(function (opts: unknown) {
        return { _opts: opts };
    }),
}));

afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
});

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

    it('captures X-Conversation-Id from the first response and calls onNewSessionId', async () => {
        const onNewSessionId = vi.fn();

        const { result } = renderHook(() =>
            useSessionChat({ sessionId: null, kind: 'global', onNewSessionId }),
        );

        // Grab the fetch function from the transport options captured by the mock.
        const transportOpts = vi.mocked(DefaultChatTransport).mock.calls[0][0] as {
            fetch: (input: unknown, init: unknown) => Promise<{ headers: { get: (k: string) => string | null } }>;
        };
        expect(typeof transportOpts.fetch).toBe('function');

        // Stub window.fetch to return a response with the X-Conversation-Id header.
        vi.stubGlobal(
            'fetch',
            vi.fn().mockResolvedValue({
                headers: {
                    get: (k: string) =>
                        k === 'X-Conversation-Id' ? 'sess-123' : null,
                },
            }),
        );

        // First call — should capture the id.
        await act(async () => {
            await transportOpts.fetch('/ai/chat', {});
        });

        expect(onNewSessionId).toHaveBeenCalledTimes(1);
        expect(onNewSessionId).toHaveBeenCalledWith('sess-123');
        expect(result.current.sessionId).toBe('sess-123');

        // Second call — guard !sessionIdRef.current prevents a second fire.
        await act(async () => {
            await transportOpts.fetch('/ai/chat', {});
        });

        expect(onNewSessionId).toHaveBeenCalledTimes(1);
    });

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
});
