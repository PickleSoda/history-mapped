"""Person date backfill: life dates from Wikidata's qualified statements and the enwiki lead, never a reign."""

import pytest

from pipeline.backfill_person_dates import (
    finish_plan,
    lead_groups,
    parse_claims,
    parse_lead,
    pick_wd,
    plan_person,
    wd_values,
    write_rollback,
)


# ── helpers ──────────────────────────────────────────────────────────────────
def t(time: str, precision: int = 9) -> dict:
    return {"datavalue": {"value": {"time": time, "precision": precision}}, "snaktype": "value"}


def st(time: str | None, precision: int = 9, rank: str = "normal", earliest: str | None = None,
       latest: str | None = None, circa: bool = False) -> dict:
    """A raw wbgetentities time statement (time None = unknown value)."""
    snak = {"snaktype": "somevalue"} if time is None else {"snaktype": "value", "datavalue": {
        "type": "time", "value": {"time": time, "precision": precision}}}
    s: dict = {"rank": rank, "mainsnak": snak, "qualifiers": {}}
    if earliest:
        s["qualifiers"]["P1319"] = [t(earliest)]
    if latest:
        s["qualifiers"]["P1326"] = [t(latest)]
    if circa:
        s["qualifiers"]["P1480"] = [{"datavalue": {"value": {"id": "Q5727902"}}}]
    return s


def item(**props) -> dict:
    return parse_claims({"claims": {p: v if isinstance(v, list) else [v] for p, v in props.items()}})


def person(**kw) -> dict:
    return {"entity_id": "e1", "name": "X", "entity_type": "person", "wikidata_id": "Q1",
            "verification_status": "pipeline_draft", "flags": [], "range_id": None,
            "row_end_year": None, "row_end_date": None, "date_confidence": None, **kw}


def plan(e: dict, rec: dict, extract: str = "", facts=(), hand: str | None = "ok", excluded=None) -> dict:
    lead = parse_lead(extract) if extract else None
    return plan_person(e, rec, lead, extract, list(facts), excluded, hand)


EMPTY = item()


# ── the lead's parentheses ────────────────────────────────────────────────────
@pytest.mark.parametrize("extract, birth, death, clean", [
    ("Al-Qadir (28 September 947 – 29 November 1031) was the caliph", 947, 1031, True),
    ("Bai Qi (Chinese: 白起; c. 332 – c. January 257 BC) was a general", -332, -257, False),
    ("Princess Jieyou (Chinese: 解忧公主; 121 BC – 49 BC), born Liu Jieyou, was", -121, -49, True),
    ("Ammar (c. 567/570 – July 657 CE) was", 567, 657, False),
    ("Wat Tyler (1341 or c. 1320 – 15 June 1381) was", 1320, 1381, False),
    ("Jacques de Molay (French: [də mɔlɛ]; c. 1240–1250 – 11 or 18 March 1314), also", 1240, 1314, False),
    ("Chen Fan (90s - 25 October 168), courtesy name", 90, 168, False),
    ("Himiko (c. 170–247/248 AD) was", 170, 248, False),
    ("Demasq Kaja (Mongolian: ᠳᠢᠮᠢᠱ, romanized: Dimiš Qoǰa, 1300 - August 24, 1327) was", 1300, 1327, False),
    ("Leonidas I (born c. 540 BC, died 11 August 480 BC) was", -540, -480, False),
    ("Mek Nimr (c. 1785 to 1846) was", 1785, 1846, False),
])
def test_life_ranges(extract, birth, death, clean) -> None:
    p = parse_lead(extract)
    assert p["kind"] == "life"
    assert (p["birth"], p["death"], p["clean"]) == (birth, death, clean)


def test_a_birth_range_is_stored_as_its_earliest_year_and_a_death_range_as_its_latest() -> None:
    assert parse_lead("Zufar (Arabic: x; died c. 694–695) was")["death"] == 695
    assert parse_lead("Hiarbas (died 82/81 BC), also")["death"] == -81
    assert parse_lead("Quao (d. c. 1750s) was")["death"] == 1750  # a decade keeps its label year


