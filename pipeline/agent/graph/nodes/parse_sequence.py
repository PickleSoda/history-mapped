from __future__ import annotations

import json
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from pipeline.agent.config import AgentConfig
from pipeline.agent.llm import create_llm_with_fallbacks
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.entities import ParsedEvent
from pipeline.agent.logging import get_logger
from pipeline.agent.schemas.validation import AuditEvent, PipelineError

logger = get_logger(__name__)

_PROMPT = """You are a historical event parser. Convert the provided historical text into a structured list of events.

For each event, extract:
- label: a concise title
- description: a 1-sentence summary
- start_date: ISO date if known, else null
- end_date: ISO date if known, else null
- mentioned_entities: list of named entities mentioned
- date_uncertain: true if the date is vague or estimated

Output strictly as JSON matching this schema:
{"events": [{"label": "...", "description": "...", "start_date": "...", "end_date": "...", "mentioned_entities": [...], "date_uncertain": false}]}
"""


def parse_sequence(state: AgentRunState) -> AgentRunState:
    cfg = AgentConfig()
    llm = create_llm_with_fallbacks("parse_model", cfg)
    logger.info("LLM call: parse_sequence (model=%s)", cfg.parse_model)
    messages = [SystemMessage(content=_PROMPT), HumanMessage(content=state["raw_input"])]
    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)
    logger.info("LLM response: %d chars", len(content))
    # Strip markdown code fences if present
    if content.strip().startswith("```json"):
        content = content.strip().removeprefix("```json").removesuffix("```").strip()
    try:
        data = json.loads(content)
        events = [ParsedEvent(**e) for e in data.get("events", [])]
    except (json.JSONDecodeError, TypeError) as exc:
        state["errors"].append(
            PipelineError(
                node="parse_sequence",
                error_type="json_parse",
                message=str(exc),
                context={"raw_response": content},
            )
        )
        events = []
    state["parsed_events"] = events
    state["audit_log"].append(
        AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            node="parse_sequence",
            action="parsed_events",
            input_summary=state["raw_input"][:100],
            output_summary=f"{len(events)} events extracted",
        )
    )
    return state
