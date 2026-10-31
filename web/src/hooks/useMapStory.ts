import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';
import { mapStory } from '@/lib/api/map-stories';
import { chronicleStepIndex } from '@/lib/map-story/steps';
import { qk } from '@/lib/query/queryKeys';
import type { MapStoryDocument } from '@/lib/schemas/map-story';
import { useChronicle } from './useChronicle';
import { useChronicleNav } from './useChronicleNav';
import { useStoryNav } from './useStoryNav';

/** A map story's whole document. Stories are static content: cache forever. */
export function useMapStory(slug: string | null) {
  return useQuery({
    queryKey: qk.mapStory(slug ?? '∅'),
    queryFn: ({ signal }) => mapStory(slug as string, signal),
    enabled: slug !== null,
    staleTime: Infinity,
  });
}

/** The story the map draws, and which of its steps. */
export interface ActiveStory {
  doc: MapStoryDocument;
  /** `story`: played on its own (URL `story` + `sstep`); `chronicle`: the map
   *  layer of the chronicle playing (URL `chron` + `step`). */
  mode: 'story' | 'chronicle';
  /** The step to draw; null when the chronicle's entry has no step (draw nothing). */
  index: number | null;
}

/**
 * The story on the map: the `?story=` one, else the map layer of the active
 * chronicle (its `map_story`), at the step for the current entry.
 */
export function useActiveStory(): ActiveStory | null {
  const { story, step } = useStoryNav();
  const { chron, step: chronStep } = useChronicleNav();
  const { data: chronicle } = useChronicle(story ? null : chron);
  const layer = !story && chron && chronicle ? (chronicle.map_story?.slug ?? null) : null;
  const slug = story ?? layer;
  const { data } = useMapStory(slug);
  const doc = slug && data?.slug === slug ? data.document : null;
  const entry = layer ? chronicle?.entries[chronStep] : undefined;

  return useMemo(() => {
    if (!doc) return null;
    if (story) return { doc, mode: 'story', index: Math.min(Math.max(step, 0), doc.steps.length - 1) };
    const index = chronicleStepIndex(doc, entry);
    return { doc, mode: 'chronicle', index: index >= 0 ? index : null };
  }, [doc, story, step, entry]);
}
