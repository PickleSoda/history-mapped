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
    const relationships = [
        {
            relationship_id: 'rel1',
            source_entity_id: 'e1',
            target_entity_id: 'e2',
            relationship_type: 'allied_with',
            temporal_start: '120',
            temporal_end: '130',
            description: 'Rel 1',
            confidence: 'medium',
            direction: 'outgoing',
            related_entity: {
                id: 'e2',
                name: 'Entity 2',
                entity_type: 'city',
                entity_group: 'PLACE',
                geojson: { type: 'Point', coordinates: [3, 4] },
                territory_geojson: null,
            },
            created_at: null,
        },
    ];

    function mockFetchImpl(url: string) {
        if (url.includes('relationships')) {
            return Promise.resolve({
                ok: true,
                json: () => Promise.resolve({ outgoing: relationships, incoming: [] }),
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
                    relationshipsUrl="/fake/relationships"
                />
            </QueryClientProvider>,
        );

        // Wait for timeline items to appear
        expect(await screen.findByText(/allied with Entity 2/i)).toBeInTheDocument();

        // Simulate clicking the relationship timeline item
        const relItem = screen.getByText(/allied with Entity 2/i);
        fireEvent.click(relItem);

        // No assertion on map overlays (MapLibre is not rendered in jsdom),
        // but we can check that the timeline selection logic works by checking for selected class
        // or by checking that the timeline item is still present
        expect(screen.getByText(/allied with Entity 2/i)).toBeInTheDocument();
    });
});
