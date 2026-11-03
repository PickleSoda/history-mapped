# Deployment Runbook — GHCR image → DigitalOcean

Concrete steps to take the container image CI publishes and run it on DigitalOcean,
either on **App Platform** (managed) or a **Droplet** (self-hosted Compose).

---

## 1. What CI publishes, and where

On every push to `main`, `.github/workflows/ci.yml` builds `docker/api/Dockerfile.prod`
(FrankenPHP + Octane) and pushes it to **GitHub Container Registry**:

```
ghcr.io/picklesoda/history-mapped/api:<commit-sha>
ghcr.io/picklesoda/history-mapped/api:latest
```

> The owner segment is **lowercased** (`PickleSoda` → `picklesoda`) because Docker
> requires lowercase image names. The workflow does this automatically now; before
> the fix the push failed with *"repository name must be lowercase."*

## 2. GitHub setup required

| Item | Needed? | Notes |
|------|---------|-------|
| Registry auth for the push | **No setup** | Uses the built-in `GITHUB_TOKEN` + job-level `packages: write`. |
| Workflow permissions | Check once | Settings → Actions → General → Workflow permissions. The job's explicit `packages: write` normally overrides this. |
| Package visibility | **Yes, decide** | The package is **private** by default. To pull it from DO you either (a) make it public — package page → Package settings → Change visibility → Public, or (b) keep it private and supply a **PAT with `read:packages`** to the puller. |
| `DIGITALOCEAN_ACCESS_TOKEN` secret | Only for auto-deploy | Settings → Secrets and variables → Actions → Secrets. Create the token in the DO console (API → Generate New Token, write scope). |
| `DEPLOY_TO_DO` variable | Only for auto-deploy | Set to `true` (Actions → Variables) to enable the `deploy` job. It stays skipped until then, so it won't break CI. |

## 3. Option A — App Platform (managed, recommended)

App Platform natively supports GHCR. Spec: [`.do/app.yaml`](../../.do/app.yaml).

1. **Install + auth doctl:** `doctl auth init`.
2. **Create managed data services** (PostGIS + pgvector need a real cluster, not the dev DB):
   - Create a **Managed PostgreSQL** cluster and a **Managed Valkey (Redis)** cluster.
   - Enable extensions on the Postgres DB:
     ```sql
     CREATE EXTENSION IF NOT EXISTS postgis;
     CREATE EXTENSION IF NOT EXISTS vector;   -- registered as "vector", not "pgvector"
     ```
   - Put the cluster names into `databases[].cluster_name` in `.do/app.yaml`.
3. **Registry credentials:** make the GHCR package public, or set `registry_credentials: "PickleSoda:<PAT-read:packages>"` in the spec.
4. **Fill placeholders** in `.do/app.yaml` (domains, `VITE_API_URL`, region).
5. **Validate + create:**
   ```bash
   doctl apps spec validate .do/app.yaml
   doctl apps create --spec .do/app.yaml
   ```
6. **Set the `APP_KEY` secret** in the App → Settings (value: `php artisan key:generate --show`).
7. **Auto-deploy on push:** set repo secret `DIGITALOCEAN_ACCESS_TOKEN` and variable `DEPLOY_TO_DO=true`. CI's `deploy` job then redeploys after each image publish (GHCR images can't use App Platform's deploy-on-push, so the action triggers it).

Components in the spec: `api` (HTTP), `queue` + `scheduler` (workers), `migrate` (PRE_DEPLOY job), `web` (static SPA), plus the two managed databases. Migrations run as the pre-deploy job so replicas never race `migrate --force`.

**Valkey TLS gotcha:** DO Valkey requires TLS. If phpredis can't connect, set a `'scheme' => 'tls'` option on the redis connection in `config/database.php` (or prefix the host with `tls://`).

## 4. Option B — Droplet (cheapest, you own ops)

Files: [`docker/docker-compose.prod.yml`](../../docker/docker-compose.prod.yml), [`docker/Caddyfile`](../../docker/Caddyfile), [`docker/.env.prod.example`](../../docker/.env.prod.example), [`docker/martin/config.yaml`](../../docker/martin/config.yaml).

**Two domains.** The admin (Inertia, served by the app) and the customer SPA both live at `/`, so they need separate hostnames:
- **`APP_DOMAIN`** → the app container (API `/api`, admin UI, OpenAPI `/docs`).
- **`WEB_DOMAIN`** → the customer SPA (static files: CI builds them into the `web` image, the `web-dist` service installs them into the `web_dist` volume as `releases/<sha>`, and Caddy serves `/srv/web/current`). Point an A record for each at the Droplet.

