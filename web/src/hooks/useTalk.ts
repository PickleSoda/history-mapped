import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRef } from 'react';
import { clearTalk, sendTalkMessage, talkConversation, talkList } from '@/lib/api';
import { qk } from '@/lib/query/queryKeys';
import type { TalkConversation } from '@/lib/schemas/talk';
import { withoutPending, withPendingMessage, withReply } from '@/lib/talk';
import { useMe } from './useMe';

/** The people the user has talked with, most recent first. Empty for guests. */
export function useTalkList() {
  const { me } = useMe();
  return useQuery({
    queryKey: qk.talkList(),
    queryFn: ({ signal }) => talkList(signal),
    enabled: me != null,
    staleTime: 60_000,
  });
}

/** One conversation (empty before the first message). A 422 means this person
 *  cannot be talked to, which is final, so it is never retried. */
export function useTalkConversation(entityId: string | undefined) {
  const { me } = useMe();
  return useQuery({
    queryKey: qk.talkConversation(entityId ?? ''),
    queryFn: ({ signal }) => talkConversation(entityId as string, signal),
    enabled: me != null && !!entityId,
    staleTime: 30_000,
    retry: false,
  });
}

/**
 * Send a message. The user's text shows at once and is swapped for the server's
 * copy with the reply; if the send fails it is taken back out (nothing was
 * stored) and the caller restores the draft from the error.
 */
export function useSendTalkMessage(entityId: string) {
  const qc = useQueryClient();
  const nextTempId = useRef(-1);
  return useMutation({
    mutationFn: (text: string) => sendTalkMessage(entityId, text),
    onMutate: async (text) => {
      await qc.cancelQueries({ queryKey: qk.talkConversation(entityId) });
      const tempId = nextTempId.current--;
      qc.setQueryData<TalkConversation>(qk.talkConversation(entityId), (old) =>
        old ? withPendingMessage(old, text, tempId) : old,
      );
      return { tempId };
    },
    onSuccess: (reply, _text, ctx) => {
      qc.setQueryData<TalkConversation>(qk.talkConversation(entityId), (old) =>
        old ? withReply(old, ctx.tempId, reply) : old,
      );
      void qc.invalidateQueries({ queryKey: qk.talkList() });
    },
    onError: (_error, _text, ctx) => {
      if (!ctx) return;
      qc.setQueryData<TalkConversation>(qk.talkConversation(entityId), (old) =>
        old ? withoutPending(old, ctx.tempId) : old,
      );
      // A refused send may have changed the allowance (daily cap): refetch it.
      void qc.invalidateQueries({ queryKey: qk.talkConversation(entityId) });
    },
  });
}

/** Forget the conversation: the list drops the person, the view starts empty. */
export function useClearTalk(entityId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => clearTalk(entityId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: qk.talkList() });
      void qc.invalidateQueries({ queryKey: qk.talkConversation(entityId) });
    },
  });
}
