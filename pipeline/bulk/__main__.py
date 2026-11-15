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
from pathlib import Path
from typing import Any

import click

from pipeline.bulk.build import CURRENT_YEAR, build
from pipeline.bulk.fetch import fetch_batch
from pipeline.bulk.spec import Slice, ValueShard, Window, all_slices
from pipeline.bulk.store import API_DROP, PART_SIZE, REPO, SliceStore, add_claims, claims, db_qids, locked, try_locked
from pipeline.bulk.wdqs import LIST_ENDPOINT, Client, QueryTimeout, qid_of, value

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


def run_import(slice_id: str, src: Path, name: str, batch: str) -> dict[str, Any]:
    """Copy a JSONL file into the API's storage and run pipeline:import on it."""
    compose = str(REPO / "docker" / "docker-compose.yml")
    dest = API_DROP / slice_id / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    cmd = [
        "docker", "compose", "-f", compose, "exec", "-T", "app", "php", "artisan", "pipeline:import",
        f"storage/app/pipeline/bulk/{slice_id}/{name}", "--sync", "--skip-images", f"--batch-id={batch}",
    ]
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
    return result


def import_part(s: Slice, store: SliceStore, n: int) -> dict[str, Any] | None:
    """Import one built part, or return None when another importer holds it.

    Each part has its own lock, so any number of importer daemons share the
    queue. Concurrent parts are safe: claims keep a QID in one slice and one
    part, and the name fallback only matches rows without a QID or with the
    same one.
    """
    name = f"part-{n:04d}.jsonl"
    with try_locked(store.import_lock_path(n)) as mine:
        if not mine:
            return None
        # Another importer may have finished this part before we looked.
        if store.import_path(n).exists():
            return store.read_json(store.import_path(n)) or {}
        result = run_import(s.id, store.part_path(n), name, f"bulk-{s.id}-{n:04d}")
        store.write_json(store.import_path(n), result)
    if "summary" in result:
        sm = result["summary"]
        say(f"{s.id} {name}: imported {sm['imported']}, skipped {sm['skipped']}, failed {sm['failed']} in {result['seconds']}s")
    else:
        say(f"{s.id} {name}: import FAILED (exit {result['exit']}); see {store.import_path(n)}")
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
    step_qids(s, store, Client(endpoint=LIST_ENDPOINT))


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
    step_qids(s, store, Client(endpoint=LIST_ENDPOINT))
    step_fetch(s, store, client, max_parts)
    if not no_import:
        step_import(s, store)


@cli.command()
@click.argument("slice_id")
@click.option("--imported", is_flag=True, help="Also imported parts; then `prune` deletes the rows they no longer keep")
def rebuild(slice_id: str, imported: bool) -> None:
    """Re-run the gates on fetched raw parts (after editing the spec); parts not yet imported unless --imported."""
    s, store = _load(slice_id)
    for n in store.part_numbers():
        if (store.import_path(n).exists() and not imported) or not store.raw_path(n).exists():
            continue
        meta = _build_part(s, store, n, store.read_raw(n))
        say(f"{s.id} part {n + 1}: kept {meta['records']}, dropped {meta['dropped']}")


@cli.command()
@click.argument("slice_ids", nargs=-1, required=True)
@click.option("--yes", is_flag=True, help="Import them; without it, a dry run")
def fill(slice_ids: tuple[str, ...], yes: bool) -> None:
    """Import rows of imported parts that the build used to drop for want of an English label.

    Run `rebuild --imported` first. Only records whose raw label was empty
    (items labelled in "mul" alone) and whose QID the DB lacks are imported,
    so rows that audits deleted or merged never come back.
    """
    have = db_qids()
    for sid in slice_ids:
        s, store = _load(sid)
        unlabelled: set[str] = set()
        for n in store.part_numbers():
            if store.import_path(n).exists() and store.raw_path(n).exists():
                unlabelled |= {r["qid"] for r in store.read_raw(n) if not (r.get("label") or "").strip()}
        lines = []
        for n in store.part_numbers():
            if not store.import_path(n).exists():
                continue
            for line in store.part_path(n).read_text().splitlines():
                qid = json.loads(line).get("wikidata_id")
                if qid in unlabelled and qid not in have:
                    lines.append(line)
        say(f"{sid}: {len(lines)} unlabelled rows missing from the DB")
        if not yes or not lines:
            continue
        src = store.dir / "parts" / "fill.jsonl"
        src.write_text("\n".join(lines) + "\n")
        result = run_import(sid, src, "fill.jsonl", f"bulk-{sid}-fill")
        sm = result.get("summary")
        say(f"{sid} fill: " + (f"imported {sm['imported']}, skipped {sm['skipped']}, failed {sm['failed']}" if sm else f"FAILED (exit {result['exit']})"))


