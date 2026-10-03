#!/usr/bin/env bash
# Process pending opencode extraction handoffs through the deterministic tail.
# Usage: bash run_campaign.sh
# Env:
#   ONLY=<regex>          only run_ids matching this (bash ERE), e.g. ONLY='^campaign_e0[45]__'
#   RETRY_FAILED=1        add --refresh for runs whose manifest recorded errors
#   RUN_TIMEOUT=1800      per-run timeout in seconds (recorded as TIMEOUT)
#   EXTRA_AGENT_FLAGS=..  extra flags for every run, e.g. --refresh
#   DRY_RUN=1             list what would run (no docker needed)
#   SKIP_PREFLIGHT=1      don't require the compose app/db services
#   CAMPAIGN_LOG_DIR      default output/campaign/logs/<YYYYmmdd-HHMMSS>
#   CAMPAIGN_SUMMARY      default $CAMPAIGN_LOG_DIR/summary.txt
#   EXTRACTIONS_DIR       default output/campaign/extractions
set -euo pipefail
cd "$(dirname "$0")"

VENV=pipeline/.venv/bin/python
COMPOSE=(docker compose -f docker/docker-compose.yml)
EXTRACTIONS_DIR=${EXTRACTIONS_DIR:-output/campaign/extractions}
RUN_TIMEOUT=${RUN_TIMEOUT:-1800}
LOG_DIR=${CAMPAIGN_LOG_DIR:-output/campaign/logs/$(date +%Y%m%d-%H%M%S)}
DRY_RUN=${DRY_RUN:-}

if [ -z "$DRY_RUN" ] && [ -z "${SKIP_PREFLIGHT:-}" ]; then
    RUNNING=$("${COMPOSE[@]}" ps --status running --services 2>/dev/null || true)
    for SVC in app db; do
        if ! grep -qx "$SVC" <<< "$RUNNING"; then
            echo "preflight: docker compose service '$SVC' is not running; start the stack first (pnpm dev, or ${COMPOSE[*]} up -d)" >&2
            exit 2
        fi
    done
fi

mkdir -p "$LOG_DIR"
SUMMARY=${CAMPAIGN_SUMMARY:-$LOG_DIR/summary.txt}
: > "$SUMMARY"
MANIFEST_DIR=$("$VENV" -c 'import pipeline.config; from pipeline.agent.config import AgentConfig; print(AgentConfig().output_dir)')

manifest_state() {
    [ -f "$1" ] || { echo none; return; }
    "$VENV" -c 'import json, sys
m = json.load(open(sys.argv[1]))
print("failed" if m.get("errors") or m.get("errors_count") else "clean")' "$1" 2>/dev/null || echo failed
}

record() {
    echo "[$1] $2"
    echo "[$1] $2" >> "$SUMMARY"
}

echo "logs: $LOG_DIR  summary: $SUMMARY"
TOTAL=0; OK=0; FAILED=0; SKIPPED=0; TIMEOUTS=0
for HANDOFF in "$EXTRACTIONS_DIR"/*/candidates.json; do
    [ -f "$HANDOFF" ] || continue
    RUN_ID=$(basename "$(dirname "$HANDOFF")")
    if [ -n "${ONLY:-}" ] && ! [[ "$RUN_ID" =~ $ONLY ]]; then
        continue
    fi
    TOTAL=$((TOTAL + 1))
    LOG="$LOG_DIR/$RUN_ID.log"
    STATE=$(manifest_state "$MANIFEST_DIR/$RUN_ID/manifest.json")
    FLAGS=${EXTRA_AGENT_FLAGS:-}
    if [ "$STATE" = failed ] && [ -n "${RETRY_FAILED:-}" ] && [[ " $FLAGS " != *" --refresh "* ]]; then
        FLAGS="$FLAGS --refresh"
    fi
    if [ "$STATE" = clean ] && [[ " $FLAGS " != *" --refresh "* ]]; then
        SKIPPED=$((SKIPPED + 1))
        record "$RUN_ID" "skip (clean manifest)"
        continue
    fi
    if [ -n "$DRY_RUN" ]; then
        record "$RUN_ID" "would run (manifest=$STATE flags:${FLAGS:- none})"
        continue
    fi

    echo ""
    echo "[$TOTAL] START $RUN_ID at $(date) (manifest=$STATE flags:${FLAGS:- none})"
    if ! "$VENV" -m pipeline.agent.validate_handoff "$HANDOFF" > "$LOG" 2>&1; then
        tail -20 "$LOG"
        record "$RUN_ID" "INVALID handoff (see $LOG)"
        FAILED=$((FAILED + 1))
        continue
    fi

    set +e
    # shellcheck disable=SC2086
    timeout -k 30 "$RUN_TIMEOUT" "$VENV" -m pipeline agent --from-candidates "$HANDOFF" --run-id "$RUN_ID" $FLAGS >> "$LOG" 2>&1
    RC=$?
    set -e
    if [ "$RC" -eq 0 ]; then
        OK=$((OK + 1))
        record "$RUN_ID" ok
    elif [ "$RC" -eq 124 ] || [ "$RC" -eq 137 ]; then
        TIMEOUTS=$((TIMEOUTS + 1)); FAILED=$((FAILED + 1))
        tail -20 "$LOG"
        record "$RUN_ID" "TIMEOUT after ${RUN_TIMEOUT}s (see $LOG)"
    else
        FAILED=$((FAILED + 1))
        tail -20 "$LOG"
        record "$RUN_ID" "ERR rc=$RC (see $LOG)"
    fi
done

echo ""
echo "=== campaign: $TOTAL total, $OK ok, $FAILED failed ($TIMEOUTS timeout), $SKIPPED skipped at $(date) ===" | tee -a "$SUMMARY"
[ "$FAILED" -eq 0 ]
