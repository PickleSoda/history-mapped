"""Write the benchmark's read queries as one psql script with literal values,
to time them on the production database (warm) and compare with the 1 vCPU /
2 GB tier. Each request runs five times; a `\\echo` marker precedes each run.

    .venv/bin/python scripts/scalability/calibrate.py > output/scalability/calibrate.sql
    ssh <droplet> 'cd /opt/history-mapped && docker compose ... exec -T db \\
        psql -U history-mapped -d history-mapped -f -' < output/scalability/calibrate.sql > prod.txt
    .venv/bin/python scripts/scalability/calibrate.py --parse prod.txt

Read-only statements only. See docs/architecture/scalability.md.
"""

from __future__ import annotations

import re
import statistics
import sys

import psycopg

from bench import DSN, PORT, READ_QUERIES, load_queries

RUNS = 5


def write_script() -> None:
    queries = load_queries()
    conn = psycopg.connect(DSN.format(port=PORT, db="b_full"), autocommit=True, cursor_factory=psycopg.ClientCursor)
    cur = conn.cursor()
    print("\\pset pager off\n\\o /dev/null\n\\timing on\nSET statement_timeout = 60000;")
    for name in READ_QUERIES:
        for run in range(RUNS):
            print(f"\\echo @@ {name} {run}")
            for sql, bindings in queries[name]:
                print(cur.mogrify(sql, bindings).rstrip(";") + ";")


def parse(path: str) -> None:
    times: dict[tuple[str, int], float] = {}
    current = None
    for line in open(path, encoding="utf-8"):
        if line.startswith("@@ "):
            name, run = line[3:].split()
            current = (name, int(run))
            times[current] = 0.0
        elif current and (m := re.match(r"Time: ([\d.]+) ms", line)):
            times[current] += float(m.group(1))
    for name in READ_QUERIES:
        runs = [times[(name, r)] for r in range(RUNS) if (name, r) in times]
        if runs:
            print(f"{name},{runs[0]:.1f},{statistics.median(runs[1:]):.1f}")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--parse":
        parse(sys.argv[2])
    else:
        write_script()
