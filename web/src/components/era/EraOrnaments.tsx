import { cn } from '@/lib/utils';

/**
 * The era's ornament band (a Greek key, a row of dentils, lotus buds…) in the
 * era's accent colour. Purely decorative and hidden when the active era has
 * no ornament, so it can sit under any header or above any footer.
 */
export function EraRule({ className }: { className?: string }) {
  return <div aria-hidden className={cn('era-rule pointer-events-none', className)} />;
}

/**
 * A vertical ornament beside a panel, such as a fluted column for Rome.
 * Position it with `className`; hidden when the era has no pillar.
 */
export function EraPillar({ className }: { className?: string }) {
  return <div aria-hidden className={cn('era-pillar pointer-events-none', className)} />;
}
