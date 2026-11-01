import { useParams } from 'react-router-dom';
import { PagePlaceholder } from './PagePlaceholder';

/** Standalone entity page, `/entities/:id` (spec D3). Skeleton; track B replaces it. */
export function EntityRoute() {
  const { id = '' } = useParams();
  return <PagePlaceholder title="Entity" note={id} />;
}
