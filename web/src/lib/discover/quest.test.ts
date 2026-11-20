import { describe, expect, it } from 'vitest';
import { QuestSchema } from '@/lib/schemas/discover';
import {
  clueText,
  compassBearing,
  compassPoint,
  completeStreak,
  distanceKm,
  eighthTurn,
  expeditionName,
  hasArrived,
  HIDDEN_YEAR,
  hideYears,
  kmText,
  needsZoomIn,
  NO_PROGRESS,
  NO_STREAK,
  placeWarmth,
  readTime,
  roundKm,
  sameLevels,
  sameReading,
  shareText,
  standingStreak,
  starRow,
  starsFor,
  takeReading,
  tally,
  targetSpan,
  timeWarmth,
  warmthSteps,
  yearsFromSpan,
  yearsShown,
} from './quest';
import type { MapView } from './quest';
import { CANNAE, HASTINGS, MAGDALA, questPayload } from './quest.fixtures';

const quest = QuestSchema.parse(questPayload.data);
const [hastings, magdala, cannae] = quest.targets;
/** A siege that lasted years. */
const candia = { id: 'candia', year: 1648, start_year: 1648, end_year: 1669 };

describe('warmthSteps', () => {
  it('fills one step more for each warmth', () => {
    expect((['cold', 'cool', 'warm', 'hot', 'here'] as const).map(warmthSteps)).toEqual([1, 2, 3, 4, 5]);
  });
});

describe('targetSpan', () => {
  it('is one year for a target with no end, or without its own start', () => {
    expect(targetSpan(cannae)).toEqual([-216, -216]);
    expect(targetSpan({ year: 1066, start_year: null, end_year: null })).toEqual([1066, 1066]);
  });

  it('runs from the first year to the last', () => {
    expect(targetSpan(candia)).toEqual([1648, 1669]);
  });

  it('ignores an end before the start and always holds the year to be in', () => {
    expect(targetSpan({ year: 1066, start_year: 1066, end_year: 1060 })).toEqual([1066, 1066]);
    expect(targetSpan({ year: 1070, start_year: 1066, end_year: 1068 })).toEqual([1066, 1070]);
  });
});

describe('warmth in time', () => {
  it('counts the years to the span, none inside it', () => {
    expect(yearsFromSpan(1640, [1648, 1669])).toBe(8);
    expect(yearsFromSpan(1648, [1648, 1669])).toBe(0);
    expect(yearsFromSpan(1660, [1648, 1669])).toBe(0);
    expect(yearsFromSpan(1700, [1648, 1669])).toBe(31);
  });

  it.each([
    [0, 'here'],
    [10, 'here'],
    [11, 'hot'],
    [50, 'hot'],
    [51, 'warm'],
    [200, 'warm'],
    [201, 'cool'],
    [800, 'cool'],
    [801, 'cold'],
    [5000, 'cold'],
  ] as const)('%i years away is %s', (years, warmth) => {
    expect(timeWarmth(years)).toBe(warmth);
  });

  it.each([
    [1066, 'here', null],
    [1076, 'here', 'earlier'],
    [1077, 'hot', 'earlier'],
    [1116, 'hot', 'earlier'],
    [1117, 'warm', 'earlier'],
    [1266, 'warm', 'earlier'],
    [1267, 'cool', 'earlier'],
    [1866, 'cool', 'earlier'],
    [1867, 'cold', 'earlier'],
    [1056, 'here', 'later'],
    [1055, 'hot', 'later'],
    [1016, 'hot', 'later'],
    [1015, 'warm', 'later'],
    [866, 'warm', 'later'],
    [865, 'cool', 'later'],
    [266, 'cool', 'later'],
    [265, 'cold', 'later'],
    [-3000, 'cold', 'later'],
  ] as const)('a single year (1066) from %i: %s, target %s', (year, warmth, direction) => {
    expect(readTime(year, hastings)).toEqual({ warmth, direction });
  });

  it.each([
    [1648, 'here', null],
    [1660, 'here', null],
    [1669, 'here', null],
    [1638, 'here', 'later'],
    [1637, 'hot', 'later'],
    [1598, 'hot', 'later'],
    [1597, 'warm', 'later'],
    [1679, 'here', 'earlier'],
    [1680, 'hot', 'earlier'],
    [1719, 'hot', 'earlier'],
    [1720, 'warm', 'earlier'],
    [1869, 'warm', 'earlier'],
    [1870, 'cool', 'earlier'],
    [2469, 'cool', 'earlier'],
    [2470, 'cold', 'earlier'],
  ] as const)('a span of years (1648–1669) from %i: %s, target %s', (year, warmth, direction) => {
    expect(readTime(year, candia)).toEqual({ warmth, direction });
  });

  it.each([
    [-216, 'here', null],
    [-226, 'here', 'later'],
    [-227, 'hot', 'later'],
    [-266, 'hot', 'later'],
    [-267, 'warm', 'later'],
    [-416, 'warm', 'later'],
    [-417, 'cool', 'later'],
    [-1016, 'cool', 'later'],
    [-1017, 'cold', 'later'],
    [-206, 'here', 'earlier'],
    [-205, 'hot', 'earlier'],
    [-166, 'hot', 'earlier'],
    [-165, 'warm', 'earlier'],
    [-16, 'warm', 'earlier'],
    [-15, 'cool', 'earlier'],
    [1, 'cool', 'earlier'],
    [584, 'cool', 'earlier'],
    [585, 'cold', 'earlier'],
    [2026, 'cold', 'earlier'],
  ] as const)('a year BCE (216 BCE) from %i: %s, target %s', (year, warmth, direction) => {
    expect(readTime(year, cannae)).toEqual({ warmth, direction });
  });
});

