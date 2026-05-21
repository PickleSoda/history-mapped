import json
from pathlib import Path
from unittest.mock import Mock

import pipeline.ohm_borders.stage_relations as stage_relations_module
from pipeline.ohm_borders.relations_enricher import enrich_relation_candidates
from pipeline.ohm_borders.stages import run_relations_enrich_stage



def test_enrich_relation_candidates_hydrates_direct_qid_targets() -> None:
    candidates = [
        {
            "source_ohm_relation_id": "100",
            "source_wikidata_id": "Q100",
            "source_name": "Kingdom of Testland",
            "relationship_type": "preceded_by",
            "target_wikidata_id": "Q090",
            "target_label": "Old Testland",
            "source_tag_key": "predecessor",
            "temporal_start": None,
            "temporal_end": None,
        }
    ]

    wikipedia = Mock()
    wikipedia.enrich_batch.side_effect = lambda items: items

    enriched = enrich_relation_candidates(
        candidates,
        metadata_fetcher=lambda qids: {
            "Q090": {
                "name_en": "Old Testland",
                "description": "former kingdom",
                "aliases_en": ["Ancient Testland"],
                "temporal_start": "1700",
                "temporal_end": "1799",
                "wikipedia_title": "Old_Testland",
            }
        },
        name_searcher=lambda name: None,
        wikipedia_enricher=wikipedia,
    )

    assert enriched[0]["relationship_type"] == "preceded_by"
    assert enriched[0]["inverse_relationship_type"] == "succeeded_by"
    assert enriched[0]["source"] == "wikidata:P155"
    assert enriched[0]["target_entity"] == {
        "name": "Old Testland",
        "entity_type": "political_entity",
        "entity_group": "POLITY",
        "wikidata_id": "Q090",
        "summary": "former kingdom",
        "alternative_names": ["Ancient Testland"],
        "temporal_start": "1700",
        "temporal_end": "1799",
        "verification_status": "pipeline_draft",
        "confidence": "medium",
        "source_citations": [{"source": "wikidata", "wikidata_id": "Q090"}],
        "attributes": {"wikipedia_title": "Old_Testland"},
    }



def test_enrich_relation_candidates_falls_back_to_name_search_for_missing_qids() -> None:
    candidates = [
        {
            "source_ohm_relation_id": "100",
            "source_wikidata_id": "Q100",
            "source_name": "Kingdom of Testland",
            "relationship_type": "resulted_from",
            "target_wikidata_id": None,
            "target_label": "Testland Revolution",
            "source_tag_key": "start_event",
            "temporal_start": "1800",
            "temporal_end": "1800",
        }
    ]

    wikipedia = Mock()
    wikipedia.enrich_batch.side_effect = lambda items: items

    enriched = enrich_relation_candidates(
        candidates,
        metadata_fetcher=lambda qids: {
            "Q120": {
                "name_en": "Testland Revolution",
                "description": "revolution in Testland",
                "aliases_en": [],
                "temporal_start": "1800",
                "temporal_end": "1800",
            }
        },
        name_searcher=lambda name: "Q120" if name == "Testland Revolution" else None,
        wikipedia_enricher=wikipedia,
    )

    assert enriched[0]["target_wikidata_id"] == "Q120"
    assert enriched[0]["relationship_type"] == "resulted_from"
    assert enriched[0]["source"] == "wikidata:P828"
    assert enriched[0]["target_entity"]["entity_type"] == "event_rebellion"
    assert enriched[0]["target_entity"]["entity_group"] == "EVENT"



