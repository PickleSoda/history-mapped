import { BotMessageSquare, Plus, X } from 'lucide-react';
import { AiChatPanel } from '@/components/ai/ai-chat-panel';
import { useAiPanel } from '@/components/ai/ai-panel-context';
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
                // Mobile: fixed off-canvas overlay (works well on small screens).
                'fixed inset-y-0 right-0 w-110 max-w-full shadow-lg transition-transform duration-200 ease-in-out',
                open ? 'translate-x-0' : 'pointer-events-none translate-x-full',
                // Desktop (md+): in-flow column, but viewport-tall + sticky so it
                // pins to the screen with its own scroll like the left sidebar
                // (self-start stops it stretching to content height), while its
                // width collapses to squish the main content.
                'md:sticky md:top-0 md:h-svh md:max-w-none md:shrink-0 md:translate-x-0 md:self-start md:overflow-hidden md:shadow-none md:transition-[width] md:duration-200',
                open ? 'md:w-110' : 'md:pointer-events-none md:w-0',
            )}
        >
            {/* Inner keeps a fixed width so content doesn't reflow while the panel
                animates its width open/closed on desktop. */}
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
