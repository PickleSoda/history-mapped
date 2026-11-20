import { useEffect } from 'react';
import { useSearchFilter, useSelection } from '@/hooks';
import { recordRecentEntity, recordRecentSearch } from '@/lib/discover/recents';

/**
 * Mounted once for the whole atlas session (AtlasLayout), whichever shell or
 * sidebar tab shows. Renders nothing: it only records what this browser opens
 * and searches, for the "For you" suggestions.
 *
 * An entity counts as opened when it becomes the selection (a click on the
 * map or a list, a link that arrives with `sel`); a search counts when its
 * word is kept as the filter (`q`). Both stay in this browser
 * (`lib/discover/recents`).
 */
export function DiscoverRuntime() {
  const { sel } = useSelection();
  const { q } = useSearchFilter();

  useEffect(() => {
    if (sel) recordRecentEntity(sel);
  }, [sel]);

  useEffect(() => {
    if (q) recordRecentSearch(q);
  }, [q]);

  return null;
}
