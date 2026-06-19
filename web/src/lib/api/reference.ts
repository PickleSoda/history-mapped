/** Typed public reference endpoints against the real Laravel API. */
import { HistoricalPeriodListSchema } from '@/lib/schemas/reference';
import type { HistoricalPeriod } from '@/lib/schemas/reference';
import { api } from './client';

/**
 * GET /reference/historical-periods — public list of named historical periods
 * (eras) with their date ranges, hierarchy depth, and colours. Used by the
 * bottom timeline's gantt.
 */
export async function historicalPeriods(
  signal?: AbortSignal,
): Promise<HistoricalPeriod[]> {
  const { data } = await api.get('/api/v1/reference/historical-periods', {
    signal,
  });
  return HistoricalPeriodListSchema.parse(data).data;
}
