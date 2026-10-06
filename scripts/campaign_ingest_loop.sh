#!/usr/bin/env bash
# Continuous ingest of review-passed campaign runs. Stop: touch output/campaign/INGEST_STOP
# Start: setsid nohup env MEM_MAX=4G bash scripts/capped.sh bash scripts/campaign_ingest_loop.sh &
# INGEST_WORKERS=N (default 3) drivers run side by side on disjoint run lists. Wikidata
# backs off on 429 by itself; OHM Nominatim asks for <=1 req/s in total, so its
# per-process limit is split across workers. DB imports serialise on a lock file.
# --refresh policy: a FIRST-TIME ingest (no manifest, or a manifest with errors) runs WITHOUT
# --refresh, so entities already in the DB are kept as-is (first writer wins, no Wikidata
# re-resolution for them) while the run's relations and chronicle still link to them by name.
# --refresh (= --force downstream) is passed ONLY for a run whose manifest is already clean,
# i.e. a re-ingest because its handoff/review changed ("stale") or INGEST_REFRESH_BEFORE.
cd "$(dirname "$0")/.."
PY=pipeline/.venv/bin/python
LOG=output/campaign/logs/ingest-loop.log
WORKERS=${INGEST_WORKERS:-3}
OHM_RPM=$(( 60 / WORKERS )); [ "$OHM_RPM" -ge 1 ] || OHM_RPM=1
mkdir -p output/campaign/logs
while [ ! -e output/campaign/INGEST_STOP ]; do
    TS=$(date '+%F %T')
    READY=$(PYTHONPATH=. bash scripts/capped.sh "$PY" scripts/campaign_ingest_ready.py --record 2>>"$LOG" | paste -sd' ')
    N=$(wc -w <<< "$READY")
    OK=0; FAILED=0
    if [ "$N" -gt 0 ]; then
        D=output/campaign/logs/ingest-$(date +%Y%m%d-%H%M%S); mkdir -p "$D"
        read -ra RUNS <<< "$READY"
        for ((w = 0; w < WORKERS; w++)); do
            PART=()
            for ((i = w; i < ${#RUNS[@]}; i += WORKERS)); do PART+=("${RUNS[i]}"); done
            [ "${#PART[@]}" -gt 0 ] || continue
            mkdir -p "$D/w$w"
            # first-time runs: no --refresh; clean-manifest (stale) runs: --refresh
            RE_FIRST=""; RE_STALE=""
            for r in "${PART[@]}"; do
                if [ -f "api/storage/app/pipeline/agent_runs/$r/manifest.json" ] && \
                   PYTHONPATH=. "$PY" -c 'import json,sys; m=json.load(open(sys.argv[1])); sys.exit(1 if m.get("errors") or m.get("errors_count") else 0)' \
                       "api/storage/app/pipeline/agent_runs/$r/manifest.json" 2>/dev/null; then
                    RE_STALE+="${RE_STALE:+|}$r"
                else
                    RE_FIRST+="${RE_FIRST:+|}$r"
                fi
            done
            (
                for MODE in first stale; do
                    if [ "$MODE" = first ]; then RX=$RE_FIRST; FL=""; else RX=$RE_STALE; FL="--refresh"; fi
                    [ -n "$RX" ] || continue
                    mkdir -p "$D/w$w/$MODE"
                    ONLY="^($RX)\$" RUN_TIMEOUT=2400 EXTRA_AGENT_FLAGS="$FL" CAMPAIGN_LOG_DIR="$D/w$w/$MODE" \
                        OHM_REQUESTS_PER_MINUTE=$OHM_RPM \
                        bash scripts/capped.sh bash run_campaign.sh > "$D/w$w/$MODE/driver.out" 2>&1
                done
            ) &
        done
        wait
        cat "$D"/w*/*/summary.txt > "$D/summary.txt" 2>/dev/null
        OK=$(grep -c '\] ok$' "$D/summary.txt"); FAILED=$(grep -cE '\] (ERR|TIMEOUT|INVALID)' "$D/summary.txt")
    fi
    echo "$TS ready=$N ok=$OK failed=$FAILED workers=$WORKERS runs=[$READY]" >> "$LOG"
    for _ in $(seq 60); do [ -e output/campaign/INGEST_STOP ] && break; sleep 10; done
done
echo "$(date '+%F %T') stopped" >> "$LOG"
