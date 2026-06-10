"""LLM provider factory for the agentic pipeline.

Supports any OpenAI-compatible API endpoint, including:
- OpenAI (default)
- OpenRouter
- Local models (Ollama, vLLM, LM Studio, etc.)

Usage:
    from pipeline.agent.llm import create_llm
    from pipeline.agent.config import AgentConfig

    cfg = AgentConfig()
    llm = create_llm(cfg.parse_model, cfg.openai_api_key, cfg.llm_base_url)
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI


def create_llm(
    model: str,
    api_key: str | None,
    base_url: str | None = None,
    temperature: float = 0.0,
) -> ChatOpenAI:
    """Create a ChatOpenAI instance configured for the given endpoint.

    Parameters
    ----------
    model: Model identifier (e.g. "gpt-4o-mini", "anthropic/claude-3.5-sonnet",
           "meta-llama/llama-3.1-70b-instruct", "qwen/qwen-2.5-72b-instruct")
    api_key: API key for the provider. Required for all remote providers.
    base_url: Custom base URL for the API endpoint. If None, uses OpenAI's
              default endpoint (https://api.openai.com/v1/).
              For OpenRouter, use "https://openrouter.ai/api/v1".
              For Ollama, use "http://localhost:11434/v1".
    temperature: Sampling temperature. Defaults to 0 for deterministic output.

    Returns
    -------
    Configured ChatOpenAI instance.
    """
    kwargs: dict = {
        "model": model,
        "temperature": temperature,
    }
    if api_key is not None:
        kwargs["api_key"] = api_key
    if base_url is not None:
        kwargs["base_url"] = base_url

    return ChatOpenAI(**kwargs)
