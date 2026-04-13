from pathlib import Path

from pipeline.ohm_borders.enricher import enrich_output_jsonl_missing_qids


def test_enrich_output_jsonl_searches_missing_qids_and_applies_metadata(tmp_path: Path) -> None:
    input_path = tmp_path / "ohm_borders.jsonl"
    output_path = tmp_path / "ohm_borders_enriched.jsonl"
    input_path.write_text(
        "\n".join(
            [
                '{"name":"Kingdom of Hungary","wikidata_id":null,"summary":null,"alternative_names":[],"temporal_start":"1867","temporal_end":"1918"}',
                '{"name":"Existing State","wikidata_id":"Q123","summary":"Existing summary","alternative_names":["Old"],"temporal_start":"1900","temporal_end":"1950"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    def fake_searcher(name: str) -> str | None:
        return "Q171150" if name == "Kingdom of Hungary" else None

    def fake_enricher(qids: list[str], batch_size: int = 50):
        assert qids == ["Q171150", "Q123"]
        return {
            "Q171150": {
                "name_en": "Kingdom of Hungary",
                "description": "A historical state in Central Europe",
                "aliases_en": ["Hungary"],
                "temporal_start": "1867",
                "temporal_end": "1918",
            },
            "Q123": {
                "name_en": "Existing State",
                "description": "Ignored because summary already set",
                "aliases_en": ["Existing alias"],
                "temporal_start": "1900",
                "temporal_end": "1950",
            },
        }

    result = enrich_output_jsonl_missing_qids(
        input_path=input_path,
        output_path=output_path,
        searcher=fake_searcher,
        enricher=fake_enricher,
    )

    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert result["record_count"] == 2
    assert result["searched_count"] == 1
    assert result["matched_count"] == 1

    assert '"wikidata_id":"Q171150"' in lines[0]
    assert '"summary":"A historical state in Central Europe"' in lines[0]
    assert '"alternative_names":["Hungary"]' in lines[0]
    assert '"_wikidata_match_source":"name_search"' in lines[0]

    assert '"wikidata_id":"Q123"' in lines[1]
    assert '"summary":"Existing summary"' in lines[1]


def test_enrich_output_jsonl_leaves_unmatched_records_without_qids(tmp_path: Path) -> None:
    input_path = tmp_path / "ohm_borders.jsonl"
    output_path = tmp_path / "ohm_borders_enriched.jsonl"
    input_path.write_text('{"name":"Unknown Realm","wikidata_id":null}\n', encoding="utf-8")

    result = enrich_output_jsonl_missing_qids(
        input_path=input_path,
        output_path=output_path,
        searcher=lambda _name: None,
        enricher=lambda _qids, batch_size=50: {},
    )

    line = output_path.read_text(encoding="utf-8").strip()
    assert result["searched_count"] == 1
    assert result["matched_count"] == 0
    assert '"wikidata_id":null' in line
    assert '"_wikidata_match_source":"name_search_unmatched"' in line