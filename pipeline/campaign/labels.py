"""Bare regnal person labels ('Philip II', 'Charles V', 'al-Mustansir', 'Taizong').

The pipeline matches a candidate against existing DB rows by exact name, so a
bare regnal name links to whichever namesake the atlas already holds: the
Macedonian 'Philip II' ends up ruling Spain in 1556, Charles V of France the
Holy Roman Empire in 1519. `handoff check` therefore warns `ambiguous-label`
for such person labels and `handoff add` prints a hint; neither blocks.

Detection is offline and cheap (no network, ever):

1. Shape. A person label is "bare" when it is only a name plus a regnal numeral
   (roman, or 'the Second'), optionally followed by an epithet ('Ptolemy II
   Philadelphus'), with no qualifier: no ' of X', comma, parenthesis or leading
   title ('Pope', 'King', ...). Also bare: a lone Arabic regnal laqab
   ('al-Mustansir') and a lone Chinese posthumous/temple name ('Emperor Wu',
   'Taizong').
2. Wikipedia cache. When `python -m pipeline.campaign wiki "<label>"` has
   already fetched the bare label (output/campaign/cache/wiki/), that page
   can settle it: a disambiguation page ('... may refer to:') or a redirect to
   a qualified title ('Alfonso X' -> 'Alfonso X of Castile') warns, naming the
   title; a page titled with the label itself ('Thutmose III') never warns. Any
   other redirect ('Leo I' -> 'Pope Leo I') leaves it to step 3. The cache is
   only read, never filled: a live lookup per label would make every `check`
   slow and network-dependent.
3. Heuristic, when the cache has no page. Only the strict 'Name Numeral' form
   warns (an epithet or dynastic surname after the numeral -- 'Antiochus III
   the Great', 'Michael VIII Palaiologos' -- already picks one person in
   practice), and only for given names that several realms numbered in
   parallel, up to the numeral where the overlap ends (SHARED_REGNAL_NAMES:
   Louis I-X collide across France/Bavaria/Hungary/Italy, Louis XIV does not).
   Famous primary-topic titles ('Henry VIII', 'George III') are exempt.
   Laqabs and Chinese names use their own lists. The lists are deliberately
   conservative (a noisy warning gets ignored); extend them when a review finds
   a new namesake collision.
"""
from __future__ import annotations

import json
import re
import unicodedata

CODE = "ambiguous-label"

# Given name -> highest regnal numeral still shared by two or more realms (so
# 'Name I'..'Name <n>' are ambiguous). Keys are ASCII-folded, lowercase.
SHARED_REGNAL_NAMES: dict[str, int] = {
    # Latin West: one dynastic name stock numbered separately in each realm.
    "philip": 6, "louis": 10, "charles": 10, "henry": 7, "frederick": 9, "william": 5,
    "john": 8, "james": 7, "robert": 3, "alfonso": 11, "afonso": 6, "ferdinand": 5,
    "peter": 5, "pedro": 5, "sancho": 7, "ramiro": 3, "garcia": 6, "otto": 4,
    "conrad": 4, "rudolf": 3, "albert": 2, "leopold": 3, "sigismund": 3, "boleslaw": 3,
    "boleslaus": 3, "wladyslaw": 5, "ladislaus": 5, "stephen": 5, "eric": 8, "erik": 8,
    "magnus": 4, "harald": 3, "canute": 4, "cnut": 4, "knut": 4, "francis": 2,
    "joseph": 2, "isabella": 2, "mary": 2, "joanna": 2, "george": 12, "david": 9,
    "baldwin": 9, "raymond": 7,
    # Greek East, Black Sea and Iranian lines that reuse the same names.
    "alexander": 5, "constantine": 4, "michael": 3, "leo": 6, "manuel": 3,
    "alexios": 5, "andronikos": 4, "theodore": 2, "demetrius": 3, "antiochus": 4,
    "mithridates": 6, "tiridates": 3, "orodes": 3, "vologases": 6, "artabanus": 4,
    "arsaces": 2, "ariobarzanes": 3,
    # Islamic and South/Southeast Asian lines.
    "muhammad": 12, "suleiman": 2, "mahmud": 2, "indravarman": 3,
}

