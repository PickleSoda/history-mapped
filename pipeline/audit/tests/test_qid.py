"""C2 verdicts and C3 resolution against an offline client."""
from pipeline.audit.qid import check_row, find_correct_qid
from pipeline.audit.tests.conftest import CLOSURE, make_row, rec


def _closure_fn(classes):
    return CLOSURE


def test_consistent_row_is_ok(client):
    client.entities["Q1531906"] = rec("Jean-Baptiste Drouet", dates={"P569": [1763, 11], "P570": [1824, 11]})
    row = make_row("Jean-Baptiste Drouet", qid="Q1531906", start=1763, end=1824)
    assert check_row(row, client, CLOSURE)["verdict"] == "ok"


def test_namesake_from_another_era_with_unrelated_name_is_wrong(client):
    client.entities["Q155540"] = rec("Hans von Bülow", dates={"P569": [1830, 11], "P570": [1894, 11]})
    row = make_row("Friedrich Wilhelm Bülow von Dennewitz", qid="Q155540", start=1755, end=1816)
    out = check_row(row, client, CLOSURE)
    assert out["verdict"] == "wrong" and out["rule"].startswith("W5")


def test_namesake_with_compatible_name_needs_the_text(client):
    client.entities["Q140222"] = rec("Philip II of Spain", dates={"P569": [1527, 11], "P570": [1598, 11]})
    plain = make_row("Philip II", qid="Q140222", start=-382, end=-336)
    assert check_row(plain, client, CLOSURE)["rule"].startswith("W8")  # 1,863 years apart decides alone
    told = make_row("Philip II", qid="Q140222", start=-382, end=-336,
                    summary="King of Macedon who won at Chaeronea in 338 BCE.")
    out = check_row(told, client, CLOSURE)
    assert out["verdict"] == "wrong" and out["rule"].startswith("W6")


def test_disambiguation_and_missing_and_redirect(client):
    client.entities["Q1"] = rec("Salamis", p31=["Q4167410"])
    client.entities["Q2"] = {"status": "missing"}
    client.entities["Q3"] = {"status": "redirect", "redirect_to": "Q4"}
    client.entities["Q4"] = rec("Themistocles", dates={"P569": [-524, 9], "P570": [-459, 9]})
    assert check_row(make_row("Salamis", "city", qid="Q1"), client, CLOSURE)["rule"].startswith("W2")
    assert check_row(make_row("Salamis", "city", qid="Q1"), client, CLOSURE)["severity"] == "high"
    assert check_row(make_row("Ur", "city", qid="Q2"), client, CLOSURE)["rule"].startswith("W1")
    out = check_row(make_row("Themistocles", qid="Q3", start=-524, end=-459), client, CLOSURE)
    assert out["verdict"] == "redirect" and out["resolved_qid"] == "Q4"


def test_soft_contradiction_is_suspect_decisive_is_wrong(client):
    # a church reaching 'built structure' on a religious-movement row: ontology noise or a type slip
    client.entities["Q10"] = rec("Malankara Church", p31=["Q16970"])
    out = check_row(make_row("Malankara Church", "religious_movement", qid="Q10"), client, CLOSURE)
    assert out["verdict"] == "suspect" and out["rule"].startswith("S1")
    # a ship on a person row, an article on a city row: the QID is wrong whatever the name
    client.entities["Q11"] = rec("Victory", p31=["Q11446"])
    assert check_row(make_row("Victory", qid="Q11"), client, CLOSURE)["rule"].startswith("W4")
    client.entities["Q12"] = rec("Kumbakonam", p31=["Q17329259"])
    assert check_row(make_row("Kumbakonam", "city", qid="Q12"), client, CLOSURE)["rule"].startswith("W4")


def test_concept_qid_on_a_proper_named_row(client):
    client.entities["Q131668"] = rec("acropolis", p31=["Q99999"], p279=["Q99999"])
    out = check_row(make_row("Acropolis", "infrastructure_monument", qid="Q131668"), client, CLOSURE)
    assert out["rule"].startswith("W7")
    client.entities["Q1353951"] = rec("Antarctic France", p31=["Q3024240"], p279=["Q99999"])
    out = check_row(make_row("France Antarctique", "political_entity", qid="Q1353951"), client, CLOSURE)
    assert out["verdict"] != "wrong"  # capitalised label: a proper name, not a concept


