import { cn } from '@/lib/utils';

/**
 * The era's ornament (a Greek key, dentils, lotus buds…) as a thin, solid
 * border down a panel's inner edge. Place it beside the panel with
 * `className`; `flip` mirrors it for a panel's left edge, so the motif backs
 * onto the panel on either side. Purely decorative: hidden when the active
 * era has no ornament, or when it has no panel beside it (an empty side).
 */
export function EraBorder({ className, flip = false }: { className?: string; flip?: boolean }) {
  return <div aria-hidden data-flip={flip || undefined} className={cn('era-border pointer-events-none', className)} />;
}
