// @vitest-environment jsdom
/**
 * Renders of the Discover feed against fixture payloads (stubbed transport, no
 * network): the browse section and the atlas panel show their cards, every
 * action goes where it should (links on the page, the URL in the atlas), the
 * atlas records what is opened and searched, and endpoints that 404 (not
 * deployed yet) leave nothing behind. The expedition card is another
 * workstream's and is stubbed out.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, configure, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { AxiosError } from 'axios';
import type { AxiosResponse } from 'axios';
import { NuqsTestingAdapter } from 'nuqs/adapters/testing';
import type { UrlUpdateEvent } from 'nuqs/adapters/testing';
import { createElement } from 'react';
import type { ReactElement } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '@/lib/api/client';
import { dayKey } from '@/lib/discover/date';
import {
  clearRecents,
  getRecents,
  recentEntityIds,
  recordRecentEntity,
  recordRecentSearch,
} from '@/lib/discover/recents';
import { DiscoverPanel } from './DiscoverPanel';
import { DiscoverRuntime } from './DiscoverRuntime';
import { DiscoverSection } from './DiscoverSection';

vi.mock('./QuestCard', () => ({ QuestCard: () => null }));

// A full parallel run is slow under jsdom; the default 1s wait can flake.
configure({ asyncUtilTimeout: 15_000 });

const uid = (n: number) => `11111111-1111-4111-8111-${String(n).padStart(12, '0')}`;

const TOLSTOY = uid(1);
const OBLIGADO = uid(2);
const HUBBLE = uid(5);
const MEXICAN_WAR = uid(10);
const SIKH_WAR = uid(11);
const HANNIBAL = uid(20);
const SCIPIO = uid(21);
const CANNAE = uid(22);
const CARTHAGE = uid(24);
const JULY_MONARCHY = uid(32);
const QING = uid(35);

/** An entity as the discover endpoints send it. */
function entity(id: string, name: string, more: Record<string, unknown> = {}) {
  return {
    id,
    name,
    entity_type: 'event_battle',
    entity_group: 'EVENT',
    summary: null,
    start_year: null,
    end_year: null,
    at: null,
    has_map_story: false,
    ...more,
  };
}

const person = { entity_type: 'person', entity_group: 'POLITY' };
const state = { entity_type: 'political_entity', entity_group: 'POLITY' };

/** GET /discover/on-this-day for 20 November: seven items, so both row limits show. */
const onThisDay = {
  month: 11,
  day: 20,
  widened: 0,
  items: [
    entity(TOLSTOY, 'Leo Tolstoy', {
      ...person,
      summary: 'Russian novelist.',
      kind: 'died',
      year: 1910,
      date: '1910-11-20',
    }),
    entity(OBLIGADO, 'Battle of Vuelta de Obligado', {
      summary: 'An Anglo-French fleet forces its way up the Paraná.',
      start_year: 1845,
      end_year: 1845,
      at: [-59.6, -33.59],
      has_map_story: true,
      kind: 'happened',
      year: 1845,
      date: '1845-11-20',
    }),
    entity(uid(3), 'Battle of Cambrai', { kind: 'began', year: 1917, date: '1917-11-20' }),
    entity(uid(4), 'Ukrainian People’s Republic', { ...state, kind: 'founded', year: 1917, date: '1917-11-20' }),
    entity(HUBBLE, 'Edwin Hubble', { ...person, kind: 'born', year: 1889, date: '1889-11-20' }),
    entity(uid(6), 'Nuremberg trials', {
      entity_type: 'event_legal_reform',
      kind: 'began',
      year: 1945,
      date: '1945-11-20',
    }),
    entity(uid(7), 'Francisco Franco', { ...person, kind: 'died', year: 1975, date: '1975-11-20' }),
  ],
};

const REGIONS = [
  'North America',
  'South America',
  'Europe',
  'Middle East & North Africa',
  'South Asia',
  'East Asia',
  'Oceania',
];

