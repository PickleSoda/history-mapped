"""Derive each campaign run's resume stage from on-disk state.

Usage: pipeline/.venv/bin/python scripts/campaign_wave_state.py --since 2026-10-02T23:00:00Z [SLUG ...]
Prints JSON {slug: {stage, facts, slices}} with stage one of
done | author | extract | review | regather | fix.
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRANSCRIPTS = ROOT / "output/transcripts/campaign"
EXTRACTIONS = ROOT / "output/campaign/extractions"
PY = str(ROOT / "pipeline/.venv/bin/python")


def ts(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def mtime(path):
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def fact_count(path):
    return sum(1 for line in path.read_text().splitlines() if re.match(r"^\s*\d+[.)]", line))


def handoff_complete(run_id, handoff):
    gate = subprocess.run([PY, "-m", "pipeline.agent.validate_handoff", str(handoff)], cwd=ROOT, capture_output=True, text=True)
    if gate.returncode != 0:
        return False
    check = subprocess.run([PY, "-m", "pipeline.campaign", "handoff", "check", run_id, "--all"], cwd=ROOT, capture_output=True, text=True)
    return not re.search(r"fact-(uncovered|missing)", check.stdout + check.stderr)


def stage_for(slug, since):
    run_id = f"campaign_{slug}"
    transcript = TRANSCRIPTS / f"{slug}.txt"
    run_dir = EXTRACTIONS / run_id
    handoff = run_dir / "candidates.json"
    facts = fact_count(transcript) if transcript.exists() else 0
    history = []
    if (run_dir / "review.json").exists():
        history = [h for h in json.loads((run_dir / "review.json").read_text()).get("history", []) if ts(h["timestamp"]) >= since]
    if history:
        latest = history[-1]
        if latest["verdict"] in ("PASS", "FIXED"):
            return {"stage": "done", "facts": facts}
        if latest["verdict"] == "ESCALATE" or sum(h["verdict"] == "REGATHER" for h in history) >= 2:
            return {"stage": "fix", "facts": facts, "reason": " | ".join(latest.get("issues", []))[:600]}
        slices = ""
        for issue in latest.get("issues", []):
            match = re.match(r"\s*slices:\s*([\d,\s-]+)", issue)
            if match:
                slices = match.group(1).replace(" ", "")
                break
        return {"stage": "regather" if slices else "fix", "facts": facts, "slices": slices, "reason": " | ".join(latest.get("issues", []))[:600]}
    if not transcript.exists() or mtime(transcript) < since or facts == 0:
        return {"stage": "author", "facts": facts}
    if handoff.exists() and mtime(handoff) >= mtime(transcript) and handoff_complete(run_id, handoff):
        return {"stage": "review", "facts": facts}
    return {"stage": "extract", "facts": facts}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", required=True)
    parser.add_argument("slugs", nargs="*")
    args = parser.parse_args()
    since = ts(args.since)
    slugs = args.slugs or sorted(p.stem for p in TRANSCRIPTS.glob("*.txt"))
    json.dump({s: stage_for(s, since) for s in slugs}, sys.stdout, indent=1)


if __name__ == "__main__":
    main()
