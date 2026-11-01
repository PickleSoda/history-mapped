import { useParams } from 'react-router-dom';
import { EntityPage } from '@/components/atlas/EntityPage';
import { LinkModeProvider } from '@/components/atlas/link-mode';
import { useEntity } from '@/hooks';
import { errorStatus } from '@/lib/api';
import { useDocumentMeta } from '@/lib/document-meta';
import { isEntityId } from '@/lib/site-links';
import { NotFoundContent } from './NotFoundPage';
import { SiteBreadcrumb } from './SiteBreadcrumb';

/**
 * Standalone entity page, `/entities/:id` (spec D3): the atlas's entity page
 * in its `site` variant, with site link mode (its links open site pages, or
 * the globe for what needs the map) and an "Open on the globe" link. An id
 * that isn't a UUID, or a 404, is a not-found page.
 */
export function EntityRoute() {
  const { id = '' } = useParams();
  const valid = isEntityId(id);
  const { data: entity, error } = useEntity(valid ? id : null);
  const notFound = !valid || errorStatus(error) === 404;

  useDocumentMeta({
    title: notFound ? 'Entity not found' : (entity?.name ?? null),
    description: entity ? (entity.summary ?? entity.description ?? entity.significance) : null,
  });

  if (notFound) {
    return (
      <NotFoundContent title="Entity not found">
        There is no entity at this address. It may have been merged into another one, or the link may be
        mistyped.
      </NotFoundContent>
    );
  }

  return (
    <LinkModeProvider mode="site">
      <EntityPage
        key={id}
        id={id}
        variant="site"
        lead={<SiteBreadcrumb items={[{ label: 'Browse', to: '/browse' }, { label: entity?.name ?? 'Entity' }]} />}
      />
    </LinkModeProvider>
  );
}
