"""BCE/CE sign and lifespan guards (2026-10-07 sign fix).

Persons ended up with spans of centuries (Coponius -100..100, Bagrat IV -1015..1072,
Lewis Powell 1576..1865) because Wikidata century-precision dates were stored as
years, a namesake QID's birth was glued to the transcript's death, Wikidata's own
unsigned BCE years were copied, and the gatherer slipped a minus onto CE years.
"""
import json

from pipeline.agent.date_utils import MAX_PERSON_LIFESPAN, lifespan_problem
from pipeline.agent.graph.nodes.resolve_wikidata import _wikidata_fill
from pipeline.agent.schemas.entities import CandidateEntity, EnrichedCandidate
from pipeline.agent.tests.test_handoff import _sample_doc
from pipeline.agent.tools.wikidata import _claim_dates, storable_wikidata_dates
from pipeline.agent.validate_handoff import validate


def _stmt(time, precision, rank="normal"):
    return {"rank": rank, "mainsnak": {"datavalue": {"value": {"time": time, "precision": precision}}}}


# ── lifespan_problem ────────────────────────────────────────────────────────

def test_lifespan_problem_flags_persons_over_110_and_sign_splits():
    assert MAX_PERSON_LIFESPAN == 110
    assert lifespan_problem("person", -63, 14) is None            # Augustus crosses year 0 within a life
    assert lifespan_problem("person", 1073, 1183) is None         # exactly 110
    assert "111 years" in lifespan_problem("person", 1073, 1184)
    assert lifespan_problem("person", -1015, 1072).startswith("sign split")
    assert lifespan_problem("person", 1072, 1018) == "start 1072 > end 1018"
    assert lifespan_problem("political_entity", -27, 1453) is None  # only persons have a lifespan cap
    assert lifespan_problem("person", None, 1072) is None


# ── Wikidata claim dates ────────────────────────────────────────────────────

def test_claim_dates_prefer_preferred_rank_and_skip_deprecated():
    claims = {"P569": [_stmt("+1015-00-00T00:00:00Z", 9, "deprecated"), _stmt("+1017-00-00T00:00:00Z", 9),
                       _stmt("+1018-00-00T00:00:00Z", 9, "preferred")],
              "P570": [_stmt("+1072-11-24T00:00:00Z", 11)]}
    assert _claim_dates(claims) == {"start_date": "+1018", "end_date": "+1072-11-24T00:00:00Z",
                                    "start_precision": 9, "end_precision": 11}


def test_storable_dates_drop_century_precision_for_persons_only():
    coponius = {"start_date": "-0100", "start_precision": 7, "end_date": "+0100", "end_precision": 7}
    assert storable_wikidata_dates(coponius, "person") == (None, None)
    # A polity's century inception still places it; a millennium does not.
    assert storable_wikidata_dates(coponius, "political_entity") == ("-0100", "+0100")
    babylon = {"start_date": "-1894", "start_precision": 9, "end_date": "+0001", "end_precision": 6}
    assert storable_wikidata_dates(babylon, "city") == ("-1894", None)
    # Decade precision is close enough for a person; unknown precision (old caches) is kept.
    assert storable_wikidata_dates({"start_date": "-0050", "start_precision": 8}, "person") == ("-0050", None)
    assert storable_wikidata_dates({"start_date": "-0331", "end_date": "-0323"}, "person") == ("-0331", "-0323")


def test_storable_dates_refuse_an_impossible_wikidata_lifespan():
    # Shuttarna II: birth "14th century BCE", death entered on Wikidata without its minus.
    shuttarna = {"start_date": "-1350", "start_precision": 7, "end_date": "+1375", "end_precision": 9}
    assert storable_wikidata_dates(shuttarna, "person") == (None, None)
    # Xolotl: year-precise but 194 years.
    assert storable_wikidata_dates({"start_date": "+1110", "start_precision": 9, "end_date": "+1304",
                                    "end_precision": 9}, "person") == (None, None)


def test_storable_dates_keep_a_good_bound_beside_a_century_one():
    # Tacfarinas: born "1st century BCE" (-0100, century), died 24 CE — a possible life.
    tacfarinas = {"start_date": "-0100", "start_precision": 7, "end_date": "+0024", "end_precision": 9}
    assert storable_wikidata_dates(tacfarinas, "person") == (None, "+0024")


# ── resolve_wikidata fill guard ─────────────────────────────────────────────

def _enriched(label, start=None, end=None, match=None, identity_span=None, entity_type="person"):
    return EnrichedCandidate(candidate=CandidateEntity(label=label, entity_type=entity_type, start_date=start,
                                                       end_date=end),
                             wikidata_match=match, identity_span=identity_span)


def test_fill_refuses_a_namesake_whose_other_bound_disagrees():
    # Q6536971 is an English politician (1576-1636), not the 1865 conspirator.
    powell = _enriched("Lewis Powell", end="1865-07-07",
                       match={"start_date": "+1576", "start_precision": 9, "end_date": "+1636", "end_precision": 9})
    start, end, refused = _wikidata_fill(powell)
    assert (start, end) == (None, None) and "namesake" in refused


def test_fill_refuses_an_undated_person_far_from_the_runs_dates():
    dido = _enriched("Dido", identity_span=[-814, -760],
                     match={"start_date": "+1971-12-25T00:00:00Z", "start_precision": 11})
    assert _wikidata_fill(dido)[:2] == (None, None)


def test_fill_refuses_a_lifespan_that_would_exceed_110_years():
    lin_qing = _enriched("Lin Qing", end="1813", match={"start_date": "+1434", "start_precision": 9})
    start, end, refused = _wikidata_fill(lin_qing)
    assert (start, end) == (None, None) and "379 years" in refused


def test_fill_keeps_a_matching_person_and_leaves_sign_slips_to_the_sign_correction():
    # The extractor wrote "-1162" for Genghis Khan; Wikidata's +1162 must still reach _sign_corrected.
    genghis = _enriched("Genghis Khan", start="-1162", end="1227",
                        match={"start_date": "+1162", "start_precision": 9,
                               "end_date": "+1227-08-25T00:00:00Z", "end_precision": 11})
    assert _wikidata_fill(genghis) == ("+1162", "+1227-08-25T00:00:00Z", None)
    tamar = _enriched("Tamar of Georgia", end="1213", match={"start_date": "+1160", "start_precision": 9})
    assert _wikidata_fill(tamar) == ("+1160", None, None)


def test_fill_never_uses_a_century_value_for_a_person():
    khalid = _enriched("Khalid al-Qasri", match={"start_date": "+0601", "start_precision": 7,
                                                 "end_date": "+0743", "end_precision": 9})
    assert _wikidata_fill(khalid) == (None, "+0743", None)


# ── validate_handoff ────────────────────────────────────────────────────────

def _handoff(tmp_path, start, end):
    doc = _sample_doc()
    person = next(e for e in doc["candidate_entities"] if e["entity_type"] == "person")
    person["start_date"], person["end_date"] = start, end
    p = tmp_path / "candidates.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p, person["label"]


def test_validator_rejects_a_sign_split_person(tmp_path):
    path, label = _handoff(tmp_path, "-1015", "1072")
    errors = validate(path)
    assert any(label in e and "sign split" in e for e in errors), errors


def test_validator_rejects_a_window_given_as_a_lifespan(tmp_path):
    path, label = _handoff(tmp_path, "-3517", "-3108")
    assert any("409 years" in e for e in validate(path))


def test_validator_accepts_a_real_lifespan_across_year_zero(tmp_path):
    path, _ = _handoff(tmp_path, "-63", "14")
    assert validate(path) == []
