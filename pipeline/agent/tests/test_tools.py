import pytest
from unittest.mock import patch, MagicMock

from pipeline.agent.tools.db import search_entity_by_name
from pipeline.agent.tools.wikidata import search_wikidata_by_name, enrich_wikidata_entities


@patch("pipeline.agent.tools.db._get_db_connection")
def test_db_search_returns_list(mock_conn):
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        ("E123", "David IV of Georgia", "person", "Q405"),
    ]
    mock_conn.return_value.__enter__ = MagicMock(return_value=mock_conn.return_value)
    mock_conn.return_value.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.return_value.cursor.return_value.__exit__ = MagicMock(return_value=False)

    results = search_entity_by_name("David IV", entity_type="person")
    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0]["wikidata_id"] == "Q405"


@patch("pipeline.agent.tools.wikidata._query_sparql")
def test_wikidata_search(mock_query):
    mock_query.return_value = {
        "results": {
            "bindings": [
                {"item": {"value": "http://www.wikidata.org/entity/Q405"}, "itemLabel": {"value": "David IV of Georgia"}, "itemDescription": {"value": "King of Georgia"}}
            ]
        }
    }
    results = search_wikidata_by_name("David IV of Georgia")
    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0]["qid"] == "Q405"


@patch("pipeline.agent.tools.wikidata._query_sparql")
def test_wikidata_enrich(mock_query):
    mock_query.return_value = {
        "results": {
            "bindings": [
                {"item": {"value": "http://www.wikidata.org/entity/Q405"}, "itemLabel": {"value": "David IV"}, "itemDescription": {"value": "King"}}
            ]
        }
    }
    results = enrich_wikidata_entities(["Q405"])
    assert "Q405" in results
    assert results["Q405"]["label"] == "David IV"


from pipeline.agent.tools.wikipedia import fetch_wikipedia_summary


@patch("pipeline.agent.tools.wikipedia.requests.get")
def test_wikipedia_fetch(mock_get):
    mock_get.return_value = MagicMock(
        json=lambda: {
            "query": {"pages": {"1": {"extract": "David IV was a king.", "title": "David IV of Georgia"}}}
        },
        raise_for_status=lambda: None,
    )
    result = fetch_wikipedia_summary("David IV of Georgia")
    assert result is not None
    assert "king" in result.get("extract", "").lower()
    assert result["url"] == "https://en.wikipedia.org/wiki/David_IV_of_Georgia"


from pipeline.agent.tools.ohm import search_ohm_by_name, search_ohm_by_wikidata_id, resolve_ohm_geometry


@patch("pipeline.agent.tools.ohm.find_objects_by_name")
def test_ohm_search_name(mock_find):
    mock_find.return_value = [{"object_type": "node", "object_id": 123, "name": "Didgori"}]
    results = search_ohm_by_name("Didgori", "test.db")
    assert len(results) == 1
    assert results[0]["name"] == "Didgori"


@patch("pipeline.agent.tools.ohm.find_objects_by_wikidata_id")
def test_ohm_search_qid(mock_find):
    mock_find.return_value = [{"object_type": "way", "object_id": 456, "wikidata_id": "Q12345"}]
    results = search_ohm_by_wikidata_id("Q12345", "test.db")
    assert len(results) == 1


@patch("pipeline.agent.tools.ohm.resolve_best_point")
def test_ohm_geometry(mock_resolve):
    mock_resolve.return_value = {"type": "Point", "coordinates": [44.5, 41.7]}
    geo = resolve_ohm_geometry("test.db", "node", 123)
    assert geo is not None
    assert geo["type"] == "Point"


from pipeline.agent.tools.app_api import build_artisan_command, run_artisan_command


def test_build_import_command():
    cmd = build_artisan_command("pipeline:import", "/tmp/test.jsonl", sync=True, batch_id="run_123")
    assert "pipeline:import" in cmd
    assert "/tmp/test.jsonl" in cmd
    assert "--sync" in cmd
    assert "--batch-id=run_123" in cmd
    assert cmd[0] == "docker"


def test_build_borders_command():
    cmd = build_artisan_command("pipeline:import-borders", "/tmp/borders.jsonl", sync=True)
    assert "pipeline:import-borders" in cmd
    assert "--sync" in cmd