def test_enrich_relation_candidates_runs_wikipedia_enrichment_once_for_deduped_targets() -> None:
    candidates = [
        {
            "source_ohm_relation_id": "100",
            "source_wikidata_id": "Q100",
            "source_name": "Kingdom of Testland",
            "relationship_type": "preceded_by",
            "target_wikidata_id": "Q090",
            "target_label": "Old Testland",
            "source_tag_key": "predecessor",
            "temporal_start": None,
            "temporal_end": None,
        },
        {
            "source_ohm_relation_id": "101",
            "source_wikidata_id": "Q101",
            "source_name": "Duchy of Testland",
            "relationship_type": "preceded_by",
            "target_wikidata_id": "Q090",
            "target_label": "Old Testland",
            "source_tag_key": "predecessor",
            "temporal_start": None,
            "temporal_end": None,
        },
    ]

    def metadata_fetcher(qids: list[str]) -> dict[str, dict]:
        return {
            "Q090": {
                "name_en": "Old Testland",
                "description": "former kingdom",
                "aliases_en": [],
                "temporal_start": "1700",
                "temporal_end": "1799",
                "wikipedia_title": "Old_Testland",
            }
        }

    def enrich_batch(items: list[dict]) -> list[dict]:
        assert len(items) == 1
        items[0]["summary"] = "Wikipedia summary"
        return items

    wikipedia = Mock()
    wikipedia.enrich_batch.side_effect = enrich_batch

    enriched = enrich_relation_candidates(
        candidates,
        metadata_fetcher=metadata_fetcher,
        name_searcher=lambda name: None,
        wikipedia_enricher=wikipedia,
    )

    assert wikipedia.enrich_batch.call_count == 1
    assert enriched[0]["target_entity"]["summary"] == "Wikipedia summary"
    assert enriched[1]["target_entity"]["summary"] == "Wikipedia summary"



def test_run_relations_enrich_stage_writes_enriched_shards(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    input_path = artifact_dir / "relations_candidates" / "relations-candidates-00001.jsonl"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text(
        json.dumps(
            {
                "source_ohm_relation_id": "100",
                "source_wikidata_id": "Q100",
                "source_name": "Kingdom of Testland",
                "relationship_type": "preceded_by",
                "target_wikidata_id": "Q090",
                "target_label": "Old Testland",
                "source_tag_key": "predecessor",
                "temporal_start": None,
                "temporal_end": None,
            }
        ) + "\n",
        encoding="utf-8",
    )

    wikipedia = Mock()
    wikipedia.enrich_batch.side_effect = lambda items: items

    result = run_relations_enrich_stage(
        run_id="run-001",
        artifact_dir=artifact_dir,
        metadata_fetcher=lambda qids: {
            "Q090": {
                "name_en": "Old Testland",
                "description": "former kingdom",
                "aliases_en": [],
                "temporal_start": "1700",
                "temporal_end": "1799",
            }
        },
        name_searcher=lambda name: None,
        wikipedia_enricher=wikipedia,
    )

    output_path = artifact_dir / "relations_enriched" / "relations-enriched-00001.json"
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    enriched = json.loads(output_path.read_text(encoding="utf-8"))

    assert result["status"] == "completed"
    assert len(enriched) == 1
    assert enriched[0]["target_entity"]["wikidata_id"] == "Q090"
    assert manifest["relation_stages"]["enrich"]["status"] == "completed"
    assert manifest["summary"]["relation_enriched_shards"] == 1
    assert manifest["summary"]["relation_enriched_candidates"] == 1


def test_run_relations_enrich_stage_uses_default_name_searcher_when_target_qid_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    artifact_dir = tmp_path / "artifacts"
    input_path = artifact_dir / "relations_candidates" / "relations-candidates-00001.jsonl"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text(
        json.dumps(
            {
                "source_ohm_relation_id": "100",
                "source_wikidata_id": "Q100",
                "source_name": "Kingdom of Testland",
                "relationship_type": "resulted_from",
                "target_wikidata_id": None,
                "target_label": "Testland Revolution",
                "source_tag_key": "start_event",
                "temporal_start": None,
                "temporal_end": None,
            }
        ) + "\n",
        encoding="utf-8",
    )

    wikipedia = Mock()
    wikipedia.enrich_batch.side_effect = lambda items: items

    monkeypatch.setattr(stage_relations_module, "search_qid_by_name", lambda name: "Q120" if name == "Testland Revolution" else None)

    result = run_relations_enrich_stage(
        run_id="run-001",
        artifact_dir=artifact_dir,
        metadata_fetcher=lambda qids: {
            "Q120": {
                "name_en": "Testland Revolution",
                "description": "revolution in Testland",
                "aliases_en": [],
                "temporal_start": "1800",
                "temporal_end": "1800",
            }
        },
        wikipedia_enricher=wikipedia,
    )

    output_path = artifact_dir / "relations_enriched" / "relations-enriched-00001.json"
    enriched = json.loads(output_path.read_text(encoding="utf-8"))

    assert result["status"] == "completed"
    assert enriched[0]["target_wikidata_id"] == "Q120"
    assert enriched[0]["target_entity"]["wikidata_id"] == "Q120"
