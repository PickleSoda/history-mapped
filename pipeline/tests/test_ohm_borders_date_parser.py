from pipeline.ohm_borders.date_parser import from_ohm_year, parse_end_year, parse_start_year


def test_full_date_ce() -> None:
    assert parse_start_year("1908-10-05") == 1908


# OHM numbers years astronomically: 0000 is 1 BCE, -0499 is 500 BCE.
def test_full_date_bce() -> None:
    assert parse_start_year("-0499-01-01") == -500


def test_year_zero_is_1_bce() -> None:
    assert parse_start_year("0000") == -1
    assert parse_end_year("-0001") == -2


def test_from_ohm_year() -> None:
    assert [from_ohm_year(y) for y in (-43, 0, 1, 1453)] == [-44, -1, 1, 1453]


def test_year_only() -> None:
    assert parse_start_year("1908") == 1908
    assert parse_end_year("1908") == 1908


def test_partial_year_month_start() -> None:
    assert parse_start_year("1908-10") == 1908


def test_partial_year_month_end() -> None:
    assert parse_end_year("1908-10") == 1908


def test_none_returns_none() -> None:
    assert parse_start_year(None) is None
    assert parse_end_year(None) is None


def test_empty_returns_none() -> None:
    assert parse_start_year("") is None


def test_deeply_bce() -> None:
    assert parse_start_year("-2999") == -3000
