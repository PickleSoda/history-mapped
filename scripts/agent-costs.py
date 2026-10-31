#!/usr/bin/env python3
"""Where did agents spend their time and tokens? Reads Claude Code transcripts.

    scripts/agent-costs.py ~/.claude-personal/projects/<project>/<session-id>/      # every subagent of a session
    scripts/agent-costs.py <session-dir> --match "battle-author|Author .* map story"  # filter by task description
    scripts/agent-costs.py <session>.jsonl                                           # one transcript
    scripts/agent-costs.py <dir> --detail                                            # per-category breakdown

Input: a transcript (.jsonl), a directory of `agent-*.jsonl`, or a session
directory with a `subagents/` folder. `--match` filters subagents on the
`description` in their `agent-*.meta.json` (a regex, case-insensitive).

Per agent: wall time, turns (API responses — a response split over several
transcript lines is counted once), billed tokens (uncached input + cache read
+ cache write + output), peak context, the tool categories that took the most
wall time, and the largest tool results. The transcripts are parsed line by
line and never printed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


def ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def category(name: str, inp: dict) -> str:
    """A coarse bucket for a tool call."""
    if name == "Bash":
        c = inp.get("command", "")
        m = re.search(r"pipeline\.map_stories\s+(\w+)", c)
        if m:
            return f"ms:{m.group(1)}"
        m = re.search(r"pipeline\.campaign\s+([\w-]+)", c)
        if m:
            return f"campaign:{m.group(1)}"
        if "psql" in c:
            return "bash:psql"
        if "youtube" in c.lower() or "ytvenv" in c:
            return "bash:youtube"
        if re.search(r"nominatim|place_geometry|elevation\(|profile\(|overpass", c, re.I):
            return "bash:geo-lookup"
        if re.search(r"\bcurl\b|wget|requests\.get|wikipedia", c, re.I):
            return "bash:http-fetch"
        if re.search(r"\bpytest\b", c):
            return "bash:pytest"
        if "python" in c:
            return "bash:python"
        if re.match(r"\s*(cat|head|tail|sed -n|less)\b", c):
            return "bash:cat"
        if re.match(r"\s*(grep|rg|find|ls)\b", c):
            return "bash:search"
        return "bash:other"
    if name == "Read":
        p = inp.get("file_path", "")
        if p.endswith((".png", ".jpg", ".jpeg", ".webp")):
            return "read:image"
        if p.endswith(".jsonl"):
            return "read:transcript"
        if p.endswith(".py"):
            return "read:code"
        if p.endswith(".md"):
            return "read:docs"
        if p.endswith(".json"):
            return "read:json"
        return "read:other"
    if name in ("Write", "Edit"):
        p = inp.get("file_path", "")
        where = "builder" if "stories/" in p else "description" if "entity-descriptions" in p else "other"
        return f"{name.lower()}:{where}"
    if name == "WebFetch":
        host = re.sub(r"^https?://([^/]+).*", r"\1", inp.get("url", ""))
        return "webfetch:" + ("wikipedia" if "wikipedia" in host else "wikidata" if "wikidata" in host else "other")
    return name.lower()


def short_input(name: str, inp: dict) -> str:
    if name == "Bash":
        return re.sub(r"\s+", " ", inp.get("command", ""))[:70]
    if name in ("Read", "Write", "Edit"):
        return inp.get("file_path", "").split("/")[-1][:70]
    if name == "WebFetch":
        return inp.get("url", "")[:70]
    return json.dumps(inp)[:70]


@dataclass
class Cat:
    n: int = 0
    secs: float = 0.0
    chars: int = 0


@dataclass
class Stats:
    label: str
    wall: float = 0.0
    turns: int = 0
    uncached: int = 0
    cache_read: int = 0
    cache_write: int = 0
    output: int = 0
    peak: int = 0
    cats: dict = field(default_factory=lambda: defaultdict(Cat))
    big: list = field(default_factory=list)

    @property
    def billed(self) -> int:
        return self.uncached + self.cache_read + self.cache_write + self.output


def analyse(path: Path, label: str) -> Stats:
    st = Stats(label)
    seen: set[str] = set()
    calls: dict[str, tuple[str, datetime | None, str, str]] = {}
    first = last = None
    with path.open() as f:
        for line in f:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = ts(r["timestamp"]) if r.get("timestamp") else None
            if t:
                first = first or t
                last = t
            if r.get("type") == "assistant":
                m = r.get("message") or {}
                mid = m.get("id") or r.get("uuid")
                if mid not in seen:
                    seen.add(mid)
                    u = m.get("usage") or {}
                    st.turns += 1
                    st.uncached += u.get("input_tokens", 0) or 0
                    st.cache_read += u.get("cache_read_input_tokens", 0) or 0
                    st.cache_write += u.get("cache_creation_input_tokens", 0) or 0
                    st.output += u.get("output_tokens", 0) or 0
                    ctx = (u.get("input_tokens", 0) or 0) + (u.get("cache_read_input_tokens", 0) or 0) + (u.get("cache_creation_input_tokens", 0) or 0)
                    st.peak = max(st.peak, ctx)
                for c in m.get("content") or []:
                    if isinstance(c, dict) and c.get("type") == "tool_use":
                        inp = c.get("input") or {}
                        cat = category(c.get("name", ""), inp)
                        calls[c["id"]] = (cat, t, c.get("name", ""), short_input(c.get("name", ""), inp))
                        st.cats[cat].n += 1
            elif r.get("type") == "user":
                content = (r.get("message") or {}).get("content")
                if not isinstance(content, list):
                    continue
                for c in content:
                    if not (isinstance(c, dict) and c.get("type") == "tool_result" and c.get("tool_use_id") in calls):
                        continue
                    cat, t0, name, short = calls[c["tool_use_id"]]
                    body = c.get("content")
                    size = len(body) if isinstance(body, str) else len(json.dumps(body))
                    st.cats[cat].chars += size
                    if t0 and t:
                        st.cats[cat].secs += max(0.0, (t - t0).total_seconds())
                    if cat != "read:image":
                        st.big.append((size, name, short))
    st.wall = (last - first).total_seconds() if first and last else 0.0
    st.big.sort(reverse=True)
    return st


def transcripts(target: Path, match: str | None) -> list[tuple[Path, str]]:
    if target.is_file():
        return [(target, target.stem)]
    folder = target / "subagents" if (target / "subagents").is_dir() else target
    out = []
    for p in sorted(folder.glob("agent-*.jsonl"), key=lambda p: p.stat().st_mtime):
        meta = p.with_suffix(".meta.json")
        desc = ""
        if meta.exists():
            try:
                desc = json.loads(meta.read_text()).get("description", "")
            except json.JSONDecodeError:
                pass
        if match and not re.search(match, desc, re.I):
            continue
        out.append((p, desc or p.stem))
    return out


def m(n: float) -> str:
    return f"{n / 1e6:.1f}M" if n >= 1e6 else f"{n / 1e3:.0f}k"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("target", type=Path, help="transcript .jsonl, a dir of agent-*.jsonl, or a session dir")
    ap.add_argument("--match", help="regex on the subagent's task description")
    ap.add_argument("--top", type=int, default=3, help="tool categories / largest results per agent")
    ap.add_argument("--detail", action="store_true", help="print every tool category per agent")
    args = ap.parse_args()

    files = transcripts(args.target.expanduser(), args.match)
    if not files:
        print("no transcripts matched", file=sys.stderr)
        return 1
    rows = [analyse(p, label) for p, label in files]
    print(f"{'agent':34} {'wall':>6} {'turns':>5} {'billed':>7} {'uncach':>6} {'c.read':>7} {'c.write':>7} {'output':>6} {'peak':>5}")
    for s in rows:
        print(f"{s.label[:34]:34} {s.wall / 60:5.0f}m {s.turns:5d} {m(s.billed):>7} {m(s.uncached):>6} {m(s.cache_read):>7} {m(s.cache_write):>7} {m(s.output):>6} {m(s.peak):>5}")
    if len(rows) > 1:
        n = len(rows)
        print(f"{'mean of ' + str(n):34} {sum(s.wall for s in rows) / n / 60:5.0f}m {sum(s.turns for s in rows) / n:5.0f} {m(sum(s.billed for s in rows) / n):>7} "
              f"{'':>6} {'':>7} {'':>7} {m(sum(s.output for s in rows) / n):>6} {m(sum(s.peak for s in rows) / n):>5}")
    for s in rows:
        cats = sorted(s.cats.items(), key=lambda kv: -kv[1].secs)
        shown = cats if args.detail else cats[: args.top]
        print(f"\n{s.label[:60]}")
        tools = sum(v.secs for v in s.cats.values())
        print(f"  time:    model/other {max(0.0, s.wall - tools) / 60:.0f}m, tools {tools / 60:.0f}m: " + ", ".join(f"{k} {v.secs / 60:.1f}m ×{v.n} ({v.chars / 1e3:.0f}k chars)" for k, v in shown))
        print("  largest: " + "; ".join(f"{size / 1e3:.0f}k {name} {short}" for size, name, short in s.big[: args.top]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
