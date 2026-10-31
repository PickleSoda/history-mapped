import pytest

from pipeline.ohm_borders.fetcher import OVERPASS_URL
from pipeline.ohm_links.fetcher import (
    BOUNDARIES_QUERY,
    PLACES_WITH_WIKIDATA_QUERY,
    fetch_elements,
    ids_queries,
    read_ids_file,
)


class _StubResponse:
    def __init__(self, payload):
        self._payload = payload
        self.raise_for_status_called = False

    def raise_for_status(self):
        self.raise_for_status_called = True

    def json(self):
        return self._payload


def test_boundaries_query_is_tags_only_admin_relations():
    assert BOUNDARIES_QUERY == '[out:json][timeout:1800];relation["boundary"="administrative"];out tags;'


def test_places_query_is_tags_only_places_with_wikidata():
    assert PLACES_WITH_WIKIDATA_QUERY == (
        '[out:json][timeout:1800];('
        'node["place"]["wikidata"];way["place"]["wikidata"];relation["place"]["wikidata"];'
        ');out tags;'
    )


def test_ids_queries_groups_ids_by_type_in_one_query():
    ids = [("relation", 4), ("node", 2), ("way", 3), ("node", 1)]

    assert list(ids_queries(ids)) == [
        "[out:json][timeout:600];(node(id:1,2);way(id:3);relation(id:4););out tags;",
    ]


def test_ids_queries_splits_into_batches_and_drops_duplicates():
    ids = [("node", 1), ("node", 2), ("node", 2), ("way", 3), ("relation", 4), ("relation", 5)]

    assert list(ids_queries(ids, batch_size=2)) == [
        "[out:json][timeout:600];(node(id:1,2););out tags;",
        "[out:json][timeout:600];(way(id:3);relation(id:4););out tags;",
        "[out:json][timeout:600];(relation(id:5););out tags;",
    ]


def test_ids_queries_yields_nothing_for_no_ids():
    assert list(ids_queries([])) == []


def test_ids_queries_rejects_unknown_type_and_bad_batch_size():
    with pytest.raises(ValueError):
        list(ids_queries([("feature", 1)]))
    with pytest.raises(ValueError):
        list(ids_queries([("node", 1)], batch_size=0))


def test_fetch_elements_posts_query_to_overpass_and_returns_elements():
    calls = []
    response = _StubResponse({"version": 0.6, "elements": [{"type": "node", "id": 1, "tags": {"name": "x"}}]})

    def stub_post(url, **kwargs):
        calls.append((url, kwargs))
        return response

    elements = fetch_elements(BOUNDARIES_QUERY, post=stub_post)

    assert elements == [{"type": "node", "id": 1, "tags": {"name": "x"}}]
    assert len(calls) == 1
    url, kwargs = calls[0]
    assert url == OVERPASS_URL
    assert kwargs["data"] == {"data": BOUNDARIES_QUERY}
    assert kwargs["timeout"] == 1800
    assert response.raise_for_status_called


def test_fetch_elements_raises_on_overpass_runtime_error_remark():
    def stub_post(url, **kwargs):
        return _StubResponse(
            {"elements": [], "remark": 'runtime error: Query timed out in "query" at line 1 after 1801 seconds.'}
        )

    with pytest.raises(RuntimeError, match="Query timed out"):
        fetch_elements(BOUNDARIES_QUERY, post=stub_post)


def test_read_ids_file_parses_type_slash_id_lines(tmp_path):
    path = tmp_path / "ids.txt"
    path.write_text("node/42\n\nrelation/1880\nfeature/7\nnot-an-id\nway/3\n", encoding="utf-8")

    assert read_ids_file(path) == [("node", 42), ("relation", 1880), ("way", 3)]
