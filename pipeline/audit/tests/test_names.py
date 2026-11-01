"""C5 name normalisation."""
from collections import Counter

from pipeline.audit.names import conventions, dominant, mechanical_rename, name_issues
from pipeline.audit.tests.conftest import make_row

CONV = {"epithet_article": Counter({"the": 141}), "era_suffix": Counter({"BCE": 76, "CE": 47})}


def test_whitespace_and_quotes():
    assert mechanical_rename("  Battle  of Zama ", "event_battle", CONV) == ("Battle of Zama", ["whitespace"])
    assert mechanical_rename('"Hannibal"', "person", CONV)[0] == "Hannibal"


def test_battle_prefix():
    assert mechanical_rename("The Battle of Zama", "event_battle", CONV)[0] == "Battle of Zama"
    assert mechanical_rename("Siege Of Alesia", "event_battle", CONV)[0] == "Siege of Alesia"
    assert mechanical_rename("Battle of Zama", "event_battle", CONV) == ("Battle of Zama", [])
    # only battles
    assert mechanical_rename("The Battle of Zama", "cultural_work", CONV)[0] == "The Battle of Zama"


def test_epithet_article_only_when_lower_case_dominates():
    assert mechanical_rename("Alexander The Great", "person", CONV)[0] == "Alexander the Great"
    mixed = {"epithet_article": Counter({"the": 5, "The": 5})}
    assert mechanical_rename("Alexander The Great", "person", mixed)[0] == "Alexander The Great"


def test_era_suffix_follows_the_dominant_style():
    assert mechanical_rename("Battle of Salamis (306 BC)", "event_battle", CONV)[0] == "Battle of Salamis (306 BCE)"
    assert mechanical_rename("Revolt of AD 66", "event_rebellion", CONV)[0] == "Revolt of 66 CE"
    even = {"era_suffix": Counter({"BCE": 10, "BC": 10})}
    assert mechanical_rename("Battle of Salamis (306 BC)", "event_battle", even)[0] == "Battle of Salamis (306 BC)"


def test_dominant():
    assert dominant(Counter({"a": 95, "b": 5}), "a", "b") == "a"
    assert dominant(Counter({"a": 80, "b": 20}), "a", "b") is None
    assert dominant(Counter(), "a", "b") is None


def test_name_issues_report_and_collision():
    rows = [make_row("Battle  of Zama", "event_battle", id="a"), make_row("Battle of Zama", "event_battle", id="b"),
            make_row("Cleopatra (film)", "person", id="c"), make_row("NATO", "diplomatic_relationship", id="d"),
            make_row("al-Mansur", "person", id="e")]
    conv = conventions(rows)
    issues = {i["entity_id"]: i for i in name_issues(rows, conv)}
    assert issues["a"]["apply"] is False and "collides" in issues["a"]["note"]
    assert any("media disambiguator" in x for x in issues["c"]["issues"])
    assert any("all caps" in x for x in issues["d"]["issues"]) and not issues["d"]["apply"]
    assert "e" not in issues  # Arabic article is not a lower-case-first problem
