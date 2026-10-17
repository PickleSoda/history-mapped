import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback } from 'react';
import {
  addToFolder,
  createFolder,
  deleteFolder,
  folders,
  removeFromFolder,
  star,
  starKeys,
  stars,
  unstar,
  updateFolder,
} from '@/lib/api';
import type { FolderInput, StarListParams } from '@/lib/api';
import { qk } from '@/lib/query/queryKeys';
import type { SaveableType, StarKey } from '@/lib/schemas/saved';
import { useMe } from './useMe';

/** Map key for a saved target. */
export const starKey = (type: SaveableType, id: string) => `${type}:${id}`;

function indexKeys(keys: StarKey[]): Map<string, StarKey> {
  return new Map(keys.map((k) => [starKey(k.type, k.id), k]));
}

/** Every star the user has, indexed `type:id` → key. Empty for guests. */
export function useStarKeys() {
  const { me } = useMe();
  return useQuery({
    queryKey: qk.starKeys(),
    queryFn: ({ signal }) => starKeys(signal),
    enabled: me != null,
    staleTime: 5 * 60_000,
    select: indexKeys,
  });
}

/** One target's star state: starred + the folders it is filed in. */
export function useStarState(type: SaveableType, id: string) {
  const { data } = useStarKeys();
  const key = data?.get(starKey(type, id));
  return { starred: key != null, folderIds: key?.folder_ids ?? [] };
}

/**
 * Optimistically rewrite the cached star keys, returning a rollback. Every
 * star/folder mutation goes through this, so all toggles on screen agree
 * instantly, then the server's answer is refetched.
 */
function useOptimisticKeys() {
  const qc = useQueryClient();
  const patch = useCallback(
    async (fn: (keys: StarKey[]) => StarKey[]) => {
      await qc.cancelQueries({ queryKey: qk.starKeys() });
      const prev = qc.getQueryData<StarKey[]>(qk.starKeys());
      qc.setQueryData<StarKey[]>(qk.starKeys(), (old) => fn(old ?? []));
      return () => qc.setQueryData(qk.starKeys(), prev);
    },
    [qc],
  );
  const settle = useCallback(() => {
    void qc.invalidateQueries({ queryKey: qk.stars() });
    void qc.invalidateQueries({ queryKey: qk.folders() });
  }, [qc]);
  return { patch, settle };
}

const without = (keys: StarKey[], type: SaveableType, id: string) =>
  keys.filter((k) => !(k.type === type && k.id === id));

/** Star / unstar. Pass the current state; the mutation flips it. */
export function useToggleStar() {
  const { patch, settle } = useOptimisticKeys();
  return useMutation({
    mutationFn: ({ type, id, starred }: { type: SaveableType; id: string; starred: boolean }) =>
      starred ? unstar(type, id) : star(type, id).then(() => undefined),
    onMutate: ({ type, id, starred }) =>
      patch((keys) =>
        starred
          ? without(keys, type, id)
          : [...without(keys, type, id), { type, id, star_id: -1, folder_ids: [] }],
      ),
    onError: (_e, _v, rollback) => rollback?.(),
    onSettled: settle,
  });
}

/** Add to / remove from a folder (adding stars the item if needed). */
export function useFolderMembership() {
  const { patch, settle } = useOptimisticKeys();
  return useMutation({
    mutationFn: ({
      folderId,
      type,
      id,
      member,
    }: {
      folderId: number;
      type: SaveableType;
      id: string;
      /** Currently in the folder → remove; else add. */
      member: boolean;
    }) =>
      member ? removeFromFolder(folderId, type, id) : addToFolder(folderId, type, id).then(() => undefined),
    onMutate: ({ folderId, type, id, member }) =>
      patch((keys) => {
        const current = keys.find((k) => k.type === type && k.id === id);
        const folderIds = current?.folder_ids ?? [];
        const next: StarKey = {
          type,
          id,
          star_id: current?.star_id ?? -1,
          folder_ids: member ? folderIds.filter((f) => f !== folderId) : [...folderIds, folderId],
        };
        return [...without(keys, type, id), next];
      }),
    onError: (_e, _v, rollback) => rollback?.(),
    onSettled: settle,
  });
}

/** The user's folders, by name. Empty for guests. */
export function useFolders() {
  const { me } = useMe();
  return useQuery({
    queryKey: qk.folders(),
    queryFn: ({ signal }) => folders(signal),
    enabled: me != null,
    staleTime: 5 * 60_000,
  });
}

export function useCreateFolder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: FolderInput) => createFolder(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.folders() }),
  });
}

export function useUpdateFolder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...input }: Partial<FolderInput> & { id: number }) => updateFolder(id, input),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.folders() }),
  });
}

/** Delete a folder — its stars stay, so the keys lose that folder id. */
export function useDeleteFolder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteFolder(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: qk.folders() });
      void qc.invalidateQueries({ queryKey: qk.stars() });
    },
  });
}

/** A page of starred items (optionally one type / one folder). */
export function useStars(params: StarListParams) {
  const { me } = useMe();
  return useQuery({
    queryKey: qk.starList(params),
    queryFn: ({ signal }) => stars(params, signal),
    enabled: me != null,
    placeholderData: keepPreviousData,
  });
}