/** GET /discover/meanwhile: the seven regions above, four of them with an event. */
function meanwhile(year: number) {
  const counts = { events: 3, polities: 5 };
  return {
    year,
    window: 10,
    totals: { events: 42, polities: 233 },
    regions: [
      {
        key: 'north-america',
        name: 'North America',
        event: entity(MEXICAN_WAR, 'Mexican–American War', {
          entity_type: 'event_war',
          start_year: 1846,
          end_year: 1848,
          at: [-99.13, 19.43],
        }),
        polity: entity(uid(30), 'United States', state),
        counts,
      },
      {
        key: 'south-america',
        name: 'South America',
        event: entity(OBLIGADO, 'Battle of Vuelta de Obligado', {
          start_year: 1845,
          end_year: 1845,
          at: [-59.6, -33.59],
          has_map_story: true,
        }),
        polity: entity(uid(31), 'Argentine Confederation', state),
        counts,
      },
      { key: 'europe', name: 'Europe', event: null, polity: entity(JULY_MONARCHY, 'July Monarchy', state), counts },
      {
        key: 'middle-east-north-africa',
        name: 'Middle East & North Africa',
        event: null,
        polity: entity(uid(33), 'Ottoman Empire', state),
        counts,
      },
      {
        key: 'south-asia',
        name: 'South Asia',
        event: entity(SIKH_WAR, 'First Anglo-Sikh War', {
          entity_type: 'event_war',
          start_year: 1845,
          end_year: 1846,
          at: [74.87, 31.07],
        }),
        polity: entity(uid(34), 'Sikh Empire', state),
        counts,
      },
      { key: 'east-asia', name: 'East Asia', event: null, polity: entity(QING, 'Qing dynasty', state), counts },
      {
        key: 'oceania',
        name: 'Oceania',
        event: entity(uid(12), 'Flagstaff War', { start_year: 1845, end_year: 1846, at: [174.1, -35.3] }),
        polity: null,
        counts,
      },
    ],
  };
}

/** GET /discover/for-you after opening Hannibal, then Scipio. */
const forYou = {
  because: [
    { id: SCIPIO, name: 'Scipio Africanus' },
    { id: HANNIBAL, name: 'Hannibal' },
  ],
  entities: [
    entity(uid(23), 'Battle of Zama', { start_year: -202, end_year: -202, via: SCIPIO, relation: 'victorious_at' }),
    entity(CANNAE, 'Battle of Cannae', {
      start_year: -216,
      end_year: -216,
      has_map_story: true,
      via: HANNIBAL,
      relation: 'defeated_at',
    }),
    entity(CARTHAGE, 'Carthage', { entity_type: 'city', entity_group: 'PLACE', via: HANNIBAL, relation: null }),
    // Related to both: listed once, where it first came.
    entity(CANNAE, 'Battle of Cannae', { start_year: -216, via: SCIPIO, relation: 'part_of' }),
  ],
  chronicles: [
    {
      chronicle_id: uid(40),
      title: 'The Punic Wars',
      slug: 'the-punic-wars',
      start_year: -264,
      end_year: -146,
      impact_score: 90,
      entry_count: 42,
      status: 'published',
      tags: ['classical'],
      via: HANNIBAL,
    },
  ],
  stories: [
    {
      id: uid(41),
      slug: 'battle-of-cannae',
      kind: 'battle',
      title: 'Cannae, step by step',
      year: -216,
      step_count: 7,
      via: HANNIBAL,
    },
  ],
};

function notFound(): never {
  throw new AxiosError('Not Found', 'ERR_BAD_REQUEST', undefined, undefined, {
    status: 404,
    statusText: 'Not Found',
    data: { message: 'Not Found' },
    headers: {},
    config: {},
  } as AxiosResponse);
}

type Params = Record<string, unknown>;

/** Serve the discover endpoints from fixtures; `missing` lists the ones that 404. */
function stubApi(missing: string[] = [], day: unknown = onThisDay) {
  return vi.spyOn(api, 'get').mockImplementation(async (url: string, config?: { params?: Params }) => {
    const name = url.replace('/api/v1/discover/', '');
    if (missing.includes(name)) notFound();
    if (name === 'on-this-day') return { data: { data: day } };
    if (name === 'meanwhile') return { data: { data: meanwhile(Number(config?.params?.year)) } };
    if (name === 'for-you') return { data: { data: forYou } };
    notFound();
  });
}

/** The params each call to one endpoint was made with. */
function asked(spy: ReturnType<typeof stubApi>, name: string): Params[] {
  return spy.mock.calls
    .filter(([url]) => url === `/api/v1/discover/${name}`)
    .map(([, config]) => (config as { params?: Params } | undefined)?.params ?? {});
}

/** Render inside the providers the app has: the query client, the router and the URL state. */
function mount(element: ReactElement, search = '', onUrlUpdate?: (event: UrlUpdateEvent) => void) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    createElement(
      QueryClientProvider,
      { client },
      createElement(
        MemoryRouter,
        null,
        createElement(NuqsTestingAdapter, { searchParams: search, hasMemory: true, onUrlUpdate, children: element }),
      ),
    ),
  );
}

