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

HISTORICAL_POLITY = {
    "relation_id": 300,
    "tags": {"name": "Sindh", "wikidata": "Q37211"},
    "stages": [
        {
            "relation_id": 301,
            "tags": {"start_date": "-0489", "end_date": "0712"},
            "geometry": {"type": "MultiPolygon", "coordinates": [[[[0, 0], [2, 0], [2, 2], [0, 0]]]]},
        },
        {
            "relation_id": 302,
            "tags": {"start_date": "0861", "end_date": "1843-03-24"},
            "geometry": {"type": "MultiPolygon", "coordinates": [[[[0, 0], [3, 0], [3, 3], [0, 0]]]]},
        },
    ],
}

HISTORICAL_WD_META = {
    "Q37211": {
        "name_en": "Sindh",
        "description": "province of Pakistan",
        "aliases_en": ["Sind"],
        "temporal_start": "1947",
        "temporal_end": None,
    }
}

INVALID_STAGE_POLITY = {
    "relation_id": 400,
    "tags": {"name": "Republic of Venice", "wikidata": "Q4948"},
    "stages": [
        {
            "relation_id": 401,
            "tags": {"start_date": "1390", "end_date": "1363"},
            "geometry": {"type": "MultiPolygon", "coordinates": [[[[0, 0], [2, 0], [2, 2], [0, 0]]]]},
        },
        {
            "relation_id": 402,
            "tags": {"start_date": "1391", "end_date": "1404"},
            "geometry": {"type": "MultiPolygon", "coordinates": [[[[0, 0], [3, 0], [3, 3], [0, 0]]]]},
        },
    ],
}

INVALID_STAGE_WD_META = {
    "Q4948": {
        "name_en": "Republic of Venice",
        "description": "former state",
        "aliases_en": [],
        "temporal_start": "0697",
        "temporal_end": "1797",
    }
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
    assert period["geojson"]["type"] == "Point"
    assert len(period["geojson"]["coordinates"]) == 2


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


def test_map_prefers_ohm_stage_bounds_over_conflicting_wikidata_dates() -> None:
    record = map_polity_to_jsonl(HISTORICAL_POLITY, HISTORICAL_WD_META)
    assert record["temporal_start"] == "-0489"
    assert record["temporal_end"] == "1843-03-24"


def test_map_skips_invalid_stage_periods_with_reversed_years() -> None:
    record = map_polity_to_jsonl(INVALID_STAGE_POLITY, INVALID_STAGE_WD_META)

    assert len(record["_geometry_periods"]) == 1
    assert record["_geometry_periods"][0]["ohm_relation_id"] == "402"
    assert record["_geometry_periods"][0]["start_year"] == 1391
    assert record["_geometry_periods"][0]["end_year"] == 1404
