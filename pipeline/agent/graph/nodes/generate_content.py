from __future__ import annotations

import json
import re
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


# Entities per LLM call. The old node summarised every entity in one blob, so
# each got a sliver of the token budget and came back as a one-line paraphrase of
# the Wikidata description. Small chunks give each entity real tokens; the rich
# per-entity context (its source event text + its relationships) gives the model
# something concrete to write from.
ENTITY_CHUNK_SIZE = 6


def _event_text_by_label(parsed_events: list) -> dict[str, str]:
    """Map each parsed event's label to its descriptive text (the source material)."""
    out: dict[str, str] = {}
    for event in parsed_events:
        label = getattr(event, "label", None)
        text = getattr(event, "description", None)
        if label and text:
            out[label] = text
    return out


def _relations_by_entity(candidate_relations: list) -> dict[str, list[dict[str, str]]]:
    """Group relationships touching each entity label, from both directions, so an
    entity's context lists what it did and what was done to/with it."""
    out: dict[str, list[dict[str, str]]] = {}
    for relation in candidate_relations:
        src, tgt = relation.source_label, relation.target_label
        rtype = relation.relationship_type
        if src and tgt:
            out.setdefault(src, []).append({"role": "source", "type": rtype, "other": tgt})
            out.setdefault(tgt, []).append({"role": "target", "type": rtype, "other": src})
    return out


def _entity_context(enriched, event_text: dict[str, str], rels: dict[str, list[dict[str, str]]]) -> dict:
    """Rich, grounded context for one entity: dates, Wikidata gloss, the text of
    the event it came from, and its relationships."""
    cand = enriched.candidate
    source_event = None
    if cand.source_event:
        source_event = {"label": cand.source_event, "text": event_text.get(cand.source_event)}
    return {
        "label": cand.label,
        "type": cand.entity_type,
        "dates": {"start": cand.start_date, "end": cand.end_date},
        "wikidata_description": enriched.wikidata_match.get("description") if enriched.wikidata_match else None,
        "source_event": source_event,
        "relationships": rels.get(cand.label, []),
    }


_ENTITY_PROMPT = """You are a historical content writer. For EACH entity below, write two fields:
- "summary": AT LEAST THREE full sentences (3–5) of specific, engaging, flowing prose — never a single
  sentence. Open with a vivid framing of what the entity is, then ground it in the entity's source-event text
  and relationships, naming concrete actors, places, dates, and outcomes, and close on its arc or fate. Write
  it like a paragraph in a popular history book, not a dictionary gloss. Do NOT just restate the Wikidata
  description.
- "significance": 1–2 sentences on why this entity matters historically — its consequences, role, or influence.

Draw on the source text and relationships first; for well-known entities you may add widely-established
historical facts to give a fuller, multi-sentence picture. Do not fabricate. Only omit an entity's key if you
genuinely cannot identify who or what it is — a recognised historical figure, place, or event should always get
both fields, and its summary must still be at least three sentences.

Write every field in English, regardless of the entity's origin (e.g. write "Born in 1783, Agustín
de Iturbide…", never "Nacido en 1783…").

Style Guide:
{style_guide}

Entities:
{entities}

Output strictly as JSON:
{{"entities": {{"<Entity Label>": {{"summary": "...", "significance": "..."}}, ...}}}}
"""


