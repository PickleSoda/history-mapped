from pipeline.agent.config import AgentConfig, ENTITY_RISK_POLICIES, RELATION_RISK_POLICIES


def test_config_loads_defaults():
    cfg = AgentConfig()
    # Model identities are tuned over time (and per the OpenRouter free tiers), so
    # assert they load as non-empty strings rather than pinning exact slugs.
    assert isinstance(cfg.parse_model, str) and cfg.parse_model
    assert isinstance(cfg.extract_model, str) and cfg.extract_model
    assert isinstance(cfg.generate_model, str) and cfg.generate_model
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


def test_output_dir_is_container_visible():
    """Test that output_dir resolves to container-visible path for artisan commands."""
    cfg = AgentConfig()
    # Must resolve under the mounted api/storage path so `docker compose exec app` can see it.
    assert cfg.output_dir.endswith("storage/app/pipeline/agent_runs")


def test_container_output_dir_returns_absolute_container_path():
    """Test that container_output_dir returns the in-container absolute path."""
    cfg = AgentConfig()
    container_path = cfg.container_output_dir
    assert container_path == "/var/www/html/storage/app/pipeline/agent_runs"
