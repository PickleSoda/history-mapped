from __future__ import annotations

import os
from dataclasses import dataclass


MODEL_FALLBACKS: dict[str, list[str]] = {
    "parse_model": [
        "openai/gpt-oss-20b:free",
        "google/gemma-4-26b-a4b-it:free",
        "deepseek/deepseek-v3.1-terminus",
    ],
    "extract_model": [
        "google/gemma-4-31b-it:free",
        "openai/gpt-oss-120b:free",
        "deepseek/deepseek-v3.1-terminus",
    ],
    "generate_model": [
        "deepseek/deepseek-v3.1-terminus",
        "google/gemini-2.5-flash",
        "x-ai/grok-4.20",
    ],
}


@dataclass
class AgentConfig:
    parse_model: str = "gpt-4o-mini"
    extract_model: str = "gpt-4o-mini"
    generate_model: str = "gpt-4o"
    openai_api_key: str | None = None
    llm_base_url: str | None = None
    model_fallbacks: dict[str, list[str]] | None = None
    auto_commit_threshold: float = 0.95
    output_dir: str = "output/agent_runs"
    chronicle_output_dir: str = "output/agent_runs"
    ohm_index_path: str = "output/ohm_collections/map-egypt.xml.sqlite"

    def __post_init__(self):
        if self.openai_api_key is None:
            self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if self.llm_base_url is None:
            self.llm_base_url = os.getenv("LLM_BASE_URL")
        if self.model_fallbacks is None:
            self.model_fallbacks = MODEL_FALLBACKS


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
