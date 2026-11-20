import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { QuestReading } from './quest';
import type { QuestState } from './quest-store';

const KEY = 'hm-quest';
const A = 'target-a';
const B = 'target-b';
const C = 'target-c';
const ALL = [A, B, C];

/** Noon on a day of November 2026, local time (what `dayKey` reads). */
const november = (day: number, hour = 12) => new Date(2026, 10, day, hour);

/** A fresh copy of the module: it reads storage when first imported. */
const load = () => import('./quest-store');
const saved = (): unknown => JSON.parse(localStorage.getItem(KEY) ?? 'null');
/** The saved part of the store's state (without its actions). */
const data = ({ v, date, active, targets, streak }: QuestState): QuestState => ({ v, date, active, targets, streak });

const progress = (patch: Partial<Record<'when' | 'where' | 'taken' | 'found', boolean>> = {}) => ({
  when: false,
  where: false,
  taken: false,
  found: false,
  ...patch,
});

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(november(20));
  vi.resetModules();
  localStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe('the expedition store', () => {
  it('starts empty, for today, and writes nothing until something changes', async () => {
    const write = vi.spyOn(Storage.prototype, 'setItem');
    const { useQuestStore } = await load();
    expect(data(useQuestStore.getState())).toEqual({
      v: 1,
      date: '2026-11-20',
      active: null,
      targets: {},
      streak: { count: 0, last: null },
    });
    expect(write).not.toHaveBeenCalled();
  });

  it('saves on every change, in the saved shape', async () => {
    const { useQuestStore } = await load();
    const { start, hint, stop } = useQuestStore.getState();
    start(A);
    expect(saved()).toEqual({ v: 1, date: '2026-11-20', active: A, targets: {}, streak: { count: 0, last: null } });
    hint(A, 'when');
    expect(saved()).toMatchObject({ active: A, targets: { [A]: progress({ when: true }) } });
    stop();
    expect(saved()).toMatchObject({ active: null, targets: { [A]: progress({ when: true }) } });
  });

  it('does not write a state that did not change', async () => {
    const { useQuestStore } = await load();
    useQuestStore.getState().start(A);
    const write = vi.spyOn(Storage.prototype, 'setItem');
    useQuestStore.getState().start(A);
    useQuestStore.getState().sync();
    expect(write).not.toHaveBeenCalled();
    useQuestStore.getState().stop();
    expect(write).toHaveBeenCalledTimes(1);
    useQuestStore.getState().stop();
    expect(write).toHaveBeenCalledTimes(1);
  });

  it('keeps each target’s hints when another is started', async () => {
    const { useQuestStore } = await load();
    const { start, hint, take } = useQuestStore.getState();
    start(A);
    hint(A, 'where');
    start(B);
    take(B);
    expect(useQuestStore.getState().active).toBe(B);
    expect(useQuestStore.getState().targets).toEqual({
      [A]: progress({ where: true }),
      [B]: progress({ taken: true }),
    });
  });

  it('marks a find, clears the active target and freezes what it earned', async () => {
    const { useQuestStore } = await load();
    const { start, hint, take, find } = useQuestStore.getState();
    start(A);
    hint(A, 'when');
    find(A, ALL);
    expect(useQuestStore.getState().active).toBeNull();
    expect(useQuestStore.getState().targets[A]).toEqual(progress({ when: true, found: true }));
    // Nothing done to a found target changes it, and it cannot be started again.
    hint(A, 'where');
    take(A);
    start(A);
    find(A, ALL);
    expect(useQuestStore.getState().active).toBeNull();
    expect(useQuestStore.getState().targets[A]).toEqual(progress({ when: true, found: true }));
  });

  it('counts the streak when the day’s last target is found, once', async () => {
    const { useQuestStore } = await load();
    const { find } = useQuestStore.getState();
    find(A, ALL);
    find(B, ALL);
    expect(useQuestStore.getState().streak).toEqual({ count: 0, last: null });
    find(C, ALL);
    expect(useQuestStore.getState().streak).toEqual({ count: 1, last: '2026-11-20' });
    find(C, ALL);
    find('stray', [...ALL, 'stray']);
    expect(useQuestStore.getState().streak).toEqual({ count: 1, last: '2026-11-20' });
    expect(saved()).toMatchObject({ streak: { count: 1, last: '2026-11-20' } });
  });

  it('grows the streak on the next day and starts it again after a gap', async () => {
    const { useQuestStore } = await load();
    const complete = () => ALL.forEach((id) => useQuestStore.getState().find(id, ALL));
    complete();
    vi.setSystemTime(november(21));
    complete();
    expect(useQuestStore.getState().streak).toEqual({ count: 2, last: '2026-11-21' });
    vi.setSystemTime(november(22, 0));
    complete();
    expect(useQuestStore.getState().streak).toEqual({ count: 3, last: '2026-11-22' });
    vi.setSystemTime(november(24));
    complete();
    expect(useQuestStore.getState().streak).toEqual({ count: 1, last: '2026-11-24' });
  });

  it('comes back from storage on the same day', async () => {
    const first = await load();
    first.useQuestStore.getState().find(B, ALL);
    first.useQuestStore.getState().start(A);
    first.useQuestStore.getState().hint(A, 'when');
    vi.resetModules();
    const second = await load();
    expect(second.useQuestStore).not.toBe(first.useQuestStore);
    expect(data(second.useQuestStore.getState())).toEqual(data(first.useQuestStore.getState()));
    expect(second.useQuestStore.getState().active).toBe(A);
  });
});

