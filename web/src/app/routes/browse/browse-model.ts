/**
 * Pure view-model for the browse pages (spec 2026-11-01 public site, D4): tag
 * grids and trees, facet-route resolution, count and year labels, collection
 * item ordering, story kinds, and the tiny markdown subset set descriptions
 * use (paragraphs and links). No React, no fetching: Vitest-covered.
 */
import { primaryImage } from '@/lib/entity-format';
import type { MediaItem } from '@/lib/entity-format';
import { formatYear } from '@/lib/format';
import type { CollectionItem, CollectionItemKind, ItemsByKind } from '@/lib/schemas/collection';
import { TAG_FACETS } from '@/lib/schemas/tag';
import type { Tag, TagFacet } from '@/lib/schemas/tag';
import { FACETS, ancestorsOf, displayTags } from '@/lib/tags';
import type { IndexedTag, TagIndex } from '@/lib/tags';

/** The facets `/browse` shows as grids (topics are open-ended, so they only
 *  get pages, not a grid). */
export const BROWSE_FACETS: TagFacet[] = ['era', 'region', 'theme', 'type'];

export const FACET_HEADINGS: Record<TagFacet, string> = {
  era: 'Eras',
  region: 'Regions',
  theme: 'Themes',
  type: 'Kinds of chronicle',
  topic: 'Topics',
};

// ── Labels ────────────────────────────────────────────────────────────────

/** "1 chronicle", "1,259 entities". */
export function countLabel(n: number, one: string, many: string): string {
  return `${n.toLocaleString('en-US')} ${n === 1 ? one : many}`;
}

/** "19 chronicles · 1,259 entities"; zero parts left out; null when both are 0. */
export function tagCountsLabel(t: Pick<Tag, 'chronicle_count' | 'entity_count'>): string | null {
  const parts = [
    t.chronicle_count > 0 ? countLabel(t.chronicle_count, 'chronicle', 'chronicles') : null,
    t.entity_count > 0 ? countLabel(t.entity_count, 'entity', 'entities') : null,
  ].filter(Boolean);
  return parts.length > 0 ? parts.join(' · ') : null;
}

const KIND_NOUNS: Record<CollectionItemKind, [string, string]> = {
  chronicle: ['chronicle', 'chronicles'],
  story: ['battle map', 'battle maps'],
  entity: ['entity', 'entities'],
  tag: ['tag', 'tags'],
};

/** Display order of item kinds in counts and filters. */
export const ITEM_KIND_ORDER: CollectionItemKind[] = ['chronicle', 'story', 'entity', 'tag'];

/** "Chronicles", "Battle maps"… for a filter chip. */
export function itemKindHeading(kind: CollectionItemKind): string {
  const many = KIND_NOUNS[kind][1];
  return many.charAt(0).toUpperCase() + many.slice(1);
}

/** "3 chronicles · 2 battle maps · 5 entities"; null for an empty set. */
export function itemsByKindLabel(counts: ItemsByKind): string | null {
  const parts = ITEM_KIND_ORDER.filter((k) => counts[k] > 0).map((k) =>
    countLabel(counts[k], ...KIND_NOUNS[k]),
  );
  return parts.length > 0 ? parts.join(' · ') : null;
}

/**
 * A span of years: "500 – 1499 CE", "3000 – 501 BCE", "500 BCE – 499 CE";
 * "from 1945 CE" / "until 3001 BCE" with one open end; null with neither.
 */
export function yearRangeLabel(start: number | null, end: number | null): string | null {
  if (start != null && end != null) {
    if (start === end) return formatYear(start);
    if (start < 0 && end < 0) return `${-start} – ${-end} BCE`;
    if (start >= 0 && end >= 0) return `${start} – ${end} CE`;
    return `${formatYear(start)} – ${formatYear(end)}`;
  }
  if (start != null) return `from ${formatYear(start)}`;
  if (end != null) return `until ${formatYear(end)}`;
  return null;
}

// ── Tag grids ─────────────────────────────────────────────────────────────

/** A tag anything carries (unused tags get no card). */
export function isUsedTag(t: Pick<Tag, 'chronicle_count' | 'entity_count'>): boolean {
  return t.chronicle_count > 0 || t.entity_count > 0;
}

export interface TagNode {
  tag: IndexedTag;
  children: TagNode[];
}

/**
 * One facet's tags as a forest along `parent` (Asia › Middle East ›
 * Mesopotamia), in vocabulary order. A tag whose parent is missing or in
 * another facet is a root. Unused tags are dropped unless something under
 * them is used.
 */
