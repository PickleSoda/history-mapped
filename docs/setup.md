# WikiGlobe - Monorepo Setup Guide

## Overview

WikiGlobe is a monorepo containing:

- **`api/`** - Laravel 11 backend with Inertia.js (React) for the admin panel, and a REST API for the customer frontend.
- **`web/`** - React (Vite) customer-facing frontend.
- **`shared/`** - Real TypeScript workspace package for generated API contracts, shared client utilities, and stable cross-app types.

Package manager: **pnpm** with workspaces.  
Local dev environment: **fully dockerized with Docker Compose**.

---

## 0. Foundation Decisions

- **Admin architecture** - The admin lives inside Laravel as an Inertia React app. It is not a separate SPA and does not consume the public REST API for routine page rendering.
- **Customer auth model** - The customer frontend is a first-party SPA and uses **Laravel Sanctum SPA cookie auth**. This keeps browser auth aligned with Laravel sessions and avoids token storage in the browser.
- **API contract strategy** - Laravel is the source of truth for routes, validation, and response shapes. Generate **OpenAPI** from Laravel code, then generate TypeScript contract artifacts into `shared/`. Do not manually mirror request and response shapes forever.
- **Shared package strategy** - `shared/` is a real buildable workspace package with `dist/` output and explicit exports. Apps consume it through `workspace:*`, not via source aliases like `../shared/src`.
- **Development model** - Development is fully dockerized. PHP, Node, Vite, Composer, pnpm, queue workers, and supporting services all run in containers.
- **Deployment model** - Deploy the Laravel app, queue worker, and scheduler as separate processes from the same application image. Deploy `web/` separately as static assets behind a CDN.

---

## 1. Repository Structure

```
wikiglobe/
|- api/                         # Laravel 11 application
|  |- app/
|  |- bootstrap/
|  |- config/
|  |- database/
|  |- resources/
|  |  \- js/                   # Inertia React admin frontend
|  |     |- Pages/
|  |     |- Components/
|  |     |- Layouts/
|  |     \- app.tsx
|  |- routes/
|  |  |- web.php               # Inertia admin routes
|  |  |- api.php               # Public API routes
|  |  \- auth.php              # Login/logout/password routes
|  |- storage/
|  |  \- app/
|  |     \- openapi.json       # Generated OpenAPI artifact
|  |- composer.json
|  |- vite.config.ts           # Vite config for Inertia admin assets
|  |- tsconfig.json
|  \- package.json             # Admin frontend package deps
|
|- web/                         # Customer-facing React SPA
|  |- src/
|  |  |- pages/
|  |  |- components/
|  |  |- hooks/
|  |  |- lib/
|  |  \- main.tsx
|  |- vite.config.ts
|  |- tsconfig.json
|  \- package.json
|
|- shared/                      # Real TypeScript workspace package
|  |- src/
|  |  |- generated/            # Generated from OpenAPI
|  |  |- client/               # Thin shared HTTP client utilities
|  |  |- types/                # Stable hand-authored cross-app types
|  |  \- index.ts
|  |- dist/
|  |- tsconfig.json
|  \- package.json             # Name: @wikiglobe/shared
|
|- docker/
|  |- api/
|  |  |- Dockerfile            # PHP 8.3-FPM + Composer
|  |  \- nginx.conf
|  |- web/
|  |  \- Dockerfile            # Node 20 for Vite/web workspace commands
|  |- admin/
|  |  \- Dockerfile            # Node 20 for Inertia Vite server
|  \- docker-compose.yml
|
|- pnpm-workspace.yaml
|- package.json                # Root workspace and Docker helper scripts
|- .gitignore
|- .env.example                # Root Docker Compose env only
\- README.md
```

---

## 2. Docker Compose Services

File: `docker/docker-compose.yml`