def test_find_correct_qid_unique_and_ambiguous(client):
    row = make_row("Friedrich Wilhelm Bülow", qid="Q155540", start=1755, end=1816)
    client.searches["Friedrich Wilhelm Bülow␟10"] = [
        {"qid": "Q60401", "label": "Friedrich Wilhelm Bülow von Dennewitz", "match_text": ""},
        {"qid": "Q155540", "label": "Hans von Bülow", "match_text": ""},
        {"qid": "Q777", "label": "Friedrich Wilhelm Bülow", "match_text": ""}]
    client.entities["Q60401"] = rec("Friedrich Wilhelm Bülow von Dennewitz",
                                    dates={"P569": [1755, 11], "P570": [1816, 11]})
    client.entities["Q155540"] = rec("Hans von Bülow", dates={"P569": [1830, 11], "P570": [1894, 11]})
    client.entities["Q777"] = rec("Friedrich Wilhelm Bülow", dates={"P569": [1900, 9], "P570": [1950, 9]})
    out = find_correct_qid(row, client, _closure_fn, exclude={"Q155540"})
    assert out["outcome"] == "high" and out["qid"] == "Q60401"
    client.entities["Q777"] = rec("Friedrich Wilhelm Bülow", dates={"P569": [1754, 9], "P570": [1816, 9]})
    assert find_correct_qid(row, client, _closure_fn, exclude={"Q155540"})["outcome"] == "ambiguous"


def test_transliteration_with_reign_dates_is_not_wrong(client):
    client.entities["Q8409"] = rec("Muawiyah I", dates={"P569": [602, 9], "P570": [680, 9]})
    out = check_row(make_row("Muawiya I", qid="Q8409", start=661, end=680), client, CLOSURE)
    assert out["verdict"] == "suspect"


def test_regnal_marker_conflict_with_dates_is_wrong(client):
    client.entities["Q3"] = rec("Ptolemy III Euergetes", dates={"P569": [-280, 9], "P570": [-222, 9]})
    out = check_row(make_row("Ptolemy II Philadelphus", qid="Q3", start=-309, end=-246), client, CLOSURE)
    assert out["verdict"] == "wrong" and out["rule"].startswith("W3")


def test_plural_names_are_compatible():
    from pipeline.audit.qid import inflected_equal, name_verdict
    assert inflected_equal("Khokhars", "Khokhar")
    assert not inflected_equal("Qi", "Qing")
    assert name_verdict(["Khokhars"], rec("Khokhar")) == "inflected"


def test_concept_row_with_concept_qid_is_not_wrong(client):
    client.entities["Q131401"] = rec("caliphate", p31=["Q3024240"], p279=["Q99999"])
    out = check_row(make_row("Caliphate", "political_entity", qid="Q131401"), client, CLOSURE)
    assert out["verdict"] == "suspect" and out["rule"].startswith("S2")


def test_exact_name_and_matching_dates_soften_a_human_qid(client):
    # a person mistyped as a polity: same name, same dates -> type problem, not a wrong QID
    client.entities["Q8462"] = rec("Timur", dates={"P569": [1336, 9], "P570": [1405, 9]})
    out = check_row(make_row("Timur", "political_entity", qid="Q8462", start=1336, end=1405), client, CLOSURE)
    assert out["verdict"] == "suspect" and out["rule"].startswith("S1")


def test_concept_rows_keep_their_concept_qid(client):
    client.entities["Q6465"] = rec("department of France", p31=["Q99999"], p279=["Q99999"])
    out = check_row(make_row("Departments of France", "political_entity", qid="Q6465"), client, CLOSURE)
    assert out["verdict"] != "wrong"
    client.entities["Q333247"] = rec("temperance movement", p31=[], p279=["Q99999"])
    out = check_row(make_row("Temperance Movement", "political_entity", qid="Q333247"), client, CLOSURE)
    assert out["verdict"] != "wrong"


def test_far_era_namesake_is_wrong_unless_the_text_points_to_the_qid(client):
    client.entities["Q353305"] = rec("John Wesley", dates={"P569": [1962, 11]}, description="American guitarist")
    out = check_row(make_row("John Wesley", qid="Q353305", start=1703, end=1791), client, CLOSURE)
    assert out["rule"].startswith("W8")
    told = make_row("Ptolemy", qid="Q34943", start=-367, end=-282, summary="Greek geographer (90–168 CE).")
    client.entities["Q34943"] = rec("Ptolemy", dates={"P569": [100, 9], "P570": [170, 9]})
    assert check_row(told, client, CLOSURE)["verdict"] == "suspect"  # the row's dates are wrong, not the QID
    # a few decades apart: chronologies differ, only a suspect
    client.entities["Q1282616"] = rec("Pulcheria", dates={"P569": [379, 9], "P570": [386, 9]})
    assert check_row(make_row("Pulcheria", qid="Q1282616", start=399, end=453), client, CLOSURE)["verdict"] == "suspect"


