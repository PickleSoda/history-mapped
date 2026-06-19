from __future__ import annotations

import os
from dataclasses import dataclass


# ── Free-first model chains (OpenRouter), slugs verified via the models API ──
# 2026-06-19. The primary for each step is the matching AgentConfig field below
# (also free); FallbackLLM then walks primary → this list, top→bottom. Notes:
#   • Every entry except the final backstop is a $0 ":free" tier, verified
#     against https://openrouter.ai/api/v1/models.
#   • Chains are provider-diversified (nvidia/openai/google/poolside) so one
#     provider's rate-limit or daily cap can't stall the whole step.
#   • The last entry per chain stays PAID (deepseek) as a last-resort backstop —
#     only reached if every free tier fails. Remove it for strictly-$0 runs.
#   • Deliberately NOT used: "nex-agi/nex-n2-pro:free" (deprecating 2026-06-22).
#   • The pipeline parses JSON from plain text (no response_format / tools), so
#     native structured-output support on the :free tiers isn't required.
#   • Privacy: Owl Alpha logs prompts/completions; Poolside may train on free
#     inputs — acceptable for public-history transcripts.
MODEL_FALLBACKS: dict[str, list[str]] = {
    # parse: high-volume, lightweight; just needs to emit clean JSON.
    # Primary: openai/gpt-oss-20b:free (see AgentConfig.parse_model).
    "parse_model": [
        "nvidia/nemotron-3-nano-30b-a3b:free",
        "google/gemma-4-26b-a4b-it:free",
        "poolside/laguna-xs.2:free",
        "deepseek/deepseek-v3.1-terminus",
    ],
    # extract: mid-tier reasoning + dependable structured extraction.
    # Primary: nvidia/nemotron-3-super-120b-a12b:free (1M ctx, strong SWE-bench).
    "extract_model": [
        "openai/gpt-oss-120b:free",
        "google/gemma-4-31b-it:free",
        "deepseek/deepseek-v3.1-terminus",
    ],
    # generate: highest-quality summaries/prose; long context helps.
    # Primary: nvidia/nemotron-3-ultra-550b-a55b:free (1M ctx, frontier reasoning).
    "generate_model": [
        "openrouter/owl-alpha",
        "nvidia/nemotron-3-super-120b-a12b:free",
        "deepseek/deepseek-v3.1-terminus",
    ],
}


@dataclass
class AgentConfig:
    # Primary models per step — free OpenRouter tiers (see MODEL_FALLBACKS for
    # the per-step fallback chains). The previous "gpt-4o*" bare names were not
    # valid OpenRouter slugs, so every primary call failed straight into the
    # fallback chain; these resolve directly.
    parse_model: str = "openai/gpt-oss-20b:free"
    extract_model: str = "nvidia/nemotron-3-super-120b-a12b:free"
    generate_model: str = "nvidia/nemotron-3-ultra-550b-a55b:free"
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
    generate_max_tokens: int = 8000
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
