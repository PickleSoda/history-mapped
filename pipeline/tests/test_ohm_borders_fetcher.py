from pipeline.ohm_borders.fetcher import parse_elements, assemble_geometry

BOUNDARY_FIXTURE = {
    "elements": [
        {
            "type": "relation",
            "id": 100,
            "tags": {
                "boundary": "administrative",
                "admin_level": "2",
                "name": "Testland",
                "wikidata": "Q999",
                "start_date": "1900",
                "end_date": "1950",
                "type": "boundary",
            },
            "members": [
                {
                    "type": "way", "ref": 1, "role": "outer",
                    "geometry": [
                        {"lat": 0.0, "lon": 0.0},
                        {"lat": 1.0, "lon": 0.0},
                        {"lat": 1.0, "lon": 1.0},
                    ],
                },
                {
                    "type": "way", "ref": 2, "role": "outer",
                    "geometry": [
                        {"lat": 1.0, "lon": 1.0},
                        {"lat": 0.0, "lon": 1.0},
                        {"lat": 0.0, "lon": 0.0},
                    ],
                },
            ],
        }
    ]
}

CHRONOLOGY_FIXTURE = {
    "elements": [
        {
            "type": "relation",
            "id": 200,
            "tags": {
                "type": "chronology",
                "boundary": "administrative",
                "name": "Evolving State",
                "wikidata": "Q1000",
            },
            "members": [
                {"type": "relation", "ref": 201, "role": ""},
                {"type": "relation", "ref": 202, "role": ""},
            ],
        },
        {
            "type": "relation",
            "id": 201,
            "tags": {
                "boundary": "administrative",
                "admin_level": "2",
                "start_date": "1800",
                "end_date": "1850",
                "type": "boundary",
            },
            "members": [
                {
                    "type": "way", "ref": 10, "role": "outer",
                    "geometry": [
                        {"lat": 0.0, "lon": 0.0},
                        {"lat": 2.0, "lon": 0.0},
                        {"lat": 2.0, "lon": 2.0},
                        {"lat": 0.0, "lon": 2.0},
                        {"lat": 0.0, "lon": 0.0},
                    ],
                }
            ],
        },
        {
            "type": "relation",
            "id": 202,
            "tags": {
                "boundary": "administrative",
                "admin_level": "2",
                "start_date": "1850",
                "end_date": "1900",
                "type": "boundary",
            },
            "members": [
                {
                    "type": "way", "ref": 11, "role": "outer",
                    "geometry": [
                        {"lat": 0.0, "lon": 0.0},
                        {"lat": 3.0, "lon": 0.0},
                        {"lat": 3.0, "lon": 3.0},
                        {"lat": 0.0, "lon": 3.0},
                        {"lat": 0.0, "lon": 0.0},
                    ],
                }
            ],
        },
    ]
}


def test_parse_elements_standalone() -> None:
    polities = parse_elements(BOUNDARY_FIXTURE["elements"])
    assert len(polities) == 1
    polity = polities[0]
    assert polity["relation_id"] == 100
    assert polity["tags"]["wikidata"] == "Q999"
    assert len(polity["stages"]) == 1


def test_parse_elements_chronology() -> None:
    polities = parse_elements(CHRONOLOGY_FIXTURE["elements"])
    assert len(polities) == 1
    polity = polities[0]
    assert polity["relation_id"] == 200
    assert polity["tags"]["wikidata"] == "Q1000"
    assert len(polity["stages"]) == 2


def test_assemble_geometry_closed_outer() -> None:
    members = BOUNDARY_FIXTURE["elements"][0]["members"]
    geojson = assemble_geometry(members)
    assert geojson is not None
    assert geojson["type"] in ("Polygon", "MultiPolygon")


def test_assemble_geometry_returns_none_on_empty() -> None:
    assert assemble_geometry([]) is None
