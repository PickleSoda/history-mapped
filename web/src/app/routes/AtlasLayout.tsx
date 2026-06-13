import { Outlet } from 'react-router-dom';
import { MapCanvas } from '@/components/map/MapCanvas';

/**
 * The persistent shell (spec §7). The map mounts here once and never unmounts;
 * child routes swap only the side panel via <Outlet/>. The timeline lives here
 * too (placeholder until the scrubber lands).
 */
export function AtlasLayout() {
  return (
    <div className="relative h-screen w-screen overflow-hidden">
      {/* Persistent map fills the viewport */}
      <MapCanvas />

      {/* Side panel — child route content */}
      <aside className="absolute left-0 top-0 z-10 h-full w-[360px] max-w-[90vw] overflow-y-auto border-r border-neutral-200 bg-white/95 backdrop-blur">
        <Outlet />
      </aside>

      {/* Timeline placeholder (scrubber + density bars land here) */}
      <div className="absolute bottom-0 left-0 z-10 h-14 w-full border-t border-neutral-200 bg-white/95 backdrop-blur" />
    </div>
  );
}
