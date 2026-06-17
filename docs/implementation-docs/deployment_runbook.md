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

Files: [`docker/docker-compose.prod.yml`](../../docker/docker-compose.prod.yml), [`docker/Caddyfile`](../../docker/Caddyfile), [`docker/.env.prod.example`](../../docker/.env.prod.example).

1. Create a Droplet (≥2 GB RAM), point your DNS A record at it.
2. Install Docker Engine + Compose plugin.
3. Clone the repo (or copy the `docker/` files), then:
   ```bash
   cp docker/.env.prod.example docker/.env.prod   # fill APP_KEY, passwords, APP_DOMAIN, ...
   docker login ghcr.io                            # PAT with read:packages (skip if package is public)
   cd docker
   docker compose --env-file .env.prod -f docker-compose.prod.yml pull
   docker compose --env-file .env.prod -f docker-compose.prod.yml --profile setup run --rm migrate
   docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
   ```
4. Caddy auto-provisions Let's Encrypt TLS for `APP_DOMAIN` and proxies to the app on 8080.
5. To update after a new image: `pull` again, run `migrate`, then `up -d` (rolling).

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
4. Push to `main` → CI builds + pushes the image, then SSHes in and runs `git pull → compose pull → migrate → up -d → prune`.

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
