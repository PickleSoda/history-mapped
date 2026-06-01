"""CLI dispatcher: unified entry point for history-mapped pipeline.

Routes commands to appropriate submodules:
  - Wikidata scraping, topic extraction: pipeline.wikidata
  - OHM borders fetch/parse/build: pipeline.ohm_borders

Maintained for backward compatibility. New code should import from submodules directly.

Examples:
  python -m pipeline scrape --type political_entity
  python -m pipeline topic "Roman Empire"
  python -m pipeline borders fetch
  python -m pipeline wikidata scrape --type political_entity  (alternative)
  python -m pipeline ohm-borders fetch  (alternative)
"""

import logging
import re
import shutil
from pathlib import Path

import click
from rich.console import Console

from pipeline.wikidata.__main__ import cli as wikidata_cli
from pipeline.ohm_borders.__main__ import cli as ohm_cli
from pipeline.ohm_collections.__main__ import cli as collections_cli
from pipeline.ohm_borders.fetcher import load_query_text
from pipeline.ohm_borders.stages import (
    default_parallelism,
    run_build_stage,
    run_enrich_stage,
    run_fetch_stage,
    run_parse_stage,
)
from pipeline.ohm_borders.enricher import enrich_output_jsonl_missing_qids

console = Console(legacy_windows=False)

_LEGACY_SCRAPE_COMMANDS = ["scrape", "dedup", "topic"]
_LEGACY_BORDERS_COMMANDS = {"borders": ["extract-subgraph", "build-index", "fetch", "parse", "enrich", "build", "run", "enrich-output-names", "relations-scan", "relations-enrich", "relations-build", "relations-run"]}
def _configure_logging() -> None:
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@click.group()
def cli():
    """history-mapped data pipeline: scrape Wikidata entities and OHM borders."""
    _configure_logging()




# === WIKIDATA SUBCOMMANDS (legacy) ===
# Re-export wikidata commands for backward compatibility.
# These can be called as: python -m pipeline scrape, python -m pipeline topic, etc.

# Import the actual command functions from wikidata submodule
from pipeline.wikidata.__main__ import (
    scrape as wikidata_scrape_impl,
    dedup as wikidata_dedup_impl,
    topic as wikidata_topic_impl,
)

# Register wikidata commands under the top-level CLI for legacy compatibility
cli.add_command(wikidata_scrape_impl, name="scrape")
cli.add_command(wikidata_dedup_impl, name="dedup")
cli.add_command(wikidata_topic_impl, name="topic")
cli.add_command(collections_cli, name="collections")


# === OHM BORDERS SUBCOMMANDS (legacy) ===
# Create a borders subgroup that re-exports commands from ohm_borders module
from pipeline.ohm_borders.__main__ import (
    build_index_command,
    extract_subgraph,
    fetch,
    parse,
    enrich,
    build,
    run_full,
    enrich_output_names,
    _run_borders_pipeline,
    relations_scan,
    relations_enrich,
    relations_build,
    relations_run,
)


# Create a borders subgroup
@cli.group(invoke_without_command=True)
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
def borders(ctx, output, run_id, artifact_dir, query_file, raw_shard_size, parsed_shard_size, parse_workers, build_workers, enrich_batch_size, enrich_workers, resume, force):
    """OHM borders pipeline (legacy: delegates to pipeline.ohm_borders)."""
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
    elif ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


# Register ohm_borders commands under the borders subgroup
borders.add_command(extract_subgraph, name="extract-subgraph")
borders.add_command(build_index_command, name="build-index")
borders.add_command(fetch, name="fetch")
borders.add_command(parse, name="parse")
borders.add_command(enrich, name="enrich")
borders.add_command(build, name="build")
borders.add_command(run_full, name="run")
borders.add_command(enrich_output_names, name="enrich-output-names")
borders.add_command(relations_scan, name="relations-scan")
borders.add_command(relations_enrich, name="relations-enrich")
borders.add_command(relations_build, name="relations-build")
borders.add_command(relations_run, name="relations-run")


def _slugify(text: str) -> str:
    """Convert a string to a safe filename slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = slug.strip("_")
    return slug[:80]


if __name__ == "__main__":
    cli()
