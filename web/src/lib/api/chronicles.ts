/** Typed chronicle endpoint — the whole tour in one request. */
import { ChronicleSchema, type Chronicle } from '@/lib/schemas/chronicle';
import { api } from './client';

export async function chronicle(
  id: string,
  signal?: AbortSignal,
): Promise<Chronicle> {
  const { data } = await api.get(
    `/api/v1/atlas/chronicles/${encodeURIComponent(id)}`,
    { signal },
  );
  return ChronicleSchema.parse(data);
}
