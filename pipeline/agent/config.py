from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class AgentConfig:
    parse_model: str = "gpt-4o-mini"
    extract_model: str = "gpt-4o-mini"
    generate_model: str = "gpt-4o"
    openai_api_key: str | None = None
    llm_base_url: str | None = None
    auto_commit_threshold: float = 0.95
    output_dir: str = "output/agent_runs"
    ohm_index_path: str = "output/ohm_collections/global/index.db"

    def __post_init__(self):
        if self.openai_api_key is None:
            self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if self.llm_base_url is None:
            self.llm_base_url = os.getenv("LLM_BASE_URL")


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
