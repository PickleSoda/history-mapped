// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import {
    afterAll,
    afterEach,
    beforeAll,
    describe,
    expect,
    it,
    vi,
} from 'vitest';
import Dashboard from '../dashboard';

const YEAR_STORAGE_KEY = 'historical-dashboard:selected-year';

const historicalMapViewerMock = vi.fn(
    ({
        timeframeDate,
        baseGeometries,
    }: {
        timeframeDate?: string;
        baseGeometries?: unknown[];
    }) => (
        <div
            data-testid="mock-map-viewer"
            data-feature-count={String(baseGeometries?.length ?? 0)}
            data-timeframe={timeframeDate ?? ''}
        />
    ),
);

vi.mock('@inertiajs/react', () => ({
    Head: () => null,
    Link: ({ children, href }: { children: React.ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
}));

vi.mock('@/components/historical-map-viewer', () => ({
    default: (props: { timeframeDate?: string; baseGeometries?: unknown[] }) =>
        historicalMapViewerMock(props),
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

let fetchMock: ReturnType<typeof vi.fn>;

beforeAll(() => {
    fetchMock = vi.fn();
    global.fetch = fetchMock as unknown as typeof fetch;
});

afterAll(() => {
    fetchMock.mockRestore();
});

afterEach(() => {
    fetchMock.mockReset();
    historicalMapViewerMock.mockClear();
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
    it('restores the selected year from session storage and re-renders the map when the year changes', async () => {
        window.sessionStorage.setItem(YEAR_STORAGE_KEY, '250');

        fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
            const url = new URL(String(input), 'http://localhost');
            const year = url.searchParams.get('year') ?? '0';

            return {
                ok: true,
                json: async () => ({
                    type: 'FeatureCollection',
                    features: [
                        {
                            type: 'Feature',
                            id: `entity-${year}`,
                            geometry: {
                                type: 'Point',
                                coordinates: [Number(year), 10],
                            },
                            properties: {
                                id: `entity-${year}`,
                                name: `Entity ${year}`,
                                entity_type: 'polity',
                                entity_group: 'place',
                                temporal_start: null,
                                temporal_end: null,
                                impact_score: 50,
                                entity_color: null,
                            },
                        },
                    ],
                }),
            } as Response;
        });

        renderDashboard();

        const yearInput = await screen.findByLabelText(/Active year/i);
        expect(yearInput).toHaveValue(250);

        await waitFor(() => {
            expect(fetchMock).toHaveBeenCalledWith(
                '/api/v1/entities/map/year?year=250',
                expect.objectContaining({
                    headers: { Accept: 'application/json' },
                }),
            );
        });

        await waitFor(() => {
            expect(screen.getByTestId('mock-map-viewer')).toHaveAttribute(
                'data-timeframe',
                '250-01-01',
            );
        });

        fireEvent.change(yearInput, { target: { value: '500' } });

        await waitFor(() => {
            expect(fetchMock).toHaveBeenCalledWith(
                '/api/v1/entities/map/year?year=500',
                expect.objectContaining({
                    headers: { Accept: 'application/json' },
                }),
            );
        });

        expect(window.sessionStorage.getItem(YEAR_STORAGE_KEY)).toBe('500');

        await waitFor(() => {
            expect(screen.getByTestId('mock-map-viewer')).toHaveAttribute(
                'data-timeframe',
                '500-01-01',
            );
        });
    });
});
