import { DesktopShell } from '@/components/atlas/DesktopShell';
import { MobileShell } from '@/components/atlas/MobileShell';
import { useIsMobile } from '@/hooks';

/**
 * Top-level shell selector. Below `md` (≤767px) the touch shell (bottom sheet)
 * renders; above it, the desktop sidebar layout. Only one mounts at a time, so
 * the heavy sidebar and the vaul sheet never coexist in the DOM. Crossing the
 * breakpoint live remounts MapCanvas, which restores its view from the URL
 * `bbox` — an acceptable trade for the simpler render-branch.
 */
export function AtlasLayout() {
  const isMobile = useIsMobile();
  return isMobile ? <MobileShell /> : <DesktopShell />;
}