describe('warmth in place', () => {
  const far = { inView: false, diagonalKm: 20_000 };

  it.each([
    [0, 'hot'],
    [800, 'hot'],
    [800.1, 'warm'],
    [2500, 'warm'],
    [2500.1, 'cool'],
    [6000, 'cool'],
    [6000.1, 'cold'],
    [19_000, 'cold'],
  ] as const)('%d km from the middle of the map is %s', (km, warmth) => {
    expect(placeWarmth({ km, ...far })).toBe(warmth);
  });

  it('is here when the target is in view and the view is no wider than a region', () => {
    expect(placeWarmth({ km: 0, inView: true, diagonalKm: 3000 })).toBe('here');
    expect(placeWarmth({ km: 1400, inView: true, diagonalKm: 3000 })).toBe('here');
    expect(placeWarmth({ km: 5, inView: true, diagonalKm: 40 })).toBe('here');
  });

  it('is not here on a wider view, however near the middle the target is', () => {
    expect(placeWarmth({ km: 0, inView: true, diagonalKm: 3000.1 })).toBe('hot');
    expect(placeWarmth({ km: 2000, inView: true, diagonalKm: 9000 })).toBe('warm');
    expect(placeWarmth({ km: 7000, inView: true, diagonalKm: 30_000 })).toBe('cold');
  });

  it('is not here when the target is out of view, however close the view', () => {
    expect(placeWarmth({ km: 100, inView: false, diagonalKm: 150 })).toBe('hot');
    expect(placeWarmth({ km: 900, inView: false, diagonalKm: 2900 })).toBe('warm');
  });

  it('is cold for a map that cannot be measured', () => {
    expect(placeWarmth({ km: Number.NaN, inView: false, diagonalKm: Number.NaN })).toBe('cold');
    expect(placeWarmth({ km: 10, inView: true, diagonalKm: Number.NaN })).toBe('hot');
  });

  it('asks to zoom in only when hot, in view, and too wide a view', () => {
    expect(needsZoomIn({ km: 300, inView: true, diagonalKm: 5000 })).toBe(true);
    expect(needsZoomIn({ km: 300, inView: true, diagonalKm: 3000 })).toBe(false);
    expect(needsZoomIn({ km: 300, inView: false, diagonalKm: 5000 })).toBe(false);
    expect(needsZoomIn({ km: 900, inView: true, diagonalKm: 5000 })).toBe(false);
  });
});

describe('hasArrived', () => {
  it('needs both the time and the place', () => {
    expect(hasArrived('here', 'here')).toBe(true);
    expect(hasArrived('hot', 'here')).toBe(false);
    expect(hasArrived('here', 'hot')).toBe(false);
    expect(hasArrived('here', null)).toBe(false);
  });
});

