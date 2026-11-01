import { useParams } from 'react-router-dom';
import { PagePlaceholder } from '../site/PagePlaceholder';

/** `/docs` and `/docs/:slug` (spec D5). Skeleton; track C replaces it. */
export function DocPage() {
  const { slug = 'index' } = useParams();
  return <PagePlaceholder title="Docs" note={slug} />;
}
