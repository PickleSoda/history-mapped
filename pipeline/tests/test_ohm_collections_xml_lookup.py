import json
from pathlib import Path

from pipeline.ohm_collections.xml_index_store import initialize_index_schema, insert_object_aliases, insert_objects
from pipeline.ohm_collections.xml_lookup import (
    find_objects_by_name,
    find_objects_by_tag_value,
    find_objects_by_wikidata_id,
)


def _seed_lookup_index(db_path: Path) -> None:
    initialize_index_schema(db_path)
    insert_objects(
        db_path,
        [
            (
                "node",
                100,
                "Ancient Memphis",
                "ancient memphis",
                "Q123",
                json.dumps(
                    {
                        "name": "Ancient Memphis",
                        "name:fr": "Memphis antique",
                        "alt_name": "Ineb-Hedj",
                        "wikidata": "Q123",
                        "historic": "city",
                    }
                ),
                29.871,
                31.205,
            ),
            (
                "relation",
                300,
                "Kingdom of Egypt",
                "kingdom of egypt",
                "Q456",
                json.dumps(
                    {
                        "name": "Kingdom of Egypt",
                        "short_name": "Egypt",
                        "wikidata": "Q456",
                        "type": "boundary",
                    }
                ),
                None,
                None,
            ),
            (
                "way",
                200,
                "Temple District",
                "temple district",
                None,
                json.dumps(
                    {
                        "name": "Temple District",
                        "official_name": "Temple District of Memphis",
                    }
                ),
                None,
                None,
            ),
        ],
    )
    insert_object_aliases(
        db_path,
        [
            ("node", 100, "alt_name", "Ineb-Hedj", "ineb hedj"),
            ("node", 100, "name:fr", "Memphis antique", "memphis antique"),
            ("node", 100, "name:en", "Ancient Memphis", "ancient memphis"),
            ("relation", 300, "short_name", "Egypt", "egypt"),
            ("way", 200, "official_name", "Temple District of Memphis", "temple district of memphis"),
        ],
    )


def test_find_objects_by_name_matches_primary_name_aliases_and_multilingual_name_tags_without_duplicates(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "ohm-xml-index.sqlite3"
    _seed_lookup_index(db_path)

    primary_name_matches = find_objects_by_name(db_path, "Ancient Memphis")
    alias_matches = find_objects_by_name(db_path, "Ineb Hedj")
    multilingual_matches = find_objects_by_name(db_path, "Memphis antique")

    assert [(row["object_type"], row["object_id"]) for row in primary_name_matches] == [("node", 100)]
    assert [(row["object_type"], row["object_id"]) for row in alias_matches] == [("node", 100)]
    assert [(row["object_type"], row["object_id"]) for row in multilingual_matches] == [("node", 100)]


def test_find_objects_by_wikidata_id_returns_matching_objects(tmp_path: Path) -> None:
    db_path = tmp_path / "ohm-xml-index.sqlite3"
    _seed_lookup_index(db_path)

    matches = find_objects_by_wikidata_id(db_path, "Q456")

    assert [(row["object_type"], row["object_id"], row["name"]) for row in matches] == [
        ("relation", 300, "Kingdom of Egypt"),
    ]


def test_find_objects_by_tag_value_returns_objects_with_matching_raw_tag_values(tmp_path: Path) -> None:
    db_path = tmp_path / "ohm-xml-index.sqlite3"
    _seed_lookup_index(db_path)

    matches = find_objects_by_tag_value(db_path, tag_key="historic", tag_value="city")

    assert [(row["object_type"], row["object_id"], row["name"]) for row in matches] == [
        ("node", 100, "Ancient Memphis"),
    ]