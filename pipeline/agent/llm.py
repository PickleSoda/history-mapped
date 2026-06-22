"""LLM provider factory for the agentic pipeline.

Supports any OpenAI-compatible API endpoint, including:
- OpenAI (default)
- OpenRouter
- Local models (Ollama, vLLM, LM Studio, etc.)

Also supports model-level fallback chains so a primary model can degrade to
alternates on rate-limit or availability errors.

Usage:
    from pipeline.agent.llm import create_llm, create_llm_with_fallbacks
    from pipeline.agent.config import AgentConfig

    cfg = AgentConfig()
    llm = create_llm(cfg.parse_model, cfg.openai_api_key, cfg.llm_base_url)
    # or with automatic fallback chain
    llm = create_llm_with_fallbacks("parse_model", cfg)
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI

from pipeline.agent.config import AgentConfig

logger = logging.getLogger(__name__)


def create_llm(
    model: str,
    api_key: str | None,
    base_url: str | None = None,
    temperature: float = 0.0,
    timeout: float | None = None,
    max_retries: int = 0,
    max_tokens: int | None = None,
    reasoning_effort: str | None = None,
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
    timeout: Per-request timeout in seconds. None uses the SDK default (600s).
    max_retries: SDK-internal retries. Defaults to 0 because FallbackLLM owns the
              retry/fallback loop — letting the SDK also retry compounds latency
              (600s × 3 internal × N fallback attempts hangs a run for ~30 min).

    Returns
    -------
    Configured ChatOpenAI instance.
    """
    kwargs: dict = {
        "model": model,
        "temperature": temperature,
        "max_retries": max_retries,
    }
    if api_key is not None:
        kwargs["api_key"] = api_key
    if base_url is not None:
        kwargs["base_url"] = base_url
    if timeout is not None:
        kwargs["timeout"] = timeout
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    # reasoning_effort tames the gpt-5* reasoning models: without it they spend the
    # bulk of the token budget on hidden reasoning (≈4k tokens/call) and more often
    # wander into malformed JSON; "minimal" makes them emit the structured answer
    # directly. Non-reasoning fallback models (gpt-oss, qwen) accept and ignore it.
    if reasoning_effort is not None:
        kwargs["reasoning_effort"] = reasoning_effort

    return ChatOpenAI(**kwargs)


class FallbackLLM:
    """Wrapper that tries a primary LLM and falls back through a chain of alternatives.

    Retries on transient errors (rate limits, timeouts, 5xx).
    Falls back to the next model in the chain on persistent failures.
    """

    def __init__(
        self,
        primary_model: str,
        fallback_models: list[str],
        api_key: str | None,
        base_url: str | None = None,
        temperature: float = 0.0,
        max_retries_per_model: int = 2,
        request_timeout: float | None = None,
        max_tokens: int | None = None,
        reasoning_effort: str | None = None,
    ):
        self._primary_model = primary_model
        self._fallback_models = fallback_models
        self._api_key = api_key
        self._base_url = base_url
        self._temperature = temperature
        self._max_retries = max_retries_per_model
        self._request_timeout = request_timeout
        self._max_tokens = max_tokens
        self._reasoning_effort = reasoning_effort
        self._primary_llm = self._create_llm(primary_model)

    def _create_llm(self, model: str) -> ChatOpenAI:
        return create_llm(
            model=model,
            api_key=self._api_key,
            base_url=self._base_url,
            temperature=self._temperature,
            timeout=self._request_timeout,
            max_tokens=self._max_tokens,
            reasoning_effort=self._reasoning_effort,
        )

    def invoke(self, messages: list[Any], **kwargs: Any) -> BaseMessage:
        """Invoke the LLM, falling back through the chain on failure."""
        models = [self._primary_model, *self._fallback_models]
        last_error: Exception | None = None

        for model in models:
            llm = self._create_llm(model) if model != self._primary_model else self._primary_llm
            for attempt in range(1, self._max_retries + 1):
                try:
                    result = llm.invoke(messages, **kwargs)
                    if model != self._primary_model:
                        logger.info("Fallback succeeded: model=%s", model)
                    return result
                except Exception as exc:
                    last_error = exc
                    logger.warning(
                        "LLM attempt %d/%d failed for model=%s: %s",
                        attempt,
                        self._max_retries,
                        model,
                        exc,
                    )

        raise last_error or RuntimeError("All LLM models exhausted")


def create_llm_with_fallbacks(
    model_key: str,
    cfg: AgentConfig,
    temperature: float = 0.0,
    max_tokens: int | None = None,
    reasoning_effort: str | None = None,
) -> FallbackLLM:
    """Create a FallbackLLM for the given model key.

    Reads the primary model and fallback chain from config.

    Parameters
    ----------
    model_key: One of "parse_model", "extract_model", "generate_model".
    cfg: AgentConfig instance.
    temperature: Sampling temperature.

    Returns
    -------
    FallbackLLM configured with primary + fallback chain.
    """
    primary = getattr(cfg, model_key)
    fallbacks = cfg.model_fallbacks.get(model_key, []) if cfg.model_fallbacks else []
    return FallbackLLM(
        primary_model=primary,
        fallback_models=fallbacks,
        api_key=cfg.openai_api_key,
        base_url=cfg.llm_base_url,
        temperature=temperature,
        request_timeout=cfg.llm_request_timeout,
        max_tokens=max_tokens,
        reasoning_effort=reasoning_effort,
    )