| Service | Image / Base | Ports | Notes |
|---------|--------------|-------|-------|
| **app** | PHP 8.3-FPM | - | Laravel app container for PHP, Composer, Artisan |
| **nginx** | nginx:alpine | `8000:80` | Public local entrypoint for Laravel |
| **web** | node:20-alpine | `5173:5173` | Customer Vite dev server |
| **vite-admin** | node:20-alpine | `5174:5174` | Inertia admin Vite dev server |
| **shared** | node:20-alpine | - | Watches and rebuilds `@wikiglobe/shared` into `dist/` |
| **db** | postgres:16-alpine | `5432:5432` | Primary database |
| **redis** | redis:7-alpine | `6379:6379` | Cache, sessions, queues |
| **queue** | same as `app` | - | Runs `php artisan queue:work` |
| **scheduler** | same as `app` | - | Runs Laravel scheduler loop |
| **mailpit** | axllent/mailpit | `8025:8025` | Local email testing UI |

### Service responsibilities

- **`app`** - Runs PHP-FPM, Artisan commands, migrations, tests, and OpenAPI export tasks. It is the only Laravel runtime container and is never exposed directly to the browser.
- **`nginx`** - Sole HTTP ingress for the Laravel app in local development. It serves public assets and proxies PHP requests to `app`.
- **`web`** - Runs the customer Vite dev server only. It does not own API logic, background jobs, or Laravel assets.
- **`vite-admin`** - Runs the Inertia admin Vite asset and HMR server only. It is not the admin application's browser URL.
- **`shared`** - Runs `@wikiglobe/shared` watch and build tasks so generated contracts and `dist/` stay current.
- **`db`** - PostgreSQL only. No app logic or migration orchestration should live here.
- **`redis`** - Cache, session, and queue broker only.
- **`queue`** - Runs asynchronous Laravel jobs only. No HTTP traffic, migrations, or scheduler duties.
- **`scheduler`** - Runs scheduled Laravel tasks only.
- **`mailpit`** - Local email capture and inspection only.

### Networking

- Browser traffic uses published localhost ports only: `http://localhost:8000`, `http://localhost:5173`, and `http://localhost:5174`.
- Containers talk to each other by service name: `db`, `redis`, `app`, `nginx`.
- The customer SPA calls `http://localhost:8000` in local development.
- The admin UI is opened at `http://localhost:8000/admin`; `http://localhost:5174` is only the Vite asset and HMR server.
- Vite HMR should be configured with `host: 'localhost'` and polling enabled to work reliably inside Docker on macOS and Windows.

### Volumes

- Bind-mount source code into `app`, `web`, `vite-admin`, and `shared` containers.
- Use named volumes for `vendor/`, `node_modules/`, pnpm store, Postgres data, and Redis data.
- Keep dependency directories inside Docker volumes rather than host-mounted folders for better consistency and fewer OS-specific issues.

### Local Dev Principle

- All PHP and Node commands run inside containers.
- Do not rely on host-installed PHP, Composer, Node, or pnpm for day-to-day development.
- Initial scaffolding should also run through disposable Docker containers or one-off Compose services so the repo never depends on host toolchains.
- Root helper scripts may shell into containers, but the actual work happens in Docker.

### Runtime boundaries

- Keep one responsibility per service even if multiple services share the same Docker image.
- `app`, `queue`, and `scheduler` may use the same image, but they must run different commands and be logged, restarted, and scaled independently.
- The development Compose file is for local workflow; production should use deployment-specific manifests or platform configuration rather than running the dev Compose stack unchanged.

---

## 3. Laravel Setup (`api/`)

### 3.1 Install Laravel 11

```bash
composer create-project laravel/laravel api
```

### 3.2 Install and configure packages

```bash
cd api

# API + Sanctum bootstrap
php artisan install:api

# Inertia server-side
composer require inertiajs/inertia-laravel

# Roles and permissions for admin access
composer require spatie/laravel-permission

# Code-first OpenAPI generation
composer require --dev dedoc/scramble

# Testing
composer require --dev pestphp/pest pestphp/pest-plugin-laravel
php artisan pest:install

# Admin frontend packages
pnpm add @inertiajs/react ziggy-js
pnpm add -D @vitejs/plugin-react
```

