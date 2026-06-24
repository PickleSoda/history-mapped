# Content Data Transfer — Dump Local DB → Droplet Prod

How to ship the historical-atlas **content** (entities, relationships, geometry,
chronicles, reference tables) from a local Postgres to the production droplet.

## When you need this

The remediation tooling in [data-quality-runbook.md](data-quality-runbook.md) and
[entity-reresolution.md](entity-reresolution.md) writes **directly to the
database** — geometry copies, the −753 cleanup, century-parse fixes, event
locations, merges. Those changes are **not** reflected in the `output/` JSONL
artifacts, so re-running the Laravel import on prod will **not** reproduce them.
Once you've hand-fixed data, the DB *is* the source of truth, and the only way to
get it to prod is a **database transfer** — not a re-import, not a pipeline re-run.

The [deployment-runbook.md](deployment-runbook.md) only ever runs `migrate --force`
on prod; it never seeds content. So prod's **schema** matches local (same
migrations) but its **content** is empty/stale. That's exactly the case this guide
covers: load content into prod's already-migrated schema.

> Scope here: the **droplet, self-hosted `db` container** (Option B), where you
> have Postgres superuser. DO Managed Postgres has no superuser, so
> `--disable-triggers` fails — there you'd take a full `pg_dump --clean` instead.

---

## The strategy: data-only, into the existing schema

We dump **data only** (no schema, no extensions) and load it into prod's existing
migrated schema. This sidesteps every PostGIS/pgvector restore headache — we never
recreate tables, extensions, or `spatial_ref_sys`.

What's deliberately **excluded** from the dump, and why:

| Excluded | Why |
|----------|-----|
| `users`, `roles`, `permissions`, `model_has_*`, `role_has_permissions` | Keep prod's own admin accounts — don't clobber them |
| `cache`, `cache_locks`, `jobs`, `job_batches`, `failed_jobs`, `sessions`, `password_reset_tokens` | Laravel runtime/volatile state — rebuilt on demand |
| `migrations` | Prod's migration ledger is managed by `migrate`, not us |
| `spatial_ref_sys` + `tiger.*`, `tiger_data.*`, `topology.*` schemas | PostGIS extension-owned; already present on prod, would conflict |

What's **included** — the 24 content + reference tables: `entities`,
`entity_aliases`, `entity_geo_refs`, `entity_locations`, `entity_tags`,
`entity_temporal_ranges`, `entity_timeline_entries`, `relationships`,
`geometry_periods`, `chronicles`, `chronicle_entries`,
`chronicle_entry_entities`, `sources`, `pipeline_relationship_hints`, and all
`ref_*` reference tables.

---

## Step 1 — Create the cleaned dump (local)

Read-only; safe to run anytime. Produces `output/history-mapped-content-<date>.sql`.

```bash
cd /path/to/history-mapped
STAMP=$(date +%Y%m%d)
OUT=output/history-mapped-content-$STAMP.sql
EXCLUDES="cache cache_locks failed_jobs job_batches jobs migrations \
password_reset_tokens sessions spatial_ref_sys users roles permissions \
model_has_permissions model_has_roles role_has_permissions"
ARGS=""
for t in $EXCLUDES; do ARGS="$ARGS --exclude-table-data=public.$t"; done

docker compose -f docker/docker-compose.yml exec -T db \
  pg_dump -U history-mapped -d history-mapped \
  --data-only --no-owner --no-privileges --disable-triggers \
  -N tiger -N tiger_data -N topology \
  $ARGS > "$OUT"
```

Flag notes:
- `--data-only` — no `CREATE TABLE`/extensions; load into the migrated schema.
- `--disable-triggers` — load ignores FK ordering. **Needs superuser** (fine on the
  self-hosted droplet db). This is also why the dump warns about *circular
  foreign-key constraints among `entities`/`entity_geo_refs`* — expected and
  handled, not an error.
- `--no-owner --no-privileges` — portable across roles.
- `-N tiger -N tiger_data -N topology` — drop the PostGIS extension schemas;
  without these the dump pulls in `tiger.pagc_*`, `topology.layer`, etc.

**Verify** the dump contains only the intended tables:

```bash
grep '^COPY ' "$OUT" | sed 's/ (.*//' | sort   # should list the 24 content tables only
```

`output/` is gitignored — the dump never lands in a commit.

## Step 2 — Companion artifacts

Two files live in `output/` alongside the dump (committed as templates is
unnecessary — regenerate or copy from this doc):

- **`output/truncate-content.sql`** — `TRUNCATE ... RESTART IDENTITY CASCADE` over
  exactly the 24 included tables. `CASCADE` resolves the circular FKs; the list
  must stay in sync with the dump's table set.
- **`output/load-content-on-droplet.sh`** — the loader (Step 3). Runs *on the
  droplet*.

## Step 3 — Load on the droplet (full replace)

Copy the three artifacts up and run the loader. It **backs up current prod content
first**, then runs truncate + load in a **single transaction** — any error rolls
back and prod is untouched.

```bash
# from your laptop
scp output/history-mapped-content-<date>.sql \
    output/truncate-content.sql \
    output/load-content-on-droplet.sh \
    user@droplet:/opt/history-mapped/output/

# on the droplet
ssh user@droplet
cd /opt/history-mapped
bash output/load-content-on-droplet.sh output/history-mapped-content-<date>.sql
```

The loader (`output/load-content-on-droplet.sh`) does:

1. `pg_dump` current prod content → `output/prod-content-backup-<stamp>.sql` (rollback insurance).
2. `cat truncate-content.sql <dump> | psql -1 -v ON_ERROR_STOP=1` — **atomic** truncate + load.
3. Print row counts (`entities`, `relationships`, `geometry_periods`) to confirm the load.
4. `php artisan cache:clear` + `config:clear`.

If your prod compose file or service names differ, edit the `COMPOSE=` line at the
top of the loader — it's the only environment-specific knob.

## Rollback

The pre-load backup is data-only over the same tables, so restoring it is the
mirror of the load:

```bash
cat output/truncate-content.sql output/prod-content-backup-<stamp>.sql \
  | docker compose --env-file docker/.env.prod -f docker/docker-compose.prod.yml \
      exec -T db psql -U history-mapped -d history-mapped -1 -v ON_ERROR_STOP=1
```

## Gotchas

- **Managed Postgres** (Option A) has no superuser → `--disable-triggers` fails on
  load. Use a full `pg_dump --clean --if-exists` into a fresh DB instead, or drop
  FKs around a data-only load.
- **Keep the table list in three places in sync**: the dump's `--exclude-table-data`
  set, `truncate-content.sql`, and this doc. A table added to the schema later
  must be added to (or excluded from) all three.
- **This is a destructive full replace of prod content.** It assumes prod has no
  hand-entered content worth keeping (true while `migrate` is the only seeding
  path). The auto-backup covers you regardless.
- Auth/admin users are **not** transferred — create prod admins separately.
