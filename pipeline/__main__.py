"""CLI entry point: python -m pipeline.scrape ..."""

import re
import shutil
from pathlib import Path

import click
import orjson
from rich.console import Console

from pipeline.config import settings, ENTITY_GROUPS, TYPE_TO_GROUP
from pipeline.ohm_borders.fetcher import load_query_text
from pipeline.ohm_borders.stages import (
    default_parallelism,
    run_build_stage,
    run_enrich_stage,
    run_fetch_stage,
    run_parse_stage,
)
from pipeline.scraper.wikidata import WikidataScraper
from pipeline.scraper.wikipedia import WikipediaEnricher
from pipeline.scraper.topic import TopicScraper
from pipeline.mapper.entity_mapper import EntityMapper
from pipeline.dedup.deduplicator import Deduplicator
from pipeline.resolver.geo_resolver import resolve_batch

console = Console(legacy_windows=False)


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

        # Step 5: Geo-resolve (OHM Nominatim lookup)
        if settings.ohm_enabled:
            console.print("  Resolving geo-references via OHM…")
            resolve_batch(entities)
            matched = sum(1 for e in entities if e.get("_geo_resolution", {}).get("status") == "matched")
            console.print(f"  → {matched}/{len(entities)} matched on OHM")

        # Step 6: Write JSONL
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


@cli.command()
@click.argument("query")
@click.option("--depth", type=int, default=2, help="Max BFS depth from the seed entity (default: 2)")
@click.option("--limit", type=int, default=200, help="Max entities to collect (default: 200)")
@click.option("--co-seed", "co_seeds", multiple=True, metavar="QID",
              help="Additional Wikidata QIDs to start the BFS from alongside the primary seed. "
                   "Useful when the primary seed has sparse Wikidata links. "
                   "Can be specified multiple times: --co-seed Q193850 --co-seed Q181264")
