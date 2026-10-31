import { describe, expect, it } from 'vitest';
import { MapStoryDocumentSchema } from '@/lib/schemas/map-story';
import { adminOrigins, carryEntityIds, isAllowedOrigin, parseAdminMessage, rejectedDocument, roundPoint } from './preview';

const ADMIN = 'http://localhost:8000';

const raw = {
  schema: 3,
  slug: 'battle-of-x',
  kind: 'battle',
  entity: { name: 'Battle of X', wikidata: 'Q1' },
  title: 'Battle of X',
  year: -100,
  sides: [{ id: 'red', name: 'Red', color: '#b91c1c', commanders: [{ name: 'Brutus', wikidata: 'Q2' }] }],
  units: [{ id: 'foot', side: 'red', kind: 'infantry', label: 'Foot' }],
  terrain: [{ id: 'river', kind: 'river', label: 'River', line: [[1, 2], [3, 4]] }],
  steps: [{ id: 's1', title: 'One', narrative: 'Text', positions: { foot: { at: [1, 2] } }, terrain_state: {} }],
};

describe('admin origins', () => {
  it('parses a comma-separated list and falls back to the dev admin', () => {
    expect(adminOrigins(' https://admin.example.org/ , http://localhost:8000,not a url ')).toEqual([
      'https://admin.example.org',
      'http://localhost:8000',
    ]);
    expect(adminOrigins(undefined)).toEqual([ADMIN]);
    expect(adminOrigins('')).toEqual([ADMIN]);
  });

  it('falls back to the API origin, which serves the admin too', () => {
    expect(adminOrigins(undefined, 'https://api.example.org/')).toEqual(['https://api.example.org']);
    expect(adminOrigins('', 'https://api.example.org:8443/v1')).toEqual(['https://api.example.org:8443']);
    expect(adminOrigins('https://admin.example.org', 'https://api.example.org')).toEqual(['https://admin.example.org']);
    expect(adminOrigins(undefined, '/api')).toEqual([ADMIN]);
  });

  it('matches origins exactly', () => {
    expect(isAllowedOrigin(ADMIN, [ADMIN])).toBe(true);
    expect(isAllowedOrigin('http://localhost:8001', [ADMIN])).toBe(false);
    expect(isAllowedOrigin('http://evil.example', [ADMIN])).toBe(false);
  });
});

describe('parseAdminMessage', () => {
  it('ignores messages from other origins, whatever they carry', () => {
    expect(parseAdminMessage('http://evil.example', { type: 'map-story:step', index: 2 }, [ADMIN])).toBeNull();
  });

  it('parses a draft document with the story schema (aliases normalised)', () => {
    const message = parseAdminMessage(ADMIN, { type: 'map-story:document', document: raw }, [ADMIN]);
    expect(message?.type).toBe('map-story:document');
    if (message?.type !== 'map-story:document') return;
    expect(message.document.features.map((f) => f.id)).toEqual(['river']);
    expect(message.document.steps[0].positions.foot.at).toEqual([1, 2]);
  });

  it('rejects malformed messages', () => {
    expect(parseAdminMessage(ADMIN, { type: 'map-story:document', document: { ...raw, steps: [] } }, [ADMIN])).toBeNull();
    expect(parseAdminMessage(ADMIN, { type: 'map-story:step', index: -1 }, [ADMIN])).toBeNull();
    expect(parseAdminMessage(ADMIN, { type: 'map-story:pick', mode: 'polygon' }, [ADMIN])).toBeNull();
    expect(parseAdminMessage(ADMIN, { type: 'something-else' }, [ADMIN])).toBeNull();
    expect(parseAdminMessage(ADMIN, 'map-story:ready', [ADMIN])).toBeNull();
    expect(parseAdminMessage(ADMIN, null, [ADMIN])).toBeNull();
  });

  it('parses step, pick and cancel', () => {
    expect(parseAdminMessage(ADMIN, { type: 'map-story:step', index: 3 }, [ADMIN])).toEqual({ type: 'map-story:step', index: 3 });
    expect(parseAdminMessage(ADMIN, { type: 'map-story:pick', mode: 'path' }, [ADMIN])).toEqual({ type: 'map-story:pick', mode: 'path' });
    expect(parseAdminMessage(ADMIN, { type: 'map-story:pick-cancel' }, [ADMIN])).toEqual({ type: 'map-story:pick-cancel' });
    expect(parseAdminMessage(ADMIN, { type: 'map-story:get-camera' }, [ADMIN])).toEqual({ type: 'map-story:get-camera' });
  });
});

describe('rejectedDocument', () => {
  it('names what the schema refused in a draft from the admin', () => {
    const issues = rejectedDocument(ADMIN, { type: 'map-story:document', document: { ...raw, steps: [] } }, [ADMIN]);
    expect(issues?.length).toBeGreaterThan(0);
    expect(issues?.[0]).toContain('steps');
  });

  it('is null for a good draft, another message, or another origin', () => {
    expect(rejectedDocument(ADMIN, { type: 'map-story:document', document: raw }, [ADMIN])).toBeNull();
    expect(rejectedDocument(ADMIN, { type: 'map-story:step', index: 1 }, [ADMIN])).toBeNull();
    expect(rejectedDocument('https://evil.example', { type: 'map-story:document', document: {} }, [ADMIN])).toBeNull();
  });
});

describe('carryEntityIds', () => {
  it('puts the resolved ids back beside the same Q-ids', () => {
    const draft = MapStoryDocumentSchema.parse(raw);
    const stored = MapStoryDocumentSchema.parse({
      ...raw,
      entity: { ...raw.entity, entity_id: 'e-battle' },
      sides: [{ ...raw.sides[0], commanders: [{ name: 'Brutus', wikidata: 'Q2', entity_id: 'e-brutus' }] }],
    });
    const out = carryEntityIds(draft, stored);
    expect(out.entity?.entity_id).toBe('e-battle');
    expect(out.sides[0].commanders[0].entity_id).toBe('e-brutus');
    expect(draft.sides[0].commanders[0].entity_id ?? null).toBeNull();
    expect(carryEntityIds(draft, undefined)).toBe(draft);
  });
});

describe('roundPoint', () => {
  it('rounds to five decimals as [lon, lat]', () => {
    expect(roundPoint({ lng: 16.1234567, lat: 41.3000049 })).toEqual([16.12346, 41.3]);
  });
});
