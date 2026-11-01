/**
 * Zod schemas for the curated sets (GET /collections, GET /collections/{slug};
 * spec 2026-11-01 public site, D4). Items are resolved by the API when served
 * and arrive in the author's order as `{kind, note, entity|chronicle|story|tag}`.
 * Parsing is lenient: an item whose payload is missing or malformed is dropped
 * (the API drops unresolvable refs too), never the whole set.
 */
import { z } from 'zod';
import { ChronicleSummarySchema } from './chronicle';
import { EntitySummarySchema } from './entity';
import { MapStoryListItemSchema } from './map-story-list';
import type { MapStoryListItem } from './map-story-list';
import { TagSchema } from './tag';
import type { Tag } from './tag';

export const COLLECTION_ITEM_KINDS = ['entity', 'chronicle', 'story', 'tag'] as const;
export type CollectionItemKind = (typeof COLLECTION_ITEM_KINDS)[number];

/**
 * An entity summary as a set serves it (EntitySummaryResource). The summary
 * has no image today; `media_refs` / `image` are read when the API adds one
 * (any shape `primaryImage()` understands).
 */
export const CollectionEntitySchema = EntitySummarySchema.extend({
  tags: z.array(z.string()).catch([]).default([]),
  media_refs: z.unknown().optional(),
  image: z.unknown().optional(),
});
export type CollectionEntity = z.infer<typeof CollectionEntitySchema>;

/** A chronicle row (ChronicleResource without entries) plus its introduction. */
export const CollectionChronicleSchema = ChronicleSummarySchema.extend({
  description: z.string().nullable().catch(null).default(null),
});
export type CollectionChronicle = z.infer<typeof CollectionChronicleSchema>;

const count = z.number().catch(0).default(0);

export const ItemsByKindSchema = z.object({
  entity: count,
  chronicle: count,
  story: count,
  tag: count,
});
export type ItemsByKind = z.infer<typeof ItemsByKindSchema>;

const NO_ITEMS: ItemsByKind = { entity: 0, chronicle: 0, story: 0, tag: 0 };

/** One row of GET /collections. */
export const CollectionSummarySchema = z.object({
  slug: z.string(),
  title: z.string(),
  subtitle: z.string().nullable().catch(null).default(null),
  /** Markdown (paragraphs and links). */
  description: z.string().nullable().catch(null).default(null),
  cover: CollectionEntitySchema.nullable().catch(null).default(null),
  item_count: count,
  items_by_kind: ItemsByKindSchema.catch(NO_ITEMS).default(NO_ITEMS),
});
export type CollectionSummary = z.infer<typeof CollectionSummarySchema>;

export const CollectionListSchema = z.object({
  data: z.array(CollectionSummarySchema),
});
export type CollectionList = z.infer<typeof CollectionListSchema>;

interface ItemBase {
  /** The author's note on why this item is in the set. */
  note: string | null;
}

/** A resolved item, discriminated by `kind`. */
export type CollectionItem =
  | (ItemBase & { kind: 'entity'; entity: CollectionEntity })
  | (ItemBase & { kind: 'chronicle'; chronicle: CollectionChronicle })
  | (ItemBase & { kind: 'story'; story: MapStoryListItem })
  | (ItemBase & { kind: 'tag'; tag: Tag });

const RawItemSchema = z.object({
  kind: z.enum(COLLECTION_ITEM_KINDS),
  note: z.string().nullable().catch(null).default(null),
  entity: CollectionEntitySchema.optional().catch(undefined),
  chronicle: CollectionChronicleSchema.optional().catch(undefined),
  story: MapStoryListItemSchema.optional().catch(undefined),
  tag: TagSchema.optional().catch(undefined),
});

/** One raw item → a typed item, or null when its kind's payload is missing. */
export function toCollectionItem(raw: unknown): CollectionItem | null {
  const parsed = RawItemSchema.safeParse(raw);
  if (!parsed.success) return null;
  const { kind, note, entity, chronicle, story, tag } = parsed.data;
  switch (kind) {
    case 'entity':
      return entity ? { kind, note, entity } : null;
    case 'chronicle':
      return chronicle ? { kind, note, chronicle } : null;
    case 'story':
      return story ? { kind, note, story } : null;
    case 'tag':
      return tag ? { kind, note, tag } : null;
  }
}

const ItemsSchema = z
  .array(z.unknown())
  .catch([])
  .default([])
  .transform((list) => list.map(toCollectionItem).filter((i): i is CollectionItem => i !== null));

/** GET /collections/{slug} — the summary plus its resolved, ordered items. */
export const CollectionSchema = CollectionSummarySchema.extend({
  items: ItemsSchema,
});
export type Collection = z.infer<typeof CollectionSchema>;
