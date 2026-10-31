import { useQuery } from '@tanstack/react-query';
import { mapStory } from '@/lib/api/map-stories';
import { qk } from '@/lib/query/queryKeys';

/** A battle map's whole document. Stories are static content: cache forever. */
export function useMapStory(slug: string | null) {
  return useQuery({
    queryKey: qk.mapStory(slug ?? '∅'),
    queryFn: ({ signal }) => mapStory(slug as string, signal),
    enabled: slug !== null,
    staleTime: Infinity,
  });
}
