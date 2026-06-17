# Plan 02 - App Scaffolding

> **Status: ✅ Executed** — verified 2026-06-15 against the codebase. See [STATUS.md](../../plans/STATUS.md).

## Goal

Scaffold the two applications defined by the setup guide: the Laravel 11 app with an Inertia React admin and the customer-facing Vite React app.

## Scope

- Create the Laravel application in `api/`.
- Install Sanctum API bootstrap and Inertia React admin dependencies.
- Create the React client app in `web/`.
- Keep everything runnable through the Docker stack created in plan 01.

## Deliverables

- `api/` Laravel 11 project with a minimal Inertia admin route and page
- `web/` React + Vite TypeScript app with a minimal home page
- App-specific env examples and workspace package wiring
- Updated Docker behavior where needed so both apps boot cleanly in containers

## Verification

- `docker compose up` can build all relevant images
- Laravel responds through nginx
- Admin assets are served through Vite
- The customer app starts on port `5173`

## Deferred

- Real authentication screens and permissions setup
- OpenAPI export and generated contracts beyond the package shell
- First CRUD resource and shared API client integration
