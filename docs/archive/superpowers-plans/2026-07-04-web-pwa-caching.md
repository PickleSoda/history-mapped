# Web PWA + Caching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a service worker + web manifest to the public Atlas SPA (`web/`) that disk-caches OHM basemap traffic (tiles, style, sprites, glyphs) and `GET /api/v1` responses for fast repeat visits.

**Architecture:** `vite-plugin-pwa` in `generateSW` mode — all caching behavior is declared as Workbox runtime-caching rules in `web/vite.config.ts`; the plugin generates the service worker, injects the manifest, and precaches the app shell at build time. Registration is one `registerSW()` call in `main.tsx`. No changes to hooks, the TanStack Query client, or the Axios client.

**Tech Stack:** vite-plugin-pwa 1.3.x (Workbox 7), Vite 7, React 19. Icons generated one-off with `@vite-pwa/assets-generator`.

**Spec:** `docs/superpowers/specs/2026-07-04-web-pwa-caching-design.md`

## Global Constraints

- All changes live in `web/` only — no API, admin, or pipeline changes.
- Service worker is **production-only**: `devOptions.enabled` must stay unset/false so the Docker dev server (`:5173`) is unaffected.
- `registerType: 'autoUpdate'` — no update-prompt UI.
- Cache names and bounds (exact values from spec): `ohm-tiles` CacheFirst maxEntries 2000 / 30 days / `purgeOnQuotaError: true`; `ohm-style-assets` StaleWhileRevalidate 30 days; `api-v1` StaleWhileRevalidate GET-only maxEntries 500 / 7 days.
- Never cache non-GET requests or `/sanctum/csrf-cookie` (it is outside `/api/v1`, so the API rule must match only `/api/v1` paths).
- Precache must exclude the wireframe artifacts in `web/public/` (`*.jsx`, `Historical Atlas Wireframes.html`).
- All commands below run **on the host** from `/home/pickle/code/history-mapped/web` (node 24 + pnpm 10 are available host-side; the SPA workspace does not need Docker to build).
- Quality gates for every task: `pnpm build` (runs `tsc -b`), `pnpm lint`, `pnpm test` all green.

## Environment notes for the implementer

- The OHM style JSON (`https://www.openhistoricalmap.org/map-styles/main/main.json`) references these hosts at runtime (verified 2026-07-04):
  - vector tiles: `https://vtiles.openhistoricalmap.org/maps/{ohm,ne,osm_land}/{z}/{x}/{y}.pbf`
  - hillshade raster tiles: `https://static-tiles-lclu.s3.us-west-1.amazonaws.com/{z}/{x}/{y}.png`
  - glyphs: `https://www.openhistoricalmap.org/map-styles/fonts/{fontstack}/{range}.pbf`
  - sprite: `https://www.openhistoricalmap.org/map-styles/historical/historical_spritesheet*`
  - fallback basemap (style + tiles): `https://tiles.openfreemap.org/...`
- The API is cross-origin in dev/preview (SPA on `:5173`/`:4173`, API on `http://localhost:8000`). Workbox routes cross-origin requests only when a RegExp matches from the **start** of the full URL — every runtime-caching pattern below is anchored with `^https?://`.
- Generated Workbox service workers are not unit-testable with vitest; each task verifies via build-output assertions and (Task 4) a real browser session.

---

### Task 1: PWA icons + index.html head links

**Files:**
- Create (generated): `web/public/pwa-64x64.png`, `web/public/pwa-192x192.png`, `web/public/pwa-512x512.png`, `web/public/maskable-icon-512x512.png`, `web/public/apple-touch-icon-180x180.png`, `web/public/favicon.ico`
- Modify: `web/index.html`

**Interfaces:**
- Consumes: existing `web/public/favicon.svg`
- Produces: icon files whose exact names Task 2's manifest `icons` array references (`pwa-192x192.png`, `pwa-512x512.png`, `maskable-icon-512x512.png`, `apple-touch-icon-180x180.png`)

- [ ] **Step 1: Generate icons from the existing favicon**

```bash
cd /home/pickle/code/history-mapped/web
pnpm dlx @vite-pwa/assets-generator --preset minimal-2023 public/favicon.svg
```

Expected: it logs the generated assets and exits 0.

