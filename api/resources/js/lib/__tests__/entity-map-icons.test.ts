// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import {
    GROUP_COLORS,
    groupColorExpression,
    markerImageId,
    registerGroupMarkers,
} from '../entity-map-icons';

describe('GROUP_COLORS', () => {
    it('carries the five group accents plus a default', () => {
        expect(GROUP_COLORS).toEqual({
            POLITY: '#b4543f',
            PLACE: '#6b7f4a',
            EVENT: '#bd8a2c',
            ECONOMY: '#4d6a86',
            CULTURE: '#8a5673',
            DEFAULT: '#71717a',
        });
    });
});

describe('groupColorExpression', () => {
    it('builds a match on entity_group ending in the default color', () => {
        const expr = groupColorExpression() as unknown[];
        expect(expr[0]).toBe('match');
        expect(expr[1]).toEqual(['get', 'entity_group']);
        expect(expr).toContain('POLITY');
        expect(expr).toContain('#b4543f');
        expect(expr[expr.length - 1]).toBe('#71717a');
    });
});

describe('markerImageId', () => {
    it('uppercases the group into the image id', () => {
        expect(markerImageId('polity')).toBe('marker-POLITY');
        expect(markerImageId('CULTURE')).toBe('marker-CULTURE');
    });
});

describe('registerGroupMarkers', () => {
    it('registers one image per group plus the default, skipping existing', async () => {
        const existing = new Set<string>(['marker-POLITY']);
        const addImage = vi.fn((id: string) => existing.add(id));
        const map = {
            hasImage: (id: string) => existing.has(id),
            addImage,
        };

        // jsdom never fires Image.onload — resolve loads synchronously instead.
        const originalImage = globalThis.Image;
        class InstantImage {
            public onload: (() => void) | null = null;
            public onerror: (() => void) | null = null;
            public set src(_v: string) {
                queueMicrotask(() => this.onload?.());
            }
        }
        vi.stubGlobal('Image', InstantImage);

        try {
            await registerGroupMarkers(map);
        } finally {
            vi.stubGlobal('Image', originalImage);
        }

        const added = addImage.mock.calls.map((c) => c[0]).sort();
        expect(added).toEqual([
            'marker-CULTURE',
            'marker-DEFAULT',
            'marker-ECONOMY',
            'marker-EVENT',
            'marker-PLACE',
        ]);
    });
});
