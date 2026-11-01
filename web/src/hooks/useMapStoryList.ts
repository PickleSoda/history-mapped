import { useInfiniteQuery } from '@tanstack/react-query';
import { mapStoryList } from '@/lib/api';
import type { MapStoryListParams } from '@/lib/api';
import { qk } from '@/lib/query/queryKeys';
import { retryUnlessClientError } from './useCollections';

/** The battle-map (map story) index (GET /map-stories), filtered by kind and
 *  sorted by year or title, paged ("Load more"). */
export function useMapStoryList(params: Omit<MapStoryListParams, 'page'> = {}) {
  return useInfiniteQuery({
    queryKey: qk.mapStoryList(params),
    queryFn: ({ pageParam, signal }) => mapStoryList({ ...params, page: pageParam }, signal),
    initialPageParam: 1,
    getNextPageParam: (last) =>
      last.meta.current_page < last.meta.last_page ? last.meta.current_page + 1 : undefined,
    staleTime: 5 * 60_000,
    retry: retryUnlessClientError,
  });
}
