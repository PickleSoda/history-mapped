import { describe, expect, it } from 'vitest';
import { formatValue, normalizeHumanDiff } from '@/lib/human-diff';

describe('formatValue', () => {
    it('renders null/undefined as an em dash', () => {
        expect(formatValue(null)).toBe('—');
        expect(formatValue(undefined)).toBe('—');
    });

    it('joins array values (e.g. coordinates)', () => {
        expect(formatValue([44.78, 41.71])).toBe('44.78, 41.71');
    });

    it('truncates long strings', () => {
        const long = 'x'.repeat(200);
        const out = formatValue(long);

        expect(out.length).toBeLessThan(200);
        expect(out.endsWith('…')).toBe(true);
    });
});

describe('normalizeHumanDiff', () => {
    it('maps a field-level edit diff to change rows', () => {
        const rows = normalizeHumanDiff('update_entity_fields', {
            summary: 'Update fields',
            diff: {
                founding_year: { from: 1921, to: 1922 },
                summary: { from: 'Old', to: 'New' },
            },
        });

        expect(rows).toEqual([
            {
                label: 'founding_year',
                from: '1921',
                to: '1922',
                kind: 'change',
            },
            { label: 'summary', from: 'Old', to: 'New', kind: 'change' },
        ]);
    });

    it('maps a create fields object to create rows with null from', () => {
        const rows = normalizeHumanDiff('create_entity', {
            summary: 'Create entity',
            fields: {
                name: 'Kingdom of Georgia',
                entity_type: 'political_entity',
            },
        });

        expect(rows).toEqual([
            {
                label: 'name',
                from: null,
                to: 'Kingdom of Georgia',
                kind: 'create',
            },
            {
                label: 'entity_type',
                from: null,
                to: 'political_entity',
                kind: 'create',
            },
        ]);
    });

    it('appends the verified label to a Wikidata to-value', () => {
        const rows = normalizeHumanDiff('set_entity_wikidata', {
            summary: 'Set QID',
            from: null,
            to: 'Q130229',
            verified_label: 'Georgian SSR',
        });

        expect(rows).toEqual([
            {
                label: 'Wikidata QID',
                from: '—',
                to: 'Q130229 (Georgian SSR)',
                kind: 'change',
            },
        ]);
    });

    it('formats location coordinates in a from/to row', () => {
        const rows = normalizeHumanDiff('set_entity_location', {
            summary: 'Move entity',
            from: null,
            to: [44.78, 41.71],
        });

        expect(rows).toEqual([
            {
                label: 'Location',
                from: '—',
                to: '44.78, 41.71',
                kind: 'change',
            },
        ]);
    });

    it('maps a merge to a single merge row (loser → survivor)', () => {
        const rows = normalizeHumanDiff('merge_duplicate_entities', {
            summary: 'Merge',
            survivor_name: 'Georgian SSR',
            loser_name: 'Gruzia',
        });

        expect(rows).toEqual([
            {
                label: 'merge',
                from: 'Gruzia',
                to: 'Georgian SSR',
                kind: 'merge',
            },
        ]);
    });

    it('returns [] for a summary-only diff', () => {
        expect(
            normalizeHumanDiff('create_relationship', {
                summary: 'Link A → B',
            }),
        ).toEqual([]);
    });

    it('returns [] for malformed input without throwing', () => {
        expect(normalizeHumanDiff('x', null)).toEqual([]);
        expect(normalizeHumanDiff('x', 'a string')).toEqual([]);
        expect(normalizeHumanDiff('x', 42)).toEqual([]);
        expect(normalizeHumanDiff('x', { summary: 's', fields: {} })).toEqual(
            [],
        );
    });
});
