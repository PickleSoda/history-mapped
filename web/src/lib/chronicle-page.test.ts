import { describe, expect, it } from 'vitest';
import {
  clampStep,
  defaultShowExternal,
  EXTERNAL_DEFAULT_MAX_EDGES,
  nextMounted,
  sourceTypeLabel,
  stepRows,
  yearSpanText,
} from './chronicle-page';
import type { ChronicleEntry } from './schemas/chronicle';
import type { ChronicleGraphStep } from './schemas/graph';

const entry = (id: string, seq: number): ChronicleEntry => ({
  entry_id: id,
  sequence_order: seq,
  start_year: null,
  end_year: null,
  impact_score: null,
  approximate_location: null,
  narrative_text: null,
});
const gstep = (id: string, seq: number): ChronicleGraphStep => ({
  entry_id: id,
  sequence_order: seq,
  start_year: null,
  end_year: null,
  primary_relationship_id: null,
  entity_ids: [],
  relationship_ids: [],
});

describe('defaultShowExternal', () => {
  it('shows externals on small graphs only', () => {
    expect(defaultShowExternal({ edges: new Array(39) })).toBe(true);
    expect(defaultShowExternal({ edges: new Array(EXTERNAL_DEFAULT_MAX_EDGES) })).toBe(true);
    expect(defaultShowExternal({ edges: new Array(586) })).toBe(false);
  });
});

describe('stepRows', () => {
  it('keeps entry order and joins graph steps by entry id', () => {
    const rows = stepRows([entry('a', 0), entry('b', 1), entry('c', 2)], [gstep('c', 2), gstep('a', 0)]);
    expect(rows.map((r) => [r.index, r.entry.entry_id, r.step?.sequence_order ?? null])).toEqual([
      [0, 'a', 0],
      [1, 'b', null],
      [2, 'c', 2],
    ]);
    expect(stepRows([entry('a', 0)], undefined)[0].step).toBeNull();
  });
});

describe('helpers', () => {
  it('clamps step indices', () => {
    expect(clampStep(-3, 10)).toBe(0);
    expect(clampStep(4.6, 10)).toBe(5);
    expect(clampStep(99, 10)).toBe(9);
    expect(clampStep(3, 0)).toBe(0);
  });

  it('formats year spans', () => {
    expect(yearSpanText(-30, -30)).toBe('30 BCE');
    expect(yearSpanText(-30, 476)).toBe('30 BCE – 476 CE');
    expect(yearSpanText(null, 476)).toBe('476 CE');
    expect(yearSpanText(null, null)).toBeNull();
  });

  it('labels source types', () => {
    expect(sourceTypeLabel('video_transcript')).toBe('Video transcript');
    expect(sourceTypeLabel(null)).toBeNull();
  });
});

describe('nextMounted (hysteresis)', () => {
  it('mounts on entering the near zone and unmounts only past the far zone', () => {
    expect(nextMounted(false, { near: true, far: true })).toBe(true);
    // between the zones: keep whatever it was
    expect(nextMounted(true, { near: false, far: true })).toBe(true);
    expect(nextMounted(false, { near: false, far: true })).toBe(false);
    // beyond the far zone
    expect(nextMounted(true, { near: false, far: false })).toBe(false);
    // no reading yet
    expect(nextMounted(false, { near: null, far: null })).toBe(false);
  });
});
