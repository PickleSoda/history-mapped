// @vitest-environment jsdom
/**
 * Renders of the expedition card against a fixture payload (stubbed transport,
 * no network): the playable card of the atlas's Today tab, and the teaser of
 * the browse page, which must work without the atlas's URL state.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, configure, fireEvent, render, screen, within } from '@testing-library/react';
import { AxiosError } from 'axios';
import type { AxiosResponse } from 'axios';
import { NuqsTestingAdapter } from 'nuqs/adapters/testing';
import type { UrlUpdateEvent } from 'nuqs/adapters/testing';
import { createElement } from 'react';
import type { ReactElement } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '@/lib/api/client';
import { dayKey, previousDayKey } from '@/lib/discover/date';
import { HIDDEN_YEAR, NO_PROGRESS } from '@/lib/discover/quest';
import type { QuestReading } from '@/lib/discover/quest';
import { useQuestLive, useQuestStore } from '@/lib/discover/quest-store';
import { CANNAE, HASTINGS, MAGDALA, questPayload } from '@/lib/discover/quest.fixtures';
import { useEphemeralStore } from '@/stores/ephemeral';
import { QuestCard } from './QuestCard';

// The first render pays for importing the hook barrel; give it room on a busy machine.
configure({ asyncUtilTimeout: 15_000 });

const found = { ...NO_PROGRESS, found: true };
const urlUpdates: UrlUpdateEvent[] = [];
/** The atlas's search params after the latest URL write. */
const lastUrl = (): URLSearchParams | undefined => urlUpdates[urlUpdates.length - 1]?.searchParams;

function stubQuest(payload: unknown = questPayload) {
  vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
    if (url === '/api/v1/discover/quest' && payload) return { data: payload };
    throw new AxiosError('Not Found', 'ERR_BAD_REQUEST', undefined, undefined, {
      status: 404,
      statusText: 'Not Found',
      data: { message: 'Not Found' },
      headers: {},
      config: {},
    } as AxiosResponse);
  });
}

/** Query client and router around a card; the atlas's URL state only when asked for. */
function mount(card: ReactElement, { atlas }: { atlas: boolean }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const routed = createElement(MemoryRouter, null, card);
  return render(
    createElement(
      QueryClientProvider,
      { client },
      atlas
        ? createElement(NuqsTestingAdapter, { hasMemory: true, onUrlUpdate: (event) => urlUpdates.push(event), children: routed })
        : routed,
    ),
  );
}

const panel = () => mount(createElement(QuestCard, { variant: 'panel' }), { atlas: true });
const teaser = () => mount(createElement(QuestCard, { variant: 'page' }), { atlas: false });

/** The list row of a target, by a word of its name. */
const row = async (name: RegExp) => (await screen.findByText(name)).closest('li') as HTMLElement;

const reading = (patch: Partial<QuestReading> = {}): QuestReading => ({
  id: MAGDALA,
  time: 'warm',
  direction: 'later',
  place: 'cool',
  zoomIn: false,
  compass: 'S',
  arrow: 4,
  km: 4300,
  arrived: false,
  ...patch,
});

