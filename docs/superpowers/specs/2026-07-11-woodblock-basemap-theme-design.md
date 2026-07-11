# Woodblock Basemap with Theme-Aware Recoloring

**Date:** 2026-07-11
**Surface:** `web/` (public Atlas SPA) only.
**Status:** Design approved (scope, palette, and approach chosen by user), pending implementation plan.

## Goal

Replace the OHM "main" basemap with OHM's **woodblock** style (`https://www.openhistoricalmap.org/map-styles/woodblock/woodblock.json`) in **both themes**, and give dark mode a true dark map: a **charcoal + cream ink** recoloring of the woodblock style (dark map body, light borders/lines/labels), applied at runtime via `setPaintProperty` — replacing the current `.dark .maplibregl-canvas` CSS dim filter, which is removed.

Light mode uses the woodblock style as-is: its tan-paper + ink-line aesthetic matches the app's warm paper theme.

## Approach (decided: "A — single style + runtime paint flip")

One style is fetched once through the existing `loadHistoricalBasemapStyle()` normalize pipeline (English labels, noisy-icon stripping, wikidata exclusions, runtime date filter — all unchanged and verified compatible: 79/84 woodblock layers use the time-aware `ohm` source; the style bakes in no date filters). At load time we build per-layer **paint tables** holding each color-bearing paint property's light (original) and derived dark value. Theme toggles flip paints in place — no `setStyle`, no tile refetch, no camera reset, no interaction with our entity overlay layers (which already recolor themselves the same way).

Rejected alternatives: two-JSON `setStyle` swap (inherits marker re-registration, date-filter re-application, and visible reload on toggle); vendored fork of the style (84 layers duplicated in-repo, drifts from upstream).

## Components

### 1. Basemap style switch (`web/src/lib/map-config.ts`)

- `OHM_STYLE_URL` → the woodblock URL above.
- `HISTORICAL_BASEMAP_FALLBACK_STYLE_URL` (openfreemap liberty) unchanged.
- The existing normalization pass applies as-is. The main-style-specific noisy-icon prefix lists simply won't match woodblock layer ids — harmless, keep them (they also cover a future style switch back).

### 2. Basemap theme module (`web/src/lib/basemap-theme.ts`, new)

Pure, unit-testable functions plus one map-mutating applier:

- **`WOODBLOCK_DARK_COLORS`** — an explicit lookup from the style's actual colors (~18 distinct values) to hand-picked dark counterparts. Palette anchors (chosen):
  - map body / land (paper tones `rgba(207,179,125)`, `#f5f5f5`, cream fills `rgba(241,233,218)`, `rgba(236,225,203)`, `rgba(235,222,196)`): → charcoal steps `#2e2a24` (bg) / `#353028` (land fills)
  - water: → `#221f1b` (darker than land)
  - ink blacks (`rgba(19,19,16)`) and dark grays used for lines/labels: → warm cream `#e8ddc4`
  - boundary/line grays (`#b3b3b3`, `rgba(179,179,179)`, `rgba(210,210,210)`, `rgba(215,215,215)`, `rgba(146,143,129)`, `rgba(113,110,99)`, `rgba(153,153,153)`, `rgba(210,190,190)`): → light tan ink `#cfb37d` for admin/boundary lines, muted `#8a7f6d` for roads/minor lines (the plan pins the per-color assignment)
  - gold (`rgba(182,143,53)`): → brightened gold `#d9a94e`
  - red accent (`rgba(170,44,44)`): → brightened `#d47a63`
  - whites (`#ffffff`, `rgba(255,255,255)` — halos/casings): → dark halo `#2a2722`
- **`darkenFallback(color)`** — deterministic fallback for colors not in the lookup (upstream style updates): parse to HSL-ish, map high-luminance → charcoal step, low-luminance → cream, preserving a warm hue. Never throws; returns the input on unparseable values.
- **`buildBasemapPaintTable(style)`** — walks every layer's `paint`, collecting color-bearing properties (`background-color`, `fill-color`, `fill-outline-color`, `line-color`, `text-color`, `text-halo-color`, `icon-color`, `icon-halo-color`). Handles **both** plain string colors and expressions (recursive walk replacing color-string literals inside `interpolate`/`match`/`case`/etc.). Returns `{ layerId: { prop: { light, dark } } }` where `light` is the original value and `dark` the transformed one.
- **`applyBasemapTheme(map, theme, table)`** — `setPaintProperty` per entry; additionally in dark: clears `background-pattern` (the `woodblock-paper` sprite texture cannot be tinted) and sets `visibility: none` on symbol layers whose only content is sprite icons (ink-drawn icons vanish on dark); restores both in light. Guarded per-layer with `map.getLayer(...)`, safe to call any time after the style loads.

### 3. MapCanvas integration (`web/src/components/map/MapCanvas.tsx`)

- `loadHistoricalBasemapStyle()` already returns the normalized style object — build the paint table there in the init path and keep it in a ref.
- In the `map.on('load')` handler: if the app booted in dark (`.dark` on `<html>`), call `applyBasemapTheme(map, 'dark', table)` immediately after layers are available.
- Extend the existing theme-reactive effect (`useEffect(..., [theme])`) to also call `applyBasemapTheme(map, theme, table)` alongside the current entity overlay/marker recoloring.
- **Fallback style caveat (accepted):** if the woodblock fetch fails and the openfreemap fallback loads, the paint table is built from that style instead and `darkenFallback` does all the work — best-effort dark, not hand-tuned. No special-casing.

### 4. CSS cleanup (`web/src/styles.css`)

Remove the `.dark .maplibregl-canvas { filter: ... }` rule — superseded by the true dark basemap.

## Error handling

- Unparseable/unknown colors: `darkenFallback` returns input unchanged; the map renders with an occasional light layer rather than crashing.
- `applyBasemapTheme` is idempotent and per-layer-guarded; calling with a stale table after a style reload is a no-op for missing layers.

## Testing

- **Unit (Vitest):** `basemap-theme.test.ts` — lookup mapping hits the known woodblock colors; `darkenFallback` maps light→dark and dark→light-cream deterministically and round-trips unparseable input; `buildBasemapPaintTable` extracts plain colors AND colors nested in expressions, preserving expression structure; background-pattern/icon-visibility behavior encoded in `applyBasemapTheme` unit-tested against a minimal fake map object.
- **Gates:** `pnpm lint`, `pnpm types:check`, `pnpm exec vitest run`, `pnpm build`.
- **Visual:** both themes at `:5173` — light shows woodblock paper with texture; dark shows charcoal map, cream/tan boundaries and labels, no paper texture, timeline year filtering still works, entity overlays/markers unaffected.

## Non-goals

- No basemap picker UI (woodblock replaces main outright).
- No dark tuning of the openfreemap fallback beyond `darkenFallback` best-effort.
- No changes to entity overlays, markers, or the timeline (already theme-reactive).
- No changes to the Inertia admin app.
