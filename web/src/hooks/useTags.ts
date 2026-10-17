import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';
import { tagList } from '@/lib/api';
import { qk } from '@/lib/query/queryKeys';
import { indexTags } from '@/lib/tags';

/** The tag vocabulary plus a slug → tag index. Changes rarely, so cache long. */
export function useTags() {
  const query = useQuery({
    queryKey: qk.tags(),
    queryFn: ({ signal }) => tagList(signal),
    staleTime: 30 * 60_000,
  });
  const index = useMemo(() => indexTags(query.data?.data ?? []), [query.data]);
  const tags = useMemo(() => [...index.values()], [index]);
  return { ...query, tags, index };
}
