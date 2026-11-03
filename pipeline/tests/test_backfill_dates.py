"""Date backfill: which of an item's own Wikidata dates an undated entity gets, and when it gets none."""

from pipeline.backfill_dates import (
    date_text,
    interval,
    parse_claims,
    plan_entity,
    write_rollback,
)


def st(time: str, precision: int = 9, rank: str = "normal", circa: bool = False, **quals: str) -> dict:
    """A raw wbgetentities time statement; quals are item-valued qualifiers (P518="Q486972")."""
    s = {"rank": rank, "mainsnak": {"snaktype": "value", "datavalue": {
        "type": "time", "value": {"time": time, "precision": precision}}}}
    if circa:
        quals["P1480"] = "Q5727902"
    if quals:
        s["qualifiers"] = {p: [{"datavalue": {"value": {"id": q}}}] for p, q in quals.items()}
    return s


def unknown() -> dict:
    return {"rank": "normal", "mainsnak": {"snaktype": "somevalue"}}


def item(**props) -> dict:
    return parse_claims({"claims": {p: v if isinstance(v, list) else [v] for p, v in props.items()}})


def entity(entity_type: str = "political_entity", **kw) -> dict:
    return {"entity_id": "e1", "name": "X", "entity_type": entity_type, "wikidata_id": "Q1",
            "verification_status": "pipeline_draft", "flags": [], "range_id": None,
            "row_end_year": None, "row_end_date": None, **kw}


def plan(e: dict, claims: dict, facts=(), former: bool = False) -> dict:
    return plan_entity(e, claims, former, list(facts))


# ── precision ────────────────────────────────────────────────────────────────
def test_year_precision_is_stored_as_is_with_high_confidence() -> None:
    p = plan(entity(), item(P571=st("+1282-00-00T00:00:00Z"), P576=st("+1453-05-29T00:00:00Z", 11)))
    assert p["action"] == "insert"
    assert (p["start"], p["end"], p["start_date"], p["end_date"]) == (1282, 1453, "1282", "1453-05-29")
    assert p["confidence"] == "high" and p["start_prop"] == "P571" and p["end_prop"] == "P576"


def test_decade_is_stored_with_low_confidence_and_century_is_skipped() -> None:
    decade = plan(entity("city"), item(P571=st("+1530-00-00T00:00:00Z", 8)))
    assert decade["start"] == 1530 and decade["confidence"] == "low"
    century = plan(entity("city"), item(P571=st("+1200-00-00T00:00:00Z", 7)))
    assert century["action"] == "skip" and century["reason"] == "start_coarse:P571"


def test_a_coarse_end_skips_rather_than_leaving_the_entity_open() -> None:
    p = plan(entity(), item(P571=st("+1100-00-00T00:00:00Z"), P576=st("+1500-00-00T00:00:00Z", 7)))
    assert p["action"] == "skip" and p["reason"] == "end_coarse:P576"


def test_circa_lowers_confidence_to_medium() -> None:
    p = plan(entity("city"), item(P571=st("+1150-00-00T00:00:00Z", circa=True)))
    assert p["start"] == 1150 and p["confidence"] == "medium"


# ── BCE ──────────────────────────────────────────────────────────────────────
def test_bce_years_keep_wikidatas_sign_and_numbering() -> None:
    p = plan(entity("person"), item(P569=st("-0100-07-12T00:00:00Z", 11), P570=st("-0044-03-15T00:00:00Z", 11)))
    assert (p["start"], p["end"]) == (-100, -44)  # Julius Caesar: the DB stores 44 BCE as -44
    assert (p["start_date"], p["end_date"]) == ("-0100-07-12", "-0044-03-15")
    assert date_text({"y": -490, "p": 9, "t": "-0490-00-00T00:00:00Z"}) == "-490"


def test_bce_decades_and_centuries_cover_the_right_years() -> None:
    assert interval(-480, 8) == (-489, -480)   # the 480s BCE
    assert interval(1530, 8) == (1530, 1539)
    assert interval(-500, 7) == (-500, -401)   # 5th century BCE
    assert interval(1500, 7) == (1401, 1500)   # 15th century


