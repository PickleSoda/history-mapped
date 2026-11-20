// @vitest-environment jsdom
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  EMPTY_RECENTS,
  MAX_RECENT_ENTITIES,
  MAX_RECENT_SEARCHES,
  RECENTS_KEY,
  clearRecents,
  createRecentsStore,
  getRecents,
  parseRecents,
  recentEntityIds,
  recordRecentEntity,
  recordRecentSearch,
  useRecents,
  withEntity,
  withSearch,
} from './recents';

/** A well-formed entity id for the n-th test entity. */
const id = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;

/** A Storage over a Map; `broken` makes reads and/or writes throw, as private windows do. */
function memoryStorage(broken: { read?: boolean; write?: boolean } = {}): Storage & { map: Map<string, string> } {
  const map = new Map<string, string>();
  return {
    map,
    get length() {
      return map.size;
    },
    clear: () => map.clear(),
    key: (i: number) => [...map.keys()][i] ?? null,
    getItem: (key: string) => {
      if (broken.read) throw new Error('SecurityError');
      return map.get(key) ?? null;
    },
    setItem: (key: string, value: string) => {
      if (broken.write) throw new Error('QuotaExceededError');
      map.set(key, value);
    },
    removeItem: (key: string) => {
      if (broken.write) throw new Error('QuotaExceededError');
      map.delete(key);
    },
  };
}

afterEach(() => {
  cleanup();
  clearRecents();
  localStorage.clear();
});

describe('parseRecents', () => {
  it('is empty for no value, broken JSON, another shape or another version', () => {
    expect(parseRecents(null)).toBe(EMPTY_RECENTS);
    expect(parseRecents('')).toBe(EMPTY_RECENTS);
    expect(parseRecents('{not json')).toBe(EMPTY_RECENTS);
    expect(parseRecents('[1,2]')).toBe(EMPTY_RECENTS);
    expect(parseRecents(JSON.stringify({ v: 2, entities: [{ id: id(1), at: 1 }], searches: [] }))).toBe(
      EMPTY_RECENTS,
    );
  });

  it('keeps well-formed rows in order and drops the rest', () => {
    const parsed = parseRecents(
      JSON.stringify({
        v: 1,
        entities: [
          { id: id(2), at: 20 },
          { id: 'Q1747689', at: 19 }, // not an entity id: it would fail the whole request
          { id: id(1), at: 'yesterday' },
          { id: id(2), at: 5 }, // a duplicate
          null,
          { at: 3 },
        ],
        searches: [{ q: '  temple   of ', at: 9 }, { q: 'Temple of', at: 8 }, { q: '', at: 7 }, { q: 42 }, 'rome'],
      }),
    );
    expect(parsed).toEqual({
      v: 1,
      entities: [
        { id: id(2), at: 20 },
        { id: id(1), at: 0 },
      ],
      searches: [{ q: 'temple of', at: 9 }],
    });
  });

  it('caps a list that was stored too long', () => {
    const entities = Array.from({ length: 30 }, (_, i) => ({ id: id(i), at: 100 - i }));
    const searches = Array.from({ length: 30 }, (_, i) => ({ q: `word ${i}`, at: 100 - i }));
    const parsed = parseRecents(JSON.stringify({ v: 1, entities, searches }));
    expect(parsed.entities).toHaveLength(MAX_RECENT_ENTITIES);
    expect(parsed.searches).toHaveLength(MAX_RECENT_SEARCHES);
    expect(parsed.entities[0].id).toBe(id(0));
  });
});

describe('withEntity', () => {
  it('puts the newest first, once each, at most 12', () => {
    let recents = EMPTY_RECENTS;
    for (let n = 1; n <= 14; n += 1) recents = withEntity(recents, id(n), n);
    expect(recents.entities).toHaveLength(12);
    expect(recents.entities[0]).toEqual({ id: id(14), at: 14 });
    expect(recentEntityIds(recents)).not.toContain(id(1));
    expect(recentEntityIds(recents)).not.toContain(id(2));

    const again = withEntity(recents, id(5), 99);
    expect(again.entities).toHaveLength(12);
    expect(again.entities[0]).toEqual({ id: id(5), at: 99 });
    expect(recentEntityIds(again).filter((x) => x === id(5))).toHaveLength(1);
  });

  it('changes nothing for the entity already first, or for something that is not an entity id', () => {
    const recents = withEntity(EMPTY_RECENTS, id(1), 1);
    expect(withEntity(recents, id(1), 50)).toBe(recents);
    expect(withEntity(recents, 'e:marathon', 50)).toBe(recents);
    expect(withEntity(recents, '', 50)).toBe(recents);
  });

  it('leaves the searches alone', () => {
    const recents = withSearch(EMPTY_RECENTS, 'rome', 1);
    expect(withEntity(recents, id(1), 2).searches).toBe(recents.searches);
  });
});

