#!/usr/bin/env bash
# `docker compose` for the production stack, with the tile driver applied.
#
#   bash docker/compose-prod.sh <compose args...>     e.g.  bash docker/compose-prod.sh up -d
#
# Runs `docker compose --env-file docker/.env.prod -f docker/docker-compose.prod.yml`
# from the repo root, after reading TILES_DRIVER from docker/.env.prod
# (default martin): with `martin`, the `martin` compose profile is enabled so
# `up -d` starts the sidecar Caddy proxies /tiles/* to; with `app`, it is not,
# and the app answers /tiles/* itself. The CI deploy and the runbook both go
# through this wrapper so the two never disagree.
set -Eeuo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
env_file=docker/.env.prod

driver=$(sed -n 's/^TILES_DRIVER=//p' "$env_file" 2>/dev/null | tail -n 1 | tr -d '[:space:]"'"'" || true)
driver=${driver:-martin}
# A `--profile` flag on the command line replaces COMPOSE_PROFILES from the
# environment, so the driver's profile is passed as a flag too: it then merges
# with any `--profile setup` the caller adds.
profile=()
case "$driver" in
  martin) profile=(--profile martin) ;;
  app) ;;
  *) echo "docker/compose-prod.sh: TILES_DRIVER must be 'martin' or 'app' in $env_file (got '$driver')" >&2; exit 2 ;;
esac
# Caddy's TILES_DRIVER comes from compose interpolation; export the resolved
# value so the default applies even when .env.prod has no such line.
export TILES_DRIVER="$driver"

exec docker compose --env-file "$env_file" -f docker/docker-compose.prod.yml "${profile[@]}" "$@"