@cli.command()
@click.argument("slice_ids", nargs=-1, required=True)
@click.option(
    "--reason",
    "reasons",
    multiple=True,
    default=("after-year-max", "before-year-min"),
    show_default=True,
    help="Gate reasons whose drops are given back",
)
@click.option("--yes", is_flag=True, help="Rewrite claims.tsv; without it, a dry run")
def release(slice_ids: tuple[str, ...], reasons: tuple[str, ...], yes: bool) -> None:
    """Give back claims on QIDs a fetched slice dropped for these gate reasons.

    A slice claims every QID it lists, so an item it later drops (say, a
    1960s battle under a year_max of 1950) stays out of reach of the slice
    meant for it. Only fetched parts are examined; claims of unfetched
    queue entries and of `qid-audit-blocked` are never touched.
    """
    from pipeline.bulk.store import ROOT

    freed: dict[str, set[str]] = {}
    for slice_id in slice_ids:
        s, store = _load(slice_id)
        out: set[str] = set()
        for n in store.part_numbers():
            if not store.raw_path(n).exists():
                continue
            with open(store.part_path(n)) as fh:
                kept = {json.loads(line).get("wikidata_id") for line in fh if line.strip()}
            for raw in store.read_raw(n):
                if raw.get("qid") in kept:
                    continue
                _, dropped = build([raw], s)
                if set(dropped) & set(reasons):
                    out.add(raw["qid"])
        freed[slice_id] = out
        say(f"{slice_id}: {len(out)} claims to release ({', '.join(reasons)})")
    if not yes:
        return
    with locked("claims"):
        path = ROOT / "claims.tsv"
        keep = []
        for ln in path.read_text().splitlines():
            qid, sid = (ln.split("\t") + [""])[:2]
            if qid not in freed.get(sid, ()):
                keep.append(ln)
        path.write_text("".join(f"{ln}\n" for ln in keep))
    say(f"released {sum(map(len, freed.values()))} claims")


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


def _date_attr_keys(entity_type: str) -> set[str]:
    """Attribute keys the mapper fills from date properties (birth_date, death_date…)."""
    from pipeline.bulk.fetch import DATE_PROPS
    from pipeline.wikidata.mapper.type_configs import WIKIDATA_TYPE_CONFIGS

    field_map = WIKIDATA_TYPE_CONFIGS.get(entity_type, {}).get("field_map", {})
    return {field_map[pid] for pid, _ in DATE_PROPS if pid in field_map}


def _record_span(rec: dict[str, Any]) -> tuple[str | None, str | None]:
    """The primary range the importer stores for a record (ImportEntityJob)."""
    attrs = rec.get("attributes") or {}
    start = rec.get("temporal_start") or attrs.get("start_date")
    end = rec.get("temporal_end") or attrs.get("end_date")
    y0 = re.match(r"^-?\d+", str(start)) if start is not None else None
    y1 = re.match(r"^-?\d+", str(end)) if end is not None else None
    if y0 and y1 and int(y0.group()) > int(y1.group()):
        end = None
    return (None if start is None else str(start)), (None if end is None else str(end))