describe('a new day', () => {
  const yesterday = {
    v: 1,
    date: '2026-11-19',
    active: A,
    targets: { [A]: progress({ when: true }), [B]: progress({ found: true }) },
    streak: { count: 4, last: '2026-11-18' },
  };

  it('clears the targets and the active one on load, and keeps the streak', async () => {
    localStorage.setItem(KEY, JSON.stringify(yesterday));
    const { useQuestStore } = await load();
    expect(data(useQuestStore.getState())).toEqual({
      v: 1,
      date: '2026-11-20',
      active: null,
      targets: {},
      streak: { count: 4, last: '2026-11-18' },
    });
  });

  it('rolls over when the clock passes midnight with the page open', async () => {
    const { useQuestStore } = await load();
    useQuestStore.getState().start(A);
    useQuestStore.getState().hint(A, 'where');
    ALL.forEach((id) => useQuestStore.getState().find(id, ALL));
    useQuestStore.getState().sync();
    expect(useQuestStore.getState().date).toBe('2026-11-20');
    expect(Object.keys(useQuestStore.getState().targets)).toHaveLength(3);

    vi.setSystemTime(november(21, 0));
    useQuestStore.getState().sync();
    expect(data(useQuestStore.getState())).toEqual({
      v: 1,
      date: '2026-11-21',
      active: null,
      targets: {},
      streak: { count: 1, last: '2026-11-20' },
    });
    expect(saved()).toMatchObject({ date: '2026-11-21', targets: {}, streak: { count: 1, last: '2026-11-20' } });
  });

  it('rolls over before anything is done to a state left from the day before', async () => {
    const { useQuestStore } = await load();
    useQuestStore.getState().start(A);
    useQuestStore.getState().hint(A, 'when');
    vi.setSystemTime(november(21, 9));
    useQuestStore.getState().hint(B, 'where');
    expect(data(useQuestStore.getState())).toMatchObject({
      date: '2026-11-21',
      active: null,
      targets: { [B]: progress({ where: true }) },
    });
    vi.setSystemTime(november(22, 9));
    useQuestStore.getState().stop();
    expect(data(useQuestStore.getState())).toMatchObject({ date: '2026-11-22', active: null, targets: {} });
  });

  it('keeps the page’s day current through the hook: at midnight and when the tab comes back', async () => {
    const { useQuestStore, useQuestDay } = await load();
    useQuestStore.getState().start(A);
    const { result, unmount } = renderHook(() => useQuestDay());
    expect(result.current).toBe('2026-11-20');

    // Twelve hours and a little: the timer set for midnight fires.
    act(() => {
      vi.advanceTimersByTime(12 * 3_600_000 + 5000);
    });
    expect(result.current).toBe('2026-11-21');
    expect(useQuestStore.getState().active).toBeNull();

    // The machine slept through the next midnight: no timer fired, the tab wakes up.
    vi.setSystemTime(november(23, 8));
    act(() => {
      document.dispatchEvent(new Event('visibilitychange'));
    });
    expect(result.current).toBe('2026-11-23');

    // Unmounted: the midnight timer and both listeners are gone.
    unmount();
    vi.advanceTimersByTime(48 * 3_600_000);
    window.dispatchEvent(new Event('focus'));
    document.dispatchEvent(new Event('visibilitychange'));
    expect(useQuestStore.getState().date).toBe('2026-11-23');
  });
});

