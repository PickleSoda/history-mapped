import type { EntityGroup } from '@/types/atlas';

/** Literal-hex fallbacks (light theme), used when the CSS var is unavailable. */
const FALLBACK: Record<EntityGroup, string> = {
  polity: '#b4543f',
  place: '#2f7d6b',
  event: '#b07d23',
  economy: '#3f6db4',
  culture: '#7a57ad',
};

/**
 * Resolve the active theme's hex for an entity group. Canvas cannot read
 * `var(--…)`, so we read the computed custom property (mirrors map-icons).
 */
export function groupColor(group: EntityGroup): string {
  const v = getComputedStyle(document.documentElement)
    .getPropertyValue(`--g-${group}`)
    .trim();
  return v || FALLBACK[group];
}
