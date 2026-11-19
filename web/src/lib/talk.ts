/**
 * Pure helpers of the Talk pages: cache edits for the conversation (so a sent
 * message shows at once and is swapped for the server's copy), and display
 * text. No React here, so it is unit-tested directly.
 */
import { dateText } from '@/lib/entity-format';
import type { DailyUsage, Speaker, TalkConversation, TalkMessage, TalkReply } from '@/lib/schemas/talk';

/** Ids of unsent messages are negative, so they never clash with server ids. */
export const isOptimistic = (m: TalkMessage) => m.id < 0;

/** Show the user's message immediately, before the reply arrives. */
export function withPendingMessage(
  conversation: TalkConversation,
  text: string,
  tempId: number,
  now = new Date(),
): TalkConversation {
  const pending: TalkMessage = { id: tempId, role: 'user', content: text, created_at: now.toISOString() };
  return { ...conversation, messages: [...conversation.messages, pending] };
}

/** Swap the pending message for the server's user + assistant messages. */
export function withReply(conversation: TalkConversation, tempId: number, reply: TalkReply): TalkConversation {
  const kept = conversation.messages.filter((m) => m.id !== tempId);
  return { ...conversation, messages: [...kept, reply.user_message, reply.assistant_message], daily: reply.daily };
}

/** Take the pending message back out (the send failed). */
export function withoutPending(conversation: TalkConversation, tempId: number): TalkConversation {
  return { ...conversation, messages: conversation.messages.filter((m) => m.id !== tempId) };
}

/** "1769 – 1821", "100 BCE – 44 BCE", or one bound; null when neither is known. */
export function lifeText(speaker: Pick<Speaker, 'temporal_start' | 'temporal_end'>): string | null {
  const s = dateText(speaker.temporal_start);
  const e = dateText(speaker.temporal_end);
  if (s && e) return `${s} – ${e}`;
  return s ?? e;
}

/** The notice above the input once the daily allowance runs low, else null. */
export function allowanceNotice(daily: Pick<DailyUsage, 'limit' | 'remaining'>): {
  tone: 'info' | 'blocked';
  text: string;
} | null {
  if (daily.remaining <= 0) {
    return { tone: 'blocked', text: `You have used today’s ${daily.limit} messages. The allowance resets at midnight UTC.` };
  }
  if (daily.remaining <= 10) {
    return { tone: 'info', text: `${daily.remaining} message${daily.remaining === 1 ? '' : 's'} left today.` };
  }
  return null;
}

/** A compact "5m", "3h", "2d" or a date, for the sidebar. */
export function ago(iso: string | null, now = new Date()): string {
  if (!iso) return '';
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return '';
  const s = Math.max(0, Math.round((now.getTime() - t) / 1000));
  if (s < 60) return 'now';
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  if (s < 86400 * 7) return `${Math.floor(s / 86400)}d`;
  return new Date(t).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
}

/** The first letter of a name for an avatar without a picture. */
export const initial = (name: string) => (name.trim()[0] ?? '?').toUpperCase();
