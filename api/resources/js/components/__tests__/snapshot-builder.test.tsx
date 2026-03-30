// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeAll, afterAll, afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import SnapshotBuilder from '../snapshot-builder';

let fetchMock: ReturnType<typeof vi.fn>;

beforeAll(() => {
    fetchMock = vi.fn();
    global.fetch = fetchMock as unknown as typeof fetch;

    const meta = document.createElement('meta');
    meta.setAttribute('name', 'csrf-token');
    meta.setAttribute('content', 'test-token');
    document.head.appendChild(meta);
});

afterAll(() => {
    fetchMock.mockRestore();
});

afterEach(() => {
    fetchMock.mockReset();
});

describe('SnapshotBuilder', () => {
    it('includes geography reference payload when an OHM object id is supplied', async () => {
        fetchMock
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    snapshots: [
                        {
                            snapshot_id: 'snap-existing',
                            entity_id: 'entity-1',
                            geo_ref_id: 'gr-existing',
                            geo_ref: {
                                geo_ref_id: 'gr-existing',
                                provider: 'ohm',
                                external_type: 'relation',
                                external_id: '1880',
                                match_role: 'candidate',
                                retrieval_method: 'rest',
                                match_score: 0.97,
                                source_meta: {
                                    display_name: 'Roman Empire',
                                },
                            },
                            year_start: 50,
                            year_end: 75,
                            label: 'Existing extent',
                            confidence: null,
                            notes: null,
                            description: null,
                            relationship_id: null,
                            source_event_id: null,
                            display_priority: 0,
                            source_citations: null,
                            geojson: null,
                            territory_geojson: { type: 'Polygon', coordinates: [] },
                            created_at: null,
                            updated_at: null,
                        },
                    ],
                }),
            } as Response)
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    snapshot: {
                        snapshot_id: 'snap-1',
                        entity_id: 'entity-1',
                        geo_ref_id: 'gr-1',
                        year_start: 100,
                        year_end: 120,
                        label: 'Imperial extent',
                        confidence: null,
                        notes: null,
                        description: null,
                        relationship_id: null,
                        source_event_id: null,
                        display_priority: 0,
                        source_citations: null,
                        geojson: null,
                        territory_geojson: { type: 'Polygon', coordinates: [] },
                        created_at: null,
                        updated_at: null,
                    },
                }),
            } as Response)
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    snapshots: [],
                }),
            } as Response);

        render(
            <SnapshotBuilder
                entityId="entity-1"
                listUrl="/entities/entity-1/snapshots"
                storeUrl="/entities/entity-1/snapshots"
                updateUrlFn={(snapshotId) => `/entities/entity-1/snapshots/${snapshotId}`}
                deleteUrlFn={(snapshotId) => `/entities/entity-1/snapshots/${snapshotId}`}
            />,
        );

        expect(await screen.findByText(/Roman Empire/i)).toBeInTheDocument();
        expect(screen.getByText(/candidate/i)).toBeInTheDocument();
        expect(screen.getByText(/0\.97/i)).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: /Add Snapshot/i }));
        fireEvent.change(screen.getByLabelText(/Year Start/i), {
            target: { value: '100' },
        });
        fireEvent.change(screen.getByLabelText(/Year End/i), {
            target: { value: '120' },
        });
        fireEvent.change(screen.getByLabelText(/OHM object id/i), {
            target: { value: '1880' },
        });
        fireEvent.click(screen.getByRole('button', { name: /Create Snapshot/i }));

        await waitFor(() => {
            expect(fetchMock).toHaveBeenCalledWith(
                '/entities/entity-1/snapshots',
                expect.objectContaining({
                    method: 'POST',
                    body: JSON.stringify({
                        year_start: 100,
                        year_end: 120,
                        label: undefined,
                        confidence: undefined,
                        notes: undefined,
                        display_priority: 0,
                        geojson: undefined,
                        territory_geojson: undefined,
                        geography_reference: {
                            provider: 'ohm',
                            external_type: 'relation',
                            external_id: '1880',
                            match_role: 'candidate',
                            retrieval_method: 'rest',
                        },
                    }),
                }),
            );
        });
    });
});