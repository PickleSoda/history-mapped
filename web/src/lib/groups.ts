/**
 * Entity-group display metadata. Colors reference the CSS variables defined in
 * styles.css so they track the active theme (light / parchment / dark).
 */
import type { EntityGroup } from '@/types/atlas';

export interface GroupMeta {
  label: string;
  /** Accent color (CSS var). */
  color: string;
  /** Soft background (CSS var). */
  soft: string;
}

export const GROUPS: Record<EntityGroup, GroupMeta> = {
  polity: { label: 'Polity', color: 'var(--g-polity)', soft: 'var(--g-polity-bg)' },
  place: { label: 'Place', color: 'var(--g-place)', soft: 'var(--g-place-bg)' },
  event: { label: 'Event', color: 'var(--g-event)', soft: 'var(--g-event-bg)' },
  economy: { label: 'Economy', color: 'var(--g-economy)', soft: 'var(--g-economy-bg)' },
  culture: { label: 'Culture', color: 'var(--g-culture)', soft: 'var(--g-culture-bg)' },
};

export const GROUP_ORDER: EntityGroup[] = [
  'polity',
  'place',
  'event',
  'economy',
  'culture',
];
