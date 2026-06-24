// @vitest-environment jsdom
import type { Chat, UIMessage } from '@ai-sdk/react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { describe, expect, it, vi } from 'vitest';
import { AiChatPanel } from '../ai-chat-panel';

vi.mock('@ai-sdk/react', () => ({
    useChat: () => ({
        messages: [],
        sendMessage: vi.fn(),
        status: 'idle',
        stop: vi.fn(),
    }),
}));

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

describe('AiChatPanel', () => {
    it('renders the empty state for a global session', () => {
        const mockChat = {} as Chat<UIMessage>;
        render(
            <AiChatPanel chat={mockChat} kind="global" sessionId={null} />,
        );

        expect(
            screen.getByText(/ask anything/i),
        ).toBeInTheDocument();
    });
});
