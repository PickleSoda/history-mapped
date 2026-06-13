import { useQuery } from '@tanstack/react-query';
import { entityChronicles } from '@/lib/api';

/** Chronicles the selected entity belongs to (GET /entities/{id}/chronicles). */
export function useEntityChronicles(id: string | null) {
  return useQuery({
    queryKey: ['entity', id ?? '∅', 'chronicles'] as const,
    queryFn: ({ signal }) => entityChronicles(id as string, signal),
    enabled: id !== null,
    staleTime: Infinity,
  });
}