describe('what storage holds', () => {
  it.each([
    ['not json', '{oops'],
    ['null', 'null'],
    ['an array', '[1, 2]'],
    ['a string', '"hm"'],
    ['another version', JSON.stringify({ v: 2, date: '2026-11-20', active: A, targets: {}, streak: { count: 9, last: '2026-11-19' } })],
  ])('starts fresh from %s', async (_what, raw) => {
    localStorage.setItem(KEY, raw);
    const { useQuestStore } = await load();
    expect(data(useQuestStore.getState())).toEqual({
      v: 1,
      date: '2026-11-20',
      active: null,
      targets: {},
      streak: { count: 0, last: null },
    });
    useQuestStore.getState().start(A);
    expect(saved()).toMatchObject({ v: 1, active: A });
  });

  it('drops what is malformed and keeps the rest', async () => {
    localStorage.setItem(
      KEY,
      JSON.stringify({
        v: 1,
        date: '2026-11-20',
        active: 7,
        targets: { [A]: { when: 'yes', where: true, found: 1 }, [B]: 'found', [C]: progress({ found: true }) },
        streak: { count: 3, last: '2026-11-19' },
      }),
    );
    const { parseQuestState, useQuestStore } = await load();
    expect(data(useQuestStore.getState())).toEqual({
      v: 1,
      date: '2026-11-20',
      active: null,
      targets: { [A]: progress({ where: true }), [C]: progress({ found: true }) },
      streak: { count: 3, last: '2026-11-19' },
    });
    const withStreak = (streak: unknown) =>
      parseQuestState(JSON.stringify({ v: 1, date: '2026-11-20', active: null, targets: {}, streak }), '2026-11-20').streak;
    expect(withStreak({ count: 2.5, last: '2026-11-19' })).toEqual({ count: 0, last: null });
    expect(withStreak({ count: -1, last: '2026-11-19' })).toEqual({ count: 0, last: null });
    expect(withStreak({ count: 2, last: 'yesterday' })).toEqual({ count: 0, last: null });
    expect(withStreak('3')).toEqual({ count: 0, last: null });
    // Targets that are not a record: the streak is still worth keeping.
    expect(
      parseQuestState(
        JSON.stringify({ v: 1, date: '2026-11-20', active: A, targets: 'x', streak: { count: 3, last: '2026-11-19' } }),
        '2026-11-20',
      ),
    ).toEqual({ v: 1, date: '2026-11-20', active: null, targets: {}, streak: { count: 3, last: '2026-11-19' } });
  });

  it('does not leave a found target active', async () => {
    localStorage.setItem(
      KEY,
      JSON.stringify({ v: 1, date: '2026-11-20', active: A, targets: { [A]: progress({ found: true }) }, streak: {} }),
    );
    const { useQuestStore } = await load();
    expect(useQuestStore.getState().active).toBeNull();
  });
});

