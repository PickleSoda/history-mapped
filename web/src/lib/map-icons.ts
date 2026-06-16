/**
 * Per-group map marker icons.
 *
 * The map endpoint serves a point for OHM-linked / unplaced entities. Instead of
 * drawing bare circles we render a small colored disc with a white group glyph
 * (a lucide icon) and register one image per entity group, so a symbol layer can
 * pick the right marker via `icon-image: ['concat','marker-', entity_group]`.
 */
import type { Map as MapLibreMap } from 'maplibre-gl';
import type { EntityGroup } from '@/types/atlas';

/** lucide 24×24 glyph bodies (stroke-drawn), keyed by UPPERCASE entity group. */
const GROUP_GLYPHS: Record<string, string> = {
  // crown
  POLITY:
    '<path d="M11.562 3.266a.5.5 0 0 1 .876 0L15.39 8.87a1 1 0 0 0 1.516.294L21.183 5.5a.5.5 0 0 1 .798.519l-2.834 10.246a1 1 0 0 1-.956.734H5.81a1 1 0 0 1-.957-.734L2.02 6.02a.5.5 0 0 1 .798-.519l4.276 3.664a1 1 0 0 0 1.516-.294z"/><path d="M5 21h14"/>',
  // map-pin
  PLACE:
    '<path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"/><circle cx="12" cy="10" r="3"/>',
  // star
  EVENT:
    '<path d="M11.525 2.295a.53.53 0 0 1 .95 0l2.31 4.679a2.123 2.123 0 0 0 1.595 1.16l5.166.756a.53.53 0 0 1 .294.904l-3.736 3.638a2.123 2.123 0 0 0-.611 1.878l.882 5.14a.53.53 0 0 1-.771.56l-4.618-2.428a2.122 2.122 0 0 0-1.973 0L6.79 21.61a.53.53 0 0 1-.77-.56l.881-5.139a2.122 2.122 0 0 0-.611-1.879L2.554 10.4a.53.53 0 0 1 .294-.904l5.166-.756a2.122 2.122 0 0 0 1.597-1.16z"/>',
  // coins
  ECONOMY:
    '<circle cx="8" cy="8" r="6"/><path d="M18.09 10.37A6 6 0 1 1 10.34 18"/><path d="M7 6h1v4"/><path d="m16.71 13.88.7.71-2.82 2.82"/>',
  // landmark
  CULTURE:
    '<path d="M10 18v-7"/><path d="M11.12 2.198a2 2 0 0 1 1.76.006l7.866 3.847c.476.233.31.949-.22.949H3.474c-.53 0-.695-.716-.22-.949z"/><path d="M14 18v-7"/><path d="M18 18v-7"/><path d="M3 22h18"/><path d="M6 18v-7"/>',
};

/** Plain dot fallback for any group without a dedicated glyph. */
const DEFAULT_GLYPH = '<circle cx="12" cy="12" r="4"/>';

function markerSvg(color: string, glyph: string): string {
  return [
    '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">',
    `<circle cx="24" cy="24" r="19" fill="${color}" stroke="#ffffff" stroke-width="3"/>`,
    '<g transform="translate(14.4 14.4) scale(0.8)" fill="none" stroke="#ffffff"',
    ' stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">',
    glyph,
    '</g></svg>',
  ].join('');
}

function loadImage(svg: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image(48, 48);
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
  });
}

/** The icon-image id a feature's group maps to (mirror in the symbol layout). */
export function markerImageId(group: string): string {
  return `marker-${group.toUpperCase()}`;
}

/**
 * Resolve the active theme's group palette (same tokens MapCanvas uses for
 * fills), with literal-hex fallbacks maplibre/SVG can parse.
 */
function groupColors(): Record<string, string> {
  const root = getComputedStyle(document.documentElement);
  const c = (name: string, fallback: string) =>
    root.getPropertyValue(name).trim() || fallback;
  return {
    POLITY: c('--g-polity', '#b4543f'),
    PLACE: c('--g-place', '#2f7d6b'),
    EVENT: c('--g-event', '#b07d23'),
    ECONOMY: c('--g-economy', '#3f6db4'),
    CULTURE: c('--g-culture', '#7a57ad'),
    DEFAULT: '#71717a',
  };
}

/**
 * Register a marker image per group (+ a default) on the map. Idempotent — skips
 * images that already exist, so it is safe to call after a style reload.
 */
export async function registerGroupMarkers(map: MapLibreMap): Promise<void> {
  const colors = groupColors();
  const groups: Array<{ id: string; color: string; glyph: string }> = [
    ...Object.keys(GROUP_GLYPHS).map((g) => ({
      id: markerImageId(g as EntityGroup),
      color: colors[g] ?? colors.DEFAULT,
      glyph: GROUP_GLYPHS[g],
    })),
    { id: 'marker-DEFAULT', color: colors.DEFAULT, glyph: DEFAULT_GLYPH },
  ];

  await Promise.all(
    groups.map(async ({ id, color, glyph }) => {
      if (map.hasImage(id)) return;
      const img = await loadImage(markerSvg(color, glyph));
      if (!map.hasImage(id)) map.addImage(id, img, { pixelRatio: 2 });
    }),
  );
}
