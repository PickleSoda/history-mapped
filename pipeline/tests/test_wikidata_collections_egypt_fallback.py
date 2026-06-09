from unittest.mock import MagicMock

from pipeline.wikidata.collections.egypt_fallback import (
    fetch_seed_entities,
    apply_bounded_expansion,
    build_collection_artifacts,
    CATEGORY_TO_ENTITY_TYPE,
)


def test_fetch_seed_entities_returns_mapped_records(monkeypatch) -> None:
    def mock_fetch(qids):
        return {
            "Q79": {
                "qid": "Q79",
                "label": "Egypt",
                "description": "Country",
                "aliases": [],
                "coords": None,
                "properties": {},
            },
        }

    monkeypatch.setattr("pipeline.wikidata.collections.egypt_fallback.batch_fetch_wikidata", mock_fetch)

    seeds = [{"qid": "Q79", "category": "modern_state"}]
    records = fetch_seed_entities(seeds)
    assert len(records) == 1
    assert records[0]["wikidata_id"] == "Q79"
    assert records[0]["_seed_category"] == "modern_state"


def test_bounded_expansion_respects_egypt_domain(monkeypatch) -> None:
    def mock_fetch(qids):
        return {
            "Q1": {
                "qid": "Q1",
                "label": "British Empire",
                "description": "Empire",
                "aliases": [],
                "coords": None,
                "properties": {
                    "P17": [{"qid": "Q145", "label": "United Kingdom", "uri": "http://www.wikidata.org/entity/Q145"}],
                },
            },
        }

    monkeypatch.setattr("pipeline.wikidata.collections.egypt_fallback.batch_fetch_wikidata", mock_fetch)

    included = [{"wikidata_id": "Q79", "name": "Egypt"}]
    expansion_qids = ["Q1"]
    expanded = apply_bounded_expansion(included, expansion_qids)
    # British Empire should be rejected (not Egypt domain)
    assert len(expanded) == 0


def test_build_collection_artifacts_writes_files(tmp_path) -> None:
    from pipeline.wikidata.collections.artifacts import collection_artifact_dir

    artifact_dir = collection_artifact_dir("test-run", base_dir=tmp_path)
    records = [{"name": "Egypt", "wikidata_id": "Q79", "entity_type": "political_entity"}]

    build_collection_artifacts(artifact_dir, records, seeds=[{"qid": "Q79"}], excluded=[])

    assert (artifact_dir / "entities_final" / "egypt_collection.jsonl").exists()
    assert (artifact_dir / "manifest.json").exists()
