import { Compass, Globe, Layers, MapPin, Search, SlidersHorizontal } from 'lucide-react';
import { useState } from 'react';
import { useCommandPalette, useView } from '@/hooks';
import { cn } from '@/lib/utils';

/** Mobile header: brand mark · search pill (opens ⌘K palette) · tools menu. */
export function MobileTopBar() {
  const { setOpen } = useCommandPalette();
  const { view, setView } = useView();
  const [tools, setTools] = useState(false);

  return (
    <header className="relative flex h-[52px] flex-none items-center gap-2 border-b bg-card px-3">
      <span className="grid size-8 flex-none place-items-center rounded-lg bg-primary text-primary-foreground">
        <Compass size={16} />
      </span>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex h-9 flex-1 items-center gap-2 rounded-lg border bg-muted/50 px-3 text-[13px] text-muted-foreground"
      >
        <Search size={15} />
        <span className="flex-1 text-left">Search the atlas…</span>
      </button>
      <button
        type="button"
        onClick={() => setTools((v) => !v)}
        aria-label="Tools"
        aria-expanded={tools}
        className="grid size-9 flex-none place-items-center rounded-lg border bg-card text-muted-foreground"
      >
        <SlidersHorizontal size={16} />
      </button>

      {tools && (
        <div className="absolute right-3 top-[54px] z-30 w-44 rounded-xl border bg-popover p-1.5 shadow-lg">
          <div className="flex gap-0.5 rounded-lg bg-muted p-0.5">
            {([['map', 'Map', MapPin], ['globe', 'Globe', Globe]] as const).map(
              ([v, label, Icon]) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => {
                    setView(v);
                    setTools(false);
                  }}
                  className={cn(
                    'inline-flex flex-1 items-center justify-center gap-1.5 rounded-md py-1.5 text-xs font-medium',
                    view === v ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground',
                  )}
                >
                  <Icon size={14} /> {label}
                </button>
              ),
            )}
          </div>
          <button
            type="button"
            className="mt-1 flex w-full items-center gap-2 rounded-md px-2 py-2 text-[13px] text-muted-foreground hover:bg-muted"
          >
            <Layers size={15} /> Layers
          </button>
        </div>
      )}
    </header>
  );
}
