"""Scalability benchmark: API queries over growing datasets on emulated server sizes.

The database tier is the bottleneck of the atlas (the PHP layer adds a roughly
constant few tens of ms per request), so this replays the exact SQL the API
runs (captured by capture_queries.php into queries.json) against a Postgres
container limited to a droplet's vCPUs and memory, with settings sized like
docker-compose.prod.yml. Method and results: docs/architecture/scalability.md.

    uv venv .venv && uv pip install -r scripts/scalability/requirements.txt
    .venv/bin/python scripts/scalability/bench.py --tiers S,M,L,XL \
        --datasets b_36k,b_100k,b_200k,b_400k,b_full,b_1283k,b_2566k

Modes per (tier, dataset, query):
  cold   first run after a Postgres restart with the data files evicted from
         the OS page cache (posix_fadvise DONTNEED via `dd iflag=nocache`)
  warm   median of the next four runs of the same query
  mixed  median over rounds 2-3 of a round-robin over all queries, so the
         queries compete for the cache like real traffic
plus a 30 s throughput run with 8 concurrent clients, and the tile-table refresh.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import subprocess
import threading
import time
from pathlib import Path

import psycopg

HERE = Path(__file__).resolve().parent
IMAGE = "history-mapped-db:16-pgvector-v0.8.2"
CONTAINER = "hm-bench-db"
VOLUME = "hm_bench_pgdata"
PORT = 55432
DSN = "host=127.0.0.1 port={port} user=postgres password=bench dbname={db}"
STATEMENT_TIMEOUT_MS = 180_000

# DigitalOcean Basic droplet sizes. The database gets the droplet's vCPUs and
# its RAM minus ~0.6 GB for the app, Redis, Martin and Caddy (measured on the
# 2 GB droplet: about 450-600 MB). Settings follow the prod compose file:
# shared_buffers ~20-25 % of RAM, no parallel workers on one vCPU.
TIERS: dict[str, dict] = {
    "S": {"label": "1 vCPU / 2 GB", "cpus": 1, "mem": "1400m", "shared_buffers": "384MB",
          "effective_cache_size": "1GB", "work_mem": "16MB", "parallel": 0},
    "M": {"label": "2 vCPU / 4 GB", "cpus": 2, "mem": "3400m", "shared_buffers": "1GB",
          "effective_cache_size": "2560MB", "work_mem": "32MB", "parallel": 1},
    "L": {"label": "4 vCPU / 8 GB", "cpus": 4, "mem": "7400m", "shared_buffers": "2GB",
          "effective_cache_size": "5GB", "work_mem": "32MB", "parallel": 2},
    "XL": {"label": "8 vCPU / 16 GB", "cpus": 8, "mem": "15400m", "shared_buffers": "4GB",
           "effective_cache_size": "11GB", "work_mem": "64MB", "parallel": 4},
}
# The tiers above run on full-speed cores of the benchmark host (Intel Core
# Ultra 7 258V). A DigitalOcean Basic (shared) vCPU measured about six times
# slower on single-threaded Postgres work, and a sixth of a host core in 10 ms
# CFS slices reproduces it within noise (scalability.md, "Calibration"). These
# droplet-speed tiers keep the memory and settings of S and M at that speed.
DROPLET_SPEED = 1 / 6
for _key in ("S", "M"):
    TIERS[f"{_key}-do"] = {**TIERS[_key], "label": TIERS[_key]["label"] + ", droplet-speed CPU",
                           "cpu_quota": round(TIERS[_key]["cpus"] * DROPLET_SPEED * 10_000)}

# Tiles around Rome (12.5 E, 41.9 N) at the zooms a visit walks through.
TILES = {"tile_z0": (0, 0, 0), "tile_z3": (3, 4, 2), "tile_z6": (6, 34, 23), "tile_z9": (9, 273, 190)}

READ_QUERIES = ["list_europe_1600", "list_world_-50", "search_ro", "search_rome", "search_charles",
                "tags", "entity_detail", *TILES]


def sh(*cmd: str, check: bool = True) -> str:
    return subprocess.run(cmd, check=check, capture_output=True, text=True).stdout


def load_queries() -> dict[str, list[tuple[str, list]]]:
    captured = json.loads((HERE / "queries.json").read_text())
    queries = {
        name: [(q["sql"].replace("%", "%%").replace("?", "%s"), q["bindings"]) for q in spec["queries"]]
        for name, spec in captured.items()
    }
    for name, (z, x, y) in TILES.items():
        queries[name] = [("SELECT length(mvt) FROM tiles.atlas_entities(%s, %s, %s)", [z, x, y])]
    return queries


# ── container control ──────────────────────────────────────────────────────

def start_tier(tier: dict) -> None:
    sh("docker", "rm", "-f", CONTAINER, check=False)
    cpu = (["--cpu-period=10000", f"--cpu-quota={tier['cpu_quota']}"] if "cpu_quota" in tier
           else [f"--cpus={tier['cpus']}"])
    sh("docker", "run", "-d", "--name", CONTAINER, *cpu,
       f"--memory={tier['mem']}", f"--memory-swap={tier['mem']}",
       "--shm-size=1g", "-p", f"127.0.0.1:{PORT}:5432", "-e", "POSTGRES_PASSWORD=bench",
       "-v", f"{VOLUME}:/var/lib/postgresql/data", IMAGE, "postgres",
       "-c", f"shared_buffers={tier['shared_buffers']}",
       "-c", f"effective_cache_size={tier['effective_cache_size']}",
       "-c", f"work_mem={tier['work_mem']}",
       "-c", "maintenance_work_mem=128MB",
       "-c", "random_page_cost=1.1", "-c", "effective_io_concurrency=200", "-c", "jit=off",
       "-c", f"max_parallel_workers_per_gather={tier['parallel']}",
       "-c", "max_wal_size=4GB")
    wait_ready()


def wait_ready() -> None:
    for _ in range(600):
        if subprocess.run(["docker", "exec", CONTAINER, "pg_isready", "-U", "postgres", "-q"]).returncode == 0:
            time.sleep(0.5)
            return
        time.sleep(0.5)
    raise RuntimeError("bench db did not come up")


def cold_restart(db_oid: int) -> None:
    """Stop Postgres (clean checkpoint), evict the database's files from the OS
    page cache (plus the shared catalogs and WAL), start it again."""
    sh("docker", "stop", "-t", "60", CONTAINER)
    sh("docker", "run", "--rm", "-v", f"{VOLUME}:/d", "--entrypoint", "sh", IMAGE, "-c",
       f"find /d/base/{db_oid} /d/global /d/pg_wal -type f -print0 | xargs -0 -n 500 sh -c "
       "'for f; do dd if=\"$f\" iflag=nocache count=0 status=none; done' _")
    sh("docker", "start", CONTAINER)
    wait_ready()


# ── measurement ────────────────────────────────────────────────────────────

def connect(db: str) -> psycopg.Connection:
    conn = psycopg.connect(DSN.format(port=PORT, db=db), autocommit=True, cursor_factory=psycopg.ClientCursor)
    conn.execute(f"SET statement_timeout = {STATEMENT_TIMEOUT_MS}")
    return conn


def run_query(conn: psycopg.Connection, statements: list[tuple[str, list]]) -> float:
    """Milliseconds for one API request's statements; NaN on timeout."""
    started = time.perf_counter()
    try:
        with conn.cursor() as cur:
            for sql, bindings in statements:
                cur.execute(sql, bindings)
                if cur.description is not None:
                    cur.fetchall()
    except psycopg.errors.QueryCanceled:
        return float("nan")
    return (time.perf_counter() - started) * 1000


