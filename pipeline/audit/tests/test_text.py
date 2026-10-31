"""C6 text checks and open-ended row ranges."""
from pipeline.audit.dates import row_range
from pipeline.audit.tests.conftest import make_row
from pipeline.audit.text import head_kind, text_flags


def test_head_kind():
    assert head_kind("Naval battle in September 480 BCE where the Greeks won")[0] == "battle"
    assert head_kind("German conductor who led the premiere of Tristan")[0] == "person"
    assert head_kind("Church of the East monk who reached Chang'an")[0] == "person"
    assert head_kind("Antonio José de Sucre defeated Viceroy José de la Serna at Ayacucho")[0] is None


def test_row_range_reads_missing_bounds_as_open():
    assert row_range("political_entity", 927, None)[0] == 927 and row_range("political_entity", 927, None)[1] > 3000
    assert row_range("event_battle", -480, None) == (-480, -480)
    assert row_range("person", None, 1685) == (1585, 1685)
    assert row_range("city", None, None) is None


def test_text_flags():
    rows = [make_row("Ptolemy", start=-367, end=-282, id="p",
                     summary="Greek geographer and astronomer (90–168 CE) of Alexandria."),
            make_row("Battle of X", "event_battle", start=-216, end=-216, id="b",
                     summary="City in Apulia where Hannibal camped in 216 BCE."),
            make_row("A", "city", id="c1", summary="Lombard city that joined the Lombard League in 1167 against Barbarossa."),
            make_row("B", "city", id="c2", summary="Lombard city that joined the Lombard League in 1167 against Barbarossa.")]
    checks = {(f["entity_id"], f["check"]) for f in text_flags(rows)}
    assert checks == {("p", "text_era"), ("b", "text_type"), ("c1", "dup_text"), ("c2", "dup_text")}
