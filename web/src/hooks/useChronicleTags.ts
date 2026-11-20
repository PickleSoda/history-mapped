import { useQueryState, useQueryStates } from 'nuqs';
import { useCallback, useState } from 'react';
import { create } from 'zustand';
import {
  parseAsBrowseTab,
  parseAsChronicle,
  parseAsChronicleTags,
  parseAsFull,
  parseAsSelection,
} from '@/lib/url/params';
import type { BrowseTab } from '@/lib/url/params';
import { useEphemeralStore } from '@/stores/ephemeral';

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

export type { BrowseTab };

const tabParam = parseAsBrowseTab.withOptions({ history: 'replace' });

/**
 * The last request to show a tab made from outside the list
 * (`useOpenBrowseTab`). A new object each time, so asking for the tab that is
 * already showing still counts: it is what expands a collapsed sidebar.
 */
const useTabRequest = create<{ request: { tab: BrowseTab } | null }>()(() => ({ request: null }));

/**
 * The sidebar/sheet list tab, kept in URL `tab` (absent: entities) so a link
 * can open one and it survives the sidebar's unmount while a chronicle or a
 * battle map plays.
 *
 * It follows three things set from elsewhere, running `onFollow` each time
 * (e.g. to expand a collapsed sidebar; call it only to update the calling
 * component's own state): the chronicle tag filter `ct` (a tag clicked on an
 * entity page, a shared link) opens Chronicles, a request from another
 * component (`useOpenBrowseTab`) opens the tab it names, and a `tab` that
 * arrives in the URL (a link, Back) opens that tab.
 */
export function useBrowseTab(onFollow?: () => void) {
  const { tags } = useChronicleTags();
  const [param, setParam] = useQueryState('tab', tabParam);
  const request = useTabRequest((s) => s.request);
  const key = tags.join(',');
  const [tab, setTabState] = useState<BrowseTab>(key ? 'chronicles' : (param ?? 'entities'));
  const [seen, setSeen] = useState(key);
  const [seenParam, setSeenParam] = useState(param);
  const [seenRequest, setSeenRequest] = useState(request);
  // Adjust during render (not in an effect) when any of them changes.
  if (key !== seen) {
    setSeen(key);
    if (key) {
      setTabState('chronicles');
      onFollow?.();
    }
  }
  if (request !== seenRequest) {
    setSeenRequest(request);
    if (request) {
      setTabState(request.tab);
      onFollow?.();
    }
  } else if (param !== seenParam && param && param !== tab) {
    setTabState(param);
    onFollow?.();
  }
  if (param !== seenParam) setSeenParam(param);
  const setTab = useCallback(
    (next: BrowseTab) => {
      setTabState(next);
      void setParam(next === 'entities' ? null : next);
    },
    [setParam],
  );
  return [tab, setTab] as const;
}

/**
 * Open a sidebar/sheet list tab from anywhere in the atlas (a card, the map):
 * the mounted list follows the request (`useBrowseTab`), URL `tab` is written
 * for a list that mounts later, and a peeking sheet is lifted.
 */
export function useOpenBrowseTab() {
  const [, setParam] = useQueryState('tab', tabParam);
  return useCallback(
    (tab: BrowseTab) => {
      useTabRequest.setState({ request: { tab } });
      void setParam(tab === 'entities' ? null : tab);
      // On a phone the list lives in the sheet: lift it if it is only peeking.
      const { sheet, setSheet } = useEphemeralStore.getState();
      if (sheet === 'peek') setSheet('half');
    },
    [setParam],
  );
}
