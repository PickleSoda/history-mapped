import json
from pathlib import Path

from pipeline.ohm_collections.collection_builder import build_collection_artifacts


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


def _base_candidate(name: str, entity_type: str) -> dict:
    return {
        "name": name,
        "wikidata_id": None,
        "entity_types": [entity_type],
        "alternative_names": [],
        "summary": None,
        "raw_tags": {},
        "_ohm_object_type": "node",
        "_ohm_object_id": 1,
        "decision": {"reasons": ["lexical_match"], "ambiguity": []},
        "point_resolution": {"status": "no_point", "geometry_source": "none", "point": None},
        "fallback_geojson": None,
    }


def test_build_collection_artifacts_routes_relation_backed_polities_to_border_outputs(tmp_path: Path) -> None:
    output_root = tmp_path / "egypt-run"
    candidate = _base_candidate("Kingdom of Egypt", "political_entity")
    candidate["border_record"] = {
        "name": "Kingdom of Egypt",
        "entity_type": "political_entity",
        "wikidata_id": "Q456",
        "_ohm_relation_id": "300",
        "_geometry_periods": [],
    }
    candidate["point_resolution"] = {
        "status": "resolved",
        "geometry_source": "ohm_representative_point",
        "point": {"type": "Point", "coordinates": [31.2, 29.8]},
    }

    build_collection_artifacts([candidate], output_root=output_root)

    border_records = _read_jsonl(output_root / "borders_final" / "ohm_borders.jsonl")
    entity_records = _read_jsonl(output_root / "entities_final" / "egypt_collection.jsonl")

    assert [(record["name"], record["_ohm_relation_id"]) for record in border_records] == [
        ("Kingdom of Egypt", "300"),
    ]
    assert entity_records == []


def test_build_collection_artifacts_routes_point_only_candidates_to_generic_entity_output(tmp_path: Path) -> None:
    output_root = tmp_path / "egypt-run"
    candidate = _base_candidate("Ancient Memphis", "city")
    candidate["point_resolution"] = {
        "status": "resolved",
        "geometry_source": "ohm_point",
        "point": {"type": "Point", "coordinates": [31.205, 29.871]},
    }

    build_collection_artifacts([candidate], output_root=output_root)

    entity_records = _read_jsonl(output_root / "entities_final" / "egypt_collection.jsonl")

    assert [
        (
            record["name"],
            record["entity_type"],
            record["entity_group"],
            record["verification_status"],
            record["confidence"],
            record["geojson"],
            record["_geometry_source"],
        )
        for record in entity_records
    ] == [
        (
            "Ancient Memphis",
            "city",
            "PLACE",
            "pipeline_draft",
            "medium",
            {"type": "Point", "coordinates": [31.205, 29.871]},
            "ohm_point",
        ),
    ]


def test_build_collection_artifacts_uses_fallback_geojson_when_no_ohm_point_exists(tmp_path: Path) -> None:
    output_root = tmp_path / "egypt-run"
    candidate = _base_candidate("Late Period of Egypt", "historical_period")
    candidate["fallback_geojson"] = {"type": "Point", "coordinates": [30.0, 26.5]}

    build_collection_artifacts([candidate], output_root=output_root)

    entity_records = _read_jsonl(output_root / "entities_final" / "egypt_collection.jsonl")

    assert [
        (
            record["name"],
            record["entity_type"],
            record["entity_group"],
            record["attributes"]["collection_entity_type"],
            record["geojson"],
            record["_geometry_source"],
        )
        for record in entity_records
    ] == [
        (
            "Late Period of Egypt",
            "political_entity",
            "POLITY",
            "historical_period",
            {"type": "Point", "coordinates": [30.0, 26.5]},
            "pipeline_geojson",
        ),
    ]


def test_build_collection_artifacts_uses_ohm_points_for_events_and_fallback_points_for_wars(tmp_path: Path) -> None:
    output_root = tmp_path / "egypt-run"
    battle = _base_candidate("Battle of Kadesh", "battle")
    battle["point_resolution"] = {
        "status": "resolved",
        "geometry_source": "ohm_point",
        "point": {"type": "Point", "coordinates": [36.0, 34.5]},
    }
    war = _base_candidate("Egyptian-Hittite War", "war")
    war["fallback_geojson"] = {"type": "Point", "coordinates": [35.1, 33.9]}

    build_collection_artifacts([battle, war], output_root=output_root)

    entity_records = _read_jsonl(output_root / "entities_final" / "egypt_collection.jsonl")

    assert [(record["name"], record["entity_type"], record["entity_group"], record["geojson"], record["_geometry_source"]) for record in entity_records] == [
        ("Battle of Kadesh", "event_battle", "EVENT", {"type": "Point", "coordinates": [36.0, 34.5]}, "ohm_point"),
        ("Egyptian-Hittite War", "event_war", "EVENT", {"type": "Point", "coordinates": [35.1, 33.9]}, "pipeline_geojson"),
    ]


