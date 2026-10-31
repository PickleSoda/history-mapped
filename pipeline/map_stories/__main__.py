"""Map-story CLI. `cheatsheet` prints everything an author needs on one screen.

    python -m pipeline.map_stories cheatsheet
    python -m pipeline.map_stories research "Battle of Waterloo" [--section Hougoumont …] [--qids Q131691 …]
    python -m pipeline.map_stories places "Hougoumont" "La Haye Sainte" --near 4.412,50.678 [--elevation]
    python -m pipeline.map_stories build battle_of_cannae          # run stories/battle_of_cannae.py, check, write JSON
    python -m pipeline.map_stories build --all
    python -m pipeline.map_stories build battle_of_cannae --force  # overwrite a file edited outside the builder
    python -m pipeline.map_stories check api/resources/map-stories/battle-of-cannae.json [--verbose | --json]
    python -m pipeline.map_stories preview <story.json> [--step ID | --all-steps]
    python -m pipeline.map_stories queue --limit 200
"""

from __future__ import annotations

import hashlib
import importlib
import json
import re
import sys
from pathlib import Path

import click

from pipeline.map_stories.lint import Issue, lint
from pipeline.map_stories.validate import validate

REPO = Path(__file__).resolve().parents[2]
STORIES = Path(__file__).resolve().parent / "stories"
OUT = REPO / "api" / "resources" / "map-stories"
#: Committed sidecar: file name → sha1 of what the builder last wrote there. A
#: file whose bytes match neither it nor the new build was edited outside the
#: builder (in the admin, by the AI agent, then `map-stories:export`ed).
HASHES = OUT / ".build-hashes.json"
MAX_LINES = 20
_STEP_MSG = re.compile(r"^step '([^']*)'[.:]?\s*(.*)$")


# ── reporting ─────────────────────────────────────────────────────────────


def analyse(doc: dict) -> dict:
    """Validation plus (when the document is structurally sound) lint."""
    rep = validate(doc)
    issues: list[Issue] = lint(doc) if rep.ok else []
    return {"ok": rep.ok, "errors": list(rep.errors), "warnings": list(rep.warnings), "lint": issues}


def _by_step(doc: dict, res: dict) -> list[tuple[str, list[str]]]:
    """Warnings and lint issues grouped by step id, in story order ('story' first)."""
    groups: dict[str, list[str]] = {}
    for w in res["warnings"]:
        m = _STEP_MSG.match(w)
        sid, msg = (m.group(1), m.group(2)) if m else ("story", w)
        groups.setdefault(sid, []).append(msg)
    for i in res["lint"]:
        groups.setdefault(i.step or "story", []).append(f"{i.code}: {i.msg}")
    order = ["story"] + [str(s.get("id")) for s in doc.get("steps", []) if isinstance(s, dict)]
    return sorted(groups.items(), key=lambda kv: order.index(kv[0]) if kv[0] in order else len(order))


def report_lines(name: str, doc: dict, res: dict, verbose: bool = False, max_lines: int = MAX_LINES) -> list[str]:
    steps = doc.get("steps") if isinstance(doc, dict) else None
    n_steps = len(steps) if isinstance(steps, list) else 0
    n_units = len(doc.get("units") or []) if isinstance(doc, dict) else 0
    head = (
        f"{name}: {'ok' if res['ok'] else 'FAILED'} — {len(res['errors'])} errors, {len(res['warnings'])} warnings, "
        f"{len(res['lint'])} lint ({n_steps} steps, {n_units} units)"
    )
    lines = [head] + [f"  ERROR {e}" for e in res["errors"]]
    for sid, msgs in _by_step(doc, res):
        if verbose:
            lines += [f"  [{sid}] {m}" for m in msgs]
        else:
            joined = " · ".join(msgs)
            lines.append(f"  [{sid}] {joined if len(joined) <= 230 else joined[:220] + f' … (+{len(msgs)} in all)'}")
    if not verbose and max_lines <= 1:
        more = len(lines) - 1
        return [head + (f" — {more} issue line(s): check this file alone" if more else "")]
    if not verbose and len(lines) > max_lines:
        cut = len(lines) - (max_lines - 1)
        lines = lines[: max_lines - 1] + [f"  … {cut} more lines (--verbose shows everything)"]
    return lines


def report_json(name: str, res: dict) -> dict:
    return {
        "file": name,
        "ok": res["ok"],
        "errors": res["errors"],
        "warnings": res["warnings"],
        "lint": [{"step": i.step, "code": i.code, "msg": i.msg} for i in res["lint"]],
    }


def _rel(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(REPO))
    except ValueError:
        return str(p)


# ── builder protection ────────────────────────────────────────────────────


def story_files(directory: Path | None = None) -> list[Path]:
    """The story JSON files (pathlib's glob also matches dotfiles: skip the sidecar)."""
    return sorted(p for p in (directory or OUT).glob("*.json") if not p.name.startswith("."))


