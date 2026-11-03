"""QID-suspect review (2026-11-01 cleanup): rows the identity audit flagged
``identity_audit:qid_suspect`` / ``identity_audit:qid_suspect:duplicate``.

The audit judged each of these QIDs doubtful (W6/W8: a namesake from another
era, judged on dates and text alone) and only flagged them. This module gives
every row a hand-checked decision.

Slice: rows carrying a ``identity_audit:qid_suspect*`` flag, minus the S1
rows of ``qid-flags.csv`` (another agent's), the merge-review survivors and
losers and the user-decision rows (``RULES.md``).

Stages (dry by default):

  scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit.suspect_review gather   # evidence (read-only)
  scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit.suspect_review plan     # planned.csv
  scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit.suspect_review apply    # backup + guarded writes

``gather`` searches Wikidata for the right item of every row with the audit's
own tools: C3 (``qid.find_correct_qid``) and the stricter reconcile scoring
(``reconcile.score`` / ``decide``: exact label/alias/enwiki name, class, own
dates, place/war/link), over ``wbsearchentities`` hits for the row's name and
aliases plus the enwiki articles titled exactly like the name, an alias, or
the name with the row's year as a disambiguator ("Sack of Rome (1527)").

Decisions (``DECISIONS``, keyed by entity_id prefix, checked by hand):

* ``confirm`` - the QID is right (the dates differ for a known reason: a reign
                against a lifespan, a chronology, a Wikidata slip). The
                suspect flag goes; ``verification_status`` returns to what the
                audit changed it from (``identity-20261031/applied.csv``)
                unless another flag still justifies ``needs_review``.
* ``repoint`` - the right QID is found, unique and certain, and no other row
                holds it (re-checked at write time). The suspect flag goes, the
                status is restored as for confirm.
* ``clear``   - the QID is another thing; no certain replacement. The audit's
                way: QID to NULL, old id to ``attributes._rejected_wikidata_id``,
                flag ``identity_audit:qid_cleared`` (replacing the suspect
                flag), status stays ``needs_review``.
* ``dup``     - the right QID is on another row: the pair goes to
                duplicate-candidates.csv and the wrong QID is cleared as for
                clear, with flag ``identity_audit:qid_cleared:duplicate``.
* ``leave``   - nothing is written; the row is listed.

On clear, dup and repoint the row's ``media_refs`` are dropped when they came
from the old QID (Wikidata P18 or its enwiki lead image) and no admin curated
them (``_media_curated_at``): they show the namesake. The nightly
``entity:fetch-images`` refetches them for a re-pointed QID.

Every write is guarded on ``wikidata_id``, ``attributes`` (md5 of the jsonb
text) and ``verification_status`` as read at plan time; a row another agent
changed is skipped. One transaction; applied.csv and rollback.sql come from
what the transaction changed.
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import gzip
import json
import subprocess
import time
from pathlib import Path
from typing import Any

from pipeline.audit import classes as C
from pipeline.audit.common import CACHE_DIR, COMPOSE, REPO, connect, load_relationships, load_rows, write_csv
from pipeline.audit.dates import EVENT_TYPES
from pipeline.audit.qid import check_row, find_correct_qid, prefetch_candidates
from pipeline.audit.wd import WikidataClient

OUT = REPO / "output" / "audit" / "qid-suspect-20261101"
QID_FLAGS = REPO / "output" / "audit" / "identity-20261031" / "qid-flags.csv"
IDENTITY_APPLIED = REPO / "output" / "audit" / "identity-20261031" / "applied.csv"
MERGE_VERDICTS = REPO / "output" / "audit" / "merge-review-20261101" / "verdicts.csv"
USER_DECISION_PREFIXES = ("a05afb75", "6255478f", "17d96812", "7baeedc3")
SUSPECT = "identity_audit:qid_suspect"     # prefix: qid_suspect, qid_suspect:duplicate
SEARCH_LIMIT = 20


class PoliteClient(WikidataClient):
    """The audit client plus maxlag=5 (many agents share the quota), backing off on maxlag."""

    def _get(self, url, params, timeout=60):
        if "wikidata.org/w/api.php" in url:
            params = {**params, "maxlag": "5"}
        for attempt in range(12):
            resp = super()._get(url, params, timeout)
            if "api.php" in url:
                try:
                    err = (resp.json() or {}).get("error") or {}
                except ValueError:
                    err = {}
                if err.get("code") == "maxlag":
                    time.sleep(min(5 * 2 ** attempt, 120))
                    continue
            return resp
        raise RuntimeError("Wikidata kept reporting maxlag")


def client(offline: bool = False) -> PoliteClient:
    return PoliteClient(CACHE_DIR, max_rps=1.0, workers=1, offline=offline)


# ── selection ───────────────────────────────────────────────────────────────
def excluded_ids() -> set[str]:
    ids: set[str] = set()
    with MERGE_VERDICTS.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            ids.update(x for x in (r.get("survivor_id"), r.get("loser_id")) if x)
    return ids


def qid_flags() -> dict[str, dict[str, str]]:
    with QID_FLAGS.open(encoding="utf-8") as fh:
        return {r["entity_id"]: r for r in csv.DictReader(fh)}


def audit_status_before() -> dict[str, str]:
    """entity_id -> the verification_status the identity audit changed (first change wins)."""
    out: dict[str, str] = {}
    with IDENTITY_APPLIED.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["column"] == "verification_status" and r["status"] == "applied" and r["id"] not in out:
                out[r["id"]] = r["old"]
    return out


def select(rows) -> tuple[list[Any], list[tuple[str, str, str]]]:
    """[row in slice], [(entity_id, name, skip reason)]."""
    excl = excluded_ids()
    flags_csv = qid_flags()
    picked, skipped = [], []
    for r in rows.values():
        flags = (r.attributes or {}).get("validation_flags") or []
        if not any(str(f).startswith(SUSPECT) for f in flags):
            continue
        f = flags_csv.get(r.id, {})
        if r.id in excl:
            skipped.append((r.id, r.name, "merge-review exclusion"))
        elif r.id.startswith(USER_DECISION_PREFIXES):
            skipped.append((r.id, r.name, "user-decision exclusion"))
        elif "S1" in f.get("rule", "") + f.get("issues", ""):
            skipped.append((r.id, r.name, "S1 row (other agent)"))
        elif not r.qid:
            skipped.append((r.id, r.name, "no QID any more"))
        else:
            picked.append(r)
    picked.sort(key=lambda r: (r.type, r.name))
    return picked, skipped


def title_variants(r) -> list[str]:
    """enwiki titles to try: the name, the aliases, and for an event the name
    with its year ('Sack of Rome (1527)', 'Siege of Rhegium (270 BC)')."""
    from pipeline.audit.reconcile import split_qualifier

    base = split_qualifier(r.name)[0]
    out = [r.name, base, *r.aliases[:3]]
    if r.type in EVENT_TYPES and r.start is not None:
        y = r.start
        yr = f"{-y} BC" if y < 0 else str(y)
        out += [f"{base} ({yr})"]
        if r.end is not None and r.end != r.start:
            e = r.end
            if y < 0 and e < 0:
                out.append(f"{base} ({-y}–{-e} BC)")
            elif y > 0:
                out.append(f"{base} ({y}–{e})")
    return list(dict.fromkeys(t for t in out if t))


# ── gather (read-only) ──────────────────────────────────────────────────────
def gather(out: Path, offline: bool) -> None:
    from pipeline.audit.reconcile import (PLACE_PROPS, WAR_PROPS, build_contexts, c2_passes, decide,
                                          reverse_links, score, split_qualifier)
    from pipeline.audit.qid import wd_names

    conn = connect()
    rows = load_rows(conn)
    rels = load_relationships(conn)
    picked, skipped = select(rows)
    cl = client(offline)
    closure_fn = lambda cs: cl.class_roots(cs, C.ALL_ROOTS)  # noqa: E731
    print(f"gather: {len(picked)} rows, {len(skipped)} skipped", flush=True)

    cl.get_entities([r.qid for r in picked], need_links=True)
    # C3 as the audit ran it (search limit 10 on the name and two aliases)
    if not offline:
        prefetch_candidates([(r, {r.qid}) for r in picked], cl, closure_fn)
    # the wider candidate set: limit-20 searches on name + aliases, enwiki titles
    names = {n for r in picked for n in [split_qualifier(r.name)[0], *r.aliases[:3]] if n}
    titles = {t for r in picked for t in title_variants(r)}
    if not offline:
        cl.search_many(names, limit=SEARCH_LIMIT)
        cl.by_titles(titles, progress=True)
    cands: dict[str, list[str]] = {}
    for r in picked:
        qs = [h["qid"] for n in [split_qualifier(r.name)[0], *r.aliases[:3]] if n
              for h in cl.searches.get(f"{n}␟{SEARCH_LIMIT}", [])]
        qs += [cl.titles[t] for t in title_variants(r) if cl.titles.get(t)]
        reject = {r.qid, (r.attributes or {}).get("_rejected_wikidata_id")}
        cands[r.id] = [q for q in dict.fromkeys(qs) if q and q not in reject]
    all_q = {q for qs in cands.values() for q in qs}
    print(f"gather: fetching {len(all_q)} candidate items", flush=True)
    cl.get_entities(all_q, progress=True, need_links=True)
    cl.get_entities([rec["redirect_to"] for q in all_q
                     if (rec := cl.entities.get(q, {})).get("status") == "redirect"], need_links=True)
    recs = {q: rec for q in all_q if (rec := cl.resolved(q)[1]) and rec.get("status") == "ok"}
    closure = closure_fn([c for rec in [*recs.values(), *(cl.resolved(r.qid)[1] or {} for r in picked)]
                          for c in rec.get("p31", [])])
    ctxs = build_contexts(picked, rows, rels)
    linked = {v for rec in recs.values() for p in PLACE_PROPS + WAR_PROPS for v in (rec.get("links") or {}).get(p, [])}
    related = {q for r in picked for q in ctxs[r.id].related_qids}
    cl.get_entities(linked)
    cl.get_entities(related, need_links=True)

    def names_of(q: str) -> list[str]:
        _, rec = cl.resolved(q)
        return wd_names(rec) if rec and rec.get("status") == "ok" else []

    by_qid: dict[str, list[str]] = {}
    for x in rows.values():
        if x.qid:
            by_qid.setdefault(x.qid, []).append(x.id)
    by_row: dict[str, list[str]] = {}
    for rel in rels:
        for a, b, arrow in ((rel["source"], rel["target"], "->"), (rel["target"], rel["source"], "<-")):
            o = rows.get(b)
            if o:
                yrs = "-".join(str(y) for y in (rel["start"], rel["end"]) if y is not None)
                by_row.setdefault(a, []).append(f"{arrow}{rel['type']} {o.name} [{o.type}{' ' + o.qid if o.qid else ''}]"
                                                f"{' ' + yrs if yrs else ''}")
    flags_csv = qid_flags()
    evidence = []
    for r in picked:
        bare = dataclasses.replace(r, qid=None)
        ctx = ctxs[r.id]
        ctx.reverse = reverse_links(ctx.related_qids, cl)
        scored, seen = [], set()
        for q in cands[r.id]:
            fq, rec = cl.resolved(q)
            if q not in recs or fq in seen or fq == r.qid:
                continue
            seen.add(fq)
            scored.append(score(bare, fq, rec, ctx, closure, names_of))
        res = decide(bare, scored)
        win = res.get("win") or {}
        if win:
            c2 = check_row(dataclasses.replace(r, qid=win["qid"]), cl, closure)
            res["c2"] = c2["verdict"] + (f" {c2['rule']}" if c2["rule"] else "")
            if not c2_passes(c2, win):
                res["outcome"], res["why"] = "c2_rejected", res["c2"]
        c3 = find_correct_qid(r, cl, closure_fn, exclude={r.qid}) if not offline else {}
        cur_fq, cur = cl.resolved(r.qid)
        cur = cur or {}
        cur_score = score(bare, cur_fq, cur, ctx, closure, names_of) if cur.get("status") == "ok" else {}
        f = flags_csv.get(r.id, {})
        winner = win.get("qid", "")
        evidence.append({
            "entity_id": r.id, "name": r.name, "type": r.type, "qid": r.qid, "status": r.status,
            "flags": (r.attributes or {}).get("validation_flags") or [], "start": r.start, "end": r.end,
            "aliases": r.aliases[:5], "summary": r.summary, "description": r.description[:500],
            "rule": f.get("rule", ""), "audit_c3": f.get("resolution", ""),
            "wd_label": cur.get("label", ""), "wd_desc": cur.get("description", ""), "wd_dates": cur.get("dates"),
            "wd_enwiki": cur.get("enwiki"), "wd_aliases": (cur.get("aliases") or [])[:6],
            "cur_score": {k: cur_score.get(k) for k in ("name", "class", "dates", "date_detail", "place", "war",
                                                        "link", "need")} if cur_score else {},
            "rec_outcome": res["outcome"], "rec_why": res.get("why", ""), "rec_qid": winner,
            "rec_label": win.get("label", ""), "rec_desc": win.get("description", ""),
            "rec_enwiki": win.get("enwiki", ""), "rec_dates": win.get("date_detail", ""),
            "rec_signals": {k: win.get(k) for k in ("name", "place", "war", "link")} if win else {},
            "rec_c2": res.get("c2", ""), "rec_held_by": [h for h in by_qid.get(winner, []) if h != r.id],
            "rec_cands": res.get("candidates", []),
            "c3": c3.get("outcome", ""), "c3_qid": c3.get("qid", ""), "c3_label": c3.get("label", ""),
            "c3_held_by": [h for h in by_qid.get(c3.get("qid", ""), []) if h != r.id] if c3.get("qid") else [],
            "c3_cands": c3.get("candidates", []),
            "media": [m.get("source") for m in (r.attributes or {}).get("media_refs") or []],
            "curated": bool((r.attributes or {}).get("_media_curated_at")),
            "rels": by_row.get(r.id, [])[:20], "n_rels": len(by_row.get(r.id, [])), "chron": r.chron,
            "point": r.point, "stories": r.stories,
        })
    out.mkdir(parents=True, exist_ok=True)
    (out / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=1, default=str))
    (out / "skipped.json").write_text(json.dumps(skipped, ensure_ascii=False, indent=1))
    print(f"gather: {len(picked)} rows; reconcile outcomes "
          f"{dict(__import__('collections').Counter(e['rec_outcome'] for e in evidence))}; "
          f"requests made {cl.requests_made}")


# ── decisions (hand-checked) ────────────────────────────────────────────────
# entity_id prefix -> (decision, new QID for repoint/dup, reason)
DECISIONS: dict[str, tuple[str, str, str]] = {
    # confirm: the QID is right, the dates differ for a known reason
    "9a6bd0c6": ("confirm", "", "Q201615 is the Piast dynasty; its end 1675 is the last Silesian Piast, the row's 1370 the end of the royal line"),
    "03d29690": ("confirm", "", "Q786657 is the 1811 battle (description '1811 battle', enwiki title exact); its P585 2000 is a Wikidata slip"),
    "199cb6ca": ("confirm", "", "Q636389 is the archbishopric (enwiki 'Archbishopric of Magdeburg', founded 968); its inception 1180 is the prince-archbishopric's"),
    "3125a2fd": ("confirm", "", "Q387123 is the Mahabharata war; the row's 1198 BCE is a scholarly dating, Wikidata's 3102 BCE the traditional one"),
    "eb1a5e75": ("confirm", "", "same philosopher; 700-750 and 788-820 are competing datings"),
    "7f74cbd1": ("confirm", "", "first Funj ruler (r. 1504-1533/4, enwiki); the row's end 1504 is the founding, inside his life"),
    "52a10f66": ("confirm", "", "the Indo-Greek king; Wikidata's birth is century-precision"),
    "0a7bcd75": ("confirm", "", "the Kushite king; Wikidata's birth is century-precision"),
    "8d864edf": ("confirm", "", "the Ptolemaic queen; the row's span is her reign, Wikidata gives birth c. 120 BCE"),
    "9aa80118": ("confirm", "", "the Gupta emperor (r. c. 476-495 per enwiki); Wikidata's death 480 differs"),
    "a685d824": ("confirm", "", "the king of Sidon (r. c. 539-525 BCE per enwiki); Wikidata's dates are decade/century precision"),
    "39924e74": ("confirm", "", "Patriarch Euphemius, deposed 496, died 515: the row's end is the deposition"),
    "6b3150b7": ("confirm", "", "Han Um, Wiman Joseon chancellor who surrendered in 108 BCE and died 19 years later (enwiki); the row's end is the surrender"),
    "5621d860": ("confirm", "", "the First Dynasty king; Early Dynastic chronologies differ"),
    "feab4351": ("confirm", "", "the jiedushi; the row's 917-923 is his rule, Wikidata's death 940 is decade-precision"),
    "6da34568": ("confirm", "", "the unifier of Egypt; Early Dynastic chronologies differ"),
    "b5a1b575": ("confirm", "", "the Kushite king; Meroitic chronologies differ"),
    "e8e86e02": ("confirm", "", "the Second Dynasty king; Early Dynastic chronologies differ"),
    "31fc0f1f": ("confirm", "", "the Second Dynasty king; Early Dynastic chronologies differ"),
    "a6807a17": ("confirm", "", "the only Assyrian king Puzur-Sin; Old Assyrian chronologies differ"),
    "eb8173b1": ("confirm", "", "the Fifth Dynasty king; Old Kingdom chronologies differ"),
    "e4bc2309": ("confirm", "", "Sunan Giri (Raden Paku), born 1442; the row's 1487 is the start of his rule at Gresik"),
    "898c3524": ("confirm", "", "the Shang king; Shang chronologies differ"),
    "0f500e1c": ("confirm", "", "Q141126502 is Abd al-Hamid ibn Abd al-Aziz al-Umari, the rebel in the Beja lands defeated by Ibn Tulun's army (ar description), d. 873; the row's 'by 884' holds"),
    # confirm_dates: the QID is right, the row's own dates are wrong (kept needs_review, flagged for a date fix)
    "54032c73": ("confirm_dates", "", "Khan Omurtag (r. 814-831, enwiki); the row's span 800-814 ends before the 815 peace its own text names"),
    "ce17d37f": ("confirm_dates", "", "Raja Ganesha, king of Bengal 1415-1418 (Wikidata, enwiki); the row's end 1432 is after his death"),
    "4429ee39": ("confirm_dates", "", "Tiglath-Pileser I reigned 1114-1076 BCE; the row's end 1007 BCE and its text's 'around 1020 BCE' are after his death"),
    "f83d9380": ("confirm_dates", "", "Ja'far al-Mushafi, hajib of Hisham II, died in Almanzor's prison 982/983; the row's end 996 is after his death"),

    # repoint: reconcile scoring accepted a unique candidate (checked by hand)
    "4a2eb802": ("repoint", "Q183725", "reconcile accepted: International Workingmen's Association, enwiki 'First International', 1864-1876"),
    "42e26afc": ("repoint", "Q2511385", "reconcile accepted: first autonomous government of Argentina, enwiki 'Primera Junta', 1810 (its English label is vandalised on Wikidata)"),
    "3e5e7dc1": ("repoint", "Q151290", "reconcile accepted: 1941 World War II campaign, enwiki 'Battle of Moscow', part of WWII"),
    "b01966d1": ("repoint", "Q132488359", "reconcile accepted: '1059 battle' at Ray (P276)"),
    "b55221f4": ("repoint", "Q3269760", "reconcile accepted: Khwarazm vs Mongols on the Indus, enwiki 'Battle of the Indus', 1221"),
    "cbbdd204": ("repoint", "Q14689", "reconcile accepted: 1242 battle, enwiki 'Battle on the Ice' (the names-followup agent set Q14689 at 22:53; this drops the suspect flag and the Karuse images)"),
    "55c7ba1c": ("repoint", "Q465627", "reconcile accepted: enwiki 'Sack of Rome (1527)'"),
    "f5b68116": ("repoint", "Q97175293", "reconcile accepted: 'Siege of Baku' dated 1723, located at Baku"),
    "2deab271": ("repoint", "Q20107791", "reconcile accepted: '212-211 BCE siege' of Capua, part of the Second Punic War"),
    "4b02dbd4": ("repoint", "Q42760463", "reconcile accepted: 'siege in 1204' of Rouen"),
    "ebd99a3e": ("repoint", "Q686474", "reconcile accepted: Whitsuntide events in Prague, 12-17 June 1848, enwiki 'Prague uprising (1848)'"),
    "32b0df5f": ("repoint", "Q17035527", "reconcile accepted: enwiki 'Treaty of Amritsar (1809)', EIC and Ranjit Singh"),
    "2d7b912d": ("repoint", "Q2629695", "reconcile accepted: 1779 treaty by which Spain joined the American Revolutionary War, enwiki 'Treaty of Aranjuez (1779)'"),
    "e61517ad": ("repoint", "Q11011", "reconcile accepted: 1504 treaty that ended the War of Naples"),
    "5f782bbe": ("repoint", "Q473661", "reconcile accepted: Chile-Bolivia treaty, enwiki 'Treaty of Peace and Friendship (1904)' (its label is vandalised on Wikidata)"),
    "b858c7c8": ("repoint", "Q11220", "reconcile accepted: United States Navy, inception 1775"),
    "63780ccb": ("repoint", "Q880886", "reconcile accepted: Khmer ruler Indravarman II (d. 1243), son of Jayavarman VII"),
    "7a04b0d4": ("repoint", "Q561219", "reconcile accepted: Qara Qoyunlu sultan Jahan Shah (1397-1467)"),
    "91d6244f": ("repoint", "Q511683", "reconcile accepted: Narathu, king of Pagan (r. 1167-1170)"),
    "1d4716bf": ("repoint", "Q103333", "reconcile accepted: Odoacer, king of Italy 476-493 (433-493)"),
    "1a849c93": ("repoint", "Q124622486", "reconcile accepted: Ghurid ruler Qutb al-Din Muhammad, d. 1148/9"),
    "b25ee6fb": ("repoint", "Q2422946", "reconcile accepted: Thoros I, Prince of Armenia (d. 1129), enwiki 'Thoros I'"),
    # repoint: reconcile's candidate failed only C2's name axis (a vandalised or variant label), checked by hand
    "e745f175": ("repoint", "Q18353917", "21 April 43 BCE battle, enwiki 'Battle of Mutina' (label misspelt 'Matina' on Wikidata)"),
    "5bce20fd": ("repoint", "Q11306135", "1596 Spanish shipwreck in Japan, enwiki 'San Felipe incident (1596)'"),
    "c958d997": ("repoint", "Q5023851", "enwiki 'Treaty of Madrid (1630)', Spain-England peace"),
    "f7f27982": ("repoint", "Q792340", "enwiki 'German invasion of Belgium (1914)'"),
    "034efb61": ("repoint", "Q3826903", "Hadim Suleiman Pasha, Ottoman grand vizier (1467-1547), enwiki 'Hadim Suleiman Pasha'; led the 1538 Diu expedition"),
    # repoint: one candidate fits the row's own dates and text; the reconcile rivals are undated namesakes or other people
    "7bee4d52": ("repoint", "Q3536825", "'1718 alliance between Austria, England, France and the Netherlands' (the war Q221941 is another row's)"),
    "f26fca57": ("repoint", "Q76640124", "'1761 siege' of Kolberg (the 1758 and 1760 sieges are other items)"),
    "eaf138c2": ("repoint", "Q824689", "conference on Canadian confederation, enwiki 'Quebec Conference, 1864'"),
    "188c4cd0": ("repoint", "Q610272", "enwiki 'First Geneva Convention', adopted 1864 (Q21335074 is a second, text-only item)"),
    "96cbc254": ("repoint", "Q1051668", "Strategic Arms Limitation Treaty II, alias SALT II, 1979"),
    "d5e7b9a6": ("repoint", "Q1184068", "Strategic Arms Limitation Treaty I, alias SALT I, 1972 (the talks Q623994 are another row's)"),
    "c8e1d9b6": ("repoint", "Q1194699", "US-Japan treaty of 1858, alias Harris Treaty"),
    "62f19a1c": ("repoint", "Q3100682", "Second Treaty of London, 1359"),
    "0fac899b": ("repoint", "Q1366196", "enwiki 'Gothic War (376-382)'"),
    "60350507": ("repoint", "Q535413", "Seleucid general Achaeus, enwiki 'Achaeus (general)', d. 213"),
    "7b1efab2": ("repoint", "Q185476", "Flavius Aetius (c. 390-454), enwiki 'Flavius Aetius'; row af645188 is the same general (listed as a duplicate)"),
    "714932a1": ("repoint", "Q356050", "Macedonian general Attalus, enwiki 'Attalus (general)', d. 336 BCE"),
    "2c286440": ("repoint", "Q193056", "Basiliscus, Leo I's general and Eastern emperor 475-476, enwiki 'Basiliscus'"),
    "8307331b": ("repoint", "Q4998043", "Mongol lord Buqa (d. 1289), enwiki 'Buqa'"),
    "34dddc34": ("repoint", "Q175714", "Demetrios Palaiologos, Despot of the Morea (1407-1470)"),
    "24c06d74": ("repoint", "Q515741", "Francisco Serrano, 1st Duke of la Torre (1810-1885)"),
    "4f999432": ("repoint", "Q451516", "Curio, Caesar's general (d. 49 BCE), enwiki 'Gaius Scribonius Curio (tribune 50 BC)'"),
    "564be929": ("repoint", "Q741120", "Welsh journalist (1905-1935), enwiki 'Gareth Jones (journalist)'"),
    "7818f8e6": ("repoint", "Q191819", "English record producer (1926-2016), enwiki 'George Martin'"),
    "0226b217": ("repoint", "Q335384", "Peruvian theologian (1928-2024), enwiki 'Gustavo Gutierrez'"),
    "da053614": ("repoint", "Q722689", "James Springer White (1821-1881), co-founder of the Seventh-day Adventist Church"),
    "c44c7d13": ("repoint", "Q314335", "British clockmaker (1693-1776), enwiki 'John Harrison'"),
    "bbbb896b": ("repoint", "Q957542", "English major (1600-1672), enwiki 'John Mason (colonist)'"),
    "08244c8b": ("repoint", "Q886420", "American general (1740-1795), enwiki 'John Sullivan (general)'"),
    "2232ece3": ("repoint", "Q321183", "Lincoln conspirator (1844-1865), enwiki 'Lewis Powell (conspirator)'"),
    "50ac8ec2": ("repoint", "Q710277", "Chinese general (1895-1974), enwiki 'Lu Han (general)'"),
    "4b156692": ("repoint", "Q304970", "consul of 234 BCE killed by the Boii in 216 BCE, enwiki 'Lucius Postumius Albinus (consul 234 BC)'"),
    "88580b6d": ("repoint", "Q314457", "King Magnus IV of Sweden (1316-1374), enwiki 'Magnus Eriksson'"),
    "b883c48b": ("repoint", "Q3870512", "Emir of Bukhara (1806-1860), enwiki 'Nasrullah Khan (emir of Bukhara)'"),
    "ae671bb9": ("repoint", "Q314001", "Rudolf II, Duke of Austria (1270-1290)"),
    "249367fa": ("repoint", "Q75698", "Samuel F. B. Morse (1791-1872), enwiki 'Samuel Morse'"),
    "d605316c": ("repoint", "Q1369409", "explorer (1593-1635), enwiki 'Thomas James (sea captain)'"),
    "feec30d8": ("repoint", "Q342512", "father of Emperor Tiberius (d. 33 BCE)"),
    "94c5bd85": ("repoint", "Q7967574", "Tang politician Wang Pi (d. 805), enwiki 'Wang Pi'; the old QID's person died 785"),
    "6fb66e68": ("repoint", "Q1210370", "Plymouth Colony governor (1590-1657), enwiki 'William Bradford (governor)'"),
    "168af30d": ("repoint", "Q45361363", "Song dynasty person CBDB 3378 (1091-1153), the row's exact dates"),
    "a57f7997": ("repoint", "Q11101788", "Ming dynasty politician (1572-1625)"),
    "731e3213": ("repoint", "Q3944411", "Sack of Mantua, 1630, War of the Mantuan Succession (own dates, place, war, link)"),
    "68879e7d": ("repoint", "Q60188600", "Persian destruction of Athens, 480 BCE"),
    "3072f9f4": ("repoint", "Q679793", "Lausanne Conference of 1932"),
    "6211397d": ("repoint", "Q2047143", "Partition of Bengal by Lord Curzon in 1905, enwiki 'Partition of Bengal (1905)'"),
    "de4d1724": ("repoint", "Q1419429", "11 ships that founded the penal colony in Australia, enwiki 'First Fleet', 1787"),
    "bbce971c": ("repoint", "Q165119", "1929 programme for Germany's WWI reparations, enwiki 'Young Plan'"),
    "fe5c35e5": ("repoint", "Q1150730", "Swedish crown's reduction of noble lands, alias 'Great Reduction of 1680'"),
    "515b3e3c": ("repoint", "Q8187836", "enwiki 'Tripartite Agreement of 1936'"),
    "158a4014": ("repoint", "Q2092225", "Congress of Arras, 1435 (the enwiki article of the 1435 treaty)"),
    "5d59434a": ("repoint", "Q1068139", "Shah's reform programme launched 1963, enwiki 'White Revolution'"),
    "835e0a6d": ("repoint", "Q96506039", "Golden Horde siege of Genoese Caffa ended by plague in 1346, enwiki 'Siege of Caffa'"),
    "977a6f6f": ("repoint", "Q549041", "12th-century jurist, compiler of the Decretum, enwiki 'Gratian (jurist)'"),
    "39240763": ("repoint", "Q11905415", "Hamilcar d. 339 BCE, participant in the Battle of the Crimissus (P1344)"),
    "35eb1e8d": ("repoint", "Q964587", "Hasdrubal d. 339 BCE, participant in the Battle of the Crimissus (P1344)"),
    "f207326f": ("repoint", "Q435531", "tyrant of Athens 528-514 BCE, enwiki 'Hipparchus (brother of Hippias)' (the old QID is the astronomer)"),
    "95daa110": ("repoint", "Q4497915", "king of the Awan dynasty of Elam, enwiki 'Khita'"),
    "4c5f6578": ("repoint", "Q295168", "Frankish merchant who unified Slavic tribes (d. 658), enwiki 'Samo'"),
    "b2aeb778": ("repoint", "Q905162", "legendary founder of Carthage, enwiki 'Dido', alias Elissa"),
    # repoint: the item's enwiki article was looked up by its exact title (the audit client's by_titles), checked by hand
    "06362071": ("repoint", "Q648544", "Ikhshidid ruler of Egypt 960-966, enwiki 'Abu'l-Hasan Ali ibn al-Ikhshid'"),
    "57b781e3": ("repoint", "Q1151461", "Kan B'alam I, ajaw of Palenque (d. 583)"),
    "46440305": ("repoint", "Q5071257", "maharaja of Sindh, enwiki 'Chandar of Sindh'"),
    "30cd0cc7": ("repoint", "Q954089", "Charles Howard, 1st Earl of Nottingham (1536-1624)"),
    "037a3c33": ("repoint", "Q156949", "Charles V, Duke of Lorraine (1643-1690), victor at Buda 1686 (reconcile's pick Q3659993, a Count of Armagnac, was wrong)"),
    "54fcd622": ("repoint", "Q83066", "Coloman, king of Hungary 1095-1116, enwiki 'Coloman, King of Hungary'"),
    "c192d5b8": ("repoint", "Q170335", "Constance I of Sicily (1154-1198), wife of Henry VI"),
    "1baa6e25": ("repoint", "Q1127505", "Louis, Duke of Burgundy (1682-1712)"),
    "8f726e32": ("repoint", "Q378088", "Prince William, Duke of Cumberland (1721-1765), commander at Fontenoy"),
    "127052bb": ("repoint", "Q1000874", "Thomas Montacute, 4th Earl of Salisbury (1388-1428), commander at Orleans"),
    "459c7501": ("repoint", "Q320791", "Jaroslav Borita of Martinice (1582-1649), defenestrated 1618"),
    "2af81a1d": ("repoint", "Q136647363", "British colonial police officer (1907-1928), enwiki 'John P. Saunders'"),
    "b39a6608": ("repoint", "Q828583", "French admiral (1699-1753), enwiki 'Bertrand-Francois Mahe de La Bourdonnais'"),
    "0ba4a823": ("repoint", "Q372740", "Luis Filipe, Prince Royal of Portugal (1887-1908)"),
    "3f7b4687": ("repoint", "Q4404612", "British politician (1780-1835), enwiki 'Michael Thomas Sadler'"),
    "6cc9f4bb": ("repoint", "Q12827827", "Timurid commander (1375-1403), enwiki 'Muhammad Sultan Mirza'"),
    "b78d5bde": ("repoint", "Q465844", "Armand de Bourbon, Prince of Conti (1629-1666)"),
    "6e587997": ("repoint", "Q77255", "William II of Holland, king of the Romans (1228-1256)"),
    "1faba7a6": ("repoint", "Q3391914", "Yahya II al-Qadir, ruler of Toledo then Valencia (d. 1092)"),
    "702c265d": ("repoint", "Q58275", "Henry Montgomery Lawrence (1806-1857), British general at Lucknow"),
    "d7aeb106": ("repoint", "Q468653", "Tancred, King of Sicily (1138-1194)"),
    "879707fc": ("repoint", "Q721440", "Walter V of Brienne, Duke of Athens, d. 1311 at Halmyros"),
    "4a78a56a": ("repoint", "Q283909", "Maximilian III, Archduke of Austria (1558-1618)"),
    "1828bfd3": ("repoint", "Q1061404", "1859 battle, enwiki 'Battle of Taku Forts (1859)'"),
    "300d46b0": ("repoint", "Q1233475", "778 battle between Charlemagne and Basques, enwiki 'Battle of Roncevaux Pass'"),
    "d147ed59": ("repoint", "Q555839", "1812 battle, enwiki 'Battle of Berezina'"),
    "df1b1ff5": ("repoint", "Q4682165", "1839 British capture of Aden, enwiki 'Aden Expedition'"),
    "6c6e16f8": ("repoint", "Q3636319", "30 BCE battle of the last Roman Republican war, enwiki 'Battle of Alexandria (30 BC)'"),
    "6dd0ac6a": ("repoint", "Q815114", "1302 Mamluk siege, enwiki 'Fall of Ruad'"),
    "503af93d": ("repoint", "Q2631076", "1717 siege, enwiki 'Siege of Belgrade (1717)'"),
    "87ba6e40": ("repoint", "Q2546566", "1847 battle, enwiki 'Battle for Mexico City'"),
    "a9bd5c3f": ("repoint", "Q570456", "September 1831 Russian-Polish battle, enwiki 'Battle of Warsaw (1831)'"),
    "624cf40c": ("repoint", "Q1417490", "enwiki '1929 Hebron massacre'"),
    "0e5705e8": ("repoint", "Q815162", "1240 Mongol siege, enwiki 'Siege of Kiev (1240)'"),
    "a4b9c1f4": ("repoint", "Q3625476", "635-636 Rashidun siege, enwiki 'Siege of Emesa'"),
    "824fc507": ("repoint", "Q5432166", "1289 Mamluk capture, enwiki 'Fall of Tripoli (1289)'"),
    "ec784cb0": ("repoint", "Q1509221", "Sulla's victory over Archelaus, enwiki 'Battle of Orchomenus' (P585 86 BCE)"),
    "1644b4e8": ("repoint", "Q2306075", "enwiki 'Dutch Ethical Policy'"),
    "20e6fb84": ("repoint", "Q4566250", "enwiki '1948 Donora smog'"),
    "d1ee37af": ("repoint", "Q551302", "1679 peace treaty, enwiki 'Treaty of Saint-Germain-en-Laye (1679)'"),
    "55e6b9b4": ("repoint", "Q24202", "August 1828 treaty recognising Uruguay, enwiki 'Preliminary Peace Convention (1828)'"),
    "a1ae2e4d": ("repoint", "Q3375560", "Royal Newfoundland Regiment (inception 1795; its enwiki article covers Beaumont-Hamel 1916)"),
    "13ef4f99": ("repoint", "Q2902142", "London Stock Exchange changes of 27 October 1986, enwiki 'Big Bang (financial markets)'"),
    "b8af60d6": ("repoint", "Q5533037", "Reagan-Gorbachev meeting, enwiki 'Geneva Summit (1985)'"),
    "c3feb394": ("repoint", "Q301300", "1942 Pacific battle, enwiki 'Battle of Java (1942)'"),
    # repoint_dates: the right item is certain, but the row's own dates disagree with it (kept needs_review)
    "7dde9a01": ("repoint_dates", "Q2631753", "Andronikos Palaiologos, Lord of Thessalonica (1400-1429); the row's start 1390 predates his birth"),
    "6c61aeed": ("repoint_dates", "Q3620409", "Antoniotto II Adorno, doge 1522 (1479-1528); the row's 1470-1530 differs"),
    "ac4cf545": ("repoint_dates", "Q982003", "architect of the Spanish Steps (1679-1731); the row's 1693-1740 differs"),
    "c6bd412b": ("repoint_dates", "Q712202", "consul of 125 BCE (c. 168-121 BCE); the row's start 180 BCE differs"),
    "186f2bad": ("repoint_dates", "Q250731", "Prince Almos, Duke of Nitra (c. 1070-1127/9), blinded c. 1114; the row's end 1113 is before the blinding its text names"),
    "23b831aa": ("repoint_dates", "Q712674", "Raymond II, Count of Tripoli 1137-1152 (b. c. 1115); the row's start 1100 differs"),
    "dd2cc2a4": ("repoint_dates", "Q547911", "Eric Magnusson, Duke of Sodermanland (1282-1318); the row's start 1300 differs"),
    "33a0c29f": ("repoint_dates", "Q367578", "Vladislaus II, Duke and King of Bohemia (c. 1110-1174); the row's 1131-1180 differs"),
    "a75c3d97": ("repoint_dates", "Q7205532", "Kim Jun, Goryeo military ruler, enwiki 'Kim Chun', d. 1268; the row's end 1258 is the coup year"),

    # dup: the right item is on another row (pair in duplicate-candidates.csv); the wrong QID is cleared
    "0bad6228": ("dup", "Q7316", "Liu Xie is Emperor Xian of Han (alias 'Liu Xie'), whom Jian Shuo tried to enthrone in 189"),
    "29e884c2": ("dup", "Q293455", "the Salvadoran archbishop (1917-1980)"),
    "b0d25bb6": ("dup", "Q293505", "Mamluk sultan al-Nasir Muhammad (1285-1341)"),
    "ec4ba475": ("dup", "Q310035", "Charles George Gordon (1833-1885), died at Khartoum"),
    "522464d1": ("dup", "Q53449", "Jadwiga, Queen of Poland 1384-1399"),
    "f50d93cb": ("dup", "Q272173", "Aethelberht, King of Kent"),
    "c29fbf5d": ("dup", "Q160077", "the 1453 Ottoman capture, enwiki 'Fall of Constantinople'"),
    "a9124639": ("dup", "Q698045", "the 1631 siege and destruction of Magdeburg, enwiki 'Sack of Magdeburg'"),
    "1e35e315": ("dup", "Q3591483", "the 1815 eruption (the old QID is a national park)"),
    "8bdb1db4": ("dup", "Q3651751", "Trajan's Parthian campaign (115-117)"),
    "322a951f": ("dup", "Q13600791", "Battle of Gol-Zarriun, alias 'Battle of Bukhara' (c. 557-560)"),
    "a8732d5a": ("dup", "Q815160", "the storming of Carthage ending the 149-146 BCE siege, enwiki 'Siege of Carthage (Third Punic War)'"),

    # clear: the QID is another thing and no certain replacement was found
    "377b7700": ("clear", "", "the old QID is the unicameral Congress from 1995; the row is the 1822-1826 constituent congress"),
    "a32fb3df": ("clear", "", "the old QID is the renminbi; the row is the Northern Wei surname Yuan"),
    "bf58fb17": ("clear", "", "the old QID is the 963 battle; the row is the 1486 Ottoman-Mamluk battle"),
    "bd1077ee": ("clear", "", "the old QID is the 1821 battle; the row is the 1428 Tepanec war battle"),
    "edbc00f4": ("clear", "", "the old QID is the 1941 Battle of Hong Kong; the row is the 638 BCE Battle of Hong"),
    "9e8ff61b": ("clear", "", "the old QID is the 1497 battle; the row is 749 (Q16822633 'Battle of Spahan' is 642)"),
    "5ee5e2fa": ("clear", "", "the old QID is the 1184/5 Genpei battle; the row is the 940 battle against Masakado"),
    "6ea86db9": ("clear", "", "the old QID is the 1950 battle; the row is Qi Jiguang's 1565 victory"),
    "2e89296e": ("clear", "", "the old QID is the 1853 battle; the row is Zhu Di's 1402 entry into Nanjing"),
    "68acdf17": ("clear", "", "the old QID is the 1038 battle; the row is the 1340 Sarbadar victory"),
    "7a043eb5": ("clear", "", "the old QID is the 1757 battle; the row is Ismail I's 1501 victory"),
    "5e79610c": ("clear", "", "the old QID is the 1914 battle; the row is Labienus' 53 BCE victory over Indutiomarus"),
    "5c7feaee": ("clear", "", "the old QID is the 1555 siege; the row is the 1152 Almohad capture (the 1510 one is another row)"),
    "fe51db43": ("clear", "", "the old QID is the 1918 capture; the row is Tiglath-Pileser III's 732 BCE conquest"),
    "efcfcdc2": ("clear", "", "the old QID is the 1614 capture; the row is the 1681 Moroccan capture"),
    "549b3f2a": ("clear", "", "the old QID is the 218 BCE Roman invasion; the row is the 870 Aghlabid conquest"),
    "bf5f0a02": ("clear", "", "the old QID is the 1884 operation; the row is the 651 Arab capture"),
    "05e0a805": ("clear", "", "the old QID is the 1038 siege; the row is the 842/3 Aghlabid capture"),
    "b67d2c40": ("clear", "", "the old QID is the 1831 battle; the row is the 1509 Spanish conquest"),
    "7c29762b": ("clear", "", "the old QID is the 1585 siege; the row is the 1534 Ottoman capture"),
    "954b26ff": ("clear", "", "the old QID is a Veronese painting; the row is the Lydian conquest c. 600 BCE"),
    "47daf231": ("clear", "", "the old QID is the 539 BCE fall; the row is Ashurbanipal's 648 BCE capture"),
    "647a9d2a": ("clear", "", "the old QID is the 1944 anniversary; the row is Demetrius' 307 BCE operation"),
    "46f3aaf2": ("clear", "", "the old QID is the 1500-1501 campaign; the row is Tahmasp I's 1538 annexation"),
    "05dfc0c5": ("clear", "", "the old QID is the 1101 siege; the row is the 640 Muslim capture (Q7509892 is the 614 siege)"),
    "59654b10": ("clear", "", "the old QID is the 859 siege; the row is the 132 BCE Roman capture"),
    "4116c0e8": ("clear", "", "the old QID is the 197-198 siege; the row is Trajan's siege (candidate Q128094228 'siege by Trajan' is dated 177 on Wikidata)"),
    "f0e70315": ("clear", "", "the old QID is the 1360s expedition; the row is the 1620 Mughal capture"),
    "f921c944": ("clear", "", "the old QID is the 1794 siege; the row is Mahmud Hotak's 1721 siege"),
    "fedb0e26": ("clear", "", "the old QID is the 1159-1160 siege; the row is Abu Yazid's 945 siege"),
    "40628ce4": ("clear", "", "the old QID is the 573 siege; the row is the 338-350 series (one item per siege on Wikidata)"),
    "d83ce287": ("clear", "", "the old QID is the 387 BCE siege; the row is the 270 BCE Roman operation"),
    "55eac24f": ("clear", "", "the old QID is the 108-107 BCE siege; the row is the 725-722 BCE Assyrian siege"),
    "074f6c08": ("clear", "", "the old QID is the 1247-1248 siege; the row is Leovigild's 584 siege"),
    "1cbf5872": ("clear", "", "the old QID is the 1863 siege; the row is Xu Da's 1366-1367 siege"),
    "52b22766": ("clear", "", "the old QID is Gallait's painting; the row is the 1556 abdication"),
    "753c94b0": ("clear", "", "the old QID is the 554 council; the row is the 314 council"),
    "4b53db41": ("clear", "", "the old QID is the 1148 council; the row is Leo IX's 1049 council"),
    "51de4ab4": ("clear", "", "the old QID is a 1976 film; the row is the 1291-1292 Scottish succession case"),
    "a04eb8bb": ("clear", "", "the old QID is a Japanese government department; the row is the 1910-1918 Korean cadastral survey"),
    "6ff483d3": ("clear", "", "the old QID is the 964 synod; the row is the 1059 council"),
    "fe0f39c0": ("clear", "", "the old QID is a Santiago metro station; the row is the Cuban patronato (1880-1886)"),
    "082397dd": ("clear", "", "the old QID is the 341 synod; the row is the 268 synod against Paul of Samosata"),
    "00ab42d7": ("clear", "", "the old QID is a 1955 article on prehistory; the row is the 1923 Pan-African Congress"),
    "a5e3c441": ("clear", "", "the old QID is the 1703 forty-seven ronin affair; the row is the 888 Ako dispute"),
    "317feb95": ("clear", "", "the old QID is the Soviet Great Purge; the row is the French Terror of June-July 1794"),
    "b0f3c04c": ("clear", "", "the old QID is a 2003 article; the row is the European Neolithic transition"),
    "480b3f37": ("clear", "", "the old QID is a 2021 conference; the row is the 1960 conference that founded OPEC"),
    "4d7f8719": ("clear", "", "the old QID is the 2001 POPs convention; the row is the 1960 EFTA convention"),
    "00cd796b": ("clear", "", "the old QID is a Lucas van Leyden painting; the row is the 1647 Engagement"),
    "4d7987b4": ("clear", "", "the old QID is a 1942 treaty; the row is the 1906 Ethiopia accord"),
    "c8a8cb02": ("clear", "", "the old QID is a 1990 book; the row is the 1942 U-boat offensive (candidate Q569454 'Second Happy Time' is wider)"),
    "f84755ec": ("clear", "", "the old QID is the 1400-1401 campaign; the row is Napoleon's 1799 campaign"),
    "a5e5fab9": ("clear", "", "the old QID is Nevrev's painting; the row is Ivan IV's oprichniki"),
    "63ec91a6": ("clear", "", "the old QID is the emir of Sicily (d. 989); the row is the last Midrarid emir (d. 976)"),
    "d4d3662a": ("clear", "", "the old QID is the Companion (d. 657); the row is the Kharijite leader killed in 865"),
    "03271a01": ("clear", "", "the old QID is Empress Deng Sui's father (d. 92); the row is the Wu administrator killed in 263"),
    "1b57a49c": ("clear", "", "the old QID is Patriarch Clement (1667); the row is the office as created in 1454"),
    "0cfc6ee7": ("clear", "", "the old QID died 1625; the row is the Nerchinsk negotiator (1650-1706), whose item was not found"),
    "391aa31b": ("clear", "", "the old QID is an Indonesian politician; the row is a 23rd-century BCE king of Mari"),
    "fe23d054": ("clear", "", "the old QID is the Queen of Italy (1851-1926); the row is Margherita of Savoy (1589-1655)"),
    "18e6159d": ("clear", "", "the old QID is a playwright (1917-2009); the row is the Fort Sumter commander, whose item was not found"),
    "27eb578e": ("clear", "", "the old QID is a sultan of Kedah; the row is the Tughlaq sultan Nasir-ud-Din Mahmud Shah"),
    "cec0979b": ("clear", "", "the old QID is Maurice's son (583-602); the row is Count Theodosius (its dates 340-395 do not fit him)"),
    "31808d5f": ("clear", "", "the old QID is a badminton player; the row is the Old Kingdom official Weni"),
    "682c0a24": ("clear", "", "the old QID is Emperor Yeshaq Iyasu (d. 1685); the row is the bahr negash defeated in 1559"),
}

# rows that are the same thing as another row although neither holds the other's QID (listed, not merged)
EXTRA_DUPS: list[tuple[str, str, str]] = [
    ("7b1efab2", "af645188", "'Aetius' and 'Flavius Aetius' are the same general (d. 454); af645188 carries Q3746479, a consul of 454, not him"),
]


# ── plan ────────────────────────────────────────────────────────────────────
PLANNED_FIELDS = ["entity_id", "name", "entity_type", "row_start", "row_end", "decision", "old_qid", "old_label",
                  "old_description", "new_qid", "new_label", "new_description", "status_before", "status_after",
                  "flags_before", "flags_after", "drop_media", "point_method", "point_from_old_qid", "new_c2", "attrs_md5", "note"]
DUP_FIELDS = ["entity_id", "name", "entity_type", "row_span", "wrong_qid", "right_qid", "right_label",
              "held_by_id", "held_by_name", "held_by_type", "held_by_span", "evidence", "merge_command"]
# flags (besides the suspect flag) that keep a row in needs_review
REVIEW_FLAGS = ("identity_audit:", "namesake_ambiguous", "low_wikidata_match", "no_wikidata_match",
                "implausible_lifespan")
MEDIA_FROM_QID = ("wikidata", "wikipedia")
REPOINTS = ("repoint", "repoint_dates")
DATES_FLAG = "identity_audit:row_dates_suspect"


def _span(start, end) -> str:
    return f"{'' if start is None else start}..{'' if end is None else end}"


def new_flags(flags: list[str], decision: str) -> list[str]:
    out = [f for f in flags if not str(f).startswith(SUSPECT)]
    add = {"clear": "identity_audit:qid_cleared", "dup": "identity_audit:qid_cleared:duplicate",
           "confirm_dates": DATES_FLAG, "repoint_dates": DATES_FLAG}.get(decision)
    if add and add not in out:
        out.append(add)
    return out


def new_status(status: str, flags_after: list[str], decision: str, before: str | None) -> str:
    if decision in ("clear", "dup", "confirm_dates", "repoint_dates"):
        return "needs_review"
    if any(str(f).startswith(REVIEW_FLAGS) for f in flags_after):
        return status
    # back to what the identity audit changed it from; unchanged when the audit never set it
    return before or status


def new_attributes(attrs: dict[str, Any], decision: str, old_qid: str) -> tuple[dict[str, Any], int]:
    """(attributes after the decision, number of media_refs dropped)."""
    out = dict(attrs)
    out["validation_flags"] = new_flags(list(attrs.get("validation_flags") or []), decision)
    dropped = 0
    if decision in ("clear", "dup"):
        out["_rejected_wikidata_id"] = old_qid
    if decision in ("clear", "dup", "repoint", "repoint_dates") and not attrs.get("_media_curated_at"):
        media = attrs.get("media_refs")
        if isinstance(media, list) and media:
            keep = [m for m in media if not (isinstance(m, dict) and m.get("source") in MEDIA_FROM_QID)]
            dropped = len(media) - len(keep)
            if dropped:
                if keep:
                    out["media_refs"] = keep
                else:
                    out.pop("media_refs")  # NULL again: the nightly fetch refetches it for a new QID
        elif media == [] and decision in REPOINTS:
            out.pop("media_refs")  # "nothing found" for the old QID: let the nightly fetch try the new one
    return out, dropped


def _same_point(point, coord) -> bool:
    """Whether the row's primary point is the old QID's P625 (point is lon/lat, coord lat/lon)."""
    return bool(point and coord) and abs(point[0] - coord[1]) < 1e-3 and abs(point[1] - coord[0]) < 1e-3


def merge_command(survivor: str, loser: str) -> str:
    return ('scripts/capped.sh pipeline/.venv/bin/python3 -c "import psycopg; from pipeline.merge_entities '
            f"import merge, DSN; c=psycopg.connect(DSN); merge(c.cursor(), '{survivor}', '{loser}'); c.commit()\"")


def plan(out: Path) -> None:
    evidence = json.loads((out / "evidence.json").read_text())
    before = audit_status_before()
    conn = connect()
    cur = conn.cursor()
    cl = client(offline=True)
    rows = load_rows(conn)
    planned, dups, missing = [], [], []
    for e in evidence:
        key = e["entity_id"][:8]
        if key not in DECISIONS:
            missing.append(f"{key} {e['name']}")
            continue
        decision, new_qid, note = DECISIONS[key]
        cur.execute("SELECT wikidata_id, verification_status::text, coalesce(attributes, '{}'::jsonb), "
                    "md5(attributes::text), e.name FROM entities e WHERE entity_id = %s", (e["entity_id"],))
        got = cur.fetchone()
        if not got:
            missing.append(f"{key} {e['name']} (row gone)")
            continue
        qid, status, attrs, md5, name = got
        cur.execute("SELECT coalesce(location_method,'') FROM entity_locations WHERE entity_id = %s AND is_primary",
                    (e["entity_id"],))
        pm = cur.fetchone()
        flags = list(attrs.get("validation_flags") or [])
        attrs_after, dropped = (attrs, 0) if decision == "leave" else new_attributes(attrs, decision, qid)
        flags_after = flags if decision == "leave" else attrs_after["validation_flags"]
        status_after = status if decision == "leave" else new_status(status, flags_after, decision,
                                                                     before.get(e["entity_id"]))
        _, old_rec = cl.resolved(qid) if qid else (None, None)
        _, new_rec = cl.resolved(new_qid) if new_qid else (None, None)
        if decision in REPOINTS + ("dup",) and not (new_rec and new_rec.get("status") == "ok"):
            raise SystemExit(f"{key} {e['name']}: {new_qid} not in the entity cache")
        new_c2 = ""
        if decision in REPOINTS:
            fq, _ = cl.resolved(new_qid)
            closure = cl.class_roots(new_rec.get("p31", []), C.ALL_ROOTS)
            c2 = check_row(dataclasses.replace(rows[e["entity_id"]], qid=fq), cl, closure)
            new_c2 = f"{c2['verdict']} {c2['rule']}".strip()
        line = {"entity_id": e["entity_id"], "name": name, "entity_type": e["type"], "row_start": e["start"],
                "row_end": e["end"], "decision": decision, "old_qid": qid,
                "old_label": (old_rec or {}).get("label", ""), "old_description": (old_rec or {}).get("description", ""),
                "new_qid": new_qid if decision in REPOINTS else "" if decision in ("clear", "dup") else qid,
                "new_label": (new_rec or {}).get("label", "") if decision in REPOINTS + ("dup",) else "",
                "new_description": (new_rec or {}).get("description", "") if decision in REPOINTS + ("dup",) else "",
                "new_c2": new_c2,
                "status_before": status, "status_after": status_after, "flags_before": flags,
                "flags_after": flags_after, "drop_media": dropped, "point_method": pm[0] if pm else "",
                "point_from_old_qid": _same_point(rows[e["entity_id"]].point, (old_rec or {}).get("coord")),
                "attrs_md5": md5,
                "note": f"{note} | was {qid} {(old_rec or {}).get('label', '')!r} "
                        f"({(old_rec or {}).get('description', '')}; {(old_rec or {}).get('dates') or {}})"}
        planned.append(line)
        if decision == "dup":
            cur.execute("SELECT e.entity_id::text, e.name, e.entity_type::text, t.start_year, t.end_year "
                        "FROM entities e LEFT JOIN entity_temporal_ranges t ON t.entity_id = e.entity_id "
                        "AND t.is_primary WHERE e.wikidata_id = %s", (new_qid,))
            for hid, hname, htype, hs, he in cur.fetchall():
                dups.append({"entity_id": e["entity_id"], "name": name, "entity_type": e["type"],
                             "row_span": _span(e["start"], e["end"]), "wrong_qid": qid, "right_qid": new_qid,
                             "right_label": f"{new_rec.get('label', '')} ({new_rec.get('description', '')})",
                             "held_by_id": hid, "held_by_name": hname, "held_by_type": htype,
                             "held_by_span": _span(hs, he), "evidence": note,
                             "merge_command": merge_command(hid, e["entity_id"])})
    if missing:
        raise SystemExit("no decision for: " + "; ".join(missing))
    for a, b, note in EXTRA_DUPS:
        cur.execute("SELECT e.entity_id::text, e.name, e.entity_type::text, e.wikidata_id, t.start_year, t.end_year "
                    "FROM entities e LEFT JOIN entity_temporal_ranges t ON t.entity_id = e.entity_id "
                    "AND t.is_primary WHERE e.entity_id::text LIKE %s OR e.entity_id::text LIKE %s",
                    (a + "%", b + "%"))
        got = {r[0][:8]: r for r in cur.fetchall()}
        ra, rb = got[a], got[b]
        dups.append({"entity_id": ra[0], "name": ra[1], "entity_type": ra[2], "row_span": _span(ra[4], ra[5]),
                     "wrong_qid": "", "right_qid": next((p["new_qid"] for p in planned if p["entity_id"] == ra[0]), ra[3]) or "",
                     "right_label": "", "held_by_id": rb[0],
                     "held_by_name": rb[1], "held_by_type": rb[2], "held_by_span": _span(rb[4], rb[5]),
                     "evidence": note, "merge_command": merge_command(ra[0], rb[0])})
    order = {"repoint": 0, "repoint_dates": 1, "dup": 2, "clear": 3, "confirm": 4, "confirm_dates": 5, "leave": 6}
    planned.sort(key=lambda x: (order[x["decision"]], x["entity_type"], x["name"]))
    write_csv(out / "planned.csv", planned, PLANNED_FIELDS)
    write_csv(out / "duplicate-candidates.csv", dups, DUP_FIELDS)
    from collections import Counter
    print(f"plan: {dict(Counter(p['decision'] for p in planned))}; duplicates {len(dups)}; "
          f"media_refs dropped on {sum(1 for p in planned if p['drop_media'])} rows")


# ── apply ───────────────────────────────────────────────────────────────────
APPLIED_FIELDS = ["ts", "decision", "entity_id", "name", "column", "old", "new", "note", "status"]


def _lit(v: Any) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, (dict, list)):
        return "'" + json.dumps(v, ensure_ascii=False).replace("'", "''") + "'::jsonb"
    return "'" + str(v).replace("'", "''") + "'"


def backup(out: Path) -> Path:
    path = out / f"backup-{time.strftime('%Y%m%d-%H%M%S')}.sql.gz"
    cmd = [*COMPOSE, "exec", "-T", "db", "pg_dump", "-U", "history-mapped", "-d", "history-mapped",
           "--no-owner", "--data-only", "-t", "public.entities"]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0 or not proc.stdout:
        raise SystemExit(f"pg_dump failed: {proc.stderr.decode()[:500]}")
    with gzip.open(path, "wb") as fh:
        fh.write(proc.stdout)
    return path


def apply(out: Path, dry: bool = False) -> None:
    """Write the planned changes in one transaction (``dry``: roll back, write no files)."""
    with (out / "planned.csv").open(encoding="utf-8") as fh:
        planned = [p for p in csv.DictReader(fh) if p["decision"] != "leave"]
    if not dry:
        bk = backup(out)
        print(f"apply: backup {bk.name}")
    conn = connect(read_only=False)
    cur = conn.cursor()
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    log: list[dict[str, Any]] = []
    rollback: list[str] = []

    def entry(p, column, old, new, status="applied"):
        log.append({"ts": ts, "decision": p["decision"], "entity_id": p["entity_id"], "name": p["name"],
                    "column": column, "old": json.dumps(old, ensure_ascii=False) if isinstance(old, list) else old,
                    "new": json.dumps(new, ensure_ascii=False) if isinstance(new, list) else new,
                    "note": p["note"], "status": status})

    try:
        for p in planned:
            eid = p["entity_id"]
            cur.execute("SELECT wikidata_id, verification_status::text, coalesce(attributes, '{}'::jsonb), "
                        "md5(attributes::text), updated_at FROM entities WHERE entity_id = %s FOR UPDATE", (eid,))
            got = cur.fetchone()
            if not got:
                entry(p, "-", None, None, "skipped: row gone")
                continue
            qid, status, attrs, md5, updated = got
            if (qid or "") != p["old_qid"] or status != p["status_before"] or md5 != p["attrs_md5"]:
                entry(p, "-", None, None, f"skipped: row changed since plan (qid {qid}, status {status})")
                continue
            new_qid = p["new_qid"] or None
            if p["decision"] in REPOINTS:
                cur.execute("SELECT entity_id::text FROM entities WHERE wikidata_id = %s AND entity_id <> %s LIMIT 1",
                            (new_qid, eid))
                holder = cur.fetchone()
                if holder:
                    entry(p, "wikidata_id", qid, new_qid, f"skipped: {new_qid} is on row {holder[0]}")
                    continue
            attrs_after, _ = new_attributes(attrs, p["decision"], qid)
            status_after = p["status_after"]
            cur.execute("UPDATE entities SET wikidata_id = %s, attributes = %s::jsonb, "
                        "verification_status = %s::verification_status, updated_at = now() "
                        "WHERE entity_id = %s AND wikidata_id IS NOT DISTINCT FROM %s "
                        "AND verification_status = %s::verification_status AND md5(attributes::text) = %s",
                        (new_qid, json.dumps(attrs_after, ensure_ascii=False), status_after, eid, qid, status, md5))
            if cur.rowcount != 1:
                entry(p, "-", None, None, "skipped: guarded update matched no row")
                continue
            if new_qid != qid:
                entry(p, "wikidata_id", qid, new_qid)
            entry(p, "attributes.validation_flags", attrs.get("validation_flags") or [],
                  attrs_after.get("validation_flags") or [])
            if attrs_after.get("_rejected_wikidata_id") != attrs.get("_rejected_wikidata_id"):
                entry(p, "attributes._rejected_wikidata_id", attrs.get("_rejected_wikidata_id"),
                      attrs_after.get("_rejected_wikidata_id"))
            if attrs_after.get("media_refs") != attrs.get("media_refs"):
                entry(p, "attributes.media_refs", f"{len(attrs.get('media_refs') or [])} items",
                      f"{len(attrs_after.get('media_refs') or [])} items")
            if status_after != status:
                entry(p, "verification_status", status, status_after)
            # the inverse, guarded on what this write left behind
            cur.execute("SELECT attributes FROM entities WHERE entity_id = %s", (eid,))
            written = cur.fetchone()[0]
            rollback.append(
                f"UPDATE entities SET wikidata_id = {_lit(qid)}, attributes = {_lit(attrs)}, "
                f"verification_status = {_lit(status)}, updated_at = {_lit(str(updated) if updated else None)} "
                f"WHERE entity_id = {_lit(eid)} AND wikidata_id IS NOT DISTINCT FROM {_lit(new_qid)} "
                f"AND verification_status = {_lit(status_after)} AND attributes = {_lit(written)};")
        if dry:
            conn.rollback()
        else:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    if dry:
        from collections import Counter
        print(f"dry run (rolled back): {len(rollback)} rows; log {dict(Counter(x['status'][:40] for x in log))}")
        return
    write_csv(out / "applied.csv", log, APPLIED_FIELDS)
    rb = out / "rollback.sql"
    rb.write_text(
        "-- Rollback of the qid-suspect review (pipeline/audit/suspect_review.py).\n"
        f"-- Run: docker compose -f docker/docker-compose.yml exec -T db psql -U history-mapped "
        f"-d history-mapped -f - < {rb.resolve().relative_to(REPO)}\n"
        "-- Each statement fires only while the row still holds exactly what the review wrote.\n"
        "\\set ON_ERROR_STOP on\n"
        f"-- batch {ts}: {len(rollback)} rows\nBEGIN;\n" + "\n".join(reversed(rollback)) + "\nCOMMIT;\n")
    from collections import Counter
    print(f"apply: {len(rollback)} rows written; log {dict(Counter(x['status'] for x in log))}")


def apply_media(out: Path) -> None:
    """Second batch (2026-11-01 23:1x): drop an empty ``media_refs`` ([] = nothing found for the OLD QID)
    on re-pointed rows, so the nightly ``entity:fetch-images`` fetches the new QID's images. Guarded on
    the QID and status the first batch wrote and on media_refs still being []; appended to applied.csv and
    rollback.sql."""
    with (out / "planned.csv").open(encoding="utf-8") as fh:
        planned = [p for p in csv.DictReader(fh) if p["decision"] in REPOINTS]
    conn = connect(read_only=False)
    cur = conn.cursor()
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    log, rollback = [], []
    try:
        for p in planned:
            cur.execute("UPDATE entities SET attributes = attributes - 'media_refs', updated_at = now() "
                        "WHERE entity_id = %s AND wikidata_id = %s AND verification_status = %s::verification_status "
                        "AND attributes->'media_refs' = '[]'::jsonb AND NOT attributes ? '_media_curated_at'",
                        (p["entity_id"], p["new_qid"], p["status_after"]))
            if cur.rowcount == 1:
                log.append({"ts": ts, "decision": p["decision"], "entity_id": p["entity_id"], "name": p["name"],
                            "column": "attributes.media_refs", "old": "[] (nothing found for the old QID)",
                            "new": "(removed: refetch for the new QID)", "note": p["note"], "status": "applied"})
                rollback.append(f"UPDATE entities SET attributes = attributes || '{{\"media_refs\": []}}'::jsonb "
                                f"WHERE entity_id = {_lit(p['entity_id'])} AND wikidata_id = {_lit(p['new_qid'])} "
                                f"AND NOT attributes ? 'media_refs';")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    path = out / "applied.csv"
    with path.open(encoding="utf-8") as fh:
        previous = list(csv.DictReader(fh))
    write_csv(path, previous + log, APPLIED_FIELDS)
    rb = out / "rollback.sql"
    head, body = rb.read_text().split("\\set ON_ERROR_STOP on\n", 1)
    rb.write_text(head + "\\set ON_ERROR_STOP on\n" + f"-- batch {ts}: {len(rollback)} rows (empty media_refs)\nBEGIN;\n"
                  + "\n".join(rollback) + "\nCOMMIT;\n" + body)
    print(f"apply-media: {len(rollback)} rows")


def test_rollback(out: Path) -> None:
    """Run rollback.sql's statements in a transaction that is rolled back; report how many fire."""
    body = (out / "rollback.sql").read_text()
    stmts = [s for s in body.splitlines() if s.startswith("UPDATE entities")]
    conn = connect(read_only=False)
    cur = conn.cursor()
    fired = 0
    try:
        for s in stmts:
            cur.execute(s)
            fired += cur.rowcount
        cur.execute("SELECT count(*) FROM entities WHERE attributes->'validation_flags' @> %s::jsonb",
                    (json.dumps([SUSPECT]),))
        print(f"rollback test: {fired}/{len(stmts)} statements fired; rows flagged {SUSPECT} after: "
              f"{cur.fetchone()[0]} (rolled back)")
    finally:
        conn.rollback()


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="pipeline.audit.suspect_review")
    ap.add_argument("stage", choices=("gather", "plan", "apply", "apply-media", "test-rollback"))
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="apply: run the transaction and roll it back")
    a = ap.parse_args(argv)
    if a.stage == "gather":
        gather(a.out, a.offline)
    elif a.stage == "plan":
        plan(a.out)
    elif a.stage == "apply-media":
        apply_media(a.out)
    elif a.stage == "apply":
        apply(a.out, a.dry_run)
    else:
        test_rollback(a.out)


if __name__ == "__main__":
    main()
