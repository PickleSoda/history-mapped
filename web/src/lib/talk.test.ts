import { describe, expect, it } from 'vitest';
import {
  TalkConversationSchema,
  TalkListSchema,
  TalkReplySchema,
} from './schemas/talk';
import type { TalkConversation } from './schemas/talk';
import { ago, allowanceNotice, isOptimistic, lifeText, withoutPending, withPendingMessage, withReply } from './talk';

const daily = { limit: 100, used: 1, remaining: 99, resets_at: null };
const speaker = { id: 'e1', name: 'Napoleon', entity_type: 'person', temporal_start: '1769', temporal_end: '1821', image: null };
const base: TalkConversation = {
  entity: speaker,
  talkable: true,
  knowledge_year: 1821,
  daily,
  messages: [{ id: 1, role: 'user', content: 'hi', created_at: null }],
};

describe('talk schemas', () => {
  it('parses a conversation and tolerates a missing image and unknown fields', () => {
    const parsed = TalkConversationSchema.parse({ data: { ...base, entity: { id: 'e', name: 'N', extra: 1 } } });
    expect(parsed.data.entity.image).toBeNull();
    expect(parsed.data.entity.temporal_end).toBeNull();
  });

  it('keeps a linked image with its credit and drops a malformed one', () => {
    const ok = TalkListSchema.parse({
      data: [{ id: 1, entity: { ...speaker, image: { url: 'https://x/y.jpg', author: 'A', license: 'CC BY 4.0' } }, last_message: null, last_message_at: null }],
      daily,
    });
    expect(ok.data[0].entity.image?.license).toBe('CC BY 4.0');
    const bad = TalkListSchema.parse({
      data: [{ id: 1, entity: { ...speaker, image: { nope: true } }, last_message: null, last_message_at: null }],
      daily,
    });
    expect(bad.data[0].entity.image).toBeNull();
  });

  it('rejects an unknown message role', () => {
    expect(() =>
      TalkReplySchema.parse({
        data: { user_message: { id: 1, role: 'system', content: 'x' }, assistant_message: { id: 2, role: 'assistant', content: 'y' }, daily },
      }),
    ).toThrow();
  });
});

describe('conversation cache edits', () => {
  it('shows a pending message, then swaps it for the server copies', () => {
    const pending = withPendingMessage(base, 'Tell me more', -5);
    expect(pending.messages.at(-1)).toMatchObject({ id: -5, role: 'user', content: 'Tell me more' });
    expect(isOptimistic(pending.messages.at(-1)!)).toBe(true);
    expect(base.messages).toHaveLength(1);

    const done = withReply(pending, -5, {
      user_message: { id: 2, role: 'user', content: 'Tell me more', created_at: null },
      assistant_message: { id: 3, role: 'assistant', content: 'Gladly.', created_at: null },
      daily: { ...daily, used: 2, remaining: 98 },
    });
    expect(done.messages.map((m) => m.id)).toEqual([1, 2, 3]);
    expect(done.daily.used).toBe(2);
  });

  it('drops the pending message when the send fails', () => {
    const pending = withPendingMessage(base, 'x', -9);
    expect(withoutPending(pending, -9).messages).toEqual(base.messages);
  });
});

describe('display helpers', () => {
  it('formats life dates, BCE included', () => {
    expect(lifeText({ temporal_start: '1769', temporal_end: '1821' })).toBe('1769 CE – 1821 CE');
    expect(lifeText({ temporal_start: '-100', temporal_end: '-44' })).toBe('100 BCE – 44 BCE');
    expect(lifeText({ temporal_start: null, temporal_end: '1821' })).toBe('1821 CE');
    expect(lifeText({ temporal_start: null, temporal_end: null })).toBeNull();
  });

  it('warns when the daily allowance runs low or out', () => {
    expect(allowanceNotice({ limit: 100, remaining: 50 })).toBeNull();
    expect(allowanceNotice({ limit: 100, remaining: 3 })).toEqual({ tone: 'info', text: '3 messages left today.' });
    expect(allowanceNotice({ limit: 100, remaining: 1 })?.text).toBe('1 message left today.');
    expect(allowanceNotice({ limit: 100, remaining: 0 })?.tone).toBe('blocked');
  });

  it('writes a compact age', () => {
    const now = new Date('2026-11-19T12:00:00Z');
    expect(ago('2026-11-19T11:59:40Z', now)).toBe('now');
    expect(ago('2026-11-19T11:30:00Z', now)).toBe('30m');
    expect(ago('2026-11-19T09:00:00Z', now)).toBe('3h');
    expect(ago('2026-11-17T12:00:00Z', now)).toBe('2d');
    expect(ago(null, now)).toBe('');
  });
});