describe('without storage', () => {
  /** A whole day played; gives the store back. */
  const play = async () => {
    const { useQuestStore } = await load();
    const { start, hint, find } = useQuestStore.getState();
    start(A);
    hint(A, 'when');
    find(A, ALL);
    find(B, ALL);
    find(C, ALL);
    return useQuestStore;
  };
  const played = {
    v: 1,
    date: '2026-11-20',
    active: null,
    targets: { [A]: progress({ when: true, found: true }), [B]: progress({ found: true }), [C]: progress({ found: true }) },
    streak: { count: 1, last: '2026-11-20' },
  };

  it('plays on when reading throws', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('denied', 'SecurityError');
    });
    expect(data((await play()).getState())).toEqual(played);
  });

  it('plays on when writing throws', async () => {
    const write = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('full', 'QuotaExceededError');
    });
    expect(data((await play()).getState())).toEqual(played);
    expect(write).toHaveBeenCalled();
    expect(localStorage.getItem(KEY)).toBeNull();
  });

  it('plays on when the storage itself cannot be reached', async () => {
    const real = window.localStorage;
    const original = Object.getOwnPropertyDescriptor(window, 'localStorage');
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      get() {
        throw new DOMException('denied', 'SecurityError');
      },
    });
    try {
      const store = await play();
      expect(data(store.getState())).toEqual(played);
      // Another tab's write cannot be told from another storage's: it is left alone, without a throw.
      window.dispatchEvent(new StorageEvent('storage', { key: KEY, newValue: null, storageArea: real }));
      expect(data(store.getState())).toEqual(played);
    } finally {
      if (original) Object.defineProperty(window, 'localStorage', original);
      else Reflect.deleteProperty(window, 'localStorage');
    }
  });
});

describe('another tab', () => {
  const theirs = {
    v: 1,
    date: '2026-11-20',
    active: B,
    targets: { [A]: progress({ found: true }) },
    streak: { count: 2, last: '2026-11-19' },
  };

  it('is followed, without writing its state back', async () => {
    const { useQuestStore } = await load();
    useQuestStore.getState().start(A);
    const write = vi.spyOn(Storage.prototype, 'setItem');
    window.dispatchEvent(
      new StorageEvent('storage', { key: KEY, newValue: JSON.stringify(theirs), storageArea: localStorage }),
    );
    expect(data(useQuestStore.getState())).toEqual(theirs);
    expect(write).not.toHaveBeenCalled();
    // …and this tab goes on from there.
    useQuestStore.getState().find(B, ALL);
    expect(write).toHaveBeenCalledTimes(1);
    expect(saved()).toMatchObject({ active: null, targets: { [A]: progress({ found: true }), [B]: progress({ found: true }) } });
  });

  it('is ignored when it changed some other key, or another storage', async () => {
    const { useQuestStore } = await load();
    useQuestStore.getState().start(A);
    window.dispatchEvent(new StorageEvent('storage', { key: 'hm-theme', newValue: 'dark', storageArea: localStorage }));
    window.dispatchEvent(
      new StorageEvent('storage', { key: KEY, newValue: JSON.stringify(theirs), storageArea: sessionStorage }),
    );
    expect(useQuestStore.getState().active).toBe(A);
  });

  it('clearing the storage starts this tab afresh', async () => {
    const { useQuestStore } = await load();
    useQuestStore.getState().start(A);
    window.dispatchEvent(new StorageEvent('storage', { key: null, newValue: null, storageArea: localStorage }));
    expect(data(useQuestStore.getState())).toMatchObject({ active: null, targets: {} });
  });
});

describe('the live reading', () => {
  const reading: QuestReading = {
    id: A,
    time: 'warm',
    direction: 'later',
    place: 'cool',
    zoomIn: false,
    compass: 'NE',
    arrow: 1,
    km: 4300,
    arrived: false,
  };

  it('is held until it changes, and is never saved', async () => {
    const { useQuestLive } = await load();
    const write = vi.spyOn(Storage.prototype, 'setItem');
    const heard = vi.fn();
    useQuestLive.subscribe(heard);

    useQuestLive.getState().publish(reading);
    expect(useQuestLive.getState().reading).toBe(reading);
    // The same values again: the held object stays, nobody is told.
    useQuestLive.getState().publish({ ...reading });
    expect(useQuestLive.getState().reading).toBe(reading);
    expect(heard).toHaveBeenCalledTimes(1);

    useQuestLive.getState().publish({ ...reading, km: 4200 });
    expect(useQuestLive.getState().reading?.km).toBe(4200);
    expect(heard).toHaveBeenCalledTimes(2);

    useQuestLive.getState().clear();
    useQuestLive.getState().clear();
    expect(useQuestLive.getState().reading).toBeNull();
    expect(heard).toHaveBeenCalledTimes(3);
    expect(write).not.toHaveBeenCalled();
  });
});
