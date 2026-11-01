/**
 * Loads a published doc's markdown. The sources are bundled at build time as
 * lazy `?raw` chunks, one per file; a chunk is fetched only when its page is
 * opened.
 *
 * The glob lists the manifest's paths one by one instead of `docs/**\/*.md`:
 * every file a glob matches is emitted into the public build (and the service
 * worker's precache), unpublished runbooks and plans included, whether or not
 * the manifest ever loads it.
 */
import type { DocEntry } from '@/content/docs/manifest';
import { docTitle, findDoc, tocFromMarkdown } from './docs';
import type { TocItem } from './docs';

const SOURCES = import.meta.glob<string>(
  [
    '../../../../docs/README.md',
    '../../../../docs/architecture/system-overview.md',
    '../../../../docs/architecture/frontend-app.md',
    '../../../../docs/architecture/data-pipeline.md',
    '../../../../docs/architecture/ohm-integration.md',
    '../../../../docs/architecture/tags.md',
    '../../../../docs/architecture/entity-images.md',
    '../../../../docs/architecture/admin-map-editor.md',
    '../../../../docs/entity-model/entity-specification.md',
    '../../../../docs/entity-model/for-historians.md',
    '../../../../docs/entity-model/diagrams.md',
    '../../../../docs/implementation-docs/setup.md',
    '../../../../docs/implementation-docs/data-contributor-guide.md',
    '../../../../docs/implementation-docs/map-story-authoring.md',
  ],
  { query: '?raw', import: 'default' },
);

const PREFIX = '../../../../';

/** Repo-relative paths of the bundled sources (for the manifest sync test). */
export function bundledDocPaths(): string[] {
  return Object.keys(SOURCES).map((key) => key.slice(PREFIX.length));
}

export interface LoadedDoc {
  entry: DocEntry;
  markdown: string;
  /** The doc's own H1, else the manifest title. */
  title: string;
  toc: TocItem[];
}

/** The doc for a slug, or null when the slug is not in the manifest. */
export async function loadDoc(slug: string): Promise<LoadedDoc | null> {
  const entry = findDoc(slug);
  if (!entry) return null;
  const load = SOURCES[PREFIX + entry.path];
  if (!load) throw new Error(`Doc source not bundled: ${entry.path}`);
  const markdown = await load();
  return { entry, markdown, title: docTitle(markdown) ?? entry.title, toc: tocFromMarkdown(markdown) };
}
