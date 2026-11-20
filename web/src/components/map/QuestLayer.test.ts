// @vitest-environment jsdom
/**
 * The expedition's map layer against a stand-in map (a flat web-mercator
 * camera with MapLibre's event names) and a stand-in `maplibregl.Marker`:
 * what it listens to and when, when the marker is on the map, what a click on
 * it does, and that nothing is left behind.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, configure, fireEvent, render, screen } from '@testing-library/react';
import { NuqsTestingAdapter } from 'nuqs/adapters/testing';
import type { UrlUpdateEvent } from 'nuqs/adapters/testing';
import { createElement, Fragment, useEffect } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useTimeState } from '@/hooks';
import { api } from '@/lib/api/client';
import { dayKey } from '@/lib/discover/date';
import { NO_PROGRESS } from '@/lib/discover/quest';
import type { LngLat } from '@/lib/discover/quest';
import { useQuestLive, useQuestStore } from '@/lib/discover/quest-store';
import { CANNAE, HASTINGS, MAGDALA, questPayload } from '@/lib/discover/quest.fixtures';
import { useEphemeralStore } from '@/stores/ephemeral';
import { QuestLayer } from './QuestLayer';

const fake = vi.hoisted(() => {
  /** Stands in for `maplibregl.Marker`: remembers where it was put and whether it was taken off. */
  class Marker {
    element: HTMLElement;
    lngLat: [number, number] | null = null;
    removed = false;
    constructor({ element }: { element: HTMLElement }) {
      this.element = element;
      markers.push(this);
    }
    setLngLat(lngLat: [number, number]) {
      this.lngLat = lngLat;
      return this;
    }
    addTo(map: { getCanvasContainer(): HTMLElement }) {
      map.getCanvasContainer().appendChild(this.element);
      return this;
    }
    remove() {
      this.removed = true;
      this.element.remove();
      return this;
    }
  }
  const markers: Marker[] = [];
  return { Marker, markers };
});
vi.mock('maplibre-gl', () => ({ default: { Marker: fake.Marker } }));

// The first render pays for importing the hook barrel; give it room on a busy machine.
configure({ asyncUtilTimeout: 15_000 });

const AT_HASTINGS: LngLat = [0.49, 50.91];
const AT_MAGDALA: LngLat = [39.18, 11.35];
const FAR_AWAY: LngLat = [-60, -20];

/** A 1440 × 800 map looking at `FAR_AWAY` from zoom 2, with MapLibre's `on` / `off`. */
function stage() {
  const width = 1440;
  const height = 800;
  let center = FAR_AWAY;
  let zoom = 2;
  const listeners = new Map<string, Set<() => void>>();
  const canvas = document.createElement('div');
  document.body.appendChild(canvas);
  const world = () => 512 * 2 ** zoom;
  const x = (lng: number) => ((lng + 180) / 360) * world();
  const y = (lat: number) => (0.5 - Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360)) / (2 * Math.PI)) * world();
  const map = {
    on(type: string, listener: () => void) {
      if (!listeners.has(type)) listeners.set(type, new Set());
      listeners.get(type)?.add(listener);
      return map;
    },
    off(type: string, listener: () => void) {
      listeners.get(type)?.delete(listener);
      return map;
    },
    getContainer: () => ({ clientWidth: width, clientHeight: height }),
    getCanvasContainer: () => canvas,
    project: vi.fn(([lng, lat]: LngLat) => ({ x: x(lng) - x(center[0]) + width / 2, y: y(lat) - y(center[1]) + height / 2 })),
    unproject: vi.fn(([px, py]: [number, number]) => ({
      lng: ((px - width / 2 + x(center[0])) / world()) * 360 - 180,
      lat: (Math.atan(Math.exp((0.5 - (py - height / 2 + y(center[1])) / world()) * 2 * Math.PI)) * 360) / Math.PI - 90,
    })),
    getBearing: () => 0,
    getZoom: () => zoom,
    flyTo: vi.fn(),
  };
  return {
    map,
    canvas,
    /** How many listeners the map holds, of one type or in all. */
    listening: (type?: string) =>
      type ? (listeners.get(type)?.size ?? 0) : [...listeners.values()].reduce((n, set) => n + set.size, 0),
    fire: (type: string) => listeners.get(type)?.forEach((listener) => listener()),
    look: (to: LngLat, at: number) => {
      center = to;
      zoom = at;
    },
  };
}
type Stage = ReturnType<typeof stage>;

