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

/** `edit` corrects one text field; `create` proposes a new entity or relationship (made via the MCP connector). */
export const CONTRIBUTION_KINDS = ['edit', 'create'] as const;
export type ContributionKind = (typeof CONTRIBUTION_KINDS)[number];

export const ContributionSchema = z.object({
  id: z.number(),
  /** Older API responses have no `kind`: those are all edits. */
  kind: z.enum(CONTRIBUTION_KINDS).catch('edit'),
  source: z.enum(['atlas', 'mcp']).catch('atlas'),
  client: z.string().nullable().default(null),
  target_type: z.enum(CONTRIBUTION_TARGET_TYPES),
  /** Null for a proposal not yet approved. */
  target_id: z.string().nullable().default(null),
  field: z.string().catch(''),
  /** One line describing a `create` proposal; null for edits. */
  summary: z.string().nullable().default(null),
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
