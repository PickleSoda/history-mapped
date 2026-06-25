import { Chat } from '@ai-sdk/react';
import { DefaultChatTransport } from 'ai';
import type { UIMessage } from 'ai';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

function getCsrfToken(): string {
    return (
        document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')
            ?.content ?? ''
    );
}

type UseSessionChatOptions = {
    /** Ongoing session id (null = new session, id is set after first response). */
    sessionId: string | null;
    kind: 'global' | 'entity' | 'chronicle';
    /** Required for entity/chronicle kinds. */
    contextType?: string;
    /** Nullable for global / create-mode sessions. */
    contextId?: string | null;
    /** Drives create vs edit routing on the server; omitted ⇒ server default (edit). */
    mode?: 'edit' | 'create';
    /** Called when the first response returns a new X-Conversation-Id header. */
    onNewSessionId?: (id: string) => void;
    /** Bump to force a fresh Chat instance (e.g. "New session" button). */
    resetNonce?: number;
    /** Messages to seed the Chat with (supply before bumping resetNonce). */
    initialMessages?: UIMessage[];
};

export function useSessionChat({
    sessionId,
    kind,
    contextType,
    contextId,
    mode,
    onNewSessionId,
    resetNonce = 0,
    initialMessages,
}: UseSessionChatOptions) {
    const [currentSessionId, setCurrentSessionId] = useState<string | null>(
        sessionId,
    );

    // Keep a ref so the body function closure always reads the latest session id
    // without needing to recreate the Chat instance.
    const sessionIdRef = useRef<string | null>(currentSessionId);
    sessionIdRef.current = currentSessionId;

    const onNewSessionIdRef = useRef(onNewSessionId);
    onNewSessionIdRef.current = onNewSessionId;

    // Sync the internal session id when the parent changes the prop (resume → an id,
    // New chat → null). Without this, currentSessionId is frozen at its mount value.
    useEffect(() => {
        sessionIdRef.current = sessionId;
        setCurrentSessionId(sessionId);
    }, [sessionId]);

    // The Chat instance is stable for the lifetime of this session (kind + context
    // do not change mid-session). It is only recreated if the page mounts a
    // fundamentally different session type — which triggers a React remount anyway.
    const chat = useMemo(
        () =>
            new Chat({
                messages: initialMessages ?? [],
                transport: new DefaultChatTransport({
                    api: '/ai/chat',
                    headers: () => ({
                        'X-CSRF-TOKEN': getCsrfToken(),
                        'X-Requested-With': 'XMLHttpRequest',
                    }),
                    // body is a FUNCTION so session_id is read from the ref on
                    // every send (stale-closure-safe).
                    body: () => ({
                        kind,
                        conversation_id: sessionIdRef.current,
                        ...(mode ? { mode } : {}),
                        ...(kind !== 'global' && contextType
                            ? { context_type: contextType, context_id: contextId ?? null }
                            : {}),
                    }),
                    // Intercept responses to capture X-Conversation-Id from the
                    // first turn (DefaultChatTransport has no onResponse hook; the
                    // `fetch` override is the only available interception point).
                    fetch: async (input, init) => {
                        const res = await window.fetch(input, init);
                        const newId = res.headers.get('X-Conversation-Id');

                        if (newId && !sessionIdRef.current) {
                            sessionIdRef.current = newId;
                            setCurrentSessionId(newId);
                            onNewSessionIdRef.current?.(newId);
                        }

                        return res;
                    },
                }),
            }),
        // Recreate when the session identity changes OR resetNonce bumps (New session).
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [kind, contextType, contextId, mode, resetNonce],
    );

    const setSessionId = useCallback((id: string) => {
        sessionIdRef.current = id;
        setCurrentSessionId(id);
    }, []);

    return { chat, sessionId: currentSessionId, setSessionId };
}
