"""Tests for the coalition geo-ref skip in resolve_ohm."""
from __future__ import annotations

from pipeline.agent.graph.nodes.resolve_ohm import _is_coalition


def test_detects_coalitions():
    for name in (
        "Allied Powers",
        "Central Powers",
        "Axis",
        "Triple Entente",
        "Triple Alliance",
        "Delian League",
        "Holy League",
        "League of Corinth",
        "Eight-Nation Alliance",
        "Grand Alliance",
    ):
        assert _is_coalition(name), name


def test_does_not_flag_real_states():
    for name in (
        "Soviet Union",
        "Roman Empire",
        "Achaemenid Empire",
        "Kingdom of Prussia",
        "Byzantine Empire",
        "United States",
        "Holy Roman Empire",
    ):
        assert not _is_coalition(name), name
