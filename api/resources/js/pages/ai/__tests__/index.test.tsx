// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
    cleanup,
    fireEvent,
    render,
    screen,
    waitFor,
} from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import CreateWithAi from '../index';

vi.mock('@inertiajs/react', () => ({
    Head: () => null,
    Link: ({ children, href }: { children: React.ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
    usePage: () => ({ props: {} }),
}));

vi.mock('@/layouts/app-layout', () => ({
    default: ({ children }: { children: React.ReactNode }) => (
        <div>{children}</div>
    ),
}));

vi.mock('@/components/ai/ai-chat-panel', () => ({
    AiChatPanel: () => <div data-testid="chat-panel" />,
}));

vi.mock('@/hooks/use-session-chat', () => ({
    useSessionChat: () => ({
        chat: {},
        sessionId: null,
        setSessionId: vi.fn(),
    }),
}));

let fetchMock: ReturnType<typeof vi.fn>;

beforeAll(() => {
    fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ data: [] }),
    } as unknown as Response);
    globalThis.fetch = fetchMock as unknown as typeof fetch;
});

afterEach(() => {
    cleanup();
    fetchMock.mockReset();
    fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({ data: [] }),
    } as unknown as Response);
});

function renderPage() {
    const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
    });

    return render(
        <QueryClientProvider client={queryClient}>
            <CreateWithAi />
        </QueryClientProvider>,
    );
}

describe('Create with AI page', () => {
    it('renders the chat panel and a new session button', async () => {
        renderPage();

        await waitFor(() => {
            expect(screen.getByTestId('chat-panel')).toBeInTheDocument();
        });

        expect(
            screen.getByRole('button', { name: /new session/i }),
        ).toBeInTheDocument();
    });

    it('shows session list items when sessions are returned', async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                data: [
                    {
                        id: 'sess-1',
                        kind: 'entity',
                        context_label: 'Entity: Rome',
                        title: 'Edit Rome',
                        updated_at: '2026-06-25T10:00:00Z',
                    },
                ],
            }),
        } as unknown as Response);

        renderPage();

        await waitFor(() => {
            expect(screen.getByText('Edit Rome')).toBeInTheDocument();
        });

        expect(screen.getByText('Entity: Rome')).toBeInTheDocument();
    });

    it('deletes a session and refetches the list', async () => {
        fetchMock
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    data: [
                        {
                            id: 'sess-x',
                            kind: 'global',
                            context_id: null,
                            context_label: 'Global',
                            title: 'Chat X',
                            updated_at: null,
                        },
                    ],
                }),
            } as unknown as Response)
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({ deleted: true }),
            } as unknown as Response)
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({ data: [] }),
            } as unknown as Response);

        renderPage();
        await waitFor(() =>
            expect(screen.getByText('Chat X')).toBeInTheDocument(),
        );

        fireEvent.click(
            screen.getByRole('button', { name: /delete session/i }),
        );

        await waitFor(() =>
            expect(fetchMock).toHaveBeenCalledWith(
                '/ai/sessions/sess-x',
                expect.objectContaining({ method: 'DELETE' }),
            ),
        );
    });

    it('shows a kind badge for each session', async () => {
        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                data: [
                    {
                        id: 'sess-1',
                        kind: 'entity',
                        context_id: 'ent-1',
                        context_label: 'Entity: Rome',
                        title: 'Edit Rome',
                        updated_at: null,
                    },
                ],
            }),
        } as unknown as Response);

        renderPage();

        await waitFor(() =>
            expect(screen.getByText('Edit Rome')).toBeInTheDocument(),
        );
        expect(screen.getByText('Entity')).toBeInTheDocument(); // kind badge
    });

    it('fetches and rebinds when a scoped session is selected', async () => {
        // First call: session list; second call: the show() payload.
        fetchMock
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    data: [
                        {
                            id: 'sess-e',
                            kind: 'entity',
                            context_id: 'ent-1',
                            context_label: 'Entity: Rome',
                            title: 'Edit Rome',
                            updated_at: null,
                        },
                    ],
                }),
            } as unknown as Response)
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    session: {
                        id: 'sess-e',
                        kind: 'entity',
                        context_id: 'ent-1',
                        context_label: 'Entity: Rome',
                        title: 'Edit Rome',
                    },
                    messages: [
                        {
                            id: 'm1',
                            role: 'user',
                            content: 'hi',
                            tool_results: [],
                            created_at: null,
                        },
                    ],
                    proposals: [],
                }),
            } as unknown as Response);

        renderPage();

        await waitFor(() =>
            expect(screen.getByText('Edit Rome')).toBeInTheDocument(),
        );

        fireEvent.click(screen.getByText('Edit Rome'));

        await waitFor(() =>
            expect(fetchMock).toHaveBeenCalledWith(
                '/ai/sessions/sess-e',
                expect.anything(),
            ),
        );
    });
});
