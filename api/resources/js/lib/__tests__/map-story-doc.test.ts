import { describe, expect, it } from 'vitest';
import {
    featuresKey,
    freeId,
    fromGeoJson,
    issueTarget,
    lastPosition,
    lengthStatus,
    moveUnitTo,
    renameFeature,
    renameSide,
    renameUnit,
    stepStateKey,
    toGeoJson,
} from '../map-story-doc';
import type { StoryDoc } from '../map-story-doc';

const doc = (): StoryDoc => ({
    schema: 2,
    slug: 'battle-of-x',
    kind: 'battle',
    sides: [
        { id: 'rome', name: 'Rome', color: '#aa0000' },
        { id: 'carthage', name: 'Carthage', color: '#0000aa' },
    ],
    units: [
        { id: 'legion', side: 'rome', kind: 'infantry', label: 'Legion' },
        { id: 'horse', side: 'carthage', kind: 'cavalry', label: 'Horse' },
    ],
    terrain: [
        {
            id: 'river',
            kind: 'river',
            label: 'River',
            line: [
                [0, 0],
                [1, 1],
            ],
            side: 'rome',
        },
    ],
    steps: [
        {
            id: 's1',
            positions: { legion: { at: [1, 1] }, horse: { at: [2, 2] } },
            moves: [],
            terrain_state: { river: { held_by: 'rome' } },
        },
        {
            id: 's2',
            positions: {
                legion: { at: [1.5, 1.5] },
                horse: { with: 'legion', by: 'rome' },
            },
            moves: [
                {
                    unit: 'legion',
                    type: 'advance',
                    path: [
                        [1, 1],
                        [1.5, 1.5],
                    ],
                },
                {
                    side: 'rome',
                    type: 'fire',
                    path: [
                        [1, 1],
                        [2, 2],
                    ],
                    target: 'horse',
                },
            ],
            focus: ['legion', 'horse'],
            beats: [
                { label: 'then', positions: { legion: { at: [1.6, 1.6] } } },
            ],
        },
    ],
});

describe('issueTarget', () => {
    it('points step, list, feature and top-level messages at their tab', () => {
        expect(issueTarget("step 's2'.moves[0].path: needs ≥2 points")).toEqual(
            { tab: 'steps', step: 's2' },
        );
        expect(issueTarget("units[3].side: unknown side 'x'")).toEqual({
            tab: 'sides',
            list: 'units',
            index: 3,
        });
        expect(issueTarget('sides: at least one')).toEqual({
            tab: 'sides',
            list: 'sides',
            index: undefined,
        });
        expect(issueTarget('features[2] (caffa): a city needs `at`')).toEqual({
            tab: 'features',
            index: 2,
        });
        expect(issueTarget('terrain[0].id: unique lowercase id')).toEqual({
            tab: 'features',
            index: 0,
        });
        expect(issueTarget('intro: missing')).toEqual({
            tab: 'overview',
            field: 'intro',
        });
        expect(issueTarget('Something odd')).toEqual({
            tab: 'overview',
            field: undefined,
        });
    });
});

describe('freeId', () => {
    it('slugs the base and numbers it when taken', () => {
        expect(freeId('Roman Legion', [])).toBe('roman-legion');
        expect(freeId('s3', ['s3', 's3-2'])).toBe('s3-3');
        expect(freeId('!!!', [])).toBe('item');
    });
});

describe('renames', () => {
    it('renames a unit everywhere it is referenced, keeping key order', () => {
        const out = renameUnit(doc(), 'legion', 'first-legion');
        expect(out.units[0].id).toBe('first-legion');
        expect(Object.keys(out.steps[0].positions)).toEqual([
            'first-legion',
            'horse',
        ]);
        expect(out.steps[1].positions.horse.with).toBe('first-legion');
        expect(out.steps[1].moves[0].unit).toBe('first-legion');
        expect(out.steps[1].focus).toEqual(['first-legion', 'horse']);
        expect(Object.keys(out.steps[1].beats[0].positions)).toEqual([
            'first-legion',
        ]);
    });

    it('renames a side in units, features, holders, captors and side arrows', () => {
        const out = renameSide(doc(), 'rome', 'roma');
        expect(out.sides[0].id).toBe('roma');
        expect(out.units[0].side).toBe('roma');
        expect(out.terrain[0].side).toBe('roma');
        expect(out.steps[0].terrain_state.river.held_by).toBe('roma');
        expect(out.steps[1].positions.horse.by).toBe('roma');
        expect(out.steps[1].moves[1].side).toBe('roma');
    });

    it('renames a feature and its per-step state', () => {
        const out = renameFeature(doc(), 'river', 'aufidus');
        expect(out.terrain[0].id).toBe('aufidus');
        expect(Object.keys(out.steps[0].terrain_state)).toEqual(['aufidus']);
    });

    it('leaves the input alone', () => {
        const input = doc();
        renameUnit(input, 'legion', 'x');
        expect(input.units[0].id).toBe('legion');
    });
});