beforeEach(() => {
  localStorage.clear();
  urlUpdates.length = 0;
  useQuestStore.setState({ date: dayKey(), active: null, targets: {}, streak: { count: 0, last: null } });
  useQuestLive.getState().clear();
  useEphemeralStore.setState({ map: null, mapInsets: null });
  // jsdom has no matchMedia (the atlas hooks ask whether this is a phone).
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('QuestCard, in the atlas', { timeout: 30_000 }, () => {
  it('lists the day’s three targets, each to start, with no year given away', async () => {
    stubQuest({
      data: {
        ...questPayload.data,
        targets: questPayload.data.targets.map((t) => (t.id === CANNAE ? { ...t, name: 'Battle of Cannae (216 BC)' } : t)),
      },
    });
    panel();
    expect(await screen.findByRole('heading', { name: 'Expedition 12' })).toBeTruthy();
    expect(screen.getAllByRole('button', { name: 'Start' })).toHaveLength(3);
    expect(within(await row(/Hastings/)).getByText('easy')).toBeTruthy();
    expect(within(await row(/Magdala/)).getByText('medium')).toBeTruthy();
    const cannae = await row(/Cannae/);
    expect(within(cannae).getByText('hard')).toBeTruthy();
    expect(cannae.textContent).not.toContain('216');
    expect(within(cannae).getByRole('img', { name: 'year hidden' })).toBeTruthy();
    // No summary until a target is started, and no streak to show yet.
    expect(document.body.textContent).not.toContain('Napier');
    expect(document.body.textContent).not.toContain('streak');
  });

  it('shows the clue of the target being looked for, without its year, and the warmth as it is read', async () => {
    stubQuest();
    panel();
    fireEvent.click(within(await row(/Magdala/)).getByRole('button', { name: 'Start' }));
    expect(useQuestStore.getState().active).toBe(MAGDALA);

    const active = await row(/Magdala/);
    expect(active.textContent).toContain('battle where British General Robert Napier');
    expect(active.textContent).not.toContain('1868');
    expect(active.textContent).not.toContain(HIDDEN_YEAR);
    expect(within(active).getAllByRole('img', { name: 'year hidden' })).toHaveLength(1);
    expect(within(active).getByRole('img', { name: '3 of 3 stars' })).toBeTruthy();
    expect(within(active).queryByText(/Right place/)).toBeNull();
    // The other two can still be started instead.
    expect(screen.getAllByRole('button', { name: 'Start' })).toHaveLength(2);

    act(() => useQuestLive.getState().publish(reading()));
    expect(within(active).getByText('warm')).toBeTruthy();
    expect(within(active).getByText('later')).toBeTruthy();
    expect(within(active).getByText('cool')).toBeTruthy();
    expect(within(active).queryByText('zoom in')).toBeNull();

    act(() => useQuestLive.getState().publish(reading({ time: 'hot', direction: 'earlier', place: 'hot', zoomIn: true })));
    expect(within(active).getAllByText('hot')).toHaveLength(2);
    expect(within(active).getByText('earlier')).toBeTruthy();
    expect(within(active).getByText('zoom in')).toBeTruthy();

    // A reading for another target is not this one's.
    act(() => useQuestLive.getState().publish(reading({ id: HASTINGS, time: 'cold', place: 'cold' })));
    expect(within(active).queryByText('cold')).toBeNull();

    act(() => useQuestLive.getState().publish(reading({ time: 'here', direction: null, place: 'here', arrived: true })));
    expect(within(active).getAllByText('here')).toHaveLength(2);
    expect(within(active).getByText(/Right place, right time/)).toBeTruthy();
  });

  it('gives the hints, each for a star', async () => {
    stubQuest();
    useQuestStore.setState({ active: MAGDALA });
    panel();
    const active = await row(/Magdala/);
    act(() => useQuestLive.getState().publish(reading()));

    fireEvent.click(within(active).getByRole('button', { name: /When hint/ }));
    expect(useQuestStore.getState().targets[MAGDALA]).toEqual({ ...NO_PROGRESS, when: true });
    expect(within(active).getByText('1868 CE')).toBeTruthy();
    expect(active.textContent).toContain('1868 battle where British General Robert Napier');
    expect(within(active).queryByRole('button', { name: /When hint/ })).toBeNull();
    expect(within(active).getByRole('img', { name: '2 of 3 stars' })).toBeTruthy();

    fireEvent.click(within(active).getByRole('button', { name: /Where hint/ }));
    expect(useQuestStore.getState().targets[MAGDALA]).toEqual({ ...NO_PROGRESS, when: true, where: true });
    expect(within(active).getByText('Sub-Saharan Africa · Amhara, Ethiopia')).toBeTruthy();
    expect(within(active).getByText('about 4,300 km to the south')).toBeTruthy();
    expect(within(active).getByRole('img', { name: '1 of 3 stars' })).toBeTruthy();

    // The way there follows the map.
    act(() => useQuestLive.getState().publish(reading({ km: 650, compass: 'NE', arrow: 1, place: 'hot' })));
    expect(within(active).getByText('about 650 km to the north-east')).toBeTruthy();
    act(() => useQuestLive.getState().publish(reading({ km: 0, compass: null, arrow: null, place: 'here' })));
    expect(within(active).getByText('Under the middle of the map')).toBeTruthy();
  });

  it('shows a span of years, and only the region when the atlas names no place', async () => {
    stubQuest({
      data: {
        ...questPayload.data,
        targets: questPayload.data.targets.map((t) => (t.id === CANNAE ? { ...t, end_year: -202 } : t)),
      },
    });
    useQuestStore.setState({ active: CANNAE, targets: { [CANNAE]: { ...NO_PROGRESS, when: true, where: true } } });
    panel();
    const active = await row(/Cannae/);
    expect(within(active).getByText('216 BCE – 202 BCE')).toBeTruthy();
    expect(within(active).getByText('Europe')).toBeTruthy();
  });

  it('takes the reader there: the year through the URL, the flight on the map, no stars', async () => {
    stubQuest();
    const flyTo = vi.fn();
    const map = { getContainer: () => ({ clientWidth: 1440, clientHeight: 800 }), getZoom: () => 3, flyTo };
    useEphemeralStore.setState({ map: map as never, mapInsets: { top: 0, right: 0, bottom: 0, left: 0.25 } });
    useQuestStore.setState({ active: MAGDALA });
    panel();
    const active = await row(/Magdala/);

    fireEvent.click(within(active).getByRole('button', { name: /Take me there/ }));
    expect(useQuestStore.getState().targets[MAGDALA]).toEqual({ ...NO_PROGRESS, taken: true });
    expect(flyTo).toHaveBeenCalledTimes(1);
    expect(flyTo.mock.calls[0][0]).toMatchObject({
      center: [39.18, 11.35],
      padding: { top: 64, right: 24, bottom: 24, left: 384 },
    });
    expect(flyTo.mock.calls[0][0].zoom).toBeGreaterThanOrEqual(5.5);
    await vi.waitFor(() => expect(lastUrl()?.get('t')).toBe('1868'));
    expect(lastUrl()?.get('sel')).toBeNull();

    // Both hints are open now, and it says what that cost.
    expect(within(active).getByText('1868 CE')).toBeTruthy();
    expect(within(active).getByText('Sub-Saharan Africa · Amhara, Ethiopia')).toBeTruthy();
    expect(within(active).getByRole('img', { name: '0 of 3 stars' })).toBeTruthy();
    expect(within(active).getByText(/no stars this time/)).toBeTruthy();
    expect(within(active).queryByRole('button', { name: /hint/ })).toBeNull();
  });

  it('stops, keeping the hints taken', async () => {
    stubQuest();
    useQuestStore.setState({ active: MAGDALA, targets: { [MAGDALA]: { ...NO_PROGRESS, when: true } } });
    panel();
    fireEvent.click(within(await row(/Magdala/)).getByRole('button', { name: 'Stop' }));
    expect(useQuestStore.getState().active).toBeNull();
    expect(useQuestStore.getState().targets[MAGDALA]).toEqual({ ...NO_PROGRESS, when: true });
    const waiting = await row(/Magdala/);
    expect(within(waiting).getByRole('button', { name: 'Start' })).toBeTruthy();
    expect(waiting.textContent).not.toContain('Napier');
  });

  it('shows a found target with its stars and its summary, and opens it again at its year', async () => {
    stubQuest();
    useQuestStore.setState({ targets: { [HASTINGS]: { ...found, where: true } } });
    panel();
    const hastings = await row(/Hastings/);
    expect(within(hastings).getByRole('img', { name: '2 of 3 stars' })).toBeTruthy();
    expect(hastings.textContent).toContain('Fought on 14 October 1066');
    expect(within(hastings).queryByRole('button', { name: 'Start' })).toBeNull();
    expect(screen.getAllByRole('button', { name: 'Start' })).toHaveLength(2);

    fireEvent.click(within(hastings).getByRole('button'));
    await vi.waitFor(() => expect(lastUrl()?.get('sel')).toBe(HASTINGS));
    expect(lastUrl()?.get('t')).toBe('1066');
  });

  it('ends the day with the stars and a result to copy that names no target', async () => {
    stubQuest();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } });
    useQuestStore.setState({
      targets: { [HASTINGS]: found, [MAGDALA]: { ...found, when: true }, [CANNAE]: { ...found, taken: true } },
      streak: { count: 3, last: dayKey() },
    });
    panel();
    expect(await screen.findByText('All three found')).toBeTruthy();
    expect(screen.getByText(/5 of 9 stars/)).toBeTruthy();
    expect(screen.getByText('3-day streak')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Start' })).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: /Copy result/ }));
    expect(await screen.findByText('Copied')).toBeTruthy();
    expect(writeText).toHaveBeenCalledWith(
      ['History Mapped · Expedition 12', '★★★ easy', '★★☆ medium', '☆☆☆ hard', `${window.location.origin}/browse`].join('\n'),
    );
  });

  it('offers the result to copy by hand when the clipboard is refused', async () => {
    stubQuest();
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn().mockRejectedValue(new Error('denied')) },
    });
    useQuestStore.setState({ targets: { [HASTINGS]: found, [MAGDALA]: found, [CANNAE]: found } });
    panel();
    fireEvent.click(await screen.findByRole('button', { name: /Copy result/ }));
    const text = (await screen.findByRole('textbox', { name: 'Your result' })) as HTMLTextAreaElement;
    expect(text.value).toContain('History Mapped · Expedition 12\n★★★ easy\n★★★ medium\n★★★ hard\n');
  });

  it('shows a streak that still stands, and not one that lapsed', async () => {
    stubQuest();
    useQuestStore.setState({ streak: { count: 4, last: previousDayKey(dayKey()) } });
    const first = panel();
    expect(await screen.findByText('4-day streak')).toBeTruthy();
    first.unmount();
    useQuestStore.setState({ streak: { count: 4, last: previousDayKey(previousDayKey(dayKey())) } });
    panel();
    expect(await screen.findByRole('heading', { name: 'Expedition 12' })).toBeTruthy();
    expect(document.body.textContent).not.toContain('streak');
  });

  it('renders nothing when the endpoint is missing, or the day has no targets', async () => {
    stubQuest(null);
    const missing = panel();
    await vi.waitFor(() => expect(api.get).toHaveBeenCalled());
    await vi.waitFor(() => expect(missing.container.innerHTML).toBe(''));
    missing.unmount();

    vi.restoreAllMocks();
    stubQuest({ data: { ...questPayload.data, targets: [] } });
    const empty = panel();
    await vi.waitFor(() => expect(api.get).toHaveBeenCalled());
    await vi.waitFor(() => expect(empty.container.innerHTML).toBe(''));
  });
});

