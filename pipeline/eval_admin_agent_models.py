#!/usr/bin/env python3
"""Side-by-side eval of OpenRouter models for the History Mapped **admin AI
editing agent** (the config/ai.php model — NOT the LangGraph pipeline).

Replays the real agent loop across several SCENARIOS: system prompt + tool
schemas + one user turn, executing the model's tool calls with stubs (real,
live Wikidata for `verify_wikidata`) and feeding results back until the model
stops — exactly what the Laravel EntityEditorAgent / ChronicleEditorAgent do.
Each scenario AUTO-GRADES the tool-calling against a rubric and prints any
proposed summary so YOU can judge writing quality.

Scenarios:
  1. fix-karnak       (entity editor)    QID + location + summary-from-source
  2. link-new-entity  (entity editor)    nested create-relationship via new_target
  3. chronicle-relate (chronicle editor) link two referenced entities + write a summary

No third-party deps (stdlib urllib). Run:

    python3 pipeline/eval_admin_agent_models.py
    python3 pipeline/eval_admin_agent_models.py --models openai/gpt-5-mini,mistralai/mistral-medium-3.1
    python3 pipeline/eval_admin_agent_models.py --scenarios chronicle-relate
    python3 pipeline/eval_admin_agent_models.py --repeat 3        # run each combo N times

Key: --key, then $OPENROUTER_API_KEY, then api/.env / pipeline/.env.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

DEFAULT_MODELS = [
    "openai/gpt-5-mini",
    "mistralai/mistral-medium-3.1",      # verify slug on openrouter.ai/models
    "google/gemini-3.1-flash-lite",      # verify slug
    "qwen/qwen3.7-plus",                 # verify slug (Chinese family)
]

# ── Tool schemas (mirror the Laravel AgentTool schemas) ───────────────────────
def _tool(name, desc, props, required=None):
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required or []}}}

T_GET_CONTEXT = _tool("get_entity_context", "Return the bound entity's live state. Read-only.", {})
T_VERIFY = _tool("verify_wikidata", "Look up a Wikidata QID (label, description, P31, coordinate). Read-only. Use before set_entity_wikidata.",
                 {"qid": {"type": "string", "description": "e.g. Q522862"}}, ["qid"])
T_SET_QID = _tool("set_entity_wikidata", "Correct an entity's Wikidata QID. Rejects namesakes (songs/streets/films) by P31; cascades into provenance.",
                  {"entity_id": {"type": "string"}, "wikidata_id": {"type": "string"}}, ["entity_id", "wikidata_id"])
T_SET_LOC = _tool("set_entity_location", "Set the entity's primary location to a coordinate. Use for any location change.",
                  {"entity_id": {"type": "string"}, "lon": {"type": "number"}, "lat": {"type": "number"}}, ["entity_id", "lon", "lat"])
T_UPDATE = _tool("update_entity_fields", "Update one or more fields. Only pass fields you want changed; others are preserved.",
                 {"entity_id": {"type": "string"}, "name": {"type": "string"}, "summary": {"type": "string"},
                  "significance": {"type": "string"}, "entity_type": {"type": "string"},
                  "start_year": {"type": "integer"}, "end_year": {"type": "integer"}}, ["entity_id"])
T_REL = _tool("create_relationship", "Link this entity to another (type + optional dates). If the target does not exist yet, pass new_target to create it first instead of a UUID.",
              {"source_entity_id": {"type": "string"}, "relationship_type": {"type": "string"},
               "target_entity_id": {"type": "string"},
               "new_target": {"type": "object", "properties": {"name": {"type": "string"}, "entity_type": {"type": "string"},
                              "wikidata_id": {"type": "string"}, "lon": {"type": "number"}, "lat": {"type": "number"}}},
               "start_year": {"type": "integer"}, "end_year": {"type": "integer"}}, ["source_entity_id", "relationship_type"])
T_CREATE = _tool("create_entity", "Create a new historical entity. Verify any wikidata_id first; pass a representative lon/lat when known.",
                 {"name": {"type": "string"}, "entity_type": {"type": "string"}, "wikidata_id": {"type": "string"},
                  "summary": {"type": "string"}, "lon": {"type": "number"}, "lat": {"type": "number"},
                  "start_year": {"type": "integer"}, "end_year": {"type": "integer"}}, ["name", "entity_type"])
T_MERGE = _tool("merge_duplicate_entities", "Merge a duplicate (loser) into the survivor, re-pointing its relationships.",
                {"survivor_id": {"type": "string"}, "loser_id": {"type": "string"}}, ["survivor_id", "loser_id"])

ENTITY_TOOLS = [T_GET_CONTEXT, T_VERIFY, T_SET_QID, T_SET_LOC, T_UPDATE, T_REL, T_CREATE, T_MERGE]
# ChronicleEditorAgent exposes the staging tools + verify, but NOT get_entity_context.
CHRONICLE_TOOLS = [T_VERIFY, T_SET_QID, T_SET_LOC, T_UPDATE, T_REL, T_CREATE, T_MERGE]


# ── grading helpers ───────────────────────────────────────────────────────────
def _names(tc):
    return [n for n, _ in tc]


def _arg(tc, name):
    return next((a for n, a in tc if n == name), None)


def _score(checks, flags, summary=""):
    return {"checks": checks, "flags": flags, "score": sum(1 for v in checks.values() if v),
            "max": len(checks), "summary_text": summary}


# ════════════════════════════════════════════════════════════════════════════
# SCENARIO 1 — fix Karnak (entity editor): QID + location + summary
# ════════════════════════════════════════════════════════════════════════════
KARNAK_ID = "abc11ad4-2527-4eb6-bb22-54d3cd1d3d9d"

S1_SYSTEM = f"""You are the **History Mapped Entity Editor**, an AI assistant embedded in an operator-facing admin panel for a historical atlas.

