"""Map-story CLI.

    python -m pipeline.map_stories build battle_of_cannae    # run stories/battle_of_cannae.py, check, write JSON
    python -m pipeline.map_stories build --all
    python -m pipeline.map_stories check api/resources/map-stories/battle-of-cannae.json
    python -m pipeline.map_stories preview api/resources/map-stories/battle-of-cannae.json [--step N]
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import click

from pipeline.map_stories.validate import validate

REPO = Path(__file__).resolve().parents[2]
STORIES = Path(__file__).resolve().parent / "stories"
OUT = REPO / "api" / "resources" / "map-stories"


def _report(name: str, doc: dict) -> bool:
    rep = validate(doc)
    for e in rep.errors:
        click.echo(f"  ERROR   {e}")
    for w in rep.warnings:
        click.echo(f"  warning {w}")
    click.echo(f"{name}: {'ok' if rep.ok else 'FAILED'} ({len(rep.errors)} errors, {len(rep.warnings)} warnings)")
    return rep.ok


@click.group()
def cli() -> None:
    """Build, check and preview map stories."""


@cli.command()
@click.argument("modules", nargs=-1)
@click.option("--all", "build_all", is_flag=True, help="Build every story module.")
def build(modules: tuple[str, ...], build_all: bool) -> None:
    """Run story builder modules and write their JSON to api/resources/map-stories/."""
    names = sorted(p.stem for p in STORIES.glob("*.py") if not p.stem.startswith("_")) if build_all else list(modules)
    if not names:
        raise click.UsageError("name a builder module or pass --all")
    failed = False
    OUT.mkdir(parents=True, exist_ok=True)
    for name in names:
        mod = importlib.import_module(f"pipeline.map_stories.stories.{name.removesuffix('.py')}")
        doc = mod.build()
        if not _report(name, doc):
            failed = True
            continue
        target = OUT / f"{doc['slug']}.json"
        target.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
        click.echo(f"  wrote {target.relative_to(REPO)}")
    sys.exit(1 if failed else 0)


@cli.command()
@click.argument("files", nargs=-1, type=click.Path(exists=True, path_type=Path))
def check(files: tuple[Path, ...]) -> None:
    """Validate story JSON files."""
    targets = list(files) or sorted(OUT.glob("*.json"))
    ok = all([_report(str(f), json.loads(f.read_text())) for f in targets])
    sys.exit(0 if ok else 1)


@cli.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option("--step", type=int, default=None, help="1-based step to render alone (default: all steps in a grid).")
def preview(file: Path, step: int | None) -> None:
    """Screenshot the story over a topographic map (output/map-stories/preview/)."""
    from pipeline.map_stories.preview import render

    png = render(json.loads(file.read_text()), None if step is None else step - 1)
    click.echo(str(png))


if __name__ == "__main__":
    cli()
