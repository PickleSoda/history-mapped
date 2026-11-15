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
    if store.queue_path.exists() and store.part_numbers():
        # Parts index into the queue by position; re-filtering it now (rows
        # imported since) would shift every later part and skip rows.
        say(f"{s.id}: queue frozen ({state.get('queued', len(store.queue()))} queued, parts already fetched)")
        return state
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
    meta = {"fetched": len(raws), "records": len(records), "dropped": dict(dropped), "built_at": time.time()}
    store.write_json(store.meta_path(n), meta)
    return meta


def step_fetch(s: Slice, store: SliceStore, client: Client, max_parts: int | None = None) -> None:
    queue = [q for q, _ in store.queue()]
    nparts = math.ceil(len(queue) / PART_SIZE)
    done_now = 0
    for n in range(nparts):
        if store.meta_path(n).exists():
            continue
        if max_parts is not None and done_now >= max_parts:
            break
        qids = queue[n * PART_SIZE : (n + 1) * PART_SIZE]
        raws: list[dict] = []
        for i in range(0, len(qids), BATCH):
            raws += fetch_batch(client, qids[i : i + BATCH], s.entity_type)
        store.write_raw(n, raws)
        meta = _build_part(s, store, n, raws)
        done_now += 1
        say(f"{s.id} part {n + 1}/{nparts}: fetched {meta['fetched']}, kept {meta['records']}, dropped {meta['dropped']}")


def import_part(s: Slice, store: SliceStore, n: int) -> dict[str, Any]:
    compose = str(REPO / "docker" / "docker-compose.yml")
    name = f"part-{n:04d}.jsonl"
    dest = API_DROP / s.id / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(store.part_path(n), dest)
    cmd = [
        "docker", "compose", "-f", compose, "exec", "-T", "app", "php", "artisan", "pipeline:import",
        f"storage/app/pipeline/bulk/{s.id}/{name}", "--sync", "--skip-images", f"--batch-id=bulk-{s.id}-{n:04d}",
    ]
    with locked("import"):
        # Another importer may have taken this part while we waited.
        if store.import_path(n).exists():
            return store.read_json(store.import_path(n)) or {}
        started = time.monotonic()
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=4 * 3600)
        m = SUMMARY.search(proc.stdout)
        result: dict[str, Any] = {"seconds": round(time.monotonic() - started), "exit": proc.returncode, "at": time.time()}
        if m:
            summary = json.loads(m.group(1))
            summary["failed_names"] = summary.get("failed_names", [])[:20]
            result["summary"] = summary
        else:
            result["error"] = (proc.stderr or proc.stdout)[-1500:]
        store.write_json(store.import_path(n), result)
    if m:
        sm = result["summary"]
        say(f"{s.id} {name}: imported {sm['imported']}, skipped {sm['skipped']}, failed {sm['failed']} in {result['seconds']}s")
    else:
        say(f"{s.id} {name}: import FAILED (exit {proc.returncode}); see {store.import_path(n)}")
    return result


def pending_imports(store: SliceStore) -> list[int]:
    return [n for n in store.part_numbers() if not store.import_path(n).exists()]


def step_import(s: Slice, store: SliceStore) -> None:
    for n in pending_imports(store):
        import_part(s, store, n)


def _load(slice_id: str) -> tuple[Slice, SliceStore]:
    s = Slice.load(slice_id)
    return s, SliceStore(s.id)


@click.group()
def cli() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")


@cli.command()
def check() -> None:
    """Validate every slice spec."""
    errors: list[str] = []
    slices = all_slices(errors=errors)
    for s in slices:
        click.echo(f"ok  {s.priority}  {s.id:40} {s.entity_type}")
    for e in errors:
        click.echo(f"BAD {e}")
    click.echo(f"{len(slices)} slices, {len(errors)} invalid")
    if errors:
        raise SystemExit(1)


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
    """Re-run the gates on fetched raw parts (after editing the spec); parts not yet imported only."""
    s, store = _load(slice_id)
    for n in store.part_numbers():
        if store.import_path(n).exists() or not store.raw_path(n).exists():
            continue
        meta = _build_part(s, store, n, store.read_raw(n))
        say(f"{s.id} part {n + 1}: kept {meta['records']}, dropped {meta['dropped']}")


@cli.command()
@click.argument("slice_id")
def reset(slice_id: str) -> None:
    """Forget a slice's listing, parts and claims (only before any part is imported)."""
    from pipeline.bulk.store import ROOT

    store = SliceStore(slice_id)
    if any(store.import_path(n).exists() for n in store.part_numbers()):
        raise click.ClickException(f"{slice_id} has imported parts; reset refuses")
    with locked("claims"):
        path = ROOT / "claims.tsv"
        if path.exists():
            keep = [ln for ln in path.read_text().splitlines() if ln.split("\t")[1:2] != [slice_id]]
            path.write_text("".join(f"{ln}\n" for ln in keep))
    shutil.rmtree(store.dir, ignore_errors=True)
    say(f"{slice_id}: reset")


