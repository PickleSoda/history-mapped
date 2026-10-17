# User accounts, saved items and text contributions — design

Date: 2026-10-18 · Status: implemented (uncommitted)

Public-facing account features for the Atlas SPA (`web/`): sign in / register,
default permissions for registered users, starring + folders for chronicles,
entities and relationships, and a "suggest an edit" contribution tool whose
submissions are stored as diffs and reviewed by staff in the Inertia admin.

## 1. Auth

Sanctum **cookie** (stateful SPA) auth — already wired (`statefulApi()`, CORS
`supports_credentials`, `getCsrfCookie()`). The SPA calls Fortify's JSON
endpoints directly; the API host sets the session cookie.

| Call | Body | Result |
|---|---|---|
| `GET /sanctum/csrf-cookie` | – | sets `XSRF-TOKEN` (call before any mutation) |
| `POST /login` | `email, password, remember?` | `200 {two_factor:false}` · `200 {two_factor:true}` (2FA pending) · `422 errors.email` · `429` |
| `POST /two-factor-challenge` | `code` or `recovery_code` | `204` · `422` |
| `POST /register` | `name, email, password, password_confirmation` | `201` (now logged in) · `422` |
| `POST /logout` | – | `204` |
| `POST /forgot-password` | `email` | `200 {message}` (reset link opens the admin-host reset page) |
| `GET /api/v1/me` | – | `200 {data: Me}` · `401` guest |

```ts
Me = {
  id: number; name: string; email: string;
  roles: string[];
  can: { access_admin: boolean; contribute: boolean; review_contributions: boolean };
  admin_url: string;               // APP_URL/dashboard
}
```

Axios must send `withXSRFToken: true` (cross-origin dev: `:5173` → `:8000`).
Production needs the SPA and API on one registrable domain with
`SESSION_DOMAIN=.<domain>`, `SANCTUM_STATEFUL_DOMAINS=<web host>` and
`FRONTEND_URL=https://<web host>`.

## 2. Default permissions

New permissions (in `PermissionSeeder`):

| Permission | Meaning |
|---|---|
| `admin.access` | enter the Inertia admin panel at all (read pages) |
| `contributions.create` | submit text corrections |
| `contributions.review` | approve / reject contributions |

Role matrix additions: `moderator` and `history_moderator` get all three;
`geo_moderator` gets `admin.access` + `contributions.create`; `user` gets
`contributions.create`. `admin` still bypasses everything via `Gate::before`.

* Registration (`CreateNewUser`) assigns the `user` role.
* Every Inertia admin route (dashboard, entities, chronicles, reference, AI)
  now sits behind `permission:admin.access`. Settings pages stay open to any
  signed-in user. A non-staff login on the admin host is redirected to
  `FRONTEND_URL` instead of a 403.
* Migration `seed_rbac_and_backfill_user_roles` runs the role/permission
  seeders (prod deploys only run `migrate`) and gives every pre-existing
  role-less user the `user` role **plus a direct `admin.access`**, so nobody
  loses the read access they had before. No escalation beyond that.
* Starring and folders need only authentication (personal data).

## 3. Stars and folders

GitHub-style: a **star** marks an item; **folders** organise starred items. An
item can be in several folders; adding to a folder stars it; unstarring removes
it from every folder; deleting a folder keeps its stars.

Saveable types: `entity` (id = `entity_id`), `chronicle` (id = `chronicle_id`,
not the slug), `relationship` (id = `relationship_id`).

Tables: `stars (id, user_id, starrable_type, starrable_id, timestamps,
unique(user_id, starrable_type, starrable_id))`, `saved_folders (id, user_id,
name, description, color, timestamps, unique(user_id, name))`,
`saved_folder_star (saved_folder_id, star_id, created_at, pk both)`.

All under `auth:sanctum`:

