"""Bulk Wikidata ingest by slices: tens of thousands of entities per slice.

A slice (`pipeline/bulk/slices/<id>.json`) is one entity type plus a SPARQL
pattern, a notability bar and a sharding rule. Each slice runs through four
resumable steps, with state under `output/bulk/<id>/`:

    qids    list the slice's QIDs shard by shard (adaptive year bisection),
            minus QIDs already in the DB or claimed by an earlier slice
    fetch   labels, dates (with precision), coordinates, P31, aliases and
            relationship properties from WDQS in batches, plus the English
            Wikipedia lead from the MediaWiki API
    build   map with the regular EntityMapper, apply the slice's gates
            (excluded classes, required dates/coords, year bounds), and write
            JSONL parts of 2,000 records
    import  `php artisan pipeline:import --sync` per part, one importer at a
            time across processes (a file lock)

Differences from `pipeline scrape`: no LIMIT ceiling, BCE years read
correctly (WDQS dates are astronomical: -0489 is 490 BCE), never a point
borrowed from a linked place, a short Wikipedia lead instead of 8,000
characters, and an impact score from the sitelink count, so bulk rows rank
below hand-curated ones unless they are very notable. Every row carries
`attributes._bulk = {slice, sitelinks}` for audit and rollback.
"""
