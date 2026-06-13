/** GET /chronicles/{slug} — the whole tour (ChronicleResource + entries). */
import { ChronicleSchema, type Chronicle } from '@/lib/schemas/chronicle';
import { api } from './client';

export async function chronicle(
  slug: string,
  signal?: AbortSignal,
): Promise<Chronicle> {
  const { data } = await api.get(
    `/api/v1/chronicles/${encodeURIComponent(slug)}`,
    { signal },
  );
  return ChronicleSchema.parse(data);
}