@pytest.mark.parametrize("extract, kind, death", [
    ("Shawar (Arabic: شاور; died 18 January 1169) was", "died", 1169),
    ("Luh-ishan (𒇻𒄴𒅖𒀭 lu-uh-ish-an, also x; died c. 2325 BC) was", "died", -2325),
    ("Uchaʼan Kʼin Bʼalam (died on May 28, 741) was", "died", 741),
    ("Faris al-Din Aktay (Arabic: x; d. 1254, Cairo) was", "died", 1254),
    ("Antiochus Hierax (; killed c. 226 BC) was", "died", -226),
    ("Chu Đạt (Chinese: 朱達; ?–160) was", "life", 160),
])
def test_death_only(extract, kind, death) -> None:
    p = parse_lead(extract)
    assert (p["kind"], p["birth"], p["death"]) == (kind, None, death)


@pytest.mark.parametrize("extract, kind", [
    ("Köten (Russian: Котян; fl. 1205–1241) was", "floruit"),
    ("Mithridates I of Pontus (Greek: x; reigned 281–266 BC) was", "reign"),
    ("Asharaja (IAST: Āśārāja, r. c. 1110–1119 CE) was", "reign"),
    ("Ezra (fl. fifth or fourth century BCE) was", "floruit"),
])
def test_floruit_and_reign_are_never_a_life(extract, kind) -> None:
    p = parse_lead(extract)
    assert p["kind"] == kind and p["birth"] is None and p["death"] is None


@pytest.mark.parametrize("extract", [
    "Nasir ad-Din Mahmud (died 18 years old) was",          # an age, not a year
    "Devapala of Bengal (c. 9th century) was",              # a century
    "Gindibu (Akkadian: x; c. 853 BCE) was",                # one year alone: life or floruit?
    "Abimilki (Amorite: x) around 1347 BC held the rank of Prince of Tyre, during the "
    "period of the Amarna letters correspondence (1360–1332 BC).",  # a later parenthesis is not the life
])
def test_no_life_dates(extract) -> None:
    p = parse_lead(extract)
    assert p["birth"] is None and p["death"] is None


def test_several_life_pieces_are_ambiguous() -> None:
    assert parse_lead("Yasovarman (889 - 910; 1160 - 1166; c. 725 – 752) may refer to")["kind"] == "ambiguous"


def test_one_sided_bounds_and_unknown_sides_are_marked() -> None:
    p = parse_lead("Chares of Lindos (; Ancient Greek: x; before 305 BC – c.280 BC) was")
    assert p["birth"] == -305 and "bound" in p["b_why"]
    p = parse_lead("Tiberius Sempronius Longus (c. 260 BC – unknown) was")
    assert (p["birth"], p["death"], p["flags"]) == (-260, None, ["unknown_side"])
    p = parse_lead("Pothinus (Ancient Greek: x; early 1st century BC – 48 or 47 BC) was")
    assert (p["birth"], p["death"]) == (None, -47) and "coarse_side" in p["flags"]


def test_era_on_the_start_only_is_flagged() -> None:
    p = parse_lead("Augustus (63 BC – 14) was")
    assert (p["birth"], p["death"]) == (-63, 14) and "era_ambiguous" in p["flags"] and not p["clean"]


def test_lead_groups_stop_at_the_verb() -> None:
    assert lead_groups("A (x; 1 – 2) was a king (r. 5–9).") == ["x; 1 – 2"]


# ── Wikidata's qualified statements ──────────────────────────────────────────
def test_an_unknown_birth_with_a_narrow_earliest_latest_pair_gives_its_earliest_year() -> None:
    rec = item(P569=st(None, earliest="+0810-00-00T00:00:00Z", latest="+0813-00-00T00:00:00Z"))
    b, why = pick_wd(wd_values(rec["dates"]["P569"]), "birth")
    assert (b["year"], b["conf"], why) == (810, "low", "")


def test_a_one_sided_or_wide_bound_is_only_a_limit() -> None:
    for s in (st(None, latest="-0520-00-00T00:00:00Z"),
              st(None, earliest="+1450-00-00T00:00:00Z", latest="+1503-00-00T00:00:00Z"),
              st("+1300-00-00T00:00:00Z", 7)):
        assert pick_wd(wd_values(item(P569=s)["dates"]["P569"]), "birth") == (None, "limits_only")
    assert pick_wd(wd_values(item(P569=st(None))["dates"]["P569"]), "birth") == (None, "unknown")


