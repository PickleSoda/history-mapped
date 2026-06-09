from pipeline.agent.config import AgentConfig, ENTITY_RISK_POLICIES, RELATION_RISK_POLICIES


def test_config_loads_defaults():
    cfg = AgentConfig()
    assert cfg.parse_model == "gpt-4o-mini"
    assert cfg.ohm_index_path == "output/ohm_collections/global/index.db"


def test_risk_policies():
    assert "political_entity" in ENTITY_RISK_POLICIES
    assert "participated_in" in RELATION_RISK_POLICIES
    assert ENTITY_RISK_POLICIES["person"]["risk_level"] == "high"
