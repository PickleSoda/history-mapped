"""OHM borders extraction and enrichment pipeline CLI."""

import logging
import shutil
from pathlib import Path

import click
from rich.console import Console

from pipeline.ohm_borders.fetcher import load_query_text
from pipeline.ohm_borders.index_builder import build_index
from pipeline.ohm_borders.stages import (
    default_parallelism,
    run_build_stage,
    run_enrich_stage,
    run_extract_subgraph_stage,
    run_fetch_stage,
    run_parse_stage,
    run_relations_build_stage,
    run_relations_enrich_stage,
    run_relations_scan_stage,
)
from pipeline.ohm_borders.enricher import enrich_output_jsonl_missing_qids

console = Console(legacy_windows=False)


def _default_index_path(input_path: Path) -> Path:
    return input_path.parent / "overpass.sqlite3"


def _configure_logging() -> None:
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _run_borders_pipeline(
    *,
    run_id,
    artifact_dir,
    query_file,
    output,
    raw_shard_size,
    parsed_shard_size,
    parse_workers,
    build_workers,
    enrich_batch_size,
    enrich_workers,
    resume,
    force,
):
    fetch_result = run_fetch_stage(
        run_id=run_id,
        artifact_dir=artifact_dir,
        query=load_query_text(query_file),
        raw_shard_size=raw_shard_size or 200,
        resume=resume,
        force=force,
    )
    console.print(f"Fetch {fetch_result['status']}: {fetch_result['element_count']} elements -> {fetch_result['raw_path']}")

    resolved_parallelism = default_parallelism()
    parse_result = run_parse_stage(
        run_id=run_id,
        artifact_dir=artifact_dir,
        parsed_shard_size=parsed_shard_size or 100,
        parse_workers=parse_workers or resolved_parallelism,
        resume=resume,
        force=force,
    )
    console.print(f"Parse {parse_result['status']}: {parse_result['polity_count']} polities across {parse_result['shard_count']} shards")

    enrich_result = run_enrich_stage(
        run_id=run_id,
        artifact_dir=artifact_dir,
        enrich_batch_size=enrich_batch_size or 50,
        enrich_workers=enrich_workers or 4,
        resume=resume,
        force=force,
    )
    console.print(f"Enrich {enrich_result['status']}: {enrich_result['qid_count']} unique QIDs across {enrich_result['shard_count']} shards")

    build_result = run_build_stage(
        run_id=run_id,
        artifact_dir=artifact_dir,
        resume=resume,
        force=force,
        build_workers=build_workers,
    )

    final_output_path = build_result["final_path"]
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(build_result["final_path"], output)
        final_output_path = output

    console.print(f"Build {build_result['status']}: {build_result['record_count']} records -> {build_result['final_path']}")
    console.print(f"Borders run complete -> {final_output_path}")


def _run_relations_pipeline(*, run_id, artifact_dir, resume, force):
    scan_result = run_relations_scan_stage(
        run_id=run_id,
        artifact_dir=artifact_dir,
        resume=resume,
        force=force,
    )
    console.print(f"Relations scan {scan_result['status']}: {scan_result['candidate_count']} candidates")

    enrich_result = run_relations_enrich_stage(
        run_id=run_id,
        artifact_dir=artifact_dir,
        resume=resume,
        force=force,
    )
    console.print(f"Relations enrich {enrich_result['status']}: {enrich_result['candidate_count']} enriched candidates")

    build_result = run_relations_build_stage(
        run_id=run_id,
        artifact_dir=artifact_dir,
        resume=resume,
        force=force,
    )
    console.print(
        f"Relations build completed: {build_result['entity_count']} entities, {build_result['hint_count']} hints"
    )

