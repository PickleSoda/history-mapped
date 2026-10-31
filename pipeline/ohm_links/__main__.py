"""OHM links CLI: tags-only Overpass extraction of boundaries and places for the geo-ref backfill."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from pipeline.ohm_links.fetcher import (
    BOUNDARIES_QUERY,
    PLACES_WITH_WIKIDATA_QUERY,
    fetch_elements,
    ids_queries,
    read_ids_file,
)
from pipeline.ohm_links.records import element_to_record
from pipeline.ohm_links.writer import write_manifest, write_records

logger = logging.getLogger(__name__)

console = Console(legacy_windows=False)

RECORDS_FILENAME = "ohm_links.jsonl"
MANIFEST_FILENAME = "manifest.json"


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
    """OHM links: tags-only Overpass extraction (JSONL for pipeline:import-ohm-links)."""
    _configure_logging()


@cli.command("fetch")
@click.option("--run-id", default=None, help="Run directory name (default: UTC timestamp YYYYMMDD-HHMM)")
@click.option(
    "--out-dir",
    type=click.Path(path_type=Path, file_okay=False),
    default=Path("output/ohm_links"),
    show_default=True,
    help="Parent directory for run directories",
)
@click.option("--skip-boundaries", is_flag=True, help='Skip relation["boundary"="administrative"]')
@click.option("--skip-places", is_flag=True, help='Skip node/way/relation["place"]["wikidata"]')
@click.option(
    "--ids-file",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    default=None,
    help="Text file of type/id lines (from pipeline:export-ohm-ref-ids) to fetch by id",
)
def fetch(run_id, out_dir, skip_boundaries, skip_places, ids_file):
    """Fetch OHM tags via Overpass and write <out-dir>/<run-id>/ohm_links.jsonl + manifest.json."""
    queries: list[tuple[str, str]] = []
    if not skip_boundaries:
        queries.append(("boundaries", BOUNDARIES_QUERY))
    if not skip_places:
        queries.append(("places", PLACES_WITH_WIKIDATA_QUERY))
    if ids_file is not None:
        queries.extend(("ids", query) for query in ids_queries(read_ids_file(ids_file)))

    if not queries:
        raise click.UsageError("Nothing to fetch: both queries are skipped and no --ids-file yields ids.")

    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    run_dir = out_dir / run_id

    counts: dict[str, int] = {}
    elements: list[dict] = []
    for source, query in queries:
        logger.info("Fetching %s from Overpass", source)
        source_elements = fetch_elements(query)
        logger.info("Fetched %d %s element(s)", len(source_elements), source)
        counts[f"{source}_elements"] = counts.get(f"{source}_elements", 0) + len(source_elements)
        elements.extend(source_elements)

    records = [record for record in map(element_to_record, elements) if record is not None]
    counts["elements"] = len(elements)
    counts["without_tags"] = len(elements) - len(records)
    counts.update(write_records(records, run_dir / RECORDS_FILENAME))
    write_manifest(run_dir / MANIFEST_FILENAME, run_id, counts)

    table = Table(title=f"OHM links run {run_id}")
    table.add_column("Count")
    table.add_column("Value", justify="right")
    for key, value in counts.items():
        table.add_row(key, str(value))
    console.print(table)
    console.print(f"Wrote {counts['records']} records -> {run_dir / RECORDS_FILENAME}")


if __name__ == "__main__":
    cli()
