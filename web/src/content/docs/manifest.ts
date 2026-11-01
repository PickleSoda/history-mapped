/**
 * The published docs (spec 2026-11-01 public site, D5): which markdown files
 * under the repo's `docs/` appear at `/docs`, under which section, in which
 * order. `path` is relative to the repo root. Runbooks, plans and the archive
 * stay unpublished: a file is public only if it is listed here.
 *
 * Adding a page: add an entry below AND its path to the `import.meta.glob`
 * list in `lib/docs/load.ts` (the glob must be a literal; a test keeps the
 * two in sync and checks every path exists).
 */

export type DocSectionId = 'overview' | 'architecture' | 'data-model' | 'guides' | 'contracts';

export interface DocSection {
  id: DocSectionId;
  title: string;
}

export interface DocEntry {
  /** URL segment: `/docs/<slug>`. The index page is served at `/docs`. */
  slug: string;
  /** Sidebar label and document title. */
  title: string;
  section: DocSectionId;
  /** Markdown source, relative to the repo root. */
  path: string;
  /** One sentence for the meta description. */
  description: string;
}

/** Slug of the page rendered at `/docs`. */
export const DOCS_INDEX_SLUG = 'index';

export const DOC_SECTIONS: readonly DocSection[] = [
  { id: 'overview', title: 'Overview' },
  { id: 'architecture', title: 'Architecture' },
  { id: 'data-model', title: 'Data model' },
  { id: 'guides', title: 'Guides' },
  { id: 'contracts', title: 'Contracts' },
];

/** In reading order: the sidebar, previous / next links and the index follow it. */
export const DOC_PAGES: readonly DocEntry[] = [
  {
    slug: DOCS_INDEX_SLUG,
    title: 'Documentation',
    section: 'overview',
    path: 'docs/README.md',
    description: 'How History Mapped is built and documented: architecture, data model, guides and contracts.',
  },
  {
    slug: 'system-overview',
    title: 'System overview',
    section: 'overview',
    path: 'docs/architecture/system-overview.md',
    description: 'The runtime surfaces of History Mapped (API, admin, public atlas, data pipeline) and how they fit together.',
  },
  {
    slug: 'frontend-app',
    title: 'Frontend app',
    section: 'architecture',
    path: 'docs/architecture/frontend-app.md',
    description: 'Architecture of the public atlas: the React single-page app, its URL state, map, timeline and data fetching.',
  },
  {
    slug: 'data-pipeline',
    title: 'Data pipeline',
    section: 'architecture',
    path: 'docs/architecture/data-pipeline.md',
    description: 'How historical data flows from Wikidata, Wikipedia and OpenHistoricalMap through the pipeline into the database.',
  },
  {
    slug: 'ohm-integration',
    title: 'OpenHistoricalMap',
    section: 'architecture',
    path: 'docs/architecture/ohm-integration.md',
    description: 'Integrating OpenHistoricalMap vector tiles with MapLibre: date filtering, styling and custom overlays.',
  },
  {
    slug: 'tags',
    title: 'Tags',
    section: 'architecture',
    path: 'docs/architecture/tags.md',
    description: 'The faceted tag vocabulary (era, region, theme, type) used to find chronicles and entities.',
  },
  {
    slug: 'entity-images',
    title: 'Entity images',
    section: 'architecture',
    path: 'docs/architecture/entity-images.md',
    description: 'How entities link freely licensed Wikimedia Commons images and display their credits, without copying them.',
  },
  {
    slug: 'admin-map-editor',
    title: 'Admin map editor',
    section: 'architecture',
    path: 'docs/architecture/admin-map-editor.md',
    description: 'The admin entity editor and map UI used to author and correct entities and their geometry.',
  },
  {
    slug: 'entity-specification',
    title: 'Entity specification',
    section: 'data-model',
    path: 'docs/entity-model/entity-specification.md',
    description: 'The canonical entity model: 30 entity types in 5 groups, their attributes, relationships and geometry.',
  },
  {
    slug: 'for-historians',
    title: 'For historians',
    section: 'data-model',
    path: 'docs/entity-model/for-historians.md',
    description: 'A guide for historians to how historical knowledge is structured in the database, with no technical background needed.',
  },
  {
    slug: 'diagrams',
    title: 'Diagrams',
    section: 'data-model',
    path: 'docs/entity-model/diagrams.md',
    description: 'Diagrams of the live entity model: the write model, relationships, chronicles and time-aware geometry.',
  },
  {
    slug: 'setup',
    title: 'Local setup',
    section: 'guides',
    path: 'docs/implementation-docs/setup.md',
    description: 'Running the History Mapped monorepo locally with Docker Compose: services, URLs and common commands.',
  },
  {
    slug: 'data-contributor-guide',
    title: 'Data contributor guide',
    section: 'guides',
    path: 'docs/implementation-docs/data-contributor-guide.md',
    description: 'Running the pipeline, importing data into the app and debugging issues, for data contributors.',
  },
  {
    slug: 'map-story-authoring',
    title: 'Map story authoring',
    section: 'guides',
    path: 'docs/implementation-docs/map-story-authoring.md',
    description: 'Authoring map stories: step-by-step battle maps with formations, movements and narrative on the atlas.',
  },
  {
    slug: 'atlas-tiles',
    title: 'Atlas vector tiles',
    section: 'contracts',
    path: 'docs/schemas/atlas-tiles.md',
    description: 'The atlas_entities vector-tile contract: endpoints, layer properties, the decimal-date rule and the OHM link.',
  },
];
