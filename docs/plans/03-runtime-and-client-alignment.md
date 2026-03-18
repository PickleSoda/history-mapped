# Plan 03 - Runtime and Client Alignment

## Goal

Align the Laravel app with the monorepo's Docker-first runtime assumptions, then scaffold the separate customer client app.

## Scope

- Update `api/` environment defaults for Docker Compose, Postgres, Redis, Mailpit, and Sanctum SPA auth.
- Add missing API route bootstrap for versioned `/api/v1` endpoints.
- Ensure Laravel runtime settings match the documented local architecture.
- Scaffold `web/` as a Vite React TypeScript client that fits the pnpm workspace and Docker stack.

## Deliverables

- Docker-aligned `api/.env.example` and bootstrap middleware
- Basic `api/routes/api.php` with a minimal versioned health endpoint
- `web/` client app with package metadata, Vite config, TS config, and starter pages
- Root and Docker wiring updated if needed for the new client app

## Verification

- Compose config remains valid
- Laravel exposes `/api/v1/health`
- `web/` can boot in the Docker stack
- Shared package and both apps continue to resolve in the workspace

## Deferred

- Full contract export/generation loop
- Customer auth screens and API integration
- Role/permission hardening for the admin area
