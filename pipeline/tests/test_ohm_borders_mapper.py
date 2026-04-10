from pipeline.ohm_borders.mapper import map_polity_to_jsonl

BASE_POLITY = {
    "relation_id": 100,
    "tags": {
        "name": "Testland",
        "name:en": "Testland (EN)",
        "wikidata": "Q999",
        "start_date": "1900",
        "end_date": "1950",
    },
    "stages": [
        {
            "relation_id": 100,
            "tags": {"start_date": "1900", "end_date": "1950"},
            "geometry": {"type": "MultiPolygon", "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 0]]]]},
        }
    ],
}

CHRON_POLITY = {
    "relation_id": 200,
    "tags": {"name": "Evolving State", "wikidata": "Q1000"},
    "stages": [
        {
            "relation_id": 201,
            "tags": {"start_date": "1800", "end_date": "1850"},
            "geometry": {"type": "MultiPolygon", "coordinates": [[[[0, 0], [2, 0], [2, 2], [0, 0]]]]},
        },
        {
            "relation_id": 202,
            "tags": {"start_date": "1850", "end_date": "1900"},
            "geometry": {"type": "MultiPolygon", "coordinates": [[[[0, 0], [3, 0], [3, 3], [0, 0]]]]},
        },
    ],
}

WD_META = {
    "Q999": {
        "name_en": "Testland",
        "description": "A test polity",
        "aliases_en": ["TL"],
        "temporal_start": "1900",
        "temporal_end": "1950",
    },
    "Q1000": {
        "name_en": "Evolving State",
        "description": None,
        "aliases_en": [],
        "temporal_start": "1800",
        "temporal_end": "1900",
    },
}


def test_map_standalone_basic_fields() -> None:
    record = map_polity_to_jsonl(BASE_POLITY, WD_META)
    assert record["entity_type"] == "political_entity"
    assert record["entity_group"] == "POLITY"
    assert record["wikidata_id"] == "Q999"
    assert record["name"] == "Testland"
    assert record["verification_status"] == "ohm_draft"


def test_map_standalone_geometry_period() -> None:
    record = map_polity_to_jsonl(BASE_POLITY, WD_META)
    assert len(record["_geometry_periods"]) == 1
    period = record["_geometry_periods"][0]
    assert period["ohm_relation_id"] == "100"
    assert period["start_year"] == 1900
    assert period["end_year"] == 1950
    assert period["geojson"]["type"] == "MultiPolygon"


def test_map_chronology_produces_multiple_periods() -> None:
    record = map_polity_to_jsonl(CHRON_POLITY, WD_META)
    assert len(record["_geometry_periods"]) == 2
    assert record["_geometry_periods"][0]["start_year"] == 1800
    assert record["_geometry_periods"][1]["start_year"] == 1850


def test_map_without_wikidata_uses_ohm_name() -> None:
    record = map_polity_to_jsonl(BASE_POLITY, {})
    assert record["name"] in ("Testland (EN)", "Testland")
    assert record["wikidata_id"] == "Q999"


def test_map_ohm_relation_id_stored() -> None:
    record = map_polity_to_jsonl(BASE_POLITY, WD_META)
    assert record["_ohm_relation_id"] == "100"
