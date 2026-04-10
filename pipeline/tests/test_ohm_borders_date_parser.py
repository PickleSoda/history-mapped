from pipeline.ohm_borders.date_parser import parse_start_year, parse_end_year


def test_full_date_ce() -> None:
    assert parse_start_year("1908-10-05") == 1908


def test_full_date_bce() -> None:
    assert parse_start_year("-0500-01-01") == -500


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
    assert parse_start_year("-3000") == -3000
