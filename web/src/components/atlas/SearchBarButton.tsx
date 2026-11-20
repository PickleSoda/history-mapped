import { Search, X } from 'lucide-react';
import { useCommandPalette, useSearchFilter } from '@/hooks';
import { cn } from '@/lib/utils';

/**
 * The top bar's search box: opens the command palette. While a search word is
 * kept as a filter it shows that word, with a button to clear it.
 */
export function SearchBarButton({
  placeholder,
  shortcut = false,
  className,
}: {
  placeholder: string;
  /** Show the ⌘K hint (desktop). */
  shortcut?: boolean;
  className?: string;
}) {
  const { setOpen } = useCommandPalette();
  const { q, clear } = useSearchFilter();

  return (
    <div
      className={cn(
        'flex items-center rounded-lg border bg-muted/50 text-[13px] text-muted-foreground transition-colors hover:bg-muted',
        q && 'border-primary/50 bg-primary/5',
        className,
      )}
    >
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex h-full min-w-0 flex-1 items-center gap-2.5 px-3 text-left"
      >
        <Search size={15} className="flex-none" />
        {q ? (
          <span className="min-w-0 flex-1 truncate text-foreground">
            <span className="text-muted-foreground">Filter:</span> {q}
          </span>
        ) : (
          <span className="min-w-0 flex-1 truncate">{placeholder}</span>
        )}
        {shortcut && !q && (
          <kbd className="rounded border border-b-2 bg-muted px-1.5 py-0.5 font-mono text-[10px]">⌘K</kbd>
        )}
      </button>
      {q && (
        <button
          type="button"
          onClick={() => void clear()}
          aria-label={`Clear the filter “${q}”`}
          title="Clear filter"
          className="mr-1.5 grid size-6 flex-none place-items-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <X size={15} />
        </button>
      )}
    </div>
  );
}
