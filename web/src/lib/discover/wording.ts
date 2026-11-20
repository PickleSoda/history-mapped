/**
 * The words of the Discover feed (on this day, meanwhile, for you), in one
 * place and pure, so they can be read and tested without rendering a card.
 * Nothing here adds a fact: every sentence is built from names, years and
 * kinds the API sent.
 */
import type { DiscoverEntity, MeanwhileRegion, OnThisDayItem, OnThisDayKind } from '@/lib/schemas/discover';
import { dayMonthLabel } from './date';

// ── names ─────────────────────────────────────────────────────────────────────

type Named = Pick<DiscoverEntity, 'name' | 'entity_group'>;

/** "Battle of Hastings", "Norman conquest of England", "Wall Street Crash of 1929". */
const OF_PHRASE = /^[\p{L}\p{N}][\p{L}\p{N}.–-]*(?:\s[\p{L}\p{N}][\p{L}\p{N}.–-]*){0,2}\s(?:of|on|at|for)\s/u;

/** Nouns that close an event's name: "First Crusade", "An Lushan Rebellion", "Yalta Conference". */
const EVENT_NOUNS = [
  'wars? revolutions? rebellion revolt uprising rising crusade campaign expedition conquest invasion offensive',
  'siege raids? landings? blockade bombings? massacre genocide mutiny coup plot conspiracy purge riots? strike',
  'crisis conflict emergency incident affair controversy intervention seizure trials? scheme',
  'famine plague pandemic epidemic earthquake eruption fire floods? disaster explosion',
  'treaty armistice agreement accords? pact protocol convention conference congress declaration referendum',
  'schism reformation restoration migrations? expansion',
].flatMap((line) => line.split(' '));
const EVENT_NOUN = new RegExp(`\\s(?:${EVENT_NOUNS.join('|')})$`, 'i');

/** The same nouns followed by a place: "Williamite War in Ireland", "War in the Vendée". */
const EVENT_NOUN_IN = new RegExp(`(?:^|\\s)(?:${EVENT_NOUNS.join('|')}|battles?)\\sin\\s`, 'i');

/** Names that never take the article ("Operation Overlord"). */
const NO_ARTICLE = /^(?:operation|hurricane|typhoon|cyclone)\s/i;

/** A name that brings its own ("The Troubles"). */
const OWN_ARTICLE = /^the\s+/i;

/** "Queen Anne's War", "Hundred Years' War" (but not "Xi'an"). */
const POSSESSIVE = /['’]s?(?:\s|$)/;

/** A name as it reads inside a sentence: the article, written small, and the name after it. */
export interface SentenceName {
  article: '' | 'the ';
  name: string;
}

/**
 * An event's name for use inside a sentence: "the " + "Battle of Hastings".
 *
 * The atlas stores names bare. The article is added only where the name's own
 * shape makes it safe: a "… of / on / at / for …" phrase, a closing noun such
 * as War or Rebellion, or such a noun followed by "in" and a place ("Williamite
 * War in Ireland"); a name that starts with its own ("The Troubles")
 * has it moved out and written small. Every other name is left as it is, and
 * so are people, states and places: a bare name reads as a title, a wrong
 * "the" reads as a mistake. Names with a possessive ("Queen Anne's War",
 * "Hannibal's crossing of the Alps") never get one.
 */
export function sentenceName(entity: Named): SentenceName {
  const name = entity.name.trim();
  if (entity.entity_group !== 'event') return { article: '', name };
  if (OWN_ARTICLE.test(name)) return { article: 'the ', name: name.replace(OWN_ARTICLE, '') };
  const plain = name.replace(/\s*\([^)]*\)$/, '');
  if (NO_ARTICLE.test(plain) || POSSESSIVE.test(plain)) return { article: '', name };
  const takesArticle = OF_PHRASE.test(plain) || EVENT_NOUN.test(plain) || EVENT_NOUN_IN.test(plain);
  return { article: takesArticle ? 'the ' : '', name };
}

/** The same as one string: "the Battle of Hastings". */
export function inSentence(entity: Named): string {
  const { article, name } = sentenceName(entity);
  return `${article}${name}`;
}

// ── on this day ───────────────────────────────────────────────────────────────

/**
 * What the date marks, as a word after the name ("Leo Tolstoy died", "Siege of
 * Vienna begins"). An event that simply happened that day needs none; anything
 * that is not an event or a person "ends" on its last day, whatever it was (a
 * state, a city, a unit).
 */
const KIND_WORDS: Record<OnThisDayKind, string | null> = {
  happened: null,
  began: 'begins',
  ended: 'ends',
  born: 'born',
  died: 'died',
  founded: 'founded',
  dissolved: 'ends',
};

export function kindWord(kind: OnThisDayKind): string | null {
  return KIND_WORDS[kind];
}

/** How far into a summary its opening aside may start (a long name with titles fits). */
const ASIDE_WITHIN = 90;

/**
 * A person's summary for a short preview. Encyclopedic leads open with an
 * aside in brackets right after the name (pronunciation, other spellings, life
 * dates), which fills two lines before the sentence says who they were:
 * "Selma Lagerlöf (US also; Swedish: […]; 20 November 1858 – 16 March 1940)
 * was a Swedish writer." That first aside is left out and nothing else is
 * touched. A summary whose first bracket opens late, or never closes, is
 * returned as it is.
 */
