// @vitest-environment jsdom
/**
 * Link mode in the DOM: on the site every control that opens another page is
 * a real `<a href>` (crawlers follow anchors, never click handlers) and a
 * plain click is still client-side navigation; in the atlas the same
 * controls stay buttons whose clicks run the atlas hooks (the URL keys they
 * write show it).
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, configure, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { AxiosError } from 'axios';
import type { AxiosResponse } from 'axios';
import { NuqsTestingAdapter } from 'nuqs/adapters/testing';
import type { UrlUpdateEvent } from 'nuqs/adapters/testing';
import { createElement } from 'react';
import type { ReactElement } from 'react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PageWhatChanged } from '@/components/atlas/ChroniclePlayer';
import { EntityPage } from '@/components/atlas/EntityPage';
import { LinkModeProvider, PageLink } from '@/components/atlas/link-mode';
import type { LinkMode } from '@/components/atlas/link-mode';
import { RelationshipTimeline } from '@/components/atlas/RelationshipTimeline';
import { PageTagPills } from '@/components/atlas/TagPills';
import { api } from '@/lib/api/client';
import { tagRow } from '@/lib/schemas/collection.fixtures';
import { RelationshipSchema } from '@/lib/schemas/entity';

// A full parallel run is slow under jsdom; the default 1s wait can flake.
configure({ asyncUtilTimeout: 15_000 });

const uid = (n: number) => `22222222-2222-4222-8222-${String(n).padStart(12, '0')}`;
const ROME = uid(1);
const CARTHAGE = uid(2);
const SCIPIO = uid(3);

const summary = (id: string, name: string, entity_group = 'POLITY') => ({ id, name, entity_group });

/** Rome fought Carthage; the relationship is part of the Punic Wars chronicle. */
const war = RelationshipSchema.parse({
  id: uid(10),
  source_entity_id: ROME,
  target_entity_id: CARTHAGE,
  relationship_type: 'at_war_with',
  temporal_start: -264,
  confidence: 'high',
  source_entity: summary(ROME, 'Roman Republic'),
  target_entity: summary(CARTHAGE, 'Carthage'),
});
/** A relationship whose far side did not load: nothing to open. */
const unknown = RelationshipSchema.parse({
  id: uid(11),
  source_entity_id: ROME,
  target_entity_id: uid(99),
  relationship_type: 'allied_with',
  temporal_start: -200,
  confidence: 'low',
  source_entity: summary(ROME, 'Roman Republic'),
});
const relChronicle = new Map([[war.id, { title: 'The Punic Wars', slug: 'punic-wars' }]]);

function notFound(): never {
  throw new AxiosError('Not Found', 'ERR_BAD_REQUEST', undefined, undefined, {
    status: 404,
    statusText: 'Not Found',
    data: { message: 'Not Found' },
    headers: {},
    config: {},
  } as AxiosResponse);
}

const ZAMA = uid(4);

/** The battle of Zama's page: a place on the map, a battle map, a chronicle,
 *  a timeline row and a relationship. The graph and the story document 404. */
const zamaPayloads: Record<string, unknown> = {
  [`/api/v1/entities/${ZAMA}`]: {
    data: {
      id: ZAMA,
      name: 'Battle of Zama',
      entity_type: 'event_battle',
      entity_group: 'EVENT',
      summary: 'Scipio defeats Hannibal.',
      temporal_start: -202,
      geom: { type: 'Point', coordinates: [9.75, 36.3] },
      location_name: 'Zama',
      tags: ['classical'],
      map_stories: [{ id: uid(20), slug: 'battle-of-zama', kind: 'battle', title: 'Zama', step_count: 4 }],
    },
  },
  [`/api/v1/entities/${ZAMA}/relationships`]: {
    data: [
      {
        id: uid(21),
        source_entity_id: ZAMA,
        target_entity_id: CARTHAGE,
        relationship_type: 'participant',
        temporal_start: -202,
        confidence: 'high',
        source_entity: summary(ZAMA, 'Battle of Zama', 'EVENT'),
        target_entity: summary(CARTHAGE, 'Carthage'),
      },
    ],
  },
  [`/api/v1/entities/${ZAMA}/chronicles`]: {
    data: [{ chronicle_id: uid(22), title: 'The Punic Wars', slug: 'punic-wars', relationship_ids: [] }],
  },
  [`/api/v1/entities/${ZAMA}/timeline`]: {
    data: [
      {
        id: uid(23),
        entity_id: ZAMA,
        entry_kind: 'relationship',
        start_year: -202,
        title: 'Scipio Africanus',
        relationship_type: 'commander',
        related_entity_id: SCIPIO,
        related_entity_name: 'Scipio Africanus',
      },
    ],
  },
};

