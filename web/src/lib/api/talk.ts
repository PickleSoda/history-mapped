/** "Talk with people": the user's one conversation per historical person. */
import { isAxiosError } from 'axios';
import { TalkConversationSchema, TalkListSchema, TalkReplySchema } from '@/lib/schemas/talk';
import type { TalkConversation, TalkList, TalkReply } from '@/lib/schemas/talk';
import { api, getCsrfCookie } from './client';

const path = (entityId: string) => `/api/v1/me/talk/${encodeURIComponent(entityId)}`;

/** GET /me/talk — the people already talked with, most recent first. */
export async function talkList(signal?: AbortSignal): Promise<TalkList> {
  const { data } = await api.get('/api/v1/me/talk', { signal });
  return TalkListSchema.parse(data);
}

/** GET /me/talk/{entity} — the conversation (empty before the first message). */
export async function talkConversation(entityId: string, signal?: AbortSignal): Promise<TalkConversation> {
  const { data } = await api.get(path(entityId), { signal });
  return TalkConversationSchema.parse(data).data;
}

/** POST /me/talk/{entity}/messages — send a message, get the reply. Not streamed (v1). */
export async function sendTalkMessage(entityId: string, message: string): Promise<TalkReply> {
  await getCsrfCookie();
  const { data } = await api.post(`${path(entityId)}/messages`, { message });
  return TalkReplySchema.parse(data).data;
}

/** DELETE /me/talk/{entity} — forget the whole conversation. */
export async function clearTalk(entityId: string): Promise<void> {
  await getCsrfCookie();
  await api.delete(path(entityId));
}

/** The API's machine code for a refusal: `daily_limit`, `not_talkable`,
 *  `provider_failed`, `busy`, `crowded`; null for anything else. */
export function talkErrorCode(error: unknown): string | null {
  if (!isAxiosError(error)) return null;
  const code = (error.response?.data as { code?: unknown } | undefined)?.code;
  return typeof code === 'string' ? code : null;
}