describe('distance and direction', () => {
  const london: [number, number] = [-0.1276, 51.5072];
  const paris: [number, number] = [2.3522, 48.8566];
  const tokyo: [number, number] = [139.6917, 35.6895];

  it('measures great-circle km', () => {
    expect(distanceKm(london, london)).toBe(0);
    expect(distanceKm(london, paris)).toBeGreaterThan(340);
    expect(distanceKm(london, paris)).toBeLessThan(347);
    expect(distanceKm([0, 0], [1, 0])).toBeCloseTo(111.195, 2);
    expect(distanceKm([0, 0], [180, 0])).toBeCloseTo(20015.1, 0);
    // The short way round, whatever the longitudes are written as.
    expect(distanceKm([179, 0], [-179, 0])).toBeCloseTo(222.39, 1);
    expect(distanceKm([179, 0], [181, 0])).toBeCloseTo(222.39, 1);
  });

  it('gives the bearing to hold on the map', () => {
    expect(compassBearing([0, 0], [0, 10])).toBeCloseTo(0);
    expect(compassBearing([0, 0], [10, 0])).toBeCloseTo(90);
    expect(compassBearing([0, 0], [0, -10])).toBeCloseTo(180);
    expect(compassBearing([0, 0], [-10, 0])).toBeCloseTo(270);
    expect(compassBearing([10, 10], [20, 19.72])).toBeCloseTo(45, 0);
    // Tokyo is east of London on the map (the great circle would set off north-east).
    expect(compassPoint(compassBearing(london, tokyo))).toBe('E');
    expect(compassPoint(compassBearing(tokyo, london))).toBe('W');
  });

  it('goes the short way across the date line', () => {
    expect(compassBearing([170, 0], [-170, 0])).toBeCloseTo(90);
    expect(compassBearing([-170, 10], [170, 10])).toBeCloseTo(270);
    expect(compassBearing([530, 0], [-170, 0])).toBeCloseTo(90);
  });

  it('stays finite at the poles', () => {
    expect(compassBearing([0, 80], [0, 90])).toBeCloseTo(0);
    expect(Number.isFinite(compassBearing([10, -90], [50, 90]))).toBe(true);
  });

  it.each([
    [0, 'N'],
    [22.4, 'N'],
    [22.5, 'NE'],
    [45, 'NE'],
    [67.4, 'NE'],
    [67.5, 'E'],
    [90, 'E'],
    [135, 'SE'],
    [180, 'S'],
    [225, 'SW'],
    [270, 'W'],
    [315, 'NW'],
    [337.4, 'NW'],
    [337.5, 'N'],
    [360, 'N'],
    [405, 'NE'],
    [-45, 'NW'],
    [-90, 'W'],
  ] as const)('a bearing of %d is %s', (bearing, point) => {
    expect(compassPoint(bearing)).toBe(point);
  });

  it('counts eighths of a turn from north', () => {
    expect([0, 45, 90, 135, 180, 225, 270, 315, 360, -90].map(eighthTurn)).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 0, 6]);
  });

  it('rounds a distance the way it is shown', () => {
    expect([4, 5, 44, 95, 130, 974, 1234, 9960, 12_345].map(roundKm)).toEqual([
      0, 10, 40, 100, 150, 950, 1200, 10_000, 12_500,
    ]);
    // Rounding again changes nothing: the rounded value can be stored and shown.
    for (const km of [4, 44, 97, 990, 9960, 12_345]) expect(roundKm(roundKm(km))).toBe(roundKm(km));
    expect(kmText(4)).toBe('under 10 km');
    expect(kmText(44)).toBe('about 40 km');
    expect(kmText(1234)).toBe('about 1,200 km');
    expect(kmText(12_345)).toBe('about 12,500 km');
  });
});

