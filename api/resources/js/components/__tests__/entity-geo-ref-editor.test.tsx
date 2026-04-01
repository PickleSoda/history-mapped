// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeAll, afterAll, afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import EntityGeoRefEditor from '../entity-geo-ref-editor';

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

describe('EntityGeoRefEditor', () => {
    it('searches OHM by name, attaches a result, and hydrates geometry callback', async () => {
        const onHydratedGeometryChange = vi.fn();

        fetchMock
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({ data: [] }),
            } as Response)
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    data: [
                        {
                            external_type: 'relation',
                            external_id: '1880',
                            display_name: 'Roman Empire, Mediterranean',
                            match_label: 'Roman Empire',
                            source_meta: {
                                class: 'boundary',
                                type: 'historic',
                            },
                            external_tags: {
                                historic: 'empire',
                            },
                            geojson: {
                                type: 'Polygon',
                                coordinates: [],
                            },
                        },
                    ],
                }),
            } as Response)
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    data: {
                        geo_ref_id: 'gr-1',
                        provider: 'ohm',
                        external_type: 'relation',
                        external_id: '1880',
                        match_role: 'primary',
                        retrieval_method: 'rest',
                        source_meta: { display_name: 'Roman Empire' },
                        is_active: true,
                    },
                }),
            } as Response)
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    id: 'entity-1',
                    geom: null,
                    territory_geom: {
                        type: 'Polygon',
                        coordinates: [],
                    },
                }),
            } as Response)
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    data: [
                        {
                            geo_ref_id: 'gr-1',
                            provider: 'ohm',
                            external_type: 'relation',
                            external_id: '1880',
                            match_role: 'primary',
                            retrieval_method: 'rest',
                            source_meta: { display_name: 'Roman Empire' },
                            is_active: true,
                        },
                    ],
                }),
            } as Response);

        render(
            <EntityGeoRefEditor
                entityId="entity-1"
                onHydratedGeometryChange={onHydratedGeometryChange}
            />,
        );

        expect(await screen.findByText(/No OHM references attached yet/i)).toBeInTheDocument();

        fireEvent.change(screen.getByLabelText(/Search OHM by name/i), {
            target: { value: 'Roman Empire' },
        });
        fireEvent.click(screen.getByRole('button', { name: /Search OHM/i }));

        expect(await screen.findByText(/Roman Empire, Mediterranean/i)).toBeInTheDocument();
        expect(screen.getByText(/boundary/i)).toBeInTheDocument();
        expect(screen.getByText('historic')).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: /Attach Roman Empire/i }));

        await waitFor(() => {
            expect(onHydratedGeometryChange).toHaveBeenCalledWith(null, {
                type: 'Polygon',
                coordinates: [],
            });
        });

        expect(await screen.findByText(/Roman Empire/i)).toBeInTheDocument();
        expect(fetchMock).toHaveBeenCalledWith(
            '/api/v1/entities/entity-1/geography-references',
            expect.objectContaining({ method: 'POST' }),
        );
        expect(fetchMock).toHaveBeenCalledWith(
            '/api/v1/entities/entity-1/geography-references/search?q=Roman+Empire',
            expect.objectContaining({ method: 'GET' }),
        );
    });
});
