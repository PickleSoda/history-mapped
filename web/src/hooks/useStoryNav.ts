import { useQueryStates } from 'nuqs';
import { useCallback } from 'react';
import { PREVIEW } from '@/lib/map-story/preview';
import { parseAsChronicle, parseAsFull, parseAsStep, parseAsStory, parseAsStoryStep } from '@/lib/url/params';
import { useSelection } from './useSelection';

/**
 * Map-story (battle map) navigation <-> URL `story` + `sstep`, written with
 * `push` so the back button walks steps backward and then leaves the story.
 * A story takes the same place as a chronicle tour, so entering one closes
 * the tour, the open entity and any full page (the map has to be visible).
 * In the admin's preview (`?preview=1`) steps replace the history entry instead.
 */
export function useStoryNav() {
  const [{ story, sstep }, set] = useQueryStates(
    {
      story: parseAsStory,
      sstep: parseAsStoryStep.withDefault(0),
      chron: parseAsChronicle,
      step: parseAsStep,
      full: parseAsFull,
    },
    { history: PREVIEW ? 'replace' : 'push' },
  );
  const { clear: clearSelection } = useSelection();

  const enter = useCallback(
    (slug: string, at = 0) => {
      clearSelection();
      void set({ story: slug, sstep: at, chron: null, step: null, full: null });
    },
    [set, clearSelection],
  );
  const exit = useCallback(() => void set({ story: null, sstep: null }), [set]);
  const goto = useCallback((index: number) => void set({ sstep: Math.max(0, index) }), [set]);
  const next = useCallback(() => void set((p) => ({ sstep: (p.sstep ?? 0) + 1 })), [set]);
  const prev = useCallback(() => void set((p) => ({ sstep: Math.max(0, (p.sstep ?? 0) - 1) })), [set]);

  return { story, step: sstep, isActive: story !== null, enter, exit, goto, next, prev };
}
