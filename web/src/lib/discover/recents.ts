/**
 * What this browser opened and searched lately, for the "For you" suggestions.
 *
 * Kept in `localStorage` under `hm-recents` and nowhere else: the only thing
 * that leaves the browser is the list of entity ids sent to
 * GET /discover/for-you. Shape: `{ v: 1, entities: [{ id, at }], searches:
 * [{ q, at }] }`, newest first, at most 12 entities and 8 searches, no
 * duplicates; `at` is epoch milliseconds.
 *
 * Storage can be missing or throw (private windows, blocked site data). The
 * store then keeps its list in memory for the life of the page, so the cards
 * still agree with each other.
 */
import { useSyncExternalStore } from 'react';
import { isEntityId } from '@/lib/site-links';

export const RECENTS_KEY = 'hm-recents';
export const MAX_RECENT_ENTITIES = 12;
export const MAX_RECENT_SEARCHES = 8;
/** A longer "search" is a pasted text, not a word to offer again. */
const MAX_SEARCH_LENGTH = 80;

export interface RecentEntity {
  id: string;
  /** When it was opened, epoch milliseconds. */
  at: number;
}

export interface RecentSearch {
  q: string;
  at: number;
}

export interface Recents {
  v: 1;
  /** Opened entities, most recent first. */
  entities: RecentEntity[];
  /** Search words kept as a filter, most recent first. */
  searches: RecentSearch[];
}

export const EMPTY_RECENTS: Recents = { v: 1, entities: [], searches: [] };

// ── pure ──────────────────────────────────────────────────────────────────────

/** One spelling per search: trimmed, inner whitespace collapsed. */
function tidySearch(q: string): string {
  return q.trim().replace(/\s+/g, ' ');
}

const searchKey = (q: string) => q.toLowerCase();

const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null;

const time = (v: unknown): number => (typeof v === 'number' && Number.isFinite(v) ? v : 0);

/**
 * The stored text as a clean list. Anything unreadable (no value, broken JSON,
 * another version, a hand-edited row) is dropped rather than trusted: ids that
 * are not entity ids would make the suggestions request fail as a whole.
 */
export function parseRecents(raw: string | null | undefined): Recents {
  if (!raw) return EMPTY_RECENTS;
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return EMPTY_RECENTS;
  }
  if (!isRecord(value) || value.v !== 1) return EMPTY_RECENTS;

  const entities: RecentEntity[] = [];
  for (const row of Array.isArray(value.entities) ? value.entities : []) {
    if (entities.length >= MAX_RECENT_ENTITIES) break;
    if (!isRecord(row) || typeof row.id !== 'string' || !isEntityId(row.id)) continue;
    const id = row.id;
    if (!entities.some((e) => e.id === id)) entities.push({ id, at: time(row.at) });
  }

  const searches: RecentSearch[] = [];
  for (const row of Array.isArray(value.searches) ? value.searches : []) {
    if (searches.length >= MAX_RECENT_SEARCHES) break;
    if (!isRecord(row) || typeof row.q !== 'string') continue;
    const q = tidySearch(row.q);
    if (!q || q.length > MAX_SEARCH_LENGTH) continue;
    if (!searches.some((s) => searchKey(s.q) === searchKey(q))) searches.push({ q, at: time(row.at) });
  }

  return entities.length === 0 && searches.length === 0 ? EMPTY_RECENTS : { v: 1, entities, searches };
}

/**
 * `recents` with the entity opened now at the front. The same object comes
 * back when nothing changes: not an entity id, or already the most recent.
 */
export function withEntity(recents: Recents, id: string, at: number): Recents {
  if (!isEntityId(id) || recents.entities[0]?.id === id) return recents;
  const entities = [{ id, at }, ...recents.entities.filter((e) => e.id !== id)].slice(0, MAX_RECENT_ENTITIES);
  return { ...recents, entities };
}

/**
 * `recents` with the search word at the front. Words differing only in case
 * or spacing are one search, kept in its latest spelling.
 */
export function withSearch(recents: Recents, word: string, at: number): Recents {
  const q = tidySearch(word);
  if (!q || q.length > MAX_SEARCH_LENGTH || recents.searches[0]?.q === q) return recents;
  const searches = [{ q, at }, ...recents.searches.filter((s) => searchKey(s.q) !== searchKey(q))].slice(
    0,
    MAX_RECENT_SEARCHES,
  );
  return { ...recents, searches };
}