# Bare labels that are themselves the English Wikipedia title of one famous
# ruler (a primary topic), so the shared-name rule must not flag them.
PRIMARY_TITLES = {
    "henry viii", "elizabeth i", "elizabeth ii", "edward vii", "edward viii",
    "george iii", "george iv", "george v", "george vi", "louis xiv", "louis xv",
    "louis xvi", "louis xviii", "napoleon iii", "william iv", "isabella ii",
}

# Arabic regnal titles (laqabs) borne by rulers of two or more lines -- the
# Baghdad and Cairo Abbasids, the Fatimids, the Taifa kings, Almohads, Hafsids,
# Ayyubids, Mamluks -- so a lone 'al-<laqab>' names no one in particular.
SHARED_LAQABS = {
    "mansur", "mahdi", "hadi", "rashid", "mamun", "mutasim", "wathiq", "mutawakkil",
    "muntasir", "mustain", "mutamid", "mutadid", "muqtadir", "qahir", "mustakfi",
    "qadir", "qaim", "mustazhir", "mustanjid", "nasir", "zahir", "mustansir",
    "muizz", "aziz", "hakim", "adil", "salih", "ashraf", "muzaffar",
}

# One-syllable Chinese posthumous names: 'Emperor Wu' is Han, Jin, Liang,
# Northern Zhou, ... ; English Wikipedia titles them 'Emperor Wu of Han'.
CHINESE_POSTHUMOUS = {
    "wu", "wen", "jing", "ling", "xian", "ming", "gao", "hui", "zhao", "xuan", "yuan",
    "cheng", "ai", "ping", "zhang", "he", "an", "shun", "huan", "shao", "yang", "gong",
    "mu", "xiao", "min", "huai", "zhuang", "xiang", "kang", "dai", "de", "su", "jian",
}
# Temple names ('Taizong', 'Gaozu') recur in every dynasty from Han to Qing.
_TEMPLE_NAME = re.compile(
    r"^(?:Tai|Gao|Shi|Sheng|Ren|Ying|Xian|Xuan|Su|Dai|De|Shun|Mu|Jing|Wen|Wu|Yi|Xi|Zhao|Ai|Hui|"
    r"Qin|Xiao|Guang|Ning|Li|Du|Rui|Zhong|Cheng|Jia|Dao|Xing|Min|Zhen|Yuan|Ding|Kang|Yong|Qian|"
    r"Gong|Ling|Huan|Ming|Zhuang|Lie|Shen|Yin|Chong|Shao|Tong|Zhe)(?:zong|zu)$")

