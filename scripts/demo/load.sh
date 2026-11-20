#!/usr/bin/env bash
# Load the demo data set (the atlas's ~36,000 curated entities, their relationships,
# chronicles and battle maps) into the local Docker stack.
#
#   pnpm demo:load                 download the release asset and load it
#   pnpm demo:load -- --yes        no confirmation
#   pnpm demo:load -- path.sql.gz  load a file you already have
#
# It REPLACES the content tables of the local database (entities, relationships,
# chronicles, ...). Users, roles and saved items are left alone. Needs the stack
# running and migrated (see docs/implementation-docs/setup.md).
set -euo pipefail

cd "$(dirname "$0")/../.."
VERSION="${DEMO_DATA_VERSION:-demo-data-v1}"
URL="${DEMO_DATA_URL:-https://github.com/PickleSoda/history-mapped/releases/download/$VERSION/history-mapped-demo.sql.gz}"
DC=(docker compose -f docker/docker-compose.yml)
# DEMO_DB loads into another database of the same server (it must be migrated).
DB_ENV=()
[ -n "${DEMO_DB:-}" ] && DB_ENV=(-e "POSTGRES_DB=$DEMO_DB" -e "DB_DATABASE=$DEMO_DB")

YES=0
FILE=""
for arg in "$@"; do
  case "$arg" in
    --yes|-y) YES=1 ;;
    --) ;;
    -*) echo "Unknown option: $arg" >&2; exit 2 ;;
    *) FILE="$arg" ;;
  esac
done

if ! "${DC[@]}" exec -T db true 2>/dev/null; then
  echo "The stack is not running. Start it with 'pnpm dev' and run the migrations first." >&2
  exit 1
fi

if [ -z "$FILE" ]; then
  mkdir -p output/demo
  FILE="output/demo/$VERSION.sql.gz"
  if [ ! -s "$FILE" ]; then
    # The release holds the file in parts (part-00, part-01, ...); they are joined here.
    echo "Downloading $URL"
    : > "$FILE.part"
    i=0
    # A part that is not there (404) ends the list.
    while curl -fsL --retry 3 -o "$FILE.chunk" "$(printf '%s.part-%02d' "$URL" "$i")"; do
      cat "$FILE.chunk" >> "$FILE.part"
      i=$((i + 1))
    done
    rm -f "$FILE.chunk"
    [ "$i" -gt 0 ] || curl -fL --retry 3 -o "$FILE.part" "$URL"
    mv "$FILE.part" "$FILE"
  fi
  # The release carries the file's checksum; a missing one is not an error.
  if SUM=$(curl -fsL "$URL.sha256" 2>/dev/null); then
    echo "${SUM%% *}  $FILE" | sha256sum -c - >/dev/null || { echo "Checksum mismatch: delete $FILE and retry." >&2; exit 1; }
  fi
fi
[ -s "$FILE" ] || { echo "No such file: $FILE" >&2; exit 1; }
gzip -t "$FILE"

# The tables to replace are exactly the ones the file carries.
TABLES=$(gzip -dc "$FILE" | grep -a '^COPY public\.' | sed -E 's/^COPY (public\.[a-z_0-9]+) .*/\1/' | sort -u | paste -sd, -)
[ -n "$TABLES" ] || { echo "The file holds no tables." >&2; exit 1; }

if [ "$YES" != 1 ]; then
  echo "This replaces the content of the local database with the demo data set."
  read -r -p "Continue? [y/N] " answer
  case "$answer" in y|Y|yes) ;; *) echo "Nothing changed."; exit 0 ;; esac
fi

echo "Loading (one transaction; an error leaves the database as it was)"
{
  echo "TRUNCATE TABLE $TABLES RESTART IDENTITY CASCADE;"
  gzip -dc "$FILE"
} | "${DC[@]}" exec -T "${DB_ENV[@]}" db sh -c 'psql -q -1 -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null

"${DC[@]}" exec -T "${DB_ENV[@]}" app php artisan db:repair-sequences
"${DC[@]}" exec -T "${DB_ENV[@]}" app php artisan tiles:refresh --force
"${DC[@]}" exec -T "${DB_ENV[@]}" app php artisan collections:sync
"${DC[@]}" exec -T "${DB_ENV[@]}" app php artisan cache:clear
"${DC[@]}" exec -T "${DB_ENV[@]}" db sh -c 'psql -At -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "ANALYZE" -c "SELECT (SELECT count(*) FROM entities) || '"'"' entities, '"'"' || (SELECT count(*) FROM relationships) || '"'"' relationships, '"'"' || (SELECT count(*) FROM chronicles) || '"'"' chronicles'"'"'"'
echo "Done. Open http://localhost:5173/app"