@cli.command()
@click.argument("slice_ids", nargs=-1, required=True)
@click.option("--yes", is_flag=True, help="Write; without it, a dry run")
def redate(slice_ids: tuple[str, ...], yes: bool) -> None:
    """Give imported rows the dates of their rebuilt records (after a date-gate change).

    Run `rebuild <id> --imported` and `prune <id> --yes` first. Updates the
    primary range, date_confidence and the date attributes of rows tagged
    with the slice; rows a curated audit re-dated (fix_dates) are left alone.
    Before-values go to output/bulk/redate/redate-<stamp>.csv.
    """
    import csv

    import psycopg
    from psycopg.types.json import Jsonb

    from pipeline.bulk.store import ROOT
    from pipeline.local_db import dsn

    curated: set[str] = set()
    for path in (ROOT / "audit").glob("applied-*.csv"):
        with open(path, newline="") as fh:
            curated |= {r["entity_id"] for r in csv.DictReader(fh) if (r.get("action") or "").startswith("fix_dates")}
    log_rows: list[list[Any]] = []
    total: Counter = Counter()
    with locked("import"), psycopg.connect(dsn()) as conn, conn.cursor() as cur:
        for slice_id in slice_ids:
            s, store = _load(slice_id)
            keys = _date_attr_keys(s.entity_type)
            records: dict[str, dict[str, Any]] = {}
            for n in store.part_numbers():
                if store.import_path(n).exists():
                    with open(store.part_path(n)) as fh:
                        for line in fh:
                            if line.strip():
                                rec = json.loads(line)
                                records[rec.get("wikidata_id")] = rec
            cur.execute(
                "select e.entity_id::text, e.wikidata_id, e.name, e.date_confidence::text, e.attributes, "
                "t.temporal_range_id::text, t.start_date, t.end_date from entities e "
                "left join entity_temporal_ranges t on t.entity_id = e.entity_id and t.is_primary "
                "where e.attributes->'_bulk'->>'slice' = %s",
                (slice_id,),
            )
            done: Counter = Counter()
            for eid, qid, name, conf, attrs, range_id, d0, d1 in cur.fetchall():
                rec = records.get(qid)
                if rec is None or eid in curated:
                    continue
                n0, n1 = _record_span(rec)
                nconf = rec.get("date_confidence")
                rattrs = rec.get("attributes") or {}
                attr_patch = {k: rattrs[k] for k in keys if k in rattrs}
                attr_drop = [k for k in keys if k in attrs and k not in rattrs]
                stale_attrs = attr_drop or any(attrs.get(k) != v for k, v in attr_patch.items())
                if (n0, n1) == (d0, d1) and nconf == conf and not stale_attrs:
                    continue
                done["changed"] += 1
                log_rows.append([slice_id, eid, qid, name, d0, d1, conf, n0, n1, nconf])
                if not yes:
                    continue
                if n0 is None and n1 is None:
                    if range_id:
                        cur.execute("delete from entity_temporal_ranges where temporal_range_id = %s", (range_id,))
                elif range_id:
                    cur.execute(
                        "update entity_temporal_ranges set start_date = %s, end_date = %s, date_confidence = %s, "
                        "updated_at = now() where temporal_range_id = %s",
                        (n0, n1, nconf, range_id),
                    )
                else:
                    cur.execute(
                        "insert into entity_temporal_ranges (entity_id, range_type, start_date, end_date, "
                        "date_confidence, is_primary, created_at, updated_at) "
                        "values (%s, 'primary', %s, %s, %s, true, now(), now())",
                        (eid, n0, n1, nconf),
                    )
                cur.execute(
                    "update entities set date_confidence = %s::confidence_level, "
                    "attributes = (attributes - %s::text[]) || %s, updated_at = now() where entity_id = %s",
                    (nconf, attr_drop, Jsonb(attr_patch), eid),
                )
            say(f"{slice_id}: {done['changed']} rows to re-date")
            total.update(done)
        for r in log_rows[:8]:
            say(f"  {r[2]} {r[3]}: {r[4]}..{r[5]} ({r[6]}) -> {r[7]}..{r[8]} ({r[9]})")
        if not yes:
            say(f"redate: {total['changed']} rows (dry run; pass --yes to write)")
            return
        out = ROOT / "redate" / f"redate-{time.strftime('%Y%m%d-%H%M%S')}.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["slice", "entity_id", "qid", "name", "start", "end", "confidence", "new_start", "new_end", "new_confidence"])
            w.writerows(log_rows)
        conn.commit()
    say(f"redate: {total['changed']} rows written; before-values in {out}")


# Relations a bulk import created between a polity and something outside the
# polity's lifetime (with slack): Wikidata names today's state for old
# events and births (France, founded 1958 in our rows, "participating" in a
# 1781 action). An event or a person with no end year is a single year;
# anything else with no end (a polity, a city, a building) is ongoing.
# Not checked: capital_of (from the polity's own P36; a mismatch means the
# city's dates are off, e.g. a modern municipal founding year), succession
# (preceded_by/succeeded_by never overlap by nature: Roman Britain ->
# Ceredigion) and used_currency (a coin is used long after its minting dates).
ANACHRONISTIC = """
with r as (
  select r.relationship_id, r.relationship_type, s.entity_type st, t.entity_type tt, s.name sn, t.name tn,
         ts.start_year s0,
         case when s.entity_type = 'person' or s.entity_type::text like 'event%%' then coalesce(ts.end_year, ts.start_year)
              else coalesce(ts.end_year, %(now)s) end s1,
         tr.start_year t0,
         case when t.entity_type = 'person' or t.entity_type::text like 'event%%' then coalesce(tr.end_year, tr.start_year)
              else coalesce(tr.end_year, %(now)s) end t1
  from relationships r
  join entities s on s.entity_id = r.source_entity_id
  join entities t on t.entity_id = r.target_entity_id
  left join entity_temporal_ranges ts on ts.entity_id = s.entity_id and ts.is_primary
  left join entity_temporal_ranges tr on tr.entity_id = t.entity_id and tr.is_primary
  where r.created_by like 'pipeline:bulk-%%'
    and r.relationship_type not in ('capital_of', 'preceded_by', 'succeeded_by', 'used_currency')
)
select relationship_id::text, relationship_type, sn, tn, s0, s1, t0, t1 from r
where s0 is not null and t0 is not null and (
      (st = 'political_entity' and (t1 < s0 - %(slack)s or t0 > s1 + %(slack)s))
   or (tt = 'political_entity' and (s1 < t0 - %(slack)s or s0 > t1 + %(slack)s)))
"""