/** The tag list and Zama's page; everything else (the signed-in user, stars,
 *  the graph) is a 404. */
function stubApi() {
  vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
    if (url === '/api/v1/tags') return { data: { data: [tagRow], facets: [] } };
    if (url in zamaPayloads) return { data: zamaPayloads[url] };
    notFound();
  });
}

/** Shows the router's location, so a test can see client-side navigation. */
function Where() {
  const { pathname, search } = useLocation();
  return createElement('output', { 'data-testid': 'where' }, `${pathname}${search}`);
}
const where = () => screen.getByTestId('where').textContent;

/** Mount `element` at `/entities/<Rome>` in a link mode (atlas = no provider, as in `/app`). */
function mount(mode: LinkMode, element: ReactElement, onUrlUpdate = vi.fn<(event: UrlUpdateEvent) => void>()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const page = mode === 'site' ? createElement(LinkModeProvider, { mode: 'site', children: element }) : element;
  render(
    createElement(
      QueryClientProvider,
      { client },
      createElement(
        MemoryRouter,
        { initialEntries: [`/entities/${ROME}`] },
        createElement(NuqsTestingAdapter, {
          searchParams: '?t=-250',
          hasMemory: true,
          onUrlUpdate,
          children: [createElement(Where, { key: 'where' }), createElement('main', { key: 'page' }, page)],
        }),
      ),
    ),
  );
  return onUrlUpdate;
}

/** The URL after the atlas's latest write. */
function lastUrl(onUrlUpdate: ReturnType<typeof vi.fn>): URLSearchParams {
  const event = onUrlUpdate.mock.calls[onUrlUpdate.mock.calls.length - 1]?.[0] as UrlUpdateEvent | undefined;
  return event?.searchParams ?? new URLSearchParams();
}

const main = () => screen.getByRole('main');

