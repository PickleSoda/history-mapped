"""OHM links CLI: tags-only Overpass extraction of boundaries and places for the geo-ref backfill."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from itertools import chain
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from pipeline.ohm_links.fetcher import (
    BOUNDARIES_QUERY,
    PLACES_WITH_WIKIDATA_QUERY,
    fetch_elements,
    id_batches,
    ids_query,
    read_ids_file,
)
from pipeline.ohm_links.records import element_to_record
from pipeline.ohm_links.writer import read_jsonl, write_manifest, write_part, write_records

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


def _selected_sources(skip_boundaries: bool, skip_places: bool, ids_file: Path | None) -> list[tuple[str, list[tuple[str, str]]]]:
    """Return [(source, [(label, query), ...])] in merge order: boundaries, places, ids."""
    sources: list[tuple[str, list[tuple[str, str]]]] = []
    if not skip_boundaries:
        sources.append(("boundaries", [("boundaries", BOUNDARIES_QUERY)]))
    if not skip_places:
        sources.append(("places", [("places", PLACES_WITH_WIKIDATA_QUERY)]))
    if ids_file is not None:
        batches = list(id_batches(read_ids_file(ids_file)))
        if batches:
            total = len(batches)
            sources.append(
                (
                    "ids",
                    [
                        (f"ids batch {index}/{total} ({len(batch)} ids)", ids_query(batch))
                        for index, batch in enumerate(batches, start=1)
                    ],
                )
            )
    return sources


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
@click.option("--resume", is_flag=True, help="Keep a source's existing part file in the run directory instead of re-fetching it")
def fetch(run_id, out_dir, skip_boundaries, skip_places, ids_file, resume):
    """Fetch OHM tags via Overpass into <out-dir>/<run-id>/: one part file per source
    (boundaries.jsonl, places.jsonl, ids.jsonl), the merged ohm_links.jsonl, then manifest.json."""
    sources = _selected_sources(skip_boundaries, skip_places, ids_file)
    if not sources:
        raise click.UsageError("Nothing to fetch: both queries are skipped and no --ids-file yields ids.")

    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    run_dir = out_dir / run_id

    counts: dict[str, int] = {"elements": 0, "skipped": 0}
    for source, queries in sources:
        part_path = run_dir / f"{source}.jsonl"
        if resume and part_path.exists():
            logger.info("Resume: keeping %s, not re-fetching %s", part_path, source)
            counts[f"{source}_records"] = sum(1 for _ in read_jsonl(part_path))
            continue

        records: list[dict] = []
        source_elements = 0
        for label, query in queries:
            logger.info("Fetching %s", label)
            started = time.monotonic()
            elements = fetch_elements(query)
            mapped = [record for record in map(element_to_record, elements) if record is not None]
            logger.info(
                "Fetched %s: %d element(s), %d record(s) in %.1f s",
                label,
                len(elements),
                len(mapped),
                time.monotonic() - started,
            )
            source_elements += len(elements)
            counts["skipped"] += len(elements) - len(mapped)
            records.extend(mapped)
            del elements

        counts["elements"] += source_elements
        counts[f"{source}_elements"] = source_elements
        counts[f"{source}_records"] = write_part(records, part_path)
        logger.info("Wrote %d %s record(s) -> %s", counts[f"{source}_records"], source, part_path)

    merged = chain.from_iterable(read_jsonl(run_dir / f"{source}.jsonl") for source, _ in sources)
    counts.update(write_records(merged, run_dir / RECORDS_FILENAME))
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