def test_c3_needs_precise_dates_and_exact_one_word_names(client):
    from pipeline.audit.qid import score_candidate
    row = make_row("Constance of Sicily", qid="Q774888", start=1154, end=1198)
    coarse = rec("Constance of Sicily, Dogaressa of Venice", dates={"P569": [1200, 7], "P570": [1300, 7]})
    assert not score_candidate(row, "Q14916860", coarse, CLOSURE)["checks"]["dates"]
    precise = rec("Constance I of Sicily", dates={"P569": [1154, 11], "P570": [1198, 11]})
    assert score_candidate(row, "Q229203", precise, CLOSURE)["checks"]["dates"]
    majlis = make_row("Majlis", "political_entity", start=1906)
    saudi = rec("Consultative Assembly of Saudi Arabia", p31=["Q3024240"], aliases=["Majlis al-Shura"],
                dates={"P571": [1927, 11]})
    assert not score_candidate(majlis, "Q818708", saudi, CLOSURE)["checks"]["name"]


def test_c3_coarse_dated_namesake_still_blocks_the_winner(client):
    from pipeline.audit.qid import score_candidate
    row = make_row("Constance of Sicily", qid="Q774888", start=1154, end=1198)
    coarse = rec("Constance of Sicily", dates={"P569": [1150, 7], "P570": [1200, 7]})
    s = score_candidate(row, "Q1", coarse, CLOSURE)
    assert not s["checks"]["dates"] and s["rival"]


def test_mistyped_row_carrying_its_own_event_is_only_a_suspect(client):
    from pipeline.audit.qid import check_row
    closure = {**CLOSURE, "Q178561": {"Q178561"}}
    row = make_row("Montaperti", "city", qid="Q587095", start=1260)
    client.entities["Q587095"] = rec("Battle of Montaperti", p31=["Q178561"], dates={"P585": [1260, 11]})
    out = check_row(row, client, closure)
    assert out["verdict"] == "suspect" and out["rule"].startswith("S1")


def test_c3_rejects_a_band_for_a_religious_row(client):
    from pipeline.audit.qid import score_candidate
    closure = {**CLOSURE, "Q215380": {"Q215380", "Q43229"}}
    row = make_row("Astarte", "religious_movement")
    band = rec("Astarte", p31=["Q215380"], dates={"P571": [1995, 9]})
    assert not score_candidate(row, "Q2462076", band, closure)["checks"]["class"]


def test_band_on_a_mistyped_row_is_only_a_suspect(client):
    from pipeline.audit.qid import check_row
    closure = {**CLOSURE, "Q215380": {"Q215380", "Q43229"}}
    client.entities["Q1299"] = rec("The Beatles", p31=["Q215380"], dates={"P571": [1960, 11], "P576": [1970, 11]})
    out = check_row(make_row("The Beatles", "intellectual_movement", qid="Q1299", start=1960, end=1970),
                    client, closure)
    assert out["verdict"] == "suspect"
    client.entities["Q3212490"] = rec("Maritime Silk Road", p31=["Q11424"], dates={"P577": [2011, 11]})
    closure["Q11424"] = {"Q11424"}
    out = check_row(make_row("Maritime Silk Road", "trade_route", qid="Q3212490", start=1087), client, closure)
    assert out["verdict"] == "wrong" and out["rule"].startswith("W4")


def test_exact_name_with_a_relative_kind_is_only_a_suspect(client):
    from pipeline.audit.qid import check_row
    closure = {**CLOSURE, "Q1781513": {"Q178561"}, "Q20643955": {"Q4271324", "Q14897293"},
               "Q1229765": {"Q1229765"}}
    # a controversy (reaches 'war') on an intellectual_movement row: mistyped row
    client.entities["Q525545"] = rec("Chinese Rites controversy", p31=["Q1781513"],
                                     dates={"P580": [1645, 11], "P582": [1742, 11]})
    out = check_row(make_row("Chinese Rites controversy", "intellectual_movement", qid="Q525545",
                             start=1630, end=1742), client, closure)
    assert out["verdict"] == "suspect"
    # a ship stays decisive even with the exact name
    client.entities["Q6805435"] = rec("Media", p31=["Q11446"])
    out = check_row(make_row("Media", "political_entity", qid="Q6805435"), client, closure)
    assert out["verdict"] == "wrong" and out["rule"].startswith("W4")


def test_two_rows_never_get_one_qid():
    from pipeline.audit.identity import _settle_collisions
    rows = {"a": make_row("Battle of Vienna", "event_battle", id="a"),
            "b": make_row("Siege of Vienna", "event_battle", id="b"),
            "c": make_row("Rab'-i Rashidi", "infrastructure_monument", id="c")}
    flags = [{"entity_id": "a", "action": "set_qid", "proposed_qid": "Q200855", "rule": "W6",
              "proposed_label": "Battle of Vienna — 1683 battle"},
             {"entity_id": "b", "action": "set_qid", "proposed_qid": "Q200855", "rule": "W6",
              "proposed_label": "Battle of Vienna — 1683 battle"},
             {"entity_id": "c", "action": "set_qid(redirect)", "proposed_qid": "Q80053", "rule": "S8"}]
    _settle_collisions(flags, rows, {"Q80053": ["z"]})
    assert [f["action"] for f in flags] == ["set_qid", "needs_review+duplicate_of:a", "needs_review+duplicate_of:z"]
