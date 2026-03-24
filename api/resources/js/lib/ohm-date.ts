/**
 * OHM date utilities.
 *
 * Provides conversion from internal integer year values (positive = CE, negative = BCE)
 * to OHM-compatible date strings accepted by `map.filterByDate()`.
 *
 * OHM date string format: `YYYY`, `YYYY-MM`, or `YYYY-MM-DD` (ISO 8601-extended).
 * Negative years are supported: -1 = 1 BCE, -753 = 753 BCE, etc.
 * There is no Year Zero in the proleptic Gregorian calendar.
 */

/**
 * Converts an integer year to an OHM-compatible date string.
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
