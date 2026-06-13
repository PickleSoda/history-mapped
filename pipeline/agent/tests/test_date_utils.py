"""Tests for historical date normalization."""
from __future__ import annotations

import pytest

from pipeline.agent.date_utils import normalize_historical_date


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("2112 BCE", "-2112"),
        ("2095 BC", "-2095"),
        ("334 bce", "-334"),
        ("c. 1200 BCE", "-1200"),
        ("1453 CE", "1453"),                                 # strip CE marker
        ("1933 CE", "1933"),
        ("476 AD", "476"),                                   # strip AD marker
        ("1453", "1453"),
        ("1945-04-30T00:00:00Z", "1945-04-30"),              # strip ISO time
        ("-0334-01-01T00:00:00Z", "-0334-01-01"),            # signed ISO, time dropped
        ("+0476-01-01T00:00:00Z", "0476-01-01"),             # strip leading + and time
        ("1453-05-29", "1453-05-29"),
        (None, None),
        ("", ""),
    ],
)
def test_normalize_historical_date(raw, expected):
    assert normalize_historical_date(raw) == expected


def test_bce_range_orders_correctly():
    # The Ur-Nammu failure: a BCE reign must yield start_year <= end_year.
    start = normalize_historical_date("2112 BCE")
    end = normalize_historical_date("2095 BCE")
    assert int(start) <= int(end)  # -2112 <= -2095
