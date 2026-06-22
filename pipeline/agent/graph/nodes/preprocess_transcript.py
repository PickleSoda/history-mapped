"""Preprocess raw transcripts for better LLM parsing.

Uses a lightweight LLM to clean and structure any transcript format.
Handles:
- Line-break artifacts (joining broken lines)
- OCR-like errors (fixing misspellings)
- Capitalization normalization
- Date extraction and standardization
- Paragraph segmentation
"""

from __future__ import annotations

from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from pipeline.agent.config import AgentConfig
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.llm import create_llm_with_fallbacks
from pipeline.agent.log_config import get_logger
from pipeline.agent.schemas.validation import AuditEvent, PipelineError

logger = get_logger(__name__)

_PROMPT = """You are a historical transcript cleaner. Clean up the provided text for downstream entity extraction.

Tasks:
1. Join broken lines and fix obvious OCR errors (e.g., "frilia" → "Phrygia", "isus" → "Issus").
2. Normalize capitalization (proper nouns, start of sentences).
3. Fix punctuation and spacing issues.
4. Extract inline dates (e.g., "334 BCE", "331 BC") and ensure they are clearly associated with events.
5. Structure into logical paragraphs separated by blank lines.
6. Keep the original meaning and facts intact.

Output strictly as JSON:
{"cleaned_text": "Cleaned and structured transcript here..."}
"""


def preprocess_transcript(state: AgentRunState) -> AgentRunState:
    """Clean and structure raw transcript text."""
    cfg = AgentConfig()
    # Was a bare create_llm (no fallback, no retry); use the fallback factory so a
    # malformed clean-up response retries/falls back like the other nodes.
    llm = create_llm_with_fallbacks("parse_model", cfg, reasoning_effort=cfg.reasoning_effort)

    logger.info("LLM call: preprocess_transcript (model=%s, input=%d chars)",
                cfg.parse_model, len(state["raw_input"]))

    messages = [
        SystemMessage(content=_PROMPT),
        HumanMessage(content=state["raw_input"]),
    ]

    try:
        data = llm.invoke_json(
            messages, validate=lambda d: isinstance(d, dict) and "cleaned_text" in d
        )
        cleaned = (data.get("cleaned_text") or "").strip()
        if cleaned:
            state["raw_input"] = cleaned
        else:
            state["errors"].append(PipelineError(
                node="preprocess_transcript",
                error_type="empty_output",
                message="LLM returned empty cleaned text, using original.",
                context={"original_length": len(state["raw_input"])},
            ))
    except Exception as exc:
        state["errors"].append(PipelineError(
            node="preprocess_transcript",
            error_type="json_parse",
            message=str(exc),
            context={},
        ))

    state["audit_log"].append(
        AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            node="preprocess_transcript",
            action="preprocessed",
            input_summary=f"Original: {len(state['raw_input'])} chars",
            output_summary=f"Cleaned: {len(state['raw_input'])} chars",
        )
    )
    return state