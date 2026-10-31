"""C2b: same-name places (no network)."""
from pipeline.audit.places import place_words, text_mentions


def test_place_words():
    assert place_words("town and port in Lincolnshire, England, UK") == {"lincolnshire", "england"}
    assert place_words("city in Minnesota, United States") == {"minnesota"}
    assert place_words("") == set()


def test_text_mentions_whole_words():
    text = "Major Puritan city founded by John Winthrop in 1630 as the center of Massachusetts Bay Colony."
    assert text_mentions(text, {"massachusetts"})
    assert not text_mentions(text, {"lincolnshire", "england"})
