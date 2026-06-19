/**
 * Zod schemas for the public reference endpoints.
 *
 * Historical periods: GET /api/v1/reference/historical-periods — a flat,
 * hierarchical (depth_level/parent) list of named eras with their own colours.
 * The API sends `start_date`/`end_date` as year STRINGS (negative = BCE), so we
 * coerce to numbers at the boundary.
 */
import { z } from 'zod';

export const HistoricalPeriodSchema = z.object({
  period_id: z.number(),
  name: z.string(),
  /** Year (negative = BCE). API sends as a numeric string. */
  start_date: z.coerce.number(),
  end_date: z.coerce.number(),
  /** Nesting depth: 0 = top-level era. Drives the gantt lane. */
  depth_level: z.coerce.number().default(0),
  parent_period_id: z.number().nullable().default(null),
  /** Per-period cartographic colour, e.g. "#8B4513". */
  color_hex: z.string().nullable().default(null),
  sort_order: z.coerce.number().default(0),
});

export type HistoricalPeriod = z.infer<typeof HistoricalPeriodSchema>;

/** Laravel wraps collections in a `data` envelope. */
export const HistoricalPeriodListSchema = z.object({
  data: z.array(HistoricalPeriodSchema),
});