@click.group(invoke_without_command=True)
@click.option("--output", type=click.Path(path_type=Path, dir_okay=False), default=None, help="Compatibility mode: copy the final merged JSONL to this path")
@click.option("--run-id", default=None, help="Deterministic run id for the artifact directory")
@click.option("--artifact-dir", type=click.Path(path_type=Path, file_okay=False), default=None, help="Explicit artifact directory override")
@click.option("--query-file", type=click.Path(path_type=Path, exists=True, dir_okay=False), default=None, help="Override Overpass query file")
@click.option("--raw-shard-size", type=int, default=None, help="Relations per raw fetch shard")
@click.option("--parsed-shard-size", type=int, default=None, help="Polities per parsed shard")
@click.option("--parse-workers", type=int, default=None, help="Reserved worker count for parallel parse stages")
@click.option("--build-workers", type=int, default=None, help="Reserved worker count for parallel build stage")
@click.option("--enrich-batch-size", type=int, default=None, help="Unique Wikidata QIDs per enrichment shard")
@click.option("--enrich-workers", type=int, default=None, help="Bounded worker count for enrichment batches")
@click.option("--resume", is_flag=True, help="Skip writing existing stage artifacts when possible")
@click.option("--force", is_flag=True, help="Overwrite existing stage artifacts")
@click.pass_context
def cli(ctx, output, run_id, artifact_dir, query_file, raw_shard_size, parsed_shard_size, parse_workers, build_workers, enrich_batch_size, enrich_workers, resume, force):
    """OHM borders extraction and enrichment."""
    _configure_logging()
    
    if ctx.invoked_subcommand is None and output is not None:
        _run_borders_pipeline(
            run_id=run_id,
            artifact_dir=artifact_dir,
            query_file=query_file,
            output=output,
            raw_shard_size=raw_shard_size,
            parsed_shard_size=parsed_shard_size,
            parse_workers=parse_workers,
            build_workers=build_workers,
            enrich_batch_size=enrich_batch_size,
            enrich_workers=enrich_workers,
            resume=resume,
            force=force,
        )
        return

    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


@cli.command("extract-subgraph")
@click.option("--input", "input_path", required=True, type=click.Path(path_type=Path, exists=True, dir_okay=False), help="Existing global overpass.json to subset")
@click.option("--index-path", type=click.Path(path_type=Path, dir_okay=False), default=None, help="Optional reusable SQLite index path for subgraph extraction")
@click.option("--seed-qid", default=None, help="Seed polity Wikidata QID")
@click.option("--seed-name", default=None, help="Exact OHM seed polity name fallback")
@click.option("--build-index-if-missing", is_flag=True, help="Build the default or explicit SQLite index before extraction when it does not exist yet")
@click.option("--auto-select-fuzzy", is_flag=True, help="Allow indexed extraction to auto-select the top fuzzy seed-name match")
@click.option("--run-id", default=None, help="Deterministic run id for the artifact directory")
@click.option("--artifact-dir", type=click.Path(path_type=Path, file_okay=False), default=None, help="Explicit artifact directory override")
@click.option("--max-depth", type=int, required=True, help="Maximum recursive graph depth from the seed")
@click.option("--max-nodes", type=int, required=True, help="Maximum included relations before truncation")
@click.option("--raw-shard-size", type=int, default=200, show_default=True, help="Relations per extracted raw shard")
@click.option("--resume", is_flag=True, help="Reuse existing subset artifacts when parameters match")
@click.option("--force", is_flag=True, help="Overwrite existing subset artifacts")
def extract_subgraph(input_path, index_path, seed_qid, seed_name, build_index_if_missing, auto_select_fuzzy, run_id, artifact_dir, max_depth, max_nodes, raw_shard_size, resume, force):
    """Extract a country-centered OHM border subgraph from an existing Overpass payload."""
    result = run_extract_subgraph_stage(
        run_id=run_id,
        artifact_dir=artifact_dir,
        input_path=input_path,
        index_path=index_path,
        seed_qid=seed_qid,
        seed_name=seed_name,
        build_index_if_missing=build_index_if_missing,
        max_depth=max_depth,
        max_nodes=max_nodes,
        raw_shard_size=raw_shard_size,
        auto_select_fuzzy=auto_select_fuzzy,
        resume=resume,
        force=force,
    )

    console.print(
        f"Extract subgraph {result['status']}: {result.get('relation_count', 'existing')} relations -> {result['raw_path']}"
    )