def test_statements_more_than_five_years_apart_conflict() -> None:
    rec = item(P569=[st(None, earliest="+0545-00-00T00:00:00Z", latest="+0550-00-00T00:00:00Z"),
                     st("+0534-00-00T00:00:00Z", circa=True)])
    assert pick_wd(wd_values(rec["dates"]["P569"]), "birth") == (None, "conflict")


# ── planning ─────────────────────────────────────────────────────────────────
def test_a_lead_life_fills_an_existing_row_and_keeps_its_end() -> None:
    e = person(range_id="r1", row_end_year=1336, row_end_date="1336-07-04")
    p = plan(e, EMPTY, "Kusunoki Masashige (Japanese: x, 1294 – 4 July 1336) was")
    assert p["action"] == "update"
    assert (p["start"], p["end"], p["start_date"], p["end_date"]) == (1294, 1336, "1294", "1336-07-04")
    assert (p["confidence"], p["method"], p["start_src"], p["end_src"]) == ("medium", "nlp_direct", "enwiki", "row")


def test_circa_is_low_and_nlp_approximate() -> None:
    p = plan(person(), EMPTY, "Robert the Strong (c. 830 – 866) was")
    assert (p["action"], p["start"], p["end"], p["confidence"], p["method"]) == (
        "insert", 830, 866, "low", "nlp_approximate")


def test_every_lead_parse_waits_for_a_hand_check_and_a_reject_wins() -> None:
    assert plan(person(), EMPTY, "Bijjala II (1130–1167 CE) was", hand=None)["reason"] == "awaiting_hand_check"
    assert plan(person(), EMPTY, "Bijjala II (1130–1167 CE) was",
                hand="reject:reign_not_life")["reason"] == "hand_check:reign_not_life"


def test_wikidata_comes_first_and_the_lead_only_refines_its_range() -> None:
    rec = item(P569=st(None, earliest="+0810-00-00T00:00:00Z", latest="+0813-00-00T00:00:00Z"))
    p = plan(person(), rec, "", hand=None)
    assert (p["start"], p["method"], p["start_src"]) == (810, "source_database", "P569-bounds")
    rec = item(P569=st("+0900-00-00T00:00:00Z", 7, earliest="+0815-00-00T00:00:00Z",
                       latest="+0830-00-00T00:00:00Z"), P570=st("+0866-00-00T00:00:00Z"))
    p = plan(person(), rec, "Robert the Strong (c. 830 – 866) was")
    assert (p["start"], p["start_src"], p["confidence"]) == (830, "enwiki+P569", "low")


def test_sources_that_disagree_skip() -> None:
    rec = item(P569=st(None, earliest="+0810-00-00T00:00:00Z", latest="+0813-00-00T00:00:00Z"))
    assert plan(person(), rec, "X (c. 830 – 866) was")["reason"] == "birth_sources_disagree"
    e = person(range_id="r1", row_end_year=850)
    assert plan(e, EMPTY, "X (c. 800 – 866) was")["reason"] == "death_sources_disagree"
    rec = item(P570=st("+0255-00-00T00:00:00Z"))
    assert plan(person(range_id="r1", row_end_year=244), rec)["reason"] == "row_end_disagrees_with_wikidata"


def test_a_value_wikidata_itself_doubts_needs_the_lead_to_agree() -> None:
    rec = item(P569=[st(None, rank="preferred"), st("+0646-00-00T00:00:00Z")], P570=st("+0685-00-00T00:00:00Z"))
    assert plan(person(), rec, hand=None)["reason"] == "wd_birth_in_doubt"
    assert plan(person(), rec, "Ecgfrith (c. 645 – 20 May 685) was")["start"] == 646
    rec = item(P569=st(None), P570=[st(None, earliest="+1217-00-00T00:00:00Z"), st("+1218-00-00T00:00:00Z")])
    assert plan(person(), rec, hand=None)["reason"] == "wd_death_in_doubt"  # Boril: deposed 1218, died after
    rec = item(P569=[st(None), st("-0542-00-00T00:00:00Z", rank="preferred", circa=True)],
               P570=st("-0485-00-00T00:00:00Z"))
    assert plan(person(), rec, hand=None)["start"] == -542  # the preferred value is Wikidata's answer