describe('feature keys', () => {
    it('uses terrain / terrain_state for older documents and features for schema 3', () => {
        const v2 = doc();
        expect(featuresKey(v2)).toBe('terrain');
        expect(stepStateKey(v2, v2.steps[0])).toBe('terrain_state');
        expect(stepStateKey(v2, v2.steps[1])).toBe('terrain_state');
        const v3 = { schema: 3, features: [], steps: [{ id: 's1' }] };
        expect(featuresKey(v3)).toBe('features');
        expect(stepStateKey(v3, v3.steps[0])).toBe('features');
    });
});

describe('positions', () => {
    it('finds where a unit last stood before a step', () => {
        expect(lastPosition(doc(), 0, 'legion')).toBeNull();
        expect(lastPosition(doc(), 2, 'legion')).toEqual([1.6, 1.6]);
        expect(lastPosition(doc(), 2, 'horse')).toEqual([2, 2]);
    });

    it('moves a dragged unit: its point, and the end of its arrow (not a fire line)', () => {
        const out = moveUnitTo(doc(), 1, 'legion', [3, 3]);
        expect(out.steps[1].positions.legion.at).toEqual([3, 3]);
        expect(out.steps[1].moves[0].path.at(-1)).toEqual([3, 3]);
        const horse = moveUnitTo(doc(), 1, 'horse', [4, 4]);
        expect(horse.steps[1].positions.horse).toEqual({
            at: [4, 4],
            by: 'rome',
        });
        expect(horse.steps[1].moves[1].path.at(-1)).toEqual([2, 2]);
    });
});

describe('GeoJSON', () => {
    it('round-trips points, lines, one ring and several rings', () => {
        expect(fromGeoJson('at', toGeoJson('at', [1.123456, 2]))).toEqual([
            1.12346, 2,
        ]);
        expect(
            fromGeoJson(
                'line',
                toGeoJson('line', [
                    [0, 0],
                    [1, 1],
                ]),
            ),
        ).toEqual([
            [0, 0],
            [1, 1],
        ]);
        const ring = [
            [0, 0],
            [1, 0],
            [1, 1],
        ];
        expect(toGeoJson('area', ring)).toEqual({
            type: 'Polygon',
            coordinates: [[...ring, [0, 0]]],
        });
        expect(fromGeoJson('area', toGeoJson('area', ring))).toEqual(ring);
        const rings = [
            ring,
            [
                [5, 5],
                [6, 5],
                [6, 6],
            ],
        ];
        expect(toGeoJson('area', rings)?.type).toBe('MultiPolygon');
        expect(fromGeoJson('area', toGeoJson('area', rings))).toEqual(rings);
    });

    it('reads a feature collection from the draw tools and gives null when nothing fits', () => {
        const fc = {
            type: 'FeatureCollection',
            features: [
                {
                    type: 'Feature',
                    geometry: { type: 'Point', coordinates: [7, 8] },
                },
            ],
        };
        expect(fromGeoJson('at', fc)).toEqual([7, 8]);
        expect(fromGeoJson('line', fc)).toBeNull();
        expect(toGeoJson('line', [[0, 0]])).toBeNull();
    });
});

describe('lengthStatus', () => {
    it('counts trimmed characters against the limits', () => {
        expect(lengthStatus('  abc ', [3, 10])).toEqual({
            n: 3,
            ok: true,
            label: '3 / 3–10',
        });
        expect(lengthStatus('ab', [3, 10]).ok).toBe(false);
        expect(lengthStatus(undefined, undefined)).toEqual({
            n: 0,
            ok: true,
            label: '0',
        });
    });
});
