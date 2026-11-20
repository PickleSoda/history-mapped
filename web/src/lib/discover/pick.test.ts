import { describe, expect, it } from 'vitest';
import type { DiscoverEntity, MeanwhileRegion } from '@/lib/schemas/discover';
import {
  ON_THIS_DAY_ROWS,
  distanceKm,
  farthestEvents,
  leadEvents,
  offYear,
  spread,
  underWay,
  uniqueBy,
  yearAnchor,
} from './pick';

function entity(name: string, at: [number, number] | null): DiscoverEntity {
  return {
    id: name,
    name,
    entity_type: null,
    entity_group: 'event',
    summary: null,
    start_year: 1066,
    end_year: 1066,
    at,
    has_map_story: false,
  };
}

function region(key: string, event: DiscoverEntity | null): MeanwhileRegion {
  return { key, name: key, event, polity: null, counts: { events: event ? 1 : 0, polities: 0 } };
}

const LONDON: [number, number] = [-0.13, 51.51];
const KAIFENG: [number, number] = [114.35, 34.8];
const SYDNEY: [number, number] = [151.21, -33.87];
const LIMA: [number, number] = [-77.04, -12.05];

describe('rows', () => {
  it('shows five rows in the sidebar and six on the page', () => {
    expect(ON_THIS_DAY_ROWS).toEqual({ panel: 5, page: 6 });
  });

  it('takes the year from the first event, else from the first row', () => {
    const person = { id: 'p', entity_group: 'polity' as const };
    const state = { id: 's', entity_group: 'polity' as const };
    const battle = { id: 'b', entity_group: 'event' as const };
    const war = { id: 'w', entity_group: 'event' as const };
    expect(yearAnchor([person, battle, war])).toBe(battle);
    expect(yearAnchor([person, state])).toBe(person);
    expect(yearAnchor([])).toBeNull();
  });

  it('lists a repeated suggestion once, where it first came', () => {
    const rows = [
      { id: 'cannae', via: 'hannibal' },
      { id: 'zama', via: 'hannibal' },
      { id: 'cannae', via: 'second-punic-war' },
    ];
    expect(uniqueBy(rows, (row) => row.id)).toEqual([rows[0], rows[1]]);
    expect(uniqueBy([], (row: { id: string }) => row.id)).toEqual([]);
  });
});

describe('distanceKm', () => {
  it('measures along the globe', () => {
    expect(distanceKm(LONDON, LONDON)).toBe(0);
    // London to Sydney is about 17,000 km.
    expect(distanceKm(LONDON, SYDNEY)).toBeGreaterThan(16_500);
    expect(distanceKm(LONDON, SYDNEY)).toBeLessThan(17_500);
    expect(distanceKm(SYDNEY, LONDON)).toBeCloseTo(distanceKm(LONDON, SYDNEY), 6);
    // Across the date line the short way round, not the long one.
    expect(distanceKm([179, 0], [-179, 0])).toBeLessThan(250);
  });
});

describe('farthestEvents', () => {
  it('needs two regions with an event', () => {
    expect(farthestEvents([])).toBeNull();
    expect(farthestEvents([region('europe', entity('Hastings', LONDON)), region('east-asia', null)])).toBeNull();
  });

  it('picks the two events farthest apart, in the order given', () => {
    const regions = [
      region('south-america', entity('Lima', LIMA)),
      region('europe', entity('Hastings', LONDON)),
      region('sub-saharan-africa', null),
      region('east-asia', entity('Kaifeng', KAIFENG)),
      region('oceania', entity('Sydney', SYDNEY)),
    ];
    // Lima–Kaifeng (about 17,200 km) beats London–Sydney (about 17,000) and the list's two ends
    // (Lima–Sydney, about 12,800).
    const pair = farthestEvents(regions);
    expect(pair?.map((r) => r.key)).toEqual(['south-america', 'east-asia']);
  });

  it('falls back to the first and the last region when the events have no map point', () => {
    const regions = [
      region('north-america', entity('A', null)),
      region('europe', entity('B', null)),
      region('east-asia', entity('C', null)),
    ];
    expect(farthestEvents(regions)?.map((r) => r.key)).toEqual(['north-america', 'east-asia']);
  });

  it('prefers a placed pair to an unplaced one', () => {
    const regions = [
      region('north-america', entity('A', null)),
      region('europe', entity('Hastings', LONDON)),
      region('east-asia', entity('Kaifeng', KAIFENG)),
    ];
    expect(farthestEvents(regions)?.map((r) => r.key)).toEqual(['europe', 'east-asia']);
  });
});

