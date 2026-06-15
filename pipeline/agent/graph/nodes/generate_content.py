from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.messages import HumanMessage

from pipeline.agent.config import AgentConfig
from pipeline.agent.json_utils import parse_llm_json
from pipeline.agent.llm import create_llm_with_fallbacks
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.log_config import get_logger
from pipeline.agent.schemas.validation import AuditEvent, PipelineError

logger = get_logger(__name__)

_STYLE_GUIDE_PATH = Path(__file__).parent.parent.parent / "style_guide.md"


def _load_style_guide() -> str:
    if _STYLE_GUIDE_PATH.exists():
        return _STYLE_GUIDE_PATH.read_text(encoding="utf-8")
    return ""


def generate_content(state: AgentRunState) -> AgentRunState:
    cfg = AgentConfig()
    llm = create_llm_with_fallbacks("generate_model", cfg, max_tokens=cfg.generate_max_tokens)
    style_guide = _load_style_guide()
    logger.info("LLM call: generate_content (model=%s, entities=%d, relations=%d)",
                cfg.generate_model, len(state["enriched_entities"]), len(state["candidate_relations"]))
    entities_context = json.dumps(
        [
            {
                "label": e.candidate.label,
                "type": e.candidate.entity_type,
                "wikidata_description": e.wikidata_match.get("description")
                if e.wikidata_match
                else None,
                "dates": {"start": e.candidate.start_date, "end": e.candidate.end_date},
            }
            for e in state["enriched_entities"]
        ],
        default=str,
    )
    relations_context = json.dumps(
        [
            {
                "source": r.source_label,
                "target": r.target_label,
                "type": r.relationship_type,
                "dates": {"start": r.start_date, "end": r.end_date},
            }
            for r in state["candidate_relations"]
        ],
        default=str,
    )
    prompt = f"""You are a historical content writer. Write concise, flowing summaries and descriptions.\n\nStyle Guide:\n{style_guide}\n\nEntities:\n{entities_context}\n\nRelations:\n{relations_context}\n\nOutput strictly as JSON:\n{{"summaries": {{"Entity Label": "Summary text...", ...}}, "relation_descriptions": {{"Source Label|relationship_type|Target Label": "Description text...", ...}}}}\n"""
    response = llm.invoke([HumanMessage(content=prompt)])
    content = response.content if hasattr(response, "content") else str(response)
    try:
        data = parse_llm_json(content)
        summaries = data.get("summaries", {})
        rel_descs = data.get("relation_descriptions", {})
        for enriched in state["enriched_entities"]:
            enriched.summary = summaries.get(enriched.candidate.label)
        for relation in state["candidate_relations"]:
            key = f"{relation.source_label}|{relation.relationship_type}|{relation.target_label}"
            relation.description = rel_descs.get(key)
    except (json.JSONDecodeError, TypeError) as exc:
        state["errors"].append(
            PipelineError(
                node="generate_content",
                error_type="json_parse",
                message=str(exc),
                context={"raw_response": content},
            )
        )
    state["audit_log"].append(
        AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            node="generate_content",
            action="content_generated",
            output_summary=f"Generated content for {len(state['enriched_entities'])} entities, {len(state['candidate_relations'])} relations",
        )
    )
    return state
