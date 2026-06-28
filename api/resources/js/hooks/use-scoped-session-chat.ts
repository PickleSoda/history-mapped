import type { Chat, UIMessage } from '@ai-sdk/react';
import { useCallback, useEffect, useState } from 'react';

import { useSessionChat } from '@/hooks/use-session-chat';
import { reconstructSessionMessages } from '@/lib/reconstruct-session-messages';

type Args = {
    type: 'entity' | 'chronicle';
    id: string | null;
    mode: 'edit' | 'create';
};

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

        // eslint-disable-next-line react-hooks/set-state-in-effect
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
                const latest = listRes.ok
                    ? (await listRes.json()).data?.[0]
                    : undefined;

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

                seed(
                    reconstructSessionMessages(await showRes.json()),
                    latest.id,
                );
            } catch {
                seed([], null); // open empty on any failure rather than break
            }
        }

        void resume();

        return () => {
            cancelled = true;
        };
    }, [type, id, mode]);

    const startNewChat = useCallback(() => {
        setSeedMessages([]);
        setSeedSessionId(null);
        setResetNonce((n) => n + 1);
        setResolved(true);
    }, []);

    return { chat, sessionId, resolved, startNewChat };
}