describe('takeReading', () => {
  const there: MapView = { km: 120, inView: true, diagonalKm: 1800, bearing: 44, screenBearing: 134 };
  const wide: MapView = { km: 120, inView: true, diagonalKm: 9000, bearing: 44, screenBearing: 44 };
  const away: MapView = { km: 4321, inView: false, diagonalKm: 2000, bearing: 200, screenBearing: 200 };

  it('reads the time alone until the map is ready', () => {
    expect(takeReading(hastings, { shown: 1100, committed: 1100 }, null)).toEqual({
      id: HASTINGS,
      time: 'hot',
      direction: 'earlier',
      place: null,
      zoomIn: false,
      compass: null,
      arrow: null,
      km: null,
      arrived: false,
    });
  });

  it('has arrived when the year and the view are both there', () => {
    expect(takeReading(hastings, { shown: 1066, committed: 1066 }, there)).toEqual({
      id: HASTINGS,
      time: 'here',
      direction: null,
      place: 'here',
      zoomIn: false,
      compass: 'NE',
      arrow: 3,
      km: 100,
      arrived: true,
    });
  });

  it('has not arrived in the right year on too wide a view, and says to zoom in', () => {
    const reading = takeReading(hastings, { shown: 1066, committed: 1066 }, wide);
    expect(reading).toMatchObject({ time: 'here', place: 'hot', zoomIn: true, arrived: false });
  });

  it('has not arrived in the right place in the wrong year', () => {
    const reading = takeReading(hastings, { shown: 1500, committed: 1500 }, there);
    expect(reading).toMatchObject({ time: 'cool', direction: 'earlier', place: 'here', arrived: false });
  });

  it('shows the warmth of the year being dragged, but arrives only on the year the map is at', () => {
    // Dragging the timeline over the target's year: warm words, no marker yet.
    expect(takeReading(hastings, { shown: 1066, committed: 1500 }, there)).toMatchObject({
      time: 'here',
      arrived: false,
    });
    // Dragging away from it: the marker stays until the year is let go.
    expect(takeReading(hastings, { shown: 1500, committed: 1066 }, there)).toMatchObject({
      time: 'cool',
      arrived: true,
    });
  });

  it('gives the way to a target that is not under the middle of the map', () => {
    expect(takeReading(magdala, { shown: 1868, committed: 1868 }, away)).toMatchObject({
      place: 'cool',
      compass: 'S',
      arrow: 4,
      km: 4300,
    });
    const onTop = takeReading(magdala, { shown: 1868, committed: 1868 }, { ...there, km: 4 });
    expect(onTop).toMatchObject({ compass: null, arrow: null, km: 0 });
  });

  it('tells a change of level from a change of distance', () => {
    const a = takeReading(magdala, { shown: 1868, committed: 1868 }, away);
    const nearer = takeReading(magdala, { shown: 1868, committed: 1868 }, { ...away, km: 4100 });
    const warmer = takeReading(magdala, { shown: 1868, committed: 1868 }, { ...away, km: 2400 });
    expect(sameReading(a, { ...a })).toBe(true);
    expect(sameLevels(a, nearer)).toBe(true);
    expect(sameReading(a, nearer)).toBe(false);
    expect(sameLevels(a, warmer)).toBe(false);
    expect(sameLevels(a, { ...a, id: CANNAE })).toBe(false);
    expect(sameLevels(a, { ...a, arrived: true })).toBe(false);
    expect(sameLevels(a, { ...a, direction: 'later' })).toBe(false);
    expect(sameLevels(a, { ...a, zoomIn: true })).toBe(false);
    expect(sameReading(a, { ...a, compass: 'N' })).toBe(false);
    expect(sameReading(a, { ...a, arrow: 0 })).toBe(false);
  });
});

describe('stars', () => {
  it.each([
    [false, false, false, 3],
    [true, false, false, 2],
    [false, true, false, 2],
    [true, true, false, 1],
    [false, false, true, 0],
    [true, false, true, 0],
    [false, true, true, 0],
    [true, true, true, 0],
  ])('when %s, where %s, taken %s: %i', (when, where, taken, stars) => {
    expect(starsFor({ when, where, taken })).toBe(stars);
  });

  it('tallies the day', () => {
    const ids = [HASTINGS, MAGDALA, CANNAE];
    const found = { ...NO_PROGRESS, found: true };
    expect(tally(ids, {})).toEqual({ found: 0, stars: 0, complete: false });
    expect(
      tally(ids, { [HASTINGS]: found, [MAGDALA]: { ...found, when: true }, [CANNAE]: { ...NO_PROGRESS, where: true } }),
    ).toEqual({ found: 2, stars: 5, complete: false });
    expect(
      tally(ids, { [HASTINGS]: found, [MAGDALA]: { ...found, when: true, where: true }, [CANNAE]: { ...found, taken: true } }),
    ).toEqual({ found: 3, stars: 4, complete: true });
  });

  it('never calls an empty day complete, and counts only the day’s own targets', () => {
    const found = { ...NO_PROGRESS, found: true };
    expect(tally([], { stray: found })).toEqual({ found: 0, stars: 0, complete: false });
    expect(tally([HASTINGS], { [HASTINGS]: found, stray: found })).toEqual({ found: 1, stars: 3, complete: true });
  });
});

