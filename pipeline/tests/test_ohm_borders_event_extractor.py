"""Tests for OHM border event extractor."""

from pipeline.ohm_borders.event_extractor import extract_event_refs


def test_extracts_start_event_from_stage_tags() -> None:
    polity = {
        "relation_id": 28513,
        "tags": {"name": "Austria-Hungary", "wikidata": "Q28513"},
        "stages": [
            {
                "relation_id": 999,
                "tags": {
                    "start_date": "1908-10-06",
                    "start_event": "Bosnian crisis, de jure inclusion of Bosnian Condominium",
                    "start_event:wikidata": "Q167246",
                },
                "geometry": None,
            }
        ],
    }

    refs = extract_event_refs(polity)

    assert len(refs) == 1
    assert refs[0] == {
        "event_role": "start",
        "event_label": "Bosnian crisis, de jure inclusion of Bosnian Condominium",
        "event_wikidata_id": "Q167246",
        "polity_ohm_relation_id": "28513",
        "stage_ohm_relation_id": "999",
        "polity_name": "Austria-Hungary",
        "event_date": "1908-10-06",
        "source_tag_key": "start_event",
        "source_tags": {
            "start_event": "Bosnian crisis, de jure inclusion of Bosnian Condominium",
            "start_event:wikidata": "Q167246",
            "start_date": "1908-10-06",
        },
    }


def test_ignores_empty_event_labels() -> None:
    polity = {
        "relation_id": 1,
        "tags": {"name": "Test"},
        "stages": [
            {
                "relation_id": 10,
                "tags": {"start_event": "   ", "end_event": ""},
                "geometry": None,
            }
        ],
    }

    refs = extract_event_refs(polity)
    assert refs == []


def test_extracts_end_event_without_qid() -> None:
    polity = {
        "relation_id": 2,
        "tags": {"name": "Romania"},
        "stages": [
            {
                "relation_id": 20,
                "tags": {"end_event": "End of World War I", "end_date": "1918-12-01"},
                "geometry": None,
            }
        ],
    }

    refs = extract_event_refs(polity)
    assert len(refs) == 1
    assert refs[0]["event_role"] == "end"
    assert refs[0]["event_wikidata_id"] is None
    assert refs[0]["event_label"] == "End of World War I"


def test_deduplicates_repeated_events_across_stages() -> None:
    polity = {
        "relation_id": 3,
        "tags": {"name": "Test"},
        "stages": [
            {
                "relation_id": 30,
                "tags": {"start_event": "Same Event", "start_event:wikidata": "Q1"},
                "geometry": None,
            },
            {
                "relation_id": 31,
                "tags": {"start_event": "Same Event", "start_event:wikidata": "Q1"},
                "geometry": None,
            },
        ],
    }

    refs = extract_event_refs(polity)
    assert len(refs) == 1