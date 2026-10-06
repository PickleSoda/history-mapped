import json

import pytest

from pipeline.campaign import wiki
from pipeline.campaign.labels import ambiguous_label, regnal_parts
from pipeline.campaign.tests.conftest import SLUG, read


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    """Empty wiki cache under tmp, and any live Wikipedia request fails the test."""
    monkeypatch.setenv("CAMPAIGN_ROOT", str(tmp_path))

    def no_network(params):
        raise AssertionError(f"ambiguous-label must never hit the network: {params}")

    monkeypatch.setattr(wiki, "_http_get", no_network)


def _cache_page(label, title, extract):
    path = wiki._cache_file("page", label)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"query": {"pages": [{"title": title, "extract": extract}]}}), encoding="utf-8")


# ── detection ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("label", [
    "Philip II", "Louis II", "Charles V", "Charles VI", "Henry VI", "Otto I", "Frederick II",
    "Leo I", "Antiochus I", "Bolesław II", "Louis the Second",
    "al-Mustansir", "Al-Muqtadir", "al-Mu'tadid", "an-Nasir",
    "Emperor Wu", "Taizong", "Emperor Gaozu",
])
def test_bare_shared_regnal_names_warn(label):
    why = ambiguous_label(label, "person")
    assert why and "English Wikipedia title" in why and "Philip II of Spain" in why
    assert f"handoff rename RUN {label!r}" in why


@pytest.mark.parametrize("label", [
    # qualified the way English Wikipedia titles them
    "Philip II of Spain", "Philip II of Macedon", "Louis II of Italy", "Charles V, Holy Roman Emperor",
    "Charles V of France", "Emperor Wu of Han", "Emperor Taizong of Tang", "al-Mustansir Billah",
    # unique regnal names, famous primary titles, epithets, titles
    "Thutmose III", "Darius I", "Shapur I", "Louis XIV", "Henry VIII", "George III", "Charles XII",
    "Antiochus III the Great", "Michael VIII Palaiologos", "Frederick I Barbarossa", "Pope Leo III",
    "King George III", "Emperor Nintoku",
    # not regnal at all
    "al-Biruni", "al-Tabari", "Augustus", "Cleopatra VII", "Henry", "Philip",
])
def test_qualified_or_unique_labels_do_not_warn(label):
    assert ambiguous_label(label, "person") is None


def test_only_person_labels_are_checked():
    assert ambiguous_label("Philip II", "cultural_work") is None
    assert ambiguous_label("Philip II", None) is None


def test_regnal_parts():
    assert regnal_parts("Philip II") == ("philip", 2, False)
    assert regnal_parts("Louis the Second") == ("louis", 2, False)
    assert regnal_parts("Victor Emmanuel II") == ("victor emmanuel", 2, False)
    assert regnal_parts("Antiochus III the Great") == ("antiochus", 3, True)
    assert regnal_parts("Władysław III") == ("wladyslaw", 3, False)
    for label in ("Philip II of Spain", "Charles V, Holy Roman Emperor", "Pope Leo III", "Augustus",
                  "Abd al-Rahman III", "Xi Jinping"):
        assert regnal_parts(label) is None


# ── Wikipedia cache (read-only) ─────────────────────────────────────────────

def test_cached_disambiguation_page_warns_even_off_list():
    assert ambiguous_label("Darius II", "person") is None
    _cache_page("Darius II", "Darius II", "Darius II may refer to:\n\nDarius II of Persia ...")
    assert "disambiguation page" in ambiguous_label("Darius II", "person")


def test_cached_redirect_to_qualified_title_names_it():
    _cache_page("Hamilcar I", "Hamilcar I of Carthage", "Hamilcar I was a Magonid king of Carthage.")
    why = ambiguous_label("Hamilcar I", "person")
    assert "'Hamilcar I of Carthage'" in why and "wiki-search" not in why


def test_cached_article_titled_with_the_label_suppresses_the_list():
    _cache_page("Louis II", "Louis II", "Louis II was a king.")
    assert ambiguous_label("Louis II", "person") is None


def test_cached_unqualified_redirect_falls_back_to_the_list():
    _cache_page("Leo I", "Pope Leo I", "Pope Leo I was bishop of Rome.")
    assert ambiguous_label("Leo I", "person") is not None
    _cache_page("Darius I", "Darius the Great", "Darius I, commonly known as Darius the Great ...")
    assert ambiguous_label("Darius I", "person") is None


def test_unreadable_cache_is_ignored():
    path = wiki._cache_file("page", "Charles V")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    assert ambiguous_label("Charles V", "person") is not None


# ── CLI: add hint + check warning ───────────────────────────────────────────

BARE = {"label": "Philip II", "entity_type": "person", "start_date": "1527", "end_date": "1598",
        "source_event": None}


def test_add_prints_hint_but_writes_the_item(invoke, built):
    res = invoke("handoff", "add", SLUG, "entities", "-", input=json.dumps([BARE]))
    assert res.exit_code == 0, res.output
    assert "hint [0] Philip II: ambiguous-label: bare regnal name" in res.output
    assert "Philip II of Spain" in res.output
    assert "entities: added=1 updated=0 rejected=0" in res.output
    assert "Philip II" in [e["label"] for e in read(built)["candidate_entities"]]


def test_add_qualified_label_prints_no_hint(invoke, built):
    res = invoke("handoff", "add", SLUG, "entities", "-",
                 input=json.dumps([{**BARE, "label": "Philip II of Spain", "aliases": ["Philip II"]}]))
    assert res.exit_code == 0, res.output
    assert "hint" not in res.output and "ambiguous-label" not in res.output


def test_check_warns_ambiguous_label_without_failing(invoke, built):
    assert invoke("handoff", "check", SLUG).output.count("ambiguous-label") == 0
    invoke("handoff", "add", SLUG, "entities", "-", input=json.dumps([BARE]))
    invoke("handoff", "add", SLUG, "summaries", "-",
           input=json.dumps({"Philip II": {"summary": "King of Spain.", "significance": "Armada."}}))
    res = invoke("handoff", "check", SLUG)
    assert res.exit_code == 0, res.output
    assert "  ambiguous-label: entity 'Philip II': bare regnal name shared by several rulers" in res.output
    assert "OK: 0 error(s)" in res.output
    res = invoke("handoff", "rename", SLUG, "Philip II", "Philip II of Spain")
    assert res.exit_code == 0, res.output
    assert "ambiguous-label" not in invoke("handoff", "check", SLUG).output