### 3.3 Auth and permissions

- **Admin panel (Inertia):** Laravel session auth with the `web` guard.
- **Customer frontend (`web/`):** Sanctum SPA cookie auth.
- **Not in scope for v1:** bearer-token auth for the first-party browser app. If mobile apps or third-party clients are introduced later, add a dedicated OAuth2/OIDC strategy rather than overloading the SPA flow.
- **Admin authorization:** use `spatie/laravel-permission` with explicit roles and permissions.

In `config/sanctum.php`:

```php
'stateful' => explode(',', env('SANCTUM_STATEFUL_DOMAINS', 'localhost:5173,localhost:5174,localhost:8000')),
```

In `config/cors.php`:

```php
'paths' => ['api/*', 'login', 'logout', 'sanctum/csrf-cookie'],
'supports_credentials' => true,
```

If additional SPA auth endpoints are added later, keep this CORS list aligned with the real browser-facing auth routes.

Recommended production session and cookie guidance:

- `SESSION_DOMAIN=.wikiglobe.com`
- `SANCTUM_STATEFUL_DOMAINS=app.wikiglobe.com,admin.wikiglobe.com,api.wikiglobe.com`
- Serve all first-party apps over HTTPS

### 3.4 Route organization

```
routes/
|- web.php       # Inertia admin routes under /admin
|- api.php       # Versioned public API under /api/v1
\- auth.php      # Shared auth endpoints such as login/logout
```

Admin routes should be prefixed and protected:

```php
// routes/web.php
Route::middleware(['auth', 'verified', 'role:admin'])
    ->prefix('admin')
    ->name('admin.')
    ->group(function () {
        Route::get('/dashboard', fn () => Inertia::render('Admin/Dashboard'))
            ->name('dashboard');
    });
```

API routes stay versioned:

```php
// routes/api.php
Route::prefix('v1')->group(function () {
    Route::apiResource('articles', ArticleController::class);
});
```

### 3.4.1 `/api/v1` contract versioning rules

- `/api/v1` is the public contract namespace for the customer application and any future first-party API consumers.
- Changes shipped under `/api/v1` must be backward compatible.
- Allowed in `v1`: new endpoints, new optional request fields, new optional or nullable response fields, additive pagination metadata, and additive enum values when consumers can safely ignore unknown values.
- Breaking changes require a new version such as `/api/v2`. Breaking changes include removing or renaming endpoints or fields, changing field types, making optional fields required, changing validation semantics incompatibly, changing status code meaning, or changing auth requirements in a way that breaks existing clients.
- Deprecations should be marked in OpenAPI, documented in the changelog, and kept functional through an announced migration window before removal in the next major API version.
- Never ship undocumented breaking changes under `/api/v1`.

### 3.5 Inertia root view

Create `resources/views/app.blade.php`:

```blade
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    @viteReactRefresh
    @vite(['resources/js/app.tsx'])
    @inertiaHead
</head>
<body>
    @inertia
</body>
</html>
```

### 3.6 API contract generation

Recommended approach for Laravel:

- Use **OpenAPI** as the contract format.
- Generate it from Laravel source code with **`dedoc/scramble`**.
- Treat Laravel routes, Form Requests, API Resources, enums, and DTOs as the contract source of truth.
- Commit the generated OpenAPI artifact so API diffs are reviewable in pull requests.

Export the contract from Laravel:

```bash
php artisan scramble:export --path=storage/app/openapi.json
```

Guidance:

- Prefer code-first OpenAPI generation over hand-maintained Swagger YAML or heavy annotation-only workflows.
- If human-readable docs are needed, render the generated OpenAPI with Swagger UI or Scalar. The source of truth remains the generated spec, not the viewer.
- Regenerate the contract whenever API routes, request validation, or response resources change.

#### Local contract workflow

