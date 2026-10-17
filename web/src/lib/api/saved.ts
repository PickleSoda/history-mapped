/** Personal saved items: stars (entities, chronicles, relationships) + folders. */
import { FolderSchema, FoldersSchema, StarKeysSchema, StarListSchema, StarSchema } from '@/lib/schemas/saved';
import type { Folder, SaveableType, Star, StarKey, StarList } from '@/lib/schemas/saved';
import { api, getCsrfCookie } from './client';

const unwrap = (data: unknown) => (data as { data?: unknown }).data ?? data;
const item = (type: SaveableType, id: string) =>
  `${encodeURIComponent(type)}/${encodeURIComponent(id)}`;

/** GET /me/stars/keys — every star the user has, for toggle state. */
export async function starKeys(signal?: AbortSignal): Promise<StarKey[]> {
  const { data } = await api.get('/api/v1/me/stars/keys', { signal });
  return StarKeysSchema.parse(data).data;
}

export interface StarListParams {
  type?: SaveableType | null;
  folder?: number | null;
  page?: number;
  per_page?: number;
}

/** GET /me/stars — paginated starred items, newest first. */
export async function stars(params: StarListParams, signal?: AbortSignal): Promise<StarList> {
  const { data } = await api.get('/api/v1/me/stars', {
    signal,
    params: {
      type: params.type ?? undefined,
      folder: params.folder ?? undefined,
      page: params.page ?? 1,
      per_page: params.per_page ?? 20,
    },
  });
  return StarListSchema.parse(data);
}

/** POST /me/stars — idempotent; optionally files it into folders too. */
export async function star(type: SaveableType, id: string, folderIds?: number[]): Promise<Star> {
  await getCsrfCookie();
  const { data } = await api.post('/api/v1/me/stars', {
    type,
    id,
    ...(folderIds && { folder_ids: folderIds }),
  });
  return StarSchema.parse(unwrap(data));
}

/** DELETE /me/stars/{type}/{id} — also removes it from every folder. */
export async function unstar(type: SaveableType, id: string): Promise<void> {
  await getCsrfCookie();
  await api.delete(`/api/v1/me/stars/${item(type, id)}`);
}

export async function folders(signal?: AbortSignal): Promise<Folder[]> {
  const { data } = await api.get('/api/v1/me/folders', { signal });
  return FoldersSchema.parse(data).data;
}

export interface FolderInput {
  name: string;
  description?: string | null;
  color?: string | null;
}

export async function createFolder(input: FolderInput): Promise<Folder> {
  await getCsrfCookie();
  const { data } = await api.post('/api/v1/me/folders', input);
  return FolderSchema.parse(unwrap(data));
}

export async function updateFolder(id: number, input: Partial<FolderInput>): Promise<Folder> {
  await getCsrfCookie();
  const { data } = await api.patch(`/api/v1/me/folders/${id}`, input);
  return FolderSchema.parse(unwrap(data));
}

/** DELETE /me/folders/{id} — the stars inside are kept. */
export async function deleteFolder(id: number): Promise<void> {
  await getCsrfCookie();
  await api.delete(`/api/v1/me/folders/${id}`);
}

/** PUT /me/folders/{folder}/items/{type}/{id} — stars the item if needed. */
export async function addToFolder(folderId: number, type: SaveableType, id: string): Promise<Star> {
  await getCsrfCookie();
  const { data } = await api.put(`/api/v1/me/folders/${folderId}/items/${item(type, id)}`);
  return StarSchema.parse(unwrap(data));
}

/** DELETE /me/folders/{folder}/items/{type}/{id} — keeps the star. */
export async function removeFromFolder(folderId: number, type: SaveableType, id: string): Promise<void> {
  await getCsrfCookie();
  await api.delete(`/api/v1/me/folders/${folderId}/items/${item(type, id)}`);
}