/** The URL after the latest write. */
function lastUrl(onUrlUpdate: ReturnType<typeof vi.fn>): URLSearchParams {
  const event = onUrlUpdate.mock.calls[onUrlUpdate.mock.calls.length - 1]?.[0] as UrlUpdateEvent | undefined;
  return event?.searchParams ?? new URLSearchParams();
}

/** The card an element sits in. */
const cardOf = (element: HTMLElement) => element.closest('section') as HTMLElement;

/** Each card, once its data is on screen (their outlines carry the same titles). */
const onThisDayCard = async (role: 'link' | 'button') =>
  cardOf(await screen.findByRole(role, { name: /Leo Tolstoy/ }));
const meanwhileCard = async () => cardOf(await screen.findByText(/^(While|Around) /));
const forYouCard = async () => cardOf(await screen.findByText(/^Because you opened/));

beforeEach(() => {
  // jsdom lacks matchMedia; "go there" reads it to pad the map's camera.
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
});

afterEach(() => {
  cleanup();
  clearRecents();
  localStorage.clear();
  vi.restoreAllMocks();
});

// The first render pays for importing the hook barrel; give it room on a busy machine.
describe('Discover on the browse page', { timeout: 30_000 }, () => {
  it('on this day: six rows, each a link to the entity in its own year', async () => {
    const spy = stubApi();
    mount(createElement(DiscoverSection));

    const card = await onThisDayCard('link');
    expect(within(card).getByRole('heading', { name: 'On this day' })).toBeTruthy();
    expect(within(card).getByText('20 November')).toBeTruthy();
    expect(asked(spy, 'on-this-day')).toEqual([{ date: dayKey() }]);

    expect(within(card).getAllByRole('link')).toHaveLength(6);
    expect(within(card).queryByText('Francisco Franco')).toBeNull();

    const tolstoy = within(card).getByRole('link', { name: /Leo Tolstoy/ });
    expect(tolstoy.getAttribute('href')).toBe(`/app?sel=${TOLSTOY}&t=1910`);
    expect(within(tolstoy).getByText('1910 CE')).toBeTruthy();
    expect(within(tolstoy).getByText('died')).toBeTruthy();
    expect(within(tolstoy).getByText('Russian novelist.')).toBeTruthy();

    const battle = within(card).getByRole('link', { name: /Battle of Vuelta de Obligado/ });
    expect(battle.getAttribute('href')).toBe(`/app?sel=${OBLIGADO}&t=1845`);
    expect(within(battle).getByText(/has a battle map/)).toBeTruthy();
    // An event that simply happened that day gets no word.
    expect(within(battle).queryByText(/^(begins|ends|born|died|founded)$/)).toBeNull();
    expect(within(tolstoy).queryByText(/has a battle map/)).toBeNull();

    expect(within(within(card).getByRole('link', { name: /Battle of Cambrai/ })).getByText('begins')).toBeTruthy();
    expect(within(within(card).getByRole('link', { name: /Ukrainian/ })).getByText('founded')).toBeTruthy();
    expect(within(within(card).getByRole('link', { name: /Edwin Hubble/ })).getByText('born')).toBeTruthy();
    // No row shows its own day while the list is this day alone.
    expect(within(card).queryByText(/Includes nearby days/)).toBeNull();
    expect(within(card).getAllByText('20 November')).toHaveLength(1);
  });

  it('on this day: a widened list shows each row’s own day', async () => {
    stubApi([], {
      ...onThisDay,
      widened: 1,
      items: [
        entity(OBLIGADO, 'Battle of Vuelta de Obligado', { kind: 'happened', year: 1845, date: '1845-11-20' }),
        entity(uid(8), 'Battle of Tarawa', { kind: 'began', year: 1943, date: '1943-11-19' }),
      ],
    });
    mount(createElement(DiscoverSection));
    const tarawa = await screen.findByRole('link', { name: /Battle of Tarawa/ });
    const card = cardOf(tarawa);
    expect(within(tarawa).getByText('19 November')).toBeTruthy();
    expect(within(within(card).getByRole('link', { name: /Obligado/ })).getByText('20 November')).toBeTruthy();
    expect(within(card).getByText(/Includes nearby days/)).toBeTruthy();
  });

  it('meanwhile: the year of the first event, a lead sentence, and regions that link with that year', async () => {
    const spy = stubApi();
    mount(createElement(DiscoverSection));

    const card = await meanwhileCard();
    expect(within(card).getByRole('heading', { name: 'Meanwhile in 1845 CE' })).toBeTruthy();
    expect(asked(spy, 'meanwhile')).toEqual([{ year: 1845 }]);
    expect(
      within(card).getByText('The year of the Battle of Vuelta de Obligado · 233 states and 42 events on the map'),
    ).toBeTruthy();

    // The two events of that year farthest apart (the Paraná and the Punjab), west first.
    expect(within(card).getByText(/^While /).textContent).toBe(
      'While the Battle of Vuelta de Obligado took place in South America, the First Anglo-Sikh War took place in South Asia.',
    );
    expect(within(card).getByRole('link', { name: 'First Anglo-Sikh War' }).getAttribute('href')).toBe(
      `/app?sel=${SIKH_WAR}&t=1845`,
    );

    // Four of the seven regions, spread west to east, until the reader asks for all.
    const shown = () => REGIONS.filter((name) => within(card).queryByText(name));
    expect(shown()).toEqual(['North America', 'Europe', 'South Asia', 'Oceania']);
    // An event from the window around the year says which year it is from.
    const war = within(card).getByRole('link', { name: /Mexican–American War/ });
    expect(war.getAttribute('href')).toBe(`/app?sel=${MEXICAN_WAR}&t=1845`);
    expect(within(war).getByText('1846 CE')).toBeTruthy();
    expect(within(card).getByRole('link', { name: /July Monarchy/ }).getAttribute('href')).toBe(
      `/app?sel=${JULY_MONARCHY}&t=1845`,
    );

    fireEvent.click(within(card).getByRole('button', { name: 'Show all 7 regions' }));
    expect(shown()).toEqual(REGIONS);
    expect(within(card).getByRole('button', { name: 'Show fewer regions' })).toBeTruthy();
    expect(within(card).getByText(/its most notable event within 10 years/)).toBeTruthy();
  });

  it('for you: hidden until something was opened, and no request is made', async () => {
    const spy = stubApi();
    mount(createElement(DiscoverSection));
    await meanwhileCard();
    expect(screen.queryByRole('heading', { name: 'For you' })).toBeNull();
    expect(asked(spy, 'for-you')).toEqual([]);
  });

  it('for you: suggestions as links into the atlas, searches to run again, and Clear', async () => {
    recordRecentEntity(HANNIBAL);
    recordRecentEntity(SCIPIO);
    recordRecentSearch('rome');
    const spy = stubApi();
    mount(createElement(DiscoverSection));

    const card = await forYouCard();
    expect(within(card).getByRole('heading', { name: 'For you' })).toBeTruthy();
    expect(within(card).getByText('Because you opened Scipio Africanus and Hannibal')).toBeTruthy();
    // Only the ids leave the browser, most recent first.
    expect(asked(spy, 'for-you')).toEqual([{ ids: `${SCIPIO},${HANNIBAL}` }]);

    const cannae = within(card).getByRole('link', { name: /Battle of Cannae/ });
    expect(cannae.getAttribute('href')).toBe(`/app?sel=${CANNAE}&t=-216`);
    expect(within(cannae).getByText('216 BCE')).toBeTruthy();
    expect(within(cannae).getByText(/defeated at · via Hannibal$/)).toBeTruthy();
    expect(within(cannae).getByText(/has a battle map/)).toBeTruthy();
    // Nothing known about the relation or the year: the name and where it comes from.
    const carthage = within(card).getByRole('link', { name: /Carthage/ });
    expect(carthage.getAttribute('href')).toBe(`/app?sel=${CARTHAGE}`);
    expect(within(carthage).getByText('via Hannibal')).toBeTruthy();

    const chronicle = within(card).getByRole('link', { name: /The Punic Wars/ });
    expect(chronicle.getAttribute('href')).toBe('/app?chron=the-punic-wars');
    expect(within(chronicle).getByText('264 – 146 BCE')).toBeTruthy();
    const story = within(card).getByRole('link', { name: /Cannae, step by step/ });
    expect(story.getAttribute('href')).toBe('/app?story=battle-of-cannae');
    expect(within(story).getByText('Battle map · 216 BCE · 7 steps')).toBeTruthy();
    expect(within(card).getByRole('link', { name: 'rome' }).getAttribute('href')).toBe('/app?q=rome');

    expect(within(card).getByText('From what you opened in this browser.')).toBeTruthy();
    fireEvent.click(within(card).getByRole('button', { name: 'Clear' }));
    expect(screen.queryByRole('heading', { name: 'For you' })).toBeNull();
    expect(getRecents().entities).toEqual([]);
    expect(getRecents().searches).toEqual([]);
  });

  it('every action on the page is a link: the only buttons unfold the list and clear the recents', async () => {
    recordRecentEntity(HANNIBAL);
    stubApi();
    mount(createElement(DiscoverSection));
    await forYouCard();
    await meanwhileCard();
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual(['Show all 7 regions', 'Clear']);
    const links = screen.getAllByRole('link');
    expect(links.length).toBeGreaterThan(15);
    for (const link of links) expect(link.getAttribute('href')).toMatch(/^\/app\?/);
  });

  it('stays out of the way when the endpoints 404', async () => {
    recordRecentEntity(HANNIBAL);
    const spy = stubApi(['on-this-day', 'meanwhile', 'for-you']);
    const { container } = mount(createElement(DiscoverSection));
    await waitFor(() => expect(asked(spy, 'for-you')).toHaveLength(1));
    await waitFor(() => expect(container.querySelector('section')).toBeNull());
    expect(container.textContent).toBe('');
    // Without "on this day" there is no year to ask about.
    expect(asked(spy, 'meanwhile')).toEqual([]);
  });

  it('shows the other cards when one endpoint 404s', async () => {
    stubApi(['meanwhile']);
    mount(createElement(DiscoverSection));
    await onThisDayCard('link');
    await waitFor(() => expect(screen.queryByRole('heading', { name: /Meanwhile/ })).toBeNull());
    expect(screen.getByRole('heading', { name: 'On this day' })).toBeTruthy();
  });
});