def test_build_collection_artifacts_preserves_relation_source_metadata_for_later_relation_runs(tmp_path: Path) -> None:
    output_root = tmp_path / "egypt-run"
    candidate = _base_candidate("Kingdom of Egypt", "political_entity")
    candidate["wikidata_id"] = "Q456"
    candidate["raw_tags"] = {
        "name": "Kingdom of Egypt",
        "wikidata": "Q456",
        "predecessor": "Old Kingdom of Egypt",
        "predecessor:wikidata": "Q123",
    }
    candidate["_ohm_object_type"] = "relation"
    candidate["_ohm_object_id"] = 300
    candidate["border_record"] = {
        "name": "Kingdom of Egypt",
        "entity_type": "political_entity",
        "entity_group": "POLITY",
        "wikidata_id": "Q456",
        "_ohm_relation_id": "300",
        "_geometry_periods": [],
    }

    build_collection_artifacts([candidate], output_root=output_root)

    included_records = _read_jsonl(output_root / "reports" / "included.jsonl")

    assert included_records == [
        {
            "name": "Kingdom of Egypt",
            "wikidata_id": "Q456",
            "entity_types": ["political_entity"],
            "reasons": ["lexical_match"],
            "ambiguity": [],
            "geometry_source": "none",
            "raw_tags": {
                "name": "Kingdom of Egypt",
                "wikidata": "Q456",
                "predecessor": "Old Kingdom of Egypt",
                "predecessor:wikidata": "Q123",
            },
            "_ohm_object_type": "relation",
            "_ohm_object_id": 300,
        }
    ]


def test_build_collection_artifacts_records_geometry_sources_and_reports(tmp_path: Path) -> None:
    output_root = tmp_path / "egypt-run"
    border_candidate = _base_candidate("Kingdom of Egypt", "political_entity")
    border_candidate["border_record"] = {
        "name": "Kingdom of Egypt",
        "entity_type": "political_entity",
        "entity_group": "POLITY",
        "wikidata_id": "Q456",
        "_ohm_relation_id": "300",
        "_geometry_periods": [],
    }
    border_candidate["point_resolution"] = {
        "status": "resolved",
        "geometry_source": "ohm_representative_point",
        "point": {"type": "Point", "coordinates": [31.2, 29.8]},
    }

    point_candidate = _base_candidate("Ancient Memphis", "city")
    point_candidate["point_resolution"] = {
        "status": "resolved",
        "geometry_source": "ohm_point",
        "point": {"type": "Point", "coordinates": [31.205, 29.871]},
    }

    fallback_candidate = _base_candidate("Late Period of Egypt", "historical_period")
    fallback_candidate["fallback_geojson"] = {"type": "Point", "coordinates": [30.0, 26.5]}

    no_geometry_candidate = _base_candidate("Lost Delta Shrine", "place")

    excluded_candidate = _base_candidate("Egypt-adjacent Trade Token", "currency")
    excluded_candidate["decision"] = {
        "reasons": ["weak_incidental_match"],
        "ambiguity": ["summary_only_egypt_reference"],
    }

    manifest = build_collection_artifacts(
        [border_candidate, point_candidate, fallback_candidate, no_geometry_candidate],
        excluded_candidates=[excluded_candidate],
        output_root=output_root,
    )

    included_records = _read_jsonl(output_root / "reports" / "included.jsonl")
    excluded_records = _read_jsonl(output_root / "reports" / "excluded.jsonl")

    assert manifest["geometry_sources"] == {
        "ohm_point": 1,
        "ohm_representative_point": 1,
        "pipeline_geojson": 1,
        "none": 1,
    }
    assert manifest["counts"] == {"included": 4, "excluded": 1, "border_records": 1, "entity_records": 3}
    assert [(record["name"], record["geometry_source"], record["wikidata_id"]) for record in included_records] == [
        ("Kingdom of Egypt", "ohm_representative_point", None),
        ("Ancient Memphis", "ohm_point", None),
        ("Late Period of Egypt", "pipeline_geojson", None),
        ("Lost Delta Shrine", "none", None),
    ]
    assert excluded_records == [
        {
            "name": "Egypt-adjacent Trade Token",
            "entity_types": ["currency"],
            "reasons": ["weak_incidental_match"],
            "ambiguity": ["summary_only_egypt_reference"],
        }
    ]