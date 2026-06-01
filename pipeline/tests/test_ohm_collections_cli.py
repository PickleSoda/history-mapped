import json
from pathlib import Path

from click.testing import CliRunner

import pipeline.__main__ as main_module
import pipeline.ohm_collections.__main__ as collections_main_module
from pipeline.__main__ import cli
from pipeline.ohm_collections.xml_index_builder import build_index


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_root_collections_build_xml_index_cli_wires_paths_and_force(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    source_path = tmp_path / "map.xml"
    index_path = tmp_path / "map.sqlite3"
    source_path.write_text("<osm version='0.6'></osm>", encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_build_index(input_path, *, index_path, force=False):
        captured["input_path"] = input_path
        captured["index_path"] = index_path
        captured["force"] = force
        return {"status": "completed", "index_path": index_path, "object_count": 0}

    monkeypatch.setattr(collections_main_module, "build_index", fake_build_index)

    result = runner.invoke(
        cli,
        [
            "collections",
            "build-xml-index",
            "--input",
            str(source_path),
            "--index-path",
            str(index_path),
            "--force",
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        "input_path": source_path,
        "index_path": index_path,
        "force": True,
    }


def test_collections_egypt_build_cli_writes_manifest_and_supports_resume(tmp_path: Path) -> None:
    runner = CliRunner()
    source_path = tmp_path / "map.xml"
    xml_index_path = tmp_path / "map.sqlite3"
    ohm_index_path = tmp_path / "ohm.sqlite3"
    output_root = tmp_path / "egypt-run"
    source_path.write_text("<?xml version='1.0' encoding='UTF-8'?><osm version='0.6'></osm>", encoding="utf-8")
    build_index(source_path, index_path=xml_index_path, force=True)
    ohm_index_path.write_text("sqlite placeholder", encoding="utf-8")

    force_result = runner.invoke(
        cli,
        [
            "collections",
            "egypt-build",
            "--xml-index-path",
            str(xml_index_path),
            "--ohm-index-path",
            str(ohm_index_path),
            "--run-id",
            "egypt-run",
            "--output-root",
            str(output_root),
            "--force",
        ],
    )

    manifest_path = output_root / "manifest.json"
    assert force_result.exit_code == 0
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["counts"] == {"included": 0, "excluded": 0, "border_records": 0, "entity_records": 0}

    resume_result = runner.invoke(
        cli,
        [
            "collections",
            "egypt-build",
            "--xml-index-path",
            str(xml_index_path),
            "--ohm-index-path",
            str(ohm_index_path),
            "--run-id",
            "egypt-run",
            "--output-root",
            str(output_root),
            "--resume",
        ],
    )

    assert resume_result.exit_code == 0
    assert "skipped" in resume_result.output.lower()


def test_collections_egypt_relations_run_cli_writes_contract_files_and_supports_resume(tmp_path: Path) -> None:
    runner = CliRunner()
    output_root = tmp_path / "egypt-run"

    force_result = runner.invoke(
        cli,
        [
            "collections",
            "egypt-relations-run",
            "--run-id",
            "egypt-run",
            "--output-root",
            str(output_root),
            "--force",
        ],
    )

    entities_path = output_root / "relations_final" / "ohm_relation_entities.jsonl"
    hints_path = output_root / "relations_final" / "ohm_relation_hints.jsonl"

    assert force_result.exit_code == 0
    assert entities_path.exists()
    assert hints_path.exists()

    resume_result = runner.invoke(
        cli,
        [
            "collections",
            "egypt-relations-run",
            "--run-id",
            "egypt-run",
            "--output-root",
            str(output_root),
            "--resume",
        ],
    )

    assert resume_result.exit_code == 0
    assert "skipped" in resume_result.output.lower()


def test_run_egypt_build_assembles_candidates_from_the_xml_index(tmp_path: Path) -> None:
    source_path = tmp_path / "map.xml"
    source_path.write_text(
        """<?xml version='1.0' encoding='UTF-8'?>
<osm version="0.6" generator="pytest">
  <node id="100" lat="29.871" lon="31.205">
    <tag k="name" v="Upper Egypt Shrine" />
  </node>
  <relation id="300">
    <member type="node" ref="100" role="label" />
    <tag k="name" v="Kingdom of Egypt" />
    <tag k="wikidata" v="Q456" />
    <tag k="type" v="boundary" />
  </relation>
</osm>
""",
        encoding="utf-8",
    )
    xml_index_path = tmp_path / "map.sqlite3"
    output_root = tmp_path / "egypt-run"

    build_index(source_path, index_path=xml_index_path, force=True)

    result = collections_main_module.run_egypt_build(
        xml_index_path=xml_index_path,
        ohm_index_path=None,
        run_id="egypt-run",
        output_root=output_root,
        resume=False,
        force=True,
    )

    border_records = _read_jsonl(output_root / "borders_final" / "ohm_borders.jsonl")
    entity_records = _read_jsonl(output_root / "entities_final" / "egypt_collection.jsonl")

    assert result["status"] == "completed"
    assert [(record["name"], record["entity_group"], record["_ohm_relation_id"]) for record in border_records] == [
        ("Kingdom of Egypt", "POLITY", "300"),
    ]
    assert [
        (record["name"], record["entity_type"], record["entity_group"], record["_geometry_source"])
        for record in entity_records
    ] == [
        ("Upper Egypt Shrine", "infrastructure_monument", "PLACE", "ohm_point"),
    ]


def test_run_egypt_relations_generates_relation_entity_contract_files(tmp_path: Path, monkeypatch) -> None:
    output_root = tmp_path / "egypt-run"
    borders_dir = output_root / "borders_final"
    reports_dir = output_root / "reports"
    borders_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    (borders_dir / "ohm_borders.jsonl").write_text(
        json.dumps(
            {
                "name": "Kingdom of Egypt",
                "entity_type": "political_entity",
                "entity_group": "POLITY",
                "wikidata_id": "Q456",
                "_ohm_relation_id": "300",
                "_geometry_periods": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (reports_dir / "included.jsonl").write_text(
        json.dumps(
            {
                "name": "Kingdom of Egypt",
                "wikidata_id": "Q456",
                "entity_types": ["political_entity"],
                "reasons": ["lexical_match"],
                "ambiguity": [],
                "geometry_source": "none",
                "raw_tags": {
                    "name": "Kingdom of Egypt",
                    "wikidata": "Q456",
                    "predecessor": "Old Kingdom of Egypt",
                    "predecessor:wikidata": "Q123",
                },
                "_ohm_object_type": "relation",
                "_ohm_object_id": 300,
            }
        )
        + "\n"
        + json.dumps(
            {
                "name": "Upper Egypt Shrine",
                "wikidata_id": "Q999",
                "entity_types": ["place"],
                "reasons": ["lexical_match"],
                "ambiguity": [],
                "geometry_source": "ohm_point",
                "raw_tags": {
                    "name": "Upper Egypt Shrine",
                    "wikidata": "Q999",
                    "successor": "Shrine Restoration",
                    "successor:wikidata": "Q777",
                },
                "_ohm_object_type": "node",
                "_ohm_object_id": 100,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    def fake_enrich_relation_candidates(candidates, **_kwargs):
        enriched = []
        for candidate in candidates:
            target_qid = candidate.get("target_wikidata_id")
            target_label = candidate.get("target_label")
            if target_qid == "Q123":
                target_entity = {
                    "name": "Old Kingdom of Egypt",
                    "entity_type": "political_entity",
                    "entity_group": "POLITY",
                    "wikidata_id": "Q123",
                    "summary": None,
                    "alternative_names": [],
                    "temporal_start": None,
                    "temporal_end": None,
                    "verification_status": "pipeline_draft",
                    "confidence": "medium",
                    "source_citations": [{"source": "wikidata", "wikidata_id": "Q123"}],
                }
            else:
                target_entity = {
                    "name": target_label,
                    "entity_type": "infrastructure_monument",
                    "entity_group": "PLACE",
                    "wikidata_id": target_qid,
                    "summary": None,
                    "alternative_names": [],
                    "temporal_start": None,
                    "temporal_end": None,
                    "verification_status": "pipeline_draft",
                    "confidence": "medium",
                    "source_citations": [{"source": "wikidata", "wikidata_id": target_qid}],
                }
            enriched.append(
                {
                    **candidate,
                    "relationship_type": candidate.get("relationship_type"),
                    "source": "wikidata:P155" if candidate.get("relationship_type") == "preceded_by" else "wikidata:P156",
                    "target_entity": target_entity,
                }
            )
        return enriched

    monkeypatch.setattr(collections_main_module, "enrich_relation_candidates", fake_enrich_relation_candidates)

    result = collections_main_module.run_egypt_relations(
        run_id="egypt-run",
        output_root=output_root,
        resume=False,
        force=True,
    )

    entity_records = _read_jsonl(output_root / "relations_final" / "ohm_relation_entities.jsonl")
    hint_records = _read_jsonl(output_root / "relations_final" / "ohm_relation_hints.jsonl")

    assert result["status"] == "completed"
    assert [(record["name"], record["entity_type"], record["entity_group"], record["wikidata_id"]) for record in entity_records] == [
        ("Old Kingdom of Egypt", "political_entity", "POLITY", "Q123"),
        ("Shrine Restoration", "infrastructure_monument", "PLACE", "Q777"),
    ]
    assert hint_records == [
        {
            "source_wikidata_id": "Q456",
            "source_name": "Kingdom of Egypt",
            "relationship_type": "preceded_by",
            "target_wikidata_id": "Q123",
            "target_label": "Old Kingdom of Egypt",
            "temporal_start": None,
            "temporal_end": None,
            "confidence": "medium",
            "source": "wikidata:P155",
        },
        {
            "source_wikidata_id": "Q999",
            "source_name": "Upper Egypt Shrine",
            "relationship_type": "succeeded_by",
            "target_wikidata_id": "Q777",
            "target_label": "Shrine Restoration",
            "temporal_start": None,
            "temporal_end": None,
            "confidence": "medium",
            "source": "wikidata:P156",
        },
    ]