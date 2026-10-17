import { useQueryState, useQueryStates } from 'nuqs';
import { useCallback, useState } from 'react';
import {
  parseAsChronicle,
  parseAsChronicleTags,
  parseAsFull,
  parseAsSelection,
} from '@/lib/url/params';

/**
 * Chronicles-tab tag filter <-> URL `ct`, so a filtered list is shareable and
 * survives back/forward. Written with `replace` (a refinement, not a place).
 */
export function useChronicleTags() {
  const [tags, setTags] = useQueryState(
    'ct',
    parseAsChronicleTags.withDefault([]).withOptions({ history: 'replace' }),
  );
  return { tags, setTags };
}

/**
 * "Show chronicles tagged X" from anywhere (an entity page, a chronicle page):
 * leave the current page/tour and land on the filtered Chronicles tab. Pushes
 * history, so Back returns to where the tag was clicked.
 */
export function useShowChroniclesTagged() {
  const [, set] = useQueryStates(
    { ct: parseAsChronicleTags, sel: parseAsSelection, chron: parseAsChronicle, full: parseAsFull },
    { history: 'push' },
  );
  return useCallback(
    (slug: string) => set({ ct: [slug], sel: null, chron: null, full: null }),
    [set],
  );
}

export type BrowseTab = 'entities' | 'chronicles';

/**
 * The sidebar/sheet list tab. Follows `ct`: whenever the chronicle tag filter
 * is set from elsewhere (a tag clicked on an entity page, a shared link), the
 * Chronicles tab opens (and `onFollow` runs, e.g. to expand a collapsed
 * sidebar). Call `onFollow` only to update the calling component's own state.
 */
export function useBrowseTab(onFollow?: () => void) {
  const { tags } = useChronicleTags();
  const key = tags.join(',');
  const [tab, setTab] = useState<BrowseTab>(key ? 'chronicles' : 'entities');
  const [seen, setSeen] = useState(key);
  // Adjust during render (not in an effect) when the filter changes.
  if (key !== seen) {
    setSeen(key);
    if (key) {
      setTab('chronicles');
      onFollow?.();
    }
  }
  return [tab, setTab] as const;
}
