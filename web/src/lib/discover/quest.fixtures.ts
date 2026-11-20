/**
 * A raw GET /discover/quest payload for the expedition's tests, shaped like
 * the contract in the Discover design spec (§3.3). Test-only: imported by
 * `*.test.ts`, never by app code.
 */

export const HASTINGS = '6f1c2f4e-0000-4000-8000-00000000a001';
export const MAGDALA = '6f1c2f4e-0000-4000-8000-00000000a002';
export const CANNAE = '6f1c2f4e-0000-4000-8000-00000000a003';

export const questPayload = {
  data: {
    date: '2026-11-20',
    number: 12,
    targets: [
      {
        id: HASTINGS,
        name: 'Battle of Hastings',
        entity_type: 'event_battle',
        entity_group: 'EVENT',
        summary:
          'Fought on 14 October 1066 between the Norman-French army of William of Normandy and an English army under King Harold Godwinson.',
        start_year: 1066,
        end_year: 1066,
        at: [0.49, 50.91],
        has_map_story: true,
        difficulty: 'easy',
        year: 1066,
        region: 'Europe',
        place: 'East Sussex, England',
      },
      {
        id: MAGDALA,
        name: 'Battle of Magdala',
        entity_type: 'event_battle',
        entity_group: 'EVENT',
        summary:
          '1868 battle where British General Robert Napier defeated Emperor Tewodros II, ending Ethiopian imperial power.',
        start_year: 1868,
        end_year: 1868,
        at: [39.18, 11.35],
        has_map_story: false,
        difficulty: 'medium',
        year: 1868,
        region: 'Sub-Saharan Africa',
        place: 'Amhara, Ethiopia',
      },
      {
        id: CANNAE,
        name: 'Battle of Cannae',
        entity_type: 'event_battle',
        entity_group: 'EVENT',
        summary:
          'Fought in 216 BCE, when the army of Hannibal surrounded and destroyed a Roman force of 80,000 men in Apulia.',
        start_year: -216,
        end_year: null,
        at: [16.13, 41.31],
        has_map_story: true,
        difficulty: 'hard',
        year: -216,
        region: 'Europe',
        place: null,
      },
    ],
  },
};
