import { describe, expect, it, vi } from 'vitest';
import { applyOhmLayerDateFilter } from '@/lib/ohm-layer-date-filter';

/** The filter applyOhmLayerDateFilter gives a map's one OHM layer, as JSON. */
function filterFor(date: string): string {
    const setFilter = vi.fn();
    const map = {
        style: {},
        getStyle: () => ({
            layers: [
                {
                    id: 'borders',
                    type: 'line',
                    source: 'ohm',
                    'source-layer': 'boundaries',
                },
            ],
        }),
        getFilter: () => undefined,
        setFilter,
    };

    applyOhmLayerDateFilter(map as never, date);

    return JSON.stringify(setFilter.mock.lastCall?.[1]);
}

describe('applyOhmLayerDateFilter', () => {
    it('bounds a year-only date by that year', () => {
        const filter = filterFor('1066');

        expect(filter).toContain(
            '["<",["to-number",["get","start_decdate"]],1067]',
        );
        expect(filter).toContain(
            '[">=",["to-number",["get","end_decdate"]],1066]',
        );
    });

    // Date.UTC reads years 0–99 as 1900–1999; the bounds must not.
    it('bounds a first-century year by that year', () => {
        const filter = filterFor('0050');

        expect(filter).toContain(
            '["<",["to-number",["get","start_decdate"]],51]',
        );
        expect(filter).toContain(
            '[">=",["to-number",["get","end_decdate"]],50]',
        );
    });
});
