# 17 — RBAC: Role-Gated Writes, Public Reads

> **Status: 🟡 Partial** — verified 2026-06-15; remaining work tracked in [STATUS.md](STATUS.md).

> Resolves the Final-Report open issue: *"RBAC enforcement — roles are seeded via
> spatie/laravel-permission and writes are auth-gated, but fine-grained per-endpoint permissions and
> Policy classes are staged for the editorial-hardening phase."*

## Guiding principle (from the product owner)

> **The `/api/v1` read API does not need roles — only CRUD/write operations need roles.**

So: **all `GET /api/v1/*` stay public and unauthenticated.** Authorization is added *only* to the
write/editorial surfaces (the `auth:sanctum` API writes and the `auth,verified` admin Inertia routes).

## Current state (verified)

- `spatie/laravel-permission` installed; `User` uses `HasRoles` (`api/app/Models/User.php`).
- `database/seeders/RoleSeeder.php` seeds 5 roles — `admin, moderator, geo_moderator,
  history_moderator, user` — **with no permissions** ("policy enforcement deferred").
- **No `role:`/`permission:` middleware applied anywhere; no Policy classes; no gates.**
- `api/routes/api.php`: GET reads are **public** (good — keep as is); writes live under
  `Route::middleware('auth:sanctum')->group(...)` (POST/PUT/DELETE entities, geo-refs, relationships,
  sources, `reference/cache/clear`).
- `api/routes/web.php`: admin CRUD under `Route::middleware(['auth','verified'])` (entities, geometry
  periods, relationships, reference tables, chronicles).
- `POST /api/v1/map/resolve-ohm-feature` is currently **public and outside** the auth group — see
  "Open question" below.
- spatie auto-registers the `role`, `permission`, `role_or_permission` middleware aliases (Laravel 11+).

## Design

Use **permissions** (not bare role names) at the route layer for flexibility, plus a couple of
**Policies** for record-level/sensitive actions. Roles are bundles of permissions.

### Permission set
| Permission | Covers |
|---|---|
| `entities.write` | create/update/delete entities (admin + API) |
| `entities.verify` | change `verification_status` (sensitive promotion) |
| `relationships.write` | create/update/delete relationships |
| `geometry.write` | geometry periods + entity geo-references + OHM feature resolution |
| `chronicles.write` | create/update/delete chronicles + entries |
| `sources.write` | create/update sources |
| `reference.manage` | reference-table admin + `reference/cache/clear` |

### Role → permission matrix (starting point — tune as needed)
| Role | Permissions |
|---|---|
| `admin` | **all** (grant via Gate::before super-admin, see below) |
| `moderator` | entities.write, entities.verify, relationships.write, chronicles.write, sources.write |
| `history_moderator` | entities.write, relationships.write, chronicles.write, sources.write |
| `geo_moderator` | geometry.write |
| `user` | *(none — authenticated but read-only)* |

## Implementation steps

### 1. Seed permissions + assignments
Create `database/seeders/PermissionSeeder.php` (idempotent; run after `RoleSeeder`):
```php
use Spatie\Permission\Models\{Role, Permission};

$perms = ['entities.write','entities.verify','relationships.write','geometry.write',
          'chronicles.write','sources.write','reference.manage'];
foreach ($perms as $p) { Permission::firstOrCreate(['name' => $p]); }

Role::findByName('moderator')->syncPermissions(
    ['entities.write','entities.verify','relationships.write','chronicles.write','sources.write']);
Role::findByName('history_moderator')->syncPermissions(
    ['entities.write','relationships.write','chronicles.write','sources.write']);
Role::findByName('geo_moderator')->syncPermissions(['geometry.write']);
// 'admin' gets everything via Gate::before; 'user' gets none.
```
Register it in `DatabaseSeeder` after `RoleSeeder::class`.