**Vector tiles.** `APP_DOMAIN/tiles/*` serves the atlas tiles from Postgres ([contract](../schemas/atlas-tiles.md)).
`TILES_DRIVER` in `docker/.env.prod` picks who answers, with no SPA rebuild either way:
- `martin` (default): the `martin` sidecar, image `ghcr.io/maplibre/martin:1.16.1`, config
  [`docker/martin/config.yaml`](../../docker/martin/config.yaml). It connects with the app's `DB_*` credentials (keep `DB_PASSWORD`
  URL-safe, because it is interpolated into Martin's connection URL). The port is not published. The service sits in the `martin`
  compose profile, which [`docker/compose-prod.sh`](../../docker/compose-prod.sh) enables from this value: always use the wrapper,
  a plain `docker compose up -d` would not start it.
- `app`: the app serves the same tiles at the same URLs (`api/routes/tiles.php`, 5-min cache in Redis). One container fewer;
  tile requests then share Octane's PHP workers (one per vCPU) with the API.
- Caddy imports the matching upstream and adds `Cache-Control: public, max-age=300` plus gzip/zstd. It reads the value at start:
  recreate `caddy` after a change.
- The SPA switches to tiles only when the repository variable `VITE_MAP_TILES_URL=https://<APP_DOMAIN>/tiles` is set when CI
  builds the `web` image. Unset keeps the REST GeoJSON overlay.

1. Create a Droplet (≥2 GB RAM), point DNS A records for **both** `APP_DOMAIN` and `WEB_DOMAIN` at it.
2. Install Docker Engine + Compose plugin.
3. Clone the repo (the `db` image is built locally, so the full repo is needed), then:
   ```bash
   cp docker/.env.prod.example docker/.env.prod   # fill APP_KEY, passwords, APP_DOMAIN, WEB_DOMAIN, ...
   docker login ghcr.io                            # PAT with read:packages (skip if package is public)
   bash docker/compose-prod.sh pull
   bash docker/compose-prod.sh --profile setup run --rm web-dist   # install the SPA bundle from the web image
   bash docker/compose-prod.sh --profile setup run --rm migrate
   bash docker/compose-prod.sh up -d
   ```
   (`docker/compose-prod.sh` is `docker compose --env-file docker/.env.prod -f docker/docker-compose.prod.yml` plus the `martin`
   profile when `TILES_DRIVER=martin`.)
4. Caddy auto-provisions Let's Encrypt TLS for both domains; it proxies `APP_DOMAIN` to the app on 8080 (and `/tiles/*` to the tile driver) and serves the SPA on `WEB_DOMAIN`.
5. To update after new images: `pull`, re-run `web-dist` + `migrate`, then `up -d`, then recreate `caddy` (and `martin` when it is the driver; see below). The automated SSH deploy does exactly this.
   The `migrate` job also runs `php artisan collections:sync`, which loads the curated sets shipped in `api/resources/collections/` (they come with the code, not with content loads).

**SPA bundle (built in CI, 2026-11-01).** A `vite build` on the 2 GB droplet starved it of memory and hung a deploy, so the
bundle is built by the `images` job into `ghcr.io/<owner>/history-mapped/web:<sha>` ([`docker/web/Dockerfile.prod`](../../docker/web/Dockerfile.prod))
with the `VITE_*` repository variables baked in. On the droplet, `web-dist` ([`docker/web/install-web-dist.sh`](../../docker/web/install-web-dist.sh))
copies it to `web_dist:/srv/web/releases/<sha>` and renames the `current` symlink onto it, keeping the previous release for a
rollback: `WEB_IMAGE=ghcr.io/<owner>/history-mapped/web:<old sha> $COMPOSE --profile setup run --rm web-dist`. Files from the
former on-droplet build remain at the volume root until deleted by hand; Caddy no longer reads them.

**Tiles: first deploy and later changes.** Commands run from the repo root with `COMPOSE="bash docker/compose-prod.sh"`.
- **Set the flag before the first tiles deploy.** Set the repository variable `VITE_MAP_TILES_URL` before pushing the code; the
  `images` job bakes it into the `web` image on every push to `main`.
- **Caddy must be restarted when the Caddyfile changes.** It is a single-file bind mount, and `git pull` replaces the file, so the
  running container keeps the old copy. `up -d` does not recreate Caddy, because its compose config did not change. The same
  applies to `docker/martin/config.yaml`.
- **Martin must be restarted after migrations that add tile functions.** It discovers them only at startup. The app driver
  needs nothing: it calls the function by name on each request.
