// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import {
    describe,
    it,
    beforeAll,
    afterAll,
    afterEach,
    vi,
    expect,
} from 'vitest';
import EntityHistoryPanel from '../entity-history-panel';
import '@testing-library/jest-dom/vitest';

const historicalMapViewerMock = vi.fn(() => (
    <div data-testid="mock-map-viewer" />
));

vi.mock('../historical-map-viewer', () => ({
    default: (props: unknown) => historicalMapViewerMock(props),
}));

let fetchMock: ReturnType<typeof vi.fn>;

// Mock fetch globally
beforeAll(() => {
    fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
        configurable: true,
        value: vi.fn(),
    });
});

afterAll(() => {
    fetchMock.mockRestore();
});

afterEach(() => {
    fetchMock.mockReset();
    historicalMapViewerMock.mockClear();
});

describe('EntityHistoryPanel', () => {
    const timelineEntries = [
        {
            id: 'timeline-1',
            entity_id: 'e1',
            entry_kind: 'relationship_presence',
            start_year: 120,
            end_year: 130,
            title: 'Alliance of 120 CE',
            description: 'Rel 1',
            location_entity_id: null,
            has_geom: true,
            has_territory_geom: false,
            geom: { type: 'Point', coordinates: [3, 4] },
            source_table: 'geometry_periods',
            source_id: 'gp-1',
            relationship_type: 'allied_with',
            related_entity_id: 'e2',
            related_entity_name: 'Entity 2',
            derived_at: null,
            created_at: null,
            updated_at: null,
        },
    ];

    const timelineEntryDetail = {
        data: {
            ...timelineEntries[0],
            geom: { type: 'Point', coordinates: [3, 4] },
            territory_geom: null,
        },
    };

    function mockFetchImpl(url: string) {
        if (url.endsWith('/timeline')) {
            return Promise.resolve({
                ok: true,
                json: () => Promise.resolve({ data: timelineEntries }),
            } as Response);
        }

        if (url.endsWith('/timeline/timeline-1')) {
            return Promise.resolve({
                ok: true,
                json: () => Promise.resolve(timelineEntryDetail),
            } as Response);
        }

        return Promise.reject(new Error('Unknown URL'));
    }

    it('renders timeline items and uses summary point geometry without an extra detail fetch', async () => {
        fetchMock.mockImplementation((input) => mockFetchImpl(String(input)));

        const queryClient = new QueryClient({
            defaultOptions: {
                queries: {
                    retry: false,
                },
            },
        });

        render(
            <QueryClientProvider client={queryClient}>
                <EntityHistoryPanel
                    entityGeojson={{ type: 'FeatureCollection', features: [] }}
                    entityTerritoryGeojson={{
                        type: 'FeatureCollection',
                        features: [],
                    }}
                    entityTemporalStart={null}
                    entityTemporalEnd={null}
                    timelineUrl="/api/v1/entities/e1/timeline"
                />
            </QueryClientProvider>,
        );

        // Wait for timeline items to appear
        expect(
            await screen.findByText(/Alliance of 120 CE/i),
        ).toBeInTheDocument();

        // Simulate clicking the relationship timeline item
        const relItem = screen.getByText(/Alliance of 120 CE/i);
        fireEvent.click(relItem);

        await waitFor(() => {
            expect(fetchMock).toHaveBeenCalledTimes(1);
        });

        expect(fetchMock).toHaveBeenCalledWith(
            '/api/v1/entities/e1/timeline',
            expect.objectContaining({
                headers: { Accept: 'application/json' },
            }),
        );

        expect(screen.getByText(/Alliance of 120 CE/i)).toBeInTheDocument();
    });

    it('shows timeline point geometries from the summary payload on the map', async () => {
        fetchMock.mockImplementation((input) => mockFetchImpl(String(input)));

        const queryClient = new QueryClient({
            defaultOptions: {
                queries: {
                    retry: false,
                },
            },
        });

        render(
            <QueryClientProvider client={queryClient}>
                <EntityHistoryPanel
                    entityGeojson={{ type: 'FeatureCollection', features: [] }}
                    entityTerritoryGeojson={{
                        type: 'FeatureCollection',
                        features: [],
                    }}
                    entityTemporalStart={null}
                    entityTemporalEnd={null}
                    timelineUrl="/api/v1/entities/e1/timeline"
                />
            </QueryClientProvider>,
        );

        expect(
            await screen.findByText(/Alliance of 120 CE/i),
        ).toBeInTheDocument();

        await waitFor(() => {
            const calls = historicalMapViewerMock.mock.calls;
            expect(
                calls.some(
                    (call) =>
                        Array.isArray(call[0]?.overlayGeometries) &&
                        call[0].overlayGeometries.some(
                            (geometry: {
                                type?: string;
                                geometry?: { type?: string };
                            }) =>
                                geometry?.type === 'Feature' &&
                                geometry?.geometry?.type === 'Point',
                        ),
                ),
            ).toBe(true);
        });
    });

    it('lazy loads detail geometry when a selected entry advertises territory geometry', async () => {
        const territorySummary = [
            {
                ...timelineEntries[0],
                id: 'timeline-2',
                title: 'Territorial expansion',
                has_geom: false,
                has_territory_geom: true,
                geom: null,
            },
        ];

        const territoryDetail = {
            data: {
                ...territorySummary[0],
                territory_geom: {
                    type: 'Polygon',
                    coordinates: [
                        [
                            [3, 4],
                            [4, 4],
                            [4, 5],
                            [3, 5],
                            [3, 4],
                        ],
                    ],
                },
            },
        };

        fetchMock.mockImplementation((input) => {
            const url = String(input);

            if (url.endsWith('/timeline')) {
                return Promise.resolve({
                    ok: true,
                    json: () => Promise.resolve({ data: territorySummary }),
                } as Response);
            }

            if (url.endsWith('/timeline/timeline-2')) {
                return Promise.resolve({
                    ok: true,
                    json: () => Promise.resolve(territoryDetail),
                } as Response);
            }

            return Promise.reject(new Error('Unknown URL'));
        });

        const queryClient = new QueryClient({
            defaultOptions: {
                queries: {
                    retry: false,
                },
            },
        });

        render(
            <QueryClientProvider client={queryClient}>
                <EntityHistoryPanel
                    entityGeojson={{ type: 'FeatureCollection', features: [] }}
                    entityTerritoryGeojson={{
                        type: 'FeatureCollection',
                        features: [],
                    }}
                    entityTemporalStart={null}
                    entityTemporalEnd={null}
                    timelineUrl="/api/v1/entities/e1/timeline"
                />
            </QueryClientProvider>,
        );

        expect(
            await screen.findByText(/Territorial expansion/i),
        ).toBeInTheDocument();

        fireEvent.click(screen.getByText(/Territorial expansion/i));

        await waitFor(() => {
            expect(fetchMock).toHaveBeenCalledWith(
                '/api/v1/entities/e1/timeline/timeline-2',
                expect.objectContaining({
                    headers: { Accept: 'application/json' },
                }),
            );
        });
    });
});
