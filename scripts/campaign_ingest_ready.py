"""Print ready-to-ingest run_ids (one per line) for campaign_ingest_loop.sh.

READY = latest review verdict in {PASS, FIXED} AND (ingest != clean OR handoff edited after
manifest OR review.json newer than manifest OR manifest older than $INGEST_REFRESH_BEFORE,
an epoch used to re-ingest everything after an ingest-side fix). A run is attempted at most 3 times per
(candidates, review) mtime pair so a persistently failing run cannot spin forever.
"""
import json, os, sys
from pathlib import Path
from pipeline.campaign import paths, status

state_file = paths.root() / "output/campaign/.ingest_attempts.json"
try:
    attempts = json.loads(state_file.read_text())
except (FileNotFoundError, ValueError):
    attempts = {}
record = "--record" in sys.argv
mf = paths.manifests_dir()
refresh_before = float(os.environ.get("INGEST_REFRESH_BEFORE") or 0)
ready = []
for r in status.collect():
    if r.review not in ("PASS", "FIXED"):
        continue
    rv, cand, man = paths.review_path(r.slug), paths.candidates_path(r.slug), paths.manifest_path(r.slug, mf)
    if not cand.exists() or not rv.exists():
        continue
    needs = (r.ingest != "clean" or r.stale or rv.stat().st_mtime > man.stat().st_mtime
             or (man.exists() and man.stat().st_mtime < refresh_before))
    if not needs:
        continue
    key = f"{int(cand.stat().st_mtime)}:{int(rv.stat().st_mtime)}"
    ent = attempts.get(r.slug, {})
    if ent.get("key") == key and ent.get("n", 0) >= 3:
        continue
    ready.append((r.slug, key))
if record:
    for s, k in ready:
        e = attempts.get(s, {})
        attempts[s] = {"key": k, "n": (e.get("n", 0) + 1) if e.get("key") == k else 1}
    state_file.write_text(json.dumps(attempts))
for s, _ in ready:
    print(paths.run_id_of(s))
