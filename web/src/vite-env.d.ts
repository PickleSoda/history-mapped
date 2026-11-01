/// <reference types="vite/client" />
/// <reference types="vite-plugin-pwa/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  readonly VITE_APP_NAME: string;
  /** Martin tile root (e.g. http://localhost:3000/tiles); unset = GeoJSON viewport queries. */
  readonly VITE_MAP_TILES_URL?: string;
  /** Admin origins allowed to drive the map-story preview (comma-separated). */
  readonly VITE_ADMIN_ORIGINS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
