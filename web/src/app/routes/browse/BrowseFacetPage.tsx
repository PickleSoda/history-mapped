import { useParams } from 'react-router-dom';
import { PagePlaceholder } from '../site/PagePlaceholder';

/** `/browse/:facet/:tag` (spec D4). Skeleton; track D replaces it. */
export function BrowseFacetPage() {
  const { facet = '', tag = '' } = useParams();
  return <PagePlaceholder title={`${facet} / ${tag}`} />;
}