describe('Discover in the atlas', { timeout: 30_000 }, () => {
  it('on this day: five rows; a click sets the year and opens the entity in one step', async () => {
    stubApi();
    const onUrlUpdate = vi.fn();
    mount(createElement(DiscoverPanel), '?t=1066', onUrlUpdate);

    const card = await onThisDayCard('button');
    expect(within(card).getAllByRole('button')).toHaveLength(5);
    expect(within(card).queryByText('Nuremberg trials')).toBeNull();
    expect(within(card).queryByRole('link')).toBeNull();
    // The sidebar is dense: no summaries.
    expect(within(card).queryByText('Russian novelist.')).toBeNull();

    fireEvent.click(within(card).getByRole('button', { name: /Edwin Hubble/ }));
    await waitFor(() => expect(onUrlUpdate).toHaveBeenCalledTimes(1));
    expect(lastUrl(onUrlUpdate).get('sel')).toBe(HUBBLE);
    expect(lastUrl(onUrlUpdate).get('t')).toBe('1889');
  });

  it('meanwhile: the timeline’s year and every region; a click opens the entity and leaves the year', async () => {
    const spy = stubApi();
    const onUrlUpdate = vi.fn();
    mount(createElement(DiscoverPanel), '?t=1066', onUrlUpdate);

    const card = await meanwhileCard();
    expect(within(card).getByRole('heading', { name: 'Meanwhile in 1066 CE' })).toBeTruthy();
    expect(asked(spy, 'meanwhile')).toEqual([{ year: 1066 }]);
    expect(within(card).getByText('233 states and 42 events on the map')).toBeTruthy();
    // Neither event is from 1066 itself: no "While", and each says its own year.
    expect(within(card).getByText(/^Around /).textContent).toBe(
      'Around 1066 CE, the Battle of Vuelta de Obligado (1845 CE) took place in South America and the First Anglo-Sikh War (1845 CE) took place in South Asia.',
    );
    expect(REGIONS.filter((name) => within(card).queryByText(name))).toEqual(REGIONS);
    expect(within(card).queryByRole('button', { name: /Show all/ })).toBeNull();
    expect(within(card).queryByRole('link')).toBeNull();

    fireEvent.click(within(card).getByRole('button', { name: /Qing dynasty/ }));
    await waitFor(() => expect(onUrlUpdate).toHaveBeenCalledTimes(1));
    expect(lastUrl(onUrlUpdate).get('sel')).toBe(QING);
    expect(lastUrl(onUrlUpdate).get('t')).toBe('1066');
  });

  it('meanwhile: follows the timeline once it rests, keeping the last answer until then', async () => {
    const spy = stubApi();
    mount(createElement(DiscoverPanel), '?t=1066', vi.fn());
    await meanwhileCard();

    // Going to a row's year moves the timeline: the card still shows 1066, then asks about 1889.
    fireEvent.click(await screen.findByRole('button', { name: /Edwin Hubble/ }));
    expect(screen.getByRole('heading', { name: 'Meanwhile in 1066 CE' })).toBeTruthy();
    expect(await screen.findByRole('heading', { name: 'Meanwhile in 1889 CE' })).toBeTruthy();
    expect(asked(spy, 'meanwhile')).toEqual([{ year: 1066 }, { year: 1889 }]);
  });

  it('meanwhile: asks nothing for a year the API does not cover', async () => {
    const spy = stubApi();
    mount(createElement(DiscoverPanel), '?t=-9000');
    await onThisDayCard('button');
    expect(screen.queryByRole('heading', { name: /Meanwhile/ })).toBeNull();
    expect(asked(spy, 'meanwhile')).toEqual([]);
  });

  it('for you: rows act in place (the entity, the tour, the battle map, the search filter)', async () => {
    recordRecentEntity(HANNIBAL);
    recordRecentEntity(SCIPIO);
    recordRecentSearch('rome');
    stubApi();
    const onUrlUpdate = vi.fn();
    mount(createElement(DiscoverPanel), `?t=1066&sel=${SCIPIO}`, onUrlUpdate);

    const card = await forYouCard();
    expect(within(card).queryByRole('link')).toBeNull();

    fireEvent.click(within(card).getByRole('button', { name: /Battle of Cannae/ }));
    await waitFor(() => expect(lastUrl(onUrlUpdate).get('sel')).toBe(CANNAE));
    expect(lastUrl(onUrlUpdate).get('t')).toBe('-216');

    fireEvent.click(within(card).getByRole('button', { name: /The Punic Wars/ }));
    await waitFor(() => expect(lastUrl(onUrlUpdate).get('chron')).toBe('the-punic-wars'));
    expect(lastUrl(onUrlUpdate).get('sel')).toBeNull();

    fireEvent.click(within(card).getByRole('button', { name: /Cannae, step by step/ }));
    await waitFor(() => expect(lastUrl(onUrlUpdate).get('story')).toBe('battle-of-cannae'));
    expect(lastUrl(onUrlUpdate).get('chron')).toBeNull();

    fireEvent.click(within(card).getByRole('button', { name: /Battle of Zama/ }));
    await waitFor(() => expect(lastUrl(onUrlUpdate).get('sel')).toBe(uid(23)));

    // As the search box does: the word becomes the filter and the open entity is closed.
    fireEvent.click(within(card).getByRole('button', { name: 'rome' }));
    await waitFor(() => expect(lastUrl(onUrlUpdate).get('q')).toBe('rome'));
    expect(lastUrl(onUrlUpdate).get('sel')).toBeNull();
  });

  it('stays out of the way when the endpoints 404', async () => {
    recordRecentEntity(HANNIBAL);
    const spy = stubApi(['on-this-day', 'meanwhile', 'for-you']);
    const { container } = mount(createElement(DiscoverPanel), '?t=1066');
    await waitFor(() => expect(asked(spy, 'meanwhile')).toHaveLength(1));
    await waitFor(() => expect(container.querySelector('section')).toBeNull());
    expect(container.textContent).toBe('');
  });
});

