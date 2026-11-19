/**
 * The published docs (spec 2026-11-01 public site, D5): which markdown files
 * under the repo's `docs/` appear at `/docs`, under which section, in which
 * order. `path` is relative to the repo root. Runbooks, plans and the archive
 * stay unpublished: a file is public only if it is listed here.
 *
 * Sections run from the broad picture to the detail (start here → domain
 * guides → architecture → data model → features → guides → reference), and
 * pages within a section by priority, so reading top to bottom works.
 *
 * Adding a page: add an entry below AND its path to the `import.meta.glob`
 * list in `lib/docs/load.ts` (the glob must be a literal; a test keeps the
 * two in sync and checks every path exists).
 */

export type DocSectionId = 'start' | 'domain' | 'architecture' | 'data-model' | 'features' | 'guides' | 'reference';

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
  { id: 'start', title: 'Start here' },
  { id: 'domain', title: 'Domain guides' },
  { id: 'architecture', title: 'Architecture' },
  { id: 'data-model', title: 'Data model' },
  { id: 'features', title: 'Features' },
  { id: 'guides', title: 'Guides' },
  { id: 'reference', title: 'Reference' },
];

/** In reading order: the sidebar, previous / next links and the index follow it. */
export const DOC_PAGES: readonly DocEntry[] = [
  // ── Start here ────────────────────────────────────────────────────────────
  {
    slug: DOCS_INDEX_SLUG,
    title: 'Documentation',
    section: 'start',
    path: 'docs/README.md',
    description: 'The History Mapped documentation: where to start for developers, historians, geographers and business readers.',
  },
  {
    slug: 'product-overview',
    title: 'What is History Mapped?',
    section: 'start',
    path: 'docs/overview/product-overview.md',
    description: 'What History Mapped does, who it serves, how its content is made and where it is going.',
  },
  {
    slug: 'concepts',
    title: 'Core concepts',
    section: 'start',
    path: 'docs/overview/concepts.md',
    description: 'Entities, relationships, chronicles, map stories, geometry periods, tags and the other ideas the atlas is built from.',
  },
  // ── Domain guides ─────────────────────────────────────────────────────────
  {
    slug: 'for-historians',
    title: 'For historians',
    section: 'domain',
    path: 'docs/entity-model/for-historians.md',
    description: 'How historical knowledge is modelled: entities, dates and uncertainty, relationships, chronicles, sources and confidence.',
  },
  {
    slug: 'for-geographers',
    title: 'For geographers',
    section: 'domain',
    path: 'docs/entity-model/for-geodata-contributors.md',
    description: 'How places, borders and their change over time are stored and drawn: points, OHM territories, CRS and placement rules.',
  },
  // ── Architecture ──────────────────────────────────────────────────────────
  {
    slug: 'system-overview',
    title: 'System overview',
    section: 'architecture',
    path: 'docs/architecture/system-overview.md',
    description: 'The parts of History Mapped (public app, API and admin, database, tiles, pipeline) and how they fit together.',
  },
  {
    slug: 'data-pipeline',
    title: 'Data pipeline',
    section: 'architecture',
    path: 'docs/architecture/data-pipeline.md',
    description: 'How content flows from Wikidata, Wikipedia, OpenHistoricalMap and AI agents through the pipeline into the database.',
  },
  {
    slug: 'backend',
    title: 'Backend and API',
    section: 'architecture',
    path: 'docs/architecture/backend.md',
    description: 'The Laravel application: API and admin routes, layering, auth and roles, jobs, scheduler and commands.',
  },
  {
    slug: 'frontend-app',
    title: 'Public web app',
    section: 'architecture',
    path: 'docs/architecture/frontend-app.md',
    description: 'Architecture of the public React app: routes, URL state, data fetching, the atlas map, timeline and pages.',
  },
  {
    slug: 'ohm-integration',
    title: 'Maps, tiles and OHM',
    section: 'architecture',
    path: 'docs/architecture/ohm-integration.md',
    description: 'How the map is composed: the OpenHistoricalMap basemap, our vector tiles, date filtering and OHM correlation.',
  },
  {
    slug: 'admin-map-editor',
    title: 'Admin and editing',
    section: 'architecture',
    path: 'docs/architecture/admin-map-editor.md',
    description: 'The editorial back office: entity and geometry editing, the AI assistant, contributions review and the map-story editor.',
  },
  {
    slug: 'deployment',
    title: 'Deployment and operations',
    section: 'architecture',
    path: 'docs/architecture/deployment.md',
    description: 'How History Mapped is hosted and shipped: the production topology, CI/CD, environments and content operations.',
  },
  {
    slug: 'scalability',
    title: 'Scalability benchmark',
    section: 'architecture',
    path: 'docs/architecture/scalability.md',
    description: 'How request times change as the atlas grows from 36k to 2.6M entities, on four server sizes, calibrated against the live droplet.',
  },
  // ── Data model ────────────────────────────────────────────────────────────
  {
    slug: 'data-model',
    title: 'Data model overview',
    section: 'data-model',
    path: 'docs/entity-model/README.md',
    description: 'The database behind the atlas: ER and class diagrams, the time model and the geometry model.',
  },
  {
    slug: 'entity-specification',
    title: 'Entity types',
    section: 'data-model',
    path: 'docs/entity-model/entity-specification.md',
    description: 'The canonical entity model: 30 entity types in 5 groups, their enums and type-specific attributes.',
  },
  {
    slug: 'relationships',
    title: 'Relationship types',
    section: 'data-model',
    path: 'docs/entity-model/relationships.md',
    description: 'Every relationship type between entities, by category, with direction, examples, time windows and confidence.',
  },
  // ── Features ──────────────────────────────────────────────────────────────
  {
    slug: 'chronicles',
    title: 'Chronicles',
    section: 'features',
    path: 'docs/architecture/chronicles.md',
    description: 'Guided historical tours: how chronicles are modelled, produced by the pipeline, served and played in the atlas.',
  },
  {
    slug: 'map-stories',
    title: 'Map stories',
    section: 'features',
    path: 'docs/architecture/map-stories.md',
    description: 'Battle maps and other step-by-step map stories: the document format, how they are built, stored and played.',
  },
  {
    slug: 'tags',
    title: 'Tags',
    section: 'features',
    path: 'docs/architecture/tags.md',
    description: 'The faceted tag vocabulary (era, region, theme, type) used to find chronicles and entities.',
  },
  {
    slug: 'mcp-connector',
    title: 'MCP connector',
    section: 'features',
    path: 'docs/architecture/mcp-connector.md',
    description: 'Connect Claude or another MCP host to the atlas: read tools, inline cards and maps, limits, and local testing.',
  },
  {
    slug: 'collections',
    title: 'Collections',
    section: 'features',
    path: 'docs/schemas/collections.md',
    description: 'Curated sets of entities, chronicles and map stories: the file format, the sync command and the API.',
  },
  {
    slug: 'entity-images',
    title: 'Entity images',
    section: 'features',
    path: 'docs/architecture/entity-images.md',
    description: 'How entities link freely licensed Wikimedia Commons images and display their credits, without copying them.',
  },
  // ── Guides ────────────────────────────────────────────────────────────────
  {
    slug: 'setup',
    title: 'Local setup',
    section: 'guides',
    path: 'docs/implementation-docs/setup.md',
    description: 'Running the History Mapped monorepo locally with Docker Compose: services, URLs and common commands.',
  },
  {
    slug: 'data-contributor-guide',
    title: 'Importing data',
    section: 'guides',
    path: 'docs/implementation-docs/data-contributor-guide.md',
    description: 'Running the pipeline, importing its output into the app and checking the result, for data contributors.',
  },
  {
    slug: 'map-story-authoring',
    title: 'Authoring map stories',
    section: 'guides',
    path: 'docs/implementation-docs/map-story-authoring.md',
    description: 'Authoring map stories: step-by-step battle maps with formations, movements and narrative on the atlas.',
  },
  // ── Reference ─────────────────────────────────────────────────────────────
  {
    slug: 'api',
    title: 'REST API',
    section: 'reference',
    path: 'docs/schemas/rest-api.md',
    description: 'The public JSON API under /api/v1: endpoint groups, authentication, conventions and the generated OpenAPI docs.',
  },
  {
    slug: 'atlas-tiles',
    title: 'Atlas vector tiles',
    section: 'reference',
    path: 'docs/schemas/atlas-tiles.md',
    description: 'The atlas_entities vector-tile contract: endpoints, layer properties, the decimal-date rule and the OHM link.',
  },
  {
    slug: 'relation-graph-api',
    title: 'Relation graph API',
    section: 'reference',
    path: 'docs/schemas/relation-graph-api.md',
    description: 'Response contracts of the entity and chronicle relation-graph endpoints used by the graph view.',
  },
  {
    slug: 'pipeline-entity-record',
    title: 'Pipeline entity record',
    section: 'reference',
    path: 'docs/schemas/pipeline-entity-record.md',
    description: 'The JSONL entity record the pipeline writes and pipeline:import reads.',
  },
  {
    slug: 'content-bundle',
    title: 'Content bundles',
    section: 'reference',
    path: 'docs/schemas/content-bundle.md',
    description: 'The content bundle format for exporting, editing and validating site content as JSONL.',
  },
];