# ── rank and conflicts ───────────────────────────────────────────────────────
def test_values_more_than_ten_years_apart_conflict_whatever_their_rank() -> None:
    germany = item(P571=[st("+1871-01-18T00:00:00Z", 11, "preferred"), st("+1949-05-23T00:00:00Z", 11)])
    p = plan(entity(), germany)
    assert p["action"] == "skip" and p["reason"] == "start_conflict:P571"


def test_preferred_rank_wins_among_close_values_and_deprecated_ones_are_ignored() -> None:
    claims = item(P571=[st("+1236-00-00T00:00:00Z"), st("+1240-00-00T00:00:00Z", rank="preferred"),
                        st("+1900-00-00T00:00:00Z", rank="deprecated")])
    p = plan(entity("city"), claims)
    assert p["start"] == 1240 and p["confidence"] == "medium"  # the values disagree by 4 years


def test_alternative_properties_must_agree() -> None:
    p = plan(entity(), item(P571=st("+1918-00-00T00:00:00Z"), P580=st("+1100-00-00T00:00:00Z"),
                            P576=st("+1941-00-00T00:00:00Z")))
    assert p["action"] == "skip" and p["reason"] == "start_prop_conflict:P571/P580"


def test_an_unknown_value_beside_a_known_one_skips() -> None:
    # Mahmud Khalji: P569 is both "unknown value" and 1436 (his accession year)
    p = plan(entity("person"), item(P569=[unknown(), st("+1436-00-00T00:00:00Z")], P570=st("+1469-00-00T00:00:00Z")))
    assert p["action"] == "skip" and p["reason"] == "start_unknown:P569"


def test_values_about_a_part_are_ignored_and_disputed_ones_never_stored() -> None:
    # Fayette NY: 1790 applies to the settlement, 1800 to the town
    fayette = item(P571=[st("+1790-00-00T00:00:00Z", P518="Q486972"), st("+1800-00-00T00:00:00Z", P518="Q15127012")])
    assert plan(entity("city"), fayette)["reason"] == "start_qualified:P571"
    kyoto = item(P571=[st("+0794-00-00T00:00:00Z"), st("+1889-04-01T00:00:00Z", 11, P518="Q1637706")])
    assert plan(entity("city"), kyoto)["start"] == 794  # the scoped modern date is no conflict
    disputed = item(P571=st("+1100-00-00T00:00:00Z", P1480="Q18912752"))
    assert plan(entity("city"), disputed)["reason"] == "start_qualified:P571"


def test_a_pre_1584_date_flagged_for_its_calendar_keeps_only_its_year() -> None:
    p = plan(entity("person"), item(P569=st("+1452-04-15T00:00:00Z", 11, P31="Q26961029"),
                                    P570=st("+1519-05-02T00:00:00Z", 11)))
    assert (p["start_date"], p["end_date"], p["confidence"]) == ("1452", "1519-05-02", "high")


def test_a_coarse_value_overlapping_a_precise_one_is_not_a_conflict() -> None:
    p = plan(entity("city"), item(P571=[st("+1147-00-00T00:00:00Z"), st("+1200-00-00T00:00:00Z", 7)]))
    assert p["action"] == "insert" and p["start"] == 1147


# ── the modern-inception guard ───────────────────────────────────────────────
def test_an_inception_later_than_the_entitys_own_facts_is_rejected() -> None:
    kingdom = item(P571=st("+1918-12-01T00:00:00Z", 11), P576=st("+1941-04-17T00:00:00Z", 11))
    facts = [(1100, 1125, "rel X rules →"), (1914, 1918, "chronicle war")]
    p = plan(entity(), kingdom, facts)
    assert p["action"] == "skip" and p["reason"] == "start_after_evidence"
    assert p["earliest"].startswith("1125 rel")  # a span counts by its last year


def test_a_year_named_in_the_summary_counts_as_a_fact() -> None:
    p = plan(entity(), item(P571=st("+1991-00-00T00:00:00Z")), [(-331, -331, "summary")])
    assert p["action"] == "skip" and p["reason"] == "start_after_evidence"


