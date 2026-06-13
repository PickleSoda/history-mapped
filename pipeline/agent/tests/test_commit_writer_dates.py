"""Tests for commit_writer's date-consistency guard."""
from __future__ import annotations

from pipeline.agent.graph.nodes.commit_writer import _consistent_dates


def test_drops_end_when_a_ce_year_was_mis_signed_negative():
    # The Justinian/Opium-War regression: a CE date emitted negative leaves
    # start_year > end_year. Drop the end so the entity still imports.
    assert _consistent_dates("-527", "-565") == ("-527", None)


def test_keeps_valid_bce_range():
    assert _consistent_dates("2112 BCE", "2095 BCE") == ("-2112", "-2095")


def test_keeps_valid_ce_range():
    # CE markers are stripped to a clean year by normalize_historical_date.
    assert _consistent_dates("527 CE", "565 CE") == ("527", "565")


def test_passes_through_nones_and_singletons():
    assert _consistent_dates(None, None) == (None, None)
    assert _consistent_dates("1453", None) == ("1453", None)
