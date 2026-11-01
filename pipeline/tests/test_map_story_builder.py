"""`build` refuses to overwrite a story JSON edited outside the builder
(exported from the admin), unless --force; it records what it wrote in the
committed sidecar `.build-hashes.json`."""

import json
import sys
import types
from pathlib import Path

import pytest
from click.testing import CliRunner

import pipeline.map_stories.__main__ as cli_mod

REPO = Path(__file__).resolve().parents[2]
SAMPLE = REPO / "api" / "resources" / "map-stories" / "battle-of-cannae.json"
MODULE = "pipeline.map_stories.stories.test_only_story"


@pytest.fixture()
def out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(cli_mod, "OUT", tmp_path)
    monkeypatch.setattr(cli_mod, "HASHES", tmp_path / ".build-hashes.json")
    return tmp_path


@pytest.fixture()
def story(monkeypatch: pytest.MonkeyPatch) -> dict:
    doc = json.loads(SAMPLE.read_text())
    monkeypatch.setitem(sys.modules, MODULE, types.SimpleNamespace(build=lambda: doc))
    return doc


def _build(*args: str):
    return CliRunner().invoke(cli_mod.cli, ["build", "test_only_story", *args])


def test_build_writes_the_file_and_records_its_hash(out: Path, story: dict) -> None:
    res = _build()
    assert res.exit_code == 0, res.output
    target = out / "battle-of-cannae.json"
    assert target.read_text() == cli_mod.encode(story)
    assert json.loads((out / ".build-hashes.json").read_text()) == {target.name: cli_mod.sha1(target.read_bytes())}


def test_rebuild_overwrites_what_the_builder_wrote(out: Path, story: dict) -> None:
    assert _build().exit_code == 0
    story["title"] = "Battle of Cannae (revised)"
    res = _build()
    assert res.exit_code == 0, res.output
    assert "revised" in (out / "battle-of-cannae.json").read_text()


def test_refuses_a_file_edited_outside_the_builder_unless_forced(out: Path, story: dict) -> None:
    assert _build().exit_code == 0
    target = out / "battle-of-cannae.json"
    exported = target.read_text().replace('"Battle of Cannae"', '"Battle of Cannae (admin edit)"', 1)
    target.write_text(exported)
    story["outcome"] = "A builder change."

    res = _build()
    assert res.exit_code == 1
    assert "REFUSED" in res.output and "--force" in res.output
    assert target.read_text() == exported

    res = _build("--force")
    assert res.exit_code == 0, res.output
    assert "A builder change." in target.read_text()
    assert json.loads((out / ".build-hashes.json").read_text())[target.name] == cli_mod.sha1(target.read_bytes())


def test_an_unrecorded_file_identical_to_the_build_is_fine(out: Path, story: dict) -> None:
    (out / "battle-of-cannae.json").write_text(cli_mod.encode(story))
    assert _build().exit_code == 0


def test_sidecar_matches_the_committed_stories() -> None:
    """Every committed story is recorded, so the builder can tell an export from its own output."""
    hashes = json.loads((REPO / "api" / "resources" / "map-stories" / ".build-hashes.json").read_text())
    for path in cli_mod.story_files(REPO / "api" / "resources" / "map-stories"):
        assert path.name in hashes, f"{path.name} missing from .build-hashes.json"
