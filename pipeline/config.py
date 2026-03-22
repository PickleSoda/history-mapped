"""Pipeline configuration — loads .env, defines constants."""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from pipeline directory
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)


class Settings:
    """Typed access to environment configuration."""

    @property
    def wikidata_endpoint(self) -> str:
        return os.getenv("WIKIDATA_ENDPOINT", "https://query.wikidata.org/sparql")

    @property
    def wikidata_user_agent(self) -> str:
        return os.getenv("WIKIDATA_USER_AGENT", "WikiGlobe/1.0 (https://github.com/PickleSoda/WG)")

    @property
    def wikipedia_language(self) -> str:
        return os.getenv("WIKIPEDIA_LANGUAGE", "en")

    @property
    def openai_api_key(self) -> str | None:
        return os.getenv("OPENAI_API_KEY") or None

    @property
    def openai_embedding_model(self) -> str:
        return os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    @property
    def openai_summary_model(self) -> str:
        return os.getenv("OPENAI_SUMMARY_MODEL", "gpt-4o-mini")

    @property
    def summary_max_chars(self) -> int:
        return int(os.getenv("SUMMARY_MAX_CHARS", "420"))

    @property
    def summary_use_llm(self) -> bool:
        return os.getenv("SUMMARY_USE_LLM", "false").lower() in {"1", "true", "yes", "on"}

    @property
    def wikipedia_extract_max_chars(self) -> int:
        return int(os.getenv("WIKIPEDIA_EXTRACT_MAX_CHARS", "8000"))

    @property
    def output_dir(self) -> str:
        return os.getenv("OUTPUT_DIR", str(Path(__file__).parent / "output"))

    @property
    def log_level(self) -> str:
        return os.getenv("LOG_LEVEL", "INFO")

    @property
    def wikidata_rpm(self) -> int:
        return int(os.getenv("WIKIDATA_REQUESTS_PER_MINUTE", "30"))

    @property
    def wikipedia_rpm(self) -> int:
        return int(os.getenv("WIKIPEDIA_REQUESTS_PER_MINUTE", "60"))

    @property
    def commons_rpm(self) -> int:
        return int(os.getenv("COMMONS_REQUESTS_PER_MINUTE", "30"))

    @property
    def database_url(self) -> str | None:
        return os.getenv("DATABASE_URL") or None


settings = Settings()


# ── Entity group → type mapping (mirrors the Laravel enums) ──────────────────

ENTITY_GROUPS: dict[str, list[str]] = {
    "POLITY": [
        "political_entity", "dynasty", "person", "military_unit",
        "diplomatic_relationship", "social_class",
    ],
    "PLACE": [
        "city", "infrastructure_monument", "extraction_infra",
        "educational_institution",
    ],
    "EVENT": [
        "event_war", "event_battle", "event_treaty", "event_rebellion",
        "event_natural_disaster", "event_tech_adoption", "event_legal_reform",
        "migration", "epidemic_disease",
    ],
    "ECONOMY": [
        "trade_route", "natural_resource", "currency_monetary_system",
    ],
    "CULTURE": [
        "cultural_work", "intellectual_movement", "archaeological_culture",
        "language", "religious_text", "legal_code", "religious_movement",
        "technology",
    ],
}

# Reverse lookup: entity_type → entity_group
TYPE_TO_GROUP: dict[str, str] = {}
for group, types in ENTITY_GROUPS.items():
    for t in types:
        TYPE_TO_GROUP[t] = group
