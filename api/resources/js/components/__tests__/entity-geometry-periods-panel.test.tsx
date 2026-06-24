// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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
import EntityGeometryPeriodsPanel from '../entity-geometry-periods-panel';

vi.mock('@/components/map-editor', () => ({
    default: ({
        onChange,
    }: {
        onChange: (
            geom: { type: string; coordinates: number[] } | null,
            territoryGeom: null,
        ) => void;
    }) => (
        <div>
            <label>
                Longitude
                <input
                    aria-label="Longitude"
                    onChange={(event) => {
                        const lon = Number(event.currentTarget.value);
                        onChange(
                            { type: 'Point', coordinates: [lon, 41.89] },
                            null,
                        );
                    }}
                />
            </label>
            <label>
                Latitude
                <input aria-label="Latitude" />
            </label>
        </div>
    ),
}));

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

describe('EntityGeometryPeriodsPanel', () => {
    it('loads, creates, updates, and deletes geometry periods', async () => {
        let rows: Array<{
            geometry_period_id: string;
            entity_id: string;
            period_type: string;
            start_year: number;
            end_year: number;
            description: string | null;
            provenance_mode: string;
            has_geom?: boolean;
            has_territory_geom?: boolean;
            geom?: { type: string; coordinates: number[] };
            territory_geom?: unknown;
        }> = [
            {
                geometry_period_id: 'gp-1',
                entity_id: 'e1',
                period_type: 'territory',
                start_year: 100,
                end_year: 120,
                description: 'Initial period',
                provenance_mode: 'manual',
                has_geom: true,
                has_territory_geom: false,
            },
        ];

        const detail = {
            geometry_period_id: 'gp-1',
            entity_id: 'e1',
            period_type: 'territory',
            start_year: 100,
            end_year: 120,
            description: 'Initial period',
            provenance_mode: 'manual',
            geom: { type: 'Point', coordinates: [12.48, 41.89] },
            territory_geom: null,
        };

        fetchMock.mockImplementation(
            async (input: RequestInfo | URL, init?: RequestInit) => {
                const url = String(input);
                const method = init?.method ?? 'GET';

                if (
                    url.includes('/entities/e1/geometry-periods') &&
                    method === 'GET'
                ) {
                    if (url.endsWith('/entities/e1/geometry-periods/gp-1')) {
                        return {
                            ok: true,
                            json: async () => ({ data: detail }),
                        } as Response;
                    }

                    return {
                        ok: true,
                        json: async () => ({ data: rows }),
                    } as Response;
                }

                if (
                    url.endsWith('/entities/e1/geometry-periods') &&
                    method === 'POST'
                ) {
                    const body = JSON.parse(String(init?.body ?? '{}')) as {
                        start_year: number;
                        end_year: number;
                        period_type: string;
                        description?: string;
                    };

                    rows = [
                        ...rows,
                        {
                            geometry_period_id: 'gp-2',
                            entity_id: 'e1',
                            period_type: body.period_type,
                            start_year: body.start_year,
                            end_year: body.end_year,
                            description: body.description ?? null,
                            provenance_mode: 'manual',
                            geom: { type: 'Point', coordinates: [13.0, 42.0] },
                            territory_geom: null,
                        },
                    ];

                    return {
                        ok: true,
                        json: async () => ({ data: rows[1] }),
                    } as Response;
                }

                if (
                    url.includes('/entities/e1/geometry-periods/') &&
                    method === 'PUT'
                ) {
                    const body = JSON.parse(String(init?.body ?? '{}')) as {
                        description?: string;
                        start_year: number;
                        end_year: number;
                        period_type: string;
                    };
                    const periodId = url.split('/').pop() ?? '';

                    rows = rows.map((row) =>
                        row.geometry_period_id === periodId
                            ? {
                                  ...row,
                                  period_type: body.period_type,
                                  start_year: body.start_year,
                                  end_year: body.end_year,
                                  description: body.description ?? null,
                              }
                            : row,
                    );

                    return {
                        ok: true,
                        json: async () => ({
                            data: rows.find(
                                (row) => row.geometry_period_id === periodId,
                            ),
                        }),
                    } as Response;
                }

                if (
                    url.endsWith('/entities/e1/geometry-periods/gp-1') &&
                    method === 'DELETE'
                ) {
                    rows = rows.filter(
                        (row) => row.geometry_period_id !== 'gp-1',
                    );

                    return {
                        ok: true,
                        json: async () => ({}),
                    } as Response;
                }

                return {
                    ok: false,
                    status: 500,
                    json: async () => ({}),
                } as Response;
            },
        );

        render(
            <EntityGeometryPeriodsPanel
                listUrl="/entities/e1/geometry-periods"
                detailUrlFn={(id) => `/entities/e1/geometry-periods/${id}`}
                storeUrl="/entities/e1/geometry-periods"
                updateUrlFn={(id) => `/entities/e1/geometry-periods/${id}`}
                deleteUrlFn={(id) => `/entities/e1/geometry-periods/${id}`}
            />,
        );

        expect(await screen.findByText(/Initial period/i)).toBeInTheDocument();

        fireEvent.change(screen.getByLabelText(/Start year/i), {
            target: { value: '130' },
        });
        fireEvent.change(screen.getByLabelText(/End year/i), {
            target: { value: '140' },
        });
        fireEvent.change(screen.getByLabelText(/Longitude/i), {
            target: { value: '13.0' },
        });
        fireEvent.change(screen.getByLabelText(/Latitude/i), {
            target: { value: '42.0' },
        });
        fireEvent.change(screen.getByLabelText(/^Description$/i), {
            target: { value: 'Created period' },
        });

        fireEvent.click(screen.getByRole('button', { name: /Add Period/i }));

        expect(await screen.findByText(/Created period/i)).toBeInTheDocument();

        fireEvent.click(screen.getAllByRole('button', { name: /Edit/i })[0]);

        await waitFor(() => {
            expect(fetchMock).toHaveBeenCalledWith(
                '/entities/e1/geometry-periods/gp-1',
                expect.objectContaining({
                    headers: { Accept: 'application/json' },
                }),
            );
        });

        fireEvent.change(screen.getByLabelText(/Edit description/i), {
            target: { value: 'Updated period' },
        });
        fireEvent.click(screen.getByRole('button', { name: /^Save$/i }));

        await waitFor(() => {
            expect(fetchMock).toHaveBeenCalledWith(
                expect.stringContaining('/entities/e1/geometry-periods/'),
                expect.objectContaining({ method: 'PUT' }),
            );
        });

        fireEvent.click(screen.getAllByRole('button', { name: /Delete/i })[0]);

        await waitFor(() => {
            expect(fetchMock).toHaveBeenCalledWith(
                '/entities/e1/geometry-periods/gp-1',
                expect.objectContaining({ method: 'DELETE' }),
            );
        });

        expect(fetchMock).toHaveBeenCalledWith(
            '/entities/e1/geometry-periods',
            expect.objectContaining({ method: 'POST' }),
        );
        expect(fetchMock).toHaveBeenCalledWith(
            '/entities/e1/geometry-periods/gp-1',
            expect.objectContaining({ method: 'DELETE' }),
        );
    });

    it('runs backfill, shows the counts, and reloads periods', async () => {
        fetchMock.mockImplementation(
            async (input: RequestInfo | URL, init?: RequestInit) => {
                const url = String(input);
                const method = init?.method ?? 'GET';

                if (
                    url.endsWith('/entities/e1/backfill') &&
                    method === 'POST'
                ) {
                    return {
                        ok: true,
                        json: async () => ({
                            data: {
                                counts: {
                                    aliases: 0,
                                    tags: 0,
                                    temporal_ranges: 1,
                                    locations: 1,
                                    geometry_periods: 2,
                                },
                            },
                        }),
                    } as Response;
                }

                // All geometry-period list/detail GETs return empty.
                return {
                    ok: true,
                    json: async () => ({ data: [] }),
                } as Response;
            },
        );

        render(
            <EntityGeometryPeriodsPanel
                listUrl="/entities/e1/geometry-periods"
                backfillUrl="/entities/e1/backfill"
            />,
        );

        const backfillButton = await screen.findByRole('button', {
            name: /Backfill from primary location/i,
        });
        fireEvent.click(backfillButton);

        // POST hits the backfill endpoint...
        await waitFor(() => {
            expect(fetchMock).toHaveBeenCalledWith(
                '/entities/e1/backfill',
                expect.objectContaining({ method: 'POST' }),
            );
        });

        // ...the counts are surfaced...
        expect(
            await screen.findByText(/2 geometry period\(s\)/i),
        ).toBeInTheDocument();

        // ...and the period list is reloaded afterwards (a GET after the POST).
        const listGets = fetchMock.mock.calls.filter(
            ([input, init]) =>
                String(input) === '/entities/e1/geometry-periods' &&
                (init?.method ?? 'GET') === 'GET',
        );
        expect(listGets.length).toBeGreaterThanOrEqual(2);
    });
});
