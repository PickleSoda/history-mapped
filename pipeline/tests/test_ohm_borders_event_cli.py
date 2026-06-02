"""Tests for OHM border event CLI commands."""

from click.testing import CliRunner

from pipeline.ohm_borders.__main__ import cli


def test_events_scan_command_exists() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["events-scan", "--help"])
    assert result.exit_code == 0
    assert "events-scan" in result.output


def test_events_enrich_command_exists() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["events-enrich", "--help"])
    assert result.exit_code == 0
    assert "events-enrich" in result.output


def test_events_build_command_exists() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["events-build", "--help"])
    assert result.exit_code == 0
    assert "events-build" in result.output


def test_events_run_command_exists() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["events-run", "--help"])
    assert result.exit_code == 0
    assert "events-run" in result.output