describe('QuestCard, on the browse page', { timeout: 30_000 }, () => {
  it('teases the day without the atlas’s URL state, and links into the Today tab', async () => {
    stubQuest();
    teaser();
    expect(await screen.findByRole('heading', { name: 'Expedition 12' })).toBeTruthy();
    for (const name of ['Battle of Hastings', 'Battle of Magdala', 'Battle of Cannae']) {
      expect(screen.getByText(name)).toBeTruthy();
    }
    for (const level of ['easy', 'medium', 'hard']) expect(screen.getByText(level)).toBeTruthy();
    expect(screen.getByText('Not started yet today.')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Start in the atlas' }).getAttribute('href')).toBe('/app?tab=today');
    // A teaser: nothing to press, no clue.
    expect(screen.queryByRole('button')).toBeNull();
    expect(document.body.textContent).not.toContain('Napier');
  });

  it('shows today’s progress from the store', async () => {
    stubQuest();
    useQuestStore.setState({ active: MAGDALA, targets: { [HASTINGS]: { ...found, when: true } } });
    const first = teaser();
    expect(await screen.findByText('1 of 3 found, 2 stars so far.')).toBeTruthy();
    expect(within(await row(/Hastings/)).getByRole('img', { name: '2 of 3 stars' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Continue in the atlas' }).getAttribute('href')).toBe('/app?tab=today');
    first.unmount();

    useQuestStore.setState({ active: null, targets: { [MAGDALA]: { ...NO_PROGRESS, where: true } } });
    const second = teaser();
    expect(await screen.findByText('Started, nothing found yet.')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Continue in the atlas' })).toBeTruthy();
    second.unmount();

    useQuestStore.setState({
      targets: { [HASTINGS]: found, [MAGDALA]: { ...found, taken: true }, [CANNAE]: { ...found, where: true } },
      streak: { count: 2, last: dayKey() },
    });
    teaser();
    expect(await screen.findByText('All three found: 5 of 9 stars.')).toBeTruthy();
    expect(screen.getByText('2-day streak')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'See it in the atlas' }).getAttribute('href')).toBe('/app?tab=today');
  });

  it('renders nothing when the endpoint is missing', async () => {
    stubQuest(null);
    const { container } = teaser();
    await vi.waitFor(() => expect(api.get).toHaveBeenCalled());
    await vi.waitFor(() => expect(container.innerHTML).toBe(''));
  });
});