TITLE_WORDS = {
    "pope", "antipope", "patriarch", "saint", "st", "king", "queen", "emperor", "empress",
    "sultan", "shah", "caliph", "khan", "khagan", "tsar", "czar", "duke", "prince",
    "princess", "count", "earl", "pharaoh", "emir", "amir", "imam", "negus", "raja",
    "maharaja", "lord", "lady", "chief", "bishop", "archbishop", "doge", "kaiser",
}
_ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
    "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12,
    "thirteenth": 13, "fourteenth": 14, "fifteenth": 15, "sixteenth": 16,
}
_ROMAN = re.compile(r"^(X{0,3})(IX|IV|V?I{0,3})$")
_ROMAN_VALUE = {"I": 1, "V": 5, "X": 10}
_QUALIFIER = re.compile(r"\bof\b|[,(/]", re.IGNORECASE)
_LAQAB = re.compile(r"^(?:a[lnrsztd]|e[ln]|ash)[-‐‑ ](\S+)$", re.IGNORECASE)
_NAME_TOKEN = re.compile(r"^[A-ZÀ-ɏ][\w'’ʿʾ-]*$")
_APOSTROPHES = re.compile("['`´‘’ʻʼʾʿ]")
_TRANSLIT = str.maketrans({"ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "ø": "o", "Ø": "O", "ß": "ss"})


def _fold(text: str) -> str:
    """ASCII, lowercase, apostrophes dropped ('Bolesław' -> 'boleslaw', "Mu'tadid" -> 'mutadid')."""
    plain = _APOSTROPHES.sub("", (text or "").translate(_TRANSLIT))
    return unicodedata.normalize("NFKD", plain).encode("ascii", "ignore").decode().lower().strip()


def _roman(token: str) -> int | None:
    if not token or not _ROMAN.match(token):
        return None
    total = 0
    for i, ch in enumerate(token):
        value = _ROMAN_VALUE[ch]
        nxt = _ROMAN_VALUE[token[i + 1]] if i + 1 < len(token) else 0
        total += -value if value < nxt else value
    return total


def regnal_parts(label: str) -> tuple[str, int, bool] | None:
    """(folded name, numeral, has_epithet) when ``label`` is 'Name Numeral [epithet]'
    with no qualifier or leading title; else None. 'Philip II' -> ('philip', 2, False)."""
    label = (label or "").strip()
    if not label or _QUALIFIER.search(label):
        return None
    tokens = label.split()
    if len(tokens) < 2 or _fold(tokens[0]) in TITLE_WORDS:
        return None
    for k in (1, 2):
        if k >= len(tokens):
            break
        numeral = _roman(tokens[k])
        consumed = 1
        if numeral is None and tokens[k].lower() == "the" and k + 1 < len(tokens):
            numeral = _ORDINALS.get(tokens[k + 1].lower())
            consumed = 2
        if numeral is None:
            continue
        name = tokens[:k]
        epithet = tokens[k + consumed:]
        if not all(_NAME_TOKEN.match(t) for t in name) or len(epithet) > 3:
            return None
        return " ".join(_fold(t) for t in name), numeral, bool(epithet)
    return None


def _cached_page(label: str) -> tuple[str | None, str] | None:
    """(resolved title, extract) of an already-cached wiki page for ``label``;
    None when it was never fetched or the cache is unreadable. Never hits the network."""
    try:
        from pipeline.campaign import wiki

        path = wiki._cache_file("page", label)
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        pages = (data.get("query") or {}).get("pages") or []
        page = pages[0] if pages else {}
        if page.get("missing") or page.get("invalid") or not page.get("extract"):
            return None  # same test as wiki.fetch_page: no such page
        return page.get("title"), page["extract"]
    except Exception:
        return None


def _hint(label: str, title: str | None = None) -> str:
    target = repr(title) if title else "e.g. 'Philip II of Spain', not 'Philip II'"
    lookup = "" if title else f"; find it with `wiki-search \"{label} <polity>\"`"
    return (f"use the English Wikipedia title ({target}): `handoff rename RUN {label!r} '<title>'`"
            f"{lookup}. A bare regnal label links to whichever namesake the DB already holds")


def ambiguous_label(label: str, entity_type: str | None) -> str | None:
    """Why a person ``label`` is a bare regnal name that several rulers share,
    phrased as the fix; None when it is qualified or unambiguous. See module doc."""
    if entity_type != "person":
        return None
    label = (label or "").strip()
    parts = regnal_parts(label)
    laqab = _LAQAB.match(label)
    tokens = label.split()
    chinese = (len(tokens) == 1 and _TEMPLE_NAME.match(label)) or (
        len(tokens) == 2 and tokens[0] == "Emperor"
        and (_fold(tokens[1]) in CHINESE_POSTHUMOUS or _TEMPLE_NAME.match(tokens[1])))
    if parts is None and not laqab and not chinese:
        return None

    # A cached page can only confirm a warning (and name the title) or show the
    # label is itself an article title; a redirect elsewhere ('Leo I' -> 'Pope
    # Leo I') says nothing about which Leo I the run means, so the lists decide.
    title, extract = _cached_page(label) or (None, "")
    if title:
        if "may refer to" in extract[:400].lower():
            return f"bare regnal name: English Wikipedia {label!r} is a disambiguation page; " + _hint(label)
        if title.casefold() == label.casefold():
            return None
        rest = title[len(label):] if title.casefold().startswith(label.casefold()) else ""
        if rest.startswith((" of ", ", ")):
            return f"bare regnal name: English Wikipedia titles this person {title!r}; " + _hint(label, title)

    if laqab:
        shared = _fold(laqab.group(1)).replace("-", "") in SHARED_LAQABS
    elif chinese:
        shared = True
    else:
        name, numeral, epithet = parts
        shared = (not epithet and _fold(label) not in PRIMARY_TITLES
                  and numeral <= SHARED_REGNAL_NAMES.get(name, 0))
    if not shared:
        return None
    return "bare regnal name shared by several rulers; " + _hint(label)