# Relations a bulk import created between a person and an event outside the
# person's lifetime: a man born 1763 "participating" in a war of 1600-1629
# (a wrong war matched by name, or a bad date). An unknown end of life is
# taken as 100 years after birth, an unknown birth as 100 years before death.
OUTSIDE_LIFE = """
with r as (
  select r.relationship_id, r.relationship_type, s.name sn, t.name tn,
         case when s.entity_type = 'person' then ts.start_year else tr.start_year end p0,
         case when s.entity_type = 'person' then ts.end_year else tr.end_year end p1,
         case when s.entity_type = 'person' then tr.start_year else ts.start_year end e0,
         case when s.entity_type = 'person' then tr.end_year else ts.end_year end e1
  from relationships r
  join entities s on s.entity_id = r.source_entity_id
  join entities t on t.entity_id = r.target_entity_id
  left join entity_temporal_ranges ts on ts.entity_id = s.entity_id and ts.is_primary
  left join entity_temporal_ranges tr on tr.entity_id = t.entity_id and tr.is_primary
  where r.created_by like 'pipeline:bulk-%%'
    and ((s.entity_type = 'person' and t.entity_type::text like 'event%%')
      or (t.entity_type = 'person' and s.entity_type::text like 'event%%'))
), b as (
  select *, coalesce(p0, p1 - 100) b0, coalesce(p1, p0 + 100) b1, coalesce(e1, e0) f1 from r
)
select relationship_id::text, relationship_type, sn, tn, p0, p1, e0, e1 from b
where b0 is not null and e0 is not null and (f1 < b0 - %(slack)s or e0 > b1 + %(slack)s)
"""


# Relations whose shape is impossible: Wikidata puts some sieges "part of"
# the commander who ran the campaign (Toyotomi Hideyoshi, Sennacherib).
MISTYPED = """
select r.relationship_id::text, r.relationship_type, s.name, t.name, null, null, null, null
from relationships r
join entities s on s.entity_id = r.source_entity_id
join entities t on t.entity_id = r.target_entity_id
where r.created_by like 'pipeline:bulk-%%' and r.relationship_type = 'part_of'
  and s.entity_type::text like 'event%%' and t.entity_type = 'person'
"""


@cli.command()
@click.option("--slack", type=int, default=25, help="Years of tolerance around a polity's lifetime")
@click.option("--person-slack", type=int, default=5, help="Years of tolerance around a person's lifetime")
@click.option("--yes", is_flag=True, help="Delete; without it, a dry run")
def tidy(slack: int, person_slack: int, yes: bool) -> None:
    """Delete bulk-created relations linking a polity or a person to something outside its lifetime,
    and events "part of" a person (CSV backup)."""
    import csv

    import psycopg

    from pipeline.bulk.store import ROOT
    from pipeline.local_db import dsn

    with psycopg.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute(ANACHRONISTIC, {"now": CURRENT_YEAR, "slack": slack})
        polity = cur.fetchall()
        cur.execute(OUTSIDE_LIFE, {"slack": person_slack})
        seen = {r[0] for r in polity}
        person = [r for r in cur.fetchall() if r[0] not in seen]
        seen |= {r[0] for r in person}
        cur.execute(MISTYPED)
        mistyped = [r for r in cur.fetchall() if r[0] not in seen]
        rows = polity + person + mistyped
        for label, part in (("polity", polity), ("person-event", person), ("event part_of person", mistyped)):
            by_type = Counter(r[1] for r in part)
            say(f"tidy: {len(part)} anachronistic {label} relations {dict(by_type.most_common())}")
            for r in part[:6]:
                say(f"  {r[2]} {r[1]} {r[3]} ({r[4]}..{r[5]} vs {r[6]}..{r[7]})")
        if not yes or not rows:
            say("dry run; pass --yes to delete" if rows else "nothing to do")
            return
        out = ROOT / "tidy" / f"anachronistic-{time.strftime('%Y%m%d-%H%M%S')}.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["relationship_id", "type", "source", "target", "s0", "s1", "t0", "t1"])
            w.writerows(rows)
        cur.execute("delete from relationships where relationship_id = any(%s::uuid[])", ([r[0] for r in rows],))
        conn.commit()
    say(f"tidy: deleted {len(rows)}; backup {out}")


@cli.command("drop-relations")
@click.argument("csv_paths", nargs=-1, required=True)
@click.option("--yes", is_flag=True, help="Delete; without it, a dry run")
def drop_relations(csv_paths: tuple[str, ...], yes: bool) -> None:
    """Delete the relations a curated QC CSV marks `delete` (relationship_id,...,action,...).

    Rows with any other action stay. The deleted rows, every column, go to
    output/bulk/tidy/dropped-<stamp>.csv.
    """
    import csv

    import psycopg

    from pipeline.bulk.store import ROOT
    from pipeline.local_db import dsn

    ids: set[str] = set()
    for path in csv_paths:
        with open(path, newline="") as fh:
            ids |= {r["relationship_id"].strip() for r in csv.DictReader(fh) if (r.get("action") or "").strip() == "delete"}
    with psycopg.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute("select * from relationships where relationship_id = any(%s::uuid[])", (sorted(ids),))
        rows = cur.fetchall()
        cols = [d.name for d in cur.description]
        by_type = Counter(r[cols.index("relationship_type")] for r in rows)
        say(f"drop-relations: {len(rows)} of {len(ids)} found {dict(by_type.most_common())}")
        if not yes or not rows:
            say("dry run; pass --yes to delete" if rows else "nothing to do")
            return
        out = ROOT / "tidy" / f"dropped-{time.strftime('%Y%m%d-%H%M%S')}.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(cols)
            w.writerows(rows)
        cur.execute("delete from relationships where relationship_id = any(%s::uuid[])", ([str(r[0]) for r in rows],))
        conn.commit()
    say(f"drop-relations: deleted {len(rows)}; backup {out}")


