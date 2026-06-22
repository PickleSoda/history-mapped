#!/usr/bin/env python3
"""Backfill entity summaries the failed batch left empty (the generate_content
truncation: 268 entities committed with no summary because max_tokens was 8000).

Regenerates ONLY the missing summaries — reusing the pipeline's own content prompt
and the (now 32k-token) generate model — from each entity's name, type, dates,
Wikidata gloss, and its relationships in the DB. Cheap and targeted: no re-parse,
no re-extract, and the 802 good summaries are untouched.

Dry-run by default (generates + prints samples, writes nothing). --apply writes.
--limit N caps entities for a cheap quality check.

    pipeline/.venv/bin/python3 -m pipeline.backfill_summaries --limit 6     # preview
    pipeline/.venv/bin/python3 -m pipeline.backfill_summaries --apply       # write all
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import psycopg
from langchain_core.messages import HumanMessage

from pipeline.agent.config import AgentConfig
from pipeline.agent.json_utils import parse_llm_json
from pipeline.agent.llm import create_llm_with_fallbacks
from pipeline.agent.tools.wikidata import fetch_entity_meta
from pipeline.agent.graph.nodes.generate_content import (
    _ENTITY_PROMPT, _load_style_guide, _sentence_count, _chunked, ENTITY_CHUNK_SIZE,
)

DSN = "postgresql://history-mapped:secret@localhost:5432/history-mapped"


def load_targets(cur, limit: int) -> list[dict]:
    """Entities with no summary, plus their type/dates/QID."""
    cur.execute("""
        SELECT e.entity_id, e.name, e.entity_type::text, e.wikidata_id,
               t.start_date, t.end_date, t.start_year, t.end_year
        FROM entities e
        LEFT JOIN entity_temporal_ranges t ON t.entity_id = e.entity_id
        WHERE e.summary IS NULL OR e.summary = ''
        ORDER BY e.name
    """)
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    return rows[:limit] if limit else rows


def load_relationships(cur, ids: list[str]) -> dict[str, list[dict]]:
    """Relationships touching each target entity (both directions), with the other
    side's name — the grounding context the summary prompt expects."""
    if not ids:
        return {}
    cur.execute("""
        SELECT r.source_entity_id, s.name AS source_name,
               r.target_entity_id, t.name AS target_name,
               r.relationship_type::text
        FROM relationships r
        JOIN entities s ON s.entity_id = r.source_entity_id
        JOIN entities t ON t.entity_id = r.target_entity_id
        WHERE r.source_entity_id = ANY(%s) OR r.target_entity_id = ANY(%s)
    """, (ids, ids))
    out: dict[str, list[dict]] = {}
    for src, src_name, tgt, tgt_name, rtype in cur.fetchall():
        out.setdefault(str(src), []).append({"role": "source", "type": rtype, "other": tgt_name})
        out.setdefault(str(tgt), []).append({"role": "target", "type": rtype, "other": src_name})
    return out


def build_context(row: dict, rels: list[dict], wd_desc: str | None) -> dict:
    start = row["start_date"] or (str(row["start_year"]) if row["start_year"] is not None else None)
    end = row["end_date"] or (str(row["end_year"]) if row["end_year"] is not None else None)
    return {
        "label": row["name"],
        "type": row["entity_type"],
        "dates": {"start": start, "end": end},
        "wikidata_description": wd_desc,
        "source_event": None,
        "relationships": rels[:12],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write summaries (default: dry run)")
    ap.add_argument("--limit", type=int, default=0, help="cap entities (cheap preview)")
    args = ap.parse_args()

    cfg = AgentConfig()
    llm = create_llm_with_fallbacks("generate_model", cfg, max_tokens=cfg.generate_max_tokens,
                                    reasoning_effort=cfg.reasoning_effort)
    style_guide = _load_style_guide()

    conn = psycopg.connect(DSN)
    cur = conn.cursor()

    targets = load_targets(cur, args.limit)
    print(f"{len(targets)} entities missing a summary\n")
    if not targets:
        return 0

    ids = [str(t["entity_id"]) for t in targets]
    rels_by_id = load_relationships(cur, ids)

    # Wikidata gloss for grounding (one batched call).
    qids = sorted({t["wikidata_id"] for t in targets if t["wikidata_id"]})
    desc_by_qid = {q: m.get("description", "") for q, m in fetch_entity_meta(qids).items()} if qids else {}

    generated: dict[str, dict] = {}
    by_name = {t["name"]: t for t in targets}

    # Small chunks keep each JSON response short (a reasoning model occasionally
    # emits an unescaped quote in long prose); a couple of retries mops up the rest.
    chunk_size = 3
    for chunk in _chunked(targets, chunk_size):
        context = [
            build_context(t, rels_by_id.get(str(t["entity_id"]), []),
                          desc_by_qid.get(t["wikidata_id"]))
            for t in chunk
        ]
        prompt = _ENTITY_PROMPT.format(style_guide=style_guide, entities=json.dumps(context, default=str))
        got_labels = set()
        for attempt in range(3):
            resp = llm.invoke([HumanMessage(content=prompt)])
            content = resp.content if hasattr(resp, "content") else str(resp)
            try:
                data = parse_llm_json(content)
            except (json.JSONDecodeError, TypeError):
                continue  # malformed JSON — retry this chunk
            for label, fields in (data.get("entities", {}) or {}).items():
                if label in by_name and isinstance(fields, dict) and fields.get("summary"):
                    generated[label] = {
                        "summary": fields["summary"],
                        "significance": fields.get("significance"),
                    }
                    got_labels.add(label)
            if len(got_labels) == len(chunk):
                break  # whole chunk covered
        missing = [t["name"] for t in chunk if t["name"] not in got_labels]
        if missing:
            print(f"  [unresolved after retries] {missing}")
        print(f"  generated {len(generated)}/{len(targets)}…", end="\r")

    print(f"\n\nGenerated {len(generated)} summaries "
          f"({sum(1 for g in generated.values() if _sentence_count(g['summary']) >= 3)} with ≥3 sentences)\n")

    for label in list(generated)[:5]:
        print(f"── {label} ──\n   {generated[label]['summary'][:300]}\n")

    if args.apply:
        n = 0
        for label, g in generated.items():
            t = by_name[label]
            cur.execute(
                "UPDATE entities SET summary = %s, significance = COALESCE(%s, significance), "
                "updated_at = now() WHERE entity_id = %s",
                (g["summary"], g["significance"], t["entity_id"]),
            )
            n += 1
        conn.commit()
        print(f"Wrote {n} summaries.")
    else:
        print("Dry run — re-run with --apply to write.")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
