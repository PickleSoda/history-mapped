# WikiGlobe - Monorepo Setup Guide

## Overview

WikiGlobe is a monorepo containing:

- **`api/`** - Laravel 13 backend with Inertia.js (React) for the admin panel, and a REST API for the customer frontend.
- **`web/`** - React (Vite) customer-facing frontend (stub — not yet connected to the API).

Package manager: **pnpm** with workspaces.  
Local dev environment: **fully dockerized with Docker Compose**.

---

## 0. Foundation Decisions

- **Admin architecture** - The admin lives inside Laravel as an Inertia React app. It is not a separate SPA and does not consume the public REST API for routine page rendering.
- **Customer auth model** - The customer frontend is a first-party SPA and uses **Laravel Sanctum SPA cookie auth**. This keeps browser auth aligned with Laravel sessions and avoids token storage in the browser.
- **API contract strategy** - Laravel is the source of truth for routes, validation, and response shapes. The OpenAPI spec can be exported via `dedoc/scramble` for documentation and contract review.
- **Development model** - Development is fully dockerized. PHP, Node, Vite, Composer, pnpm, queue workers, and supporting services all run in containers.
- **Deployment model** - Deploy the Laravel app, queue worker, and scheduler as separate processes from the same application image. Deploy `web/` separately as static assets behind a CDN.

---

## 1. Repository Structure

```
wikiglobe/
|- api/                         # Laravel 13 application
|  |- app/
|  |- bootstrap/
|  |- config/
|  |- database/
|  |- resources/
|  |  \- js/                   # Inertia React admin frontend
|  |     |- pages/
|  |     |- components/
|  |     |- layouts/
|  |     \- app.tsx
|  |- routes/
|  |  |- web.php               # Inertia admin routes
|  |  |- api.php               # Public API routes
|  |  \- auth.php              # Login/logout/password routes
|  |- storage/
|  |  \- app/
|  |     \- openapi.json       # Generated OpenAPI artifact (optional)
|  |- composer.json
|  |- vite.config.ts           # Vite config for Inertia admin assets
|  |- tsconfig.json
|  \- package.json             # Admin frontend package deps
|
|- web/                         # Customer-facing React SPA (stub)
|  |- src/
|  |  |- pages/
|  |  |- components/
|  |  |- lib/
|  |  \- main.tsx
|  |- vite.config.ts
|  |- tsconfig.json
|  \- package.json
|
|- docker/
|  |- api/
|  |  |- Dockerfile            # PHP 8.4-FPM + Composer
|  |  \- nginx.conf
|  |- db/
|  |  |- Dockerfile            # PostGIS + pgvector on Postgres 16
|  |  \- init-extensions.sql   # Creates vector and postgis extensions
|  |- web/
|  |  \- Dockerfile            # Node for Vite/web workspace commands
|  |- admin/
|  |  \- Dockerfile            # Node for Inertia Vite server
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
| **composer-install** | PHP 8.4-FPM | - | One-shot: runs `composer install` before app starts |
| **app** | PHP 8.4-FPM | - | Laravel app container for PHP-FPM |
| **nginx** | nginx:1.27-alpine | `8000:80` | Public local entrypoint for Laravel |
| **pnpm-install** | node (web Dockerfile) | - | One-shot: runs `pnpm install` before JS services start |
| **web** | node (web Dockerfile) | `5173:5173` | Customer Vite dev server (`@wikiglobe/web`) |
| **vite-admin** | PHP 8.4-FPM image | `5174:5174` | Inertia admin Vite dev server (`@wikiglobe/api`) |
| **db** | Custom PostGIS + pgvector on Postgres 16 | `5432:5432` | Primary database with PostGIS and pgvector extensions |
| **redis** | redis:7-alpine | `6379:6379` | Cache, sessions, queues |
| **queue** | same as `app` | - | Runs `php artisan queue:work` |
| **scheduler** | same as `app` | - | Runs Laravel scheduler loop |
| **mailpit** | axllent/mailpit | `8025:8025` | Local email testing UI |
| **cloudbeaver** | dbeaver/cloudbeaver | `8978:8978` | Web-based DB admin GUI |
| **redisinsight** | redis/redisinsight | `5540:5540` | Redis inspection UI |

### Service responsibilities

- **`composer-install`** - Runs `composer install` once as a prerequisite for `app`, `queue`, `scheduler`, and `vite-admin`. Uses a named Docker volume for `vendor/`.
- **`app`** - Runs PHP-FPM. It is the only Laravel PHP runtime and is never exposed directly to the browser.
- **`nginx`** - Sole HTTP ingress for the Laravel app in local development. Serves public assets and proxies PHP requests to `app`.
- **`pnpm-install`** - Runs `pnpm install` once as a prerequisite for `web` and `vite-admin`. Uses named volumes for `node_modules/`.
- **`web`** - Runs the customer Vite dev server (`pnpm --filter @wikiglobe/web dev`). Does not own API logic or Laravel assets.
- **`vite-admin`** - Runs the Inertia admin Vite asset and HMR server (`pnpm --filter @wikiglobe/api dev`). Not the admin application's browser URL.
- **`db`** - PostgreSQL with PostGIS and pgvector extensions. No app logic or migration orchestration should live here.
- **`redis`** - Cache, session, and queue broker only.
- **`queue`** - Runs asynchronous Laravel jobs only. No HTTP traffic, migrations, or scheduler duties.
- **`scheduler`** - Runs scheduled Laravel tasks only.
- **`mailpit`** - Local email capture and inspection only.

### Networking

- Browser traffic uses published localhost ports only: `http://localhost:8000`, `http://localhost:5173`, and `http://localhost:5174`.
- Containers talk to each other by service name: `db`, `redis`, `app`, `nginx`.
- The customer SPA calls `http://localhost:8000` in local development.
- The admin Inertia app is opened at `http://localhost:8000`; `http://localhost:5174` is only the Vite asset and HMR server.
- Vite HMR should be configured with `host: 'localhost'` and polling enabled to work reliably inside Docker on macOS and Windows.

