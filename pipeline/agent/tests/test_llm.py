from unittest.mock import MagicMock, patch

import pytest

from pipeline.agent.config import AgentConfig, MODEL_FALLBACKS
from pipeline.agent.llm import create_llm, create_llm_with_fallbacks, FallbackLLM


def test_create_llm_omits_none_kwargs():
    """create_llm should not pass None api_key or base_url to ChatOpenAI."""
    with patch("pipeline.agent.llm.ChatOpenAI") as mock_chat:
        mock_chat.return_value = MagicMock()
        llm = create_llm("gpt-4o", api_key=None, base_url=None)
        kwargs = mock_chat.call_args.kwargs
        assert "api_key" not in kwargs
        assert "base_url" not in kwargs
        assert kwargs["model"] == "gpt-4o"


def test_create_llm_passes_custom_base_url():
    with patch("pipeline.agent.llm.ChatOpenAI") as mock_chat:
        mock_chat.return_value = MagicMock()
        llm = create_llm(
            "anthropic/claude-3.5-sonnet",
            api_key="sk-test",
            base_url="https://openrouter.ai/api/v1",
        )
        kwargs = mock_chat.call_args.kwargs
        assert kwargs["api_key"] == "sk-test"
        assert kwargs["base_url"] == "https://openrouter.ai/api/v1"
        assert kwargs["model"] == "anthropic/claude-3.5-sonnet"


@patch("pipeline.agent.llm.ChatOpenAI")
def test_fallback_llm_uses_primary_on_success(mock_chat):
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="success")
    mock_chat.return_value = mock_llm

    fallback = FallbackLLM(
        primary_model="primary-model",
        fallback_models=["fallback-1", "fallback-2"],
        api_key="sk-test",
        base_url="https://openrouter.ai/api/v1",
        max_retries_per_model=1,
    )
    result = fallback.invoke(["msg"])

    assert result.content == "success"
    assert mock_chat.call_count == 1
    assert mock_chat.call_args.kwargs["model"] == "primary-model"


@patch("pipeline.agent.llm.ChatOpenAI")
def test_fallback_llm_falls_back_on_failure(mock_chat):
    """When primary fails, fallback LLM should try the next model in the chain."""
    primary_llm = MagicMock()
    primary_llm.invoke.side_effect = RuntimeError("primary down")

    fallback_llm = MagicMock()
    fallback_llm.invoke.return_value = MagicMock(content="fallback ok")

    mock_chat.side_effect = [primary_llm, fallback_llm]

    fallback = FallbackLLM(
        primary_model="primary-model",
        fallback_models=["fallback-1"],
        api_key="sk-test",
        max_retries_per_model=1,
    )
    result = fallback.invoke(["msg"])

    assert result.content == "fallback ok"
    assert mock_chat.call_count == 2


@patch("pipeline.agent.llm.ChatOpenAI")
def test_fallback_llm_exhausts_all_models(mock_chat):
    """When all models fail, FallbackLLM should raise the last error."""
    llm = MagicMock()
    llm.invoke.side_effect = RuntimeError("down")
    mock_chat.return_value = llm

    fallback = FallbackLLM(
        primary_model="primary-model",
        fallback_models=["fallback-1"],
        api_key="sk-test",
        max_retries_per_model=1,
    )
    with pytest.raises(RuntimeError, match="down"):
        fallback.invoke(["msg"])

    assert mock_chat.call_count == 2  # primary + 1 fallback


@patch("pipeline.agent.llm.ChatOpenAI")
def test_invoke_json_parses_valid_response(mock_chat):
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content='{"ok": true}')
    mock_chat.return_value = llm
    fb = FallbackLLM("primary", [], api_key="sk", max_retries_per_model=1)
    assert fb.invoke_json(["msg"]) == {"ok": True}


@patch("pipeline.agent.llm.ChatOpenAI")
def test_invoke_json_retries_same_model_on_bad_json(mock_chat):
    """A malformed body is treated like a transient failure: retry the SAME model."""
    llm = MagicMock()
    llm.invoke.side_effect = [MagicMock(content="not json {"), MagicMock(content='{"ok": 1}')]
    mock_chat.return_value = llm
    fb = FallbackLLM("primary", [], api_key="sk", max_retries_per_model=2)
    assert fb.invoke_json(["msg"]) == {"ok": 1}
    assert llm.invoke.call_count == 2


@patch("pipeline.agent.llm.ChatOpenAI")
def test_invoke_json_falls_back_to_next_model_on_bad_json(mock_chat):
    """Persistent bad JSON on the primary should fall back to the next model —
    the resilience a bare invoke()+parse in the caller never had."""
    primary = MagicMock()
    primary.invoke.return_value = MagicMock(content="garbage, not json")
    fallback = MagicMock()
    fallback.invoke.return_value = MagicMock(content='{"ok": true}')
    mock_chat.side_effect = [primary, fallback]
    fb = FallbackLLM("primary", ["fallback-1"], api_key="sk", max_retries_per_model=1)
    assert fb.invoke_json(["msg"]) == {"ok": True}
    assert mock_chat.call_count == 2


@patch("pipeline.agent.llm.ChatOpenAI")
def test_invoke_json_retries_on_validate_failure(mock_chat):
    """A well-formed but wrong-shape response (validate→False) also retries."""
    llm = MagicMock()
    llm.invoke.side_effect = [MagicMock(content='{"foo": 1}'), MagicMock(content='{"events": []}')]
    mock_chat.return_value = llm
    fb = FallbackLLM("primary", [], api_key="sk", max_retries_per_model=2)
    out = fb.invoke_json(["msg"], validate=lambda d: "events" in d)
    assert out == {"events": []}
    assert llm.invoke.call_count == 2


@patch("pipeline.agent.llm.ChatOpenAI")
def test_invoke_json_raises_when_all_exhausted(mock_chat):
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content="never valid json")
    mock_chat.return_value = llm
    fb = FallbackLLM("primary", ["fallback-1"], api_key="sk", max_retries_per_model=1)
    with pytest.raises(Exception):
        fb.invoke_json(["msg"])
    assert llm.invoke.call_count == 2  # primary + 1 fallback, one attempt each


def test_create_llm_with_fallbacks_reads_config():
    cfg = AgentConfig(
        parse_model="openai/gpt-oss-20b:free",
        openai_api_key="sk-or-v1-test",
        llm_base_url="https://openrouter.ai/api/v1",
    )
    fallback = create_llm_with_fallbacks("parse_model", cfg)
    assert fallback._primary_model == "openai/gpt-oss-20b:free"
    assert fallback._fallback_models == MODEL_FALLBACKS["parse_model"]
    assert fallback._base_url == "https://openrouter.ai/api/v1"


def test_create_llm_with_fallbacks_empty_fallbacks():
    cfg = AgentConfig(
        parse_model="gpt-4o-mini",
        model_fallbacks={"parse_model": []},
    )
    fallback = create_llm_with_fallbacks("parse_model", cfg)
    assert fallback._fallback_models == []
