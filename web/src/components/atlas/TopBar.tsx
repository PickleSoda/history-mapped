import {
  ChevronLeft,
  ChevronRight,
  Compass,
  Globe,
  Layers,
  MapPin,
  Search,
  SlidersHorizontal,
} from 'lucide-react';
import { useSearchQuery, useTimeState, useView } from '@/hooks';
import { formatTime } from '@/lib/format';
import { cn } from '@/lib/utils';
import type { ViewMode } from '@/types/atlas';

const YEAR_STEP = 10;

function YearNav() {
  const { time, step } = useTimeState();
  return (
    <div className="flex items-center gap-1.5">
      <button
        type="button"
        onClick={() => step(-YEAR_STEP)}
        className="grid size-7 place-items-center rounded-md text-muted-foreground hover:bg-muted"
        aria-label="Step back"
      >
        <ChevronLeft size={15} />
      </button>
      <span className="font-mono text-sm tabular-nums">{formatTime(time)}</span>
      <button
        type="button"
        onClick={() => step(YEAR_STEP)}
        className="grid size-7 place-items-center rounded-md text-muted-foreground hover:bg-muted"
        aria-label="Step forward"
      >
        <ChevronRight size={15} />
      </button>
    </div>
  );
}

function ViewToggle() {
  const { view, setView } = useView();
  const opt = (value: ViewMode, label: string, Icon: typeof MapPin) => (
    <button
      type="button"
      onClick={() => setView(value)}
      className={cn(
        'inline-flex h-7 items-center gap-1.5 rounded-md px-2.5 text-xs font-medium transition-colors',
        view === value
          ? 'bg-card text-foreground shadow-sm'
          : 'text-muted-foreground hover:text-foreground',
      )}
    >
      <Icon size={14} />
      {label}
    </button>
  );
  return (
    <div className="flex items-center gap-0.5 rounded-lg bg-muted p-0.5">
      {opt('map', 'Map', MapPin)}
      {opt('globe', 'Globe', Globe)}
    </div>
  );
}

export function TopBar() {
  const { open } = useSearchQuery();

  return (
    <header className="flex h-[54px] flex-none items-center gap-3.5 border-b bg-card px-4">
      {/* Brand */}
      <div className="flex items-center gap-2">
        <span className="grid size-[30px] place-items-center rounded-lg bg-primary text-primary-foreground">
          <Compass size={17} />
        </span>
        <span className="text-[15px] font-bold tracking-[0.14em]">ATLAS</span>
        <span className="ml-0.5 hidden rounded-full border px-2 py-0.5 text-[11px] font-medium text-muted-foreground sm:inline">
          Historical
        </span>
      </div>

      {/* Center: omni-search + year nav */}
      <div className="flex flex-1 items-center justify-center gap-3.5">
        <button
          type="button"
          onClick={() => open('')}
          className="mx-auto flex h-[38px] w-full max-w-[520px] items-center gap-2.5 rounded-lg border bg-muted/50 px-3 text-[13px] text-muted-foreground transition-colors hover:bg-muted"
        >
          <Search size={15} />
          <span className="flex-1 text-left">Search places, polities, events…</span>
          <kbd className="rounded border border-b-2 bg-muted px-1.5 py-0.5 font-mono text-[10px]">
            ⌘K
          </kbd>
        </button>
        <div className="hidden lg:block">
          <YearNav />
        </div>
      </div>

      {/* Right: view toggle + tools */}
      <div className="flex items-center gap-2">
        <ViewToggle />
        <button
          type="button"
          className="grid size-9 place-items-center rounded-lg text-muted-foreground hover:bg-muted"
          aria-label="Layers"
        >
          <Layers size={16} />
        </button>
        <button
          type="button"
          className="grid size-9 place-items-center rounded-lg text-muted-foreground hover:bg-muted"
          aria-label="Settings"
        >
          <SlidersHorizontal size={16} />
        </button>
        <span className="size-8 rounded-full bg-muted" />
      </div>
    </header>
  );
}
