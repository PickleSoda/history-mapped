/**
 * Raw API payloads for the browse tests (GET /collections, /collections/{slug},
 * /map-stories, /tags), shaped like the contract in spec 2026-11-01 public
 * site, D4. Test-only: imported by `*.test.ts`, never by app code.
 */

export const entityRow = {
  id: '6f1c2f4e-0000-4000-8000-000000000001',
  name: 'Roman Empire',
  entity_type: 'political_entity',
  entity_group: 'POLITY',
  summary: 'The post-Republic state of ancient Rome.',
  tags: ['classical', 'europe', 'italy', 'empires-states'],
  impact_score: 100,
  temporal_start: '-27',
  temporal_end: '476',
  temporal_display_range: null,
  era_label: null,
  location_name: 'Rome',
  geom: '{"type": "Point", "coordinates": [12.5, 41.9]}',
  verification_status: 'pipeline_draft',
  confidence: null,
  display_priority: 100,
  icon_class: null,
  entity_color: null,
  created_at: '2026-10-05T15:27:10.000000Z',
};

export const chronicleRow = {
  chronicle_id: '7a0cc374-73c9-44ed-b28f-1c57b23a5b9d',
  title: 'The Roman World',
  slug: 'the-roman-world',
  description: 'From the founding of the city to the fall of the West.',
  source_type: 'video_transcript',
  start_year: -753,
  end_year: 476,
  impact_score: 94,
  entry_count: 80,
  status: 'published',
  tags: ['classical', 'europe', 'italy', 'mediterranean', 'polity'],
  map_story: null,
};

export const storyRow = {
  id: '9b1d0000-0000-4000-8000-000000000003',
  slug: 'battle-of-cannae',
  kind: 'battle',
  title: 'Battle of Cannae',
  year: -216,
  step_count: 7,
  entity: { id: '6f1c2f4e-0000-4000-8000-000000000002', name: 'Battle of Cannae', entity_type: 'battle' },
  chronicle: null,
};

export const tagRow = {
  slug: 'classical',
  name: 'Classical Era',
  facet: 'era',
  parent: null,
  description: 'c. 500 BCE – 500 CE: Greece and Rome, Persia, the Maurya and Gupta, Qin and Han.',
  start_year: -500,
  end_year: 499,
  chronicle_count: 68,
  entity_count: 6142,
};

export const collectionSummaryRow = {
  slug: 'the-roman-world',
  title: 'The Roman world',
  subtitle: 'From city-state to empire',
  description: 'Rome grew from a hill town to a Mediterranean empire.\n\nSee [the Roman Empire](/entities/abc) and [Wikipedia](https://en.wikipedia.org/wiki/Ancient_Rome).',
  cover: entityRow,
  item_count: 4,
  items_by_kind: { entity: 1, chronicle: 1, story: 1, tag: 1 },
  sort_order: 10,
};

export const collectionListPayload = {
  data: [
    collectionSummaryRow,
    {
      slug: 'great-battles',
      title: 'Great battles',
      subtitle: null,
      description: null,
      cover: null,
      item_count: 0,
      items_by_kind: { entity: 0, chronicle: 0, story: 0, tag: 0 },
    },
  ],
};

export const collectionDetailPayload = {
  data: {
    ...collectionSummaryRow,
    items: [
      { kind: 'chronicle', note: 'Start here.', chronicle: chronicleRow },
      { kind: 'story', note: null, story: storyRow },
      { kind: 'entity', entity: entityRow },
      { kind: 'tag', note: 'Everything from the period.', tag: tagRow },
      // Dropped: a kind without its payload, an unknown kind, a malformed payload.
      { kind: 'entity', note: 'missing payload' },
      { kind: 'poem', note: null },
      { kind: 'chronicle', note: null, chronicle: { title: 'no slug' } },
    ],
  },
};

export const mapStoryListPayload = {
  data: [
    storyRow,
    {
      id: '9b1d0000-0000-4000-8000-000000000004',
      slug: 'siege-of-alesia',
      kind: 'siege',
      title: 'Siege of Alesia',
      year: -52,
      step_count: 6,
      entity: null,
      chronicle: { slug: 'gallic-wars', title: 'The Gallic Wars' },
    },
    {
      id: '9b1d0000-0000-4000-8000-000000000005',
      slug: 'black-death',
      kind: 'epidemic',
      title: 'The Black Death',
      year: null,
      step_count: null,
      entity: { id: 'e5', name: 'Black Death' },
      chronicle: 'not-an-object',
      extra_field: true,
    },
  ],
  links: { first: null, last: null, prev: null, next: null },
  meta: { current_page: 1, from: 1, last_page: 2, per_page: 3, total: 5, path: '/api/v1/map-stories' },
};