## Current Entity

- **entity_id**: {KARNAK_ID}
- **name**: Karnak
- **entity_type**: infrastructure_monument
- **entity_group**: PLACE
- **wikidata_id**: Q19291734
- **summary**: (none)
- **location**: lon=5.3878, lat=52.1893, method=wikidata
- **temporal_start**: (none)
- **temporal_end**: (none)
- **relationships**: (none)

## Rules

1. **Propose, never assert.** Every change is staged for an operator to review and apply. You do not write directly to the database.
2. **Verify Wikidata QIDs first.** Before calling `set_entity_wikidata`, always call `verify_wikidata` with the QID and confirm the label matches this entity.
3. **Use `set_entity_location` for coordinates.** Do not encode location changes as field updates.
4. **The current entity's id is `{KARNAK_ID}`.** Pass it as `entity_id` whenever a tool requires it.
5. **To link to an entity that does not exist yet**, pass `new_target` to `create_relationship` instead of a target UUID.
6. **Read context first** with `get_entity_context` before proposing changes.
7. **Be concise.** Summarise what you proposed and why."""

S1_USER = """This record is wrong — it's pointing at a street in the Netherlands. It should be the Karnak temple complex at Luxor in Upper Egypt; its Wikidata is Q522862 (coordinates roughly 32.6583 E, 25.7183 N). Fix the QID and the location.

Also it has no summary — write a concise 2-3 sentence encyclopedia-style description from this source text, and set the build period to roughly 2000 BCE-30 BCE:

\"\"\"
Karnak is a vast complex of temples, chapels, pylons and obelisks near Thebes (modern Luxor), developed over more than two thousand years from the Middle Kingdom onward. Its core was the Precinct of Amun-Re, expanded by successive pharaohs including Hatshepsut, Thutmose III and the Ramessides into the largest religious building ever constructed. It remained the principal place of worship of the Theban Triad and a centre of priestly power until the Ptolemaic period.
\"\"\""""

S1_STATE = {"entity_id": KARNAK_ID, "name": "Karnak", "entity_type": "infrastructure_monument",
            "wikidata_id": "Q19291734", "summary": None,
            "location": {"lon": 5.3878, "lat": 52.1893, "method": "wikidata"},
            "temporal_start": None, "temporal_end": None, "relationships": []}


