/**
 * The single source of truth for query keys (spec §4).
 *
 * Never hand-write a key array at a call site — always go through `qk` so
 * invalidation and prefetch line up. TanStack hashes object/array keys
 * deterministically, so passing the snapped `Scope` is stable.
 */
import type { EntitiesByTagsParams } from '@/lib/api/browse';
import type { ChronicleListParams } from '@/lib/api/chronicles';
import type { MyContributionsParams } from '@/lib/api/contributions';
import type { MapFocusTarget } from '@/lib/api/entities';
import type { ChronicleGraphParams, EntityGraphParams } from '@/lib/api/graph';
import type { MapStoryListParams } from '@/lib/api/map-stories';
import type { ListOptions, MapLayer } from '@/lib/api/params';
import type { StarListParams } from '@/lib/api/saved';
import type { EntityGroup, Scope } from '@/types/atlas';

export const qk = {
  /** Map FeatureCollection (pins/borders), one layer of the scope. */
  entitiesInView: (scope: Scope, layer: MapLayer) =>
    [
      'entities',
      'map',
      layer,
      scope.z,
      layer === 'core' ? scope.core : scope.outer,
      scope.time,
      scope.groups,
    ] as const,
  /** Map points of a focused set (an entity's relations, or a search word). */
  mapFocus: (target: MapFocusTarget, groups: EntityGroup[]) =>
    ['entities', 'map-focus', target, groups] as const,
  /** Ranked "notable here" list (paginated); with `search`, the matches
   *  anywhere and at any time, so the view and the year are left out. */
  entityList: (scope: Scope, opts: ListOptions) =>
    opts.search
      ? (['entities', 'list', 'search', opts.search, scope.groups, opts.sort, opts.page] as const)
      : (['entities', 'list', scope.bbox, scope.time, scope.groups, opts.sort, opts.page] as const),
  entity: (id: string) => ['entity', id] as const,
  connections: (id: string) => ['entity', id, 'connections'] as const,
  /** Derived timeline rows (GET /entities/{id}/timeline). */
  entityTimeline: (id: string) => ['entity', id, 'timeline'] as const,
  /** Relation graph around an entity. Pass NORMALISED params (see
   *  `normaliseEntityGraphParams`) so the "expand node" fetch and the entity
   *  page share one cache entry. */
  entityGraph: (id: string, params: EntityGraphParams) =>
    ['entity', id, 'graph', params] as const,
  chronicle: (slug: string) => ['chronicle', slug] as const,
  /** Where a chronicle's entities sit on the map (GET /chronicles/{slug}/places). */
  chroniclePlaces: (slug: string) => ['chronicle', slug, 'places'] as const,
  /** A step-by-step battle map (GET /map-stories/{slug}). */
  mapStory: (slug: string) => ['map-story', slug] as const,
  /** Filtered Chronicles-tab listing (pages are the infinite query's). */
  chronicleList: (params: Omit<ChronicleListParams, 'page'>) =>
    ['chronicles', 'list', params] as const,
  /** Tag vocabulary (GET /tags). */
  tags: () => ['tags'] as const,
  /** Whole-chronicle relation graph (params normalised, as above). */
  chronicleGraph: (slug: string, params: ChronicleGraphParams) =>
    ['chronicle', slug, 'graph', params] as const,
  /** Public historical-periods reference list (timeline gantt). */

  // ── Discover: on this day, meanwhile, the daily expedition, for you.
  onThisDay: (date: string) => ['discover', 'on-this-day', date] as const,
  meanwhile: (year: number) => ['discover', 'meanwhile', year] as const,
  dailyQuest: (date: string) => ['discover', 'quest', date] as const,
  forYou: (ids: string[]) => ['discover', 'for-you', ids] as const,

  // ── Browse (public site): curated sets, the story index, tag listings.
  /** Every published curated set (GET /collections). */
  collections: () => ['collections'] as const,
  /** One curated set with its resolved items (GET /collections/{slug}). */
  collection: (slug: string) => ['collections', slug] as const,
  /** Story index (GET /map-stories); pages are the infinite query's. */
  mapStoryList: (params: Omit<MapStoryListParams, 'page'>) => ['map-stories', 'list', params] as const,
  /** Everything carrying the tags (GET /entities?tags=), not scoped to the map;
   *  pages are the infinite query's. */
  entitiesByTags: (params: Omit<EntitiesByTagsParams, 'page'>) =>
    ['entities', 'by-tags', params] as const,

  // ── Personal (signed-in) data — everything under the `me` root, so sign-out
  //    can drop it in one `removeQueries({ queryKey: qk.personal() })`.
  personal: () => ['me'] as const,
  /** The signed-in user (null = guest). */
  me: () => ['me', 'profile'] as const,
  /** Every star + folder query (keys and lists). */
  stars: () => ['me', 'stars'] as const,
  starKeys: () => ['me', 'stars', 'keys'] as const,
  starList: (params: StarListParams) => ['me', 'stars', 'list', params] as const,
  folders: () => ['me', 'folders'] as const,
  /** Every page of the user's own contributions. */
  contributions: () => ['me', 'contributions'] as const,
  myContributions: (params: MyContributionsParams) =>
    ['me', 'contributions', params] as const,
  /** "Talk with people": every talk query, the sidebar list, one conversation. */
  talk: () => ['me', 'talk'] as const,
  talkList: () => ['me', 'talk', 'list'] as const,
  talkConversation: (entityId: string) => ['me', 'talk', 'with', entityId] as const,
};
