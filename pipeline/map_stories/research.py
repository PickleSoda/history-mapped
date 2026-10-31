"""Read a battle's Wikipedia article and Wikidata facts in small, cached pieces.

    python -m pipeline.map_stories research "Battle of Waterloo"          # outline + infobox
    python -m pipeline.map_stories research Q48314 --section Hougoumont --section "La Haye Sainte"
    python -m pipeline.map_stories research "Battle of Waterloo" --qids Q131691 Q517

Text comes from the MediaWiki API as plain text per section (never WebFetch),
the infobox from the article's wikitext, dates and coordinates from Wikidata.
Every response is cached under output/map-stories/cache/, so a reviewer
re-reading the same sections costs nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from pipeline.map_stories.net import get_json, wd_entities, wd_labels

SKIP = {
    "see also", "references", "notes", "further reading", "external links", "bibliography",
    "sources", "citations", "footnotes", "works cited", "explanatory notes", "notes and references",
    "primary sources", "secondary sources", "general and cited sources", "cited sources",
}
LEAD = "lead"
_HEADING = re.compile(r"^(={2,6})\s*(.+?)\s*\1\s*$")
INFOBOX_KEYS = (
    "date", "place", "result", "territory",
    "combatant1", "combatant2", "combatant3", "commander1", "commander2", "commander3",
    "strength1", "strength2", "strength3", "casualties1", "casualties2", "casualties3",
)
LINKED_KEYS = ("combatant1", "combatant2", "combatant3", "commander1", "commander2", "commander3")


@dataclass
class Section:
    name: str
    level: int
    lines: list[str] = field(default_factory=list)

    @property
    def chars(self) -> int:
        return sum(len(x) + 1 for x in self.lines)


@dataclass
class Article:
    title: str
    qid: str | None
    lang: str
    sections: list[Section]
    wikitext: str

    def url(self) -> str:
        return f"https://{self.lang}.wikipedia.org/wiki/{self.title.replace(' ', '_')}"


def api(lang: str) -> str:
    return f"https://{lang}.wikipedia.org/w/api.php"


# ── fetching ──────────────────────────────────────────────────────────────


def resolve_title(ref: str, lang: str = "en") -> str:
    """A Wikipedia title from a title or a Q-id."""
    if re.fullmatch(r"Q[1-9]\d*", ref):
        row = wd_entities([ref]).get(ref) or {}
        if lang == "en" and row.get("enwiki"):
            return row["enwiki"]
        data = get_json("https://www.wikidata.org/w/api.php", {"action": "wbgetentities", "ids": ref, "props": "sitelinks", "sitefilter": f"{lang}wiki", "format": "json"})
        title = data.get("entities", {}).get(ref, {}).get("sitelinks", {}).get(f"{lang}wiki", {}).get("title")
        if not title:
            raise SystemExit(f"{ref} has no {lang}.wikipedia article")
        return title
    return ref


def fetch(ref: str, lang: str = "en", refresh: bool = False) -> Article:
    title = resolve_title(ref, lang)
    data = get_json(api(lang), {
        "action": "query", "prop": "extracts|pageprops|revisions", "explaintext": 1, "exsectionformat": "wiki",
        "ppprop": "wikibase_item", "rvprop": "content", "rvslots": "main", "redirects": 1,
        "titles": title, "format": "json", "formatversion": 2,
    }, refresh=refresh)
    pages = data.get("query", {}).get("pages") or [{}]
    page = pages[0]
    if page.get("missing") or not page.get("extract"):
        raise SystemExit(f"no article '{title}' on {lang}.wikipedia (try the exact title or the Q-id)")
    wikitext = ((page.get("revisions") or [{}])[0].get("slots", {}).get("main", {}).get("content")) or ""
    return Article(page["title"], page.get("pageprops", {}).get("wikibase_item"), lang, split_sections(page["extract"]), wikitext)


def split_sections(text: str) -> list[Section]:
    """Split an `exsectionformat=wiki` plain-text extract into sections."""
    out = [Section(LEAD, 2)]
    for line in text.splitlines():
        m = _HEADING.match(line.strip())
        if m:
            out.append(Section(m.group(2), len(m.group(1))))
        elif line.strip():
            out[-1].lines.append(line.strip())
    return [s for s in out if s.lines or s.level <= 2 or s.name == LEAD]


def _skipped(name: str) -> bool:
    return name.casefold() in SKIP


def kept(article: Article) -> list[Section]:
    """Sections minus reference-type ones (and their subsections)."""
    out, inside = [], None
    for s in article.sections:
        if inside is not None and s.level > inside:
            continue
        inside = s.level if _skipped(s.name) else None
        if inside is None:
            out.append(s)
    return out


def _k(n: int) -> str:
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def outline(article: Article) -> list[str]:
    """One line per top-level section with its size; subsections inline."""
    lines: list[str] = []
    secs = kept(article)
    i = 0
    while i < len(secs):
        top = secs[i]
        subs = []
        j = i + 1
        while j < len(secs) and secs[j].level > top.level:
            subs.append(secs[j])
            j += 1
        total = top.chars + sum(s.chars for s in subs)
        tail = ": " + ", ".join(f"{s.name} {_k(s.chars)}" for s in subs if s.chars) if subs else ""
        lines.append(f"  {top.name} {_k(total)}{tail}")
        i = j
    return lines


def find_sections(article: Article, wanted: list[str]) -> tuple[list[tuple[Section, list[Section]]], list[str]]:
    """The sections named in `wanted` (exact, then prefix, then substring
    match, case-insensitive), each with its subsections; plus names not found."""
    secs = kept(article)
    found, missing = [], []
    for w in wanted:
        wl = w.casefold()
        idx = next((i for i, s in enumerate(secs) if s.name.casefold() == wl), None)
        if idx is None:
            idx = next((i for i, s in enumerate(secs) if s.name.casefold().startswith(wl)), None)
        if idx is None:
            idx = next((i for i, s in enumerate(secs) if wl in s.name.casefold()), None)
        if idx is None:
            missing.append(w)
            continue
        top, subs = secs[idx], []
        for s in secs[idx + 1 :]:
            if s.level <= top.level:
                break
            subs.append(s)
        found.append((top, subs))
    return found, missing


# ── infobox ───────────────────────────────────────────────────────────────

_DROP_TEMPLATES = ("sfn", "efn", "ref", "refn", "cite", "harvnb", "harv", "rp", "citation", "note", "nbsp", "snd", "coord", "sup", "#tag", "tree list", "*", "increase", "decrease", "steady", "flagicon", "flagdeco", "notetag", "nts")
_DASHES = {"ndash": "–", "mdash": "—", "spaced ndash": " – ", "snd": " – ", "en dash": "–", "dash": "–", "-": "–"}
_LISTS = ("plainlist", "unbulleted list", "ubl", "ubil", "flatlist", "hlist", "bulleted list", "collapsible list", "plain list", "bulletedlist")


def _render(code, links: list[str] | None = None) -> str:  # noqa: ANN001 - mwparserfromhell Wikicode
    """Plain text of infobox wikitext: footnotes dropped, lists joined with
    '; ', flags and date templates reduced to their text. Titles of the links
    that survive are appended to `links`."""
    import mwparserfromhell as mw

    out: list[str] = []
    for node in code.nodes:
        if isinstance(node, mw.nodes.Template):
            name = str(node.name).strip().casefold()
            params = [p for p in node.params if not p.showkey]
            if name in _DASHES:
                out.append(_DASHES[name])
            elif name.startswith(_DROP_TEMPLATES):
                continue
            elif name in ("kia", "k.i.a.", "dow"):
                out.append(" †")
            elif name in ("pow", "p.o.w."):
                out.append(" (POW)")
            elif name in ("wia", "w.i.a."):
                out.append(" (WIA)")
            elif name in ("circa", "c.", "c"):
                out.append("c. " + (_render(params[0].value, links) if params else ""))
            elif "date" in name and params:
                out.append("-".join(p.value.strip_code().strip() for p in params[:3]))
            elif name in _LISTS:
                items = [_render(p.value, links) for p in node.params if not str(p.name).strip().startswith(("title", "class", "style", "framestyle", "titlestyle", "liststyle", "item_style"))]
                out.append("; " + "; ".join(i for i in items if i.strip()) + "; ")
            elif name.startswith("lang") and params:
                out.append(_render(params[-1].value, links))
            elif name in ("convert", "cvt") and len(params) >= 2:
                out.append(f"{params[0].value.strip_code().strip()} {params[1].value.strip_code().strip()}")
            elif params:
                out.append(_render(params[0].value, links))
        elif isinstance(node, mw.nodes.Tag):
            tag = str(node.tag).casefold()
            if tag in ("ref", "sup"):
                continue
            if tag == "br":
                out.append("; ")
            elif node.contents is not None:
                out.append(_render(node.contents, links))
        elif isinstance(node, mw.nodes.Wikilink):
            title = str(node.title).split("#")[0].strip()
            if title.casefold().startswith(("file:", "image:", "category:")):
                continue
            if links is not None and title and title not in links:
                links.append(title)
            out.append(node.text.strip_code() if node.text else title)
        elif isinstance(node, mw.nodes.Comment):
            continue
        elif isinstance(node, mw.nodes.Text):
            out.append(str(node))
        else:
            out.append(mw.parse(str(node)).strip_code())
    return "".join(out)


def _clean(text: str) -> str:
    text = re.sub(r"^\s*[*#]\s*", "; ", text, flags=re.M)
    text = re.sub(r"\s*\n\s*", "; ", text)
    text = re.sub(r"(;\s*)+", "; ", text)
    text = re.sub(r"'{2,}", "", text)
    return re.sub(r"\s+", " ", text).strip(" ;,")


def infobox(wikitext: str) -> tuple[dict[str, str], dict[str, list[str]]]:
    """({key: plain value}, {key: [linked titles]}) of the military-conflict infobox."""
    import mwparserfromhell as mw

    code = mw.parse(wikitext)
    box = next((t for t in code.filter_templates(recursive=False) if str(t.name).strip().casefold().startswith("infobox")), None)
    if box is None:
        return {}, {}
    values: dict[str, str] = {}
    links: dict[str, list[str]] = {}
    for p in box.params:
        key = str(p.name).strip().casefold()
        if key not in INFOBOX_KEYS:
            continue
        found: list[str] = []
        v = _clean(_render(p.value, found))
        if v:
            values[key] = v
        if key in LINKED_KEYS and found:
            links[key] = found
    return values, links


def title_qids(titles: list[str], lang: str = "en") -> dict[str, str]:
    """{title: Q-id} for linked article titles (follows redirects), 50 a call."""
    out: dict[str, str] = {}
    titles = list(dict.fromkeys(titles))
    for i in range(0, len(titles), 50):
        chunk = titles[i : i + 50]
        data = get_json(api(lang), {"action": "query", "prop": "pageprops", "ppprop": "wikibase_item", "redirects": 1, "titles": "|".join(chunk), "format": "json", "formatversion": 2})
        q = data.get("query", {})
        back: dict[str, str] = {}
        for m in q.get("normalized", []) + q.get("redirects", []):
            back[m["to"]] = back.get(m["from"], m["from"])
        for page in q.get("pages", []):
            qid = page.get("pageprops", {}).get("wikibase_item")
            if qid:
                out[back.get(page["title"], page["title"])] = qid
                out[page["title"]] = qid
    return out


# ── output ────────────────────────────────────────────────────────────────


def _annotate(value: str, titles: list[str], qids: dict[str, str]) -> str:
    """Append [Qid] after each linked name that appears in the value."""
    tags = [f"{t} [{qids[t]}]" for t in titles if t in qids]
    return value + ("  ⟶ " + "; ".join(tags) if tags else "")


def overview(article: Article) -> list[str]:
    lines = [f"{article.title} [{article.qid or '?'}]  {article.url()}"]
    wd = wd_entities([article.qid]).get(article.qid, {}) if article.qid else {}
    if wd:
        dates = " ".join(f"{k}={v}" for k, v in wd.get("dates", {}).items())
        coord = ",".join(str(c) for c in wd["coord"]) if wd.get("coord") else "none"
        types = ", ".join(wd_labels(wd.get("p31", [])[:3]).values())
        lines.append(f"wikidata: {types} · {dates or 'no date'} · P625 {coord} · {wd.get('sitelinks', 0)} sitelinks")
        if wd.get("p710"):
            labels = wd_labels(wd["p710"][:12])
            lines.append("P710 participants: " + "; ".join(f"{v} [{k}]" for k, v in labels.items()))
        if wd.get("casualties"):
            lines.append(f"P1120 casualties: {wd['casualties']}")
    values, links = infobox(article.wikitext)
    qids = title_qids([t for ts in links.values() for t in ts], article.lang) if links else {}
    for key in INFOBOX_KEYS:
        if key in values:
            v = values[key]
            if len(v) > 400:
                v = v[:400] + " …"
            lines.append(f"{key}: {_annotate(v, links.get(key, []), qids)}")
    if not values:
        lines.append("infobox: none found")
    lines.append(f"sections (chars; ask with --section NAME, 'lead' for the intro): total {_k(sum(s.chars for s in kept(article)))}")
    lines.extend(outline(article))
    return lines


def section_text(article: Article, wanted: list[str], max_chars: int) -> list[str]:
    found, missing = find_sections(article, wanted)
    lines: list[str] = []
    budget = max_chars
    for top, subs in found:
        body: list[str] = []
        for s in [top, *subs]:
            if s is not top:
                body.append(f"### {s.name}")
            body.extend(s.lines)
        text = "\n".join(body)
        head = f"## {top.name} ({_k(len(text))})"
        if budget <= len(head) + 50:
            lines.append(f"[cut: '{top.name}' not shown — over --max-chars; ask for it alone]")
            continue
        room = budget - len(head) - 1
        if len(text) > room:
            cut = text.rfind(". ", 0, room)
            cut = cut + 1 if cut > room * 0.6 else room
            lines.append(head)
            lines.append(text[:cut])
            lines.append(f"[cut: {len(text) - cut:,} more chars in '{top.name}'; name a subsection or raise --max-chars]")
            budget = 0
        else:
            lines.append(head)
            lines.append(text)
            budget -= len(head) + len(text) + 2
    if missing:
        lines.append("not found: " + ", ".join(missing) + " (see the outline)")
    return lines


def qid_lines(qids: list[str]) -> list[str]:
    rows = wd_entities(qids)
    classes = wd_labels([c for r in rows.values() for c in r.get("p31", [])[:2]])
    out = []
    for q in qids:
        r = rows.get(q)
        if not r or r.get("missing"):
            out.append(f"{q}  MISSING — not a Wikidata item")
            continue
        d = r.get("dates", {})
        span = d.get("P569") or d.get("P571") or d.get("P580") or d.get("P585") or ""
        end = d.get("P570") or d.get("P576") or d.get("P582") or ""
        when = f" ({span}–{end})" if span or end else ""
        kinds = ", ".join(classes.get(c, c) for c in r.get("p31", [])[:2])
        out.append(f"{q}  {r.get('label') or '?'}{when} · {kinds or '?'} · {r.get('description') or ''}"[:200])
    return out


def run(ref: str, sections: list[str], show_outline: bool, qids: list[str], lang: str, max_chars: int, refresh: bool) -> str:
    lines: list[str] = []
    if ref:
        article = fetch(ref, lang, refresh)
        if show_outline or not sections:
            lines.extend(overview(article))
        if sections:
            lines.extend(section_text(article, sections, max_chars - sum(len(x) + 1 for x in lines)))
    if qids:
        lines.extend(qid_lines(qids))
    text = "\n".join(lines)
    return text if len(text) <= max_chars else text[: max_chars - 40] + f"\n[cut at --max-chars {max_chars}]"