@cli.command("build-index")
@click.option("--input", "input_path", required=True, type=click.Path(path_type=Path, exists=True, dir_okay=False), help="Existing global overpass.json to index")
@click.option("--index-path", type=click.Path(path_type=Path, dir_okay=False), default=None, help="Optional SQLite index output path; defaults to a sibling overpass.sqlite3")
@click.option("--force", is_flag=True, help="Rebuild an existing incompatible index")
def build_index_command(input_path, index_path, force):
    """Build or reuse the reusable SQLite index for indexed subgraph extraction."""
    resolved_index_path = index_path or _default_index_path(input_path)
    result = build_index(input_path, index_path=resolved_index_path, force=force)
    console.print(
        f"Build index {result['status']}: {result.get('relation_count', 'existing')} relations -> {result['index_path']}"
    )


@cli.command("fetch")
@click.option("--run-id", default=None, help="Deterministic run id for the artifact directory")
@click.option("--artifact-dir", type=click.Path(path_type=Path, file_okay=False), default=None, help="Explicit artifact directory override")
@click.option("--query-file", type=click.Path(path_type=Path, exists=True, dir_okay=False), default=None, help="Override Overpass query file")
@click.option("--raw-shard-size", type=int, default=None, help="Relations per raw fetch shard")
@click.option("--resume", is_flag=True, help="Skip fetch when raw/overpass.json already exists")
@click.option("--force", is_flag=True, help="Overwrite existing raw/overpass.json even when resuming")
def fetch(run_id, artifact_dir, query_file, raw_shard_size, resume, force):
    """Fetch raw OHM border data into staged artifacts."""
    result = run_fetch_stage(
        run_id=run_id,
        artifact_dir=artifact_dir,
        query=load_query_text(query_file),
        raw_shard_size=raw_shard_size or 200,
        resume=resume,
        force=force,
    )

    console.print(f"Fetch {result['status']}: {result['element_count']} elements -> {result['raw_path']}")


@cli.command("parse")
@click.option("--run-id", default=None, help="Deterministic run id for the artifact directory")
@click.option("--artifact-dir", type=click.Path(path_type=Path, file_okay=False), default=None, help="Explicit artifact directory override")
@click.option("--parsed-shard-size", type=int, default=None, help="Polities per parsed shard")
@click.option("--parse-workers", type=int, default=None, help="Reserved worker count for parallel parse stages")
@click.option("--resume", is_flag=True, help="Skip writing parsed shards that already exist")
@click.option("--force", is_flag=True, help="Overwrite existing parsed shards")
def parse(run_id, artifact_dir, parsed_shard_size, parse_workers, resume, force):
    """Parse raw OHM border elements into staged JSONL shards."""
    resolved_parallelism = default_parallelism()
    result = run_parse_stage(
        run_id=run_id,
        artifact_dir=artifact_dir,
        parsed_shard_size=parsed_shard_size or 100,
        parse_workers=parse_workers or resolved_parallelism,
        resume=resume,
        force=force,
    )

    console.print(f"Parse {result['status']}: {result['polity_count']} polities across {result['shard_count']} shards")


