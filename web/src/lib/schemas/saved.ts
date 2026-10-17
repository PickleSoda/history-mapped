/** Zod schemas for the personal saved-items endpoints (stars + folders). */
import { z } from 'zod';
import { GroupFromApi } from './entity';

export const SAVEABLE_TYPES = ['entity', 'chronicle', 'relationship'] as const;
export const SaveableTypeSchema = z.enum(SAVEABLE_TYPES);
export type SaveableType = z.infer<typeof SaveableTypeSchema>;

/** One star, minimal — GET /me/stars/keys drives every star toggle's state. */
export const StarKeySchema = z.object({
  type: SaveableTypeSchema,
  id: z.string(),
  star_id: z.number(),
  folder_ids: z.array(z.number()).default([]),
});
export type StarKey = z.infer<typeof StarKeySchema>;

export const StarKeysSchema = z.object({ data: z.array(StarKeySchema) });

const EntityRefSchema = z.object({
  id: z.string(),
  name: z.string(),
  entity_type: z.string().nullable().default(null),
  entity_group: GroupFromApi,
});
export type EntityRef = z.infer<typeof EntityRefSchema>;

/** The starred record, summarised per type. */
export const SavedItemSchema = z.discriminatedUnion('type', [
  z.object({
    type: z.literal('entity'),
    id: z.string(),
    name: z.string(),
    entity_type: z.string().nullable().default(null),
    entity_group: GroupFromApi,
    summary: z.string().nullable().default(null),
  }),
  z.object({
    type: z.literal('chronicle'),
    id: z.string(),
    slug: z.string(),
    title: z.string(),
    start_year: z.number().nullable().default(null),
    end_year: z.number().nullable().default(null),
    entry_count: z.number().nullable().default(null),
  }),
  z.object({
    type: z.literal('relationship'),
    id: z.string(),
    relationship_type: z.string().nullable().default(null),
    description: z.string().nullable().default(null),
    source: EntityRefSchema.nullable().default(null),
    target: EntityRefSchema.nullable().default(null),
  }),
]);
export type SavedItem = z.infer<typeof SavedItemSchema>;

export const StarSchema = z.object({
  id: z.number(),
  type: SaveableTypeSchema,
  target_id: z.string(),
  folder_ids: z.array(z.number()).default([]),
  created_at: z.string().nullable().default(null),
  /** null = the starred record has since been deleted. */
  item: SavedItemSchema.nullable().catch(null),
});
export type Star = z.infer<typeof StarSchema>;

const PaginatorMetaSchema = z.object({
  current_page: z.number(),
  last_page: z.number(),
  per_page: z.number(),
  total: z.number(),
});

/** GET /me/stars — paginated, newest first. */
export const StarListSchema = z.object({
  data: z.array(StarSchema),
  meta: PaginatorMetaSchema,
});
export type StarList = z.infer<typeof StarListSchema>;

export const FolderSchema = z.object({
  id: z.number(),
  name: z.string(),
  description: z.string().nullable().default(null),
  /** `#rrggbb` or null. */
  color: z.string().nullable().default(null),
  stars_count: z.number().default(0),
  created_at: z.string().nullable().default(null),
  updated_at: z.string().nullable().default(null),
});
export type Folder = z.infer<typeof FolderSchema>;

export const FoldersSchema = z.object({ data: z.array(FolderSchema) });