| Call | Body | Result |
|---|---|---|
| `GET /api/v1/me/stars/keys` | – | `{data: StarKey[]}` — every star, for UI state |
| `GET /api/v1/me/stars` | `?type=&folder=&page=&per_page=` | paginated `{data: Star[], meta, links}`, newest first |
| `POST /api/v1/me/stars` | `type, id, folder_ids?` | `201 {data: Star}` (`200` if already starred) |
| `DELETE /api/v1/me/stars/{type}/{id}` | – | `204` |
| `GET /api/v1/me/folders` | – | `{data: Folder[]}` (name order) |
| `POST /api/v1/me/folders` | `name, description?, color?` | `201 {data: Folder}` |
| `PATCH /api/v1/me/folders/{folder}` | `name?, description?, color?` | `200 {data: Folder}` |
| `DELETE /api/v1/me/folders/{folder}` | – | `204` |
| `PUT /api/v1/me/folders/{folder}/items/{type}/{id}` | – | `200 {data: Star}` |
| `DELETE /api/v1/me/folders/{folder}/items/{type}/{id}` | – | `204` (star kept) |

Folder names ≤ 80 chars, unique per user; description ≤ 500; colour `#rrggbb`;
≤ 100 folders per user. Another user's folder → `404`.

```ts
StarKey = { type: SaveableType; id: string; star_id: number; folder_ids: number[] }
Star = { id: number; type: SaveableType; target_id: string; folder_ids: number[];
         created_at: string; item: SavedItem | null }      // null = target deleted
SavedItem =
  | { type: 'entity'; id; name; entity_type; entity_group; summary }   // summary ≤ 240 chars
  | { type: 'chronicle'; id; slug; title; start_year; end_year; entry_count }
  | { type: 'relationship'; id; relationship_type; description;
      source: EntityRef | null; target: EntityRef | null }
EntityRef = { id; name; entity_type; entity_group }
Folder = { id: number; name; description: string | null; color: string | null;
           stars_count: number; created_at; updated_at }
```

The PWA service worker must not cache `/api/v1/me*` (personalised).

## 4. Contributions

A contributor edits one prose field of one record; the server stores the base
text snapshot, the proposed text, and a **word-level diff**; staff approve
(applies the proposed text) or reject.

Editable fields: `entity` → `name`, `summary`, `significance`;
`relationship` → `description`; `chronicle` → `title`;
`chronicle_entry` (id = `entry_id`) → `narrative_text`.

Table `contributions (id, user_id → users nullOnDelete, target_type, target_id,
field, base_text, proposed_text, diff jsonb, note, status, reviewer_id,
review_note, reviewed_at, timestamps)`. Status: `pending | approved | rejected
| withdrawn`.

**Diff format** (stored in `diff`, returned by the API): an ordered array of
`[op, text]` tuples, `op` ∈ `"="` (unchanged), `"-"` (removed), `"+"` (added).
Concatenating `=`/`-` texts gives `base_text`; `=`/`+` gives `proposed_text`.
Tokens are words, whitespace runs and single punctuation characters
(`App\Support\TextDiff`, LCS via `sebastian/diff`). `stats = {added, removed}`
counts changed word tokens.

| Call | Auth | Body | Result |
|---|---|---|---|
| `POST /api/v1/contributions` | `contributions.create`, throttled 10/min | `target_type, target_id, field, proposed_text, note?` | `201 {data: Contribution}` · `422` unchanged/invalid |
| `GET /api/v1/me/contributions` | signed in | `?status=&page=` | paginated `{data: Contribution[], meta}` |
| `POST /api/v1/me/contributions/{id}/withdraw` | owner | – | `200 {data: Contribution}` · `422` if not pending |

`proposed_text` ≤ 10 000 chars, must differ from the current value (after
normalising line endings / trimming); `name`/`title` must be non-empty and ≤ 255.
`note` ≤ 1 000.

```ts
Contribution = { id: number; target_type; target_id; field; target_label: string;
  status; note: string | null; review_note: string | null;
  base_text: string; proposed_text: string;
  diff: ['=' | '-' | '+', string][]; stats: { added: number; removed: number };
  created_at: string; reviewed_at: string | null }
```

**Approve** locks the target row; if the field no longer equals `base_text`
the contribution is *stale* and approval needs an explicit `force`. Applying
uses a model save, so existing observers (timeline rebuild) fire.

### Admin (Inertia, `permission:contributions.review`)

| Route | Page / effect |
|---|---|
| `GET /contributions?status=&type=` | `contributions/index` |
| `GET /contributions/{contribution}` | `contributions/show` (diff viewer) |
| `POST /contributions/{contribution}/approve` | `review_note?, force?` → back; stale without force → error `conflict` |
| `POST /contributions/{contribution}/reject` | `review_note?` → back |

