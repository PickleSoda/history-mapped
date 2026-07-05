# @history-mapped/web — Public Atlas SPA

The public-facing interactive historical atlas: a standalone React 19 + Vite single-page app
that talks to the Laravel API (`/api/v1`) with TanStack Query + Axios. Independent of the
Inertia admin (which lives in `../api/resources/js`).

What it does:

- MapLibre GL map rendering OpenHistoricalMap historical borders and entity geometry
- Time scrubber + entity-lifespan timeline (`TimelineScope`), chronicle player, entity detail panels
- Responsive desktop/mobile shells (bottom sheet on mobile)
- Installable PWA: service worker caches OHM tiles and `/api/v1` entity responses

## Running

The dev server runs as the `web` service in the Docker stack (`pnpm dev` from the repo root)
and is served at `http://localhost:5173` (override with `FORWARD_WEB_PORT`).

New dependencies need the init container + a full `web` container restart to be picked up —
a Vite config reload alone won't load new plugins.

## Commands (from this directory, or `pnpm --filter @history-mapped/web <cmd>` from the root)

```bash
pnpm lint            # eslint
pnpm types:check     # tsc --noEmit
pnpm test            # vitest run
pnpm build           # tsc -b && vite build
pnpm preview         # serve the production build
```

## Layout

```text
src/
├── app/          # app shell, routing, providers
├── components/
│   ├── atlas/    # shells, timeline, chronicle player, sidebars, detail panels
│   ├── map/      # MapLibre map layers and controls
│   └── ui/       # shared primitives
├── hooks/        # data + viewport hooks (TanStack Query)
├── stores/       # client state
├── lib/          # api client, formatting, utils
└── types/        # API payload types
```

## Docs

- [docs/architecture/frontend-app.md](../docs/architecture/frontend-app.md) — SPA architecture (state layers, hook seam, render budget)
- [docs/architecture/ohm-integration.md](../docs/architecture/ohm-integration.md) — OHM tiles / MapLibre integration
