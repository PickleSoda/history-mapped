/**
 * nuqs parsers — the typed URL schema (spec §2).
 *
 * Each search param has a parser here. Hooks in `@/hooks` consume these so that
 * a component subscribing to `sel` is not woken when `bbox` changes. History
 * mode (push vs replace) is set per-hook at the call site, not here.
 */
import {
  createParser,
  parseAsArrayOf,
  parseAsInteger,
  parseAsString,
  parseAsStringEnum,
  parseAsStringLiteral,
} from 'nuqs';
import { ENTITY_GROUPS } from '@/types/atlas';
import type { Bbox, TimeState } from '@/types/atlas';
import { parseBbox, parseTime, serializeBbox, serializeTime } from './serialize';

/** bbox = "w,s,e,n" */
export const parseAsBbox = createParser<Bbox>({
  parse: parseBbox,
  serialize: serializeBbox,
});

/** t = "-490" (instant) or "-490..-480" (range) */
export const parseAsTime = createParser<TimeState>({
  parse: parseTime,
  serialize: serializeTime,
});

/** g = "polity,event" — empty/absent means "all groups". */
export const parseAsGroups = parseAsArrayOf(
  parseAsStringEnum([...ENTITY_GROUPS]),
  ',',
);

/** sel, q, chron — type-prefixed id / free text / chronicle id. */
export const parseAsSelection = parseAsString;
export const parseAsSearch = parseAsString;
export const parseAsChronicle = parseAsString;

/** step = chronicle step index. */
export const parseAsStep = parseAsInteger;

/** view = "map" | "globe" */
export const parseAsView = parseAsStringLiteral(['map', 'globe'] as const);