def s1_grade(tc):
    checks, flags = {}, []
    verified = any(n == "verify_wikidata" and a.get("qid") == "Q522862" for n, a in tc)
    nm = _names(tc)
    before = ("set_entity_wikidata" in nm and "verify_wikidata" in nm
              and nm.index("verify_wikidata") < nm.index("set_entity_wikidata"))
    checks["verify_before_setqid"] = verified and before
    sw = _arg(tc, "set_entity_wikidata")
    checks["set_qid_Q522862"] = bool(sw and sw.get("wikidata_id") == "Q522862" and sw.get("entity_id") == KARNAK_ID)
    sl = _arg(tc, "set_entity_location")
    if sl and "lon" in sl and "lat" in sl:
        lon, lat = float(sl["lon"]), float(sl["lat"])
        checks["location_luxor"] = (32.4 <= lon <= 32.9) and (25.5 <= lat <= 26.0)
        if (25.5 <= lon <= 26.0) and (32.4 <= lat <= 32.9):
            flags.append("LON/LAT SWAPPED in set_entity_location")
        if abs(lon - 5.3878) < 0.1:
            flags.append("kept the old Netherlands coordinate")
    else:
        checks["location_luxor"] = False
    uf = _arg(tc, "update_entity_fields")
    summary = (uf or {}).get("summary") or ""
    checks["wrote_summary"] = len(summary.strip()) >= 40
    if uf and ("start_year" in uf or "end_year" in uf):
        sy, ey = uf.get("start_year"), uf.get("end_year")
        checks["years_signed_bce"] = (sy is not None and -2200 <= sy <= -1500) and (ey is not None and -200 <= ey <= 100)
        if (sy is not None and sy > 0) or (ey is not None and ey > 1000):
            flags.append(f"BCE years not negative (start={sy}, end={ey})")
    else:
        checks["years_signed_bce"] = False
    spurious = [n for n in nm if n in ("merge_duplicate_entities", "create_entity", "create_relationship")]
    checks["no_spurious_tools"] = not spurious
    if spurious:
        flags.append(f"spurious tool(s): {', '.join(sorted(set(spurious)))}")
    return _score(checks, flags, summary)


# ════════════════════════════════════════════════════════════════════════════
# SCENARIO 2 — link to a NEW entity (entity editor): nested create via new_target
# ════════════════════════════════════════════════════════════════════════════
HAT_ID = "d4e15e9a-1111-4aaa-bbbb-000000000001"

S2_SYSTEM = f"""You are the **History Mapped Entity Editor**, an AI assistant embedded in an operator-facing admin panel for a historical atlas.

## Current Entity

- **entity_id**: {HAT_ID}
- **name**: Hatshepsut
- **entity_type**: person
- **entity_group**: PERSON
- **wikidata_id**: Q1523
- **summary**: Fifth pharaoh of the Eighteenth Dynasty of Egypt, one of the few women to rule as pharaoh.
- **temporal_start**: -1507
- **temporal_end**: -1458
- **relationships**: (none)

## Rules

1. **Propose, never assert.** Every change is staged for an operator to review and apply.
2. **The current entity's id is `{HAT_ID}`.** Pass it as `source_entity_id` for relationships.
3. **To link to an entity that does NOT exist yet**, pass `new_target` (with a name and entity_type) to `create_relationship` instead of a target UUID. Do NOT invent a target_entity_id, and do NOT call create_entity separately for the relationship target.
4. **Use the appropriate relationship_type** (e.g. commissioned, built, located_at, part_of).
5. **Be concise.** Summarise what you proposed and why."""

S2_USER = """Hatshepsut commissioned her great mortuary temple at Deir el-Bahari, across the Nile from Karnak — but that temple is not in our system yet. Add it (it's a monument, roughly 32.6063 E, 25.7380 N) and link Hatshepsut to it as having commissioned it."""

S2_STATE = {"entity_id": HAT_ID, "name": "Hatshepsut", "entity_type": "person", "wikidata_id": "Q1523",
            "temporal_start": -1507, "temporal_end": -1458, "relationships": []}


