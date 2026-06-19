import { useQuery } from '@tanstack/react-query';
import { historicalPeriods } from '@/lib/api';
import { qk } from '@/lib/query/queryKeys';

/**
 * Historical periods for the timeline gantt. Reference data is immutable, so
 * `staleTime: Infinity` — fetched once and cached for the session.
 */
export function useHistoricalPeriods() {
  return useQuery({
    queryKey: qk.historicalPeriods(),
    queryFn: ({ signal }) => historicalPeriods(signal),
    staleTime: Infinity,
  });
}