def test_floruit_and_reign_are_listed_not_stored() -> None:
    p = plan(person(), item(P1317=st("+1200-00-00T00:00:00Z")), "Köten (fl. 1205–1241) was")
    assert (p["action"], p["reason"]) == ("list", "floruit_or_reign_only")
    assert "WD fl. 1200" in p["floruit"] and "fl. 1205–1241" in p["floruit"]


def test_a_birth_equal_to_a_reign_start_is_a_reign() -> None:
    facts = [(716, 746, "rel rules → Mataram")]
    assert plan(person(), EMPTY, "Sanjaya (716 – 746) was", facts=facts)["reason"] == "birth_is_reign_start"


def test_a_one_sided_bound_is_not_a_birth() -> None:
    p = plan(person(range_id="r1", row_end_year=1591), EMPTY, "E (born before 1558, died 25 June 1591) was")
    assert p["reason"].startswith("no_birth") and p["lead_note"] == "birth is a one-sided bound"


def test_death_only_fills_an_empty_end() -> None:
    p = plan(person(), EMPTY, "Shawar (died 18 January 1169) was")
    assert (p["action"], p["reason"], p["start"], p["end"], p["start_date"]) == ("insert", "end_only", None, 1169, None)
    assert plan(person(range_id="r1", row_end_year=1169), EMPTY, "Shawar (died 1169) was")["reason"].startswith(
        "no_birth")


def test_lifespan_rules() -> None:
    assert plan(person(), EMPTY, "X (625 – 855 CE) was")["reason"] == "lifespan_over_120"
    assert plan(person(), EMPTY, "X (born 1294) was")["reason"] == "no_death_date"
    assert plan(person(), EMPTY, "X (born 5 August 1985) is")["action"] == "insert"
    assert "short_life" in plan(person(), EMPTY, "Haydar Mirza (1585-1596) was")["flags"]


def test_the_persons_own_facts_must_fit() -> None:
    assert plan(person(), EMPTY, "X (1294 – 1336) was",
                facts=[(1280, 1290, "rel rules → Y")])["reason"] == "start_after_evidence"
    assert plan(person(), EMPTY, "X (1294 – 1336) was",
                facts=[(1500, 1500, "chronicle")])["reason"] == "lifespan_misses_evidence"


def test_doubtful_qids_and_other_agents_entities_are_skipped() -> None:
    e = person(verification_status="needs_review", flags=["identity_audit:qid_suspect"])
    assert plan(e, EMPTY, "X (1294 – 1336) was")["reason"] == "qid_in_doubt"
    assert plan(person(), EMPTY, "X (1294 – 1336) was", excluded="excluded:merge_review")["reason"] == (
        "excluded:merge_review")


def test_rollback_deletes_inserts_and_restores_updates(tmp_path) -> None:
    ins_e = person(entity_id="e1")
    ins = finish_plan(ins_e, plan(ins_e, EMPTY, "X (1294 – 1336) was"))
    upd_e = person(entity_id="e2", range_id="r2", row_end_year=1336, row_end_date="1336", date_method=None,
                   notes=None, duration_type=None, updated_at="2026-10-05 17:17:17")
    upd = finish_plan(upd_e, plan(upd_e, EMPTY, "X (1294 – 1336) was"))
    assert ins["notes"] == "backfill_person_dates:enwiki,enwiki" and ins["duration_type"] == "period"
    write_rollback(tmp_path / "rollback.sql", [(ins_e, ins), (upd_e, upd)])
    sql = (tmp_path / "rollback.sql").read_text()
    assert f"DELETE FROM entity_temporal_ranges WHERE notes LIKE 'backfill_person_dates:%' " \
           f"AND temporal_range_id IN ('{ins['range_id']}')" in sql
    assert ("SET start_date = NULL, end_date = '1336', date_method = NULL, date_confidence = NULL, "
            "notes = NULL, duration_type = NULL, updated_at = '2026-10-05 17:17:17' "
            "WHERE temporal_range_id = 'r2' AND notes LIKE 'backfill_person_dates:%'") in sql