const frame = () => new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));

/** Move the camera as a drag or a flight would, and let the frame that follows run. */
async function look(on: Stage, to: LngLat, zoom: number) {
  await act(async () => {
    on.look(to, zoom);
    on.fire('move');
    await frame();
  });
}

const urlUpdates: UrlUpdateEvent[] = [];
const lastUrl = (): URLSearchParams | undefined => urlUpdates[urlUpdates.length - 1]?.searchParams;

/** The timeline, for the test to turn. */
const timeline: { set: (year: number) => void } = { set: () => {} };
function Timeline() {
  const { setInstant } = useTimeState();
  useEffect(() => {
    timeline.set = (year) => void setInstant(year);
  });
  return null;
}

async function turnTo(year: number) {
  await act(async () => {
    timeline.set(year);
    await frame();
  });
}

function mount(search: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    createElement(
      QueryClientProvider,
      { client },
      createElement(NuqsTestingAdapter, {
        hasMemory: true,
        searchParams: search,
        onUrlUpdate: (event) => urlUpdates.push(event),
        children: createElement(
          MemoryRouter,
          null,
          createElement(Fragment, null, createElement(Timeline), createElement(QuestLayer)),
        ),
      }),
    ),
  );
}

const strip = () => screen.queryByText(/^Battle of/)?.closest('div') ?? null;
const live = () => fake.markers.filter((marker) => !marker.removed);

let on: Stage;

beforeEach(() => {
  localStorage.clear();
  urlUpdates.length = 0;
  fake.markers.length = 0;
  on = stage();
  useQuestStore.setState({ date: dayKey(), active: null, targets: {}, streak: { count: 0, last: null } });
  useQuestLive.getState().clear();
  useEphemeralStore.setState({
    map: on.map as never,
    mapInsets: { top: 0, right: 0, bottom: 0, left: 0 },
    liveScrub: null,
    sheet: 'peek',
  });
  vi.spyOn(api, 'get').mockImplementation(async () => ({ data: questPayload }));
  // jsdom has no matchMedia (the atlas hooks ask whether this is a phone).
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: (query: string) => ({ matches: false, media: query, addEventListener: vi.fn(), removeEventListener: vi.fn() }),
  });
});