@click.option("--skip-wikipedia", is_flag=True, help="Skip Wikipedia enrichment")
@click.option("--skip-untyped", is_flag=True, help="Skip entities that can't be classified into the 30 types")
@click.option("--output-dir", default=None, help="Override output directory")
def topic(query, depth, limit, co_seeds, skip_wikipedia, skip_untyped, output_dir):
    """Scrape a topic and all its related entities via graph walk.

    QUERY can be a Wikidata QID (e.g. Q484954) or a free-text search term
    (e.g. "Late Bronze Age Collapse"). The scraper will resolve the search
    term to a QID, then walk linked properties up to --depth levels deep,
    collecting up to --limit entities.

    Examples:

        python -m pipeline topic "Late Bronze Age Collapse"

        python -m pipeline topic Q484954 --depth 3 --limit 500

        python -m pipeline topic "Roman Empire" --depth 1 --limit 100

        python -m pipeline topic "Silk Road" --skip-wikipedia

        python -m pipeline topic "Late Bronze Age Collapse" --co-seed Q4496560 --co-seed Q193850
    """
    out = Path(output_dir or settings.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Resolve query → QID ─────────────────────────────────────────

    ts = TopicScraper(max_depth=depth, max_entities=limit)

    if query.startswith("Q") and query[1:].isdigit():
        seed_qid = query
        console.print(f"Using QID: [bold]{seed_qid}[/bold]")
    else:
        console.print(f"Searching Wikidata for: [bold]{query}[/bold]")
        seed_qid = ts.resolve_search(query)
        if not seed_qid:
            console.print("[red]Could not resolve search term to a Wikidata QID.[/red]")
            console.print("Try searching manually at https://www.wikidata.org and pass the QID directly.")
            raise SystemExit(1)
        console.print(f"Resolved to: [bold]{seed_qid}[/bold]")

    # ── Step 2: Graph walk ───────────────────────────────────────────────────

    console.rule("[bold blue]Graph Walk")
    if co_seeds:
        console.print(f"  Depth: {depth}, Limit: {limit}, Co-seeds: {', '.join(co_seeds)}")
    else:
        console.print(f"  Depth: {depth}, Limit: {limit}")

    raw_items = ts.walk(seed_qid, co_seed_qids=list(co_seeds))
    console.print(f"  → {len(raw_items)} raw entities discovered")

    if not raw_items:
        console.print("[yellow]No entities found. Try a broader depth or different seed.[/yellow]")
        raise SystemExit(0)

    # ── Step 3: Classify and separate typed vs ref-table vs untyped ────────

    typed_items: dict[str, list[dict]] = {}   # entity_type → [raw_items]
    ref_items: dict[str, list[dict]] = {}     # ref_type → [raw_items]
    untyped_items: list[dict] = []

    for item in raw_items:
        etype = item.pop("_entity_type", None)
        rtype = item.pop("_ref_type", None)
        if etype:
            typed_items.setdefault(etype, []).append(item)
        elif rtype:
            ref_items.setdefault(rtype, []).append(item)
        else:
            untyped_items.append(item)

    console.print(f"\n  Classified: {sum(len(v) for v in typed_items.values())} entities across {len(typed_items)} types")
    if ref_items:
        ref_total = sum(len(v) for v in ref_items.values())
        console.print(f"  [cyan]Reference table items: {ref_total} across {len(ref_items)} categories[/cyan]")
        for rtype, items in sorted(ref_items.items()):
            console.print(f"    {rtype}: {len(items)}")
    if untyped_items:
        console.print(f"  [yellow]Unclassifiable: {len(untyped_items)} entities[/yellow]")

    for etype, items in sorted(typed_items.items()):
        console.print(f"    {etype}: {len(items)}")

    # ── Step 4: Enrich from Wikipedia ────────────────────────────────────────

    wp = WikipediaEnricher() if not skip_wikipedia else None
    mapper = EntityMapper()
    dedup = Deduplicator()

    all_entities: list[dict] = []

    for etype, items in typed_items.items():
        console.rule(f"[blue]{etype} ({len(items)})")

        if wp:
            console.print("  Enriching from Wikipedia…")
            items = wp.enrich_batch(items)

        console.print("  Mapping to entity schema…")
        entities = [mapper.map(item, etype) for item in items]
        entities = [e for e in entities if e is not None]

        all_entities.extend(entities)

    # ── Step 5: Write reference-table items (separate from entities) ────────

    if ref_items:
        console.rule("[cyan]Reference table items")
        slug = _slugify(query)
        ref_file = out / f"topic_{slug}_ref.jsonl"
        ref_count = 0
        with open(ref_file, "wb") as f:
            for rtype, items in ref_items.items():
                for item in items:
                    # Tag with ref_type so Laravel knows which ref table it belongs to
                    item["_ref_type"] = rtype
                    f.write(orjson.dumps(item) + b"\n")
                    ref_count += 1
        console.print(f"  ✓ {ref_count} ref items written to {ref_file}")

    # ── Step 6: Also write untyped entities for manual review ────────────────

    if not skip_untyped and untyped_items:
        console.rule("[yellow]Untyped entities")
        console.print(f"  Saving {len(untyped_items)} untyped entities for manual classification")

        slug = _slugify(query)
        untyped_file = out / f"topic_{slug}_untyped.jsonl"
        with open(untyped_file, "wb") as f:
            for item in untyped_items:
                f.write(orjson.dumps(item) + b"\n")
        console.print(f"  ✓ Written to {untyped_file}")

    # ── Step 7: Deduplicate across all types ─────────────────────────────────

    console.rule("[bold blue]Deduplication")
    before = len(all_entities)
    all_entities = dedup.deduplicate(all_entities)
    console.print(f"  {before} → {len(all_entities)} ({before - len(all_entities)} duplicates removed)")

    # ── Step 8: Geo-resolve (OHM Nominatim lookup) ───────────────────────────

    if settings.ohm_enabled:
        console.rule("[bold blue]Geo-Resolution")
        console.print(f"  Resolving {len(all_entities)} entities via OHM Nominatim…")
        resolve_batch(all_entities)
        matched = sum(1 for e in all_entities if e.get("_geo_resolution", {}).get("status") == "matched")
        console.print(f"  → {matched}/{len(all_entities)} matched on OHM")

    # ── Step 9: Write output ─────────────────────────────────────────────────

    slug = _slugify(query)
    outfile = out / f"topic_{slug}.jsonl"
    with open(outfile, "wb") as f:
        for entity in all_entities:
            f.write(orjson.dumps(entity) + b"\n")

    console.print(f"\n[bold green]✓ {len(all_entities)} entities written to {outfile}[/bold green]")

    # Summary by type
    type_counts: dict[str, int] = {}
    for e in all_entities:
        t = e.get("entity_type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    console.print("\n[bold]Breakdown by type:[/bold]")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        group = TYPE_TO_GROUP.get(t, "?")
        console.print(f"  {group:8s}  {t:35s}  {c}")


def _run_borders_pipeline(
    *,
    run_id,
    artifact_dir,
    query_file,
    output,
    parsed_shard_size,
    parse_workers,
    enrich_batch_size,
    enrich_workers,
    resume,
    force,
    no_enrich,
):
    fetch_result = run_fetch_stage(
        run_id=run_id,
        artifact_dir=artifact_dir,
        query=load_query_text(query_file),
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

    if not no_enrich:
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
        no_enrich=no_enrich,
    )

    final_output_path = build_result["final_path"]
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(build_result["final_path"], output)
        final_output_path = output

    console.print(f"Build {build_result['status']}: {build_result['record_count']} records -> {build_result['final_path']}")
    console.print(f"Borders run complete -> {final_output_path}")


@cli.group(invoke_without_command=True)
@click.option("--output", type=click.Path(path_type=Path, dir_okay=False), default=None, help="Compatibility mode: copy the final merged JSONL to this path")
@click.option("--run-id", default=None, help="Deterministic run id for the artifact directory")
@click.option("--artifact-dir", type=click.Path(path_type=Path, file_okay=False), default=None, help="Explicit artifact directory override")
@click.option("--query-file", type=click.Path(path_type=Path, exists=True, dir_okay=False), default=None, help="Override Overpass query file")
@click.option("--parsed-shard-size", type=int, default=None, help="Polities per parsed shard")
@click.option("--parse-workers", type=int, default=None, help="Reserved worker count for parallel parse stages")
@click.option("--enrich-batch-size", type=int, default=None, help="Unique Wikidata QIDs per enrichment shard")
@click.option("--enrich-workers", type=int, default=None, help="Bounded worker count for enrichment batches")
@click.option("--resume", is_flag=True, help="Skip writing existing stage artifacts when possible")
@click.option("--force", is_flag=True, help="Overwrite existing stage artifacts")
@click.option("--no-enrich", is_flag=True, help="Run fetch/parse/build without the enrich stage")
@click.pass_context
def borders(ctx, output, run_id, artifact_dir, query_file, parsed_shard_size, parse_workers, enrich_batch_size, enrich_workers, resume, force, no_enrich):
    """Fetch and parse OHM borders artifacts."""
    if ctx.invoked_subcommand is None and output is not None:
        _run_borders_pipeline(
            run_id=run_id,
            artifact_dir=artifact_dir,
            query_file=query_file,
            output=output,
            parsed_shard_size=parsed_shard_size,
            parse_workers=parse_workers,
            enrich_batch_size=enrich_batch_size,
            enrich_workers=enrich_workers,
            resume=resume,
            force=force,
            no_enrich=no_enrich,
        )
        return

    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


@borders.command("fetch")
@click.option("--run-id", default=None, help="Deterministic run id for the artifact directory")
@click.option("--artifact-dir", type=click.Path(path_type=Path, file_okay=False), default=None, help="Explicit artifact directory override")
@click.option("--query-file", type=click.Path(path_type=Path, exists=True, dir_okay=False), default=None, help="Override Overpass query file")
@click.option("--resume", is_flag=True, help="Skip fetch when raw/overpass.json already exists")
@click.option("--force", is_flag=True, help="Overwrite existing raw/overpass.json even when resuming")
def borders_fetch(run_id, artifact_dir, query_file, resume, force):
    """Fetch raw OHM border data into staged artifacts."""
    result = run_fetch_stage(
        run_id=run_id,
        artifact_dir=artifact_dir,
        query=load_query_text(query_file),
        resume=resume,
        force=force,
    )

    console.print(f"Fetch {result['status']}: {result['element_count']} elements -> {result['raw_path']}")


@borders.command("parse")
@click.option("--run-id", default=None, help="Deterministic run id for the artifact directory")
@click.option("--artifact-dir", type=click.Path(path_type=Path, file_okay=False), default=None, help="Explicit artifact directory override")
@click.option("--parsed-shard-size", type=int, default=None, help="Polities per parsed shard")
@click.option("--parse-workers", type=int, default=None, help="Reserved worker count for parallel parse stages")
@click.option("--resume", is_flag=True, help="Skip writing parsed shards that already exist")
@click.option("--force", is_flag=True, help="Overwrite existing parsed shards")
def borders_parse(run_id, artifact_dir, parsed_shard_size, parse_workers, resume, force):
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


@borders.command("enrich")
@click.option("--run-id", default=None, help="Deterministic run id for the artifact directory")
@click.option("--artifact-dir", type=click.Path(path_type=Path, file_okay=False), default=None, help="Explicit artifact directory override")
@click.option("--enrich-batch-size", type=int, default=None, help="Unique Wikidata QIDs per enrichment shard")
@click.option("--enrich-workers", type=int, default=None, help="Bounded worker count for enrichment batches")
@click.option("--resume", is_flag=True, help="Skip writing enrichment shards that already exist")
@click.option("--force", is_flag=True, help="Overwrite existing enrichment shards")
def borders_enrich(run_id, artifact_dir, enrich_batch_size, enrich_workers, resume, force):
    """Enrich parsed OHM border shards with batched Wikidata metadata."""
    result = run_enrich_stage(
        run_id=run_id,
        artifact_dir=artifact_dir,
        enrich_batch_size=enrich_batch_size or 50,
        enrich_workers=enrich_workers or 4,
        resume=resume,
        force=force,
    )

    console.print(f"Enrich {result['status']}: {result['qid_count']} unique QIDs across {result['shard_count']} shards")


@borders.command("build")
@click.option("--run-id", default=None, help="Deterministic run id for the artifact directory")
@click.option("--artifact-dir", type=click.Path(path_type=Path, file_okay=False), default=None, help="Explicit artifact directory override")
@click.option("--resume", is_flag=True, help="Skip writing build outputs that already exist")
@click.option("--force", is_flag=True, help="Overwrite existing build outputs")
@click.option("--no-enrich", is_flag=True, help="Build without loading enrichment shards")
def borders_build(run_id, artifact_dir, resume, force, no_enrich):
    """Build importer-facing JSONL shards and the final merged OHM borders file."""
    result = run_build_stage(
        run_id=run_id,
        artifact_dir=artifact_dir,
        resume=resume,
        force=force,
        no_enrich=no_enrich,
    )

    console.print(f"Build {result['status']}: {result['record_count']} records -> {result['final_path']}")


@borders.command("run")
@click.option("--run-id", default=None, help="Deterministic run id for the artifact directory")
@click.option("--artifact-dir", type=click.Path(path_type=Path, file_okay=False), default=None, help="Explicit artifact directory override")
@click.option("--query-file", type=click.Path(path_type=Path, exists=True, dir_okay=False), default=None, help="Override Overpass query file")
@click.option("--output", type=click.Path(path_type=Path, dir_okay=False), default=None, help="Optional path for a copied final merged JSONL")
@click.option("--parsed-shard-size", type=int, default=None, help="Polities per parsed shard")
@click.option("--parse-workers", type=int, default=None, help="Reserved worker count for parallel parse stages")
@click.option("--enrich-batch-size", type=int, default=None, help="Unique Wikidata QIDs per enrichment shard")
@click.option("--enrich-workers", type=int, default=None, help="Bounded worker count for enrichment batches")
@click.option("--resume", is_flag=True, help="Skip writing existing stage artifacts when possible")
@click.option("--force", is_flag=True, help="Overwrite existing stage artifacts")
@click.option("--no-enrich", is_flag=True, help="Run fetch/parse/build without the enrich stage")
def borders_run(run_id, artifact_dir, query_file, output, parsed_shard_size, parse_workers, enrich_batch_size, enrich_workers, resume, force, no_enrich):
    """Run the full staged OHM borders workflow."""
    _run_borders_pipeline(
        run_id=run_id,
        artifact_dir=artifact_dir,
        query_file=query_file,
        output=output,
        parsed_shard_size=parsed_shard_size,
        parse_workers=parse_workers,
        enrich_batch_size=enrich_batch_size,
        enrich_workers=enrich_workers,
        resume=resume,
        force=force,
        no_enrich=no_enrich,
    )


def _slugify(text: str) -> str:
    """Convert a string to a safe filename slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = slug.strip("_")
    return slug[:80]


if __name__ == "__main__":
    cli()
