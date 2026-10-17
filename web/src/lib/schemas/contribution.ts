/** Zod schemas for text contributions (suggested edits). */
import { z } from 'zod';

export const CONTRIBUTION_TARGET_TYPES = [
  'entity',
  'relationship',
  'chronicle',
  'chronicle_entry',
] as const;
export type ContributionTargetType = (typeof CONTRIBUTION_TARGET_TYPES)[number];

export const CONTRIBUTION_STATUSES = ['pending', 'approved', 'rejected', 'withdrawn'] as const;
export type ContributionStatus = (typeof CONTRIBUTION_STATUSES)[number];

/** One diff chunk: `=` unchanged, `-` removed, `+` added. */
export const DiffChunkSchema = z.tuple([z.enum(['=', '-', '+']), z.string()]);

export const ContributionSchema = z.object({
  id: z.number(),
  target_type: z.enum(CONTRIBUTION_TARGET_TYPES),
  target_id: z.string(),
  field: z.string(),
  target_label: z.string().catch(''),
  /** Where the target lives in the atlas (absolute), when it still exists. */
  public_url: z.string().nullable().catch(null),
  status: z.enum(CONTRIBUTION_STATUSES),
  note: z.string().nullable().default(null),
  review_note: z.string().nullable().default(null),
  base_text: z.string().catch(''),
  proposed_text: z.string().catch(''),
  diff: z.array(DiffChunkSchema).catch([]),
  stats: z.object({ added: z.number(), removed: z.number() }).catch({ added: 0, removed: 0 }),
  created_at: z.string().nullable().default(null),
  reviewed_at: z.string().nullable().default(null),
});
export type Contribution = z.infer<typeof ContributionSchema>;

const PaginatorMetaSchema = z.object({
  current_page: z.number(),
  last_page: z.number(),
  per_page: z.number(),
  total: z.number(),
});

export const ContributionListSchema = z.object({
  data: z.array(ContributionSchema),
  meta: PaginatorMetaSchema,
});
export type ContributionList = z.infer<typeof ContributionListSchema>;