1. Change Laravel routes, Form Requests, Resources, enums, or DTOs.
2. Run `pnpm contracts:sync`.
3. Review diffs in `api/storage/app/openapi.json` and `shared/src/generated/api.ts`.
4. Update API tests and frontend consumers in the same pull request.

#### CI contract workflow

CI should treat the generated OpenAPI spec and generated TypeScript artifacts as required checked-in outputs.

Recommended CI sequence:

```bash
docker compose -f docker/docker-compose.yml up -d db redis
docker compose -f docker/docker-compose.yml run --rm app composer install
docker compose -f docker/docker-compose.yml run --rm shared pnpm install --frozen-lockfile
docker compose -f docker/docker-compose.yml run --rm app php artisan scramble:export --path=storage/app/openapi.json
docker compose -f docker/docker-compose.yml run --rm shared pnpm --filter @wikiglobe/shared generate:api
git diff --exit-code -- api/storage/app/openapi.json shared/src/generated/api.ts
docker compose -f docker/docker-compose.yml run --rm shared pnpm --filter @wikiglobe/shared build
docker compose -f docker/docker-compose.yml run --rm shared pnpm --filter @wikiglobe/shared typecheck
docker compose -f docker/docker-compose.yml run --rm app php artisan test
docker compose -f docker/docker-compose.yml run --rm web pnpm --filter web test
docker compose -f docker/docker-compose.yml run --rm web pnpm -r typecheck
```

CI rules:

- Fail the build if `api/storage/app/openapi.json` is stale.
- Fail the build if `shared/src/generated/api.ts` is stale.
- Do not regenerate artifacts in a hidden CI-only step and continue; the pull request must contain the generated changes.
- Run contract generation before typecheck and tests so downstream breakage is caught against the real contract.

### 3.7 Database

- PostgreSQL 16.
- Migrations in `database/migrations/`.
- Model factories and seeders for dev data.
- Redis-backed queues, cache, and sessions.

### 3.8 Vite config for Inertia admin

`api/vite.config.ts`:

```ts
import { defineConfig } from 'vite';
import laravel from 'laravel-vite-plugin';
import react from '@vitejs/plugin-react';

export default defineConfig({
    plugins: [
        laravel({
            input: ['resources/js/app.tsx'],
            refresh: true,
        }),
        react(),
    ],
    server: {
        host: '0.0.0.0',
        port: 5174,
        hmr: {
            host: 'localhost',
            port: 5174,
        },
        watch: {
            usePolling: true,
        },
    },
});
```

---

## 4. Customer Frontend (`web/`)

### 4.1 Scaffold

```bash
pnpm create vite web --template react-ts
```

### 4.2 Key dependencies

```bash
cd web
pnpm add react-router-dom @tanstack/react-query axios
pnpm add -D tailwindcss @tailwindcss/vite
```

### 4.3 API communication

- Use `@wikiglobe/shared` for generated API types and shared client helpers.
- Set `withCredentials: true` on browser requests so Sanctum cookies are sent.
- Before login, call `/sanctum/csrf-cookie`.
- Use `VITE_API_BASE_URL=http://localhost:8000` in local development.
- The customer SPA consumes the public REST API. The admin Inertia app does not need to consume that API for normal server-rendered workflows.

### 4.4 Vite config

`web/vite.config.ts`:

```ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
    plugins: [react(), tailwindcss()],
    server: {
        host: '0.0.0.0',
        port: 5173,
        hmr: {
            host: 'localhost',
            port: 5173,
        },
        watch: {
            usePolling: true,
        },
    },
});
```

---

## 5. Shared Package (`shared/`)

### 5.1 package.json

