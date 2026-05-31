import pytest

from pipeline.ohm_collections.egypt_rules import evaluate_candidate


@pytest.mark.parametrize(
    ("candidate", "expected_term"),
    [
        ({"name": "Kingdom of Egypt", "entity_types": ["political_entity"]}, "egypt"),
        ({"name": "Egyptian Nome", "entity_types": ["region"]}, "egyptian"),
        ({"name": "Ancient State", "alternative_names": ["Kemet"], "entity_types": ["political_entity"]}, "kemet"),
        ({"name": "Roman Province", "alternative_names": ["Aegyptus"], "entity_types": ["region"]}, "aegyptus"),
        ({"name": "Thebaid", "raw_tags": {"note": "Upper Egypt administrative region"}, "entity_types": ["region"]}, "upper egypt"),
        ({"name": "Delta Kingdom", "raw_tags": {"description": "Lower Egypt delta polity"}, "entity_types": ["region"]}, "lower egypt"),
    ],
)
def test_evaluate_candidate_matches_egypt_lexical_family_across_supported_fields(
    candidate: dict,
    expected_term: str,
) -> None:
    decision = evaluate_candidate(candidate)

    assert decision["include"] is True
    assert expected_term in decision["matched_terms"]
    assert "lexical_match" in decision["reasons"]


@pytest.mark.parametrize(
    "candidate_name",
    [
        "New Kingdom of Egypt",
        "Roman Egypt",
        "Mamluk Egypt",
        "Ottoman Egypt",
        "Kingdom of Egypt",
        "Republic of Egypt",
    ],
)
def test_evaluate_candidate_includes_all_historical_egypt_period_forms(candidate_name: str) -> None:
    decision = evaluate_candidate({"name": candidate_name, "entity_types": ["historical_period"]})

    assert decision["include"] is True
    assert "default_type" in decision["reasons"]


def test_evaluate_candidate_requires_strong_egypt_link_for_conditional_types() -> None:
    direct_lexical_match = evaluate_candidate(
        {"name": "Egyptian hieroglyphs", "entity_types": ["script"]}
    )
    summary_strong_link = evaluate_candidate(
        {
            "name": "Coptic Christianity",
            "summary": "Religion practiced in Egypt during late antiquity.",
            "entity_types": ["religion"],
        }
    )
    weak_incidental_match = evaluate_candidate(
        {
            "name": "Levantine coinage",
            "summary": "Also traded in Egypt during the Bronze Age.",
            "entity_types": ["currency"],
        }
    )

    assert direct_lexical_match["include"] is True
    assert "conditional_strong_link" in direct_lexical_match["reasons"]

    assert summary_strong_link["include"] is True
    assert "conditional_strong_link" in summary_strong_link["reasons"]

    assert weak_incidental_match["include"] is False
    assert "weak_incidental_match" in weak_incidental_match["reasons"]