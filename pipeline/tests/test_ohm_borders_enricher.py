from unittest.mock import Mock, patch

from pipeline.ohm_borders.enricher import _build_sparql_query, batch_enrich_qids, search_qid_by_name


def test_build_sparql_query_includes_qids() -> None:
    query = _build_sparql_query(["Q1", "Q2"])
    assert "wd:Q1" in query
    assert "wd:Q2" in query


def _mock_sparql_result(qid: str, label: str) -> dict:
    return {
        "polity": {"value": f"http://www.wikidata.org/entity/{qid}"},
        "polityLabel": {"value": label},
        "polityDescription": {"value": "A historic state"},
        "altLabel": {"value": "AltName"},
        "inception": {"value": "1908-01-01T00:00:00Z"},
        "dissolution": {"value": "1946-01-01T00:00:00Z"},
    }


def test_batch_enrich_returns_keyed_by_qid() -> None:
    mock_results = [_mock_sparql_result("Q219", "Kingdom of Bulgaria")]
    with patch("pipeline.ohm_borders.enricher._sparql_query") as mock_q:
        mock_q.return_value = mock_results
        result = batch_enrich_qids(["Q219"])
    assert "Q219" in result
    assert result["Q219"]["name_en"] == "Kingdom of Bulgaria"
    assert result["Q219"]["temporal_start"] == "1908"


def test_batch_enrich_returns_empty_on_missing_qid() -> None:
    with patch("pipeline.ohm_borders.enricher._sparql_query") as mock_q:
        mock_q.return_value = []
        result = batch_enrich_qids(["Q99999999"])
    assert result == {}


def test_batch_size_splits_large_list() -> None:
    qids = [f"Q{i}" for i in range(120)]
    with patch("pipeline.ohm_borders.enricher._sparql_query") as mock_q:
        mock_q.return_value = []
        batch_enrich_qids(qids, batch_size=50)
        assert mock_q.call_count == 3


def test_search_qid_by_name_accepts_string_match_text_payload() -> None:
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "search": [
            {
                "id": "Q12548",
                "label": "Holy Roman Empire",
                "description": "historical polity in Central Europe",
                "match": {
                    "type": "label",
                    "language": "en",
                    "text": "Holy Roman Empire",
                },
            }
        ]
    }

    with patch("pipeline.ohm_borders.enricher.requests.get", return_value=response):
        assert search_qid_by_name("Holy Roman Empire") == "Q12548"
