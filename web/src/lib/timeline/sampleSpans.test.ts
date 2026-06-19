import { describe, it, expect } from 'vitest';
import { sampleSpans, SAMPLE_LANES } from './sampleSpans';
import { ENTITY_GROUPS } from '@/types/atlas';

describe('sampleSpans', () => {
  it('is non-empty', () => expect(sampleSpans.length).toBeGreaterThan(0));
  it('every span uses a known entity group', () => {
    for (const s of sampleSpans) expect(ENTITY_GROUPS).toContain(s.group);
  });
  it('every span starts before it ends', () => {
    for (const s of sampleSpans) expect(s.start).toBeLessThan(s.end);
  });
  it('every lane is within [0, SAMPLE_LANES)', () => {
    for (const s of sampleSpans) {
      expect(s.lane).toBeGreaterThanOrEqual(0);
      expect(s.lane).toBeLessThan(SAMPLE_LANES);
    }
  });
});