```json
{
    "name": "@wikiglobe/shared",
    "version": "0.1.0",
    "private": true,
    "type": "module",
    "main": "./dist/index.js",
    "module": "./dist/index.js",
    "types": "./dist/index.d.ts",
    "exports": {
        ".": {
            "types": "./dist/index.d.ts",
            "import": "./dist/index.js"
        },
        "./package.json": "./package.json"
    },
    "files": [
        "dist"
    ],
    "scripts": {
        "build": "tsup src/index.ts --format esm --dts --clean",
        "dev": "tsup src/index.ts --format esm --dts --watch",
        "generate:api": "openapi-typescript ../api/storage/app/openapi.json -o src/generated/api.ts",
        "typecheck": "tsc --noEmit"
    },
    "dependencies": {
        "openapi-fetch": "^0.10.6"
    },
    "devDependencies": {
        "openapi-typescript": "^7.6.1",
        "tsup": "^8.2.4",
        "typescript": "^5.5.0"
    }
}
```

### 5.2 Contents

- **`src/generated/api.ts`** - Generated TypeScript contract artifacts from Laravel OpenAPI.
- **`src/client/`** - Thin shared HTTP client utilities used by `web/` and any future API-first consumers.
- **`src/types/`** - Stable hand-authored cross-app types that are not direct API shapes.
- **`src/index.ts`** - Public package entrypoint that re-exports supported modules.

In development, keep the package current with a dedicated watcher container that runs `pnpm --filter @wikiglobe/shared dev` so `dist/` stays fresh for consumers.

### 5.3 Rules

- Consume the package via `workspace:*` only.
- Do not alias apps directly to `../shared/src`.
- Do not hand-maintain mirrored request and response contracts that already exist in OpenAPI.
- If runtime schemas are needed later, generate them from the OpenAPI spec rather than maintaining separate manual Zod mirrors forever.

### 5.4 Consumption

Both `web/` and `api/` reference the package through pnpm workspaces:

```json
{
    "dependencies": {
        "@wikiglobe/shared": "workspace:*"
    }
}
```

---

## 6. pnpm Workspace Config

`pnpm-workspace.yaml`:

```yaml
packages:
    - 'web'
    - 'shared'
    - 'api'
```

Root `package.json`:

```json
{
    "name": "wikiglobe",
    "private": true,
    "scripts": {
        "dev": "docker compose -f docker/docker-compose.yml up --build",
        "dev:down": "docker compose -f docker/docker-compose.yml down",
        "shared:build": "docker compose -f docker/docker-compose.yml exec shared pnpm --filter @wikiglobe/shared build",
        "contracts:export": "docker compose -f docker/docker-compose.yml exec app php artisan scramble:export --path=storage/app/openapi.json",
        "contracts:generate": "docker compose -f docker/docker-compose.yml exec shared pnpm --filter @wikiglobe/shared generate:api",
        "contracts:sync": "docker compose -f docker/docker-compose.yml exec app php artisan scramble:export --path=storage/app/openapi.json && docker compose -f docker/docker-compose.yml exec shared pnpm --filter @wikiglobe/shared generate:api && docker compose -f docker/docker-compose.yml exec shared pnpm --filter @wikiglobe/shared build",
        "contracts:check": "pnpm contracts:export && pnpm contracts:generate && git diff --exit-code -- api/storage/app/openapi.json shared/src/generated/api.ts",
        "typecheck": "docker compose -f docker/docker-compose.yml exec web pnpm -r typecheck",
        "lint": "docker compose -f docker/docker-compose.yml exec web pnpm -r lint",
        "test:api": "docker compose -f docker/docker-compose.yml exec app php artisan test",
        "test:web": "docker compose -f docker/docker-compose.yml exec web pnpm --filter web test",
        "test:shared": "docker compose -f docker/docker-compose.yml exec web pnpm --filter @wikiglobe/shared test"
    }
}
```

Note: these scripts assume the Compose stack is already running.

---

## 7. Environment Variables

### 7.1 Root `.env.example`

Use the root env file for Docker Compose interpolation only:

```env
COMPOSE_PROJECT_NAME=wikiglobe
FORWARD_NGINX_PORT=8000
FORWARD_WEB_PORT=5173
FORWARD_ADMIN_PORT=5174
FORWARD_DB_PORT=5432
FORWARD_REDIS_PORT=6379
FORWARD_MAILPIT_PORT=8025
```