def test_an_inception_before_every_fact_is_kept() -> None:
    p = plan(entity(), item(P571=st("+1282-00-00T00:00:00Z"), P576=st("+1453-00-00T00:00:00Z")),
             [(1300, 1302, "chronicle"), (1453, 1453, "rel conquered")])
    assert p["action"] == "insert" and p["earliest"].startswith("1302")


def test_an_end_centuries_before_the_entitys_facts_is_an_older_namesake() -> None:
    p = plan(entity(), item(P571=st("+1217-00-00T00:00:00Z"), P576=st("+1346-00-00T00:00:00Z")),
             [(1882, 1918, "rel rules"), (1900, 1900, "summary")])
    assert p["action"] == "skip" and p["reason"] == "end_before_evidence"


def test_an_end_before_the_entitys_own_facts_is_rejected() -> None:
    # Brigantes: Wikidata ends them in 60 CE; the DB has Cerialis campaigning against them in 71
    p = plan(entity(), item(P580=st("-0470-00-00T00:00:00Z"), P582=st("+0060-00-00T00:00:00Z")),
             [(71, 71, "rel fought_at")])
    assert p["action"] == "skip" and p["reason"] == "end_before_evidence"


def test_a_work_far_older_than_anything_known_about_it_is_a_namesake() -> None:
    # "On the Sphere" (al-Bitruji, translated 1217) linked to Archimedes' On the Sphere and Cylinder
    p = plan(entity("cultural_work"), item(P577=st("-0225-00-00T00:00:00Z")), [(1217, 1217, "chronicle")])
    assert p["action"] == "skip" and p["reason"] == "start_far_before_evidence"


def test_a_lifespan_that_touches_no_fact_is_another_person() -> None:
    p = plan(entity("person"), item(P569=st("+1100-00-00T00:00:00Z"), P570=st("+1160-00-00T00:00:00Z")),
             [(1450, 1460, "rel fought_at")])
    assert p["action"] == "skip" and p["reason"] == "lifespan_misses_evidence"


# ── open ends ────────────────────────────────────────────────────────────────
def test_open_ends_only_for_things_that_may_still_exist() -> None:
    assert plan(entity("city"), item(P571=st("+1703-05-27T00:00:00Z", 11)))["end"] is None
    assert plan(entity("city"), item(P571=st("-0700-00-00T00:00:00Z")), former=True)["reason"] == "no_end_former"
    assert plan(entity(), item(P571=st("+1100-00-00T00:00:00Z")), former=True)["reason"] == "no_end_former"
    assert plan(entity("dynasty"), item(P571=st("+1100-00-00T00:00:00Z")))["reason"] == "no_end_date"
    assert plan(entity("person"), item(P569=st("+1801-00-00T00:00:00Z")))["reason"] == "no_death_date"
    assert plan(entity("person"), item(P569=st("+1801-00-00T00:00:00Z"), P570=unknown()))["reason"] == "death_unknown"
    assert plan(entity("city"), item(P571=st("+1100-00-00T00:00:00Z"), P576=unknown()))["reason"] == "end_unknown"


def test_events_are_spans_or_points() -> None:
    battle = plan(entity("event_battle"), item(P585=st("+1066-10-14T00:00:00Z", 11)))
    assert (battle["start"], battle["end"], battle["start_prop"]) == (1066, 1066, "P585")
    war = plan(entity("event_war"), item(P580=st("+1756-00-00T00:00:00Z"), P582=st("+1763-00-00T00:00:00Z"),
                                         P585=st("+1900-00-00T00:00:00Z")))
    assert war["reason"] == "start_prop_conflict:P580/P585"


def test_out_of_scope_types_and_doubtful_qids_are_skipped() -> None:
    assert plan(entity("language"), item(P571=st("+1887-00-00T00:00:00Z")))["reason"] == "type_not_covered"
    doubtful = entity(verification_status="needs_review", flags=["identity_audit:qid_suspect:duplicate"])
    assert plan(doubtful, item(P571=st("+1100-00-00T00:00:00Z")))["reason"] == "qid_in_doubt"


