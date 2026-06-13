import type { TimeState } from '@/types/atlas';

/** Format a year for display: negative = BCE, positive = CE. */
export function formatYear(year: number): string {
  if (year < 0) return `${-year} BCE`;
  return `${year} CE`;
}

/** Format the timeline state — a single instant or a range. */
export function formatTime(time: TimeState): string {
  return time.kind === 'instant'
    ? formatYear(time.year)
    : `${formatYear(time.start)} – ${formatYear(time.end)}`;
}

/** Coarse era label for a year. */
export function eraFor(year: number): string {
  if (year < -3000) return 'Prehistory';
  if (year < -800) return 'Ancient';
  if (year < 500) return 'Classical Antiquity';
  if (year < 1500) return 'Medieval';
  if (year < 1800) return 'Early Modern';
  return 'Modern';
}

/** Representative year for the current time state (range → midpoint). */
export function instantYear(time: TimeState): number {
  return time.kind === 'instant'
    ? time.year
    : Math.round((time.start + time.end) / 2);
}
