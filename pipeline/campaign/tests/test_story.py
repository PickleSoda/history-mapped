import copy
import json

from click.testing import CliRunner

from pipeline.campaign import story
from pipeline.campaign.__main__ import cli

NARRATIVE = (
    "Around 3200 BCE the temple scribes of Uruk began pressing reed styluses into wet clay to keep "
    "track of barley, sheep and labour owed to the gods. What began as bookkeeping became writing: "
    "within a few centuries the marks stood for sounds as well as things, and the same script could "
    "record a king's victory, a hymn or a contract. Writing let a city remember more than any one "
    "person could, and it let rulers count, tax and command people they would never meet."
)


def entry(i: int, year: int) -> dict:
    return {
        "sequence_order": i,
        "narrative_text": NARRATIVE,
        "start_year": year,
        "source_evidence": "Cuneiform; Uruk period",
        "secondary_entities": [
            {"entity_id": "07a30c1a-ccdc-408c-b4ac-dd70f0c1f62f", "name": "Uruk",
             "wikidata_id": "Q168518", "role": "location"},
            {"entity_id": "Cuneiform", "name": "Cuneiform", "wikidata_id": "Q401", "role": "participant"},
        ],
    }


def chapter(n: int = 16) -> dict:
    return {
        "title": "The First Cities",
        "slug": "the-first-cities",
        "source_type": "article",
        "source_reference": "Facts checked against English Wikipedia",
        "status": "draft",
        "start_year": -4000,
        "end_year": -2000,
        "tags": ["bronze-age", "mesopotamia"],
        "entries": [entry(i, -3500 + i * 50) for i in range(n)],
    }


def test_a_good_chapter_passes():
    report = story.check(chapter(), slug="the-first-cities")
    assert report.errors == []
    assert report.warnings == []


def test_schema_errors_stop_the_check():
    data = chapter()
    del data["title"]
    report = story.check(data)
    assert [e for e in report.errors if e.startswith("schema: title")]


def test_chapter_rules():
    data = chapter(n=10)
    data["status"] = "published"
    data["slug"] = "elsewhere"
    data["entries"][3]["sequence_order"] = 7
    report = story.check(data, slug="the-first-cities")
    text = "\n".join(report.errors)
    assert "10 entries" in text
    assert "status must be 'draft'" in text
    assert "does not match its directory" in text
    assert "sequence_order must run" in text


def test_entry_rules():
    data = chapter()
    e = data["entries"][2]
    e["narrative_text"] = "- a bullet list\n- is not a story " + NARRATIVE
    e["source_evidence"] = ""
    e["end_year"] = e["start_year"] - 10
    e["secondary_entities"].append(copy.deepcopy(e["secondary_entities"][0]))
    e["secondary_entities"][1]["role"] = "hero"
    e["secondary_entities"].append({"entity_id": "Gilgamesh", "name": "Gilgamesh", "role": "mentioned"})
    text = "\n".join(story.check(data).errors)
    assert "entry 2: narrative has markdown" in text
    assert "entry 2: source_evidence is empty" in text
    assert "entry 2: end_year is before start_year" in text
    assert "entry 2: Uruk is linked twice" in text
    assert "role 'hero'" in text
    assert "Gilgamesh: needs the entity_id (uuid) or wikidata_id" in text


def test_long_quotes_are_errors_and_short_ones_are_not():
    data = chapter()
    data["entries"][0]["narrative_text"] = NARRATIVE + ' The king called it "the city of the gods".'
    data["entries"][1]["narrative_text"] = NARRATIVE + (
        ' A later poem says "he who saw the deep, the foundation of the land, who knew everything '
        'and was wise in all matters".')
    errors = story.check(data).errors
    assert not [e for e in errors if e.startswith("entry 0")]
    assert [e for e in errors if e.startswith("entry 1: a quotation of")]


def test_out_of_span_and_out_of_order_entries_are_warnings():
    data = chapter()
    data["entries"][5]["start_year"] = -4500
    report = story.check(data)
    assert report.errors == []
    text = "\n".join(report.warnings)
    assert "entry 5: -4500..-4500 falls outside" in text
    assert "never re-date" in text
    assert "entry 5: starts before the entry above it" in text


def test_too_many_harari_mentions_warn():
    data = chapter()
    for e in data["entries"][:4]:
        e["narrative_text"] = NARRATIVE + " Yuval Noah Harari calls such shared stories imagined orders."
    assert any("name Harari" in w for w in story.check(data).warnings)


def test_names_agree():
    assert story.names_agree("Uruk", "Uruk (city)")
    assert story.names_agree("Sargon of Akkad", "sargon of akkad")
    assert not story.names_agree("Uruk", "Ur")
    assert not story.names_agree("", "Ur")


def test_chronicle_check_cli_without_db(tmp_path):
    d = tmp_path / "the-first-cities"
    d.mkdir()
    (d / "chronicle.json").write_text(json.dumps(chapter()))
    result = CliRunner().invoke(cli, ["chronicle-check", str(d / "chronicle.json"), "--no-db"])
    assert result.exit_code == 0, result.output
    assert "16 entries, 0 error(s), 0 warning(s)" in result.output

    bad = chapter(n=3)
    (d / "chronicle.json").write_text(json.dumps(bad))
    result = CliRunner().invoke(cli, ["chronicle-check", str(d / "chronicle.json"), "--no-db"])
    assert result.exit_code == 1
    assert "ERROR 3 entries" in result.output
