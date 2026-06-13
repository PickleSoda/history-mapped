/** Zod schema for GET /chronicles/{slug} (ChronicleResource + entries). */
import { z } from 'zod';

/** One chronicle entry (ChronicleEntryResource) — a step in the tour. */
export const ChronicleEntrySchema = z.object({
  entry_id: z.string(),
  sequence_order: z.number(),
  start_year: z.number().nullable().default(null),
  end_year: z.number().nullable().default(null),
  impact_score: z.number().nullable().default(null),
  approximate_location: z.unknown().nullable().default(null),
  narrative_text: z.string().nullable().default(null),
});
export type ChronicleEntry = z.infer<typeof ChronicleEntrySchema>;

export const ChronicleSchema = z.object({
  chronicle_id: z.string(),
  title: z.string(),
  slug: z.string(),
  start_year: z.number().nullable().default(null),
  end_year: z.number().nullable().default(null),
  impact_score: z.number().nullable().default(null),
  approximate_location: z.unknown().nullable().default(null),
  entries: z.array(ChronicleEntrySchema).default([]),
});
export type Chronicle = z.infer<typeof ChronicleSchema>;
