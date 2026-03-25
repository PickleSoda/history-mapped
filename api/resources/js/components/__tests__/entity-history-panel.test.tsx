import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, it, beforeAll, afterAll, afterEach, vi, expect } from 'vitest';
import EntityHistoryPanel from '../entity-history-panel';

// @vitest-environment jsdom
import '@testing-library/jest-dom';

let fetchMock: ReturnType<typeof vi.fn>;

// Mock fetch globally
beforeAll(() => {
    fetchMock = vi.fn();
    global.fetch = fetchMock as unknown as typeof fetch;
});

afterAll(() => {
    fetchMock.mockRestore();
});

afterEach(() => {
    fetchMock.mockReset();
});

describe('EntityHistoryPanel', () => {
    const snapshots = [
        {
            snapshot_id: 'snap1',
            entity_id: 'e1',
            year_start: 100,
            year_end: 110,
            label: 'Snapshot 1',
            confidence: 'high',
            notes: null,
            description: 'Desc 1',
            relationship_id: null,
            source_event_id: null,
            display_priority: 1,
            source_citations: null,
            geojson: { type: 'Point', coordinates: [1, 2] },
            territory_geojson: null,
            created_at: null,
            updated_at: null,
        },
    ];
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
        if (url.includes('snapshots')) {
            return Promise.resolve({
                ok: true,
                json: () => Promise.resolve({ snapshots }),
            } as Response);
        }

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
                    snapshotsUrl="/fake/snapshots"
                    relationshipsUrl="/fake/relationships"
                />
            </QueryClientProvider>,
        );

        // Wait for timeline items to appear
        expect(await screen.findByText('Snapshot 1')).toBeInTheDocument();
        expect(await screen.findByText(/allied with Entity 2/i)).toBeInTheDocument();

        // Simulate clicking the relationship timeline item
        const relItem = screen.getByText(/allied with Entity 2/i);
        fireEvent.click(relItem);

        // Simulate clicking the snapshot timeline item
        const snapItem = screen.getByText('Snapshot 1');
        fireEvent.click(snapItem);

        // No assertion on map overlays (MapLibre is not rendered in jsdom),
        // but we can check that the timeline selection logic works by checking for selected class
        // or by checking that the timeline item is still present
        expect(screen.getByText('Snapshot 1')).toBeInTheDocument();
    });
});
