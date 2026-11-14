/**
 * OHM date utilities.
 *
 * Date strings are `YYYY`, `YYYY-MM` or `YYYY-MM-DD` (ISO 8601-extended),
 * BCE years negative. Two numberings meet here:
 *
 * - Ours is historical: there is no year 0, and -1 is 1 BCE, -44 is 44 BCE.
 *   Entity years, the timeline and our own tiles use it.
 * - OpenHistoricalMap's is astronomical (ISO 8601): 0000 is 1 BCE and -0043
 *   is 44 BCE. Its `start_date`, `end_date` and decimal dates use it.
 *
 * So a BCE date moves one year toward zero on its way to OHM (`toOhmDate`).
 * The filters that read OHM layers do that themselves; callers pass ours.
 */

/**
 * Formats one of our years as a date string (no conversion: see toOhmDate).
 *
 * @param year - Positive integer for CE years, negative integer for BCE years.
 *               e.g. 753 → `'0753'`, -753 → `'-0753'`, 1453 → `'1453'`
 */
export function yearToOhmDate(year: number): string {
    if (year >= 0) {
        return String(year).padStart(4, '0');
    }

    // BCE: prepend '-' then pad the absolute value to 4 digits
    return '-' + String(Math.abs(year)).padStart(4, '0');
}

/** OHM's (astronomical) year for one of ours: 1 BCE (-1) is 0, 44 BCE (-44) is -43. */
export function toOhmYear(year: number): number {
    return year < 0 ? year + 1 : year;
}

/**
 * One of our date strings as OHM writes it: `-0044-03-15` (44 BCE) becomes
 * `-0043-03-15`. CE dates, and anything that isn't a BCE date, are unchanged.
 */
export function toOhmDate(date: string): string {
    const match = /^\s*-(\d+)((?:-\d\d){0,2})\s*$/.exec(date);

    return match
        ? yearToOhmDate(toOhmYear(-Number(match[1]))) + match[2]
        : date;
}

const OHM_DATE_PATTERN =
    /^-?\d{4,}(?:-(0[1-9]|1[0-2])(?:-(0[1-9]|[12]\d|3[01]))?)?$/;

/**
 * Returns a normalized OHM date string or `null` when the value is empty/invalid.
 */
export function normalizeOhmDate(
    value: string | null | undefined,
): string | null {
    if (typeof value !== 'string') {
        return null;
    }

    const trimmed = value.trim();

    if (!trimmed) {
        return null;
    }

    return OHM_DATE_PATTERN.test(trimmed) ? trimmed : null;
}

export const DECDATE_START_OFFSET = 0.00137;
export const DECDATE_END_OFFSET = 0.99863;

/** OHM decimal-date convention for a year-only date (spec D2); mirrors tiles.year_to_decdate. */
export function yearToDecdate(year: number, bound: 'start' | 'end'): number {
    return (
        year + (bound === 'start' ? DECDATE_START_OFFSET : DECDATE_END_OFFSET)
    );
}