@cli.command("relink-relations")
@click.argument("csv_path")
@click.option("--yes", is_flag=True, help="Write; without it, a dry run")
def relink_relations(csv_path: str, yes: bool) -> None:
    """Re-point one end of relations that hit a namesake (relationship_id,end,new_entity_id[,detail]).

    end is `source`, `target` or `swap` (an inverted link: "Balfour
    Declaration authored Arthur Balfour"). A relink that would duplicate an
    existing link deletes the wrong one instead. Before-values go to
    output/bulk/tidy/relinked-<stamp>.csv.
    """
    import csv

    import psycopg

    from pipeline.bulk.store import ROOT
    from pipeline.local_db import dsn

    with open(csv_path, newline="") as fh:
        todo = list(csv.DictReader(fh))
    done: Counter = Counter()
    log = []
    with psycopg.connect(dsn()) as conn, conn.cursor() as cur:
        for r in todo:
            rid, end, new = r["relationship_id"].strip(), r["end"].strip(), (r.get("new_entity_id") or "").strip()
            cur.execute(
                "select source_entity_id::text, target_entity_id::text, relationship_type::text from relationships "
                "where relationship_id = %s",
                (rid,),
            )
            row = cur.fetchone()
            if row is None:
                done["gone"] += 1
                continue
            src, tgt, rtype = row
            if end == "swap":
                src2, tgt2 = tgt, src
            elif end in ("source", "target"):
                cur.execute("select 1 from entities where entity_id = %s", (new,))
                if cur.fetchone() is None:
                    done["bad-new-entity"] += 1
                    continue
                src2, tgt2 = (new, tgt) if end == "source" else (src, new)
            else:
                done["bad-end"] += 1
                continue
            if src2 == tgt2:
                done["would-self-link"] += 1
                continue
            log.append([rid, rtype, src, tgt, src2, tgt2, r.get("detail", "")])
            cur.execute(
                "select 1 from relationships where source_entity_id = %s and target_entity_id = %s "
                "and relationship_type::text = %s and relationship_id <> %s",
                (src2, tgt2, rtype, rid),
            )
            if cur.fetchone():
                cur.execute("delete from relationships where relationship_id = %s", (rid,))
                done["deleted-as-duplicate"] += 1
                continue
            cur.execute(
                "update relationships set source_entity_id = %s, target_entity_id = %s "
                "where relationship_id = %s",
                (src2, tgt2, rid),
            )
            done[end] += 1
        say(f"relink-relations: {dict(done)}" + ("" if yes else " (dry run; pass --yes to write)"))
        if not yes:
            conn.rollback()
            return
        out = ROOT / "tidy" / f"relinked-{time.strftime('%Y%m%d-%H%M%S')}.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["relationship_id", "type", "source_before", "target_before", "source_after", "target_after", "detail"])
            w.writerows(log)
        conn.commit()
    say(f"relink-relations: written; before-values in {out}")


# A person's image that is really a stock file: a Commons file several
# unrelated people share whose name holds no word of the person's name and
# is not heraldry (arms are a fair stand-in for a medieval lord). "Mitre
# (plain).svg" on 46 bishops, a Knight's Cross ribbon on 50 officers, a
# House of Commons group painting, a regional map. QC judged 44 of 48 wrong.
GENERIC_IMAGES = r"""
with r as materialized (
  select e.entity_id, e.name, x.v->>'file' as file
  from entities e, jsonb_array_elements(e.attributes->'media_refs') x(v)
  where e.entity_type = 'person' and jsonb_typeof(e.attributes->'media_refs') = 'array'
    and not e.attributes ? '_media_curated_at'
), sh as materialized (
  select x.v->>'file' as file
  from entities e, jsonb_array_elements(e.attributes->'media_refs') x(v)
  where jsonb_typeof(e.attributes->'media_refs') = 'array'
  group by 1 having count(distinct e.entity_id) >= %(min)s and count(distinct lower(e.name)) >= 3
)
select r.entity_id::text, r.name, r.file from r join sh using (file)
where r.file !~* '(arms|blason|wappen|coat|stemma|herb|escudo|armoiries|COA|crest|emblem|flag|seal|gules|azure|argent|sable|chevron|fess|shield|lion|löwe|wapen|banner|house of|haus |lozenge|nassau|hohenlohe|stemme|escut|armas|brasão|bandiera|герб|clan|dynasty|family|tamga|monogram|erb|schild|slepowron|portrait|doge|\mmon\M|standard)'
  and not exists (select 1 from regexp_split_to_table(lower(r.name), '[^[:alpha:]]+') t
                  where length(t) >= 4 and lower(r.file) like '%%' || t || '%%')
"""


