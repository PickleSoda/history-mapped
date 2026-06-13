/** Zod schema for a chronicle (guided tour) — fetched whole, one request. */
import { z } from 'zod';
import { parseBbox } from '@/lib/url/serialize';
import type { Bbox } from '@/types/atlas';

const BboxFromStringSchema = z
  .string()
  .transform((s) => parseBbox(s))
  .pipe(z.custom<Bbox>((v) => v !== null, 'invalid bbox'));

export const ChronicleStepSchema = z.object({
  index: z.number(),
  title: z.string(),
  beat: z.string(),
  /** Type-prefixed entity id this step focuses. */
  sel: z.string().nullable().default(null),
  /** Derived scope for the step: the camera + timeline are driven from these. */
  bbox: BboxFromStringSchema,
  year: z.number(),
});
export type ChronicleStep = z.infer<typeof ChronicleStepSchema>;

export const ChronicleSchema = z.object({
  id: z.string(),
  title: z.string(),
  steps: z.array(ChronicleStepSchema),
});
export type Chronicle = z.infer<typeof ChronicleSchema>;
