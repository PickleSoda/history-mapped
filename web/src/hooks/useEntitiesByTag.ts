import { useInfiniteQuery } from '@tanstack/react-query';
import { entitiesByTags } from '@/lib/api';
import type { EntitiesByTagsParams } from '@/lib/api';
import { qk } from '@/lib/query/queryKeys';

/**
 * Every entity carrying a tag (GET /entities?tags=), highest impact first,
 * paged ("Load more"). Unlike `useEntityList` it ignores the map: no bbox, no
 * year, no group filter. Disabled while `tag` is null.
 */
export function useEntitiesByTag(
  tag: string | null,
  { sort = 'impact', perPage = 24 }: Omit<EntitiesByTagsParams, 'tags' | 'page'> = {},
) {
  const params = { tags: tag ? [tag] : [], sort, perPage };
  return useInfiniteQuery({
    queryKey: qk.entitiesByTags(params),
    queryFn: ({ pageParam, signal }) => entitiesByTags({ ...params, page: pageParam }, signal),
    enabled: tag !== null,
    initialPageParam: 1,
    getNextPageParam: (last) =>
      last.meta.current_page < last.meta.last_page ? last.meta.current_page + 1 : undefined,
    staleTime: 5 * 60_000,
  });
}
