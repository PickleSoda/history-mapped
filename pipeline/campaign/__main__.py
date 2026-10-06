"""History-data campaign CLI.

Run from the repo root:  pipeline/.venv/bin/python -m pipeline.campaign <command>
Every RUN argument accepts the run id (campaign_<slug>) or the bare slug.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import click

from pipeline.campaign import paths

PART_CHOICES = ["events", "entities", "relations", "summaries"]
WARN_CAP = 30


def _fail(msg: str, code: int = 1) -> None:
    click.echo(msg, err=True)
    raise SystemExit(code)


def _rel(p: Path) -> str:
    try:
        return os.path.relpath(p)
    except ValueError:
        return str(p)


def _ops():
    from pipeline.campaign import handoff_ops

    return handoff_ops


def _require_handoff(run: str) -> Path:
    p = paths.candidates_path(run)
    if not p.exists():
        _fail(f"no handoff for {paths.run_id_of(run)} at {_rel(p)} "
              f"(create it: handoff init {paths.slug_of(run)} --title \"...\")")
    return p


def _parse_payload(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        _fail(f"invalid JSON input: {exc} (nothing written)")


@click.group()
def cli():
    """History-data campaign tooling (handoffs, gathering, status, measurement)."""


# ── types / wiki ────────────────────────────────────────────────────────────

@cli.command("types")
@click.option("--relations-help", is_flag=True, help="Also print source → target hints per relation type.")
def types_cmd(relations_help: bool):
    """Allowed entity types (by group) and relation types, straight from code."""
    from pipeline.campaign.types_info import types_lines

    for line in types_lines(with_hints=relations_help):
        click.echo(line)


@cli.command("wiki")
@click.argument("titles", nargs=-1, required=True)
@click.option("--dated", is_flag=True, help="Keep only sentences with a year/century/BCE/CE/c. marker.")
@click.option("--max-chars", default=6000, show_default=True, help="Truncate each page's output.")
@click.option("--section", "sections", multiple=True, help="Only sections whose heading contains NAME ('lead' = intro). Repeatable.")
@click.option("--refresh", is_flag=True, help="Bypass the on-disk cache.")
def wiki_cmd(titles: tuple[str, ...], dated: bool, max_chars: int, sections: tuple[str, ...], refresh: bool):
    """Plain-text English Wikipedia extract(s), cached under output/campaign/cache/wiki/."""
    from pipeline.campaign import wiki

    missing = 0
    for title in titles:
        try:
            page = wiki.fetch_page(title, refresh=refresh)
        except Exception as exc:
            click.echo(f"=== {title}: request failed ({exc}) ===")
            missing += 1
            continue
        if page.title is None:
            click.echo(f"=== {title}: no such page (try: wiki-search \"{title}\") ===")
            missing += 1
            continue
        resolved = f" (-> {page.title})" if page.title != title else ""
        click.echo(f"=== {title}{resolved} ===")
        body = wiki.render(page, dated=dated, max_chars=max_chars, wanted_sections=list(sections))
        click.echo(body or "(no matching text)")
    if missing:
        raise SystemExit(1)


@cli.command("wiki-search")
@click.argument("query", nargs=-1, required=True)
@click.option("--limit", default=5, show_default=True)
def wiki_search_cmd(query: tuple[str, ...], limit: int):
    """Top Wikipedia titles for QUERY with one-line snippets."""
    from pipeline.campaign import wiki

    try:
        hits = wiki.search(" ".join(query), limit=limit)
    except Exception as exc:
        _fail(f"wiki-search failed: {exc}")
    if not hits:
        click.echo("(no results)")
    for title, snippet in hits:
        click.echo(f"{title} — {snippet}")


@cli.command("transcript-check")
@click.argument("run")
def transcript_check_cmd(run: str):
    """Lint a transcript: numbering, a BCE/CE year on every fact, era span, order.
    Errors (undated facts, repeated numbers) exit 1; era/order findings are warnings."""
    from pipeline.campaign.transcript import check_text

    tpath = paths.transcript_path(run)
    if not tpath.exists():
        _fail(f"transcript {paths.transcript_rel(run)} not found")
    era = paths.era_of(run)
    rep = check_text(tpath.read_text(encoding="utf-8"), era)
    click.echo(f"transcript {paths.slug_of(run)}: facts={rep.facts} dated={rep.dated} era={era or '-'}")
    for title, items in (("errors", rep.errors), ("warnings", rep.warnings)):
        if items:
            click.echo(f"{title} ({len(items)}):")
            for code, msg in items:
                click.echo(f"  {code}: {msg}")
    click.echo(f"{'FAIL' if rep.errors else 'OK'}: {len(rep.errors)} error(s), {len(rep.warnings)} warning(s)")
    if rep.errors:
        raise SystemExit(1)


# ── handoff ─────────────────────────────────────────────────────────────────

@cli.group("handoff")
def handoff():
    """Author and lint candidates.json handoffs (chunked, validated upserts)."""


@handoff.command("init")
@click.argument("run")
@click.option("--title", required=True, help="Chronicle title.")
@click.option("--force", is_flag=True, help="Start over; the existing file is moved to candidates.prev.json.")
def handoff_init(run: str, title: str, force: bool):
    """Create an empty handoff skeleton."""
    ops = _ops()
    path = paths.candidates_path(run)
    if path.exists():
        if not force:
            _fail(f"{_rel(path)} already exists ({ops.counts_line(ops.load_doc(path))}); "
                  f"use --force to start over (moves it to candidates.prev.json)")
        prev = path.with_name("candidates.prev.json")
        os.replace(path, prev)
        click.echo(f"moved existing handoff to {_rel(prev)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    ops.save_doc(path, ops.new_doc(paths.run_id_of(run), paths.transcript_rel(run), title))
    facts = paths.count_facts(paths.transcript_path(run))
    note = f"transcript facts={facts}" if facts is not None else f"WARNING transcript {paths.transcript_rel(run)} not found"
    click.echo(f"init {paths.run_id_of(run)} -> {_rel(path)} ({note})")


@handoff.command("add")
@click.argument("run")
@click.argument("part", type=click.Choice(PART_CHOICES))
@click.argument("source", type=click.File("r", encoding="utf-8"))
@click.option("--replace", is_flag=True, help="Replace matching items wholesale instead of merging fields.")
def handoff_add(run: str, part: str, source, replace: bool):
    """Upsert a JSON array from FILE (or - for stdin).

    Keys: events/entities/summaries by label, relations by
    (source_label, relationship_type, target_label). An existing item is updated
    by merging the given fields (null clears one). Summaries take
    {label: {summary, significance}} or [{label, summary, significance}].
    Valid items are written; rejected ones are listed and exit status is 1.
    """
    ops = _ops()
    path = _require_handoff(run)
    payload = _parse_payload(source.read())
    with ops.locked(path.parent):
        doc = ops.load_doc(path)
        try:
            res = ops.upsert(doc, part, payload, era=paths.era_of(run), replace=replace,
                             fact_map=paths.fact_lines(paths.transcript_path(run)))
        except ops.OpError as exc:
            _fail(f"{exc} (nothing written)")
        if res.added or res.updated:
            ops.save_doc(path, doc)
    for i, label, reason in res.rejected:
        click.echo(f"rejected [{i}] {label}: {reason}")
    for i, label, note in res.notes:
        click.echo(f"note [{i}] {label}: {note}")
    for i, label, hint in res.hints:
        click.echo(f"hint [{i}] {label}: {hint}")
    click.echo(f"{part}: added={res.added} updated={res.updated} rejected={len(res.rejected)}")
    click.echo(ops.counts_line(doc))
    if res.rejected:
        raise SystemExit(1)


@handoff.command("rm")
@click.argument("run")
@click.argument("part", type=click.Choice(["events", "entities", "relations"]))
@click.argument("keys", nargs=-1, required=True)
def handoff_rm(run: str, part: str, keys: tuple[str, ...]):
    """Remove items by key (relations: 'SOURCE|TYPE|TARGET'). Entities cascade to
    their relations + summary; events clear matching source_event references."""
    ops = _ops()
    path = _require_handoff(run)
    with ops.locked(path.parent):
        doc = ops.load_doc(path)
        try:
            report, missing = ops.remove(doc, part, keys)
        except ops.OpError as exc:
            _fail(f"{exc} (nothing written)")
        if report:
            ops.save_doc(path, doc)
    for line in report:
        click.echo(line)
    for key in missing:
        click.echo(f"not found: {key}")
    click.echo(ops.counts_line(doc))
    if missing:
        raise SystemExit(1)


def _rename(run: str, fn_name: str, old: str, new: str, merge: bool) -> None:
    ops = _ops()
    path = _require_handoff(run)
    with ops.locked(path.parent):
        doc = ops.load_doc(path)
        try:
            report = getattr(ops, fn_name)(doc, old, new, merge=merge)
        except ops.OpError as exc:
            _fail(f"{exc} (nothing written)")
        ops.save_doc(path, doc)
    for line in report:
        click.echo(line)
    click.echo(ops.counts_line(doc))


@handoff.command("rename")
@click.argument("run")
@click.argument("old")
@click.argument("new")
@click.option("--merge", is_flag=True, help="NEW already exists: fold OLD into it (relations repointed, OLD becomes an alias).")
def handoff_rename(run: str, old: str, new: str, merge: bool):
    """Rename an entity label everywhere (entity, relation endpoints, summary, events' mentioned_entities)."""
    _rename(run, "rename_entity", old, new, merge)


@handoff.command("rename-event")
@click.argument("run")
@click.argument("old")
@click.argument("new")
@click.option("--merge", is_flag=True, help="NEW already exists: drop OLD and repoint its references to NEW.")
def handoff_rename_event(run: str, old: str, new: str, merge: bool):
    """Rename an event label and every entity/relation source_event pointing at it."""
    _rename(run, "rename_event", old, new, merge)


@handoff.command("show")
@click.argument("run")
@click.option("--part", type=click.Choice(PART_CHOICES), default=None)
@click.option("--labels-only", is_flag=True, help="Only keys (relations as SOURCE|TYPE|TARGET).")
def handoff_show(run: str, part: str | None, labels_only: bool):
    """Compact one-line-per-item listing."""
    ops = _ops()
    doc = ops.load_doc(_require_handoff(run))
    parts = [part] if part else PART_CHOICES
    for p in parts:
        lines = ops.show_lines(doc, p, labels_only)
        if not part:
            click.echo(f"# {p} ({len(lines)})")
        for line in lines:
            click.echo(line)


@handoff.command("get")
@click.argument("run")
@click.argument("part", type=click.Choice(PART_CHOICES))
@click.argument("keys", nargs=-1, required=True)
def handoff_get(run: str, part: str, keys: tuple[str, ...]):
    """Print the full stored JSON of specific items (one per line)."""
    ops = _ops()
    doc = ops.load_doc(_require_handoff(run))
    try:
        found, missing = ops.get_items(doc, part, keys)
    except ops.OpError as exc:
        _fail(str(exc))
    for line in found:
        click.echo(line)
    for key in missing:
        click.echo(f"not found: {key}")
    if missing:
        raise SystemExit(1)


def _parse_facts_opt(spec: str) -> list[int]:
    try:
        return _ops().parse_facts(spec)
    except _ops().OpError as exc:
        _fail(str(exc))


@handoff.command("check")
@click.argument("run")
@click.option("--all", "show_all", is_flag=True, help=f"Don't cap warnings at {WARN_CAP} per kind.")
@click.option("--facts", "facts_spec", default=None,
              help="Only what this fact slice owns (e.g. 21-40), plus its density vs the slice targets.")
def handoff_check(run: str, show_all: bool, facts_spec: str | None):
    """Fast lint: hard errors exit 1, warnings exit 0."""
    ops = _ops()
    doc = ops.load_doc(_require_handoff(run))
    tpath = paths.transcript_path(run)
    fact_map = paths.fact_lines(tpath)
    kwargs = dict(era=paths.era_of(run), facts=paths.count_facts(tpath),
                  fact_numbers=None if fact_map is None else list(fact_map), fact_map=fact_map)
    scope = ops.slice_scope(doc, _parse_facts_opt(facts_spec)) if facts_spec else None
    rep = ops.lint(doc, scope=scope, **kwargs)
    stats = " ".join(f"{k}={'-' if v is None else v}" for k, v in rep.stats.items())
    click.echo(f"check {paths.run_id_of(run)}: {stats}")
    if scope is not None:
        outside = len(ops.lint(doc, **kwargs).errors) - len(rep.errors)
        if outside > 0:
            click.echo(f"({outside} error(s) outside this slice not shown; run check without --facts)")
    if rep.errors:
        click.echo(f"errors ({len(rep.errors)}):")
        for code, msg in rep.errors:
            click.echo(f"  {code}: {msg}")
    if rep.warnings:
        click.echo(f"warnings ({len(rep.warnings)}):")
        shown: dict[str, int] = {}
        for code, msg in rep.warnings:
            shown[code] = shown.get(code, 0) + 1
            if show_all or shown[code] <= WARN_CAP:
                click.echo(f"  {code}: {msg}")
        for code, n in shown.items():
            if not show_all and n > WARN_CAP:
                click.echo(f"  {code}: ... +{n - WARN_CAP} more (use --all)")
    verdict = "FAIL" if rep.errors else "OK"
    click.echo(f"{verdict}: {len(rep.errors)} error(s), {len(rep.warnings)} warning(s)")
    if rep.errors:
        raise SystemExit(1)


@handoff.command("slice")
@click.argument("run")
@click.option("--facts", "facts_spec", required=True, help="Fact numbers, e.g. 21-40 or 5,7-9.")
def handoff_slice(run: str, facts_spec: str):
    """One extraction slice: those numbered facts verbatim, events already tagged
    with them, and every existing entity label by type (no full transcript/handoff)."""
    ops = _ops()
    facts = _parse_facts_opt(facts_spec)
    fact_map = paths.fact_lines(paths.transcript_path(run))
    if fact_map is None:
        _fail(f"transcript {paths.transcript_rel(run)} not found")
    path = paths.candidates_path(run)
    doc = ops.load_doc(path) if path.exists() else None
    for line in ops.slice_lines(doc, fact_map, facts, paths.transcript_rel(run)):
        click.echo(line)


@handoff.command("rm-slice")
@click.argument("run")
@click.option("--facts", "facts_spec", required=True, help="Fact numbers, e.g. 21-40.")
def handoff_rm_slice(run: str, facts_spec: str):
    """Remove a slice's extraction (events tagged with these facts, the relations
    they produced, and entities no other fact uses) so it can be re-extracted."""
    ops = _ops()
    path = _require_handoff(run)
    facts = _parse_facts_opt(facts_spec)
    with ops.locked(path.parent):
        doc = ops.load_doc(path)
        report = ops.remove_slice(doc, facts)
        ops.save_doc(path, doc)
    for line in report:
        click.echo(line)
    click.echo(ops.counts_line(doc))


@handoff.command("fix-dates")
@click.argument("run")
@click.option("--apply", "apply_", is_flag=True, help="Write the fixes (default: only list them).")
def handoff_fix_dates(run: str, apply_: bool):
    """Un-pad -01-01 dates: a date whose fact doesn't state 1 January of that year
    becomes the bare year ("1873"), or year-month ("1873-01") when the fact says
    January. Lists the fixes; --apply writes them."""
    ops = _ops()
    path = _require_handoff(run)
    fact_map = paths.fact_lines(paths.transcript_path(run))
    if fact_map is None:
        click.echo(f"warning: transcript {paths.transcript_rel(run)} not found; every -01-01 date counts as padded")
    with ops.locked(path.parent):
        doc = ops.load_doc(path)
        report = ops.fix_padded_dates(doc, fact_map)
        if apply_ and report:
            ops.save_doc(path, doc)
    for line in report:
        click.echo(f"  {line}")
    verb = "fixed" if apply_ else "would fix (rerun with --apply)"
    click.echo(f"fix-dates {paths.run_id_of(run)}: {verb} {len(report)} padded date(s)")


@handoff.command("finalize")
@click.argument("run")
@click.option("--critic-iterations", default=2, show_default=True)
def handoff_finalize(run: str, critic_iterations: int):
    """Stamp self_audit, then run the real validation gate (exit code mirrors it)."""
    ops = _ops()
    path = _require_handoff(run)
    with ops.locked(path.parent):
        doc = ops.load_doc(path)
        doc["self_audit"] = {**(doc.get("self_audit") or {}),
                             "critic_iterations": critic_iterations, "orphan_check_done": True}
        ops.save_doc(path, doc)
    from pipeline.agent.validate_handoff import main as validate_main

    raise SystemExit(validate_main(_rel(path)))


# ── campaign-wide ───────────────────────────────────────────────────────────

def _json_rows(data: dict) -> str:
    runs = ",\n".join("  " + json.dumps(r, ensure_ascii=False) for r in data["runs"])
    return ('{"runs": [\n' + runs + "\n],\n"
            f'"totals": {json.dumps(data["totals"], ensure_ascii=False)},\n'
            f'"grid": {json.dumps(data["grid"], ensure_ascii=False)}}}')


@cli.command("status")
@click.option("--era", default=None, help="e.g. e04")
@click.option("--json", "as_json", is_flag=True)
@click.option("--thin", is_flag=True, help="Only runs with facts < 60 or r/e < 1.3.")
@click.option("--validate", is_flag=True, help="Also run the validation gate per handoff (slower).")
def status_cmd(era: str | None, as_json: bool, thin: bool, validate: bool):
    """One row per campaign run: facts, events, entities, relations, r/e, review, ingest."""
    from pipeline.campaign import status

    rows = status.collect(era=era, validate=validate)
    total = len(rows)
    if thin:
        rows = [r for r in rows if r.thin]
    if as_json:
        click.echo(_json_rows(status.as_json(rows)))
        return
    for line in status.table_lines(rows, show_valid=validate):
        click.echo(line)
    click.echo("")
    if thin:
        click.echo(f"thin: {len(rows)} of {total} runs (facts < {status.THIN_FACTS} or r/e < {status.THIN_DENSITY})")
    for line in status.footer_lines(rows):
        click.echo(line)


@cli.command("validate-all")
@click.option("--era", default=None, help="e.g. e04")
def validate_all_cmd(era: str | None):
    """Run the validation gate on every handoff; print failures only."""
    from pipeline.agent.validate_handoff import validate

    ok = failed = 0
    for d in sorted(paths.extractions_dir().glob(f"{paths.RUN_PREFIX}*")):
        cand = d / "candidates.json"
        if not cand.exists() or (era and paths.era_of(d.name) != era):
            continue
        errors = validate(_rel(cand))
        if not errors:
            ok += 1
            continue
        failed += 1
        click.echo(f"FAIL {d.name}: {len(errors)} error(s)")
        for e in errors[:5]:
            click.echo(f"  - {e}")
        if len(errors) > 5:
            click.echo(f"  (+{len(errors) - 5} more)")
    click.echo(f"{ok} ok, {failed} failed")
    if failed:
        raise SystemExit(1)


@cli.command("review-record")
@click.argument("run")
@click.option("--verdict", required=True, type=click.Choice(["PASS", "FIXED", "REGATHER", "ESCALATE"]))
@click.option("--model", required=True, help="Reviewer/fixer model name.")
@click.option("--issue", "issues", multiple=True, help="Repeatable.")
@click.option("--fixed", "fixed", multiple=True, help="Repeatable.")
def review_record_cmd(run: str, verdict: str, model: str, issues: tuple[str, ...], fixed: tuple[str, ...]):
    """Append a review entry to the run's review.json (history kept; latest = last)."""
    hdir = paths.handoff_dir(run)
    if not hdir.exists() and not paths.transcript_path(run).exists():
        _fail(f"unknown run {paths.run_id_of(run)} (no handoff dir or transcript)")
    hdir.mkdir(parents=True, exist_ok=True)
    path = paths.review_path(run)
    data: dict = {"run_id": paths.run_id_of(run), "history": []}
    if path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        data["history"] = loaded if isinstance(loaded, list) else loaded.get("history") or []
    data["history"].append({
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "verdict": verdict, "model": model, "issues": list(issues), "fixed": list(fixed),
    })
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    click.echo(f"review {paths.run_id_of(run)}: {verdict} by {model} "
               f"(issues={len(issues)} fixed={len(fixed)} history={len(data['history'])})")


@cli.command("measure")
@click.option("--jan1-csv", "jan1_csv", type=click.Path(dir_okay=False, path_type=Path), default=None,
              help="Also write every -01-01 date with its verdict and corrected value (a repair list; nothing is applied).")
def measure_cmd(jan1_csv: Path | None):
    """Acceptance metrics against the running compose DB (exit 2 if it's down)."""
    from pipeline.campaign import measure

    try:
        rows = measure.run_sql(measure.build_sql())
    except measure.DbUnavailable as exc:
        _fail(f"measure: {exc}", code=2)
    for line in measure.report_lines(rows):
        click.echo(line)
    if jan1_csv is not None:
        fixes = measure.classify_jan1([r for r in rows if r and r[0] in ("jan1_range_row", "jan1_rel_row")])
        measure.write_jan1_csv(fixes, jan1_csv)
        click.echo(f"wrote {len(fixes)} -01-01 value(s) to {_rel(jan1_csv)}")


if __name__ == "__main__":
    cli()
