/** Zod schemas for "Talk with people" (GET/POST/DELETE /me/talk…). */
import { z } from 'zod';

/** A linked Wikimedia image with its credit (shown wherever the image is). */
export const SpeakerImageSchema = z
  .object({
    url: z.string(),
    author: z.string().nullable().default(null),
    license: z.string().nullable().default(null),
    license_url: z.string().nullable().default(null),
    page_url: z.string().nullable().default(null),
  })
  .nullable()
  .catch(null);
export type SpeakerImage = z.infer<typeof SpeakerImageSchema>;

/** The person talked to. Dates are the atlas's own strings ("1769", "-44"). */
export const SpeakerSchema = z.object({
  id: z.string(),
  name: z.string(),
  entity_type: z.string().nullable().default(null),
  temporal_start: z.union([z.number(), z.string()]).nullable().default(null),
  temporal_end: z.union([z.number(), z.string()]).nullable().default(null),
  image: SpeakerImageSchema.default(null),
});
export type Speaker = z.infer<typeof SpeakerSchema>;

export const TalkRoleSchema = z.enum(['user', 'assistant']);

export const TalkMessageSchema = z.object({
  id: z.number(),
  role: TalkRoleSchema,
  content: z.string(),
  created_at: z.string().nullable().default(null),
});
export type TalkMessage = z.infer<typeof TalkMessageSchema>;

/** The user's daily message allowance (UTC day). */
export const DailyUsageSchema = z.object({
  limit: z.number(),
  used: z.number(),
  remaining: z.number(),
  resets_at: z.string().nullable().default(null),
});
export type DailyUsage = z.infer<typeof DailyUsageSchema>;

/** One row of the sidebar: a person already talked with. */
export const TalkRowSchema = z.object({
  id: z.number(),
  entity: SpeakerSchema,
  last_message: z
    .object({ role: TalkRoleSchema, snippet: z.string(), at: z.string().nullable().default(null) })
    .nullable()
    .default(null),
  last_message_at: z.string().nullable().default(null),
});
export type TalkRow = z.infer<typeof TalkRowSchema>;

export const TalkListSchema = z.object({
  data: z.array(TalkRowSchema),
  daily: DailyUsageSchema,
});
export type TalkList = z.infer<typeof TalkListSchema>;

/** One conversation with its messages (empty before the first message). */
export const TalkConversationSchema = z.object({
  data: z.object({
    entity: SpeakerSchema,
    talkable: z.boolean().default(true),
    knowledge_year: z.number().nullable().default(null),
    messages: z.array(TalkMessageSchema),
    daily: DailyUsageSchema,
  }),
});
export type TalkConversation = z.infer<typeof TalkConversationSchema>['data'];

/** The reply to a sent message. */
export const TalkReplySchema = z.object({
  data: z.object({
    user_message: TalkMessageSchema,
    assistant_message: TalkMessageSchema,
    daily: DailyUsageSchema,
  }),
});
export type TalkReply = z.infer<typeof TalkReplySchema>['data'];

/** Longest message the API accepts (config persona.limits.message_chars). */
export const TALK_MESSAGE_MAX = 2000;
