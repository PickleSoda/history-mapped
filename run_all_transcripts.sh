#!/usr/bin/env bash
# Run all transcripts through the agent pipeline sequentially.
# Usage: bash run_all_transcripts.sh 2>&1 | tee /tmp/batch_run.log

set -euo pipefail
cd "$(dirname "$0")"

VENV=pipeline/.venv/bin/python
TRANSCRIPT_DIR=output/transcripts
SUMMARY=/tmp/batch_all_summary.txt
: > "$SUMMARY"

TRANSCRIPTS=($(ls "$TRANSCRIPT_DIR"/*.txt | sort))
TOTAL=${#TRANSCRIPTS[@]}
DONE=0
FAILED=0

echo "=== Batch run: $TOTAL transcripts at $(date) ===" | tee -a "$SUMMARY"

for FILEPATH in "${TRANSCRIPTS[@]}"; do
    STEM=$(basename "$FILEPATH" .txt)
    RUN_ID="topic_$STEM"
    DONE=$((DONE + 1))
    echo ""
    echo "[$DONE/$TOTAL] START $STEM at $(date)"

    START_S=$SECONDS
    # EXTRA_AGENT_FLAGS lets a re-run pass --no-create-chronicle so existing
    # chronicles aren't duplicated (entities/relations still dedup-merge).
    if OUTPUT=$("$VENV" -m pipeline agent --input "$FILEPATH" --run-id "$RUN_ID" ${EXTRA_AGENT_FLAGS:-} 2>&1); then
        ELAPSED=$((SECONDS - START_S))
        LAST=$(echo "$OUTPUT" | tail -5)
        echo "[$DONE/$TOTAL] OK  $STEM (${ELAPSED}s)"
        echo "[$STEM] exit=0 | elapsed=${ELAPSED}s | $LAST" >> "$SUMMARY"
    else
        ELAPSED=$((SECONDS - START_S))
        LAST=$(echo "$OUTPUT" | tail -5)
        echo "[$DONE/$TOTAL] ERR $STEM (${ELAPSED}s)"
        echo "$OUTPUT" | tail -20
        echo "[$STEM] exit=1 | elapsed=${ELAPSED}s | $LAST" >> "$SUMMARY"
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo "=== DONE: $TOTAL total, $FAILED failed at $(date) ===" | tee -a "$SUMMARY"
echo "Summary at $SUMMARY"