@cli.command()
@click.argument("slice_id")
@click.option("--all", "everything", is_flag=True, help="Every row of the slice, and forget its import markers")
@click.option("--yes", is_flag=True, help="Delete; without it, a dry run")
def prune(slice_id: str, everything: bool, yes: bool) -> None:
    """Delete DB rows a slice created: rows its (rebuilt) parts no longer keep, or all of them with --all.

    Only rows tagged attributes._bulk.slice are touched (the importer never
    tags rows it merged into); their aliases, dates, points and relations
    cascade. With --all the parts can be imported again later.
    """
    import psycopg

    from pipeline.local_db import dsn

    store = SliceStore(slice_id)
    keep: set[str] = set()
    if not everything:
        for n in store.part_numbers():
            with open(store.part_path(n)) as fh:
                keep |= {json.loads(line).get("wikidata_id") for line in fh if line.strip()}
    with locked("import"), psycopg.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute(
            "select entity_id::text, wikidata_id, name from entities where attributes->'_bulk'->>'slice' = %s",
            (slice_id,),
        )
        rows = [r for r in cur.fetchall() if r[1] not in keep]
        ids = [r[0] for r in rows]
        cur.execute("select count(*) from chronicle_entry_entities where entity_id = any(%s::uuid[])", (ids,))
        linked = cur.fetchone()[0]
        say(f"{slice_id}: {len(rows)} rows to delete" + (f"; {linked} chronicle links block it" if linked else ""))
        for r in rows[:5]:
            say(f"  {r[1]} {r[2]}")
        if linked:
            raise click.ClickException("unlink those chronicle entries first")
        if not yes:
            say("dry run; pass --yes to delete")
            return
        # Hints from other rows that resolved to a deleted row lose their
        # relation in the cascade; reopen them so a later resolve pass
        # links them again if the target comes back.
        cur.execute(
            "update pipeline_relationship_hints set resolved = false, resolution_note = 'target pruned' "
            "where target_wikidata_id = any(%s) and not (source_entity_id = any(%s::uuid[]))",
            ([r[1] for r in rows if r[1]], ids),
        )
        reopened = cur.rowcount
        cur.execute("delete from entities where entity_id = any(%s::uuid[])", (ids,))
        conn.commit()
        say(f"{slice_id}: reopened {reopened} hints of other rows")
        if everything:
            for n in store.part_numbers():
                store.import_path(n).unlink(missing_ok=True)
    say(f"{slice_id}: deleted {len(rows)} rows")


@cli.command()
@click.option("--idle-exit", is_flag=True, help="Exit when nothing is left to import")
@click.option("--poll", type=int, default=30)
def importer(idle_exit: bool, poll: int) -> None:
    """Import built parts of approved slices (approved.txt), priority order, until STOP exists in the bulk root."""
    from pipeline.bulk.store import ROOT, approved

    while not (ROOT / "STOP").exists():
        did = False
        ok = approved()
        for s in all_slices(errors=[]):
            if s.id not in ok:
                continue
            store = SliceStore(s.id)
            for n in pending_imports(store):
                if (ROOT / "STOP").exists():
                    break
                import_part(s, store, n)
                did = True
        if not did:
            if idle_exit:
                return
            time.sleep(poll)
    say("importer: STOP file found; exiting")


@cli.command()
@click.argument("slice_ids", nargs=-1)
@click.option("--json", "as_json", is_flag=True)
def status(slice_ids: tuple[str, ...], as_json: bool) -> None:
    """Progress per slice."""
    ids = slice_ids or tuple(s.id for s in all_slices())
    rows = []
    for sid in ids:
        store = SliceStore(sid)
        state = store.state()
        nums = store.part_numbers()
        metas = [store.read_json(store.meta_path(n)) or {} for n in nums]
        imports = [store.read_json(store.import_path(n)) for n in nums]
        imp: Counter = Counter()
        drop: Counter = Counter()
        for r in imports:
            for k, v in ((r or {}).get("summary") or {}).items():
                if isinstance(v, int):
                    imp[k] += v
        for m in metas:
            drop.update(m.get("dropped") or {})
        nparts = math.ceil(state.get("queued", 0) / PART_SIZE) if state.get("queued") else 0
        rows.append({
            "slice": sid,
            "todo_shards": len(state.get("todo", [])) if "todo" in state else None,
            "failed_shards": len(state.get("shards_failed", [])),
            "listed": state.get("listed"),
            "queued": state.get("queued"),
            "built": len(nums),
            "parts": nparts,
            "imported_parts": sum(1 for r in imports if r and "summary" in r),
            "import_errors": sum(1 for r in imports if r and "error" in r),
            "kept": sum(m.get("records", 0) for m in metas),
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
            f"{r['slice']:40} listed {r['listed']} queued {r['queued']} built {r['built']}/{r['parts']} "
            f"imported-parts {r['imported_parts']} errors {r['import_errors']} kept {r['kept']} "
            f"imported {r['imported']} skipped {r['skipped']} failed {r['failed']} failed-shards {r['failed_shards']}"
        )


if __name__ == "__main__":
    cli()
