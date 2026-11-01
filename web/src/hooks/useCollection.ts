import { useQuery } from '@tanstack/react-query';
import { collection } from '@/lib/api';
import { qk } from '@/lib/query/queryKeys';
import { retryUnlessClientError } from './useCollections';

/** One curated set with its items resolved, in the author's order. An unknown
 *  slug is a 404 error (`errorStatus(error) === 404`). */
export function useCollection(slug: string | null) {
  return useQuery({
    queryKey: qk.collection(slug ?? '∅'),
    queryFn: ({ signal }) => collection(slug as string, signal),
    enabled: slug !== null,
    staleTime: 5 * 60_000,
    retry: retryUnlessClientError,
  });
}