@cli.command("enrich")
@click.option("--run-id", default=None, help="Deterministic run id for the artifact directory")
@click.option("--artifact-dir", type=click.Path(path_type=Path, file_okay=False), default=None, help="Explicit artifact directory override")
@click.option("--enrich-batch-size", type=int, default=None, help="Unique Wikidata QIDs per enrichment shard")
@click.option("--enrich-workers", type=int, default=None, help="Bounded worker count for enrichment batches")
@click.option("--enrich-names", is_flag=True, help="After SPARQL enrichment, also search Wikidata by name for missing Wikidata IDs")
@click.option("--resume", is_flag=True, help="Skip writing enrichment shards that already exist")
@click.option("--force", is_flag=True, help="Overwrite existing enrichment shards")
def enrich(run_id, artifact_dir, enrich_batch_size, enrich_workers, enrich_names, resume, force):
    """Enrich parsed OHM border shards with batched Wikidata metadata."""
    result = run_enrich_stage(
        run_id=run_id,
        artifact_dir=artifact_dir,
        enrich_batch_size=enrich_batch_size or 50,
        enrich_workers=enrich_workers or 4,
        enrich_names=enrich_names,
        resume=resume,
        force=force,
    )

    console.print(f"Enrich {result['status']}: {result['qid_count']} unique QIDs across {result['shard_count']} shards")


@cli.command("build")
@click.option("--run-id", default=None, help="Deterministic run id for the artifact directory")
@click.option("--artifact-dir", type=click.Path(path_type=Path, file_okay=False), default=None, help="Explicit artifact directory override")
@click.option("--resume", is_flag=True, help="Skip writing build outputs that already exist")
@click.option("--force", is_flag=True, help="Overwrite existing build outputs")
@click.option("--build-workers", type=int, default=None, help="Reserved worker count for parallel build stage")
def build(run_id, artifact_dir, resume, force, build_workers):
    """Build importer-facing JSONL shards and the final merged OHM borders file."""
    result = run_build_stage(
        run_id=run_id,
        artifact_dir=artifact_dir,
        resume=resume,
        force=force,
        build_workers=build_workers,
    )

    console.print(f"Build {result['status']}: {result['record_count']} records -> {result['final_path']}")


@cli.command("run")
@click.option("--run-id", default=None, help="Deterministic run id for the artifact directory")
@click.option("--artifact-dir", type=click.Path(path_type=Path, file_okay=False), default=None, help="Explicit artifact directory override")
@click.option("--query-file", type=click.Path(path_type=Path, exists=True, dir_okay=False), default=None, help="Override Overpass query file")
@click.option("--output", type=click.Path(path_type=Path, dir_okay=False), default=None, help="Optional path for a copied final merged JSONL")
@click.option("--raw-shard-size", type=int, default=None, help="Relations per raw fetch shard")
@click.option("--parsed-shard-size", type=int, default=None, help="Polities per parsed shard")
@click.option("--parse-workers", type=int, default=None, help="Reserved worker count for parallel parse stages")
@click.option("--build-workers", type=int, default=None, help="Reserved worker count for parallel build stage")
@click.option("--enrich-batch-size", type=int, default=None, help="Unique Wikidata QIDs per enrichment shard")
@click.option("--enrich-workers", type=int, default=None, help="Bounded worker count for enrichment batches")
@click.option("--resume", is_flag=True, help="Skip writing existing stage artifacts when possible")
@click.option("--force", is_flag=True, help="Overwrite existing stage artifacts")
def run_full(run_id, artifact_dir, query_file, output, raw_shard_size, parsed_shard_size, parse_workers, build_workers, enrich_batch_size, enrich_workers, resume, force):
    """Run the full staged OHM borders workflow."""
    _run_borders_pipeline(
        run_id=run_id,
        artifact_dir=artifact_dir,
        query_file=query_file,
        output=output,
        raw_shard_size=raw_shard_size,
        parsed_shard_size=parsed_shard_size,
        parse_workers=parse_workers,
        build_workers=build_workers,
        enrich_batch_size=enrich_batch_size,
        enrich_workers=enrich_workers,
        resume=resume,
        force=force,
    )


@cli.command("relations-scan")
@click.option("--run-id", default=None, help="Deterministic run id for the artifact directory")
@click.option("--artifact-dir", type=click.Path(path_type=Path, file_okay=False), default=None, help="Explicit artifact directory override")
@click.option("--resume", is_flag=True, help="Skip writing relation scan shards that already exist")
@click.option("--force", is_flag=True, help="Overwrite existing relation scan shards")
def relations_scan(run_id, artifact_dir, resume, force):
    result = run_relations_scan_stage(
        run_id=run_id,
        artifact_dir=artifact_dir,
        resume=resume,
        force=force,
    )

    console.print(f"Relations scan {result['status']}: {result['candidate_count']} candidates")