def encode(doc: dict) -> str:
    """The file content: what `map-stories:export` writes too (api MapStoryFile)."""
    return json.dumps(doc, ensure_ascii=False, indent=1) + "\n"


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def load_hashes() -> dict[str, str]:
    try:
        data = json.loads(HASHES.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)} if isinstance(data, dict) else {}


def save_hashes(hashes: dict[str, str]) -> None:
    HASHES.write_text(json.dumps(dict(sorted(hashes.items())), indent=1) + "\n")


def edited_outside(target: Path, content: str, hashes: dict[str, str]) -> bool:
    """Whether `target` holds something the builder did not write last (and
    the new build would change it): a hand edit or an admin/AI export."""
    if not target.exists():
        return False
    on_disk = target.read_bytes()
    return on_disk != content.encode() and sha1(on_disk) != hashes.get(target.name)


# ── commands ──────────────────────────────────────────────────────────────


@click.group()
def cli() -> None:
    """Research, build, check and preview map stories (start with `cheatsheet`)."""


@cli.command()
def cheatsheet() -> None:
    """Print the vocabulary, helper signatures, builder skeleton and commands (<150 lines)."""
    from pipeline.map_stories.cheatsheet import render

    click.echo(render())


@cli.command()
@click.argument("modules", nargs=-1)
@click.option("--all", "build_all", is_flag=True, help="Build every story module.")
@click.option("--verbose", is_flag=True, help="Print every issue.")
@click.option("--force", is_flag=True, help="Overwrite a JSON file that was edited outside the builder.")
def build(modules: tuple[str, ...], build_all: bool, verbose: bool, force: bool) -> None:
    """Run story builder modules, check them, and write their JSON to api/resources/map-stories/.

    A file edited outside the builder (exported from the admin, where humans
    and the AI agent edit stories) is not overwritten without --force: port
    those edits into the builder module first."""
    names = sorted(p.stem for p in STORIES.glob("*.py") if not p.stem.startswith("_")) if build_all else list(modules)
    if not names:
        raise click.UsageError("name a builder module or pass --all")
    failed = False
    OUT.mkdir(parents=True, exist_ok=True)
    hashes = load_hashes()
    for name in names:
        mod = importlib.import_module(f"pipeline.map_stories.stories.{Path(name).stem}")
        doc = mod.build()
        res = analyse(doc)
        lines = report_lines(Path(name).stem, doc, res, verbose, MAX_LINES if len(names) == 1 else 1)
        if not res["ok"]:
            failed = True
            click.echo("\n".join(lines))
            continue
        target = OUT / f"{doc['slug']}.json"
        content = encode(doc)
        if not force and edited_outside(target, content, hashes):
            failed = True
            lines.insert(1, f"  REFUSED {_rel(target)}: it was edited outside the builder (exported from the admin?) — "
                            f"port those edits into stories/{Path(name).stem}.py, or pass --force to overwrite them")
            click.echo("\n".join(lines))
            continue
        target.write_text(content)
        hashes[target.name] = sha1(content.encode())
        save_hashes(hashes)
        lines.insert(1, f"  wrote {_rel(target)}")
        click.echo("\n".join(lines))
    sys.exit(1 if failed else 0)


@cli.command()
@click.argument("files", nargs=-1, type=click.Path(exists=True, path_type=Path))
@click.option("--verbose", is_flag=True, help="Print every issue, one per line.")
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output (for the reviewer).")
def check(files: tuple[Path, ...], verbose: bool, as_json: bool) -> None:
    """Validate and lint story JSON. Exit 1 on errors (warnings and lint never fail)."""
    targets = list(files) or story_files()
    ok, out = True, []
    for f in targets:
        try:
            doc = json.loads(f.read_text())
        except json.JSONDecodeError as e:
            res = {"ok": False, "errors": [f"not JSON: {e}"], "warnings": [], "lint": []}
            doc = {}
        else:
            res = analyse(doc)
        ok = ok and res["ok"]
        if as_json:
            out.append(report_json(_rel(f), res))
        else:
            # One file: up to 20 lines. Several: a summary line each (failures in full).
            budget = MAX_LINES if len(targets) == 1 or not res["ok"] else 1
            click.echo("\n".join(report_lines(_rel(f), doc, res, verbose, budget)))
    if as_json:
        click.echo(json.dumps(out[0] if len(out) == 1 else out, ensure_ascii=False, indent=1))
    sys.exit(0 if ok else 1)


@cli.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option("--step", "step", default=None, help="One step (its id or 1-based number), at 900×600.")
@click.option("--all-steps", is_flag=True, help="Every step at 760×560 (large image; prefer the contact sheet).")
def preview(file: Path, step: str | None, all_steps: bool) -> None:
    """Screenshot the story over a topographic map: a contact sheet of every step by default."""
    from pipeline.map_stories.preview import render, step_index

    doc = json.loads(file.read_text())
    png = render(doc, step_index(doc, step), "all" if all_steps else "contact")
    click.echo(_rel(png))


