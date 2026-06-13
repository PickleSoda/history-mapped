import { useQuery } from '@tanstack/react-query';
import { chronicle } from '@/lib/api';
import { qk } from '@/lib/query/queryKeys';

/** The whole tour in one fetch. `staleTime: Infinity` — chronicle data is
 *  immutable, so revisiting steps is instant. */
export function useChronicle(id: string | null) {
  return useQuery({
    queryKey: qk.chronicle(id ?? '∅'),
    queryFn: ({ signal }) => chronicle(id as string, signal),
    enabled: id !== null,
    staleTime: Infinity,
  });
}
