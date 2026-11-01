import pytest
import requests

from pipeline.ohm_borders.fetcher import OVERPASS_URL
from pipeline.ohm_links.fetcher import (
    BOUNDARIES_QUERY,
    PLACES_WITH_WIKIDATA_QUERY,
    fetch_elements,
    id_batches,
    ids_queries,
    read_ids_file,
)


class _StubResponse:
    def __init__(self, payload=None, status_code=200):
        self._payload = payload if payload is not None else {}
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)

    def json(self):
        return self._payload


def _scripted_post(outcomes):
    """A stub `requests.post` that plays back responses/exceptions in order and records calls."""
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        outcome = outcomes[min(len(calls), len(outcomes)) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return post, calls


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


def test_id_batches_are_the_sorted_unique_ids_behind_each_query():
    ids = [("relation", 4), ("node", 2), ("node", 2), ("way", 3)]

    assert list(id_batches(ids, batch_size=2)) == [[("node", 2), ("way", 3)], [("relation", 4)]]


def test_ids_queries_yields_nothing_for_no_ids():
    assert list(ids_queries([])) == []


def test_ids_queries_rejects_unknown_type_and_bad_batch_size():
    with pytest.raises(ValueError):
        list(ids_queries([("feature", 1)]))
    with pytest.raises(ValueError):
        list(ids_queries([("node", 1)], batch_size=0))


def test_fetch_elements_posts_query_to_overpass_and_returns_elements():
    elements = [{"type": "node", "id": 1, "tags": {"name": "x"}}]
    post, calls = _scripted_post([_StubResponse({"version": 0.6, "elements": elements})])

    assert fetch_elements(BOUNDARIES_QUERY, post=post, sleep=lambda seconds: None) == elements
    assert len(calls) == 1
    url, kwargs = calls[0]
    assert url == OVERPASS_URL
    assert kwargs["data"] == {"data": BOUNDARIES_QUERY}
    assert kwargs["timeout"] == 1800


def test_fetch_elements_retries_503_and_timeout_with_backoff_then_succeeds():
    elements = [{"type": "relation", "id": 1880, "tags": {"name": "x"}}]
    post, calls = _scripted_post(
        [
            _StubResponse(status_code=503),
            requests.Timeout("read timed out"),
            _StubResponse({"elements": elements}),
        ]
    )
    sleeps = []

    assert fetch_elements(BOUNDARIES_QUERY, post=post, sleep=sleeps.append) == elements
    assert len(calls) == 3
    assert sleeps == [10, 20]


def test_fetch_elements_retries_429_connection_error_and_runtime_error_remark():
    post, calls = _scripted_post(
        [
            _StubResponse(status_code=429),
            requests.ConnectionError("reset by peer"),
            _StubResponse({"elements": [], "remark": "runtime error: Query timed out in \"query\" at line 1"}),
            _StubResponse({"elements": []}),
        ]
    )

    assert fetch_elements(BOUNDARIES_QUERY, post=post, sleep=lambda seconds: None) == []
    assert len(calls) == 4


def test_fetch_elements_raises_after_last_attempt_when_overpass_keeps_failing():
    post, calls = _scripted_post([_StubResponse(status_code=503)])
    sleeps = []

    with pytest.raises(RuntimeError, match="503"):
        fetch_elements(BOUNDARIES_QUERY, post=post, sleep=sleeps.append)

    assert len(calls) == 5
    assert sleeps == [10, 20, 40, 80]


def test_fetch_elements_caps_backoff_delay():
    post, _calls = _scripted_post([requests.Timeout("slow")])
    sleeps = []

    with pytest.raises(requests.Timeout):
        fetch_elements(BOUNDARIES_QUERY, post=post, sleep=sleeps.append, attempts=7)

    assert sleeps == [10, 20, 40, 80, 120, 120]


def test_fetch_elements_raises_runtime_error_remark_after_last_attempt():
    post, calls = _scripted_post(
        [_StubResponse({"elements": [], "remark": 'runtime error: Query timed out in "query" at line 1 after 1801 seconds.'})]
    )

    with pytest.raises(RuntimeError, match="Query timed out"):
        fetch_elements(BOUNDARIES_QUERY, post=post, sleep=lambda seconds: None)

    assert len(calls) == 5


def test_fetch_elements_does_not_retry_other_client_errors():
    post, calls = _scripted_post([_StubResponse(status_code=400)])

    with pytest.raises(requests.HTTPError):
        fetch_elements(BOUNDARIES_QUERY, post=post, sleep=lambda seconds: None)

    assert len(calls) == 1


def test_read_ids_file_parses_type_slash_id_lines(tmp_path):
    path = tmp_path / "ids.txt"
    path.write_text("node/42\n\nrelation/1880\nfeature/7\nnot-an-id\nway/3\n", encoding="utf-8")

    assert read_ids_file(path) == [("node", 42), ("relation", 1880), ("way", 3)]