@cli.command("relations-enrich")
@click.option("--run-id", default=None, help="Deterministic run id for the artifact directory")
@click.option("--artifact-dir", type=click.Path(path_type=Path, file_okay=False), default=None, help="Explicit artifact directory override")
@click.option("--resume", is_flag=True, help="Skip writing relation enrich shards that already exist")
@click.option("--force", is_flag=True, help="Overwrite existing relation enrich shards")
def relations_enrich(run_id, artifact_dir, resume, force):
    result = run_relations_enrich_stage(
        run_id=run_id,
        artifact_dir=artifact_dir,
        resume=resume,
        force=force,
    )

    console.print(f"Relations enrich {result['status']}: {result['candidate_count']} enriched candidates")


@cli.command("relations-build")
@click.option("--run-id", default=None, help="Deterministic run id for the artifact directory")
@click.option("--artifact-dir", type=click.Path(path_type=Path, file_okay=False), default=None, help="Explicit artifact directory override")
@click.option("--resume", is_flag=True, help="Skip writing final relation outputs that already exist")
@click.option("--force", is_flag=True, help="Overwrite existing final relation outputs")
def relations_build(run_id, artifact_dir, resume, force):
    result = run_relations_build_stage(
        run_id=run_id,
        artifact_dir=artifact_dir,
        resume=resume,
        force=force,
    )

    console.print(f"Relations build completed: {result['entity_count']} entities, {result['hint_count']} hints")


@cli.command("relations-run")
@click.option("--run-id", default=None, help="Deterministic run id for the artifact directory")
@click.option("--artifact-dir", type=click.Path(path_type=Path, file_okay=False), default=None, help="Explicit artifact directory override")
@click.option("--resume", is_flag=True, help="Skip writing existing relation stage artifacts when possible")
@click.option("--force", is_flag=True, help="Overwrite existing relation stage artifacts")
def relations_run(run_id, artifact_dir, resume, force):
    _run_relations_pipeline(
        run_id=run_id,
        artifact_dir=artifact_dir,
        resume=resume,
        force=force,
    )


@cli.command("enrich-output-names")
@click.option("--input", "input_path", required=True, type=click.Path(path_type=Path, exists=True, dir_okay=False), help="Built or final OHM borders JSONL to post-process")
@click.option("--output", "output_path", required=True, type=click.Path(path_type=Path, dir_okay=False), help="Destination JSONL with name-search Wikidata enrichment applied")
@click.option("--enrich-batch-size", type=int, default=50, show_default=True, help="Batch size for Wikidata metadata hydration after name search")
def enrich_output_names(input_path, output_path, enrich_batch_size):
    """Search Wikidata by name for OHM border records missing QIDs and write an enriched JSONL."""
    result = enrich_output_jsonl_missing_qids(
        input_path=input_path,
        output_path=output_path,
        batch_size=enrich_batch_size,
    )

    console.print(
        "Name-search enrichment complete: "
        f"{result['record_count']} records, "
        f"searched {result['searched_count']}, "
        f"matched {result['matched_count']} -> {result['output_path']}"
    )


