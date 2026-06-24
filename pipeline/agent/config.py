from __future__ import annotations

import os
from dataclasses import dataclass


# ── Fallback model chains (OpenRouter) ──
# Primary for all stages: openai/gpt-5-nano ($0.05/$0.40 per 1M tokens).
# FallbackLLM walks primary → list below, top→bottom on 429/5xx.
MODEL_FALLBACKS: dict[str, list[str]] = {
    "parse_model": [
        "openai/gpt-oss-120b",
        "meta-llama/llama-3.1-8b-instruct",
    ],
    "extract_model": [
        "openai/gpt-oss-120b",
        "qwen/qwen3-30b-a3b-instruct-2507",
    ],
    "generate_model": [
        "openai/gpt-oss-120b",
        "qwen/qwen3-32b",
    ],
}


@dataclass
class AgentConfig:
    # Primary models per step — free OpenRouter tiers (see MODEL_FALLBACKS for
    # the per-step fallback chains). The previous "gpt-4o*" bare names were not
    # valid OpenRouter slugs, so every primary call failed straight into the
    # fallback chain; these resolve directly.
    parse_model: str = "openai/gpt-5-nano"
    extract_model: str = "openai/gpt-5-nano"
    generate_model: str = "openai/gpt-5-nano"
    openai_api_key: str | None = None
    llm_base_url: str | None = None
    model_fallbacks: dict[str, list[str]] | None = None
    auto_commit_threshold: float = 0.95
    # Per-request LLM timeout (seconds). Caps a single model call so a stuck
    # endpoint fails fast and FallbackLLM moves on, instead of the OpenAI SDK's
    # 600s default × internal retries hanging the whole pipeline run.
    llm_request_timeout: float = 120.0
    # Output-token ceiling for the content-generation call. Without it the model
    # default (65536) is requested, which is both wasteful and unaffordable on a
    # low credit balance — a single generate_content call then 402s and the
    # entity summaries are lost. 8000 comfortably fits the summaries JSON.
    generate_max_tokens: int = 32000
    # Reasoning effort for the gpt-5* models. "minimal" stops them spending the
    # token budget on hidden reasoning (~4k/call) and reduces malformed-JSON
    # output; it is accepted-and-ignored by the non-reasoning fallback models.
    reasoning_effort: str = "minimal"
    output_dir: str = "api/storage/app/pipeline/agent_runs"
    chronicle_output_dir: str = "api/storage/app/pipeline/agent_runs"
    ohm_index_path: str = "output/ohm_collections/map-egypt.xml.sqlite"
    artisan_timeout: int = 300

    def __post_init__(self):
        if self.openai_api_key is None:
            self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if self.llm_base_url is None:
            self.llm_base_url = os.getenv("LLM_BASE_URL")
        if self.model_fallbacks is None:
            self.model_fallbacks = MODEL_FALLBACKS
        # Allow override via environment variable
        env_output = os.getenv("AGENT_OUTPUT_DIR")
        if env_output:
            self.output_dir = env_output

    @property
    def container_output_dir(self) -> str:
        """Return the in-container absolute path for artisan commands."""
        return "/var/www/html/storage/app/pipeline/agent_runs"


ENTITY_RISK_POLICIES: dict[str, dict] = {
    "person": {"risk_level": "high", "auto_commit_threshold": 0.97},
    "political_entity": {"risk_level": "high", "auto_commit_threshold": 0.97},
    "dynasty": {"risk_level": "high", "auto_commit_threshold": 0.97},
    "city": {"risk_level": "medium", "auto_commit_threshold": 0.94},
    "event_battle": {"risk_level": "low", "auto_commit_threshold": 0.90},
    "event_war": {"risk_level": "low", "auto_commit_threshold": 0.90},
    "event_treaty": {"risk_level": "low", "auto_commit_threshold": 0.90},
    "trade_route": {"risk_level": "low", "auto_commit_threshold": 0.90},
    "cultural_work": {"risk_level": "low", "auto_commit_threshold": 0.90},
    "archaeological_culture": {"risk_level": "medium", "auto_commit_threshold": 0.92},
}

RELATION_RISK_POLICIES: dict[str, dict] = {
    "participated_in": {"risk_level": "low", "auto_commit_threshold": 0.90},
    "fought_at": {"risk_level": "low", "auto_commit_threshold": 0.90},
    "born_in": {"risk_level": "low", "auto_commit_threshold": 0.90},
    "died_in": {"risk_level": "low", "auto_commit_threshold": 0.90},
    "rules": {"risk_level": "high", "auto_commit_threshold": 0.97},
    "governed_by": {"risk_level": "high", "auto_commit_threshold": 0.97},
    "at_war_with": {"risk_level": "high", "auto_commit_threshold": 0.95},
    "part_of": {"risk_level": "medium", "auto_commit_threshold": 0.93},
    "succeeded_by": {"risk_level": "medium", "auto_commit_threshold": 0.93},
    "preceded_by": {"risk_level": "medium", "auto_commit_threshold": 0.93},
}