### Volumes

- Bind-mount source code into `app`, `web`, `vite-admin` containers.
- Use named volumes for `vendor/`, `node_modules/`, pnpm store, Postgres data, and Redis data.
- Keep dependency directories inside Docker volumes rather than host-mounted folders for better consistency and fewer OS-specific issues.

### Local Dev Principle

- All PHP and Node commands run inside containers.
- Do not rely on host-installed PHP, Composer, Node, or pnpm for day-to-day development.
- Root helper scripts may shell into containers, but the actual work happens in Docker.

### Runtime boundaries

- Keep one responsibility per service even if multiple services share the same Docker image.
- `app`, `queue`, and `scheduler` may use the same image, but they must run different commands and be logged, restarted, and scaled independently.
- The development Compose file is for local workflow; production should use deployment-specific manifests or platform configuration rather than running the dev Compose stack unchanged.

---

## 3. Laravel Setup (`api/`)

### 3.1 Install Laravel 13

```bash
composer create-project laravel/laravel api
```

### 3.2 Install and configure packages

```bash
cd api

# API routing bootstrap (Sanctum is built into Laravel 13)
php artisan install:api

# Inertia server-side
composer require inertiajs/inertia-laravel

# Code-first OpenAPI generation (optional, for contract review)
composer require dedoc/scramble

# pgvector PHP helpers
composer require pgvector/pgvector

# PostgreSQL enhanced (enums, full-text search, etc.)
composer require tpetry/laravel-postgresql-enhanced

# Roles and permissions for admin access
composer require spatie/laravel-permission

# Admin frontend packages
pnpm add @inertiajs/react
pnpm add -D @vitejs/plugin-react
```

### 3.3 Auth and permissions

- **Admin panel (Inertia):** Laravel session auth with the `web` guard, via `laravel/fortify`.
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

Recommended production session and cookie guidance:

- `SESSION_DOMAIN=.wikiglobe.com`
- `SANCTUM_STATEFUL_DOMAINS=app.wikiglobe.com,admin.wikiglobe.com,api.wikiglobe.com`
- Serve all first-party apps over HTTPS

### 3.4 Route organization

```
routes/
|- web.php       # Inertia admin routes (no prefix — root paths)
|- api.php       # Versioned public API under /api/v1
\- auth.php      # Login/logout/password routes (via Fortify)
```

Admin routes are protected by `auth` and `verified` middleware but are **not** under an `/admin` URL prefix. They are bare paths:

```php
// routes/web.php
Route::middleware(['auth', 'verified'])->group(function () {
    Route::inertia('dashboard', 'dashboard')->name('dashboard');
    Route::get('entities', [EntityController::class, 'index'])->name('entities.index');
    Route::get('entities/{entity}', [EntityController::class, 'show'])->name('entities.show');
    // reference table routes under /reference/...
});
```

API routes stay versioned:

```php
// routes/api.php
Route::prefix('v1')->group(function () {
    Route::apiResource('entities', EntityController::class);
    Route::get('entities/map', [EntityController::class, 'map']);
});
```

### 3.4.1 `/api/v1` contract versioning rules

- `/api/v1` is the public contract namespace for the customer application and any future first-party API consumers.
- Changes shipped under `/api/v1` must be backward compatible.
- Allowed in `v1`: new endpoints, new optional request fields, new optional or nullable response fields, additive pagination metadata, and additive enum values when consumers can safely ignore unknown values.
- Breaking changes require a new version such as `/api/v2`. Breaking changes include removing or renaming endpoints or fields, changing field types, making optional fields required, changing validation semantics incompatibly, changing status code meaning, or changing auth requirements in a way that breaks existing clients.
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

OpenAPI can be exported from Laravel source code using `dedoc/scramble`:

