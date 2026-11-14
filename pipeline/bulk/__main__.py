"""CLI: python -m pipeline.bulk {check,qids,fetch,import,run,rebuild,status} …

Run it through scripts/capped.sh. Every step is resumable; `run` does
qids -> fetch -> import for one slice.
"""
from __future__ import annotations

import json
import logging
import math
import re
import shutil
import subprocess
import sys
import time
from collections import Counter, deque
from typing import Any

import click

from pipeline.bulk.build import build
from pipeline.bulk.fetch import fetch_batch
from pipeline.bulk.spec import Slice, ValueShard, Window, all_slices
from pipeline.bulk.store import API_DROP, PART_SIZE, REPO, SliceStore, add_claims, claims, db_qids, locked
from pipeline.bulk.wdqs import Client, QueryTimeout, qid_of, value

BATCH = 100
SUMMARY = re.compile(r"^IMPORT_SUMMARY (\{.*\})\s*$", re.M)


def say(msg: str) -> None:
    click.echo(f"[{time.strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()


def _shard_spec(shard: Window | ValueShard | None) -> dict[str, Any]:
    if isinstance(shard, Window):
        return {"prop": shard.prop, "start": shard.start, "end": shard.end}
    if isinstance(shard, ValueShard):
        return {"pattern": shard.pattern, "value": shard.value}
    return {}


def _shard(spec: dict[str, Any]) -> Window | ValueShard | None:
    if "prop" in spec:
        return Window(spec["prop"], spec["start"], spec["end"])
    if "value" in spec:
        return ValueShard(spec["pattern"], spec["value"])
    return None


def step_qids(s: Slice, store: SliceStore, client: Client) -> dict[str, Any]:
    state = store.state()
    if "todo" not in state:
        state["todo"] = [_shard_spec(sh) for sh in s.initial_shards()]
        store.save(state)
    todo = deque(state["todo"])
    while todo:
        spec = todo[0]
        shard = _shard(spec)
        label = shard.label if shard else "all"
        try:
            rows = client.sparql(s.qid_query(shard))
        except QueryTimeout as exc:
            todo.popleft()
            halves = shard.halves() if isinstance(shard, Window) else None
            if halves:
                todo.extendleft([_shard_spec(h) for h in reversed(halves)])
                say(f"{s.id} {label}: {exc}; splitting")
            else:
                state["shards_failed"].append(label)
                say(f"{s.id} {label}: {exc}; giving up on this shard")
            state["todo"] = list(todo)
            store.save(state)
            continue
        pairs = [(q, int(value(b, "hm_sl") or 0)) for b in rows if (q := qid_of(value(b, "item")))]
        store.add_listed(pairs, label)
        todo.popleft()
        state["todo"] = list(todo)
        state["shards_done"].append(label)
        store.save(state)
        say(f"{s.id} {label}: {len(pairs)} QIDs ({len(todo)} shards left)")

    with locked("claims"):
        in_db = db_qids()
        taken = claims()
        listed = store.listed()
        fresh = [(q, sl) for q, sl in listed.items() if q not in in_db and taken.get(q, s.id) == s.id]
        fresh.sort(key=lambda r: (-r[1], int(r[0][1:])))
        if s.max_items is not None:
            fresh = fresh[: s.max_items]
        add_claims([q for q, _ in fresh if q not in taken], s.id)
        store.queue_path.write_text("".join(f"{q}\t{sl}\n" for q, sl in fresh))
    state["listed"] = len(listed)
    state["in_db"] = sum(1 for q in listed if q in in_db)
    state["claimed_elsewhere"] = sum(1 for q in listed if q not in in_db and taken.get(q, s.id) != s.id)
    state["queued"] = len(fresh)
    store.save(state)
    say(f"{s.id}: listed {len(listed)}, in DB {state['in_db']}, other slices {state['claimed_elsewhere']}, queued {len(fresh)}")
    return state


def _build_part(s: Slice, store: SliceStore, n: int, raws: list[dict]) -> dict[str, Any]:
    records, dropped = build(raws, s)
    store.write_part(n, records)
    return {"built": True, "fetched": len(raws), "records": len(records), "dropped": dict(dropped)}


def step_fetch(s: Slice, store: SliceStore, client: Client, max_parts: int | None = None) -> None:
    state = store.state()
    queue = [q for q, _ in store.queue()]
    nparts = math.ceil(len(queue) / PART_SIZE)
    done_now = 0
    for n in range(nparts):
        if state["parts"].get(str(n), {}).get("built"):
            continue
        if max_parts is not None and done_now >= max_parts:
            break
        qids = queue[n * PART_SIZE : (n + 1) * PART_SIZE]
        raws: list[dict] = []
        for i in range(0, len(qids), BATCH):
            raws += fetch_batch(client, qids[i : i + BATCH], s.entity_type)
        store.write_raw(n, raws)
        info = _build_part(s, store, n, raws)
        state = store.state()
        state["parts"][str(n)] = {**state["parts"].get(str(n), {}), **info}
        store.save(state)
        done_now += 1
        say(f"{s.id} part {n + 1}/{nparts}: fetched {info['fetched']}, kept {info['records']}, dropped {info['dropped']}")


def step_import(s: Slice, store: SliceStore) -> None:
    state = store.state()
    compose = str(REPO / "docker" / "docker-compose.yml")
    for key in sorted(state["parts"], key=int):
        info = state["parts"][key]
        if not info.get("built") or info.get("imported"):
            continue
        n = int(key)
        name = f"part-{n:04d}.jsonl"
        dest = API_DROP / s.id / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(store.part_path(n), dest)
        cmd = [
            "docker", "compose", "-f", compose, "exec", "-T", "app", "php", "artisan", "pipeline:import",
            f"storage/app/pipeline/bulk/{s.id}/{name}", "--sync", "--skip-images", f"--batch-id=bulk-{s.id}-{n:04d}",
        ]
        started = time.monotonic()
        with locked("import"):
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=4 * 3600)
        m = SUMMARY.search(proc.stdout)
        summary = json.loads(m.group(1)) if m else None
        if summary is None:
            say(f"{s.id} {name}: import produced no summary (exit {proc.returncode}): {proc.stderr[-500:]}")
            info["import_error"] = (proc.stderr or proc.stdout)[-1000:]
            state["parts"][key] = info
            store.save(state)
            raise click.ClickException(f"import of {name} failed")
        summary["failed_names"] = summary.get("failed_names", [])[:20]
        info.update(imported=True, import_summary=summary, import_seconds=round(time.monotonic() - started))
        state = store.state()
        state["parts"][key] = info
        store.save(state)
        say(f"{s.id} {name}: imported {summary['imported']}, skipped {summary['skipped']}, failed {summary['failed']} "
            f"in {info['import_seconds']}s")


