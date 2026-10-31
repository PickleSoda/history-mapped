import { Play, Swords } from 'lucide-react';
import { useStoryNav } from '@/hooks';
import type { MapStorySummary } from '@/lib/schemas/map-story';

/** "Battle map" / "Campaign map" for a story kind. */
export function storyKindLabel(kind: string): string {
  return kind === 'campaign' ? 'Campaign map' : 'Battle map';
}

/**
 * Prominent "play the battle map" buttons for an entity's stories — the way
 * into the step-by-step replay from the detail panel.
 */
export function StoryButtons({ stories }: { stories: MapStorySummary[] }) {
  const { enter } = useStoryNav();
  if (stories.length === 0) return null;
  return (
    <div className="mt-3 space-y-1.5">
      {stories.map((s) => (
        <button
          key={s.id}
          type="button"
          onClick={() => enter(s.slug)}
          className="group flex w-full items-center gap-3 rounded-xl border border-amber-700/30 bg-gradient-to-r from-amber-50 to-orange-50 px-3 py-2.5 text-left shadow-sm transition hover:border-amber-700/60 hover:shadow dark:from-amber-950/60 dark:to-orange-950/40"
        >
          <span className="grid size-9 flex-none place-items-center rounded-lg bg-amber-700 text-white shadow-sm">
            <Swords size={18} />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-[13px] font-semibold leading-tight">
              Play the {storyKindLabel(s.kind).toLowerCase()}
            </span>
            <span className="block text-[11px] text-muted-foreground">
              {s.step_count != null ? `${s.step_count} steps · ` : ''}see how it unfolded
            </span>
          </span>
          <Play size={16} className="flex-none text-amber-800 transition group-hover:translate-x-0.5 dark:text-amber-300" />
        </button>
      ))}
    </div>
  );
}

/** Split long-form text into paragraphs (blank-line separated). */
export function paragraphs(text: string | null | undefined): string[] {
  return (text ?? '')
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean);
}
