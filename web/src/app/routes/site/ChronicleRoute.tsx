import { useParams, useSearchParams } from 'react-router-dom';
import { ChroniclePage } from '@/components/atlas/ChroniclePage';
import { LinkModeProvider } from '@/components/atlas/link-mode';
import { useChronicle } from '@/hooks';
import { errorStatus } from '@/lib/api';
import { yearSpanText } from '@/lib/chronicle-page';
import { useDocumentMeta } from '@/lib/document-meta';
import type { Chronicle } from '@/lib/schemas/chronicle';
import { parseStepParam } from '@/lib/site-links';
import { NotFoundContent } from './NotFoundPage';
import { SiteBreadcrumb } from './SiteBreadcrumb';

/** The chronicle's description, else one generated line. */
function describe(c: Chronicle): string {
  if (c.description?.trim()) return c.description;
  const span = yearSpanText(c.start_year, c.end_year);
  return `${c.title}: a chronicle in ${c.entries.length} steps${span ? `, ${span}` : ''}, on History Mapped.`;
}

/**
 * Standalone chronicle page, `/chronicles/:slug` (spec D3): the atlas's
 * chronicle page in its `site` variant, with site link mode. `?step=n`
 * (0-based, like the atlas `step`) opens it with that step selected; the page
 * never writes it back.
 */
export function ChronicleRoute() {
  const { slug = '' } = useParams();
  const [params] = useSearchParams();
  const step = parseStepParam(params.get('step'));
  const { data: chronicle, error } = useChronicle(slug || null);
  const notFound = !slug || errorStatus(error) === 404;

  useDocumentMeta({
    title: notFound ? 'Chronicle not found' : (chronicle?.title ?? null),
    description: chronicle ? describe(chronicle) : null,
  });

  if (notFound) {
    return (
      <NotFoundContent title="Chronicle not found">
        There is no chronicle at this address. The link may be mistyped, or the chronicle may have been
        renamed.
      </NotFoundContent>
    );
  }

  return (
    <LinkModeProvider mode="site">
      <ChroniclePage
        // A new chronicle or step is a new page (the step is read on mount).
        key={`${slug}?${step ?? ''}`}
        id={slug}
        variant="site"
        step={step}
        lead={
          <SiteBreadcrumb items={[{ label: 'Browse', to: '/browse' }, { label: chronicle?.title ?? 'Chronicle' }]} />
        }
      />
    </LinkModeProvider>
  );
}
