// @vitest-environment jsdom
import {
    cleanup,
    fireEvent,
    render,
    screen,
    waitFor,
} from '@testing-library/react';
import {
    afterAll,
    afterEach,
    beforeAll,
    describe,
    expect,
    it,
    vi,
} from 'vitest';
import '@testing-library/jest-dom/vitest';

import { ProposalCard } from '@/components/ai/proposal-card';
import type { Proposal } from '@/components/ai/proposal-card';

// ── Mock Inertia router.reload ────────────────────────────────────────────────

vi.mock('@inertiajs/react', () => ({
    router: { reload: vi.fn(), visit: vi.fn() },
}));

vi.mock('@/lib/ai-events', () => ({ emitAiApplied: vi.fn() }));

// ── Fetch mock ────────────────────────────────────────────────────────────────

let fetchMock: ReturnType<typeof vi.fn>;

beforeAll(() => {
    fetchMock = vi.fn();
    global.fetch = fetchMock as unknown as typeof fetch;

    const meta = document.createElement('meta');
    meta.setAttribute('name', 'csrf-token');
    meta.setAttribute('content', 'test-csrf');
    document.head.appendChild(meta);
});

afterAll(() => {
    fetchMock.mockRestore();
});

afterEach(async () => {
    fetchMock.mockReset();
    const { router } = await import('@inertiajs/react');
    vi.mocked(router.reload).mockClear();
    vi.mocked(router.visit).mockClear();
    const { emitAiApplied } = await import('@/lib/ai-events');
    vi.mocked(emitAiApplied).mockClear();
    cleanup();
});

// ── Fixtures ──────────────────────────────────────────────────────────────────

