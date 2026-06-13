import { useQueryState } from 'nuqs';
import { parseAsView } from '@/lib/url/params';

/** Map vs globe projection <-> URL `view`. Written with `replace`. */
export function useView() {
  const [view, setView] = useQueryState(
    'view',
    parseAsView.withDefault('map').withOptions({ history: 'replace' }),
  );
  return { view, setView };
}
