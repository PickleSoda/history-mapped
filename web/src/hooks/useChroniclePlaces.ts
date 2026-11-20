import { useQuery } from '@tanstack/react-query';
import { chroniclePlaces } from '@/lib/api';
import { qk } from '@/lib/query/queryKeys';

/** Where the chronicle's entities sit on the map, for the player's step layer.
 *  One small fetch per chronicle; static content, so cached for the session. */
export function useChroniclePlaces(slug: string | null) {
  return useQuery({
    queryKey: qk.chroniclePlaces(slug ?? '∅'),
    queryFn: ({ signal }) => chroniclePlaces(slug as string, signal),
    enabled: slug !== null,
    staleTime: Infinity,
  });
}