@cli.command("strip-generic-images")
@click.option("--min-uses", type=int, default=5, help="Entities that must share a file before it counts as stock")
@click.option("--yes", is_flag=True, help="Write; without it, a dry run")
def strip_generic_images(min_uses: int, yes: bool) -> None:
    """Drop stock Commons files from people's images (GENERIC_IMAGES).

    Only the matching entries go; media_refs stays (possibly empty), so the
    nightly entity:fetch-images, which fills rows without media_refs, does not
    bring them back. Removed entries go to output/bulk/tidy/images-<stamp>.csv.
    """
    import csv

    import psycopg

    from pipeline.bulk.store import ROOT
    from pipeline.local_db import dsn

    with psycopg.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute("set statement_timeout = 0")
        cur.execute(GENERIC_IMAGES, {"min": min_uses})
        rows = cur.fetchall()
        files = Counter(r[2] for r in rows)
        say(f"strip-generic-images: {len(rows)} entries on {len({r[0] for r in rows})} people; top files:")
        for f, n in files.most_common(12):
            say(f"  {n:4d}  {f}")
        if not yes or not rows:
            say("dry run; pass --yes to write" if rows else "nothing to do")
            return
        out = ROOT / "tidy" / f"images-{time.strftime('%Y%m%d-%H%M%S')}.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["entity_id", "name", "file"])
            w.writerows(rows)
        by_entity: dict[str, list[str]] = {}
        for eid, _, f in rows:
            by_entity.setdefault(eid, []).append(f)
        for eid, drop in by_entity.items():
            cur.execute(
                "update entities set attributes = jsonb_set(attributes, '{media_refs}', "
                "coalesce((select jsonb_agg(v) from jsonb_array_elements(attributes->'media_refs') v "
                "where not (v->>'file' = any(%s))), '[]'::jsonb)), updated_at = now() where entity_id = %s",
                (drop, eid),
            )
        conn.commit()
    say(f"strip-generic-images: written; removed entries in {out}")


RESUMMARIZE = r"""
select entity_id::text, summary, attributes->>'_wikipedia_extract'
from entities
where attributes ? '_bulk' and attributes ? '_wikipedia_extract' and summary is not null
  and (summary like '%%…' or summary ~ '[;:,]\s*$' or summary ~ '\(\s*[;,]?\s*\)' or summary ~ '\(\s*[;,]'
       or summary ~ '\[[0-9]+\]' or summary ~* '^(for (the|other|a|an)\M[^.]{0,200}\msee\M|not to be confused|this article)')
"""


