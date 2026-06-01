import json
from pathlib import Path

from pipeline.ohm_collections.point_resolver import resolve_best_point
from pipeline.ohm_collections.xml_index_store import (
    initialize_index_schema,
    insert_objects,
    insert_relation_members,
    insert_way_node_refs,
)


def _seed_point_index(db_path: Path) -> None:
    initialize_index_schema(db_path)
    insert_objects(
        db_path,
        [
            ("node", 1, None, None, None, json.dumps({}), 0.0, 0.0),
            ("node", 2, None, None, None, json.dumps({}), 0.0, 4.0),
            ("node", 3, None, None, None, json.dumps({}), 4.0, 4.0),
            ("node", 4, None, None, None, json.dumps({}), 4.0, 0.0),
            (
                "node",
                100,
                "Ancient Memphis",
                "ancient memphis",
                "Q123",
                json.dumps({"name": "Ancient Memphis", "wikidata": "Q123"}),
                29.871,
                31.205,
            ),
            (
                "way",
                10,
                "Memphis Boundary",
                "memphis boundary",
                "QBOUNDARY",
                json.dumps({"name": "Memphis Boundary", "wikidata": "QBOUNDARY"}),
                None,
                None,
            ),
            (
                "way",
                11,
                "Broken Boundary",
                "broken boundary",
                None,
                json.dumps({"name": "Broken Boundary"}),
                None,
                None,
            ),
            (
                "relation",
                20,
                "Egyptian Territory",
                "egyptian territory",
                "QREL",
                json.dumps({"name": "Egyptian Territory", "wikidata": "QREL"}),
                None,
                None,
            ),
        ],
    )
    insert_way_node_refs(db_path, [(10, 0, 1), (10, 1, 2), (10, 2, 3), (10, 3, 4), (10, 4, 1), (11, 0, 900)])
    insert_relation_members(db_path, [(20, 0, "way", 10, "outer")])


def test_resolve_best_point_returns_direct_node_coordinates(tmp_path: Path) -> None:
    db_path = tmp_path / "ohm-xml-index.sqlite3"
    _seed_point_index(db_path)

    result = resolve_best_point(db_path, object_type="node", object_id=100)

    assert result == {
        "status": "resolved",
        "geometry_source": "ohm_point",
        "point": {"type": "Point", "coordinates": [31.205, 29.871]},
    }


def test_resolve_best_point_returns_representative_point_for_way_geometry(tmp_path: Path) -> None:
    db_path = tmp_path / "ohm-xml-index.sqlite3"
    _seed_point_index(db_path)

    result = resolve_best_point(db_path, object_type="way", object_id=10)

    assert result == {
        "status": "resolved",
        "geometry_source": "ohm_representative_point",
        "point": {"type": "Point", "coordinates": [2.0, 2.0]},
    }


def test_resolve_best_point_returns_representative_point_for_relation_geometry(tmp_path: Path) -> None:
    db_path = tmp_path / "ohm-xml-index.sqlite3"
    _seed_point_index(db_path)

    result = resolve_best_point(db_path, object_type="relation", object_id=20)

    assert result == {
        "status": "resolved",
        "geometry_source": "ohm_representative_point",
        "point": {"type": "Point", "coordinates": [2.0, 2.0]},
    }


def test_resolve_best_point_returns_no_point_for_missing_geometry(tmp_path: Path) -> None:
    db_path = tmp_path / "ohm-xml-index.sqlite3"
    _seed_point_index(db_path)

    result = resolve_best_point(db_path, object_type="way", object_id=11)

    assert result == {
        "status": "no_point",
        "geometry_source": "none",
        "point": None,
        "reason": "missing_geometry",
    }