### 7.2 `api/.env.example`

```env
APP_NAME=WikiGlobe
APP_ENV=local
APP_KEY=
APP_DEBUG=true
APP_URL=http://localhost:8000

FRONTEND_URL=http://localhost:5173
ADMIN_URL=http://localhost:8000/admin

DB_CONNECTION=pgsql
DB_HOST=db
DB_PORT=5432
DB_DATABASE=wikiglobe
DB_USERNAME=wikiglobe
DB_PASSWORD=secret

REDIS_HOST=redis
REDIS_PORT=6379

SESSION_DRIVER=redis
SESSION_DOMAIN=localhost
SANCTUM_STATEFUL_DOMAINS=localhost:5173,localhost:5174,localhost:8000

MAIL_MAILER=smtp
MAIL_HOST=mailpit
MAIL_PORT=1025
MAIL_FROM_ADDRESS=hello@wikiglobe.test
MAIL_FROM_NAME="${APP_NAME}"
```

### 7.3 `web/.env.example`

```env
VITE_APP_NAME=WikiGlobe
VITE_API_BASE_URL=http://localhost:8000
```

Rules:

- Server secrets live only in `api/.env`.
- Public browser configuration lives only in `web/.env` and must use the `VITE_` prefix.
- The root `.env` is for Docker-only configuration, not application secrets.

---

## 8. Implementation Order

1. **Initialize monorepo** - Create root `package.json`, `pnpm-workspace.yaml`, `.gitignore`, and root Docker Compose env.
2. **Scaffold `shared/`** - Create the real buildable package, `src/index.ts`, and `dist` build flow.
3. **Scaffold `api/`** - Install Laravel, Sanctum, Inertia, Spatie permission, Scramble, and configure admin Vite.
4. **Generate first API contract** - Export `api/storage/app/openapi.json` from Laravel.
5. **Wire `shared/` to contracts** - Generate `shared/src/generated/api.ts` from the OpenAPI artifact.
6. **Scaffold `web/`** - Install React app dependencies and consume `@wikiglobe/shared`.
7. **Docker Compose** - Add app, nginx, web, vite-admin, shared, db, redis, queue, scheduler, and mailpit services. Verify HMR, DB, Redis, email, and contract generation work inside Docker.
8. **Auth flow** - Implement Sanctum SPA auth for `web/` and session auth for the admin.
9. **First feature** - Build a single CRUD resource end-to-end: migration -> model -> controller -> API Resource -> OpenAPI export -> generated TS contracts -> Inertia admin page -> customer frontend page.

---

## 9. Notes

- **Tailwind CSS** is used in both `web/` and the Inertia admin. Each keeps its own config.
- **Testing** - Pest for Laravel, Vitest for `web/` and `shared/`, and a small Playwright suite for critical end-to-end flows.
- **CI** - Run contract export, regenerate shared artifacts, fail on stale generated files, then run typecheck, lint, tests, and builds.
- **Deployment** - Build one Laravel image and run it as `app`, `queue`, and `scheduler`; use managed Postgres and Redis; deploy `web/` as static assets behind a CDN.
- **Future expansion** - If mobile apps or third-party API consumers are introduced, add a separate OAuth2/OIDC strategy instead of changing the first-party SPA auth model.

---

## 10. Production Readiness Checklist

- Every API-changing pull request updates `api/storage/app/openapi.json`, `shared/src/generated/api.ts`, and affected tests.
- `shared/` builds successfully from a clean container and never relies on direct source aliasing.
- Docker service boundaries remain clear: HTTP in `nginx`, PHP runtime in `app`, jobs in `queue`, schedules in `scheduler`, contracts/build watch in `shared`.
- `/api/v1` remains backward compatible until a deliberate `/api/v2` is introduced.
- Contract generation and stale-artifact checks are mandatory CI gates, not optional documentation steps.
