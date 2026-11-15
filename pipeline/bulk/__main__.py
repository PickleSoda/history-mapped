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

from pipeline.bulk.build import CURRENT_YEAR, build
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


AUDIT_ACTIONS = ("needs_review", "delete", "merge_into", "fix_dates", "requid")


def requid(cur, eid: str, target: str) -> str | None:
    """Give an older row that holds another item's QID the right one.

    `target` is the bulk row about the same subject (it is folded in), the
    right QID (a bulk row holding it is folded in), or `none` to clear the
    wrong QID. The older row's points (unless an admin placed them) and its
    uncurated images came from the wrong item, so they go; the bulk row's
    point takes their place. Its own text, dates and chronicle links stay.
    Returns why it was refused, or None.
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
    fix_dates:<start>..<end> sets the primary range (an empty end keeps it);
    requid:<bulk id | QID | none> gives an older row that holds the wrong
    QID the right one, folding in a bulk row about the same subject (see
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
                why = requid(cur, eid, arg)
                if why:
                    done[why] += 1
                    continue
            elif action == "fix_dates":
                a, _, b = arg.partition("..")
                start = int(a) if a.strip() else y0
                end = int(b) if b.strip() else y1
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