# ── update vs insert ─────────────────────────────────────────────────────────
def test_an_existing_primary_row_is_updated_and_keeps_its_end() -> None:
    e = entity("person", range_id="r1", row_end_year=1519, row_end_date="1519-05-02")
    p = plan(e, item(P569=st("+1452-04-15T00:00:00Z", 11), P570=st("+1519-05-02T00:00:00Z", 11)))
    assert p["action"] == "update" and p["end_date"] == "1519-05-02" and p["end_prop"] == "row"
    assert plan(entity("person", range_id="r1", row_end_year=1519, row_end_date="1519"),
                item(P569=st("+1452-00-00T00:00:00Z")))["action"] == "update"  # no WD death needed


def test_a_row_end_that_disagrees_or_predates_the_start_skips() -> None:
    e = entity("person", range_id="r1", row_end_year=1600, row_end_date="1600")
    assert plan(e, item(P569=st("+1452-00-00T00:00:00Z"), P570=st("+1519-00-00T00:00:00Z")))["reason"] \
        == "end_disagrees_with_row"
    assert plan(e, item(P569=st("+1650-00-00T00:00:00Z")))["reason"] == "start_after_row_end"


def test_rollback_deletes_inserts_and_restores_updates(tmp_path) -> None:
    ins = (entity(), {"action": "insert", "range_id": "11111111-1111-1111-1111-111111111111"})
    upd = (entity(range_id="r2", row_end_date="1519", date_method=None, date_confidence=None,
                  notes="it's old", duration_type=None, updated_at="2026-10-01 00:00:00"),
           {"action": "update", "range_id": "22222222-2222-2222-2222-222222222222"})
    write_rollback(tmp_path / "rollback.sql", [ins, upd])
    sql = (tmp_path / "rollback.sql").read_text()
    assert "DELETE FROM entity_temporal_ranges WHERE notes LIKE 'backfill_dates:%' AND temporal_range_id IN " \
           "('11111111-1111-1111-1111-111111111111')" in sql
    assert "start_date = NULL, end_date = '1519'" in sql and "notes = 'it''s old'" in sql


# ── century pass (the importer's min_storable_precision convention) ─────────
def test_century_pass_stores_a_polity_century_as_the_importer_does() -> None:
    claims = item(P571=st("+0601-00-00T00:00:00Z", 7), P576=st("+0900-00-00T00:00:00Z", 7))
    assert plan(entity(), claims)["reason"] == "start_coarse:P571"  # default pass: skipped
    p = plan_entity(entity(), claims, False, [], century=True)
    assert (p["start"], p["end"], p["start_date"], p["end_date"]) == (601, 900, "601", "900")
    assert p["confidence"] == "low" and p["precision_note"] == "century:start+end"
    bce = plan_entity(entity("city"), item(P571=st("-0100-00-00T00:00:00Z", 7)), False, [], century=True)
    assert (bce["start"], bce["start_date"], bce["end"]) == (-100, "-100", None)


def test_century_pass_leaves_persons_and_millennia_alone() -> None:
    person = item(P569=st("-0100-00-00T00:00:00Z", 7), P570=st("+0100-00-00T00:00:00Z", 7))
    assert plan_entity(entity("person"), person, False, [], century=True)["reason"] == "person_not_in_century_pass"
    millennium = item(P571=st("-1000-00-00T00:00:00Z", 6))
    assert plan_entity(entity("city"), millennium, False, [], century=True)["reason"] == "start_coarse:P571"


def test_a_century_start_after_the_entitys_own_facts_is_still_rejected() -> None:
    p = plan_entity(entity(), item(P571=st("+1200-00-00T00:00:00Z", 7)), False, [(1150, 1150, "chronicle")],
                    century=True)
    assert p["reason"] == "start_after_evidence"


def test_a_lagging_wikidata_is_never_cached_as_missing(monkeypatch) -> None:
    import pipeline.backfill_dates as bd

    class Lagging:
        appended: list = []

        def _load_jsonl(self, name, key):
            return {}

        def _get(self, url, params):
            class R:
                def json(self):
                    return {"error": {"code": "maxlag"}}
            return R()

        def _append(self, name, records):
            self.appended.extend(records)

    monkeypatch.setattr(bd.time, "sleep", lambda s: None)
    client = Lagging()
    assert bd.fetch_claims(client, ["Q1", "Q2"]) == {}
    assert client.appended == []
