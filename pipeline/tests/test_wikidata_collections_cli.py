from click.testing import CliRunner

from pipeline.ohm_collections.__main__ import cli


def test_egypt_wikidata_build_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["egypt-wikidata-build", "--help"])
    assert result.exit_code == 0
    assert "egypt-wikidata-build" in result.output


def test_egypt_wikidata_build_runs_with_dry_run(monkeypatch) -> None:
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

    runner = CliRunner()
    result = runner.invoke(cli, ["egypt-wikidata-build", "--run-id", "test-egypt", "--no-expansion"])
    assert result.exit_code == 0
    assert "Wrote" in result.output
