"""Orchestration for the reproducible eval harness.

Pipeline of a single ``evaluate()`` call:
  1. (optional) reset the database to the blank BaselineSeeder slate
  2. run the agent pipeline over each transcript (fresh subprocess each)
  3. probe the database for what actually persisted
  4. apply quality heuristics + overlap-consistency checks
  5. write report.json + report.md under output/eval_runs/<label>/

Designed to be re-run verbatim: same transcripts + same code => same report,
so iterations can be diffed.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Importing pipeline.config loads pipeline/.env (DATABASE_URL, LLM_BASE_URL, …)
# into the environment for both our DB probe and the child pipeline runs.
import pipeline.config  # noqa: F401

from pipeline.agent.config import AgentConfig
from pipeline.agent.eval import metrics, probe

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPOSE_FILE = REPO_ROOT / "docker" / "docker-compose.yml"
DEFAULT_TRANSCRIPT_DIR = REPO_ROOT / "output" / "transctipts"
EVAL_OUTPUT_DIR = REPO_ROOT / "output" / "eval_runs"
BASELINE_SEEDER = r"Database\Seeders\BaselineSeeder"


def _slug(text: str) -> str:
    out = "".join(c.lower() if c.isalnum() else "_" for c in text).strip("_")
    while "__" in out:
        out = out.replace("__", "_")
    return out[:80]


def reset_database() -> dict[str, Any]:
    """Nuke + reseed the blank baseline (entities/relations/chronicles empty)."""
    cmd = [
        "docker", "compose", "-f", str(COMPOSE_FILE), "exec", "-T", "app",
        "php", "artisan", "migrate:fresh", f"--seeder={BASELINE_SEEDER}", "--force",
    ]
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=600)
    return {
        "returncode": proc.returncode,
        "ok": proc.returncode == 0,
        "stderr_tail": proc.stderr[-500:],
    }


def run_transcript(transcript: Path, run_id: str) -> dict[str, Any]:
    """Run the agent pipeline on one transcript in a fresh subprocess."""
    cfg = AgentConfig()
    run_dir = Path(cfg.output_dir) / run_id
    if not run_dir.is_absolute():
        run_dir = REPO_ROOT / run_dir
    # Clear any prior artifacts so the idempotency guard doesn't short-circuit.
    if run_dir.exists():
        shutil.rmtree(run_dir)

    cmd = [
        sys.executable, "-m", "pipeline", "agent",
        "--input", str(transcript), "--run-id", run_id,
        # Title the chronicle after the transcript, not its first event.
        "--title", transcript.stem.strip(),
    ]
    started = datetime.now(timezone.utc)
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=1800)
    duration = (datetime.now(timezone.utc) - started).total_seconds()

    manifest_summary: dict[str, Any] | None = None
    manifest_path = run_dir / "manifest.json"
    if manifest_path.exists():
        size = manifest_path.stat().st_size
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_summary = metrics.summarize_manifest(manifest, size)
        except json.JSONDecodeError:
            manifest_summary = {"error": "unparseable manifest", "manifest_size_bytes": size}

    return {
        "transcript": transcript.name,
        "run_id": run_id,
        "returncode": proc.returncode,
        "duration_s": round(duration, 1),
        "manifest": manifest_summary,
        "stdout_tail": proc.stdout[-800:],
        "stderr_tail": proc.stderr[-800:],
    }


def collect_db_state() -> dict[str, Any]:
    entities = probe.probe_entities()
    relationships = probe.probe_relationships()
    chronicles = probe.probe_chronicles()
    counts = probe.probe_counts()
    return {
        "counts": counts,
        "entity_flags": metrics.flag_entities(entities),
        "relationship_flags": metrics.flag_relationships(relationships),
        "overlap": metrics.overlap_consistency(entities),
        "chronicles": chronicles,
        "relationships_sample": relationships[:60],
    }


def evaluate(
    transcripts: list[Path],
    label: str,
    reset: bool = True,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    report: dict[str, Any] = {
        "label": label,
        "generated_at": generated_at,
        "transcripts": [t.name for t in transcripts],
        "reset": None,
        "runs": [],
    }

    if reset:
        print(f"[eval] resetting database (BaselineSeeder)…", flush=True)
        report["reset"] = reset_database()
        if not report["reset"]["ok"]:
            print(f"[eval] WARNING: db reset failed: {report['reset']['stderr_tail']}", flush=True)

    for i, transcript in enumerate(transcripts, 1):
        run_id = f"eval_{_slug(transcript.stem)}"
        print(f"[eval] ({i}/{len(transcripts)}) running {transcript.name} -> {run_id}", flush=True)
        result = run_transcript(transcript, run_id)
        rc = result["returncode"]
        committed = (result.get("manifest") or {}).get("committed_count", "?")
        print(f"[eval]   rc={rc} duration={result['duration_s']}s committed={committed}", flush=True)
        report["runs"].append(result)

    print("[eval] probing database state…", flush=True)
    report["db_state"] = collect_db_state()

    out_dir = EVAL_OUTPUT_DIR / _slug(label)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    (out_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")
    print(f"[eval] report written to {out_dir / 'report.md'}", flush=True)
    return report


def render_markdown(report: dict[str, Any]) -> str:
    db = report.get("db_state", {})
    counts = db.get("counts", {})
    ef = db.get("entity_flags", {})
    rf = db.get("relationship_flags", {})
    overlap = db.get("overlap", {})

    lines: list[str] = []
    lines.append(f"# Pipeline eval report — `{report['label']}`")
    lines.append("")
    lines.append(f"_Generated: {report['generated_at']}_")
    lines.append("")

    # ── Per-run health ───────────────────────────────────────────────
    lines.append("## Runs")
    lines.append("")
    lines.append("| transcript | rc | dur(s) | events | cand.ent | cand.rel | committed | errors | audit_len | reducer_ok |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in report["runs"]:
        m = r.get("manifest") or {}
        lines.append(
            f"| {r['transcript'][:38]} | {r['returncode']} | {r['duration_s']} | "
            f"{m.get('parsed_events','?')} | {m.get('candidate_entities','?')} | "
            f"{m.get('candidate_relations','?')} | {m.get('committed_count','?')} | "
            f"{m.get('errors_count','?')} | {m.get('audit_log_len','?')} | "
            f"{'✅' if m.get('reducer_sane') else '❌'} |"
        )
    lines.append("")

    # Surface any per-run errors
    for r in report["runs"]:
        errs = (r.get("manifest") or {}).get("errors") or []
        if errs:
            lines.append(f"**Errors in {r['transcript']}:**")
            for e in errs:
                lines.append(f"- `[{e.get('node')}]` {e.get('type')}: {e.get('message')}")
            lines.append("")

    # ── Persisted DB state ───────────────────────────────────────────
    lines.append("## Database state (what actually persisted)")
    lines.append("")
    lines.append(f"- entities: **{counts.get('entities', 0)}** "
                 f"(wikidata: {ef.get('with_wikidata', 0)}, geometry: {ef.get('with_geometry', 0)})")
    lines.append(f"- relationships: **{counts.get('relationships', 0)}**")
    lines.append(f"- chronicles: **{counts.get('chronicles', 0)}** "
                 f"(entries: {counts.get('chronicle_entries', 0)}, "
                 f"secondary links: {counts.get('chronicle_entry_entities', 0)})")
    lines.append("")

    if ef.get("by_type"):
        lines.append("**Entities by type:** " + ", ".join(
            f"{k}={v}" for k, v in sorted(ef["by_type"].items(), key=lambda kv: -kv[1])
        ))
        lines.append("")
    if rf.get("by_type"):
        lines.append("**Relationships by type:** " + ", ".join(
            f"{k}={v}" for k, v in sorted(rf["by_type"].items(), key=lambda kv: -kv[1])
        ))
        lines.append("")

    # ── Quality flags ────────────────────────────────────────────────
    lines.append("## Quality flags")
    lines.append("")
    lines.append(f"- short-name review (≤2 chars): {ef.get('short_name_review') or '—'}")
    lines.append(f"- entities missing wikidata_id: {ef.get('missing_wikidata_count', 0)}")
    lines.append(f"- entities missing temporal: {ef.get('missing_temporal_count', 0)}")
    lines.append(f"- entities without geometry: {ef.get('no_geometry_count', 0)}")
    lines.append(f"- duplicate relationships: {len(rf.get('duplicates', []))}")
    lines.append(f"- self-loop relationships: {len(rf.get('self_loops', []))}")
    viols = rf.get("event_range_violations", [])
    lines.append(f"- event-range violations (e.g. defeated_at -> non-event): {len(viols)}")
    for v in viols[:15]:
        lines.append(f"    - {v['source']} —{v['type']}→ {v['target']} ({v['target_type']})")
    lines.append("")

    # ── Overlap consistency ──────────────────────────────────────────
    lines.append("## Overlap consistency (entity dedup across transcripts)")
    lines.append("")
    lines.append(f"- consistent: {'✅ yes' if overlap.get('consistent') else '❌ NO — duplicates found'}")
    if overlap.get("duplicate_names"):
        lines.append("- duplicate names:")
        for d in overlap["duplicate_names"][:20]:
            lines.append(f"    - {d['name']} ×{d['count']}")
    if overlap.get("duplicate_wikidata_ids"):
        lines.append("- duplicate wikidata_ids:")
        for d in overlap["duplicate_wikidata_ids"][:20]:
            lines.append(f"    - {d['wikidata_id']} ×{d['count']}")
    lines.append("")

    # ── Chronicles ───────────────────────────────────────────────────
    lines.append("## Chronicles")
    lines.append("")
    lines.append("| title | status | entries | orphans | secondary links |")
    lines.append("|---|---|---|---|---|")
    for c in db.get("chronicles", []):
        lines.append(
            f"| {str(c.get('title'))[:40]} | {c.get('status')} | {c.get('entry_count')} | "
            f"{c.get('orphan_count')} | {c.get('secondary_links')} |"
        )
    lines.append("")
    return "\n".join(lines)