- [ ] **Step 2: Verify the six icon files exist**

```bash
ls -la public/pwa-64x64.png public/pwa-192x192.png public/pwa-512x512.png \
  public/maskable-icon-512x512.png public/apple-touch-icon-180x180.png public/favicon.ico
```

Expected: all six files listed, each non-zero size. If the generator produced different names, STOP and report — Task 2 depends on these exact names.

- [ ] **Step 3: Add head links to index.html**

Edit `web/index.html` — insert two lines after the existing favicon link, so the `<head>` reads:

```html
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <link rel="apple-touch-icon" href="/apple-touch-icon-180x180.png" />
    <meta name="theme-color" content="#ffffff" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>History Mapped</title>
  </head>
```

- [ ] **Step 4: Verify the build still passes**

```bash
pnpm build
```

Expected: `tsc -b` + `vite build` succeed; `dist/` contains the new icons.

- [ ] **Step 5: Commit**

```bash
cd /home/pickle/code/history-mapped
git add web/public web/index.html
git commit -m "feat(web): add PWA icons and head links"
```

---

### Task 2: vite-plugin-pwa — manifest + workbox caching rules

**Files:**
- Modify: `web/package.json` (via `pnpm add`)
- Modify: `web/vite.config.ts`

**Interfaces:**
- Consumes: icon filenames from Task 1 (`pwa-192x192.png`, `pwa-512x512.png`, `maskable-icon-512x512.png`, `apple-touch-icon-180x180.png`)
- Produces: build emits `dist/sw.js` + `dist/manifest.webmanifest`; cache names `ohm-tiles`, `ohm-style-assets`, `api-v1` (Task 4 asserts these in the browser); `virtual:pwa-register` module for Task 3

- [ ] **Step 1: Install the plugin**

```bash
cd /home/pickle/code/history-mapped/web
pnpm add -D vite-plugin-pwa
```

Expected: `vite-plugin-pwa` ^1.3.0 added to devDependencies (it bundles workbox-build/workbox-window — no other packages needed).

- [ ] **Step 2: Add the VitePWA plugin to vite.config.ts**

In `web/vite.config.ts`, add the import at the top with the other imports:

```ts
import { VitePWA } from 'vite-plugin-pwa';
```

Add this constant above `defineConfig` (after the `timescopeJsxPlugin` function):

```ts
const DAY_SECONDS = 60 * 60 * 24;
```

Then change the `plugins` line to include the configured plugin:

```ts
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
```

- [ ] **Step 3: Build and assert the SW output**

```bash
pnpm build
ls dist/sw.js dist/manifest.webmanifest dist/workbox-*.js
```

Expected: build succeeds; all three files exist.

- [ ] **Step 4: Assert cache rules and precache contents**

```bash
grep -o "ohm-tiles\|ohm-style-assets\|api-v1" dist/sw.js | sort -u
! grep -q "Wireframes" dist/sw.js && echo "precache clean"
grep -o '"name":"History Mapped"' dist/manifest.webmanifest
```

Expected output, in order:

```
api-v1
ohm-style-assets
ohm-tiles
precache clean
"name":"History Mapped"
```

- [ ] **Step 5: Lint and test**

```bash
pnpm lint && pnpm test
```

Expected: both pass (no app source changed; this catches vite.config.ts lint issues).

- [ ] **Step 6: Commit**

```bash
cd /home/pickle/code/history-mapped
git add web/package.json web/vite.config.ts pnpm-lock.yaml
git commit -m "feat(web): add vite-plugin-pwa with OHM tile and api-v1 caching"
```

---

### Task 3: Register the service worker in the app

**Files:**
- Modify: `web/src/vite-env.d.ts`
- Modify: `web/src/main.tsx`

**Interfaces:**
- Consumes: `virtual:pwa-register` module provided by the plugin configured in Task 2
- Produces: SW registration on page load in production builds (Task 4 observes it via `navigator.serviceWorker`)

- [ ] **Step 1: Add the plugin's client types**

Edit `web/src/vite-env.d.ts` — add the reference below the existing one, so the file starts:

```ts
/// <reference types="vite/client" />
/// <reference types="vite-plugin-pwa/client" />
```

- [ ] **Step 2: Register the SW in main.tsx**

Edit `web/src/main.tsx` to:

