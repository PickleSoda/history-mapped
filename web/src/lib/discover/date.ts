/**
 * The reader's own day, for the daily parts of Discover. "Today" is the local
 * calendar day (not UTC): the expedition changes at the reader's midnight.
 */

const pad = (n: number) => String(n).padStart(2, '0');

/** A date's local calendar day as YYYY-MM-DD. */
export function dayKey(date: Date = new Date()): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** The day before a YYYY-MM-DD key (for streaks). */
export function previousDayKey(key: string): string {
  const [y, m, d] = key.split('-').map(Number);
  return dayKey(new Date(y, m - 1, d - 1));
}

const MONTHS = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
];

/** "20 November" for a month (1–12) and a day. */
export function dayMonthLabel(month: number, day: number): string {
  return `${day} ${MONTHS[month - 1] ?? ''}`.trim();
}
