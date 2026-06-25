// @vitest-environment jsdom
import type { Chat, UIMessage } from '@ai-sdk/react';
import { cleanup, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AiChatPanel } from '../ai-chat-panel';

const mockUseChat = vi.fn();

vi.mock('@ai-sdk/react', () => ({
    useChat: () => mockUseChat(),
}));

mockUseChat.mockReturnValue({
    messages: [],
    sendMessage: vi.fn(),
    status: 'idle',
    stop: vi.fn(),
});

vi.mock('@/components/ui/ai/conversation', () => ({
    Conversation: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    ConversationContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    ConversationEmptyState: ({ title }: { title: string }) => <div>{title}</div>,
    ConversationScrollButton: () => null,
}));

vi.mock('@/components/ui/ai/message', () => ({
    Message: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    MessageContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    MessageResponse: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock('@/components/ui/button', () => ({
    Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { children: React.ReactNode }) => (
        <button {...props}>{children}</button>
    ),
}));

vi.mock('@/components/ui/textarea', () => ({
    Textarea: (props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) => <textarea {...props} />,
}));

vi.mock('@/components/ai/proposal-card', () => ({
    parseProposal: () => ({ proposal_id: 'p1', parts: [{ key: 'k', human_diff: { summary: 's' } }] }),
    ProposalCard: ({ mode }: { mode?: string }) => <div data-testid="pc" data-mode={mode} />,
}));

describe('AiChatPanel', () => {
    afterEach(() => {
        mockUseChat.mockReturnValue({
            messages: [],
            sendMessage: vi.fn(),
            status: 'idle',
            stop: vi.fn(),
        });
        cleanup();
    });

    it('renders the empty state for a global session', () => {
        const mockChat = {} as Chat<UIMessage>;
        render(
            <AiChatPanel chat={mockChat} kind="global" sessionId={null} />,
        );

        expect(
            screen.getByText(/ask anything/i),
        ).toBeInTheDocument();
    });

    it('passes proposalMode through to ProposalCard', () => {
        mockUseChat.mockReturnValue({
            messages: [
                {
                    id: 'm1',
                    role: 'assistant',
                    parts: [{ type: 'dynamic-tool', state: 'output-available', output: {} }],
                },
            ],
            sendMessage: vi.fn(),
            status: 'idle',
            stop: vi.fn(),
        });

        const mockChat = {} as Chat<UIMessage>;
        render(<AiChatPanel chat={mockChat} kind="entity" sessionId={null} proposalMode="create" />);

        expect(screen.getByTestId('pc').getAttribute('data-mode')).toBe('create');
    });
});
