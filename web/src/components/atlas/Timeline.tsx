import { Minus, Play, Plus } from 'lucide-react';
import { useTimeState } from '@/hooks';
import { eraFor, formatTime, instantYear } from '@/lib/format';

/** Axis bounds the scrubber is drawn over (placeholder span). */
const AXIS_MIN = -800;
const AXIS_MAX = 800;

/** Era bands across the track (flex-weighted, colored by group palette). */
const BANDS = [
  { flex: 3, soft: 'var(--g-polity-bg)' },
  { flex: 4, soft: 'var(--g-economy-bg)' },
  { flex: 2.4, soft: 'var(--g-culture-bg)' },
  { flex: 3, soft: 'var(--g-place-bg)' },
];

/**
 * Timeline bar (spec §6, "the spine"). Visual scrubber wired to the live time
 * readout; drag-to-scrub and density bars arrive in the timeline build step.
 */
export function Timeline() {
  const { time } = useTimeState();
  const year = instantYear(time);
  const pct = Math.max(
    0,
    Math.min(100, ((year - AXIS_MIN) / (AXIS_MAX - AXIS_MIN)) * 100),
  );

  return (
    <div className="flex h-14 items-center gap-3 px-4">
      <button
        type="button"
        className="grid size-9 flex-none place-items-center rounded-lg border bg-card text-foreground hover:bg-muted"
        aria-label="Play"
      >
        <Play size={16} />
      </button>

      <div className="flex w-[150px] flex-none flex-col leading-tight">
        <span className="font-mono text-sm tabular-nums">{formatTime(time)}</span>
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
          {eraFor(year)}
        </span>
      </div>

      <div className="relative h-8 flex-1">
        {/* Era bands */}
        <div className="absolute inset-0 flex overflow-hidden rounded-md">
          {BANDS.map((b, i) => (
            <span key={i} style={{ flex: b.flex, background: b.soft }} />
          ))}
        </div>
        {/* Ticks */}
        <div className="absolute inset-x-0 bottom-0 flex h-full items-end justify-between px-px">
          {Array.from({ length: 28 }).map((_, i) => (
            <span
              key={i}
              className="w-px bg-border"
              style={{ height: i % 4 === 0 ? '60%' : '35%' }}
            />
          ))}
        </div>
        {/* Handle */}
        <div
          className="absolute top-0 h-full w-0.5 -translate-x-1/2 bg-foreground"
          style={{ left: `${pct}%` }}
        >
          <span className="absolute -top-1 left-1/2 size-3 -translate-x-1/2 rounded-full border-2 border-card bg-foreground shadow" />
        </div>
      </div>

      <div className="flex flex-none items-center gap-1">
        <button
          type="button"
          className="grid size-7 place-items-center rounded-md border bg-card text-muted-foreground hover:bg-muted"
          aria-label="Zoom out"
        >
          <Minus size={14} />
        </button>
        <button
          type="button"
          className="grid size-7 place-items-center rounded-md border bg-card text-muted-foreground hover:bg-muted"
          aria-label="Zoom in"
        >
          <Plus size={14} />
        </button>
      </div>
    </div>
  );
}
