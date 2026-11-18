"""Markdown tables for docs/architecture/scalability.md from bench.py's CSV.

    .venv/bin/python scripts/scalability/summarize.py output/scalability/results.csv \
        output/scalability/prod-calibration.csv
"""

from __future__ import annotations

import csv
import sys

DATASETS = ["b_36k", "b_100k", "b_200k", "b_400k", "b_full", "b_1283k", "b_2566k"]
QUERIES = ["list_europe_1600", "list_world_-50", "search_ro", "search_rome", "search_charles", "tags",
           "entity_detail", "tile_z0", "tile_z3", "tile_z6", "tile_z9"]


def fmt_ms(v: float | None) -> str:
    if v is None:
        return "–"
    if v != v:
        return "timeout"
    if v >= 1000:
        return f"{v / 1000:.1f} s"
    if v >= 10:
        return f"{v:.0f} ms"
    return f"{v:.1f} ms"


def main() -> None:
    rows = list(csv.DictReader(open(sys.argv[1], newline="")))
    prod = {}
    if len(sys.argv) > 2:
        for line in open(sys.argv[2]):
            name, cold, warm = line.strip().split(",")
            prod[name] = (float(cold), float(warm))
    cell: dict[tuple, float] = {}
    entities: dict[str, int] = {}
    size: dict[str, int] = {}
    tiers: list[str] = []
    for r in rows:
        if r["tier"] not in tiers:
            tiers.append(r["tier"])
        entities[r["dataset"]] = int(r["entities"])
        size[r["dataset"]] = int(r["db_bytes"])
        for field in ("ms", "qps", "p50", "p95"):
            if r[field] != "":
                cell[(r["tier"], r["dataset"], r["query"], r["mode"], field)] = float(r[field])
    datasets = [d for d in DATASETS if d in entities]
    head = "| Request | " + " | ".join(f"{entities[d] / 1000:,.0f}k" for d in datasets) + " |"
    sep = "|---|" + "---:|" * len(datasets)

    print("## Datasets\n")
    print("| Dataset | Entities | Database size |\n|---|---:|---:|")
    for d in datasets:
        print(f"| `{d}` | {entities[d]:,} | {size[d] / 1e9:.2f} GB |")

    for mode in ("warm", "cold", "mixed"):
        for tier in tiers:
            print(f"\n## {mode} · {tier}\n\n{head}\n{sep}")
            for q in QUERIES:
                vals = [fmt_ms(cell.get((tier, d, q, mode, "ms"))) for d in datasets]
                print(f"| {q} | " + " | ".join(vals) + " |")

    print("\n## Throughput (requests/s, 8 clients) and p95\n\n| Tier | " +
          " | ".join(f"{entities[d] / 1000:,.0f}k" for d in datasets) + " |\n|---|" + "---:|" * len(datasets))
    for tier in tiers:
        vals = []
        for d in datasets:
            qps = cell.get((tier, d, "all_read", "throughput", "qps"))
            p95 = cell.get((tier, d, "all_read", "throughput", "p95"))
            vals.append("–" if qps is None else f"{qps:.0f} /s, p95 {fmt_ms(p95)}")
        print(f"| {tier} | " + " | ".join(vals) + " |")

    print("\n## Tile refresh (cold)\n\n| Tier | " + " | ".join(f"{entities[d] / 1000:,.0f}k" for d in datasets) +
          " |\n|---|" + "---:|" * len(datasets))
    for tier in tiers:
        vals = [fmt_ms(cell.get((tier, d, "tiles_refresh", "cold", "ms"))) for d in datasets]
        print(f"| {tier} | " + " | ".join(vals) + " |")

    if prod:
        print("\n## Calibration at 641k: warm, prod vs bench\n")
        cols = [t for t in tiers if t in ("S", "S-do")]
        print("| Request | Prod droplet | " + " | ".join(cols) + " | Prod ÷ " + " | Prod ÷ ".join(cols) + " |")
        print("|---|---:|" + "---:|" * (2 * len(cols)))
        for q in QUERIES:
            if q not in prod:
                continue
            bench = [cell.get((t, "b_full", q, "warm", "ms")) for t in cols]
            ratios = [f"{prod[q][1] / b:.1f}×" if b else "–" for b in bench]
            print(f"| {q} | {fmt_ms(prod[q][1])} | " + " | ".join(fmt_ms(b) for b in bench) + " | " +
                  " | ".join(ratios) + " |")


if __name__ == "__main__":
    main()
