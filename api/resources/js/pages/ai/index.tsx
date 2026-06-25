import { Head, Link } from '@inertiajs/react';
import { useQuery } from '@tanstack/react-query';
import type { UIMessage } from 'ai';
import { Plus, Trash2 } from 'lucide-react';
import { useCallback, useState } from 'react';
import { AiChatPanel } from '@/components/ai/ai-chat-panel';
import type { CreatedRef } from '@/components/ai/proposal-card';
import { Button } from '@/components/ui/button';
import { useSessionChat } from '@/hooks/use-session-chat';
import AppLayout from '@/layouts/app-layout';
import { reconstructSessionMessages } from '@/lib/reconstruct-session-messages';
import { cn } from '@/lib/utils';
import type { BreadcrumbItem } from '@/types';

function getCsrfToken(): string {
    return document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content ?? '';
}

const breadcrumbs: BreadcrumbItem[] = [
    { title: 'Dashboard', href: '/dashboard' },
    { title: 'Create with AI', href: '/ai' },
];

type Session = {
    id: string;
    kind: string | null;
    context_id: string | null;
    context_label: string;
    title: string;
    updated_at: string | null;
};

type SessionsResponse = { data: Session[] };

export default function CreateWithAi() {
    // The id of the session open in the right pane. null = blank new session.
    const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
    // Incremented when "New session" is clicked — passed as resetNonce to
    // useSessionChat so the Chat instance and captured session id are reset,
    // and as key on AiChatPanel so the useChat view is remounted.
    const [chatKey, setChatKey] = useState(0);
    // Created-record links to display above the chat.
    const [createdRefs, setCreatedRefs] = useState<CreatedRef[]>([]);
    // Active session scope — drives useSessionChat's kind/context binding.
    const [activeKind, setActiveKind] = useState<'global' | 'entity' | 'chronicle'>('global');
    const [activeContextType, setActiveContextType] = useState<string | undefined>(undefined);
    const [activeContextId, setActiveContextId] = useState<string | null>(null);
    const [initialMessages, setInitialMessages] = useState<UIMessage[]>([]);

    const {
        data: sessionsData,
        refetch: refetchSessions,
    } = useQuery<SessionsResponse>({
        queryKey: ['ai-sessions'],
        queryFn: async () => {
            const res = await fetch('/ai/sessions', {
                headers: { Accept: 'application/json' },
            });

            if (!res.ok) {
                throw new Error('Failed to load sessions');
            }

            return res.json() as Promise<SessionsResponse>;
        },
    });

    const sessions = sessionsData?.data ?? [];

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

    function handleNewSession() {
        setActiveKind('global');
        setActiveContextType(undefined);
        setActiveContextId(null);
        setInitialMessages([]);
        setActiveSessionId(null);
        setCreatedRefs([]);
        setChatKey((k) => k + 1);
    }

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

    function handleCreatedRef(ref: CreatedRef) {
        setCreatedRefs((prev) => [...prev, ref]);
        void refetchSessions();
    }

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

    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title="Create with AI" />

            <div className="flex h-[calc(100svh-4rem)] gap-0">
                {/* ── Left: session list ────────────────────────────────── */}
                <aside className="flex w-64 shrink-0 flex-col border-r">
                    <div className="flex items-center justify-between border-b px-4 py-3">
                        <span className="text-sm font-semibold">Sessions</span>
                        <Button
                            size="sm"
                            variant="outline"
                            className="gap-1"
                            onClick={handleNewSession}
                        >
                            <Plus className="size-3.5" />
                            New session
                        </Button>
                    </div>

                    <ul className="flex-1 overflow-y-auto py-1">
                        {sessions.length === 0 && (
                            <li className="px-4 py-8 text-center text-xs text-muted-foreground">
                                No sessions yet. Start a conversation.
                            </li>
                        )}
                        {sessions.map((s) => (
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
                        ))}
                    </ul>
                </aside>

                {/* ── Right: chat panel ─────────────────────────────────── */}
                <div className="flex min-w-0 flex-1 flex-col">
                    {/* Created-record chips */}
                    {createdRefs.length > 0 && (
                        <div className="flex flex-wrap gap-2 border-b px-4 py-2">
                            {createdRefs.map((ref) => (
                                <Link
                                    key={ref.id}
                                    href={ref.url}
                                    className="inline-flex items-center gap-1 rounded-full border border-green-300 bg-green-50 px-3 py-1 text-xs font-medium text-green-800 hover:bg-green-100 dark:border-green-700 dark:bg-green-950/30 dark:text-green-300"
                                >
                                    <span className="capitalize">{ref.type}:</span>
                                    {ref.label}
                                    <span className="ml-1 opacity-60">→</span>
                                </Link>
                            ))}
                        </div>
                    )}

                    <AiChatPanel
                        key={chatKey}
                        chat={chat}
                        kind={activeKind}
                        sessionId={activeSessionId}
                        onCreatedRef={handleCreatedRef}
                        className="flex-1"
                    />
                </div>
            </div>
        </AppLayout>
    );
}
