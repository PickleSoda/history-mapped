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
import { afterEach, describe, expect, it, vi } from 'vitest';
import Dashboard from '../dashboard';

const YEAR_STORAGE_KEY = 'historical-dashboard:selected-year';

const dashboardMapMock = vi.fn(
    ({
        year,
        onSelect,
        onCountChange,
    }: {
        year: number;
        onSelect: (id: string | null) => void;
        onCountChange?: (n: number) => void;
    }) => (
        <>
            <button
                type="button"
                data-testid="mock-select-button"
                onClick={() => onSelect('entity-1')}
            >
                select entity
            </button>
            <button
                type="button"
                data-testid="mock-count-button"
                onClick={() => onCountChange?.(7)}
            >
                report count
            </button>
            <div data-testid="mock-dashboard-map" data-year={String(year)} />
        </>
    ),
);

vi.mock('@inertiajs/react', () => ({
    Head: () => null,
    Link: ({ children, href }: { children: React.ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
}));

vi.mock('@/components/dashboard-map', () => ({
    default: (props: {
        year: number;
        onSelect: (id: string | null) => void;
        onCountChange?: (n: number) => void;
    }) => dashboardMapMock(props),
}));

vi.mock('@/layouts/app-layout', () => ({
    default: ({ children }: { children: React.ReactNode }) => (
        <div>{children}</div>
    ),
}));

vi.mock('@/routes', () => ({
    dashboard: () => '/dashboard',
}));

vi.mock('@/routes/entities', () => ({
    show: (id: string) => ({ url: `/entities/${id}` }),
}));

const fetchMock = vi.fn(async () => ({
    ok: true,
    json: async () => ({ data: { id: 'entity-1', name: 'Entity One' } }),
}));
vi.stubGlobal('fetch', fetchMock);

afterEach(() => {
    cleanup();
    dashboardMapMock.mockClear();
    fetchMock.mockClear();
    window.sessionStorage.clear();
});

function renderDashboard() {
    const queryClient = new QueryClient({
        defaultOptions: {
            queries: {
                retry: false,
            },
        },
    });

    return render(
        <QueryClientProvider client={queryClient}>
            <Dashboard />
        </QueryClientProvider>,
    );
}

describe('Dashboard', () => {
    it('restores the selected year from session storage and passes it to the map', async () => {
        window.sessionStorage.setItem(YEAR_STORAGE_KEY, '250');

        renderDashboard();

        const yearInput = await screen.findByLabelText(/Active year/i);
        expect(yearInput).toHaveValue(250);

        await waitFor(() => {
            expect(screen.getByTestId('mock-dashboard-map')).toHaveAttribute(
                'data-year',
                '250',
            );
        });

        fireEvent.change(yearInput, { target: { value: '500' } });

        await waitFor(() => {
            expect(screen.getByTestId('mock-dashboard-map')).toHaveAttribute(
                'data-year',
                '500',
            );
        });

        expect(window.sessionStorage.getItem(YEAR_STORAGE_KEY)).toBe('500');
    });

    it('reflects the map feature count and forwards selection into the side panel', async () => {
        window.sessionStorage.setItem(YEAR_STORAGE_KEY, '250');

        renderDashboard();

        await screen.findByTestId('mock-dashboard-map');

        fireEvent.click(screen.getByTestId('mock-count-button'));

        await waitFor(() => {
            expect(
                screen.getByText(/entities are currently visible/),
            ).toHaveTextContent('7 entities are currently visible.');
        });

        fireEvent.click(screen.getByTestId('mock-select-button'));

        await waitFor(() => {
            expect(
                screen.queryByText('Nothing selected yet'),
            ).not.toBeInTheDocument();
        });
    });
});