describe('leadEvents', () => {
  const during = (name: string, at: [number, number], start: number, end: number | null) => ({
    ...entity(name, at),
    start_year: start,
    end_year: end,
  });

  it('knows when an event was under way in a year', () => {
    expect(underWay({ start_year: 1066, end_year: 1066 }, 1066)).toBe(true);
    expect(underWay({ start_year: 1060, end_year: 1070 }, 1066)).toBe(true);
    expect(underWay({ start_year: 1066, end_year: null }, 1066)).toBe(true);
    expect(underWay({ start_year: 1071, end_year: 1071 }, 1066)).toBe(false);
    expect(underWay({ start_year: 1060, end_year: null }, 1066)).toBe(false);
    expect(underWay({ start_year: null, end_year: 1070 }, 1066)).toBe(false);
  });

  it('prefers the events of that very year, even when others are farther apart', () => {
    const regions = [
      region('south-america', during('Lima', LIMA, 1071, 1071)),
      region('europe', during('Hastings', LONDON, 1066, 1066)),
      region('east-asia', during('Kaifeng', KAIFENG, 1060, 1070)),
      region('oceania', during('Sydney', SYDNEY, 1058, 1058)),
    ];
    const lead = leadEvents(regions, 1066);
    expect(lead?.sameYear).toBe(true);
    expect(lead?.pair.map((r) => r.key)).toEqual(['europe', 'east-asia']);
  });

  it('falls back to the events around the year, and says they are not of one year', () => {
    const regions = [
      region('south-america', during('Lima', LIMA, 1071, 1071)),
      region('europe', during('Hastings', LONDON, 1066, 1066)),
      region('east-asia', during('Kaifeng', KAIFENG, 1058, 1058)),
    ];
    const lead = leadEvents(regions, 1066);
    expect(lead?.sameYear).toBe(false);
    expect(lead?.pair.map((r) => r.key)).toEqual(['south-america', 'east-asia']);
  });

  it('is nothing with fewer than two events', () => {
    expect(leadEvents([region('europe', during('Hastings', LONDON, 1066, 1066)), region('oceania', null)], 1066)).toBeNull();
    expect(leadEvents([], 1066)).toBeNull();
  });
});

describe('offYear', () => {
  it('is the event’s year when the card’s year falls outside it', () => {
    expect(offYear({ start_year: 1071, end_year: 1071 }, 1066)).toBe(1071);
    expect(offYear({ start_year: 1060, end_year: null }, 1066)).toBe(1060);
    expect(offYear({ start_year: 1040, end_year: 1050 }, 1066)).toBe(1040);
  });

  it('is nothing when the event was under way that year, or has no year', () => {
    expect(offYear({ start_year: 1066, end_year: 1066 }, 1066)).toBeNull();
    expect(offYear({ start_year: 1066, end_year: null }, 1066)).toBeNull();
    expect(offYear({ start_year: 1060, end_year: 1070 }, 1066)).toBeNull();
    expect(offYear({ start_year: null, end_year: 1070 }, 1066)).toBeNull();
  });
});

describe('spread', () => {
  const eleven = Array.from({ length: 11 }, (_, i) => i);

  it('keeps a short list whole', () => {
    expect(spread([1, 2, 3], 4)).toEqual([1, 2, 3]);
    expect(spread([1, 2, 3, 4], 4)).toEqual([1, 2, 3, 4]);
    expect(spread([], 4)).toEqual([]);
  });

  it('samples a long one evenly, both ends included, in order', () => {
    expect(spread(eleven, 4)).toEqual([0, 3, 7, 10]);
    expect(spread(eleven.slice(0, 10), 4)).toEqual([0, 3, 6, 9]);
    expect(spread([0, 1, 2, 3, 4], 4)).toEqual([0, 1, 3, 4]);
    expect(spread(eleven, 2)).toEqual([0, 10]);
    expect(spread(eleven, 1)).toEqual([0]);
    expect(spread(eleven, 0)).toEqual([]);
  });

  it('never repeats an item', () => {
    for (let n = 5; n <= 12; n += 1) {
      const picked = spread(Array.from({ length: n }, (_, i) => i), 4);
      expect(new Set(picked).size, `of ${n}`).toBe(4);
    }
  });
});
