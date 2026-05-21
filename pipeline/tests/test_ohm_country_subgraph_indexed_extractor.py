import json
from pathlib import Path

import pytest

import pipeline.ohm_borders.subgraph_extractor as subgraph_module
from pipeline.ohm_borders.index_builder import build_index
from pipeline.ohm_borders.subgraph_extractor import (
    SeedResolutionError,
    extract_country_subgraph,
    extract_country_subgraph_from_index,
)
from pipeline.tests.test_ohm_country_subgraph_extractor import _fixture_overpass


def _write_fixture(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_extract_country_subgraph_from_index_resolves_qid_and_normalized_name_equivalently(tmp_path: Path) -> None:
    source_path = tmp_path / "overpass.json"
    index_path = tmp_path / "overpass.sqlite3"
    _write_fixture(source_path, _fixture_overpass())
    build_index(source_path, index_path=index_path)

    qid_result = extract_country_subgraph_from_index(
        index_path,
        seed_qid="Q1",
        max_depth=1,
        max_nodes=10,
    )
    normalized_name_result = extract_country_subgraph_from_index(
        index_path,
        seed_name="  roman   empire  ",
        max_depth=1,
        max_nodes=10,
    )

    assert qid_result["seed"]["relation_ids"] == normalized_name_result["seed"]["relation_ids"]
    assert qid_result["closure_report"]["included_relation_ids"] == [100, 101, 102, 200, 300]


def test_extract_country_subgraph_from_index_returns_fuzzy_suggestions_non_interactively(tmp_path: Path) -> None:
    source_path = tmp_path / "overpass.json"
    index_path = tmp_path / "overpass.sqlite3"
    _write_fixture(source_path, _fixture_overpass())
    build_index(source_path, index_path=index_path)

    with pytest.raises(SeedResolutionError, match="Roman Empire"):
        extract_country_subgraph_from_index(
            index_path,
            seed_name="roman empyre",
            max_depth=1,
            max_nodes=10,
        )


def test_extract_country_subgraph_from_index_allows_explicit_auto_select_fuzzy(tmp_path: Path) -> None:
    payload = _fixture_overpass()
    payload["elements"].append(
        {
            "type": "relation",
            "id": 700,
            "tags": {
                "boundary": "administrative",
                "admin_level": "2",
                "name": "Roman Empyre",
                "wikidata": "Q70",
            },
            "members": [],
        }
    )
    source_path = tmp_path / "overpass.json"
    index_path = tmp_path / "overpass.sqlite3"
    _write_fixture(source_path, payload)
    build_index(source_path, index_path=index_path)

    result = extract_country_subgraph_from_index(
        index_path,
        seed_name="roman empire",
        max_depth=1,
        max_nodes=10,
        auto_select_fuzzy=True,
    )

    assert result["seed"]["wikidata_id"] == "Q1"


def test_extract_country_subgraph_from_index_matches_known_raw_payload_result(tmp_path: Path) -> None:
    payload = _fixture_overpass()
    source_path = tmp_path / "overpass.json"
    index_path = tmp_path / "overpass.sqlite3"
    _write_fixture(source_path, payload)
    build_index(source_path, index_path=index_path)

    indexed_result = extract_country_subgraph_from_index(
        index_path,
        seed_qid="Q1",
        max_depth=1,
        max_nodes=10,
    )
    raw_result = extract_country_subgraph(
        payload,
        seed_qid="Q1",
        max_depth=1,
        max_nodes=10,
    )

    assert indexed_result["closure_report"]["included_relation_ids"] == raw_result["closure_report"]["included_relation_ids"]
    assert indexed_result["graph_edges"] == raw_result["graph_edges"]


def test_extract_country_subgraph_from_index_avoids_full_graph_reconstruction(tmp_path: Path, monkeypatch) -> None:
    payload = _fixture_overpass()
    source_path = tmp_path / "overpass.json"
    index_path = tmp_path / "overpass.sqlite3"
    _write_fixture(source_path, payload)
    build_index(source_path, index_path=index_path)

    def fail_indexed_graph(*args, **kwargs):
        raise AssertionError("full graph reconstruction should not be used for indexed extraction")

    monkeypatch.setattr(subgraph_module, "_indexed_graph", fail_indexed_graph, raising=False)

    result = extract_country_subgraph_from_index(
        index_path,
        seed_qid="Q1",
        max_depth=1,
        max_nodes=10,
    )

    assert result["closure_report"]["included_relation_ids"] == [100, 101, 102, 200, 300]


class _RecordingConnection:
    class _Cursor:
        def __init__(self, rows: list[tuple]) -> None:
            self._rows = rows

        def fetchall(self) -> list[tuple]:
            return self._rows

    def __init__(self, responses: dict[str, list[tuple]]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, tuple]] = []

    def execute(self, query: str, params: tuple):
        self.calls.append((query, params))
        return self._Cursor(self._responses.get(params[0], []))


def test_fuzzy_seed_candidates_uses_bounded_three_character_prefix_query_when_available() -> None:
    connection = _RecordingConnection(
        {
            "rom%": [
                (100, "Roman Empire", "roman empire", "Q1"),
                (700, "Roman Empiree", "roman empiree", "Q70"),
            ]
        }
    )

    candidates = subgraph_module._fuzzy_seed_candidates_from_connection(
        connection,
        "roman empire",
        limit=5,
        minimum_score=0.85,
    )

    assert [candidate["name"] for candidate in candidates] == ["Roman Empire", "Roman Empiree"]
    assert len(connection.calls) == 1
    assert connection.calls[0][1] == ("rom%", 1000)
    assert "LIKE ?" in connection.calls[0][0]
    assert "LIMIT ?" in connection.calls[0][0]


def test_fuzzy_seed_candidates_falls_back_to_two_character_prefix_and_caps_results() -> None:
    two_char_rows = [
        (index, f"Rom Candidate {index:04d}", f"rom candidate {index:04d}", f"Q{index}")
        for index in range(1005)
    ]
    connection = _RecordingConnection({"rom%": [], "ro%": two_char_rows})

    candidates = subgraph_module._fuzzy_seed_candidates_from_connection(
        connection,
        "rom candidate 0001",
        limit=5,
        minimum_score=0.0,
    )

    assert len(connection.calls) == 2
    assert connection.calls[0][1] == ("rom%", 1000)
    assert connection.calls[1][1] == ("ro%", 1000)
    assert len(candidates) == 5


def test_extract_country_subgraph_from_index_normalizes_nfc_casefold_and_whitespace_for_fuzzy_seed_names(tmp_path: Path) -> None:
    payload = _fixture_overpass()
    payload["elements"].append(
        {
            "type": "relation",
            "id": 710,
            "tags": {
                "boundary": "administrative",
                "admin_level": "2",
                "name": "Cafe\u0301 Empire",
                "wikidata": "Q710",
            },
            "members": [],
        }
    )
    source_path = tmp_path / "overpass.json"
    index_path = tmp_path / "overpass.sqlite3"
    _write_fixture(source_path, payload)
    build_index(source_path, index_path=index_path)

    result = extract_country_subgraph_from_index(
        index_path,
        seed_name="  CAF\u00c9   empire  ",
        max_depth=0,
        max_nodes=10,
    )

    assert result["seed"]["relation_ids"] == [710]