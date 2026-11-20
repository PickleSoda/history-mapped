/**
 * The daily expedition's state.
 *
 * `useQuestStore` is what the reader has done today (the target they are
 * after, the hints they took, what they found) and their streak. It is saved
 * to `localStorage` on every change and read back on load. Storage that is
 * missing or throws (a private window) only costs the memory of it: the
 * expedition still plays for the session. A new day clears the targets and
 * keeps the streak.
 *
 * `useQuestLive` is the live reading of the active target (how warm, which
 * way, arrived or not): published by the map layer, read by the strip over
 * the map and by the card. It is never saved.
 */
import { useEffect } from 'react';
import { create } from 'zustand';
import { dayKey } from './date';
import { completeStreak, NO_PROGRESS, NO_STREAK, sameReading, tally } from './quest';
import type { QuestReading, Streak, TargetProgress, TargetsProgress } from './quest';

export const QUEST_STORAGE_KEY = 'hm-quest';

/** What is saved. */
export interface QuestState {
  v: 1;
  /** The reader's local day the rest is for (YYYY-MM-DD). */
  date: string;
  /** The target being looked for. */
  active: string | null;
  /** By target id; a target not started has no entry. */
  targets: TargetsProgress;
  streak: Streak;
}

export type QuestHint = 'when' | 'where';

interface QuestActions {
  /** Go after a target (leaving the one before it as it stands). */
  start: (id: string) => void;
  stop: () => void;
  /** Take a hint: it costs a star. */
  hint: (id: string, kind: QuestHint) => void;
  /** Be taken there: no stars, but the find still counts. */
  take: (id: string) => void;
  /** The target was found; `all` are the day's target ids, to tell when the day is complete. */
  find: (id: string, all: readonly string[]) => void;
  /** Start over if the day has changed. */
  sync: () => void;
}

const DAY = /^\d{4}-\d{2}-\d{2}$/;
/** A day has three targets; a saved state with many more is not ours. */
const MAX_TARGETS = 12;

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

function freshState(date: string, streak: Streak = NO_STREAK): QuestState {
  return { v: 1, date, active: null, targets: {}, streak };
}

function parseStreak(value: unknown): Streak {
  if (!isRecord(value)) return NO_STREAK;
  const { count, last } = value;
  return typeof count === 'number' && Number.isInteger(count) && count > 0 && typeof last === 'string' && DAY.test(last)
    ? { count, last }
    : NO_STREAK;
}

/**
 * A saved state made safe to use on `today`: anything malformed is dropped
 * (the streak is kept when it can be), and a state from another day keeps
 * only its streak.
 */
export function parseQuestState(raw: string | null, today: string): QuestState {
  let saved: unknown = null;
  try {
    saved = raw ? JSON.parse(raw) : null;
  } catch {
    saved = null;
  }
  if (!isRecord(saved) || saved.v !== 1) return freshState(today);
  const streak = parseStreak(saved.streak);
  if (saved.date !== today || !isRecord(saved.targets)) return freshState(today, streak);
  const targets: TargetsProgress = {};
  for (const [id, value] of Object.entries(saved.targets).slice(0, MAX_TARGETS)) {
    if (!isRecord(value)) continue;
    targets[id] = {
      when: value.when === true,
      where: value.where === true,
      taken: value.taken === true,
      found: value.found === true,
    };
  }
  const active = typeof saved.active === 'string' && !targets[saved.active]?.found ? saved.active : null;
  return { v: 1, date: today, active, targets, streak };
}

function readSaved(): string | null {
  try {
    return window.localStorage.getItem(QUEST_STORAGE_KEY);
  } catch {
    return null;
  }
}

function writeSaved(json: string): void {
  try {
    window.localStorage.setItem(QUEST_STORAGE_KEY, json);
  } catch {
    /* a private window or a full quota: play on without it */
  }
}

/** The saved part of the store, in the saved shape. */
const snapshot = (state: QuestState): QuestState => ({
  v: 1,
  date: state.date,
  active: state.active,
  targets: state.targets,
  streak: state.streak,
});

