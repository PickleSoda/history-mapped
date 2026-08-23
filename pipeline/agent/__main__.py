"""CLI entry point for the historical entity agentic pipeline.

Usage:
    py -m pipeline agent --input transcript.txt --run-id run_001
"""
from __future__ import annotations

import sys
from pathlib import Path

import click

from pipeline.agent.graph.workflow import run_agent


def _echo_result(result) -> None:
    click.echo(f"Parsed events: {len(result['parsed_events'])}")
    click.echo(f"Candidate entities: {len(result['candidate_entities'])}")
    click.echo(f"Candidate relations: {len(result['candidate_relations'])}")
    click.echo(f"Enriched entities: {len(result['enriched_entities'])}")
    click.echo(f"Validation results: {len(result['validation_results'])}")
    click.echo(f"Committed: {len(result['committed'])}")
    click.echo(f"Audit log entries: {len(result['audit_log'])}")
    click.echo(f"Errors: {len(result['errors'])}")

    if result.get("chronicle"):
        click.echo(f"Chronicle: {result['chronicle'].title} ({len(result['chronicle'].entries)} entries)")

    if result["errors"]:
        click.echo("Errors encountered:", err=True)
        for error in result["errors"]:
            click.echo(f"  [{error.node}] {error.error_type}: {error.message}", err=True)
        sys.exit(1)

    click.echo(f"Agent run complete. Artifacts written to output/agent_runs/{result['run_id']}/")


@click.command()
@click.option("--input", "input_path", type=click.Path(exists=True, path_type=Path), default=None, help="Path to raw historical text input file")
@click.option("--from-candidates", "from_candidates", type=click.Path(exists=True, path_type=Path), default=None, help="Path to an opencode-authored candidates.json handoff file (runs the deterministic tail)")
@click.option("--run-id", default=None, help="Deterministic run ID for the artifact directory")
@click.option("--title", default=None, help="Optional chronicle title")
@click.option("--create-chronicle/--no-create-chronicle", default=True, help="Whether to create a chronicle (default: True)")
@click.option("--refresh", is_flag=True, default=False, help="Re-resolve every entity (type/QID/geo/date) and force-update existing rows IN PLACE, preserving entity_id + relationships. Re-runs even previously-completed transcripts.")
def agent(input_path: Path | None, from_candidates: Path | None, run_id: str | None,
          title: str | None, create_chronicle: bool, refresh: bool):
    """Run the historical entity agentic pipeline on a text input."""
    # Configure structured logging
    from pipeline.agent.log_config import configure_logging
    configure_logging()

    if from_candidates:
        from pipeline.agent.graph.workflow import run_agent_from_candidates
        run_id = run_id or from_candidates.parent.name
        click.echo(f"Starting handoff run: {run_id}{' [REFRESH]' if refresh else ''}")
        result = run_agent_from_candidates(str(from_candidates), run_id=run_id,
                                           create_chronicle=create_chronicle, refresh=refresh)
        _echo_result(result)
        return

    if input_path is None:
        raise click.UsageError("Provide --input <transcript.txt> or --from-candidates <candidates.json>")

    raw_text = input_path.read_text(encoding="utf-8")
    run_id = run_id or f"agent_{input_path.stem}"

    click.echo(f"Starting agent run: {run_id}{' [REFRESH]' if refresh else ''}")
    click.echo(f"Input: {input_path} ({len(raw_text)} chars)")
    result = run_agent(raw_text, run_id=run_id, title=title, create_chronicle=create_chronicle, refresh=refresh)

    _echo_result(result)


if __name__ == "__main__":
    agent()
