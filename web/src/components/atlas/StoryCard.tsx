import { Biohazard, Compass, Flag, Footprints, Map as MapIcon, Play, Ship, Sprout, Swords } from 'lucide-react';
import { useStoryNav } from '@/hooks';
import type { MapStorySummary } from '@/lib/schemas/map-story';

const KIND_LABELS: Record<string, string> = {
  battle: 'Battle map',
  naval_battle: 'Battle map',
  siege: 'Battle map',
  campaign: 'Campaign map',
  war: 'War map',
  epidemic: 'Epidemic map',
  trade_route: 'Trade map',
  migration: 'Migration map',
  exploration: 'Voyage map',
  expansion: 'Expansion map',
  diffusion: 'Spread map',
  event: 'Story map',
};

/** "Battle map", "Campaign map", "Epidemic map"… for a story kind. */
export function storyKindLabel(kind: string): string {
  return KIND_LABELS[kind] ?? 'Story map';
}

/** The icon for a story kind (crossed swords for the military ones). */
export function StoryKindIcon({ kind, size }: { kind: string; size: number }) {
  switch (kind) {
    case 'epidemic':
      return <Biohazard size={size} />;
    case 'trade_route':
      return <Ship size={size} />;
    case 'migration':
      return <Footprints size={size} />;
    case 'exploration':
      return <Compass size={size} />;
    case 'expansion':
      return <Flag size={size} />;
    case 'diffusion':
      return <Sprout size={size} />;
    case 'event':
      return <MapIcon size={size} />;
    default:
      return <Swords size={size} />;
  }
}

/**
 * Prominent "play the battle map" (or epidemic map, trade map…) buttons for an entity's stories — the way
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
            <StoryKindIcon kind={s.kind} size={18} />
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