beforeEach(() => {
  // jsdom lacks matchMedia; the atlas hooks (built in both modes) ask whether this is a phone.
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: (media: string) => ({
      matches: false,
      media,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  });
  // Nor element scrolling (the atlas page scrolls its own box to the top)…
  Element.prototype.scrollTo ??= () => {};
  // …nor IntersectionObserver, which the page's sticky header uses.
  vi.stubGlobal(
    'IntersectionObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

// The first render pays for importing the hook barrel; give it room on a busy machine.
describe('link mode', { timeout: 30_000 }, () => {
  it('site: relationship rows and chronicle badges are links to site pages', () => {
    stubApi();
    const onUrlUpdate = mount(
      'site',
      createElement(RelationshipTimeline, { rels: [war, unknown], selfId: ROME, relChronicle }),
    );

    const carthage = within(main()).getByRole('link', { name: /Carthage/ });
    expect(carthage.getAttribute('href')).toBe(`/entities/${CARTHAGE}`);
    const chronicle = within(main()).getByRole('link', { name: /The Punic Wars/ });
    expect(chronicle.getAttribute('href')).toBe('/chronicles/punic-wars');
    // The unknown far side opens nothing, as before.
    expect(within(main()).getAllByRole('link')).toHaveLength(2);
    expect((within(main()).getByRole('button', { name: '—' }) as HTMLButtonElement).disabled).toBe(true);

    // A plain click is client-side navigation and writes no atlas state.
    fireEvent.click(carthage);
    expect(where()).toBe(`/entities/${CARTHAGE}`);
    expect(onUrlUpdate).not.toHaveBeenCalled();
  });

  it('site: a modified click is the browser’s (new tab), not the router’s', () => {
    stubApi();
    mount('site', createElement(RelationshipTimeline, { rels: [war], selfId: ROME, relChronicle }));
    const carthage = within(main()).getByRole('link', { name: /Carthage/ });
    // Record whether the page took each click over, then stop jsdom from
    // trying to load the link itself.
    const takenOver: boolean[] = [];
    const record = (event: MouseEvent) => {
      takenOver.push(event.defaultPrevented);
      event.preventDefault();
    };
    window.addEventListener('click', record);
    try {
      fireEvent.click(carthage, { ctrlKey: true });
      fireEvent.click(carthage, { metaKey: true });
      fireEvent.click(carthage, { shiftKey: true });
      fireEvent.click(carthage, { button: 1 });
      expect(where()).toBe(`/entities/${ROME}`);
      fireEvent.click(carthage);
    } finally {
      window.removeEventListener('click', record);
    }
    expect(takenOver).toEqual([false, false, false, false, true]);
    expect(where()).toBe(`/entities/${CARTHAGE}`);
  });

  it('atlas: the same rows are buttons that select and enter through the hooks', async () => {
    stubApi();
    const onUrlUpdate = mount(
      'atlas',
      createElement(RelationshipTimeline, { rels: [war, unknown], selfId: ROME, relChronicle }),
    );
    expect(within(main()).queryByRole('link')).toBeNull();

    fireEvent.click(within(main()).getByRole('button', { name: /Carthage/ }));
    await waitFor(() => expect(lastUrl(onUrlUpdate).get('sel')).toBe(CARTHAGE));
    expect(lastUrl(onUrlUpdate).get('t')).toBe('-250');

    fireEvent.click(within(main()).getByRole('button', { name: /The Punic Wars/ }));
    await waitFor(() => expect(lastUrl(onUrlUpdate).get('chron')).toBe('punic-wars'));
    // The router's page never changed: the atlas works in its search params.
    expect(where()).toBe(`/entities/${ROME}`);
  });

  it('site: tag pills link to their browse pages', async () => {
    stubApi();
    mount('site', createElement(PageTagPills, { slugs: ['classical'] }));
    const pill = await within(main()).findByRole('link', { name: /Classical Era/ });
    expect(pill.getAttribute('href')).toBe('/browse/era/classical');
    fireEvent.click(pill);
    expect(where()).toBe('/browse/era/classical');
  });

  it('atlas: tag pills are buttons that filter the Chronicles tab', async () => {
    stubApi();
    const onUrlUpdate = mount('atlas', createElement(PageTagPills, { slugs: ['classical'] }));
    const pill = await within(main()).findByRole('button', { name: /Classical Era/ });
    expect(within(main()).queryByRole('link')).toBeNull();
    fireEvent.click(pill);
    await waitFor(() => expect(lastUrl(onUrlUpdate).get('ct')).toBe('classical'));
  });

  it('site: "what changed" names link to both entity pages', () => {
    stubApi();
    const onOpen = vi.fn();
    mount('site', createElement(PageWhatChanged, { rel: war, onOpen }));
    expect(within(main()).getByRole('link', { name: /Roman Republic/ }).getAttribute('href')).toBe(
      `/entities/${ROME}`,
    );
    const carthage = within(main()).getByRole('link', { name: /Carthage/ });
    expect(carthage.getAttribute('href')).toBe(`/entities/${CARTHAGE}`);
    fireEvent.click(carthage);
    expect(where()).toBe(`/entities/${CARTHAGE}`);
    expect(onOpen).not.toHaveBeenCalled();
  });

  it('atlas: "what changed" names are buttons that call onOpen', () => {
    stubApi();
    const onOpen = vi.fn();
    mount('atlas', createElement(PageWhatChanged, { rel: war, onOpen }));
    expect(within(main()).queryByRole('link')).toBeNull();
    fireEvent.click(within(main()).getByRole('button', { name: /Carthage/ }));
    expect(onOpen).toHaveBeenCalledWith(CARTHAGE);
  });

  it('PageLink: battle maps and "show on the map" leave the site for the globe', () => {
    stubApi();
    const onOpen = vi.fn();
    mount(
      'site',
      createElement(
        'div',
        null,
        createElement(PageLink, {
          key: 's',
          intent: { kind: 'story', slug: 'cannae', step: 2 },
          onOpen,
          children: 'Step 3',
        }),
        createElement(PageLink, {
          key: 'm',
          intent: { kind: 'map', entityId: SCIPIO, year: -202 },
          onOpen,
          children: 'Map',
        }),
      ),
    );
    expect(screen.getByRole('link', { name: 'Step 3' }).getAttribute('href')).toBe('/app?story=cannae&sstep=2');
    expect(screen.getByRole('link', { name: 'Map' }).getAttribute('href')).toBe(`/app?sel=${SCIPIO}&t=-202`);
    fireEvent.click(screen.getByRole('link', { name: 'Map' }));
    expect(where()).toBe(`/app?sel=${SCIPIO}&t=-202`);
    expect(onOpen).not.toHaveBeenCalled();
  });

  it('site: the entity page links every page it opens', async () => {
    stubApi();
    mount('site', createElement(EntityPage, { id: ZAMA, variant: 'site' }));
    const link = async (name: RegExp) => (await within(main()).findByRole('link', { name })).getAttribute('href');

    const onTheMap = `/app?sel=${ZAMA}&t=-202`;
    expect(await link(/View the map in 202 BCE/)).toBe(onTheMap);
    expect(await link(/^Zama$/)).toBe(onTheMap);
    expect(await link(/Play the battle/)).toBe('/app?story=battle-of-zama');
    expect(await link(/Classical Era/)).toBe('/browse/era/classical');
    expect(await link(/The Punic Wars/)).toBe('/chronicles/punic-wars');
    expect(await link(/Scipio Africanus/)).toBe(`/entities/${SCIPIO}`);
    expect(await link(/Carthage/)).toBe(`/entities/${CARTHAGE}`);
    expect(await link(/Open on the globe/)).toBe(`/app?sel=${ZAMA}&full=1`);
    // None of them is still a button.
    for (const name of [/View the map/, /Play the battle/, /Classical Era/, /The Punic Wars/, /Scipio/, /Carthage/]) {
      expect(within(main()).queryByRole('button', { name })).toBeNull();
    }
  });

  it('atlas: the entity page keeps its buttons, which select through the hooks', async () => {
    stubApi();
    const onUrlUpdate = mount('atlas', createElement(EntityPage, { id: ZAMA }));
    const scipio = await within(main()).findByRole('button', { name: /Scipio Africanus/ });
    for (const name of [/View the map/, /Play the battle/, /Classical Era/, /The Punic Wars/, /Carthage/]) {
      expect(await within(main()).findByRole('button', { name })).toBeTruthy();
      expect(within(main()).queryByRole('link', { name })).toBeNull();
    }
    fireEvent.click(scipio);
    await waitFor(() => expect(lastUrl(onUrlUpdate).get('sel')).toBe(SCIPIO));
    fireEvent.click(within(main()).getByRole('button', { name: /Play the battle/ }));
    await waitFor(() => expect(lastUrl(onUrlUpdate).get('story')).toBe('battle-of-zama'));
  });

  it('PageLink: in the atlas a button that runs the action in place', () => {
    stubApi();
    const onOpen = vi.fn();
    mount(
      'atlas',
      createElement(PageLink, { intent: { kind: 'map', entityId: SCIPIO, year: -202 }, onOpen, children: 'Map' }),
    );
    expect(screen.queryByRole('link')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Map' }));
    expect(onOpen).toHaveBeenCalledTimes(1);
    expect(where()).toBe(`/entities/${ROME}`);
  });
});
