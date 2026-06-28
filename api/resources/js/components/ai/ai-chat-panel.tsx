import { useChat } from '@ai-sdk/react';
import type { Chat, UIMessage } from '@ai-sdk/react';
import { SendHorizonal, Square } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { parseProposal, ProposalCard } from '@/components/ai/proposal-card';
import type { CreatedRef } from '@/components/ai/proposal-card';
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
import { cn } from '@/lib/utils';

type Props = {
    chat: Chat<UIMessage>;
    kind: 'global' | 'entity' | 'chronicle';
    sessionId: string | null;
    onCreatedRef?: (ref: CreatedRef) => void;
    proposalMode?: 'edit' | 'create';
    className?: string;
};

/**
 * Reusable chat panel: message list + input.
 *
 * Used both by AiSidebar (wrapped in a docked aside) and the Create with AI
 * page (rendered as a full-height column). Does NOT include the sidebar wrapper,
 * header, or close button — those are concerns of the parent.
 */
export function AiChatPanel({
    chat,
    kind,
    sessionId: _sessionId,
    onCreatedRef,
    proposalMode = 'edit',
    className,
}: Props) {
    const { messages, sendMessage, status, stop, error } = useChat({ chat });
    const [input, setInput] = useState('');
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const isStreaming = status === 'streaming' || status === 'submitted';
    const canSend = !isStreaming && input.trim().length > 0;
    // Show a typing indicator after the request is sent but before the first
    // token streams back (status 'submitted').
    const isAwaitingResponse = status === 'submitted';

    // Surface request failures: log to the console for diagnostics and show a
    // banner (see below). useChat exposes the last error on `error`.
    useEffect(() => {
        if (error) {
            console.error('[AI chat] request failed:', error);
        }
    }, [error]);

    function handleSubmit() {
        if (!canSend) {
            return;
        }

        const text = input.trim();
        setInput('');
        void sendMessage({ text });
        setTimeout(() => textareaRef.current?.focus(), 0);
    }

    function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
        }
    }

    const emptyTitle =
        kind === 'global'
            ? 'Ask anything — create or edit any record'
            : 'Ask anything about this record';

    const emptyDescription =
        kind === 'global'
            ? 'The assistant can create entities, chronicles, and relationships. Changes are proposed for your review before anything is saved.'
            : 'The assistant can read and update this entity or chronicle.';

    return (
        <div className={cn('flex flex-col', className)}>
            <Conversation className="flex-1 overflow-y-auto">
                <ConversationContent>
                    {messages.length === 0 && (
                        <ConversationEmptyState
                            title={emptyTitle}
                            description={emptyDescription}
                        />
                    )}

                    {messages.map((m) => (
                        <Message key={m.id} from={m.role}>
                            <MessageContent>
                                {m.parts.map((part, idx) => {
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
                                                    mode={proposalMode}
                                                    onCreatedRef={onCreatedRef}
                                                />
                                            );
                                        }
                                    }

                                    if (
                                        part.type.startsWith('tool-') &&
                                        'state' in part &&
                                        part.state === 'output-available' &&
                                        'output' in part
                                    ) {
                                        const proposal = parseProposal(
                                            (part as { output: unknown })
                                                .output,
                                        );

                                        if (proposal) {
                                            return (
                                                <ProposalCard
                                                    key={idx}
                                                    proposal={proposal}
                                                    mode={proposalMode}
                                                    onCreatedRef={onCreatedRef}
                                                />
                                            );
                                        }
                                    }

                                    return null;
                                })}
                            </MessageContent>
                        </Message>
                    ))}

                    {isAwaitingResponse && (
                        <Message from="assistant">
                            <MessageContent>
                                <TypingIndicator />
                            </MessageContent>
                        </Message>
                    )}
                </ConversationContent>
                <ConversationScrollButton />
            </Conversation>

            {error && (
                <div
                    role="alert"
                    className="mx-3 mb-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive"
                >
                    The assistant hit an error. Please try again.
                </div>
            )}

            <div className="border-t p-3">
                <div className="flex items-end gap-2">
                    <Textarea
                        ref={textareaRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Ask a question or request a change… (Enter to send, Shift+Enter for newline)"
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
    );
}

/**
 * Three bouncing dots shown while awaiting the assistant's first token.
 * role="status" + aria-label make it announced to screen readers.
 */
function TypingIndicator() {
    return (
        <span
            role="status"
            aria-label="Assistant is typing"
            className="inline-flex items-center gap-1 px-1 py-2 text-muted-foreground"
        >
            <span className="size-1.5 animate-bounce rounded-full bg-current opacity-60 [animation-delay:-0.3s]" />
            <span className="size-1.5 animate-bounce rounded-full bg-current opacity-60 [animation-delay:-0.15s]" />
            <span className="size-1.5 animate-bounce rounded-full bg-current opacity-60" />
        </span>
    );
}
