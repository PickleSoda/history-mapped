import { Maximize2 } from 'lucide-react';
import type { ComponentProps } from 'react';
import { cn } from '@/lib/utils';

/**
 * "Expand" into the full page — the main way onward from a panel, so it is a
 * filled primary pill rather than muted text that only reads as a button on
 * hover. Shared by the desktop asides and the mobile sheet bars.
 */
export function ExpandButton({
  className,
  children = 'Expand',
  ...props
}: ComponentProps<'button'>) {
  return (
    <button
      type="button"
      {...props}
      className={cn(
        'inline-flex h-7 flex-none items-center gap-1.5 rounded-md bg-primary px-2.5 text-xs font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/85 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50',
        className,
      )}
    >
      <Maximize2 size={14} /> {children}
    </button>
  );
}