afterEach(() => {
  cleanup();
  on.canvas.remove();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('QuestLayer', { timeout: 30_000 }, () => {
  it('does nothing at all while no target is being looked for', async () => {
    const { container } = mount('?t=1066');
    await act(async () => {
      on.look(AT_HASTINGS, 6);
      on.fire('move');
      on.fire('moveend');
      await frame();
    });
    expect(container.innerHTML).toBe('');
    expect(on.listening()).toBe(0);
    expect(on.map.unproject).not.toHaveBeenCalled();
    expect(api.get).not.toHaveBeenCalled();
    expect(fake.markers).toHaveLength(0);
    expect(useQuestLive.getState().reading).toBeNull();
  });

  it('says how warm the reader is, reading the map once a frame at most', async () => {
    useQuestStore.setState({ active: HASTINGS });
    mount('?t=1500');
    expect(await screen.findByText('Battle of Hastings')).toBeTruthy();
    expect(on.listening('move')).toBe(1);
    expect(on.listening('moveend')).toBe(1);
    expect(on.listening()).toBe(2);
    expect(screen.getByText('cool')).toBeTruthy();
    expect(screen.getByText('earlier')).toBeTruthy();
    expect(screen.getByText('cold')).toBeTruthy();
    expect(useQuestLive.getState().reading).toMatchObject({ id: HASTINGS, time: 'cool', place: 'cold', arrived: false });

    // A burst of camera moves before the next frame is one reading: the middle and two corners.
    on.map.unproject.mockClear();
    await act(async () => {
      on.look([-10, 40], 3);
      for (let i = 0; i < 8; i++) on.fire('move');
      await frame();
    });
    expect(on.map.unproject).toHaveBeenCalledTimes(3);
    expect(screen.getByText('warm')).toBeTruthy();

    // Over the target but from too far out: hot, with the cue.
    await look(on, AT_HASTINGS, 3);
    expect(screen.getByText('hot')).toBeTruthy();
    expect(screen.getByText('zoom in')).toBeTruthy();
    await look(on, AT_HASTINGS, 6);
    expect(screen.getByText('here')).toBeTruthy();
    expect(screen.queryByText('zoom in')).toBeNull();
    // Right place, wrong year: nothing on the map.
    expect(fake.markers).toHaveLength(0);
  });

  it('puts the marker on the map on arrival and takes it off when the reader leaves', async () => {
    useQuestStore.setState({ active: HASTINGS });
    mount('?t=1500');
    await screen.findByText('Battle of Hastings');
    await look(on, AT_HASTINGS, 6);
    expect(live()).toHaveLength(0);

    await turnTo(1066);
    expect(live()).toHaveLength(1);
    expect(live()[0].lngLat).toEqual(AT_HASTINGS);
    expect(on.canvas.contains(live()[0].element)).toBe(true);
    expect(live()[0].element.getAttribute('aria-label')).toContain('Battle of Hastings');
    expect(screen.getByText(/Right place, right time/)).toBeTruthy();
    expect(screen.queryByText('here')).toBeNull();
    expect(useQuestLive.getState().reading?.arrived).toBe(true);

    // Out to a view of half the world: no longer there.
    await look(on, AT_HASTINGS, 3);
    expect(live()).toHaveLength(0);
    expect(on.canvas.childElementCount).toBe(0);
    expect(screen.getByText('zoom in')).toBeTruthy();

    // Back in, then off in time.
    await look(on, AT_HASTINGS, 6);
    expect(live()).toHaveLength(1);
    await turnTo(1700);
    expect(live()).toHaveLength(0);
    expect(fake.markers).toHaveLength(2);
    expect(fake.markers.every((marker) => marker.removed)).toBe(true);
    // One pair of listeners throughout.
    expect(on.listening()).toBe(2);
  });

  it('follows the timeline while it is dragged, but arrives only on the year it is let go at', async () => {
    useQuestStore.setState({ active: HASTINGS });
    mount('?t=1500');
    await screen.findByText('Battle of Hastings');
    await look(on, AT_HASTINGS, 6);

    // Dragging over the target's year: both meters say here, the marker waits.
    await act(async () => {
      useEphemeralStore.getState().setLiveScrub(1066);
      await frame();
    });
    expect(screen.getAllByText('here')).toHaveLength(2);
    expect(live()).toHaveLength(0);

    // Dragging on past it.
    await act(async () => {
      useEphemeralStore.getState().setLiveScrub(1200);
      await frame();
    });
    expect(screen.getByText('warm')).toBeTruthy();
    expect(live()).toHaveLength(0);

    // Let go on the year (the timeline commits it, then ends the drag).
    await act(async () => {
      timeline.set(1066);
      useEphemeralStore.getState().setLiveScrub(null);
      await frame();
    });
    expect(live()).toHaveLength(1);

    // A new drag away keeps the marker until that year is let go too.
    await act(async () => {
      useEphemeralStore.getState().setLiveScrub(1400);
      await frame();
    });
    expect(live()).toHaveLength(1);
    await act(async () => {
      timeline.set(1400);
      useEphemeralStore.getState().setLiveScrub(null);
      await frame();
    });
    expect(live()).toHaveLength(0);
  });

  it('finds the target on a click of the marker, which never reaches the map', async () => {
    useQuestStore.setState({ active: HASTINGS, targets: { [HASTINGS]: { ...NO_PROGRESS, when: true } } });
    mount('?t=1066');
    await screen.findByText('Battle of Hastings');
    await look(on, AT_HASTINGS, 6);
    const [marker] = live();
    expect(marker).toBeTruthy();

    const mapClick = vi.fn();
    on.canvas.addEventListener('click', mapClick);
    fireEvent.click(marker.element);
    expect(mapClick).not.toHaveBeenCalled();

    const state = useQuestStore.getState();
    expect(state.active).toBeNull();
    expect(state.targets[HASTINGS]).toEqual({ ...NO_PROGRESS, when: true, found: true });
    expect(state.streak).toEqual({ count: 0, last: null });
    await vi.waitFor(() => expect(lastUrl()?.get('sel')).toBe(HASTINGS));

    // The hunt is over: no marker, no listener, no reading; the strip says what was earned.
    expect(marker.removed).toBe(true);
    expect(on.canvas.childElementCount).toBe(0);
    expect(on.listening()).toBe(0);
    expect(useQuestLive.getState().reading).toBeNull();
    expect(screen.getByText('Found: Battle of Hastings')).toBeTruthy();
    expect(screen.getByRole('img', { name: '2 of 3 stars' })).toBeTruthy();
    expect(screen.getByText('1 of 3 found')).toBeTruthy();

    // …until the next target is started.
    act(() => useQuestStore.getState().start(MAGDALA));
    expect(screen.queryByText(/^Found:/)).toBeNull();
    expect(await screen.findByText('Battle of Magdala')).toBeTruthy();
    act(() => useQuestStore.getState().stop());
    expect(screen.queryByText(/^Found:/)).toBeNull();
  });

  it('lets the note of a find go after a few seconds', async () => {
    useQuestStore.setState({ active: HASTINGS });
    mount('?t=1066');
    await screen.findByText('Battle of Hastings');
    await look(on, AT_HASTINGS, 6);
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
    fireEvent.click(live()[0].element);
    expect(screen.getByText('Found: Battle of Hastings')).toBeTruthy();
    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(screen.getByText('Found: Battle of Hastings')).toBeTruthy();
    act(() => {
      vi.advanceTimersByTime(1500);
    });
    expect(screen.queryByText(/^Found:/)).toBeNull();
  });

  it('counts the streak on the day’s last find', async () => {
    const found = { ...NO_PROGRESS, found: true };
    useQuestStore.setState({ active: MAGDALA, targets: { [HASTINGS]: found, [CANNAE]: { ...found, taken: true } } });
    mount('?t=1868');
    await screen.findByText('Battle of Magdala');
    await look(on, AT_MAGDALA, 6);
    fireEvent.click(live()[0].element);
    expect(useQuestStore.getState().streak).toEqual({ count: 1, last: dayKey() });
    expect(screen.getByText('Expedition complete, 6 of 9 stars')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Result' })).toBeTruthy();
  });

  it('moves everything to another target when one is started instead', async () => {
    useQuestStore.setState({ active: HASTINGS });
    mount('?t=1066');
    await screen.findByText('Battle of Hastings');
    await look(on, AT_HASTINGS, 6);
    const [first] = live();
    expect(first).toBeTruthy();

    act(() => useQuestStore.getState().start(MAGDALA));
    expect(await screen.findByText('Battle of Magdala')).toBeTruthy();
    expect(first.removed).toBe(true);
    expect(live()).toHaveLength(0);
    expect(on.listening('move')).toBe(1);
    expect(on.listening('moveend')).toBe(1);
    expect(useQuestLive.getState().reading).toMatchObject({ id: MAGDALA, arrived: false });

    await turnTo(1868);
    await look(on, AT_MAGDALA, 6);
    expect(live()).toHaveLength(1);
    expect(live()[0].lngLat).toEqual(AT_MAGDALA);
  });

  it('leaves nothing behind when it unmounts', async () => {
    useQuestStore.setState({ active: HASTINGS });
    const { unmount } = mount('?t=1066');
    await screen.findByText('Battle of Hastings');
    await look(on, AT_HASTINGS, 6);
    expect(live()).toHaveLength(1);

    // A frame is still pending when it goes.
    on.fire('move');
    unmount();
    expect(live()).toHaveLength(0);
    expect(on.canvas.childElementCount).toBe(0);
    expect(on.listening()).toBe(0);
    expect(useQuestLive.getState().reading).toBeNull();
    on.map.unproject.mockClear();
    await frame();
    useEphemeralStore.getState().setLiveScrub(1066);
    await frame();
    expect(on.map.unproject).not.toHaveBeenCalled();
    expect(useQuestLive.getState().reading).toBeNull();
  });

  it.each(['chron=the-roman-world', 'story=battle-of-hastings'])(
    'stands down while a chronicle or a battle map plays (%s)',
    async (playing) => {
      useQuestStore.setState({ active: HASTINGS });
      on.look(AT_HASTINGS, 6);
      const { container } = mount(`?t=1066&${playing}`);
      await vi.waitFor(() => expect(api.get).toHaveBeenCalled());
      await act(async () => {
        on.fire('move');
        await frame();
      });
      expect(container.innerHTML).toBe('');
      expect(fake.markers).toHaveLength(0);
      expect(on.listening()).toBe(0);
      expect(useQuestLive.getState().reading).toBeNull();
    },
  );

  it('reads again when the panels over the map change, without the map moving', async () => {
    useQuestStore.setState({ active: HASTINGS });
    mount('?t=1066');
    await screen.findByText('Battle of Hastings');
    await look(on, AT_HASTINGS, 6);
    expect(live()).toHaveLength(1);

    // A panel slides over the target: it is no longer in view.
    act(() => useEphemeralStore.setState({ mapInsets: { top: 0, right: 0, bottom: 0, left: 0.6 } }));
    expect(live()).toHaveLength(0);
    expect(screen.getByText('hot')).toBeTruthy();
    // The strip keeps to what is left of the map.
    expect((strip()?.parentElement as HTMLElement).style.left).toBe('60%');

    act(() => useEphemeralStore.setState({ mapInsets: { top: 0, right: 0, bottom: 0, left: 0.24 } }));
    expect(live()).toHaveLength(1);
  });

  it('lets the distance through a few times a second, and once more when the map rests', async () => {
    let clock = 10_000;
    vi.spyOn(performance, 'now').mockImplementation(() => clock);
    useQuestStore.setState({ active: MAGDALA });
    mount('?t=1500');
    await screen.findByText('Battle of Magdala');
    const published = vi.fn();
    const unsubscribe = useQuestLive.subscribe(published);
    const km = () => useQuestLive.getState().reading?.km;
    const start = km();

    // Creeping east, cold all the way: the distance changes, the words do not.
    clock += 40;
    await look(on, [-50, -20], 2);
    clock += 40;
    await look(on, [-40, -20], 2);
    expect(published).not.toHaveBeenCalled();
    expect(km()).toBe(start);

    // Later in the same drag it goes through.
    clock += 100;
    await look(on, [-30, -20], 2);
    expect(published).toHaveBeenCalledTimes(1);
    const mid = km();
    expect(mid).toBeLessThan(start ?? 0);

    // The map comes to rest a moment after one more move: the last distance is shown at once.
    clock += 20;
    await look(on, [-20, -20], 2);
    expect(published).toHaveBeenCalledTimes(1);
    act(() => on.fire('moveend'));
    expect(published).toHaveBeenCalledTimes(2);
    expect(km()).toBeLessThan(mid ?? 0);

    // A change of warmth never waits.
    clock += 1;
    await look(on, [20, 11], 2);
    expect(published).toHaveBeenCalledTimes(3);
    expect(useQuestLive.getState().reading?.place).toBe('warm');
    unsubscribe();
  });

  it('opens the Today tab from the strip, the only part of it that takes clicks', async () => {
    useQuestStore.setState({ active: HASTINGS });
    mount('?t=1500');
    await screen.findByText('Battle of Hastings');
    const box = strip()?.parentElement as HTMLElement;
    expect(box.className).toContain('pointer-events-none');
    const button = screen.getByRole('button', { name: 'Hints' });
    expect(button.className).toContain('pointer-events-auto');
    fireEvent.click(button);
    await vi.waitFor(() => expect(lastUrl()?.get('tab')).toBe('today'));
    // On a phone the list is in the sheet: a peeking sheet is lifted.
    expect(useEphemeralStore.getState().sheet).toBe('half');
  });
});
