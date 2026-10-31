from pipeline.ohm_links.records import TAG_KEYS, element_to_record

RELATION_ELEMENT = {
    "type": "relation",
    "id": 1880,
    "tags": {
        "boundary": "administrative",
        "admin_level": "2",
        "type": "boundary",
        "name": "Imperium Romanum",
        "name:en": "Roman Empire",
        "name:de": "Römisches Reich",
        "wikidata": "Q2277",
        "wikipedia": "en:Roman Empire",
        "start_date": "-0027-01-16",
        "end_date": "0476-09-04",
        "source": "some survey",
    },
}

NODE_ELEMENT = {
    "type": "node",
    "id": 42,
    "lat": 41.9,
    "lon": 12.5,
    "tags": {
        "place": "city",
        "name": "Roma",
        "wikidata": "Q220",
        "start_date": "-0753",
    },
}


def test_tag_keys_match_contract():
    assert TAG_KEYS == (
        "boundary",
        "admin_level",
        "type",
        "place",
        "name",
        "name:en",
        "official_name",
        "wikidata",
        "wikipedia",
        "start_date",
        "end_date",
    )


def test_relation_element_maps_to_contract_record():
    assert element_to_record(RELATION_ELEMENT) == {
        "osm_type": "relation",
        "osm_id": 1880,
        "wikidata_id": "Q2277",
        "name": "Imperium Romanum",
        "name_en": "Roman Empire",
        "admin_level": 2,
        "place": None,
        "start_date": "-0027-01-16",
        "end_date": "0476-09-04",
        "tags": {
            "boundary": "administrative",
            "admin_level": "2",
            "type": "boundary",
            "name": "Imperium Romanum",
            "name:en": "Roman Empire",
            "wikidata": "Q2277",
            "wikipedia": "en:Roman Empire",
            "start_date": "-0027-01-16",
            "end_date": "0476-09-04",
        },
    }


def test_node_element_maps_to_contract_record_without_absent_keys():
    assert element_to_record(NODE_ELEMENT) == {
        "osm_type": "node",
        "osm_id": 42,
        "wikidata_id": "Q220",
        "name": "Roma",
        "name_en": None,
        "admin_level": None,
        "place": "city",
        "start_date": "-0753",
        "end_date": None,
        "tags": {
            "place": "city",
            "name": "Roma",
            "wikidata": "Q220",
            "start_date": "-0753",
        },
    }


def test_element_without_tags_returns_none():
    assert element_to_record({"type": "way", "id": 7}) is None
    assert element_to_record({"type": "way", "id": 7, "tags": {}}) is None


def test_element_without_osm_type_or_id_returns_none():
    assert element_to_record({"type": "area", "id": 7, "tags": {"name": "x"}}) is None
    assert element_to_record({"type": "node", "tags": {"name": "x"}}) is None


def test_invalid_wikidata_tag_gives_null_wikidata_id_but_keeps_raw_tag():
    for value in ("Q2277;Q1747689", "q2277", "Q", "2277", "Q2277 "):
        element = {"type": "relation", "id": 1, "tags": {"name": "x", "wikidata": value}}
        record = element_to_record(element)
        assert record["wikidata_id"] is None
        assert record["tags"]["wikidata"] == value


def test_non_numeric_admin_level_gives_null():
    for value in ("2;4", "two", ""):
        element = {"type": "relation", "id": 1, "tags": {"admin_level": value}}
        record = element_to_record(element)
        assert record["admin_level"] is None
        assert record["tags"]["admin_level"] == value
