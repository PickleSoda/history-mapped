import { Chat } from '@ai-sdk/react';
import { useChat } from '@ai-sdk/react';
import { DefaultChatTransport } from 'ai';
import { BotMessageSquare, SendHorizonal, Square, X } from 'lucide-react';
import { useMemo, useRef, useState } from 'react';
import { useAiPanel } from '@/components/ai/ai-panel-context';
import { parseProposal, ProposalCard } from '@/components/ai/proposal-card';
import {
    Conversation,
    ConversationContent,
    ConversationEmptyState,
    ConversationScrollButton,
} from '@/components/ui/ai/conversation';
import {
    Message,
    MessageContent,
    MessageResponse,
} from '@/components/ui/ai/message';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { useAiContext } from '@/hooks/use-ai-context';
import { cn } from '@/lib/utils';

// ── Helpers ───────────────────────────────────────────────────────────────────

function getCsrfToken(): string {
    return (
        document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')
            ?.content ?? ''
    );
}

// ── Component ─────────────────────────────────────────────────────────────────

/**
 * AI chat sidebar for the admin.
 *
 * Opened by a "Ask AI" button in AppSidebar (shared open-state via useAiPanel).
 * Docks on the RIGHT as a non-modal panel — the main content is pushed left
 * (see AppContent) rather than covered, so the operator keeps working while
 * chatting. Uses `@ai-sdk/react` v3 Chat + useChat. Context (entity/chronicle
 * type + id) from `useAiContext()` is injected as extra body fields on every
 * request via `DefaultChatTransport`. The CSRF token is sent as a request header.
 *
 * When the assistant calls a staging tool, the tool output is parsed as a
 * Proposal and rendered as a <ProposalCard> with Apply/Discard buttons.
 */
export function AiSidebar() {
    const { open, setOpen } = useAiPanel();
    const aiCtx = useAiContext();
    const [input, setInput] = useState('');
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // Memoize the Chat instance so it is stable across re-renders (e.g. input
    // state changes). Only recreate it when the bound record changes so the
    // transport always has fresh context_type / context_id — and so conversation
    // history is reset when the user navigates to a different record.
    const chat = useMemo(
        () =>
            new Chat({
                transport: new DefaultChatTransport({
                    api: '/ai/chat',
                    headers: () => ({
                        'X-CSRF-TOKEN': getCsrfToken(),
                        'X-Requested-With': 'XMLHttpRequest',
                    }),
                    body: aiCtx
                        ? { context_type: aiCtx.type, context_id: aiCtx.id, mode: aiCtx.mode }
                        : {},
                }),
            }),
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [aiCtx?.type, aiCtx?.id, aiCtx?.mode],
    );

    const { messages, sendMessage, status, stop } = useChat({ chat });

    const isStreaming = status === 'streaming' || status === 'submitted';
    const canSend = !isStreaming && !!aiCtx && input.trim().length > 0;

    function handleSubmit() {
        if (!canSend) {
            return;
        }

        const text = input.trim();
        setInput('');
        void sendMessage({ text });
        // Restore focus to the textarea so the user can type a follow-up
        // immediately without clicking.
        setTimeout(() => textareaRef.current?.focus(), 0);
    }

    function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
        }
    }

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
                {/* Header */}
                <div className="flex items-center gap-2 border-b px-4 py-3 text-sm font-semibold">
                    <BotMessageSquare className="size-4 text-primary" />
                    Ask AI
                    {aiCtx && (
                        <span className="ml-auto text-xs font-normal text-muted-foreground capitalize">
                            {aiCtx.type}{aiCtx.id !== null ? ` #${aiCtx.id}` : ' (new)'}
                        </span>
                    )}
                    <Button
                        variant="ghost"
                        size="icon"
                        className={cn('size-7', aiCtx ? 'ml-2' : 'ml-auto')}
                        onClick={() => setOpen(false)}
                        title="Close"
                    >
                        <X className="size-4" />
                    </Button>
                </div>

                {/* Message list */}
                <Conversation className="flex-1">
                    <ConversationContent>
                        {messages.length === 0 && (
                            <ConversationEmptyState
                                icon={
                                    <BotMessageSquare className="size-8 text-muted-foreground" />
                                }
                                title={
                                    aiCtx
                                        ? 'Ask anything about this record'
                                        : 'No context available'
                                }
                                description={
                                    aiCtx
                                        ? 'The assistant can read and update this entity or chronicle.'
                                        : 'Navigate to an entity or chronicle page to use the AI assistant.'
                                }
                            />
                        )}

                        {messages.map((m) => (
                            <Message key={m.id} from={m.role}>
                                <MessageContent>
                                    {m.parts.map((part, idx) => {
                                        // Text parts → streaming markdown
                                        if (part.type === 'text') {
                                            return (
                                                <MessageResponse
                                                    key={idx}
                                                    isAnimating={isStreaming}
                                                >
                                                    {part.text}
                                                </MessageResponse>
                                            );
                                        }

                                        // Dynamic tool parts (staging tools)
                                        if (
                                            part.type === 'dynamic-tool' &&
                                            part.state === 'output-available'
                                        ) {
                                            const proposal = parseProposal(
                                                part.output,
                                            );

                                            if (proposal) {
                                                return (
                                                    <ProposalCard
                                                        key={idx}
                                                        proposal={proposal}
                                                        mode={aiCtx?.mode ?? 'edit'}
                                                    />
                                                );
                                            }
                                        }

                                        // Static tool parts — type is `tool-${name}`, e.g. `tool-set_entity_location`
                                        if (
                                            part.type.startsWith('tool-') &&
                                            'state' in part &&
                                            part.state === 'output-available' &&
                                            'output' in part
                                        ) {
                                            const proposal = parseProposal(
                                                (
                                                    part as {
                                                        output: unknown;
                                                    }
                                                ).output,
                                            );

                                            if (proposal) {
                                                return (
                                                    <ProposalCard
                                                        key={idx}
                                                        proposal={proposal}
                                                        mode={aiCtx?.mode ?? 'edit'}
                                                    />
                                                );
                                            }
                                        }

                                        return null;
                                    })}
                                </MessageContent>
                            </Message>
                        ))}
                    </ConversationContent>
                    <ConversationScrollButton />
                </Conversation>

                {/* Input area */}
                <div className="border-t p-3">
                    {!aiCtx && (
                        <p className="mb-2 text-center text-xs text-muted-foreground">
                            Open an entity or chronicle to enable AI assistance.
                        </p>
                    )}
                    <div className="flex items-end gap-2">
                        <Textarea
                            ref={textareaRef}
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder={
                                aiCtx
                                    ? 'Ask a question or request a change… (Enter to send, Shift+Enter for newline)'
                                    : 'No context — navigate to an entity page first'
                            }
                            disabled={!aiCtx}
                            rows={2}
                            className="min-h-0 flex-1 resize-none text-sm"
                        />
                        {isStreaming ? (
                            <Button
                                size="icon"
                                variant="outline"
                                onClick={stop}
                                title="Stop"
                                className="shrink-0"
                            >
                                <Square className="size-4" />
                            </Button>
                        ) : (
                            <Button
                                size="icon"
                                onClick={handleSubmit}
                                disabled={!canSend}
                                title="Send"
                                className="shrink-0"
                            >
                                <SendHorizonal className="size-4" />
                            </Button>
                        )}
                    </div>
                </div>
            </div>
        </aside>
    );
}
