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


def test_assemble_geometry_keeps_only_more_detailed_overlapping_outline() -> None:
    members = [
        {
            "type": "way",
            "ref": 1,
            "role": "outer",
            "geometry": [
                {"lat": 0.0, "lon": 0.0},
                {"lat": 0.0, "lon": 4.0},
                {"lat": 4.0, "lon": 4.0},
                {"lat": 4.0, "lon": 0.0},
                {"lat": 0.0, "lon": 0.0},
            ],
        },
        {
            "type": "way",
            "ref": 2,
            "role": "outer",
            "geometry": [
                {"lat": 0.0, "lon": 0.0},
                {"lat": 0.0, "lon": 1.0},
                {"lat": 0.0, "lon": 2.0},
                {"lat": 0.0, "lon": 3.0},
                {"lat": 0.0, "lon": 4.0},
                {"lat": 1.0, "lon": 4.0},
                {"lat": 2.0, "lon": 4.0},
                {"lat": 3.0, "lon": 4.0},
                {"lat": 4.0, "lon": 4.0},
                {"lat": 4.0, "lon": 3.0},
                {"lat": 4.0, "lon": 2.0},
                {"lat": 4.0, "lon": 1.0},
                {"lat": 4.0, "lon": 0.0},
                {"lat": 3.0, "lon": 0.0},
                {"lat": 2.0, "lon": 0.0},
                {"lat": 1.0, "lon": 0.0},
                {"lat": 0.0, "lon": 0.0},
            ],
        },
    ]

    geojson = assemble_geometry(members)

    assert geojson is not None
    assert geojson["type"] in ("Polygon", "MultiPolygon")
    coordinates = geojson["coordinates"] if geojson["type"] == "MultiPolygon" else [geojson["coordinates"]]
    assert len(coordinates) == 1
    assert len(coordinates[0][0]) == 17


def test_assemble_geometry_preserves_disjoint_outlines() -> None:
    members = [
        {
            "type": "way",
            "ref": 1,
            "role": "outer",
            "geometry": [
                {"lat": 0.0, "lon": 0.0},
                {"lat": 0.0, "lon": 1.0},
                {"lat": 1.0, "lon": 1.0},
                {"lat": 1.0, "lon": 0.0},
                {"lat": 0.0, "lon": 0.0},
            ],
        },
        {
            "type": "way",
            "ref": 2,
            "role": "outer",
            "geometry": [
                {"lat": 10.0, "lon": 10.0},
                {"lat": 10.0, "lon": 11.0},
                {"lat": 11.0, "lon": 11.0},
                {"lat": 11.0, "lon": 10.0},
                {"lat": 10.0, "lon": 10.0},
            ],
        },
    ]

    geojson = assemble_geometry(members)

    assert geojson is not None
    assert geojson["type"] == "MultiPolygon"
    assert len(geojson["coordinates"]) == 2


def test_assemble_geometry_deduplicates_contained_outlines() -> None:
    """Test that when one outline is contained within another, only the more detailed one is kept.
    
    This handles the case where OSM has both a simplified boundary outline and a detailed 
    one for the same region (e.g., Domnonée case).
    """
    members = [
        # Simplified outline (contained within the detailed one)
        {
            "type": "way",
            "ref": 1,
            "role": "outer",
            "geometry": [
                {"lat": 0.5, "lon": 0.5},
                {"lat": 0.5, "lon": 1.5},
                {"lat": 1.5, "lon": 1.5},
                {"lat": 1.5, "lon": 0.5},
                {"lat": 0.5, "lon": 0.5},
            ],
        },
        # Detailed outline (contains the simplified one)
        {
            "type": "way",
            "ref": 2,
            "role": "outer",
            "geometry": [
                {"lat": 0.0, "lon": 0.0},
                {"lat": 0.0, "lon": 0.1},
                {"lat": 0.0, "lon": 0.2},
                {"lat": 0.0, "lon": 2.0},
                {"lat": 0.1, "lon": 2.0},
                {"lat": 0.2, "lon": 2.0},
                {"lat": 2.0, "lon": 2.0},
                {"lat": 2.0, "lon": 1.9},
                {"lat": 2.0, "lon": 1.8},
                {"lat": 2.0, "lon": 0.0},
                {"lat": 1.9, "lon": 0.0},
                {"lat": 1.8, "lon": 0.0},
                {"lat": 0.0, "lon": 0.0},
            ],
        },
    ]

    geojson = assemble_geometry(members)

    assert geojson is not None
    assert geojson["type"] in ("Polygon", "MultiPolygon")
    coordinates = geojson["coordinates"] if geojson["type"] == "MultiPolygon" else [geojson["coordinates"]]
    # Should have only 1 polygon (the detailed one, not both)
    assert len(coordinates) == 1
    # The detailed outline has more coordinates than the simplified one
    assert len(coordinates[0][0]) >= 13  # detailed ring has at least 13 points