Add a super-admin shortcut in `AppServiceProvider::boot()`:
```php
Gate::before(fn ($user, $ability) => $user->hasRole('admin') ? true : null);
```

### 2. Enforce on API writes — `api/routes/api.php`
Keep the public GET block untouched. Inside the existing `auth:sanctum` group, split by permission:
```php
Route::middleware('auth:sanctum')->group(function () {
    Route::get('user', ...);

    Route::middleware('permission:entities.write')->group(function () {
        Route::post('entities', ...);
        Route::put('entities/{entity}', ...);
        Route::delete('entities/{entity}', ...);
    });
    Route::middleware('permission:geometry.write')->group(function () {
        // entity geo-reference writes
    });
    Route::middleware('permission:relationships.write')->group(function () { /* ... */ });
    Route::middleware('permission:sources.write')->group(function () { /* ... */ });
    Route::middleware('permission:reference.manage')->post('reference/cache/clear', ...);
});
```

### 3. Enforce on admin Inertia writes — `api/routes/web.php`
Keep `['auth','verified']`; wrap each resource's **write** verbs (store/update/destroy) in the
matching `permission:` middleware. Leave the admin **index/show** pages viewable by any authenticated,
verified user (or gate them too if the admin should be fully role-restricted — product decision).

### 4. Record-level Policy for the sensitive action
`app/Policies/EntityPolicy.php` with a `verify(User $user, Entity $e)` ability requiring
`entities.verify`; call `$this->authorize('verify', $entity)` in the verify path (controller/Action or
a `FormRequest::authorize()`), so promoting `verification_status` needs the dedicated permission even
if a user can otherwise edit entities.

### 5. Role assignment for real users
Provide an artisan command `app/Console/Commands/AssignRoleCommand.php`
(`php artisan user:role {email} {role}`) — or document `$user->assignRole('admin')` via tinker.
**Assign roles to all current editors before deploying enforcement** (see rollout).

### 6. Explicitly keep reads public
Do **not** add any middleware to the `GET /api/v1/*` routes. Add a regression test that asserts this.

## Open question to confirm
`POST /api/v1/map/resolve-ohm-feature` is public today. It is an **editorial** helper (resolves an OHM
feature for the geometry editor), so it most likely belongs under `auth:sanctum` +
`permission:geometry.write`. **Confirm it is not consumed by the public atlas SPA** before moving it;
if it is purely an editor tool, gate it.

## Testing / acceptance

`tests/Feature/Authorization/...`:
- **Reads stay public:** unauthenticated `GET /api/v1/entities`, `/entities/map`, `/chronicles` → 200.
- **Write needs permission:** authenticated `user` (no perms) `POST /api/v1/entities` → 403.
- **Granted permission works:** user with `entities.write` → 201; with only `geometry.write`,
  `POST /api/v1/entities` → 403 but geometry write → 2xx.
- **Admin bypass:** `admin` can perform every write (Gate::before).
- **Verify gate:** editor with `entities.write` but not `entities.verify` cannot change
  `verification_status`.
- **Admin web routes:** write verbs blocked without the matching permission.

**Acceptance:** all reads public; every write path requires the correct permission; the role→permission
seeder is idempotent; the above tests pass in CI (against the real PostGIS test DB).

## Rollout (ordering matters)
1. Ship the seeder + `HasRoles` (already present) and **assign roles to existing editors** first.
2. Then deploy the route/middleware enforcement. Doing it in this order avoids locking current editors
   out (they currently pass on `auth` alone; after enforcement they need a role with permissions).
3. Seed runs on `migrate --seed`; for an existing DB, run `php artisan db:seed --class=PermissionSeeder`.

## Effort & risk
- **Effort:** ~1–1.5 days incl. tests.
- **Risk:** medium — mis-ordered rollout could block editors (mitigated by step-1 assignment first);
  the `resolve-ohm-feature` decision needs confirmation. Reads are untouched, so the public atlas is
  unaffected.
