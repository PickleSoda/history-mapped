import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';
import { defineConfig, transformWithEsbuild, type Plugin } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';

/**
 * @timescope/react alpha ships JSX in its bundled ESM .js output.
 * Rollup's commonjs scanner chokes on the raw `<div` before the react plugin
 * can transpile it. This micro-plugin runs first (enforce:'pre') and strips JSX
 * via Vite's built-in esbuild transform so rollup sees plain JS.
 */
function timescopeJsxPlugin(): Plugin {
  return {
    name: 'timescope-jsx',
    enforce: 'pre',
    async transform(code, id) {
      if (!id.includes('@timescope/react')) return null;
      return transformWithEsbuild(code, id, {
        loader: 'jsx',
        jsx: 'automatic',
        target: 'es2022',
      });
    },
  };
}

const DAY_SECONDS = 60 * 60 * 24;

export default defineConfig({
  plugins: [
    timescopeJsxPlugin(),
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg', 'apple-touch-icon-180x180.png'],
      manifest: {
        name: 'History Mapped',
        short_name: 'History Mapped',
        description: 'Interactive historical atlas',
        display: 'standalone',
        start_url: '/',
        theme_color: '#ffffff',
        background_color: '#ffffff',
        icons: [
          { src: 'pwa-192x192.png', sizes: '192x192', type: 'image/png' },
          { src: 'pwa-512x512.png', sizes: '512x512', type: 'image/png' },
          {
            src: 'maskable-icon-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png,ico,woff2}'],
        // Wireframe artifacts in public/ are not app assets.
        globIgnores: ['**/*.jsx', '**/Historical Atlas Wireframes.html'],
        navigateFallback: 'index.html',
        // The MapLibre chunk exceeds workbox's 2 MB default.
        maximumFileSizeToCacheInBytes: 3 * 1024 * 1024,
        runtimeCaching: [
          // OHM vector tiles — immutable and heavy, never re-download within TTL.
          {
            urlPattern: /^https:\/\/vtiles\.openhistoricalmap\.org\/.+\.pbf/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'ohm-tiles',
              expiration: {
                maxEntries: 2000,
                maxAgeSeconds: 30 * DAY_SECONDS,
                purgeOnQuotaError: true,
              },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          // OHM hillshade raster tiles (referenced by the OHM style).
          {
            urlPattern:
              /^https:\/\/static-tiles-lclu\.s3\.[a-z0-9-]+\.amazonaws\.com\/.+\.png/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'ohm-tiles',
              expiration: {
                maxEntries: 2000,
                maxAgeSeconds: 30 * DAY_SECONDS,
                purgeOnQuotaError: true,
              },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          // OpenFreeMap fallback vector tiles (must precede the generic
          // openfreemap rule below).
          {
            urlPattern: /^https:\/\/tiles\.openfreemap\.org\/.+\.pbf/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'ohm-tiles',
              expiration: {
                maxEntries: 2000,
                maxAgeSeconds: 30 * DAY_SECONDS,
                purgeOnQuotaError: true,
              },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          // OHM style JSON, sprites, glyph PBFs.
          {
            urlPattern: /^https:\/\/www\.openhistoricalmap\.org\/map-styles\//i,
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'ohm-style-assets',
              expiration: { maxAgeSeconds: 30 * DAY_SECONDS },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          // OpenFreeMap fallback style/sprites/glyphs (non-.pbf traffic).
          {
            urlPattern: /^https:\/\/tiles\.openfreemap\.org\//i,
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'ohm-style-assets',
              expiration: { maxAgeSeconds: 30 * DAY_SECONDS },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          // API reads. Anchored regex so cross-origin (:8000 in dev) matches;
          // /sanctum/csrf-cookie is outside /api/v1 and stays uncached.
          {
            urlPattern: /^https?:\/\/[^/]+\/api\/v1\//,
            method: 'GET',
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'api-v1',
              expiration: { maxEntries: 500, maxAgeSeconds: 7 * DAY_SECONDS },
              cacheableResponse: { statuses: [200] },
            },
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  optimizeDeps: {
    include: ['@timescope/react', 'timescope', '@kikuchan/decimal'],
    esbuildOptions: {
      plugins: [
        {
          name: 'timescope-jsx-prebundle',
          setup(build) {
            build.onLoad({ filter: /@timescope[\\/]react/ }, async (args) => {
              const { readFile } = await import('node:fs/promises');
              const contents = await readFile(args.path, 'utf8');
              return { contents, loader: 'jsx' };
            });
          },
        },
      ],
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    hmr: {
      host: 'localhost',
      port: 5173,
    },
    watch: {
      usePolling: true,
    },
  },
});