def _chunked(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _sentence_count(text: str | None) -> int:
    """Rough count of sentences — enough to tell a one-liner from a paragraph."""
    if not text:
        return 0
    return len(re.findall(r"[.!?](?:\s|$)", text.strip()))


def _apply_summary_pass(llm, prompt: str, by_label: dict, state: AgentRunState, stage: str) -> None:
    """Run one summary/significance LLM call and merge results, keeping the longer
    summary so a retry never regresses an entity to a shorter one."""
    response = llm.invoke([HumanMessage(content=prompt)])
    content = response.content if hasattr(response, "content") else str(response)
    try:
        data = parse_llm_json(content)
        for label, fields in (data.get("entities", {}) or {}).items():
            enriched = by_label.get(label)
            if enriched is None or not isinstance(fields, dict):
                continue
            new_summary = fields.get("summary")
            if new_summary and _sentence_count(new_summary) >= _sentence_count(enriched.summary):
                enriched.summary = new_summary
            enriched.significance = fields.get("significance") or enriched.significance
    except (json.JSONDecodeError, TypeError) as exc:
        state["errors"].append(
            PipelineError(
                node="generate_content",
                error_type="json_parse",
                message=str(exc),
                context={"raw_response": content, "stage": stage},
            )
        )


def generate_content(state: AgentRunState) -> AgentRunState:
    cfg = AgentConfig()
    llm = create_llm_with_fallbacks("generate_model", cfg, max_tokens=cfg.generate_max_tokens,
                                    reasoning_effort=cfg.reasoning_effort)
    style_guide = _load_style_guide()
    entities = state["enriched_entities"]
    relations = state["candidate_relations"]
    logger.info("LLM call: generate_content (model=%s, entities=%d, relations=%d, chunk=%d)",
                cfg.generate_model, len(entities), len(relations), ENTITY_CHUNK_SIZE)

    event_text = _event_text_by_label(state["parsed_events"])
    rels_by_entity = _relations_by_entity(relations)
    by_label = {e.candidate.label: e for e in entities}

    # ── Entity summaries + significance, in small chunks for depth ──────────
    for chunk in _chunked(entities, ENTITY_CHUNK_SIZE):
        context = json.dumps(
            [_entity_context(e, event_text, rels_by_entity) for e in chunk],
            default=str,
        )
        prompt = _ENTITY_PROMPT.format(style_guide=style_guide, entities=context)
        _apply_summary_pass(llm, prompt, by_label, state, "summary")

    # ── Guard: re-request any summary that came back too short (<3 sentences).
    # The model intermittently returns a one-liner despite the prompt; one extra
    # targeted pass over just the deficient entities enforces the floor without
    # regenerating everything.
    deficient = [e for e in entities if _sentence_count(e.summary) < 3]
    if deficient:
        logger.info("Re-requesting %d short summaries (<3 sentences)", len(deficient))
        for chunk in _chunked(deficient, ENTITY_CHUNK_SIZE):
            context = json.dumps(
                [_entity_context(e, event_text, rels_by_entity) for e in chunk],
                default=str,
            )
            prompt = _ENTITY_PROMPT.format(style_guide=style_guide, entities=context) + (
                "\n\nIMPORTANT: a previous attempt returned summaries that were too short. Write a NEW summary "
                "of at least THREE full sentences for EVERY entity above."
            )
            _apply_summary_pass(llm, prompt, by_label, state, "summary_retry")

    # ── Relation descriptions (short; one pass) ─────────────────────────────
    if relations:
        relations_context = json.dumps(
            [
                {"source": r.source_label, "target": r.target_label, "type": r.relationship_type,
                 "dates": {"start": r.start_date, "end": r.end_date}}
                for r in relations
            ],
            default=str,
        )
        rel_prompt = (
            "You are a historical content writer. Write one concise sentence describing each relationship, "
            "grounded in the entities and dates given.\n\n"
            f"Relations:\n{relations_context}\n\n"
            'Output strictly as JSON:\n{"relation_descriptions": {"Source|relationship_type|Target": "..."}}\n'
        )
        response = llm.invoke([HumanMessage(content=rel_prompt)])
        content = response.content if hasattr(response, "content") else str(response)
        try:
            rel_descs = parse_llm_json(content).get("relation_descriptions", {})
            for relation in relations:
                key = f"{relation.source_label}|{relation.relationship_type}|{relation.target_label}"
                relation.description = rel_descs.get(key)
        except (json.JSONDecodeError, TypeError) as exc:
            state["errors"].append(
                PipelineError(
                    node="generate_content",
                    error_type="json_parse",
                    message=str(exc),
                    context={"raw_response": content, "stage": "relation_descriptions"},
                )
            )

    # ── Engaging chronicle title when the caller didn't supply one ──────────
    # The fallback (first event's label) produces flat titles like "Plague of
    # Athens"; an LLM title over the whole entity set reads far better.
    if not (state.get("title") or "").strip() and entities:
        names = ", ".join(e.candidate.label for e in entities[:14])
        title_prompt = (
            "Write ONE engaging, specific title for a historical chronicle that covers these entities:\n"
            f"{names}\n\n"
            "Make it evocative yet accurate, like 'The Rise and Fall of the Byzantine Empire', 'Plagues That "
            "Reshaped the Ancient World', or 'How the Silk Road Bound East to West'. Max 9 words, no subtitle.\n"
            'Output strictly as JSON: {"title": "..."}'
        )
        try:
            resp = llm.invoke([HumanMessage(content=title_prompt)])
            tcontent = resp.content if hasattr(resp, "content") else str(resp)
            title = (parse_llm_json(tcontent).get("title") or "").strip()
            if title:
                state["title"] = title
                logger.info("Generated chronicle title: %s", title)
        except (json.JSONDecodeError, TypeError) as exc:
            state["errors"].append(
                PipelineError(
                    node="generate_content", error_type="json_parse",
                    message=str(exc), context={"raw_response": tcontent, "stage": "title"},
                )
            )

    summarised = sum(1 for e in entities if e.summary)
    with_significance = sum(1 for e in entities if e.significance)
    state["audit_log"].append(
        AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            node="generate_content",
            action="content_generated",
            output_summary=(
                f"{summarised}/{len(entities)} summaries, {with_significance} significance, "
                f"{len(relations)} relations"
            ),
        )
    )
    return state