Shared Inertia prop `auth.can.review_contributions` hides the nav item.

```ts
// index props
{ contributions: Paginator<ContributionRow>; filters: { status: string; type: string };
  counts: Record<'pending'|'approved'|'rejected'|'withdrawn', number> }
ContributionRow = { id; target_type; target_id; field; target_label; status; note;
  stats; is_stale: boolean; user: {id; name; email} | null;
  reviewer: {id; name} | null; created_at; reviewed_at }
// show props
{ contribution: ContributionRow & { base_text; proposed_text; diff; review_note };
  current_text: string | null;          // null = target deleted
  current_diff: Diff | null;            // current → proposed, only when stale
  admin_url: string | null; public_url: string | null; other_pending: number }
```

## 5. SPA surface

* Routes: `/login`, `/register`, `/saved` (folders + starred items),
  `/contributions` (my submissions). The atlas stays at `/`.
* Top bar: the avatar placeholder becomes a user menu (sign in / saved /
  contributions / admin panel / sign out); mobile tools menu gets the same.
* Star + "save to folder" on the entity page, chronicle page, detail panel and
  relationship rows. Guests are sent to `/login?next=…`.
* "Suggest edit" next to each editable text opens a dialog with the current
  text, a note, and a live word-diff preview (client mirror of `TextDiff`).

## 6. Contributions: missing fields and aliases

* **Missing fields.** Any editable field may be empty; a suggestion against an
  empty field is a pure insertion (`base_text = ""`). The SPA shows "Suggest a
  summary" style entry points where a field has no text.
* **Aliases.** New editable field `entity.aliases` — a *list field*: the text
  is one name per line. The server normalises both the base snapshot and the
  proposal the same way: trim each line, drop blanks, sort by byte order,
  de-duplicate case-insensitively (the first spelling in that order wins), sort
  case-insensitively, join with `\n`. The SPA mirrors this
  (`web/src/lib/text-diff.ts`) and sends already de-duplicated text. So the stored diff shows only real additions/removals, never
  reordering. Staleness compares normalised lists. Approving syncs
  `entity_aliases` rows to the list (new rows get `source = 'contribution'`).
* **Name changes.** `POST /contributions/{c}/approve` accepts
  `keep_old_name_as_alias` (bool, default false; entity `name` only): the
  previous name is added to the aliases when it is not already there.

## 7. Admin user management (`permission:users.manage`)

New permission `users.manage`, granted to no role by default (the `admin`
super-user passes it). Shared prop `auth.can.manage_users` shows the nav item.

| Route | Page / effect |
|---|---|
| `GET /users?role=&search=` | `users/index` — `role` is a role name or `none` |
| `GET /users/{user}` | `users/show` |
| `GET /users/{user}/edit` | `users/edit` |
| `PUT /users/{user}` | `name, email, roles[], permissions[]` → redirect to show |

Guards (validation errors on `roles`): you cannot change your **own** roles or
direct permissions; only an `admin` may grant or revoke the `admin` role; the
last `admin` cannot lose it. Changing the email clears `email_verified_at`.

```ts
UserRow = { id: number; name; email; roles: string[]; email_verified_at: string | null;
  two_factor_enabled: boolean; contributions_count: number; created_at: string }
// index props
{ users: Paginator<UserRow>; filters: { role: string; search: string };
  roles: { name: string; users_count: number }[]; no_role_count: number }
// show props
{ user: UserRow & { updated_at: string };
  direct_permissions: string[];
  effective_permissions: string[] | 'all';      // 'all' for the admin role
  stats: { stars: number; folders: number;
           contributions: Record<'pending'|'approved'|'rejected'|'withdrawn', number> };
  recent_contributions: { id; target_type; field; target_label; status; created_at }[];
  is_self: boolean }
// edit props
{ user: { id; name; email }; roles: string[]; permissions: string[];   // current
  available_roles: { name: string; permissions: string[] }[];
  available_permissions: string[];
  is_self: boolean; can_assign_admin: boolean }
```

## 8. Known gaps / follow-ups

* Approving an entity `name` change does not touch slugs.
* No user deletion / suspension from the admin yet.
