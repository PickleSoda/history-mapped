import { describe, expect, it } from 'vitest';
import { roleLabel, sortRoles } from '@/components/user-badges';
import { permissionsFromRoles, toggleName } from '@/lib/user-admin';

describe('toggleName', () => {
    it('adds once and removes every copy', () => {
        expect(toggleName(['user'], 'moderator', true)).toEqual([
            'user',
            'moderator',
        ]);
        expect(toggleName(['user', 'moderator'], 'moderator', true)).toEqual([
            'user',
            'moderator',
        ]);
        expect(toggleName(['user', 'moderator'], 'user', false)).toEqual([
            'moderator',
        ]);
    });
});

describe('permissionsFromRoles', () => {
    const roles = [
        { name: 'user', permissions: ['contributions.create'] },
        {
            name: 'geo_moderator',
            permissions: ['geometry.write', 'admin.access'],
        },
    ];

    it('unions the permissions of the selected roles only', () => {
        expect(
            [...permissionsFromRoles(roles, ['user', 'geo_moderator'])].sort(),
        ).toEqual(['admin.access', 'contributions.create', 'geometry.write']);
        expect(permissionsFromRoles(roles, []).size).toBe(0);
    });
});

describe('role labels', () => {
    it('humanises role names and puts admin first', () => {
        expect(roleLabel('history_moderator')).toBe('History moderator');
        expect(sortRoles(['user', 'admin', 'geo_moderator'])).toEqual([
            'admin',
            'geo_moderator',
            'user',
        ]);
    });
});