```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { registerSW } from 'virtual:pwa-register';
import { Providers } from './app/providers';
import { AppRoutes } from './app/router';
import './styles.css';

// Registration failure is non-fatal: the app runs exactly as without a SW.
registerSW({ immediate: true });

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Providers>
      <AppRoutes />
    </Providers>
  </StrictMode>,
);
```

- [ ] **Step 3: Verify types, lint, tests, build**

```bash
cd /home/pickle/code/history-mapped/web
pnpm types:check && pnpm lint && pnpm test && pnpm build
```

Expected: all pass. If `import/order` flags the `virtual:pwa-register` import position, run `pnpm lint --fix` and keep the autofixed order.

- [ ] **Step 4: Assert registration code is in the bundle**

```bash
grep -rlo "serviceWorker" dist/assets/*.js | head -1
```

Expected: at least one bundle file matches (the register call shipped).

- [ ] **Step 5: Commit**

```bash
cd /home/pickle/code/history-mapped
git add web/src/vite-env.d.ts web/src/main.tsx
git commit -m "feat(web): register PWA service worker"
```

---

### Task 4: End-to-end verification in a real browser

**Files:**
- None (verification only; no code changes expected)

**Interfaces:**
- Consumes: the built app from Tasks 1–3 (`pnpm preview` serves `dist/` on `:4173`); Playwright browser tools
- Produces: verified evidence that the SW registers and the `ohm-tiles`/`ohm-style-assets` caches populate; a written verification report in the task's completion message

- [ ] **Step 1: Serve the production build**

```bash
cd /home/pickle/code/history-mapped/web
pnpm build
pnpm preview --host 0.0.0.0 --port 4173 &
```

Expected: preview server on `http://localhost:4173`.

- [ ] **Step 2: Load the app and let the map fetch tiles**

Using the Playwright browser tools: navigate to `http://localhost:4173`, wait for the map canvas to render (~5–10 s so MapLibre fetches style + tiles).

- [ ] **Step 3: Assert SW registration and cache population**

Evaluate in the page:

```js
(async () => {
  const reg = await navigator.serviceWorker.getRegistration();
  const keys = await caches.keys();
  const tiles = await caches.open('ohm-tiles');
  const tileCount = (await tiles.keys()).length;
  return { swActive: !!reg?.active, cacheKeys: keys, tileCount };
})()
```

Expected: `swActive: true`; `cacheKeys` includes `ohm-tiles`, `ohm-style-assets`, and a `workbox-precache-...` entry; `tileCount > 0`.

- [ ] **Step 4: Assert repeat load serves from the SW**

Reload the page, then evaluate:

```js
performance.getEntriesByType('resource')
  .filter((e) => e.name.includes('vtiles.openhistoricalmap.org'))
  .map((e) => ({ name: e.name.slice(-40), transferSize: e.transferSize }))
  .slice(0, 5)
```

Expected: entries with `transferSize: 0` (served by the SW cache, not the network).

- [ ] **Step 5: Check api-v1 caching if the API stack is running**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/health || echo "stack down"
```

If the Docker stack is up (any non-000 response): interact with the app so it fetches entities, then evaluate `(await (await caches.open('api-v1')).keys()).length` — expected `> 0`. If the stack is down, note that in the report and skip; the rule was already asserted in `dist/sw.js` in Task 2.

- [ ] **Step 6: Stop the preview server and report**

Kill the preview process. Report the collected evidence (swActive, cache keys, tile count, transferSize samples, api-v1 status). No commit — this task changes no files.

---

## Self-review notes

- Spec coverage: setup/registration (Tasks 2–3), precache + globIgnores + navigateFallback + 3 MB limit (Task 2), all three runtime cache rules with exact bounds (Task 2 Step 2), manifest + icons (Tasks 1–2), autoUpdate (Task 2), verification (Task 4, mirrors the spec's verification section). Update-prompt UI, offline UX, admin caching: out of scope per spec — no tasks.
- The hillshade raster host (`static-tiles-lclu...amazonaws.com`) is not named in the spec's table but is part of the OHM basemap the spec's goal targets; included in `ohm-tiles` deliberately.
- Type/name consistency: cache names, icon filenames, and `DAY_SECONDS` are used identically across tasks.
