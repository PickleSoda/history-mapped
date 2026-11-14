#!/usr/bin/env bash
# Fetch approved bulk slices in parallel and import them with one importer.
#
#   scripts/bulk_run.sh [-p PARALLEL] slice-id …
#
# Fetchers (one per slice, PARALLEL at a time) build parts; the importer
# daemon imports every built part, one at a time, until the fetchers are
# done and nothing is left. Logs: output/bulk/logs/. Stop early:
# touch output/bulk/STOP (the importer exits after its current part;
# fetchers stop at their next part boundary when killed).
set -euo pipefail
cd "$(dirname "$0")/.."

PARALLEL=4
while getopts "p:" opt; do
  case $opt in
    p) PARALLEL=$OPTARG ;;
    *) echo "usage: $0 [-p N] slice…" >&2; exit 2 ;;
  esac
done
shift $((OPTIND - 1))
[ $# -gt 0 ] || { echo "usage: $0 [-p N] slice…" >&2; exit 2; }

LOGS=output/bulk/logs
mkdir -p "$LOGS"
rm -f output/bulk/STOP
PY="pipeline/.venv/bin/python"
export LANGCHAIN_TRACING_V2=false LANGSMITH_TRACING=false

echo "[$(date -Is)] bulk_run: ${*} (parallel ${PARALLEL})" >> "$LOGS/run.log"

# Importer daemon: polls for built parts until STOP exists.
MEM_MAX=2G scripts/capped.sh "$PY" -m pipeline.bulk importer --poll 20 >> "$LOGS/importer.log" 2>&1 &
IMPORTER=$!

fetch_one() {
  local id=$1
  MEM_MAX=1500M scripts/capped.sh "$PY" -m pipeline.bulk qids "$id" >> "output/bulk/logs/$id.log" 2>&1 &&
  MEM_MAX=1500M scripts/capped.sh "$PY" -m pipeline.bulk fetch "$id" >> "output/bulk/logs/$id.log" 2>&1 ||
  echo "[$(date -Is)] fetch $id FAILED (exit $?)" >> output/bulk/logs/run.log
}
export -f fetch_one
printf '%s\n' "$@" | xargs -P "$PARALLEL" -I{} bash -c 'fetch_one "$@"' _ {}

echo "[$(date -Is)] fetchers done; draining imports" >> "$LOGS/run.log"
# Let the importer drain, then stop it.
MEM_MAX=2G scripts/capped.sh "$PY" -m pipeline.bulk importer --idle-exit >> "$LOGS/importer.log" 2>&1 || true
touch output/bulk/STOP
wait "$IMPORTER" || true
rm -f output/bulk/STOP
echo "[$(date -Is)] bulk_run done" >> "$LOGS/run.log"
