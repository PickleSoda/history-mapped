#!/usr/bin/env bash
# Run a command inside a memory-capped systemd scope so a runaway process is killed alone
# instead of OOM-killing the desktop session. Override the cap with MEM_MAX (e.g. MEM_MAX=6G).
exec systemd-run --user --scope -q -p MemoryMax="${MEM_MAX:-3G}" -p MemorySwapMax=0 "$@"