const isEmpty = (r: Recents) => r.entities.length === 0 && r.searches.length === 0;

// ── the store ─────────────────────────────────────────────────────────────────

export interface RecentsStore {
  /** The current list. The same object until something changes. */
  get: () => Recents;
  subscribe: (listener: () => void) => () => void;
  recordEntity: (id: string) => void;
  recordSearch: (word: string) => void;
  clear: () => void;
}

/** The browser's storage, or null where even reaching for it throws. */
function browserStorage(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage;
  } catch {
    return null;
  }
}

/**
 * A recents store over `storage`. One instance serves the app (below); tests
 * make their own, with a storage that is missing, full or shared.
 */
export function createRecentsStore(
  storage: () => Storage | null = browserStorage,
  now: () => number = Date.now,
): RecentsStore {
  const listeners = new Set<() => void>();
  let state: Recents | undefined;
  /** The last write did not reach storage: memory is the truth until one does. */
  let detached = false;

  /** What storage holds, or undefined when it cannot be read. */
  const read = (): Recents | undefined => {
    try {
      const s = storage();
      return s ? parseRecents(s.getItem(RECENTS_KEY)) : undefined;
    } catch {
      return undefined;
    }
  };

  const current = (): Recents => (state ??= read() ?? EMPTY_RECENTS);

  /** Take in what another tab wrote since. True when the list changed. */
  const refresh = (): boolean => {
    const before = current();
    if (detached) return false;
    const stored = read();
    if (!stored || JSON.stringify(stored) === JSON.stringify(before)) return false;
    state = stored;
    return true;
  };

  const persist = (next: Recents) => {
    try {
      const s = storage();
      if (!s) return;
      if (isEmpty(next)) s.removeItem(RECENTS_KEY);
      else s.setItem(RECENTS_KEY, JSON.stringify(next));
      detached = false;
    } catch {
      detached = true;
    }
  };

  const notify = () => listeners.forEach((listener) => listener());

  const update = (change: (recents: Recents) => Recents) => {
    const before = current();
    refresh();
    const next = change(current());
    if (next !== state) {
      state = next;
      persist(next);
    }
    if (state !== before) notify();
  };

  const onStorage = (event: StorageEvent) => {
    // `key` is null when the whole storage was cleared.
    if (event.key !== null && event.key !== RECENTS_KEY) return;
    if (refresh()) notify();
  };

  return {
    get: current,
    subscribe(listener) {
      listeners.add(listener);
      if (listeners.size === 1 && typeof window !== 'undefined') {
        window.addEventListener('storage', onStorage);
        // Nobody was listening until now: catch up on what other tabs wrote.
        // (React re-reads the snapshot right after it subscribes.)
        refresh();
      }
      return () => {
        listeners.delete(listener);
        if (listeners.size === 0 && typeof window !== 'undefined') window.removeEventListener('storage', onStorage);
      };
    },
    recordEntity: (id) => update((r) => withEntity(r, id, now())),
    recordSearch: (word) => update((r) => withSearch(r, word, now())),
    clear: () => update((r) => (isEmpty(r) ? r : EMPTY_RECENTS)),
  };
}

// ── the app's store ───────────────────────────────────────────────────────────

const store = createRecentsStore();

/** Remember that an entity was opened (ignored unless it is an entity id). */
export const recordRecentEntity = store.recordEntity;

/** Remember a search word that was kept as a filter. */
export const recordRecentSearch = store.recordSearch;

/** Forget everything this browser opened and searched. */
export const clearRecents = store.clear;

/** The current list, outside React. */
export const getRecents = store.get;

/** The entity ids to ask suggestions for: most recent first, at most 12. */
export function recentEntityIds(recents: Recents): string[] {
  return recents.entities.map((e) => e.id);
}

/**
 * What this browser opened and searched lately. Every component reading it
 * sees the same list, and it follows other tabs through the `storage` event.
 */
export function useRecents(): Recents {
  return useSyncExternalStore(store.subscribe, store.get, () => EMPTY_RECENTS);
}