@cli.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option("--step", default=None, help="Only this step's prose.")
@click.option("--links", "show_links", is_flag=True, help="Check every Q-id against its Wikidata label and class.")
def digest(file: Path, step: str | None, show_links: bool) -> None:
    """A story's prose without coordinates (for review), or a check of its Q-id links."""
    from pipeline.map_stories.digest import link_lines, prose

    doc = json.loads(file.read_text())
    click.echo("\n".join(link_lines(doc) if show_links else prose(doc, step)))


@cli.command(context_settings={"ignore_unknown_options": True, "allow_interspersed_args": False})
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def research(args: tuple[str, ...]) -> None:
    """Wikipedia/Wikidata facts in small cached pieces.

    \b
    research "<Wikipedia title>"|Qid [--outline] [--section NAME …] [--qids Q1 Q2 …]
             [--lang en] [--max-chars 6000] [--refresh]
    Default: outline (section sizes) + infobox basics with commander/polity Q-ids.
    --section: only those sections ('lead' = intro). --qids: check Q-ids in one batch.
    """
    from pipeline.map_stories.research import run

    opts: dict = {"section": [], "qids": [], "lang": "en", "max-chars": "6000", "outline": False, "refresh": False}
    ref, key = [], None
    for tok in args:
        if tok.startswith("--"):
            name, _, val = tok[2:].partition("=")
            if name in ("outline", "refresh"):
                opts[name], key = True, None
            elif name in opts:
                key = name
                if val:
                    opts[name] = opts[name] + [val] if isinstance(opts[name], list) else val
                    key = name if isinstance(opts[name], list) else None
            else:
                raise click.UsageError(f"unknown option --{name}")
        elif key in ("section", "qids"):
            opts[key].extend(t for t in re.split(r"[\s,]+", tok) if t) if key == "qids" else opts[key].append(tok)
        elif key in ("lang", "max-chars"):
            opts[key], key = tok, None
        else:
            ref.append(tok)
    if not ref and not opts["qids"]:
        raise click.UsageError("give a Wikipedia title or Q-id, or --qids")
    click.echo(run(" ".join(ref), opts["section"], opts["outline"], opts["qids"], opts["lang"], int(opts["max-chars"]), opts["refresh"]))


def _near(value: str | None) -> tuple[float, float] | None:
    if not value:
        return None
    if re.fullmatch(r"Q[1-9]\d*", value.strip()):
        from pipeline.map_stories.net import wd_entities

        coord = (wd_entities([value.strip()]).get(value.strip()) or {}).get("coord")
        if not coord:
            raise click.BadParameter(f"{value} has no P625 coordinates; pass LON,LAT")
        return (coord[0], coord[1])
    try:
        lon, lat = (float(x) for x in value.split(","))
    except ValueError as e:
        raise click.BadParameter("LON,LAT (e.g. 4.412,50.678) or a Q-id") from e
    return (lon, lat)


@cli.command()
@click.argument("names", nargs=-1, required=True)
@click.option("--near", help="LON,LAT or the battle's Q-id: rank and filter matches around it.")
@click.option("--radius-km", type=float, default=15.0, show_default=True)
@click.option("--elevation", is_flag=True, help="Add SRTM ground height at each point.")
@click.option("--geometry", type=click.Choice(["river", "stream", "coast", "lake", "ridge", "hill", "woods", "marsh", "road", "town"]), help="Print the feature's simplified line/outline.")
@click.option("--max-points", type=int, default=40, show_default=True, help="With --geometry: simplify to at most this many points.")
def places(names: tuple[str, ...], near: str | None, radius_km: float, elevation: bool, geometry: str | None, max_points: int) -> None:
    """Coordinates for many place names in one batch (OSM, then Wikidata), cached."""
    from pipeline.map_stories.places import run

    click.echo(run(list(names), _near(near), radius_km, geometry, elevation, max_points))


@cli.command()
@click.option("--limit", type=int, default=200, show_default=True)
@click.option("--kinds", default="battle,siege,naval_battle", show_default=True, help="Story kinds to include (also: campaign, other).")
@click.option("--show", type=int, default=10, show_default=True, help="Rows to print.")
def queue(limit: int, kinds: str, show: int) -> None:
    """Rank battles without a map story into output/map-stories/queue.tsv (reads the DB)."""
    from pipeline.map_stories import queue as q

    rows = q.build(limit, tuple(k.strip() for k in kinds.split(",") if k.strip()))
    click.echo(q.summary(rows, q.QUEUE, show))


if __name__ == "__main__":
    cli()