export function tagTree(tags: IndexedTag[], facet: TagFacet): TagNode[] {
  const inFacet = tags.filter((t) => t.facet === facet).sort((a, b) => a.order - b.order);
  const slugs = new Set(inFacet.map((t) => t.slug));
  const byParent = new Map<string | null, IndexedTag[]>();
  for (const t of inFacet) {
    const key = t.parent && slugs.has(t.parent) && t.parent !== t.slug ? t.parent : null;
    byParent.set(key, [...(byParent.get(key) ?? []), t]);
  }
  const build = (parent: string | null, seen: Set<string>): TagNode[] =>
    (byParent.get(parent) ?? []).flatMap((tag): TagNode[] => {
      if (seen.has(tag.slug)) return [];
      const children = build(tag.slug, new Set([...seen, tag.slug]));
      return isUsedTag(tag) || children.length > 0 ? [{ tag, children }] : [];
    });
  return build(null, new Set());
}

export interface FacetSection {
  facet: TagFacet;
  heading: string;
  roots: TagNode[];
}

/** The `/browse` grids: era, region, theme and type, each as a tag forest;
 *  facets with nothing in them are left out. */
export function facetSections(tags: IndexedTag[]): FacetSection[] {
  return BROWSE_FACETS.map((facet) => ({ facet, heading: FACET_HEADINGS[facet], roots: tagTree(tags, facet) })).filter(
    (s) => s.roots.length > 0,
  );
}

/** Used child tags of `slug` (the chips on a facet page). */
export function childTags(slug: string, tags: IndexedTag[]): IndexedTag[] {
  return tags.filter((t) => t.parent === slug && t.slug !== slug && isUsedTag(t)).sort((a, b) => a.order - b.order);
}

/** The tag's ancestors, broadest first (for the breadcrumb). */
export function tagLineage(slug: string, index: TagIndex): IndexedTag[] {
  return ancestorsOf(slug, index)
    .reverse()
    .map((s) => index.get(s))
    .filter((t): t is IndexedTag => t != null);
}

export type FacetRoute =
  | { status: 'ok'; tag: IndexedTag }
  | { status: 'redirect'; facet: TagFacet; tag: IndexedTag }
  | { status: 'not-found' };

/**
 * What `/browse/:facet/:tag` shows: the tag; a redirect when the tag exists
 * under another facet (`/browse/era/china` → `/browse/region/china`); or
 * not-found for an unknown facet or tag.
 */
export function resolveFacetRoute(facet: string, slug: string, index: TagIndex): FacetRoute {
  if (!(TAG_FACETS as readonly string[]).includes(facet)) return { status: 'not-found' };
  const tag = index.get(slug);
  if (!tag) return { status: 'not-found' };
  if (tag.facet !== facet) return { status: 'redirect', facet: tag.facet, tag };
  return { status: 'ok', tag };
}

/** "Era", "Region"… */
export function facetLabel(facet: TagFacet): string {
  return FACETS[facet].label;
}

// ── Chronicle and entity cards ────────────────────────────────────────────

/** The chronicle's kind (its `type` tag), if it has one. */
export function chronicleTypeTag(slugs: string[], index: TagIndex): IndexedTag | null {
  return displayTags(slugs, index).find((t) => t.facet === 'type') ?? null;
}

/** Up to `limit` most specific era / region / theme tags for a card, minus
 *  the tag (and its ancestors) of the page it is shown on. */
export function cardTags(slugs: string[], index: TagIndex, exclude: string | null = null, limit = 3): IndexedTag[] {
  const hidden = new Set(exclude ? [exclude, ...ancestorsOf(exclude, index)] : []);
  return displayTags(slugs, index)
    .filter((t) => (t.facet === 'era' || t.facet === 'region' || t.facet === 'theme') && !hidden.has(t.slug))
    .slice(0, limit);
}

// ── Collections ───────────────────────────────────────────────────────────

/** A stable key for an item (an id or slug can repeat across kinds). */
export function itemKey(item: CollectionItem): string {
  switch (item.kind) {
    case 'entity':
      return `entity:${item.entity.id}`;
    case 'chronicle':
      return `chronicle:${item.chronicle.slug}`;
    case 'story':
      return `story:${item.story.slug}`;
    case 'tag':
      return `tag:${item.tag.slug}`;
  }
}

export interface NumberedItem {
  /** 1-based place in the author's order (kept when the list is filtered). */
  position: number;
  key: string;
  item: CollectionItem;
}

/** Items numbered in the author's order; a repeated item keeps its first place. */
export function numberItems(items: CollectionItem[]): NumberedItem[] {
  const seen = new Set<string>();
  const out: NumberedItem[] = [];
  for (const item of items) {
    const key = itemKey(item);
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ position: out.length + 1, key, item });
  }
  return out;
}

/** Counts of the resolved items by kind (what the page can actually show). */
export function countItemsByKind(items: { item: CollectionItem }[]): ItemsByKind {
  const counts: ItemsByKind = { entity: 0, chronicle: 0, story: 0, tag: 0 };
  for (const { item } of items) counts[item.kind] += 1;
  return counts;
}

/** The kinds present, in display order (the filter chips; none when only one). */
export function itemKindFilters(counts: ItemsByKind): CollectionItemKind[] {
  const kinds = ITEM_KIND_ORDER.filter((k) => counts[k] > 0);
  return kinds.length > 1 ? kinds : [];
}