@cli.command()
@click.option("--yes", is_flag=True, help="Write; without it, a dry run")
def resummarize(yes: bool) -> None:
    """Re-cut bulk summaries that are debris-laden, cut mid-sentence or a hatnote.

    The new summary comes from the row's own stored lead with today's
    clean_lead and _truncate_sentence; a row whose summary is not a cut of
    that lead (a Wikidata description fallback, an admin edit) is left alone.
    Before-values go to output/bulk/tidy/summaries-<stamp>.csv.
    """
    import csv

    import psycopg

    from pipeline.bulk.build import HATNOTE
    from pipeline.bulk.store import ROOT
    from pipeline.config import settings
    from pipeline.local_db import dsn
    from pipeline.wikidata.mapper.entity_mapper import EntityMapper, clean_lead, lead_paragraph

    def norm(t: str) -> str:
        return re.sub(r"\W+", "", clean_lead(t).rstrip("…")).lower()

    changes = []
    kinds: Counter = Counter()
    with psycopg.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute("set statement_timeout = 0")
        cur.execute(RESUMMARIZE)
        for eid, old, extract in cur.fetchall():
            paras = [p.strip() for p in extract.split("\n") if p.strip()]
            hat = bool(HATNOTE.search(old))
            if hat:
                lead = next((p for p in paras if len(p) > 40 and not HATNOTE.search(p)), None)
            else:
                first = lead_paragraph(extract)
                lead = first if first and norm(first).startswith(norm(old)[:60]) else None
            if not lead:
                kinds["not-from-lead"] += 1
                continue
            new = EntityMapper._truncate_sentence(clean_lead(lead), settings.summary_max_chars)
            if new and new != old:
                kinds["hatnote" if hat else "recut"] += 1
                changes.append((eid, old, new))
        say(f"resummarize: {dict(kinds)}")
        for eid, old, new in changes[:: max(1, len(changes) // 6)][:6]:
            say(f"  - {old[-70:]!r}\n    + {new[-70:]!r}")
        if not yes or not changes:
            say("dry run; pass --yes to write" if changes else "nothing to do")
            return
        out = ROOT / "tidy" / f"summaries-{time.strftime('%Y%m%d-%H%M%S')}.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["entity_id", "before", "after"])
            w.writerows(changes)
        cur.executemany("update entities set summary = %s, updated_at = now() where entity_id = %s",
                        [(new, eid) for eid, _, new in changes])
        conn.commit()
    say(f"resummarize: {len(changes)} written; before-values in {out}")


AUDIT_ACTIONS = ("needs_review", "delete", "merge_into", "fix_dates", "requid")


def drop_wrong_qid_links(cur, eid: str, old_qid: str) -> int:
    """Delete relations made from hints aimed at a QID the row held by mistake.

    A hint "born in Q316891" resolved to the curated "Emile" because that row
    held Montmorency's QID. Such relations go and their hints reopen, so the
    next resolve finds the real target or none. Returns the relations deleted.
    """
    cur.execute(
        """
        with h as (
          update pipeline_relationship_hints
             set resolved = false, resolution_note = 'requid: target held this QID by mistake'
           where target_wikidata_id = %(old)s and resolved and resolution_note = 'created'
          returning source_entity_id, relationship_type
        ), d as (
          delete from relationships r using h
           where r.relationship_type::text = h.relationship_type
             and ((r.source_entity_id = h.source_entity_id and r.target_entity_id = %(eid)s)
               or (r.target_entity_id = h.source_entity_id and r.source_entity_id = %(eid)s))
          returning 1
        )
        select count(*) from d
        """,
        {"old": old_qid, "eid": eid},
    )
    return cur.fetchone()[0]


def requid(cur, eid: str, target: str, same: bool = False) -> str | None:
    """Give an older row that holds another item's QID the right one.

    `target` is the bulk row about the same subject (it is folded in), the
    right QID (a bulk row holding it is folded in), or `none` to clear the
    wrong QID. The older row's points (unless an admin placed them) and its
    uncurated images came from the wrong item, so they go; the bulk row's
    point takes their place, and relations made from hints aimed at the
    wrong QID go (`drop_wrong_qid_links`). Its own text, dates and chronicle
    links stay. With `same` the old QID is a thin duplicate of the same
    subject (a "city seat" item): its links are right, and its hints are
    pointed at the new QID instead. Returns why it was refused, or None.
    """
    from pipeline.merge_entities import merge

    bulk_id, qid = None, None
    if re.fullmatch(r"Q\d+", target):
        qid = target
        cur.execute("select entity_id::text, attributes ? '_bulk' from entities where wikidata_id = %s", (qid,))
        hit = cur.fetchone()
        if hit and hit[0] != eid:
            if not hit[1]:
                return "requid-qid-held-by-curated-row"
            bulk_id = hit[0]
    elif target != "none":
        cur.execute("select wikidata_id, attributes ? '_bulk' from entities where entity_id = %s", (target,))
        row = cur.fetchone()
        if row is None or not row[0] or not row[1] or target == eid:
            return "bad-requid-target"
        bulk_id, qid = target, row[0]
    cur.execute("select wikidata_id from entities where entity_id = %s", (eid,))
    old = (cur.fetchone() or [None])[0]
    if old and old != qid:
        if same:  # the old QID is a thin duplicate of the same subject: its links are right
            cur.execute(
                "update pipeline_relationship_hints set target_wikidata_id = %s where target_wikidata_id = %s",
                (qid, old),
            )
        else:
            drop_wrong_qid_links(cur, eid, old)
    cur.execute(
        "delete from entity_locations where entity_id = %s and location_method is distinct from 'human_assigned'",
        (eid,),
    )
    if bulk_id:
        cur.execute("select exists(select 1 from entity_locations where entity_id = %s and is_primary)", (eid,))
        has_primary = cur.fetchone()[0]
        cur.execute(
            "update entity_locations set entity_id = %s, is_primary = is_primary and not %s where entity_id = %s",
            (eid, has_primary, bulk_id),
        )
    cur.execute("update entities set wikidata_id = null where entity_id = %s", (eid,))
    cur.execute(
        "update entities set attributes = attributes - 'media_refs' "
        "where entity_id = %s and not attributes ? '_media_curated_at'",
        (eid,),
    )
    if bulk_id:
        merge(cur, eid, bulk_id)
    if qid:
        cur.execute("update entities set wikidata_id = %s where entity_id = %s", (qid, eid))
    return None


@cli.command("apply-audit")
@click.argument("csv_paths", nargs=-1, required=True)
@click.option("--yes", is_flag=True, help="Write; without it, a dry run")
def apply_audit(csv_paths: tuple[str, ...], yes: bool) -> None:
    """Apply a bulk-auditor CSV (entity_id,qid,name,action,detail) after the orchestrator has curated it.

    needs_review flags the row; delete removes a bulk row (others are only
    flagged); merge_into:<id> folds the row into <id> (relations and
    chronicle links re-pointed; the survivor takes the QID if it has none);
    fix_dates:<start>..<end> sets the primary range (an empty side keeps it,
    `none` clears it: a city's 1950 incorporation is not its founding);
    requid:<bulk id | QID | none>[:same] gives an older row that holds the
    wrong QID the right one, folding in a bulk row about the same subject;
    :same when the old QID was a duplicate item of the same subject (see
    `requid`).
    Anything else is flagged needs_review. One transaction; before-values go
    to output/bulk/audit/applied-<stamp>.csv.
    """
    import csv

    import psycopg

    from pipeline.bulk.store import ROOT
    from pipeline.local_db import dsn
    from pipeline.merge_entities import merge

    todo = []
    for path in csv_paths:
        with open(path, newline="") as fh:
            todo += [dict(r, _file=path) for r in csv.DictReader(fh)]
    done: Counter = Counter()
    log_rows = []
    with psycopg.connect(dsn()) as conn, conn.cursor() as cur:
        for r in todo:
            eid = (r.get("entity_id") or "").strip()
            if not re.fullmatch(r"[0-9a-f-]{36}", eid):
                cur.execute("select entity_id::text from entities where wikidata_id = %s", (r.get("qid"),))
                hit = cur.fetchall()
                if len(hit) != 1:
                    done["unresolved"] += 1
                    continue
                eid = hit[0][0]
            cur.execute(
                "select e.name, e.wikidata_id, e.attributes ? '_bulk', t.start_year, t.end_year from entities e "
                "left join entity_temporal_ranges t on t.entity_id = e.entity_id and t.is_primary where e.entity_id = %s",
                (eid,),
            )
            row = cur.fetchone()
            if row is None:
                done["gone"] += 1
                continue
            name, qid, is_bulk, y0, y1 = row
            action, _, arg = (r.get("action") or "").partition(":")
            if action == "delete" and not is_bulk:
                action = "needs_review"
            if action == "requid" and is_bulk:
                done["requid-on-bulk-row"] += 1
                continue
            if action not in AUDIT_ACTIONS:
                action = "needs_review"
            log_rows.append([eid, qid, name, r.get("action"), y0, y1, r["_file"]])
            if action == "needs_review":
                cur.execute("update entities set verification_status = 'needs_review' where entity_id = %s", (eid,))
            elif action == "delete":
                cur.execute("delete from entities where entity_id = %s", (eid,))
            elif action == "merge_into":
                cur.execute("select wikidata_id from entities where entity_id = %s", (arg,))
                surv = cur.fetchone()
                if surv is None or arg == eid:
                    done["bad-merge-target"] += 1
                    continue
                merge(cur, arg, eid)
                if surv[0] is None and qid:
                    cur.execute("update entities set wikidata_id = %s where entity_id = %s", (qid, arg))
            elif action == "requid":
                target, _, mode = arg.partition(":")
                why = requid(cur, eid, target, same=mode == "same")
                if why:
                    done[why] += 1
                    continue
            elif action == "fix_dates":
                a, _, b = arg.partition("..")
                start = None if a.strip() == "none" else int(a) if a.strip() else y0
                end = None if b.strip() == "none" else int(b) if b.strip() else y1
                cur.execute(
                    "update entity_temporal_ranges set start_year = %s, end_year = %s, start_date = %s, end_date = %s, "
                    "notes = coalesce(notes || ' ', '') || 'audit fix_dates', updated_at = now() "
                    "where entity_id = %s and is_primary",
                    (start, end, None if start is None else str(start), None if end is None else str(end), eid),
                )
            done[action] += 1
        say(f"apply-audit: {dict(done)}" + ("" if yes else " (dry run; pass --yes to write)"))
        if not yes:
            conn.rollback()
            return
        out = ROOT / "audit" / f"applied-{time.strftime('%Y%m%d-%H%M%S')}.csv"
        with open(out, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["entity_id", "qid", "name", "action", "before_start", "before_end", "file"])
            w.writerows(log_rows)
        conn.commit()
    say(f"apply-audit: written; before-values in {out}")


@cli.command()
@click.option("--idle-exit", is_flag=True, help="Exit when nothing is left to import")
@click.option("--poll", type=int, default=30)
def importer(idle_exit: bool, poll: int) -> None:
    """Import built parts of approved slices (approved.txt), priority order, until STOP exists in the bulk root.

    Several daemons may run at once: each takes the next part no other
    daemon holds.
    """
    from pipeline.bulk.store import ROOT, approved

    reported: set[str] = set()
    while not (ROOT / "STOP").exists():
        did = False
        ok = approved()
        errors: list[str] = []
        for s in all_slices(errors=errors):
            if s.id not in ok:
                continue
            store = SliceStore(s.id)
            for n in pending_imports(store):
                if (ROOT / "STOP").exists():
                    break
                if import_part(s, store, n) is not None:
                    did = True
        for err in set(errors) - reported:
            # an approved slice whose spec this process cannot read is never
            # imported: say so (a daemon older than a new spec key, or a typo)
            say(f"importer: skipping unreadable spec {err}")
        reported |= set(errors)
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
