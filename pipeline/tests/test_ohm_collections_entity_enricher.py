from pipeline.ohm_collections.entity_enricher import enrich_candidate


def test_enrich_candidate_merges_existing_qid_metadata_without_overwriting_name() -> None:
    candidate = {
        "name": "Ancient Memphis",
        "wikidata_id": "Q123",
        "entity_types": ["city"],
    }

    def fake_metadata_enricher(qids: list[str]) -> dict[str, dict]:
        assert qids == ["Q123"]
        return {
            "Q123": {
                "name_en": "Memphis, Egypt",
                "description": "Ancient capital city in Egypt.",
                "aliases_en": ["Ineb-Hedj", "Men-nefer"],
            }
        }

    def fake_geo_resolver(entity: dict) -> dict:
        assert entity["name"] == "Ancient Memphis"
        return {"status": "no_match", "provenance": {"reason": "no_candidates_returned"}}

    enriched = enrich_candidate(
        candidate,
        metadata_enricher=fake_metadata_enricher,
        geo_resolver=fake_geo_resolver,
    )

    assert enriched["name"] == "Ancient Memphis"
    assert enriched["wikidata_id"] == "Q123"
    assert enriched["summary"] == "Ancient capital city in Egypt."
    assert enriched["alternative_names"] == ["Ineb-Hedj", "Men-nefer"]
    assert enriched["_wikidata_match_source"] == "existing_qid"
    assert enriched["fallback_geojson"] is None
    assert enriched["_geo_resolution"]["status"] == "no_match"


def test_enrich_candidate_resolves_missing_qid_by_name_and_uses_geo_fallback_geometry() -> None:
    candidate = {
        "name": "Battle of Kadesh",
        "entity_types": ["battle"],
    }

    def fake_name_searcher(name: str) -> str | None:
        assert name == "Battle of Kadesh"
        return "Q999"

    def fake_metadata_enricher(qids: list[str]) -> dict[str, dict]:
        assert qids == ["Q999"]
        return {
            "Q999": {
                "name_en": "Battle of Kadesh",
                "description": "Battle fought between Egyptians and Hittites.",
                "aliases_en": ["Qadesh battle"],
            }
        }

    def fake_geo_resolver(entity: dict) -> dict:
        assert entity["wikidata_id"] == "Q999"
        return {
            "status": "matched",
            "geometry": {"type": "Point", "coordinates": [36.0, 34.5]},
            "provenance": {"reason": "exact_name_match"},
        }

    enriched = enrich_candidate(
        candidate,
        name_searcher=fake_name_searcher,
        metadata_enricher=fake_metadata_enricher,
        geo_resolver=fake_geo_resolver,
    )

    assert enriched["wikidata_id"] == "Q999"
    assert enriched["summary"] == "Battle fought between Egyptians and Hittites."
    assert enriched["alternative_names"] == ["Qadesh battle"]
    assert enriched["_wikidata_match_source"] == "name_search"
    assert enriched["fallback_geojson"] == {"type": "Point", "coordinates": [36.0, 34.5]}
    assert enriched["_geo_resolution"]["status"] == "matched"