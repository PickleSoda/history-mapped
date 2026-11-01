import { useParams } from 'react-router-dom';
import { PagePlaceholder } from '../site/PagePlaceholder';

/** `/browse/collections/:slug` (spec D4). Skeleton; track D replaces it. */
export function CollectionPage() {
  const { slug = '' } = useParams();
  return <PagePlaceholder title="Collection" note={slug} />;
}
