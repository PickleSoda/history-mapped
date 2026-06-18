# 16 — Expose the OpenAPI (Scramble) Documentation UI

> **Status: ✅ Executed** — implemented & tested 2026-06-15 (commit `fd6b69f`, branch `feat/openapi-docs-exposure`). See [STATUS.md](../../plans/STATUS.md).

> Resolves the Final-Report open issue: *"OpenAPI/Swagger UI — the schema is generated from the
> typed request/resource layer via Scramble, but the interactive docs route is not yet publicly
> exposed."*

## Goal

Make the OpenAPI documentation for `/api/v1` reliably available and useful:

- A browsable UI and a machine-readable spec, scoped to the `v1` API.
- The Sanctum-protected write endpoints documented with their security scheme (so consumers see
  which endpoints require auth).
- Sensible, intentional access control for the docs in **production** (today it 403s there).

## Current state (verified)

- `dedoc/scramble: ^0.13.16` is installed (`api/composer.json`). The service provider auto-registers.
- **No `config/scramble.php`** — running on vendor defaults:
  - `api_path => 'api'` (documents every `/api/*` route, including `/api/v1/*`).
  - UI served at **`GET /docs/api`** (Stoplight Elements); spec at **`GET /docs/api.json`**.
  - Docs middleware: `['web', RestrictedDocsAccess::class]`.
- `RestrictedDocsAccess` behaviour: **open when `APP_ENV=local`**; otherwise requires
  `Gate::allows('viewApiDocs')`. **No `viewApiDocs` gate is defined**, so in any non-local
  environment the docs currently **return 403**.
- Auth: SPA uses **Sanctum cookie** auth (`SANCTUM_STATEFUL_DOMAINS` set; `cors.supports_credentials
  => true`). Write routes in `api/routes/api.php` are grouped under `auth:sanctum`.

So the UI already exists in dev — the work is (1) scope + brand the spec, (2) document the auth
scheme, and (3) make a deliberate production-access decision instead of the accidental 403.

## Design decisions

1. **Scope the docs to `v1`.** Set `api_path => 'api/v1'` so the spec is exactly the public contract,
   not internal/admin routes.
2. **Production access = admin-gated by default, with an opt-out.** The read API is public, but
   publishing the *full* schema (including write endpoints) is a minor information-disclosure choice.
   Default to gating the docs UI behind `role:admin` in production; allow a config/env flag
   (`SCRAMBLE_DOCS_PUBLIC=true`) to make them fully public if desired. This depends on the
   `role:admin` capability delivered in **plan 17** (RBAC).
3. **Document the Sanctum security scheme** so protected endpoints render a lock and consumers know a
   token/session is required.

## Implementation steps

### 1. Publish and configure Scramble
```bash
docker compose -f docker/docker-compose.yml exec app \
  php artisan vendor:publish --tag=scramble-config
```
Edit `api/config/scramble.php`:
```php
'api_path' => 'api/v1',
'info' => [
    'version' => env('API_VERSION', '1.0.0'),
    'description' => 'history-mapped — public read API and editorial write API for the interactive historical atlas.',
],
// 'servers' => null  // auto-detect; or set ['Production' => 'https://api.example.org']
```

### 2. Define the production access gate + security scheme
In `api/app/Providers/AppServiceProvider.php` `boot()`:
```php
use Dedoc\Scramble\Scramble;
use Dedoc\Scramble\Support\Generator\OpenApi;
use Dedoc\Scramble\Support\Generator\SecurityScheme;
use Illuminate\Support\Facades\Gate;

// Who may view the docs UI in non-local environments.
Gate::define('viewApiDocs', function ($user = null) {
    if (config('scramble.docs_public', env('SCRAMBLE_DOCS_PUBLIC', false))) {
        return true;
    }
    return $user?->hasRole('admin') ?? false;   // requires plan 17 (HasRoles already on User)
});

// Document Sanctum auth so protected endpoints show as secured.
Scramble::configure()->withDocumentTransformers(function (OpenApi $openApi) {
    $openApi->secScheme(SecurityScheme::http('bearer')); // Sanctum personal-access token
    // Note: the SPA itself authenticates via cookie + CSRF; the bearer scheme documents
    // programmatic/token consumers.
});
```
> Verify exact transformer/security API against the installed Scramble 0.13.x (minor versions differ
> slightly: `withDocumentTransformers` vs `extendOpenApi`). Add `'docs_public' => env('SCRAMBLE_DOCS_PUBLIC', false)`
> to `config/scramble.php` if you want the config-driven toggle.

### 3. (Optional) friendlier entry point + admin link
- Add a redirect so `/api/docs` → `/docs/api` for discoverability (`routes/web.php`).
- Add a "API Docs" link in the admin sidebar pointing at `/docs/api`.

### 4. Document the env var
Add to `api/.env.example`:
```
# Expose the OpenAPI docs UI publicly in non-local environments (default: admin-only)
SCRAMBLE_DOCS_PUBLIC=false
```

## Testing / acceptance

- **Feature test** `tests/Feature/ApiDocsTest.php`:
  - `GET /docs/api.json` returns 200 and the JSON contains the key paths
    (`/api/v1/entities`, `/api/v1/entities/map`, `/api/v1/chronicles`).
  - The spec marks `POST /api/v1/entities` with a security requirement and omits non-`v1` routes.
  - With `APP_ENV != local` and `SCRAMBLE_DOCS_PUBLIC=false`: an unauthenticated `GET /docs/api`
    is forbidden; an `admin` user gets 200; with `SCRAMBLE_DOCS_PUBLIC=true` it is public.
- **Manual:** open `http://localhost:8000/docs/api` — endpoints render, "Try it" works for reads.

**Acceptance:** docs reachable in dev and (per policy) in prod; spec scoped to `v1`; protected
endpoints show auth; one feature test green in CI.

## Effort & risk

- **Effort:** ~0.5 day.
- **Risk:** low. The only cross-dependency is `role:admin` (plan 17) for the prod gate; until that
  lands, set `SCRAMBLE_DOCS_PUBLIC=true` or gate on `auth` only.
