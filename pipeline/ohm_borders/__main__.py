"""OHM borders extraction and enrichment pipeline CLI."""

import logging
import shutil
from pathlib import Path

import click
from rich.console import Console

from pipeline.ohm_borders.fetcher import load_query_text
from pipeline.ohm_borders.stages import (
    default_parallelism,
    run_build_stage,
    run_enrich_stage,
    run_fetch_stage,
    run_parse_stage,
    run_relations_build_stage,
    run_relations_enrich_stage,
    run_relations_scan_stage,
)
from pipeline.ohm_borders.enricher import enrich_output_jsonl_missing_qids

console = Console(legacy_windows=False)


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


if __name__ == "__main__":
    cli()