def _load(slice_id: str) -> tuple[Slice, SliceStore]:
    s = Slice.load(slice_id)
    return s, SliceStore(s.id)


@click.group()
def cli() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")


@cli.command()
def check() -> None:
    """Validate every slice spec."""
    slices = all_slices()
    for s in slices:
        click.echo(f"ok  {s.priority}  {s.id:40} {s.entity_type}")
    click.echo(f"{len(slices)} slices")


@cli.command()
@click.argument("slice_id")
def qids(slice_id: str) -> None:
    """List the slice's QIDs and queue the new ones."""
    s, store = _load(slice_id)
    step_qids(s, store, Client())


@cli.command()
@click.argument("slice_id")
@click.option("--max-parts", type=int, default=None, help="Stop after this many new parts")
def fetch(slice_id: str, max_parts: int | None) -> None:
    """Fetch and build the queued QIDs, PART_SIZE per part."""
    s, store = _load(slice_id)
    step_fetch(s, store, Client(), max_parts)


@cli.command("import")
@click.argument("slice_id")
def import_(slice_id: str) -> None:
    """Import every built part not yet imported (one importer at a time)."""
    s, store = _load(slice_id)
    step_import(s, store)


@cli.command()
@click.argument("slice_id")
@click.option("--max-parts", type=int, default=None)
@click.option("--no-import", is_flag=True)
def run(slice_id: str, max_parts: int | None, no_import: bool) -> None:
    """qids -> fetch -> import for one slice."""
    s, store = _load(slice_id)
    client = Client()
    step_qids(s, store, client)
    step_fetch(s, store, client, max_parts)
    if not no_import:
        step_import(s, store)


@cli.command()
@click.argument("slice_id")
def rebuild(slice_id: str) -> None:
    """Re-run the gates on fetched raw parts (after editing the spec); not-yet-imported parts only."""
    s, store = _load(slice_id)
    state = store.state()
    for key, info in sorted(state["parts"].items(), key=lambda kv: int(kv[0])):
        if info.get("imported") or not store.raw_path(int(key)).exists():
            continue
        state["parts"][key] = {**info, **_build_part(s, store, int(key), store.read_raw(int(key)))}
        say(f"{s.id} part {int(key) + 1}: kept {state['parts'][key]['records']}")
    store.save(state)


@cli.command()
@click.argument("slice_ids", nargs=-1)
@click.option("--json", "as_json", is_flag=True)
def status(slice_ids: tuple[str, ...], as_json: bool) -> None:
    """Progress per slice."""
    ids = slice_ids or tuple(s.id for s in all_slices())
    rows = []
    for sid in ids:
        state = SliceStore(sid).state()
        parts = state.get("parts", {})
        imp = Counter()
        drop = Counter()
        for p in parts.values():
            for k, v in (p.get("import_summary") or {}).items():
                if isinstance(v, int):
                    imp[k] += v
            drop.update(p.get("dropped") or {})
        nparts = math.ceil(state.get("queued", 0) / PART_SIZE) if state.get("queued") else 0
        rows.append({
            "slice": sid,
            "todo_shards": len(state.get("todo", [])) if "todo" in state else None,
            "failed_shards": len(state.get("shards_failed", [])),
            "listed": state.get("listed"),
            "queued": state.get("queued"),
            "parts": f"{sum(1 for p in parts.values() if p.get('built'))}/{nparts}",
            "kept": sum(p.get("records", 0) for p in parts.values()),
            "imported": imp.get("imported", 0),
            "skipped": imp.get("skipped", 0),
            "failed": imp.get("failed", 0),
            "dropped": dict(drop),
        })
    if as_json:
        click.echo(json.dumps(rows, indent=1))
        return
    for r in rows:
        click.echo(
            f"{r['slice']:40} listed {r['listed']} queued {r['queued']} parts {r['parts']} kept {r['kept']} "
            f"imported {r['imported']} skipped {r['skipped']} failed {r['failed']} failed-shards {r['failed_shards']}"
        )


if __name__ == "__main__":
    cli()