export function withoutOpeningAside(summary: string): string {
  const open = summary.indexOf('(');
  if (open < 0 || open > ASIDE_WITHIN) return summary;
  let depth = 0;
  for (let i = open; i < summary.length; i++) {
    if (summary[i] === '(') depth += 1;
    else if (summary[i] === ')') depth -= 1;
    if (depth > 0) continue;
    const before = summary.slice(0, open).trimEnd();
    const after = summary.slice(i + 1).trimStart();
    if (!before || !after) return summary;
    return /^[,.;:]/.test(after) ? `${before}${after}` : `${before} ${after}`;
  }
  return summary;
}

/** "20 November" for a local day key (YYYY-MM-DD), for the card's corner. */
export function dayKeyLabel(key: string): string {
  const [, month, day] = key.split('-').map(Number);
  return dayMonthLabel(month, day);
}

/**
 * "19 November" from an item's date as stored ("1815-11-19", "-0753-04-21",
 * "1925-11-19T00:00:00Z"); null when it carries no usable day.
 */
export function storedDayLabel(date: string): string | null {
  const m = /^[+-]?\d{1,6}-(\d{2})-(\d{2})(?!\d)/.exec(date.trim());
  if (!m) return null;
  const month = Number(m[1]);
  const day = Number(m[2]);
  return month >= 1 && month <= 12 && day >= 1 && day <= 31 ? dayMonthLabel(month, day) : null;
}

/**
 * Why "Meanwhile" shows that year on the browse page, from the item it was
 * taken from: "The year of the Battle of Hastings", "The year Leo Tolstoy died".
 */
export function yearReason(item: Pick<OnThisDayItem, 'kind' | 'name' | 'entity_group'>): string {
  const name = inSentence(item);
  switch (item.kind) {
    case 'born':
      return `The year ${name} was born`;
    case 'died':
      return `The year ${name} died`;
    case 'founded':
      return `The year ${name} was founded`;
    case 'began':
      return `The year ${name} began`;
    case 'ended':
    case 'dissolved':
      return `The year ${name} ended`;
    default:
      return `The year of ${name}`;
  }
}

// ── meanwhile ─────────────────────────────────────────────────────────────────

/** Region names that need the article inside a sentence, by stable key. */
const REGION_IN_SENTENCE: Record<string, string> = {
  'middle-east-north-africa': 'the Middle East & North Africa',
};

/** A region's name after "in": "Europe", "the Middle East & North Africa". */
export function regionInSentence(region: Pick<MeanwhileRegion, 'key' | 'name'>): string {
  return REGION_IN_SENTENCE[region.key] ?? region.name;
}

function counted(n: number, one: string, many: string): string {
  return `${n.toLocaleString('en-US')} ${n === 1 ? one : many}`;
}

/** "233 states and 42 events on the map"; null when there is neither. */
export function onTheMap(counts: { events: number; polities: number }): string | null {
  const parts = [
    counts.polities > 0 ? counted(counts.polities, 'state', 'states') : null,
    counts.events > 0 ? counted(counts.events, 'event', 'events') : null,
  ].filter((part): part is string => part !== null);
  return parts.length > 0 ? `${parts.join(' and ')} on the map` : null;
}

/** How each region's two rows were chosen, for the card's foot. */
export function meanwhileRule(window: number): string {
  const years = counted(Math.max(0, Math.trunc(window)), 'year', 'years');
  return `Each region: its most notable event within ${years}, and its most written-about state.`;
}

// ── for you ───────────────────────────────────────────────────────────────────

/**
 * "Because you opened Hannibal and Scipio Africanus"; with more names than
 * `show`, "… Hannibal, Scipio Africanus and 2 more". Null with no names.
 */
export function becauseLine(names: string[], show = 2): string | null {
  const list = names.map((name) => name.trim()).filter(Boolean);
  if (list.length === 0) return null;
  const head = list.slice(0, Math.max(1, show));
  const more = list.length - head.length;
  if (more > 0) return `Because you opened ${head.join(', ')} and ${more} more`;
  if (head.length === 1) return `Because you opened ${head[0]}`;
  return `Because you opened ${head.slice(0, -1).join(', ')} and ${head[head.length - 1]}`;
}

/** A relationship type in plain words: `victorious_at` → "victorious at". */
export function relationWords(relation: string | null | undefined): string | null {
  const words = (relation ?? '').replace(/[_\s]+/g, ' ').trim();
  return words || null;
}

/**
 * How a suggested entity is related to the opened one (`seed`), read in the
 * direction the relationship runs. A relationship reads "source, type,
 * target" and the row's own name is one of the two ends, so the line gives the
 * rest:
 *
 *   the row is the source   →  "victorious at Battle of Magdala"
 *   the opened one is       →  "Siege of Jhain: commanded by"
 *
 * Without a direction the two are only set side by side ("commanded by · via
 * Siege of Jhain"), which claims nothing about who did what.
 */
export function relationLine(
  relation: string | null | undefined,
  seed: string | null | undefined,
  outgoing: boolean | null | undefined,
): string | null {
  const words = relationWords(relation);
  const name = seed?.trim() || null;
  if (!words) return name ? `via ${name}` : null;
  if (!name) return words;
  if (outgoing == null) return `${words} · via ${name}`;
  return outgoing ? `${name}: ${words}` : `${words} ${name}`;
}
