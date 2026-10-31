"""C2c date tolerance and text years."""
import pytest

from pipeline.audit.dates import compare_dates, text_years, tolerance


def test_tolerances():
    assert tolerance("person") == 5
    assert tolerance("event_battle") == 2
    assert tolerance("political_entity") == 25
    assert tolerance("city") is None


def test_person_within_tolerance():
    out = compare_dates("person", 1765, 1844, {"P569": [1763, 11], "P570": [1844, 11]})
    assert out["verdict"] == "ok"


def test_person_death_twenty_years_off_is_out_of_tolerance():
    # the postmaster Drouet (1763-1824) vs the comte d'Erlon (1765-1844)
    out = compare_dates("person", 1765, 1844, {"P569": [1763, 11], "P570": [1824, 11]})
    assert out["verdict"] == "out_of_tolerance"
    assert out["off"] == 15


def test_namesake_other_era_is_conflict():
    # Bülow von Dennewitz (1755-1816) vs the conductor Hans von Bülow (1830-1894)
    out = compare_dates("person", 1755, 1816, {"P569": [1830, 11], "P570": [1894, 11]})
    assert out["verdict"] == "conflict"


def test_event_tolerance_and_conflict():
    assert compare_dates("event_battle", -480, -480, {"P585": [-480, 9]})["verdict"] == "ok"
    assert compare_dates("event_battle", -480, -480, {"P585": [-477, 9]})["verdict"] == "out_of_tolerance"
    assert compare_dates("event_battle", -306, -306, {"P585": [-480, 9]})["verdict"] == "conflict"


def test_polity_tolerance():
    assert compare_dates("political_entity", -264, -146, {"P571": [-250, 9], "P576": [-146, 9]})["verdict"] == "ok"
    # Hellenic League: row 323 BCE, QID 481 BCE
    assert compare_dates("political_entity", -323, -322, {"P571": [-481, 9]})["verdict"] == "conflict"


def test_sign_flip_is_reported_as_sign():
    assert compare_dates("person", 356, 323, {"P569": [-356, 9], "P570": [-323, 9]})["verdict"] == "sign"


def test_century_precision_widens_tolerance():
    assert compare_dates("person", -60, 10, {"P569": [-100, 7], "P570": [100, 7]})["verdict"] == "ok"


def test_untyped_and_undated_are_unknown():
    assert compare_dates("city", 100, 200, {"P571": [-3000, 9]})["verdict"] == "unknown"
    assert compare_dates("person", None, None, {"P569": [1800, 9]})["verdict"] == "unknown"


@pytest.mark.parametrize("text,years", [
    ("Naval battle in September 480 BCE where the Greek fleet won.", [-480]),
    ("Founded AD 9 and sacked in 410 CE.", [9, 410]),
    ("German conductor who led the premiere in Munich in 1865.", [1865]),
    ("Fought 1500–1400 BC along the river.", [-1400, -1500]),
    ("An army of 3,000 soldiers and 1500 men.", []),
])
def test_text_years(text, years):
    assert sorted(text_years(text)) == sorted(years)
