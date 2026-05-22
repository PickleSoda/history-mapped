from pipeline.ohm_borders.fetcher import (
    assemble_geometry,
    derive_representative_point,
    parse_elements,
    parse_relation_subset,
)

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


def test_derive_representative_point_returns_point_for_simple_polygon() -> None:
    point = derive_representative_point(
        {
            "type": "Polygon",
            "coordinates": [
                [[0.0, 0.0], [4.0, 0.0], [4.0, 4.0], [0.0, 4.0], [0.0, 0.0]],
            ],
        }
    )

    assert point == {"type": "Point", "coordinates": [2.0, 2.0]}


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


def test_parse_relation_subset_filters_and_sorts_relations_before_parsing() -> None:
    seen_ids: list[int] = []

    def fake_parser(elements: list[dict]) -> list[dict]:
        nonlocal seen_ids
        seen_ids = [int(element["id"]) for element in elements]
        return [{"relation_id": relation_id, "tags": {}, "stages": []} for relation_id in seen_ids]

    result = parse_relation_subset(
        [
            {"type": "relation", "id": "3", "tags": {"name": "Three"}},
            {"type": "way", "id": 100},
            {"type": "relation", "id": 1, "tags": {"name": "One"}},
            {"type": "relation", "id": "bad", "tags": {"name": "Bad"}},
            {"type": "relation", "id": 2, "tags": {"name": "Two"}},
        ],
        parser=fake_parser,
    )

    assert seen_ids == [1, 2, 3]
    assert [record["relation_id"] for record in result] == [1, 2, 3]


def test_parse_relation_subset_with_global_index_handles_cross_shard_chronology_members() -> None:
    relation_index = {
        200: {
            "type": "relation",
            "id": 200,
            "tags": {"type": "chronology", "boundary": "administrative", "name": "Evolving State"},
            "members": [{"type": "relation", "ref": 201, "role": ""}],
        },
        201: {
            "type": "relation",
            "id": 201,
            "tags": {"boundary": "administrative", "admin_level": "2", "start_date": "1800", "end_date": "1850"},
            "members": [],
        },
    }

    chronology_records = parse_relation_subset(
        [relation_index[200]],
        relation_index=relation_index,
        chronology_member_ids={201},
    )
    member_records = parse_relation_subset(
        [relation_index[201]],
        relation_index=relation_index,
        chronology_member_ids={201},
    )

    assert [record["relation_id"] for record in chronology_records] == [200]
    assert [stage["relation_id"] for stage in chronology_records[0]["stages"]] == [201]
    assert member_records == []


def test_parse_relation_subset_with_global_index_skips_standalone_when_chronology_has_same_wikidata() -> None:
    relation_index = {
        200: {
            "type": "relation",
            "id": 200,
            "tags": {
                "type": "chronology",
                "boundary": "administrative",
                "name": "Evolving State",
                "wikidata": "Q1000",
            },
            "members": [{"type": "relation", "ref": 201, "role": ""}],
        },
        201: {
            "type": "relation",
            "id": 201,
            "tags": {
                "boundary": "administrative",
                "admin_level": "2",
                "start_date": "1800",
                "end_date": "1850",
            },
            "members": [],
        },
        301: {
            "type": "relation",
            "id": 301,
            "tags": {
                "boundary": "administrative",
                "admin_level": "2",
                "name": "Evolving State (approx)",
                "wikidata": "Q1000",
            },
            "members": [],
        },
        302: {
            "type": "relation",
            "id": 302,
            "tags": {
                "boundary": "administrative",
                "admin_level": "2",
                "name": "Standalone",
                "wikidata": "Q2000",
            },
            "members": [],
        },
    }

    records = parse_relation_subset(
        [relation_index[200], relation_index[301], relation_index[302]],
        relation_index=relation_index,
        chronology_member_ids={201},
    )

    assert [record["relation_id"] for record in records] == [200, 302]


def test_parse_elements_skips_standalone_when_chronology_has_same_wikidata() -> None:
    elements = [
        {
            "type": "relation",
            "id": 200,
            "tags": {
                "type": "chronology",
                "boundary": "administrative",
                "name": "Evolving State",
                "wikidata": "Q1000",
            },
            "members": [{"type": "relation", "ref": 201, "role": ""}],
        },
        {
            "type": "relation",
            "id": 201,
            "tags": {
                "boundary": "administrative",
                "admin_level": "2",
                "start_date": "1800",
                "end_date": "1850",
            },
            "members": [],
        },
        {
            "type": "relation",
            "id": 301,
            "tags": {
                "boundary": "administrative",
                "admin_level": "2",
                "name": "Evolving State (approx)",
                "wikidata": "Q1000",
            },
            "members": [],
        },
        {
            "type": "relation",
            "id": 302,
            "tags": {
                "boundary": "administrative",
                "admin_level": "2",
                "name": "Standalone",
                "wikidata": "Q2000",
            },
            "members": [],
        },
    ]

    polities = parse_elements(elements)

    assert [record["relation_id"] for record in polities] == [200, 302]


def test_assemble_geometry_closed_outer() -> None:
    members = BOUNDARY_FIXTURE["elements"][0]["members"]
    geojson = assemble_geometry(members)
    assert geojson is not None
    assert geojson["type"] in ("Polygon", "MultiPolygon")


def test_assemble_geometry_returns_none_on_empty() -> None:
    assert assemble_geometry([]) is None


def test_assemble_geometry_stitches_segmented_outer_ways_into_single_polygon() -> None:
    members = [
        {
            "type": "way",
            "ref": 1,
            "role": "outer",
            "geometry": [
                {"lat": 0.0, "lon": 0.0},
                {"lat": 0.0, "lon": 1.0},
            ],
        },
        {
            "type": "way",
            "ref": 2,
            "role": "outer",
            "geometry": [
                {"lat": 0.0, "lon": 1.0},
                {"lat": 1.0, "lon": 1.0},
            ],
        },
        {
            "type": "way",
            "ref": 3,
            "role": "outer",
            "geometry": [
                {"lat": 1.0, "lon": 1.0},
                {"lat": 1.0, "lon": 0.0},
            ],
        },
        {
            "type": "way",
            "ref": 4,
            "role": "outer",
            "geometry": [
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
    assert len(coordinates[0][0]) == 5


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


def test_assemble_geometry_preserves_contained_outlines_without_extra_deduplication() -> None:
    """Contained outlines should not trigger the expensive containment heuristic.

    Polygon stitching now handles segmented borders, so nested outlines are left as-is
    unless they are near-duplicates by the cheaper overlap test.
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
    assert len(coordinates) == 2