describe('withSearch', () => {
  it('puts the newest first, at most 8, one per word whatever its case or spacing', () => {
    let recents = EMPTY_RECENTS;
    for (let n = 1; n <= 10; n += 1) recents = withSearch(recents, `word ${n}`, n);
    expect(recents.searches).toHaveLength(8);
    expect(recents.searches[0]).toEqual({ q: 'word 10', at: 10 });

    const again = withSearch(recents, '  WORD   5 ', 99);
    expect(again.searches).toHaveLength(8);
    expect(again.searches[0]).toEqual({ q: 'WORD 5', at: 99 });
    expect(again.searches.filter((s) => s.q.toLowerCase() === 'word 5')).toHaveLength(1);
  });

  it('ignores a blank word, a pasted text and the word already first', () => {
    const recents = withSearch(EMPTY_RECENTS, 'rome', 1);
    expect(withSearch(recents, '   ', 2)).toBe(recents);
    expect(withSearch(recents, 'x'.repeat(81), 2)).toBe(recents);
    expect(withSearch(recents, ' rome ', 2)).toBe(recents);
  });
});

describe('createRecentsStore', () => {
  it('saves under hm-recents as { v, entities, searches } and reads it back', () => {
    const storage = memoryStorage();
    const store = createRecentsStore(
      () => storage,
      () => 1000,
    );
    store.recordEntity(id(1));
    store.recordSearch('rome');
    store.recordEntity(id(2));
    expect(JSON.parse(storage.map.get(RECENTS_KEY) ?? 'null')).toEqual({
      v: 1,
      entities: [
        { id: id(2), at: 1000 },
        { id: id(1), at: 1000 },
      ],
      searches: [{ q: 'rome', at: 1000 }],
    });

    const reopened = createRecentsStore(() => storage);
    expect(recentEntityIds(reopened.get())).toEqual([id(2), id(1)]);
    expect(reopened.get().searches.map((s) => s.q)).toEqual(['rome']);
  });

  it('gives the same object until something changes, and tells its listeners when it does', () => {
    const storage = memoryStorage();
    const store = createRecentsStore(() => storage);
    const listener = vi.fn();
    const unsubscribe = store.subscribe(listener);
    const before = store.get();
    expect(store.get()).toBe(before);

    store.recordEntity(id(1));
    expect(listener).toHaveBeenCalledTimes(1);
    expect(store.get()).not.toBe(before);

    store.recordEntity(id(1)); // already the most recent
    store.recordEntity('not-an-id');
    expect(listener).toHaveBeenCalledTimes(1);

    unsubscribe();
    store.recordEntity(id(2));
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it('clear forgets everything and removes the key', () => {
    const storage = memoryStorage();
    const store = createRecentsStore(() => storage);
    store.recordEntity(id(1));
    store.recordSearch('rome');
    store.clear();
    expect(store.get()).toBe(EMPTY_RECENTS);
    expect(storage.map.has(RECENTS_KEY)).toBe(false);
  });

  it('works in memory when there is no storage at all', () => {
    const store = createRecentsStore(() => null);
    store.recordEntity(id(1));
    store.recordEntity(id(2));
    store.recordSearch('rome');
    expect(recentEntityIds(store.get())).toEqual([id(2), id(1)]);
    store.clear();
    expect(store.get()).toBe(EMPTY_RECENTS);
  });

  it('works in memory when reaching for storage, reading it or writing it throws', () => {
    const unreachable = createRecentsStore(() => {
      throw new Error('SecurityError');
    });
    unreachable.recordEntity(id(1));
    unreachable.recordEntity(id(2));
    expect(recentEntityIds(unreachable.get())).toEqual([id(2), id(1)]);

    const blocked = memoryStorage({ read: true, write: true });
    const unreadable = createRecentsStore(() => blocked);
    unreadable.recordEntity(id(1));
    unreadable.recordEntity(id(2));
    expect(recentEntityIds(unreadable.get())).toEqual([id(2), id(1)]);

    // Readable but full: the empty stored value must not wipe what memory holds.
    const full = memoryStorage({ write: true });
    const unwritable = createRecentsStore(() => full);
    unwritable.recordEntity(id(1));
    unwritable.recordEntity(id(2));
    unwritable.recordSearch('rome');
    expect(recentEntityIds(unwritable.get())).toEqual([id(2), id(1)]);
    expect(unwritable.get().searches).toHaveLength(1);
    expect(full.map.size).toBe(0);
  });

  it('two tabs over one storage build one list', () => {
    const storage = memoryStorage();
    const first = createRecentsStore(() => storage);
    const second = createRecentsStore(() => storage);
    first.recordEntity(id(1));
    second.recordEntity(id(2));
    // The first tab has not heard of the second's write, and still starts from it.
    first.recordEntity(id(3));
    expect(recentEntityIds(first.get())).toEqual([id(3), id(2), id(1)]);
    expect(recentEntityIds(createRecentsStore(() => storage).get())).toEqual([id(3), id(2), id(1)]);
  });

  it('follows another tab through the storage event', () => {
    const storage = memoryStorage();
    const store = createRecentsStore(() => storage);
    const listener = vi.fn();
    const unsubscribe = store.subscribe(listener);
    expect(store.get()).toBe(EMPTY_RECENTS);

    createRecentsStore(() => storage).recordEntity(id(7));
    window.dispatchEvent(new StorageEvent('storage', { key: 'hm-theme' }));
    expect(listener).not.toHaveBeenCalled();

    window.dispatchEvent(new StorageEvent('storage', { key: RECENTS_KEY }));
    expect(listener).toHaveBeenCalledTimes(1);
    expect(recentEntityIds(store.get())).toEqual([id(7)]);

    // The same value again is not a change.
    window.dispatchEvent(new StorageEvent('storage', { key: RECENTS_KEY }));
    expect(listener).toHaveBeenCalledTimes(1);

    // Everything cleared (key is null).
    storage.clear();
    window.dispatchEvent(new StorageEvent('storage', { key: null }));
    expect(listener).toHaveBeenCalledTimes(2);
    expect(store.get()).toBe(EMPTY_RECENTS);

    unsubscribe();
    createRecentsStore(() => storage).recordEntity(id(8));
    window.dispatchEvent(new StorageEvent('storage', { key: RECENTS_KEY }));
    expect(listener).toHaveBeenCalledTimes(2);
  });

  it('catches up on subscribing, for a card that mounts after another tab wrote', () => {
    const storage = memoryStorage();
    const store = createRecentsStore(() => storage);
    expect(store.get()).toBe(EMPTY_RECENTS);
    createRecentsStore(() => storage).recordEntity(id(4));
    const unsubscribe = store.subscribe(() => {});
    expect(recentEntityIds(store.get())).toEqual([id(4)]);
    unsubscribe();
  });
});

describe('useRecents', () => {
  it('starts empty and follows what is recorded and cleared', () => {
    const { result } = renderHook(() => useRecents());
    expect(result.current).toBe(EMPTY_RECENTS);

    act(() => recordRecentEntity(id(1)));
    act(() => recordRecentSearch('rome'));
    expect(recentEntityIds(result.current)).toEqual([id(1)]);
    expect(result.current.searches.map((s) => s.q)).toEqual(['rome']);
    expect(JSON.parse(localStorage.getItem(RECENTS_KEY) ?? 'null')).toMatchObject({ v: 1 });

    act(() => clearRecents());
    expect(result.current).toBe(EMPTY_RECENTS);
    expect(localStorage.getItem(RECENTS_KEY)).toBeNull();
  });

  it('gives every reader the same list', () => {
    const one = renderHook(() => useRecents());
    const two = renderHook(() => useRecents());
    act(() => recordRecentEntity(id(3)));
    expect(one.result.current).toBe(two.result.current);
    expect(one.result.current).toBe(getRecents());
  });

  it('follows another tab', () => {
    const { result } = renderHook(() => useRecents());
    act(() => {
      localStorage.setItem(RECENTS_KEY, JSON.stringify({ v: 1, entities: [{ id: id(9), at: 5 }], searches: [] }));
      window.dispatchEvent(new StorageEvent('storage', { key: RECENTS_KEY }));
    });
    expect(recentEntityIds(result.current)).toEqual([id(9)]);
  });
});
