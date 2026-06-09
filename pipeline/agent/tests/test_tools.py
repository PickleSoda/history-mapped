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
