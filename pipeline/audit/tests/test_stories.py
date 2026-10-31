"""C8: story references (no network)."""
from pipeline.audit.stories import story_refs


def test_story_refs_by_kind():
    battle = {"kind": "battle", "entity": {"name": "Battle of Cannae", "wikidata": "Q13377"},
              "sides": [{"id": "rome", "polity": {"name": "Roman Republic", "wikidata": "Q17167"},
                         "commanders": [{"name": "Varro"}]}]}
    roles = [r["role"] for r in story_refs(battle)]
    assert roles == ["entity", "polity", "commander"]
    epidemic = {"kind": "epidemic", "entity": {"name": "Black Death", "wikidata": "Q42005"}}
    assert [r["role"] for r in story_refs(epidemic)] == ["subject"]
    chronicle = {"kind": "trade_route", "chronicle": {"slug": "indian-ocean-dhow-trade"}}
    assert story_refs(chronicle) == []


def test_story_span_uses_the_period():
    from pipeline.audit.stories import era_ok, story_span
    assert story_span({"year": -216}) == (-216, -216)
    hansa = {"year": 1241, "period": {"start": {"year": 1241}, "end": {"year": 1598}}}
    assert story_span(hansa) == (1241, 1598)
    league = {"dates": {"P571": [1358, 9], "P576": [1862, 11]}}
    assert era_ok("political_entity", league, story_span(hansa))[0] is True
    assert era_ok("political_entity", league, (1241, 1241))[0] is False