const proposal: Proposal = {
    proposal_id: 'prop-123',
    parts: [
        {
            key: 'location',
            human_diff: { summary: 'Set location to Luxor, Egypt' },
        },
        {
            key: 'name',
            human_diff: { summary: 'Rename to "Thebes (Ancient City)"' },
        },
    ],
    note: 'AI-suggested correction',
};

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('ProposalCard', () => {
    it('renders all part summaries and action buttons', () => {
        render(<ProposalCard proposal={proposal} />);

        expect(
            screen.getByText('Set location to Luxor, Egypt'),
        ).toBeInTheDocument();

        expect(
            screen.getByText('Rename to "Thebes (Ancient City)"'),
        ).toBeInTheDocument();

        // Each part should have Apply and Discard buttons
        const applyButtons = screen.getAllByRole('button', { name: /apply/i });
        const discardButtons = screen.getAllByRole('button', {
            name: /discard/i,
        });

        expect(applyButtons).toHaveLength(2);
        expect(discardButtons).toHaveLength(2);
    });

    it('shows the proposal note', () => {
        render(<ProposalCard proposal={proposal} />);

        expect(screen.getByText(/AI-suggested correction/)).toBeInTheDocument();
    });

    it('calls /apply endpoint and shows Applied status on success', async () => {
        const { router } = await import('@inertiajs/react');

        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ status: 'applied' }),
        } as Response);

        render(<ProposalCard proposal={proposal} />);

        const applyButtons = screen.getAllByRole('button', { name: /apply/i });
        fireEvent.click(applyButtons[0]);

        // Shows loading state briefly then applied
        await waitFor(() => {
            expect(screen.getByText('Applied')).toBeInTheDocument();
        });

        // Verify fetch was called with the right URL
        expect(fetchMock).toHaveBeenCalledWith(
            `/ai/proposals/prop-123/parts/location/apply`,
            expect.objectContaining({
                method: 'POST',
                headers: expect.objectContaining({
                    'X-CSRF-TOKEN': 'test-csrf',
                }),
            }),
        );

        // router.reload() should be called after apply
        expect(router.reload).toHaveBeenCalled();
    });

    it('calls /discard endpoint and shows Discarded status', async () => {
        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ status: 'discarded' }),
        } as Response);

        render(<ProposalCard proposal={proposal} />);

        const discardButtons = screen.getAllByRole('button', {
            name: /discard/i,
        });
        fireEvent.click(discardButtons[0]);

        await waitFor(() => {
            expect(screen.getByText('Discarded')).toBeInTheDocument();
        });

        expect(fetchMock).toHaveBeenCalledWith(
            `/ai/proposals/prop-123/parts/location/discard`,
            expect.objectContaining({ method: 'POST' }),
        );
    });

    it('shows error state on network failure', async () => {
        fetchMock.mockRejectedValueOnce(new Error('Network error'));

        render(<ProposalCard proposal={proposal} />);

        const applyButtons = screen.getAllByRole('button', { name: /apply/i });
        fireEvent.click(applyButtons[0]);

        await waitFor(() => {
            expect(screen.getByText(/Error/)).toBeInTheDocument();
        });
    });

    it('shows error state on non-ok HTTP response', async () => {
        fetchMock.mockResolvedValueOnce({
            ok: false,
            status: 403,
        } as Response);

        render(<ProposalCard proposal={proposal} />);

        const applyButtons = screen.getAllByRole('button', { name: /apply/i });
        fireEvent.click(applyButtons[0]);

        await waitFor(() => {
            expect(screen.getByText(/Error/)).toBeInTheDocument();
        });
    });

    it('calls router.visit with redirect_url in create mode on apply success', async () => {
        const { router } = await import('@inertiajs/react');

        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ status: 'applied', redirect_url: '/entities/99/edit' }),
        } as Response);

        render(<ProposalCard proposal={proposal} mode="create" />);

        const applyButtons = screen.getAllByRole('button', { name: /apply/i });
        fireEvent.click(applyButtons[0]);

        await waitFor(() => {
            expect(screen.getByText('Applied')).toBeInTheDocument();
        });

        expect(router.visit).toHaveBeenCalledWith('/entities/99/edit');
        expect(router.reload).not.toHaveBeenCalled();
    });

    it('calls router.reload (not router.visit) in edit mode on apply success', async () => {
        const { router } = await import('@inertiajs/react');
        vi.mocked(router.reload).mockClear();
        vi.mocked(router.visit).mockClear();

        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ status: 'applied' }),
        } as Response);

        render(<ProposalCard proposal={proposal} mode="edit" />);

        const applyButtons = screen.getAllByRole('button', { name: /apply/i });
        fireEvent.click(applyButtons[0]);

        await waitFor(() => {
            expect(screen.getByText('Applied')).toBeInTheDocument();
        });

        expect(router.reload).toHaveBeenCalled();
        expect(router.visit).not.toHaveBeenCalled();
    });

    it('calls onCreatedRef when apply returns created_ref (no navigation)', async () => {
        const { router } = await import('@inertiajs/react');
        const onCreatedRef = vi.fn();

        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                status: 'applied',
                result_id: 'entity-uuid',
                redirect_url: null,
                created_ref: {
                    type: 'entity',
                    id: 'entity-uuid',
                    url: '/entities/entity-uuid/edit',
                    label: 'Rome',
                },
            }),
        } as Response);

        render(
            <ProposalCard
                proposal={proposal}
                mode="edit"
                onCreatedRef={onCreatedRef}
            />,
        );

        const applyButtons = screen.getAllByRole('button', { name: /apply/i });
        fireEvent.click(applyButtons[0]);

        await waitFor(() => {
            expect(onCreatedRef).toHaveBeenCalledWith({
                type: 'entity',
                id: 'entity-uuid',
                url: '/entities/entity-uuid/edit',
                label: 'Rome',
            });
        });
        expect(router.visit).not.toHaveBeenCalled();
        expect(router.reload).not.toHaveBeenCalled();
    });

    it('calls router.reload + emitAiApplied when no created_ref and no redirect_url', async () => {
        const { router } = await import('@inertiajs/react');
        const { emitAiApplied } = await import('@/lib/ai-events');

        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                status: 'applied',
                result_id: 'x',
                redirect_url: null,
                created_ref: null,
            }),
        } as Response);

        render(<ProposalCard proposal={proposal} mode="edit" />);

        const applyButtons = screen.getAllByRole('button', { name: /apply/i });
        fireEvent.click(applyButtons[0]);

        await waitFor(() => {
            expect(router.reload).toHaveBeenCalled();
            expect(emitAiApplied).toHaveBeenCalled();
        });
        expect(router.visit).not.toHaveBeenCalled();
    });

    it('calls router.visit with redirect_url when created_ref absent in create mode', async () => {
        const { router } = await import('@inertiajs/react');

        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                status: 'applied',
                result_id: 'x',
                redirect_url: '/entities/x/edit',
                created_ref: null,
            }),
        } as Response);

        render(<ProposalCard proposal={proposal} mode="create" />);

        const applyButtons = screen.getAllByRole('button', { name: /apply/i });
        fireEvent.click(applyButtons[0]);

        await waitFor(() => {
            expect(router.visit).toHaveBeenCalledWith('/entities/x/edit');
        });
        expect(router.reload).not.toHaveBeenCalled();
    });

    it('double-click on Apply only calls fetch once (concurrent guard)', async () => {
        // Resolve after a small delay to simulate an in-flight request so the
        // second click hits while status is already 'loading'.
        let resolveFirst!: (v: unknown) => void;
        const firstPromise = new Promise((res) => {
            resolveFirst = res;
        });

        fetchMock.mockReturnValueOnce(firstPromise);

        render(<ProposalCard proposal={proposal} />);

        const applyButtons = screen.getAllByRole('button', { name: /apply/i });

        // First click — triggers the request (status → loading).
        fireEvent.click(applyButtons[0]);
        // Second click immediately after — should be a no-op.
        fireEvent.click(applyButtons[0]);

        // Resolve the first (and only) in-flight request.
        resolveFirst({ ok: true, json: async () => ({ status: 'applied' }) });

        await waitFor(() => {
            expect(screen.getByText('Applied')).toBeInTheDocument();
        });

        // fetch must have been called exactly once.
        expect(fetchMock).toHaveBeenCalledTimes(1);
    });
});