@cli.command("events-scan")
@click.option("--run-id", default=None, help="Deterministic run id for the artifact directory")
@click.option("--artifact-dir", type=click.Path(path_type=Path, file_okay=False), default=None, help="Explicit artifact directory override")
@click.option("--candidate-shard-size", type=int, default=500, show_default=True, help="Event references per candidate shard")
@click.option("--resume", is_flag=True, help="Skip writing event scan shards that already exist")
@click.option("--force", is_flag=True, help="Overwrite existing event scan shards")
def events_scan(run_id, artifact_dir, candidate_shard_size, resume, force):
    """Extract event references from parsed OHM border shards."""
    from pipeline.ohm_borders.stage_events import run_event_scan_stage
    from pipeline.ohm_borders.stage_common import resolve_artifact_dir

    resolved_artifact_dir = resolve_artifact_dir(run_id, artifact_dir)
    result = run_event_scan_stage(
        run_id=run_id,
        artifact_dir=resolved_artifact_dir,
        candidate_shard_size=candidate_shard_size,
    )
    console.print(f"Events scan {result['status']}: {result['reference_count']} references")


@cli.command("events-enrich")
@click.option("--run-id", default=None, help="Deterministic run id for the artifact directory")
@click.option("--artifact-dir", type=click.Path(path_type=Path, file_okay=False), default=None, help="Explicit artifact directory override")
@click.option("--event-enrich-batch-size", type=int, default=50, show_default=True, help="Unique Wikidata QIDs per enrichment shard")
@click.option("--event-enrich-workers", type=int, default=4, show_default=True, help="Bounded worker count for event enrichment")
@click.option("--resume", is_flag=True, help="Skip writing event enrich shards that already exist")
@click.option("--force", is_flag=True, help="Overwrite existing event enrich shards")
def events_enrich(run_id, artifact_dir, event_enrich_batch_size, event_enrich_workers, resume, force):
    """Enrich event references with Wikidata metadata."""
    console.print("Event enrichment not yet fully implemented.")


@cli.command("events-build")
@click.option("--run-id", default=None, help="Deterministic run id for the artifact directory")
@click.option("--artifact-dir", type=click.Path(path_type=Path, file_okay=False), default=None, help="Explicit artifact directory override")
@click.option("--resume", is_flag=True, help="Skip writing final event outputs that already exist")
@click.option("--force", is_flag=True, help="Overwrite existing final event outputs")
def events_build(run_id, artifact_dir, resume, force):
    """Build final event reference and match files."""
    from pipeline.ohm_borders.stage_events import run_event_build_stage
    from pipeline.ohm_borders.stage_common import resolve_artifact_dir

    resolved_artifact_dir = resolve_artifact_dir(run_id, artifact_dir)
    result = run_event_build_stage(run_id=run_id, artifact_dir=resolved_artifact_dir)
    console.print(f"Events build {result['status']}")


@cli.command("events-run")
@click.option("--run-id", default=None, help="Deterministic run id for the artifact directory")
@click.option("--artifact-dir", type=click.Path(path_type=Path, file_okay=False), default=None, help="Explicit artifact directory override")
@click.option("--candidate-shard-size", type=int, default=500, show_default=True, help="Event references per candidate shard")
@click.option("--event-enrich-batch-size", type=int, default=50, show_default=True, help="Unique Wikidata QIDs per enrichment shard")
@click.option("--event-enrich-workers", type=int, default=4, show_default=True, help="Bounded worker count for event enrichment")
@click.option("--resume", is_flag=True, help="Skip writing existing event stage artifacts when possible")
@click.option("--force", is_flag=True, help="Overwrite existing event stage artifacts")
def events_run(run_id, artifact_dir, candidate_shard_size, event_enrich_batch_size, event_enrich_workers, resume, force):
    """Run the full event extraction workflow."""
    from pipeline.ohm_borders.stage_events import run_event_scan_stage, run_event_build_stage
    from pipeline.ohm_borders.stage_common import resolve_artifact_dir

    resolved_artifact_dir = resolve_artifact_dir(run_id, artifact_dir)
    run_event_scan_stage(run_id=run_id, artifact_dir=resolved_artifact_dir, candidate_shard_size=candidate_shard_size)
    console.print("Events scan complete.")
    console.print("Events enrich complete (placeholder).")
    run_event_build_stage(run_id=run_id, artifact_dir=resolved_artifact_dir)
    console.print("Events build complete.")


if __name__ == "__main__":
    cli()