export const useQuestStore = create<QuestState & QuestActions>()((set, get) => {
  /** The state to act on: a state left over from another day is rolled over first. */
  const current = (): QuestState => {
    const state = snapshot(get());
    const today = dayKey();
    return state.date === today ? state : freshState(today, state.streak);
  };
  const withTarget = (state: QuestState, id: string, patch: Partial<TargetProgress>): TargetsProgress => ({
    ...state.targets,
    [id]: { ...(state.targets[id] ?? NO_PROGRESS), ...patch },
  });

  return {
    ...parseQuestState(readSaved(), dayKey()),

    start: (id) => {
      const state = current();
      if (state.targets[id]?.found) return;
      set({ ...state, active: id });
    },
    stop: () => {
      const state = current();
      if (state.active !== null || state.date !== get().date) set({ ...state, active: null });
    },
    hint: (id, kind) => {
      const state = current();
      if (state.targets[id]?.found) return;
      set({ ...state, targets: withTarget(state, id, { [kind]: true }) });
    },
    take: (id) => {
      const state = current();
      if (state.targets[id]?.found) return;
      set({ ...state, active: id, targets: withTarget(state, id, { taken: true }) });
    },
    find: (id, all) => {
      const state = current();
      if (state.targets[id]?.found) return;
      const targets = withTarget(state, id, { found: true });
      set({
        ...state,
        active: null,
        targets,
        streak: tally(all, targets).complete ? completeStreak(state.streak, state.date) : state.streak,
      });
    },
    sync: () => {
      const state = current();
      if (state.date !== get().date) set(state);
    },
  };
});

// ── saving ────────────────────────────────────────────────────────────────────

/** The state as last written or read, so an unchanged state is not written again. */
let saved = JSON.stringify(snapshot(useQuestStore.getState()));

useQuestStore.subscribe((state) => {
  const json = JSON.stringify(snapshot(state));
  if (json === saved) return;
  saved = json;
  writeSaved(json);
});

// Another tab played: take its state, so two tabs do not undo each other.
if (typeof window !== 'undefined') {
  window.addEventListener('storage', (event) => {
    if (event.key !== null && event.key !== QUEST_STORAGE_KEY) return;
    try {
      if (event.storageArea && event.storageArea !== window.localStorage) return;
    } catch {
      return;
    }
    const next = parseQuestState(event.key === null ? null : event.newValue, dayKey());
    // It is what storage already holds: nothing to write back.
    saved = JSON.stringify(next);
    useQuestStore.setState(next);
  });
}

// ── the day ───────────────────────────────────────────────────────────────────

function msToTomorrow(): number {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1).getTime() - now.getTime();
}

/**
 * The reader's day (YYYY-MM-DD) for the expedition, kept current while the
 * page stays open: checked at each local midnight and whenever the tab comes
 * back into view, which is also when yesterday's targets are cleared.
 */
export function useQuestDay(): string {
  const date = useQuestStore((s) => s.date);
  useEffect(() => {
    const check = () => useQuestStore.getState().sync();
    let timer: ReturnType<typeof setTimeout>;
    const arm = () => {
      timer = setTimeout(() => {
        check();
        arm();
      }, msToTomorrow() + 1000);
    };
    check();
    arm();
    document.addEventListener('visibilitychange', check);
    window.addEventListener('focus', check);
    return () => {
      clearTimeout(timer);
      document.removeEventListener('visibilitychange', check);
      window.removeEventListener('focus', check);
    };
  }, []);
  return date;
}

// ── the live reading ──────────────────────────────────────────────────────────

interface QuestLive {
  /** How the reader stands to the active target; null when none is being read. */
  reading: QuestReading | null;
  /** Store a reading, if it differs from the one held. */
  publish: (reading: QuestReading) => void;
  clear: () => void;
}

export const useQuestLive = create<QuestLive>()((set, get) => ({
  reading: null,
  publish: (reading) => {
    const held = get().reading;
    if (!held || !sameReading(held, reading)) set({ reading });
  },
  clear: () => {
    if (get().reading) set({ reading: null });
  },
}));