```bash
php artisan scramble:export --path=storage/app/openapi.json
```

This is useful for contract review in pull requests and for generating API documentation. Regenerate whenever routes, Form Requests, or API Resources change.

### 3.7 Database

- PostgreSQL 16 with PostGIS and pgvector extensions enabled via `docker/db/init-extensions.sql`.
- Migrations in `database/migrations/`.
- Model factories and seeders for dev data.
- Redis-backed queues, cache, and sessions.
- Test database: `wikiglobe_test` on the same `db` service (configured in `phpunit.xml`).

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

The `web/` package is a Vite + React TypeScript app. It is currently a stub and not yet connected to the API. It runs as the `web` Docker service at `http://localhost:5173`.

### 4.1 Key dependencies (planned)

```bash
cd web
pnpm add react-router-dom @tanstack/react-query axios
pnpm add -D tailwindcss @tailwindcss/vite
```

### 4.2 API communication (planned)

- Set `withCredentials: true` on browser requests so Sanctum cookies are sent.
- Before login, call `/sanctum/csrf-cookie`.
- Use `VITE_API_BASE_URL=http://localhost:8000` in local development.
- The customer SPA will consume the public REST API (`/api/v1`). The admin Inertia app does not consume that API for normal server-rendered workflows.

### 4.3 Vite config

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

## 5. pnpm Workspace Config

`pnpm-workspace.yaml`:

```yaml
packages:
    - 'api'
    - 'web'
```

Root `package.json`:

```json
{
    "name": "wikiglobe",
    "private": true,
    "scripts": {
        "dev": "docker compose -f docker/docker-compose.yml up --build",
        "dev:down": "docker compose -f docker/docker-compose.yml down",
        "test:api": "docker compose -f docker/docker-compose.yml exec app php artisan test",
        "typecheck": "docker compose -f docker/docker-compose.yml exec web pnpm -r typecheck",
        "lint": "docker compose -f docker/docker-compose.yml exec web pnpm -r lint"
    }
}
```

Note: these scripts assume the Compose stack is already running.

---

## 6. Environment Variables

### 6.1 Root `.env.example`

Use the root env file for Docker Compose interpolation only:

```env
COMPOSE_PROJECT_NAME=wikiglobe
FORWARD_NGINX_PORT=8000
FORWARD_WEB_PORT=5173
FORWARD_ADMIN_PORT=5174
FORWARD_DB_PORT=5432
FORWARD_REDIS_PORT=6379
FORWARD_MAILPIT_PORT=8025
FORWARD_CLOUDBEAVER_PORT=8978
FORWARD_REDISINSIGHT_PORT=5540
```

### 6.2 `api/.env.example`

```env
APP_NAME=WikiGlobe
APP_ENV=local
APP_KEY=
APP_DEBUG=true
APP_URL=http://localhost:8000

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

### 6.3 `web/.env.example`

```env
VITE_APP_NAME=WikiGlobe
VITE_API_BASE_URL=http://localhost:8000
```

Rules:

- Server secrets live only in `api/.env`.
- Public browser configuration lives only in `web/.env` and must use the `VITE_` prefix.
- The root `.env` is for Docker-only configuration, not application secrets.

---

## 7. Testing

- **Framework:** PHPUnit v12 (not Pest). Tests live in `api/tests/`.
- **Test database:** PostgreSQL `wikiglobe_test` on the `db` service (configured in `phpunit.xml` via `DB_DATABASE=wikiglobe_test`).
- **Run all tests:** `php artisan test --compact` (inside the `app` container).
- **Run a single file:** `php artisan test --compact tests/Feature/ExampleTest.php`.
- **Run by filter:** `php artisan test --compact --filter=testName`.
- Every code change must be covered by a test. Write unit tests in `tests/Unit/` and feature tests in `tests/Feature/`.

---

## 8. Notes

- **Tailwind CSS** is used in the Inertia admin. `web/` will use its own config when developed.
- **CI** - Run PHP tests, typecheck, lint. If OpenAPI contract review is needed, export the spec and fail on stale diffs.
- **Deployment** - Build one Laravel image and run it as `app`, `queue`, and `scheduler`; use managed Postgres and Redis; deploy `web/` as static assets behind a CDN.
- **Future expansion** - If mobile apps or third-party API consumers are introduced, add a separate OAuth2/OIDC strategy instead of changing the first-party SPA auth model.

---

## 9. Production Readiness Checklist

- Admin routes are protected by `auth` and `verified` middleware.
- `/api/v1` remains backward compatible until a deliberate `/api/v2` is introduced.
- Docker service boundaries remain clear: HTTP in `nginx`, PHP runtime in `app`, jobs in `queue`, schedules in `scheduler`.
- Test database (`wikiglobe_test`) is isolated from the development database (`wikiglobe`).
- All PHP changes are formatted with `vendor/bin/pint --dirty` before committing.