def s2_grade(tc):
    checks, flags = {}, []
    nm = _names(tc)
    rel = _arg(tc, "create_relationship")
    checks["called_create_relationship"] = rel is not None
    checks["source_is_hatshepsut"] = bool(rel and rel.get("source_entity_id") == HAT_ID)
    nt = (rel or {}).get("new_target")
    checks["used_new_target"] = bool(isinstance(nt, dict) and (nt.get("name") or "").strip())
    checks["relationship_type_present"] = bool(rel and (rel.get("relationship_type") or "").strip())
    # must NOT fabricate a target UUID nor split into a separate create_entity call
    fabricated = bool(rel and rel.get("target_entity_id"))
    split = "create_entity" in nm
    checks["no_fabricated_target"] = not (fabricated or split)
    if fabricated:
        flags.append(f"passed a target_entity_id ({rel['target_entity_id']}) for a non-existent entity")
    if split:
        flags.append("called create_entity separately instead of using new_target (the relationship target can't be resolved this way)")
    if isinstance(nt, dict) and not nt.get("entity_type"):
        flags.append("new_target missing entity_type")
    return _score(checks, flags, "")


# ════════════════════════════════════════════════════════════════════════════
# SCENARIO 3 — chronicle editor: relate two referenced entities + write a summary
# ════════════════════════════════════════════════════════════════════════════
CHRON_ID = "c0000000-0000-4000-8000-000000000001"
THUT_ID = "11111111-1111-4111-8111-111111111111"
HATC_ID = "22222222-2222-4222-8222-222222222222"
KARC_ID = "33333333-3333-4333-8333-333333333333"

S3_SYSTEM = f"""You are the **History Mapped Chronicle Editor**, an AI assistant embedded in an operator-facing admin panel for a historical atlas.

## Current Chronicle

- **chronicle_id**: {CHRON_ID}
- **title**: New Kingdom Egypt
- **status**: draft
- **start_year**: -1550
- **end_year**: -1077
- **entry_count**: 2

## Chronicle Entries

- **entry_id**: e1 | years: -1479–-1458 | Hatshepsut reigns as pharaoh and undertakes major building works at Karnak.
- **entry_id**: e2 | years: -1458–-1425 | Thutmose III, after years as co-regent, campaigns in the Levant and expands the temple at Karnak.

## Referenced Entities

- {THUT_ID} — Thutmose III (person)
- {HATC_ID} — Hatshepsut (person)
- {KARC_ID} — Karnak (infrastructure_monument)

## Rules

1. **Propose, never assert.** Every change is staged for an operator to review and apply.
2. **You help curate this chronicle's entities.** Act on the entities listed above by their id — pass the id as `entity_id` (or `source_entity_id`/`target_entity_id` for relationships). Use the real ids above; do not invent ids.
3. **Verify Wikidata QIDs first** before `set_entity_wikidata`.
4. **To link to an entity that does not exist yet**, pass `new_target` to `create_relationship`.
5. **Be concise.** Summarise what you proposed and why."""

S3_USER = """Two fixes for this chronicle's entities:

1. Thutmose III was co-regent with Hatshepsut for the early part of his reign — add a relationship recording that the two were co-rulers.
2. The Karnak entity referenced here has no description. Write a concise 1-2 sentence summary of Karnak suitable for this New Kingdom chronicle."""

S3_STATE = {}  # chronicle agent has no get_entity_context tool


def s3_grade(tc):
    checks, flags = {}, []
    nm = _names(tc)
    rel = _arg(tc, "create_relationship")
    if rel:
        ids = {rel.get("source_entity_id"), rel.get("target_entity_id")}
        checks["linked_thut_and_hat"] = ids == {THUT_ID, HATC_ID}
        if rel.get("target_entity_id") not in (THUT_ID, HATC_ID, None) or rel.get("source_entity_id") not in (THUT_ID, HATC_ID):
            flags.append("relationship used an id not in the chronicle's referenced entities")
    else:
        checks["linked_thut_and_hat"] = False
    checks["relationship_type_present"] = bool(rel and (rel.get("relationship_type") or "").strip())
    uf = _arg(tc, "update_entity_fields")
    summary = (uf or {}).get("summary") or ""
    checks["karnak_summary_on_right_id"] = bool(uf and uf.get("entity_id") == KARC_ID and len(summary.strip()) >= 30)
    spurious = [n for n in nm if n in ("merge_duplicate_entities", "create_entity")]
    checks["no_spurious_tools"] = not spurious
    if spurious:
        flags.append(f"spurious tool(s): {', '.join(sorted(set(spurious)))}")
    return _score(checks, flags, summary)


