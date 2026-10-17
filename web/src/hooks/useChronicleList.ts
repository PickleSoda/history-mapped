import { useInfiniteQuery } from '@tanstack/react-query';
import { chronicleList } from '@/lib/api';
import type { ChronicleListParams } from '@/lib/api';
import { qk } from '@/lib/query/queryKeys';

/** Chronicles-tab listing (GET /chronicles), filtered and paged ("Load more"). */
export function useChronicleList(params: Omit<ChronicleListParams, 'page'> = {}) {
  return useInfiniteQuery({
    queryKey: qk.chronicleList(params),
    queryFn: ({ pageParam, signal }) => chronicleList({ ...params, page: pageParam }, signal),
    initialPageParam: 1,
    getNextPageParam: (last) =>
      last.meta.current_page < last.meta.last_page ? last.meta.current_page + 1 : undefined,
    staleTime: 5 * 60_000,
  });
}
