import { describe, it, expect } from 'vitest';
import { ENTITY_GROUPS } from '@/types/atlas';
import { groupColor } from './colors';

describe('groupColor', () => {
  it('returns a hex fallback for every group when the CSS var is unset (jsdom)', () => {
    for (const g of ENTITY_GROUPS) {
      expect(groupColor(g)).toMatch(/^#[0-9a-f]{6}$/i);
    }
  });
});
