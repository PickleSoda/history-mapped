#!/usr/bin/env bash
# Process pending opencode extraction handoffs through the deterministic tail.
# Usage: bash run_campaign.sh 2>&1 | tee /tmp/campaign_run.log
set -euo pipefail
cd "$(dirname "$0")"

VENV=pipeline/.venv/bin/python
EXTRACTIONS_DIR=${EXTRACTIONS_DIR:-output/campaign/extractions}
SUMMARY=${CAMPAIGN_SUMMARY:-/tmp/campaign_summary.txt}
: > "$SUMMARY"

TOTAL=0; OK=0; FAILED=0
for HANDOFF in "$EXTRACTIONS_DIR"/*/candidates.json; do
    [ -f "$HANDOFF" ] || continue
    TOTAL=$((TOTAL + 1))
    RUN_ID=$(basename "$(dirname "$HANDOFF")")
    echo ""
    echo "[$TOTAL] START $RUN_ID at $(date)"

    if ! OUT=$("$VENV" -m pipeline.agent.validate_handoff "$HANDOFF" 2>&1); then
        echo "$OUT"
        echo "[$RUN_ID] INVALID handoff (see log)" >> "$SUMMARY"
        FAILED=$((FAILED + 1))
        continue
    fi

    # EXTRA_AGENT_FLAGS lets re-runs pass e.g. --refresh.
    if OUT=$("$VENV" -m pipeline agent --from-candidates "$HANDOFF" --run-id "$RUN_ID" ${EXTRA_AGENT_FLAGS:-} 2>&1); then
        OK=$((OK + 1))
        echo "[$RUN_ID] OK"
        echo "[$RUN_ID] ok" >> "$SUMMARY"
    else
        FAILED=$((FAILED + 1))
        echo "$OUT" | tail -20
        echo "[$RUN_ID] ERR" >> "$SUMMARY"
    fi
done

echo ""
echo "=== campaign: $TOTAL total, $OK ok, $FAILED failed at $(date) ===" | tee -a "$SUMMARY"
