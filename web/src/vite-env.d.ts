/// <reference types="vite/client" />
/// <reference types="vite-plugin-pwa/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  readonly VITE_APP_NAME: string;
  /** Admin origins allowed to drive the map-story preview (comma-separated). */
  readonly VITE_ADMIN_ORIGINS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
