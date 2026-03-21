"""CLI entry point: python -m pipeline.scrape ..."""

import click
from rich.console import Console

from pipeline.config import settings, ENTITY_GROUPS
from pipeline.scraper.wikidata import WikidataScraper
from pipeline.scraper.wikipedia import WikipediaEnricher
from pipeline.mapper.entity_mapper import EntityMapper
from pipeline.dedup.deduplicator import Deduplicator

console = Console()


@click.group()
def cli():
    """WikiGlobe data pipeline."""
    pass


@cli.command()
@click.option("--type", "entity_type", help="Single entity_type to scrape (e.g. political_entity)")
@click.option("--group", "entity_group", help="Scrape all types in a group (POLITY, PLACE, EVENT, ECONOMY, CULTURE)")
@click.option("--start-year", type=int, default=None, help="Filter: earliest year (negative = BCE)")
@click.option("--end-year", type=int, default=None, help="Filter: latest year")
@click.option("--limit", type=int, default=100, help="Max entities per type")
@click.option("--skip-wikipedia", is_flag=True, help="Skip Wikipedia enrichment (Wikidata only)")
@click.option("--output-dir", default=None, help="Override output directory")
def scrape(entity_type, entity_group, start_year, end_year, limit, skip_wikipedia, output_dir):
    """Scrape entities from Wikidata and optionally enrich from Wikipedia."""
    import os, orjson
    from pathlib import Path

    out = Path(output_dir or settings.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Resolve which types to scrape
    if entity_type:
        types_to_scrape = [entity_type]
    elif entity_group:
        types_to_scrape = ENTITY_GROUPS.get(entity_group.upper(), [])
        if not types_to_scrape:
            console.print(f"[red]Unknown group: {entity_group}[/red]")
            raise SystemExit(1)
    else:
        console.print("[red]Specify --type or --group[/red]")
        raise SystemExit(1)

    wd = WikidataScraper()
    wp = WikipediaEnricher() if not skip_wikipedia else None
    mapper = EntityMapper()
    dedup = Deduplicator()

    for etype in types_to_scrape:
        console.rule(f"[bold blue]{etype}")

        # Step 1: SPARQL query → raw Wikidata results
        console.print(f"  Querying Wikidata for {etype} (limit={limit})…")
        raw_items = wd.query_entities(etype, limit=limit, start_year=start_year, end_year=end_year)
        console.print(f"  → {len(raw_items)} items from Wikidata")

        if not raw_items:
            continue

        # Step 2: Enrich with Wikipedia summaries
        if wp:
            console.print("  Enriching from Wikipedia…")
            raw_items = wp.enrich_batch(raw_items)

        # Step 3: Map to entity schema
        console.print("  Mapping to entity schema…")
        entities = [mapper.map(item, etype) for item in raw_items]
        entities = [e for e in entities if e is not None]

        # Step 4: Deduplicate within batch
        entities = dedup.deduplicate(entities)
        console.print(f"  → {len(entities)} unique entities after dedup")

        # Step 5: Write JSONL
        outfile = out / f"{etype}.jsonl"
        with open(outfile, "ab") as f:
            for entity in entities:
                f.write(orjson.dumps(entity) + b"\n")

        console.print(f"  ✓ Written to {outfile}")

    console.print("\n[bold green]Done.[/bold green]")


@cli.command()
@click.argument("jsonl_file", type=click.Path(exists=True))
@click.option("--check-db", is_flag=True, help="Also check against existing DB records")
def dedup(jsonl_file, check_db):
    """Deduplicate a JSONL file in-place."""
    import orjson
    from pathlib import Path

    deduplicator = Deduplicator(check_db=check_db)
    path = Path(jsonl_file)

    with open(path, "rb") as f:
        entities = [orjson.loads(line) for line in f if line.strip()]

    before = len(entities)
    entities = deduplicator.deduplicate(entities)
    after = len(entities)

    with open(path, "wb") as f:
        for entity in entities:
            f.write(orjson.dumps(entity) + b"\n")

    console.print(f"Dedup: {before} → {after} ({before - after} removed)")


if __name__ == "__main__":
    cli()
