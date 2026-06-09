import pytest
from unittest.mock import patch, MagicMock

from pipeline.agent.tools.db import search_entity_by_name


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
