// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { DefaultChatTransport } from 'ai';
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