describe('streak', () => {
  it('starts at 1 the first time ever', () => {
    expect(completeStreak(NO_STREAK, '2026-11-20')).toEqual({ count: 1, last: '2026-11-20' });
  });

  it('grows on the day after the last complete one', () => {
    expect(completeStreak({ count: 3, last: '2026-11-19' }, '2026-11-20')).toEqual({ count: 4, last: '2026-11-20' });
    expect(completeStreak({ count: 2, last: '2026-11-30' }, '2026-12-01')).toEqual({ count: 3, last: '2026-12-01' });
    expect(completeStreak({ count: 9, last: '2026-12-31' }, '2027-01-01')).toEqual({ count: 10, last: '2027-01-01' });
    expect(completeStreak({ count: 1, last: '2028-02-29' }, '2028-03-01')).toEqual({ count: 2, last: '2028-03-01' });
  });

  it('starts again at 1 after a gap', () => {
    expect(completeStreak({ count: 7, last: '2026-11-18' }, '2026-11-20')).toEqual({ count: 1, last: '2026-11-20' });
    expect(completeStreak({ count: 7, last: '2025-11-19' }, '2026-11-20')).toEqual({ count: 1, last: '2026-11-20' });
  });

  it('counts a day once', () => {
    const streak = { count: 4, last: '2026-11-20' };
    expect(completeStreak(streak, '2026-11-20')).toBe(streak);
    expect(completeStreak(completeStreak({ count: 3, last: '2026-11-19' }, '2026-11-20'), '2026-11-20')).toEqual({
      count: 4,
      last: '2026-11-20',
    });
  });

  it('leaves a streak whose last day is ahead of today (a change of time zone) as it is', () => {
    const streak = { count: 4, last: '2026-11-21' };
    expect(completeStreak(streak, '2026-11-20')).toBe(streak);
    expect(standingStreak(streak, '2026-11-20')).toBe(4);
  });

  it('stands through the day after, then is gone', () => {
    const streak = { count: 5, last: '2026-11-20' };
    expect(standingStreak(streak, '2026-11-20')).toBe(5);
    expect(standingStreak(streak, '2026-11-21')).toBe(5);
    expect(standingStreak(streak, '2026-11-22')).toBe(0);
    expect(standingStreak(NO_STREAK, '2026-11-20')).toBe(0);
  });
});

