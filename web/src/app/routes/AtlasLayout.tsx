import { DesktopShell } from '@/components/atlas/DesktopShell';
import { MobileShell } from '@/components/atlas/MobileShell';
import { useEraTheme, useIsMobile, useNavTrailSync } from '@/hooks';

/**
 * Top-level shell selector. Below `md` (≤767px) the touch shell (bottom sheet)
 * renders; above it, the desktop sidebar layout. Only one mounts at a time, so
 * the heavy sidebar and the vaul sheet never coexist in the DOM. Crossing the
 * breakpoint live remounts MapCanvas, which restores its view from the URL
 * `bbox` — an acceptable trade for the simpler render-branch.
 *
 * Both shells take on the era theme of the time and place on the map
 * (useEraTheme); leaving the atlas restores the default look.
 */
export function AtlasLayout() {
  const isMobile = useIsMobile();
  useNavTrailSync();
  useEraTheme();
  return isMobile ? <MobileShell /> : <DesktopShell />;
}
