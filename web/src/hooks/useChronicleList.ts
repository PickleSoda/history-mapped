import { useQuery } from '@tanstack/react-query';
import { chronicleList } from '@/lib/api';

/** Chronicle listing for the Chronicles tab (GET /chronicles). */
export function useChronicleList() {
  return useQuery({
    queryKey: ['chronicles', 'list'] as const,
    queryFn: ({ signal }) => chronicleList(signal),
    staleTime: 5 * 60_000,
  });
}
