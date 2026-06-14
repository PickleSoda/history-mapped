"""CLI for the reproducible pipeline eval harness.

Examples:
    # Reset the DB and run every transcript, label the report "iter1":
    py -m pipeline.agent.eval --label iter1

    # Quick loop on just the two Alexander transcripts, no reset:
    py -m pipeline.agent.eval --label alex --no-reset --only alexander

    # First two transcripts only:
    py -m pipeline.agent.eval --label smoke --limit 2
"""
from __future__ import annotations

import sys
from pathlib import Path

import click

from pipeline.agent.eval.harness import DEFAULT_TRANSCRIPT_DIR, evaluate


@click.command()
@click.option("--label", required=True, help="Report label (folder under output/eval_runs/)")
@click.option("--transcripts-dir", type=click.Path(path_type=Path, file_okay=False),
              default=DEFAULT_TRANSCRIPT_DIR, show_default=True, help="Directory of .txt transcripts")
@click.option("--reset/--no-reset", default=True, show_default=True,
              help="Nuke + reseed the blank baseline before running")
@click.option("--only", default=None, help="Case-insensitive substring filter on transcript filename")
@click.option("--limit", type=int, default=None, help="Run at most N transcripts")
@click.option("--chronicles/--no-chronicles", "create_chronicle", default=True, show_default=True,
              help="Build a chronicle per transcript (use --no-chronicles to seed entities/relations only)")
def main(label: str, transcripts_dir: Path, reset: bool, only: str | None, limit: int | None,
         create_chronicle: bool):
    transcripts = sorted(transcripts_dir.glob("*.txt"))
    if only:
        needle = only.lower()
        transcripts = [t for t in transcripts if needle in t.name.lower()]
    if limit:
        transcripts = transcripts[:limit]

    if not transcripts:
        click.echo(f"No transcripts matched in {transcripts_dir}", err=True)
        sys.exit(1)

    click.echo(f"[eval] label={label} reset={reset} transcripts={len(transcripts)}")
    for t in transcripts:
        click.echo(f"        - {t.name}")

    report = evaluate(transcripts, label=label, reset=reset, create_chronicle=create_chronicle)

    counts = report.get("db_state", {}).get("counts", {})
    failed = [r["transcript"] for r in report["runs"] if r["returncode"] != 0]
    click.echo("")
    click.echo(f"[eval] DONE. entities={counts.get('entities')} "
               f"relationships={counts.get('relationships')} "
               f"chronicles={counts.get('chronicles')}")
    if failed:
        click.echo(f"[eval] runs with non-zero exit: {failed}")


if __name__ == "__main__":
    main()