describe('DiscoverRuntime', { timeout: 30_000 }, () => {
  it('records the open entity and the search word kept as a filter', async () => {
    const { container } = mount(createElement(DiscoverRuntime), `?sel=${HANNIBAL}&q=rome`);
    await waitFor(() => expect(recentEntityIds(getRecents())).toEqual([HANNIBAL]));
    expect(getRecents().searches.map((s) => s.q)).toEqual(['rome']);
    expect(container.innerHTML).toBe('');
  });

  it('records nothing for an empty atlas, a selection that is not an entity id or a one-letter word', async () => {
    mount(createElement(DiscoverRuntime), '');
    mount(createElement(DiscoverRuntime), '?sel=e:marathon&q=r');
    await Promise.resolve();
    expect(getRecents().entities).toEqual([]);
    expect(getRecents().searches).toEqual([]);
  });

  it('feeds the card beside it: opening an entity in the atlas brings up "For you"', async () => {
    stubApi();
    mount(createElement('div', null, createElement(DiscoverRuntime), createElement(DiscoverPanel)), '?t=1066');
    const card = await onThisDayCard('button');
    expect(screen.queryByRole('heading', { name: 'For you' })).toBeNull();

    fireEvent.click(within(card).getByRole('button', { name: /Leo Tolstoy/ }));
    await forYouCard();
    expect(recentEntityIds(getRecents())).toEqual([TOLSTOY]);
  });
});