describe('the clue', () => {
  it('leaves the year out of a summary', () => {
    expect(hideYears(hastings.summary ?? '', hastings)).toBe(
      `Fought on 14 October ${HIDDEN_YEAR} between the Norman-French army of William of Normandy and an English army under King Harold Godwinson.`,
    );
    expect(hideYears(magdala.summary ?? '', magdala)).toBe(
      `${HIDDEN_YEAR} battle where British General Robert Napier defeated Emperor Tewodros II, ending Ethiopian imperial power.`,
    );
  });

  it('leaves a year BCE out, and grouped numbers in', () => {
    expect(hideYears(cannae.summary ?? '', cannae)).toBe(
      `Fought in ${HIDDEN_YEAR} BCE, when the army of Hannibal surrounded and destroyed a Roman force of 80,000 men in Apulia.`,
    );
  });

  it('leaves out every year of a span, decades, and years in a name', () => {
    expect(hideYears('The siege ran from 1648 to 1669, all of 21 years.', candia)).toBe(
      `The siege ran from ${HIDDEN_YEAR} to ${HIDDEN_YEAR}, all of 21 years.`,
    );
    expect(hideYears('A raid of the 1860s.', magdala)).toBe(`A raid of the ${HIDDEN_YEAR}s.`);
    expect(hideYears('Siege of Paris (1870–1871)', { year: 1870, start_year: 1870, end_year: 1871 })).toBe(
      `Siege of Paris (${HIDDEN_YEAR}–${HIDDEN_YEAR})`,
    );
  });

  it('leaves out a year of one or two digits when it is the target’s own', () => {
    const pharsalus = { year: -48, start_year: -48, end_year: -48 };
    expect(hideYears('Decisive battle on 9 August 48 BCE where Caesar defeated Pompey.', pharsalus)).toBe(
      `Decisive battle on 9 August ${HIDDEN_YEAR} BCE where Caesar defeated Pompey.`,
    );
    const teutoburg = { year: 9, start_year: 9, end_year: 9 };
    expect(hideYears('In 9 CE three legions were lost.', teutoburg)).toBe(`In ${HIDDEN_YEAR} CE three legions were lost.`);
    expect(hideYears('Fought between year 5 and 12.', { year: 5, start_year: 5, end_year: 9 })).toBe(
      `Fought between year ${HIDDEN_YEAR} and 12.`,
    );
  });

  it('keeps a count that could not be a year near the target’s', () => {
    const crisis = { year: 1979, start_year: 1979, end_year: 1981 };
    expect(
      hideYears('Seizure of the US embassy in Tehran in November 1979, with hostages held for 444 days.', crisis),
    ).toBe(`Seizure of the US embassy in Tehran in November ${HIDDEN_YEAR}, with hostages held for 444 days.`);
    const ghodKhind = { year: 1660, start_year: 1660, end_year: 1660 };
    expect(hideYears('On 22 September 1660 CE Baji Prabhu Deshpande and 300 Maratha soldiers held the pass.', ghodKhind)).toBe(
      `On 22 September ${HIDDEN_YEAR} CE Baji Prabhu Deshpande and 300 Maratha soldiers held the pass.`,
    );
    // Another year close by would give it away as well; one centuries off would not.
    expect(hideYears('The first such defeat since 1757, and the worst since 1066.', magdala)).toBe(
      `The first such defeat since ${HIDDEN_YEAR}, and the worst since 1066.`,
    );
    expect(hideYears('Won 200 years before 68 CE and 200 after.', { year: 68, start_year: 68, end_year: 68 })).toBe(
      `Won ${HIDDEN_YEAR} years before ${HIDDEN_YEAR} CE and ${HIDDEN_YEAR} after.`,
    );
  });

  it('keeps ordinals, long numbers and decimals', () => {
    const early = { year: 3, start_year: 3, end_year: 3 };
    expect(hideYears('A 3rd attack, the 19th of its kind, on the 216th day.', early)).toBe(
      'A 3rd attack, the 19th of its kind, on the 216th day.',
    );
    expect(hideYears('12000 men marched 3.5 km and 1,200 fell.', hastings)).toBe('12000 men marched 3.5 km and 1,200 fell.');
  });

  it('gives a text with no number back as it is', () => {
    expect(hideYears('Battle of Hastings', hastings)).toBe('Battle of Hastings');
    expect(hideYears('', hastings)).toBe('');
  });

  it('shows the years once the reader has them', () => {
    expect(yearsShown(undefined)).toBe(false);
    expect(yearsShown(NO_PROGRESS)).toBe(false);
    expect(yearsShown({ ...NO_PROGRESS, where: true })).toBe(false);
    expect(yearsShown({ ...NO_PROGRESS, when: true })).toBe(true);
    expect(yearsShown({ ...NO_PROGRESS, taken: true })).toBe(true);
    expect(yearsShown({ ...NO_PROGRESS, found: true })).toBe(true);
    const summary = magdala.summary ?? '';
    expect(clueText(summary, magdala, undefined)).toContain(HIDDEN_YEAR);
    expect(clueText(summary, magdala, { ...NO_PROGRESS, where: true })).toContain(HIDDEN_YEAR);
    expect(clueText(summary, magdala, { ...NO_PROGRESS, when: true })).toBe(summary);
    expect(clueText(summary, magdala, { ...NO_PROGRESS, found: true })).toBe(summary);
  });
});

describe('the result to share', () => {
  it('draws stars', () => {
    expect([0, 1, 2, 3].map((n) => starRow(n))).toEqual(['☆☆☆', '★☆☆', '★★☆', '★★★']);
    expect(starRow(7)).toBe('★★★');
    expect(starRow(-1)).toBe('☆☆☆');
  });

  it('is the number, a row of stars per target and the address, with no names', () => {
    const text = shareText(
      12,
      [
        { difficulty: 'easy', stars: 3 },
        { difficulty: 'medium', stars: 2 },
        { difficulty: 'hard', stars: 0 },
      ],
      'https://example.org/browse',
    );
    expect(text).toBe(
      ['History Mapped · Expedition 12', '★★★ easy', '★★☆ medium', '☆☆☆ hard', 'https://example.org/browse'].join('\n'),
    );
    for (const target of quest.targets) expect(text).not.toContain(target.name);
  });

  it('names the expedition by its number, when it has one', () => {
    expect(expeditionName(12)).toBe('Expedition 12');
    expect(expeditionName(1)).toBe('Expedition 1');
    // A reader whose day is still the one before the first expedition.
    expect(expeditionName(0)).toBe('Expedition');
    expect(expeditionName(-1)).toBe('Expedition');
    expect(shareText(0, [{ difficulty: 'easy', stars: 1 }], 'https://example.org/browse')).toBe(
      'History Mapped · Expedition\n★☆☆ easy\nhttps://example.org/browse',
    );
  });
});
