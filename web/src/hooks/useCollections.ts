import { useQuery } from '@tanstack/react-query';
import { collectionList } from '@/lib/api';
import { errorStatus } from '@/lib/api/errors';
import { qk } from '@/lib/query/queryKeys';

/**
 * Retry once on a network or server error, never on a 4xx: a missing set (or
 * an API that does not serve the endpoint yet) should show its empty state
 * straight away, not after a backoff.
 */
export function retryUnlessClientError(failureCount: number, error: unknown): boolean {
  const status = errorStatus(error);
  return failureCount < 1 && (status === null || status >= 500);
}

/** Every published curated set (GET /collections), for the browse index and
 *  the landing page. */
export function useCollections() {
  return useQuery({
    queryKey: qk.collections(),
    queryFn: ({ signal }) => collectionList(signal),
    staleTime: 5 * 60_000,
    retry: retryUnlessClientError,
  });
}
