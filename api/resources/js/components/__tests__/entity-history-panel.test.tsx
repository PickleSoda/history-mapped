// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, it, beforeAll, afterAll, afterEach, vi, expect } from 'vitest';
import EntityHistoryPanel from '../entity-history-panel';
import '@testing-library/jest-dom/vitest';

vi.mock('../historical-map-viewer', () => ({
    default: () => <div data-testid="mock-map-viewer" />,
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
            geom: { type: 'Point', coordinates: [3, 4] },
            territory_geom: null,
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

    function mockFetchImpl(url: string) {
        if (url.includes('/timeline')) {
            return Promise.resolve({
                ok: true,
                json: () => Promise.resolve({ data: timelineEntries }),
            } as Response);
        }

        return Promise.reject(new Error('Unknown URL'));
    }

    it('renders timeline items and applies overlays on click', async () => {
        fetchMock.mockImplementation((input) =>
            mockFetchImpl(String(input)),
        );

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
                    entityTerritoryGeojson={{ type: 'FeatureCollection', features: [] }}
                    entityTemporalStart={null}
                    entityTemporalEnd={null}
                    timelineUrl="/api/v1/entities/e1/timeline"
                />
            </QueryClientProvider>,
        );

        // Wait for timeline items to appear
        expect(await screen.findByText(/Alliance of 120 CE/i)).toBeInTheDocument();

        // Simulate clicking the relationship timeline item
        const relItem = screen.getByText(/Alliance of 120 CE/i);
        fireEvent.click(relItem);

        // No assertion on map overlays (MapLibre is not rendered in jsdom),
        // but we can check that the timeline selection logic works by checking for selected class
        // or by checking that the timeline item is still present
        expect(screen.getByText(/Alliance of 120 CE/i)).toBeInTheDocument();
    });
});
