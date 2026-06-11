from pipeline.agent.config import AgentConfig, ENTITY_RISK_POLICIES, RELATION_RISK_POLICIES


def test_config_loads_defaults():
    cfg = AgentConfig()
    assert cfg.parse_model == "gpt-4o-mini"
    assert cfg.ohm_index_path == "output/ohm_collections/map-egypt.xml.sqlite"


def test_risk_policies():
    assert "political_entity" in ENTITY_RISK_POLICIES
    assert "participated_in" in RELATION_RISK_POLICIES
    assert ENTITY_RISK_POLICIES["person"]["risk_level"] == "high"


def test_config_accepts_custom_base_url():
    cfg = AgentConfig(
        parse_model="meta-llama/llama-3.1-70b-instruct",
        openai_api_key="sk-test",
        llm_base_url="https://openrouter.ai/api/v1",
    )
    assert cfg.parse_model == "meta-llama/llama-3.1-70b-instruct"
    assert cfg.llm_base_url == "https://openrouter.ai/api/v1"
    assert cfg.openai_api_key == "sk-test"