/** Items of one kind (all for null), author's numbering kept. */
export function filterItems(items: NumberedItem[], kind: CollectionItemKind | null): NumberedItem[] {
  return kind ? items.filter((i) => i.item.kind === kind) : items;
}

// ── Stories ───────────────────────────────────────────────────────────────

const STORY_KIND_NAMES: Record<string, string> = {
  battle: 'Battles',
  naval_battle: 'Naval battles',
  siege: 'Sieges',
  campaign: 'Campaigns',
  war: 'Wars',
  epidemic: 'Epidemics',
  trade_route: 'Trade routes',
  migration: 'Migrations',
  exploration: 'Voyages',
  expansion: 'Expansions',
  diffusion: 'Spread',
  event: 'Events',
};

/** Plural chip label for a story kind ("Naval battles"); unknown kinds humanised. */
export function storyKindName(kind: string): string {
  const known = STORY_KIND_NAMES[kind];
  if (known) return known;
  const s = kind.replace(/[_-]+/g, ' ').trim();
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : 'Other';
}

/** Distinct story kinds with counts, most common first (then by name). */
export function storyKinds(rows: { kind: string }[]): { kind: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const r of rows) counts.set(r.kind, (counts.get(r.kind) ?? 0) + 1);
  return [...counts]
    .map(([kind, count]) => ({ kind, count }))
    .sort((a, b) => b.count - a.count || storyKindName(a.kind).localeCompare(storyKindName(b.kind)));
}

// ── Images ────────────────────────────────────────────────────────────────

/** The picture to lead an entity card with, when its summary carries one
 *  (`image`, else `media_refs`; any shape `primaryImage()` reads). */
export function entityImage(e: { image?: unknown; media_refs?: unknown } | null | undefined): MediaItem | null {
  if (!e) return null;
  return primaryImage(e.image ?? e.media_refs ?? null);
}

// ── Markdown (paragraphs and links only) ──────────────────────────────────

/** Markdown → one line of plain text (links reduced to their text), at most
 *  `max` characters, cut at a word. For meta descriptions and card blurbs. */
export function plainText(text: string | null | undefined, max = 160): string | null {
  if (!text) return null;
  const flat = text
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/[*_`#>]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
  if (!flat) return null;
  if (flat.length <= max) return flat;
  const cut = flat.slice(0, max - 1);
  return `${cut.slice(0, Math.max(cut.lastIndexOf(' '), max / 2)).trimEnd()}…`;
}

export type InlineSegment =
  | { type: 'text'; text: string }
  | { type: 'link'; text: string; to: string; external: boolean };

/** A link target we render: an in-app path (`/…`, not `//…`) or an http(s) /
 *  mailto URL. Anything else (`javascript:`, relative junk) is null. */
export function safeLinkTarget(href: string): { to: string; external: boolean } | null {
  const h = href.trim();
  if (h.startsWith('/') && !h.startsWith('//')) return { to: h, external: false };
  if (/^(https?:\/\/|mailto:)/i.test(h)) return { to: h, external: true };
  return null;
}

const LINK = /\[([^\]]+)\]\(\s*<?([^)\s>]+)>?(?:\s+"[^"]*")?\s*\)/g;

/** Strip emphasis / code markers, keeping their text. */
function plain(text: string): string {
  return text.replace(/\*\*([^*]+)\*\*/g, '$1').replace(/\*([^*\s][^*]*)\*/g, '$1').replace(/`([^`]+)`/g, '$1');
}

/** One paragraph → text and link segments (unsafe links become their text). */
export function inlineSegments(paragraph: string): InlineSegment[] {
  const out: InlineSegment[] = [];
  const push = (text: string) => {
    if (!text) return;
    const last = out[out.length - 1];
    if (last?.type === 'text') last.text += text;
    else out.push({ type: 'text', text });
  };
  let at = 0;
  for (const m of paragraph.matchAll(LINK)) {
    push(plain(paragraph.slice(at, m.index)));
    const target = safeLinkTarget(m[2]);
    if (target) out.push({ type: 'link', text: plain(m[1]), ...target });
    else push(plain(m[1]));
    at = (m.index ?? 0) + m[0].length;
  }
  push(plain(paragraph.slice(at)));
  return out;
}

/** Markdown → paragraphs of segments. Blank lines split paragraphs; single
 *  newlines join; heading and list markers are dropped. */
export function markdownParagraphs(text: string | null | undefined): InlineSegment[][] {
  return (text ?? '')
    .split(/\n\s*\n/)
    .map((p) =>
      p
        .split('\n')
        .map((line) => line.replace(/^\s{0,3}(#{1,6}\s+|[-*+]\s+|>\s?)/, '').trim())
        .filter(Boolean)
        .join(' '),
    )
    .filter(Boolean)
    .map(inlineSegments);
}