SCENARIOS = {
    "fix-karnak": {"label": "fix Karnak (entity: QID + location + summary)", "system": S1_SYSTEM,
                   "user": S1_USER, "tools": ENTITY_TOOLS, "state": S1_STATE, "grade": s1_grade},
    "link-new-entity": {"label": "link to a NEW entity (nested create_relationship)", "system": S2_SYSTEM,
                        "user": S2_USER, "tools": ENTITY_TOOLS, "state": S2_STATE, "grade": s2_grade},
    "chronicle-relate": {"label": "chronicle: relate two entities + write a summary", "system": S3_SYSTEM,
                         "user": S3_USER, "tools": CHRONICLE_TOOLS, "state": S3_STATE, "grade": s3_grade},
}


# ── Live Wikidata (mirrors app/Services/WikidataService.php) ──────────────────
def live_wikidata(qid: str) -> dict | None:
    try:
        req = urllib.request.Request(f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json",
                                     headers={"User-Agent": "history-mapped-eval/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.load(r)
        ent = data.get("entities", {}).get(qid)
        if not isinstance(ent, dict):
            return None
        claims = ent.get("claims", {})
        coord = None
        if claims.get("P625"):
            v = claims["P625"][0].get("mainsnak", {}).get("datavalue", {}).get("value")
            if v:
                coord = {"lon": v["longitude"], "lat": v["latitude"]}
        p31 = [c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id") for c in claims.get("P31", [])]
        return {"label": ent.get("labels", {}).get("en", {}).get("value"),
                "description": ent.get("descriptions", {}).get("en", {}).get("value"),
                "p31": [x for x in p31 if x], "coord": coord}
    except Exception as e:  # noqa: BLE001
        return {"error": f"wikidata lookup failed: {e}"}


def exec_tool(name: str, args: dict, state: dict) -> str:
    if name == "get_entity_context":
        return json.dumps(state)
    if name == "verify_wikidata":
        meta = live_wikidata(args.get("qid", ""))
        return json.dumps(meta if meta is not None else {"error": "QID not found"})
    return json.dumps({"proposal_id": "prop-eval-0001",
                       "parts": [{"key": name, "tool": name, "human_diff": {"summary": "staged for operator review"}}],
                       "note": "Proposed. Awaiting the operator to Apply each part."})


def call_openrouter(key, model, messages, tools, temperature):
    body = json.dumps({"model": model, "messages": messages, "tools": tools, "tool_choice": "auto",
                       "temperature": temperature, "usage": {"include": True}}).encode()
    req = urllib.request.Request(OPENROUTER_URL, data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                          "HTTP-Referer": "https://history-mapped.local", "X-Title": "history-mapped admin-agent eval"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def run(key, model, scenario, temperature, max_turns=6):
    messages = [{"role": "system", "content": scenario["system"]}, {"role": "user", "content": scenario["user"]}]
    tool_calls, final_text, cost, ptok, ctok = [], "", 0.0, 0, 0
    t0 = time.time()
    for _ in range(max_turns):
        resp = call_openrouter(key, model, messages, scenario["tools"], temperature)
        u = resp.get("usage") or {}
        cost += float(u.get("cost") or 0); ptok += int(u.get("prompt_tokens") or 0); ctok += int(u.get("completion_tokens") or 0)
        msg = resp["choices"][0]["message"]
        calls = msg.get("tool_calls") or []
        if not calls:
            final_text = msg.get("content") or ""
            break
        messages.append({"role": "assistant", "content": msg.get("content"), "tool_calls": calls})
        for c in calls:
            fn = c["function"]["name"]
            try:
                fargs = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                fargs = {"__raw__": c["function"].get("arguments")}
            tool_calls.append((fn, fargs))
            messages.append({"role": "tool", "tool_call_id": c["id"], "name": fn, "content": exec_tool(fn, fargs, scenario["state"])})
    return {"tool_calls": tool_calls, "final_text": final_text, "latency_s": round(time.time() - t0, 1),
            "cost_usd": round(cost, 5), "prompt_tokens": ptok, "completion_tokens": ctok}


def find_key(cli_key):
    import os
    if cli_key:
        return cli_key
    if os.environ.get("OPENROUTER_API_KEY"):
        return os.environ["OPENROUTER_API_KEY"]
    root = Path(__file__).resolve().parent.parent
    for envf in (root / "api" / ".env", root / "pipeline" / ".env"):
        if envf.exists():
            txt = envf.read_text()
            for var in ("OPENROUTER_API_KEY", "OPENAI_API_KEY"):
                m = re.search(rf"^{var}=(.+)$", txt, re.MULTILINE)
                if m and (val := m.group(1).strip().strip('"').strip("'")).startswith("sk-or-"):
                    return val
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models")
    ap.add_argument("--scenarios", help="comma-separated scenario keys (default: all)")
    ap.add_argument("--key")
    ap.add_argument("--temperature", type=float, default=0.3)
    ap.add_argument("--repeat", type=int, default=1, help="run each model×scenario N times (variance check)")
    args = ap.parse_args()

    key = find_key(args.key)
    if not key:
        print("No OpenRouter key. --key sk-or-..., $OPENROUTER_API_KEY, or api/.env.", file=sys.stderr); return 1
    models = [m.strip() for m in args.models.split(",")] if args.models else DEFAULT_MODELS
    keys = [s.strip() for s in args.scenarios.split(",")] if args.scenarios else list(SCENARIOS)

    agg = {m: {} for m in models}  # model -> scenario -> [scores], plus cost/latency
    for skey in keys:
        sc = SCENARIOS[skey]
        print(f"\n{'#'*78}\n# SCENARIO: {skey} — {sc['label']}\n{'#'*78}")
        for model in models:
            print(f"\n{'='*78}\n▶ {model}\n{'='*78}")
            scores, last = [], None
            for i in range(args.repeat):
                try:
                    r = run(key, model, sc, args.temperature)
                except urllib.error.HTTPError as e:
                    print(f"  HTTP {e.code}: {e.read().decode()[:240]}  (check slug on openrouter.ai/models)"); r = None; break
                except Exception as e:  # noqa: BLE001
                    print(f"  ERROR: {e}"); r = None; break
                g = sc["grade"](r["tool_calls"]); scores.append(g["score"]); last = (r, g)
                if args.repeat > 1:
                    print(f"  run {i+1}: {g['score']}/{g['max']}")
            if not last:
                continue
            r, g = last
            agg[model][skey] = {"scores": scores, "max": g["max"], "cost": r["cost_usd"], "lat": r["latency_s"]}
            print(f"  tool-calls ({len(r['tool_calls'])}): " + ", ".join(n for n, _ in r["tool_calls"]))
            for n, a in r["tool_calls"]:
                compact = {k: (v[:50] + "…" if isinstance(v, str) and len(v) > 50 else v) for k, v in a.items()}
                print(f"      {n}({json.dumps(compact, ensure_ascii=False)})")
            print(f"  SCORE {g['score']}/{g['max']}" + (f"  (runs: {scores})" if args.repeat > 1 else ""))
            for chk, ok in g["checks"].items():
                print(f"    [{'✓' if ok else '✗'}] {chk}")
            for f in g["flags"]:
                print(f"    ⚠ {f}")
            if g["summary_text"]:
                print(f"  ── PROPOSED SUMMARY (judge writing) ──\n  {g['summary_text']}")
            print(f"  final: {r['final_text'][:160]}")
            print(f"  {r['latency_s']}s · ${r['cost_usd']} · {r['prompt_tokens']}+{r['completion_tokens']} tok")

    # ── aggregate matrix ──────────────────────────────────────────────────────
    print(f"\n\n{'='*78}\nSUMMARY  (tool-calling auto-score; WRITING is yours to judge above)\n{'='*78}")
    hdr = f"{'model':<34}" + "".join(f"{k[:14]:>15}" for k in keys) + f"{'cost$':>9}{'avg lat':>9}"
    print(hdr)
    for model in models:
        cells = ""
        tcost, lats = 0.0, []
        for k in keys:
            d = agg[model].get(k)
            if d:
                avg = sum(d["scores"]) / len(d["scores"])
                cells += f"{avg:>11.1f}/{d['max']:<3}"
                tcost += d["cost"]; lats.append(d["lat"])
            else:
                cells += f"{'—':>15}"
        avglat = f"{sum(lats)/len(lats):.1f}s" if lats else "—"
        print(f"{model:<34}{cells}{round(tcost,4):>9}{avglat:>9}")
    print("\nScores are tool-calling only. Read the PROPOSED SUMMARY blocks for writing quality.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