- **The CI deploy does both restarts.** After `migrate` and `up -d` it runs
  `$COMPOSE up -d --force-recreate --no-deps caddy martin` (with `TILES_DRIVER=app`: `caddy` only, then `$COMPOSE rm -sf martin`,
  because `--remove-orphans` leaves a profiled service's container alone). When deploying by hand, run the same. Recreating
  Caddy drops connections briefly on each deploy; certificates persist in the `caddy_data` volume.
- **Switching the driver** is a `TILES_DRIVER` edit in `docker/.env.prod` followed by the next deploy, or by hand:
  `$COMPOSE up -d --remove-orphans`, then the recreate line above for the new value. Check with
  `curl -sI https://<APP_DOMAIN>/tiles/atlas_entities/0/0/0` (200 or 204, `application/x-protobuf`).
- **Toggling the flag later** is a repository-variable change plus a push to `main` (or a re-run of the `images` and deploy jobs);
  nothing is rebuilt on the droplet.

> **Map-story editor preview.** The admin's map-story editor embeds the SPA (`FRONTEND_URL`) in an iframe and drives it with `postMessage`. The SPA trusts the API origin (`VITE_API_URL`) by default; other admin origins go in the repository variable `VITE_ADMIN_ORIGINS` (comma-separated), baked into the `web` image by CI.

> Note: migrations run **without** `route:cache` — `/health` and `/user` are closure routes, which `route:cache` rejects (it would fail the one-off job and, with `script_stop: true`, abort the whole SSH deploy).

The stack runs the app (FrankenPHP/Octane), `queue`, `scheduler`, self-hosted Postgres (PostGIS+pgvector), and Redis on the one box. To use managed data services instead, delete the `db`/`redis` services and repoint `DB_*`/`REDIS_*`.

### 4b. Automated droplet deploy on push (CI over SSH)

The `deploy-droplet` job in `.github/workflows/ci.yml` SSHes into the droplet and runs the update after each image build. Opt in:

1. **On the droplet (one-time):**
   - Install Docker Engine + the Compose plugin.
   - Clone the repo at `/opt/history-mapped` (or any path). For a **private repo**, add a read-only **Deploy key** (repo → Settings → Deploy keys) so `git pull` works non-interactively.
   - `cp docker/.env.prod.example docker/.env.prod` and fill it in (gitignored; holds secrets).
   - Do the first deploy manually (section 4) so the stack is healthy.
2. **Repo secrets** (Settings → Secrets and variables → Actions → Secrets):
   - `DROPLET_HOST` — IP/hostname · `DROPLET_USER` — SSH user · `DROPLET_SSH_KEY` — the **private** key whose public half is in the droplet's `~/.ssh/authorized_keys`.
   - *Optional:* `DROPLET_SSH_PORT` (default 22); `GHCR_USERNAME` + `GHCR_TOKEN` (PAT with `read:packages`, only if the GHCR package is private — the job logs in for you).
3. **Repo variables** (→ Variables):
   - `DEPLOY_TO_DROPLET` = `true` (enables the job — it stays skipped otherwise).
   - *Optional:* `DROPLET_APP_DIR` if you cloned somewhere other than `/opt/history-mapped`.
   - `VITE_API_URL` = `https://<APP_DOMAIN>` (required: the `images` job fails without it, so no deploy runs).
   - *Optional:* `VITE_MAP_TILES_URL` = `https://<APP_DOMAIN>/tiles` (atlas tile mode), `VITE_APP_NAME`, `VITE_ADMIN_ORIGINS`.
4. Push to `main` → CI builds + pushes the `api` and `web` images, then SSHes in and runs `git pull → compose pull → web-dist → migrate → up -d → recreate caddy (+ martin, or remove it under the app driver) → /up health gate → prune`.

**Security:** use a dedicated low-privilege deploy user and an SSH key scoped to that host; the private key lives only in GitHub Secrets.

## 5. Cost comparison (approximate — confirm on DO's pricing page)

| | Droplet (Option B) | App Platform (Option A) |
|---|---|---|
| Compute | One Droplet **~$12–24/mo** (2–4 GB; runs app+queue+scheduler+db+redis) | `api` + `queue` + `scheduler` as 3 small components **~$20/mo** |
| Database | included (self-hosted on the box) | Managed Postgres **~$15/mo** (single node, PostGIS+pgvector) |
| Cache | included | Managed Valkey **~$15/mo** |
| Static SPA | served by the box | Static site free on Starter |
| **Rough total** | **~$12–24/mo** | **~$45–60/mo** |
| You manage | OS patching, backups, TLS (Caddy auto), restarts, scaling | nothing — DO handles HA, backups, TLS, rolling deploys, scaling |

**Bottom line:** the Droplet is ~2–4× cheaper but you own operations; App Platform costs more but is hands-off and tells a stronger "managed, scalable, platform-agnostic" story for the capstone report. For a class demo on a tight budget, the Droplet is fine; for the production-grade narrative, App Platform.

---

> **This is the single canonical deployment doc.** Two earlier strategy write-ups
> (`deployment-production-optimal.md`, an aspirational managed/autoscaling target, and
> `deployment-mvp-low-cost.md`, which argued *against* the VPS+Compose approach that ultimately
> shipped) were superseded by this runbook and moved to
> [`../archive/implementation-docs/`](../archive/implementation-docs/). Consult them only for historical
> rationale.
