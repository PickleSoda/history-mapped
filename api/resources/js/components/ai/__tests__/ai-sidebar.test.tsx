// @vitest-environment jsdom
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';

const startNewChat = vi.fn();
vi.mock('@/hooks/use-scoped-session-chat', () => ({
    useScopedSessionChat: () => ({
        chat: {},
        sessionId: 's1',
        resolved: true,
        startNewChat,
    }),
}));
vi.mock('@/components/ai/ai-chat-panel', () => ({
    AiChatPanel: ({ proposalMode }: { proposalMode?: string }) => (
        <div data-testid="panel" data-proposalmode={proposalMode} />
    ),
}));
vi.mock('@/components/ai/ai-panel-context', () => ({
    useAiPanel: () => ({ open: true, setOpen: vi.fn() }),
}));
const mockCtx = vi.fn();
vi.mock('@/hooks/use-ai-context', () => ({ useAiContext: () => mockCtx() }));

import { AiSidebar } from '../ai-sidebar';

describe('AiSidebar', () => {
    afterEach(() => {
        cleanup();
    });

    it('renders the scoped chat panel + New chat + scoped badge for a record', () => {
        mockCtx.mockReturnValue({ type: 'entity', id: 'e1', mode: 'edit' });
        render(<AiSidebar />);

        expect(screen.getByTestId('panel')).toBeInTheDocument();
        expect(
            screen.getByTestId('panel').getAttribute('data-proposalmode'),
        ).toBe('edit');
        expect(
            screen.getByRole('button', { name: /new chat/i }),
        ).toBeInTheDocument();
        expect(screen.getByText(/entity/i)).toBeInTheDocument(); // scoped badge

        fireEvent.click(screen.getByRole('button', { name: /new chat/i }));
        expect(startNewChat).toHaveBeenCalled();
    });

    it('shows the empty state with no record context', () => {
        mockCtx.mockReturnValue(null);
        render(<AiSidebar />);

        expect(screen.queryByTestId('panel')).not.toBeInTheDocument();
        expect(
            screen.getByText(/navigate to an entity or chronicle/i),
        ).toBeInTheDocument();
    });
});