def throughput(db: str, queries: dict, seconds: int = 30, clients: int = 8) -> dict:
    latencies: list[float] = []
    lock = threading.Lock()
    deadline = time.perf_counter() + seconds

    def worker(seed: int) -> None:
        rng = random.Random(seed)
        conn = connect(db)
        mine = []
        while time.perf_counter() < deadline:
            ms = run_query(conn, queries[rng.choice(READ_QUERIES)])
            mine.append(ms)
        conn.close()
        with lock:
            latencies.extend(mine)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(clients)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    done = [x for x in latencies if x == x]
    done.sort()
    return {"qps": len(done) / seconds, "p50": statistics.median(done) if done else float("nan"),
            "p95": done[int(len(done) * 0.95) - 1] if done else float("nan"), "timeouts": len(latencies) - len(done)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tiers", default="S,M,L,XL")
    parser.add_argument("--datasets", default="b_36k,b_100k,b_200k,b_400k,b_full,b_1283k,b_2566k")
    parser.add_argument("--out", default="output/scalability/results.csv")
    parser.add_argument("--throughput-seconds", type=int, default=30)
    args = parser.parse_args()

    queries = load_queries()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    new = not out.exists()
    with out.open("a", newline="") as fh:
        writer = csv.writer(fh)
        if new:
            writer.writerow(["tier", "tier_label", "dataset", "entities", "db_bytes", "query", "mode", "ms",
                             "qps", "p50", "p95", "timeouts"])

        def row(tier_key, dataset, info, query, mode, ms="", qps="", p50="", p95="", timeouts=""):
            writer.writerow([tier_key, TIERS[tier_key]["label"], dataset, info["entities"], info["bytes"], query, mode,
                             ms if ms == "" else round(ms, 2), qps if qps == "" else round(qps, 2),
                             p50 if p50 == "" else round(p50, 2), p95 if p95 == "" else round(p95, 2), timeouts])
            fh.flush()

        for tier_key in args.tiers.split(","):
            tier = TIERS[tier_key]
            start_tier(tier)
            for dataset in args.datasets.split(","):
                with connect(dataset) as conn:
                    entities, size, oid = conn.execute(
                        "SELECT (SELECT count(*) FROM entities), pg_database_size(current_database()), "
                        "(SELECT oid FROM pg_database WHERE datname = current_database())").fetchone()
                info = {"entities": entities, "bytes": size}
                print(f"[{time.strftime('%H:%M:%S')}] {tier_key} {dataset} ({entities:,} entities)", flush=True)

                for name in READ_QUERIES:
                    cold_restart(oid)
                    with connect(dataset) as conn:
                        row(tier_key, dataset, info, name, "cold", run_query(conn, queries[name]))
                        warm = [run_query(conn, queries[name]) for _ in range(4)]
                        row(tier_key, dataset, info, name, "warm", statistics.median(warm))

                with connect(dataset) as conn:
                    rounds = {name: [] for name in READ_QUERIES}
                    for _ in range(3):
                        for name in READ_QUERIES:
                            rounds[name].append(run_query(conn, queries[name]))
                    for name, runs in rounds.items():
                        row(tier_key, dataset, info, name, "mixed", statistics.median(runs[1:]))

                tp = throughput(dataset, queries, seconds=args.throughput_seconds)
                row(tier_key, dataset, info, "all_read", "throughput", qps=tp["qps"], p50=tp["p50"], p95=tp["p95"],
                    timeouts=tp["timeouts"])
                print(f"    throughput {tp['qps']:.1f} q/s, p95 {tp['p95']:.0f} ms", flush=True)

                cold_restart(oid)
                with connect(dataset) as conn:
                    conn.execute("SET statement_timeout = 0")
                    row(tier_key, dataset, info, "tiles_refresh", "cold",
                        run_query(conn, [("REFRESH MATERIALIZED VIEW CONCURRENTLY tiles.atlas_features", [])]))


if __name__ == "__main__":
    main()
