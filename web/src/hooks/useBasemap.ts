import { useQueryState } from 'nuqs';
import { parseAsBasemap } from '@/lib/url/params';

/** OHM basemap style <-> URL `base`. Written with `replace`. */
export function useBasemap() {
  const [basemap, setBasemap] = useQueryState(
    'base',
    parseAsBasemap.withDefault('woodblock').withOptions({ history: 'replace' }),
  );
  return { basemap, setBasemap };
}
