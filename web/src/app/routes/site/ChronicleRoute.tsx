import { useParams } from 'react-router-dom';
import { PagePlaceholder } from './PagePlaceholder';

/** Standalone chronicle page, `/chronicles/:slug` (spec D3). Skeleton; track B replaces it. */
export function ChronicleRoute() {
  const { slug = '' } = useParams();
  return <PagePlaceholder title="Chronicle" note={slug} />;
}
