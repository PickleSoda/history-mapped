"""The identity audit run: C1 inventory → C2/C3 QIDs → C4 duplicates → C5 names
→ C6 text → C7 relations → C8 stories → (C9 safe fixes) → report."""
from __future__ import annotations

import csv
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from pipeline.agent.tools.disambiguation import names_equal
from pipeline.audit import classes as C
from pipeline.audit.common import CACHE_DIR, connect, inventory, load_relationships, load_rows, write_csv
from pipeline.audit.dups import find_duplicates
from pipeline.audit.names import conventions, name_issues
from pipeline.audit.qid import check_row, find_correct_qid, prefetch_candidates
from pipeline.audit.relations import relation_flags
from pipeline.audit.text import text_flags
from pipeline.audit.wd import WikidataClient

SECTIONS = ("qid", "places", "dups", "names", "text", "relations", "stories")
PLACE_FIELDS = ["entity_id", "name", "entity_type", "qid", "wd_description", "qid_places", "summary", "action",
                "proposed_qid", "proposed_description", "held_by"]
# QID-wrong rules whose rows lose the QID when no correct one is found. W6
# (namesake judged by the row's text alone) only goes to review.
CLEAR_RULES = ("W1", "W2", "W3", "W4", "W5", "W7")

QID_FIELDS = ["entity_id", "name", "entity_type", "qid", "verdict", "severity", "rule", "issues", "wd_label",
              "wd_description", "wd_kinds", "name_check", "class_check", "generic", "date_check", "row_start",
              "row_end", "wd_start", "wd_end", "date_off", "text_supports_row", "rels", "status",
              "resolution", "proposed_qid", "proposed_label", "candidates", "action", "created_by"]
DUP_FIELDS = ["group", "category", "confidence", "entity_type", "survivor_id", "survivor_name", "survivor_qid",
              "survivor_rels", "survivor_span", "loser_id", "loser_name", "loser_qid", "loser_rels", "loser_span",
              "qids_in_group", "evidence", "moves", "lost_on_delete", "merge_command"]
NAME_FIELDS = ["entity_id", "name", "entity_type", "qid", "issues", "proposed_name", "apply", "note"]
TEXT_FIELDS = ["entity_id", "name", "entity_type", "qid", "check", "severity", "detail", "row_span", "text_years",
               "summary"]
REL_FIELDS = ["relationship_id", "check", "severity", "detail", "relationship_type", "source_id", "source_name",
              "source_type", "source_span", "target_id", "target_name", "target_type", "target_span", "description"]
STORY_FIELDS = ["story", "source", "where", "role", "name", "qid", "wd_label", "wd_description", "wd_era", "db_row",
                "problems", "proposed_qid", "evidence"]


class Audit:
    def __init__(self, out_dir: Path, *, offline: bool = False, limit: int | None = None, workers: int = 4):
        self.out = out_dir
        self.out.mkdir(parents=True, exist_ok=True)
        self.conn = connect()
        self.rows = load_rows(self.conn)
        self.client = WikidataClient(CACHE_DIR, offline=offline, workers=workers)
        self.limit = limit
        self.results: dict[str, Any] = {}

    def closure(self, classes) -> dict[str, set[str]]:
        return self.client.class_roots(classes, C.ALL_ROOTS)

    def log(self, msg: str) -> None:
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

    # ── C1 ───────────────────────────────────────────────────────────────────
    def inventory(self, label: str) -> dict[str, Any]:
        inv = inventory(self.rows)
        inv["taken_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        path = self.out / f"inventory-{label}.json"
        if label != "before" or not path.exists():
            path.write_text(json.dumps(inv, indent=1))
        else:
            inv = json.loads(path.read_text())
        self.results[f"inventory_{label}"] = inv
        self.log(f"C1 inventory ({label}): {inv['entities']} entities, {inv['with_qid']} with QID")
        return inv

    # ── C2 + C3 ──────────────────────────────────────────────────────────────
    def qids(self, only_ids: set[str] | None = None, resolve: bool = True, write: bool = True) -> list[dict[str, Any]]:
        qrows = [r for r in self.rows.values() if r.qid and (only_ids is None or r.id in only_ids)]
        qrows.sort(key=lambda r: r.id)
        if self.limit:
            qrows = qrows[:self.limit]
        self.log(f"C2 checking {len(qrows)} QIDs")
        self.client.get_entities([r.qid for r in qrows], progress=True)
        targets = [rec["redirect_to"] for q, rec in self.client.entities.items()
                   if rec.get("status") == "redirect"]
        self.client.get_entities(targets)
        p31 = {c for r in qrows for c in (self.client.resolved(r.qid)[1] or {}).get("p31", [])}
        closure = self.closure(p31)
        by_qid: dict[str, list[str]] = {}
        for r in self.rows.values():
            if r.qid:
                by_qid.setdefault(r.qid, []).append(r.id)
        checked = []
        for r in qrows:
            res = check_row(r, self.client, closure)
            res["created_by"] = r.created_by
            res["action"] = ""
            if res["verdict"] != "ok":
                checked.append((r, res))

        def excluded(r, res):
            ex = {r.qid, res.get("resolved_qid"), (r.attributes or {}).get("_rejected_wikidata_id")}
            return {q for q in ex if q}

        wrong = [(r, excluded(r, res)) for r, res in checked if res["verdict"] == "wrong"]
        if resolve and wrong:
            self.log(f"C3 resolving {len(wrong)} wrong QIDs")
            prefetch_candidates(wrong, self.client, self.closure)
        flags = []
        for r, res in checked:
            if res["verdict"] == "wrong" and resolve:
                found = find_correct_qid(r, self.client, self.closure, exclude=excluded(r, res))
                res["resolution"] = found["outcome"]
                res["candidates"] = found.get("candidates", [])
                if found["outcome"] == "high":
                    res["proposed_qid"] = found["qid"]
                    res["proposed_label"] = f"{found['label']} — {found.get('description', '')}"
                    holders = [h for h in by_qid.get(found["qid"], []) if h != r.id]
                    res["action"] = (f"duplicate_of:{','.join(holders)}" if holders else "set_qid")
                elif res["rule"][:2] in CLEAR_RULES:
                    res["action"] = "clear_qid"
                else:
                    res["action"] = "needs_review"
                if res["action"].startswith("duplicate_of"):
                    res["action"] = "clear_qid+" + res["action"] if res["rule"][:2] in CLEAR_RULES else \
                        "needs_review+" + res["action"]
            elif res["verdict"] == "redirect" or (res["resolved_qid"] != r.qid and res["verdict"] != "wrong"):
                res["action"] = "set_qid(redirect)"
                res["proposed_qid"] = res["resolved_qid"]
            flags.append(res)
        _settle_collisions(flags, self.rows, by_qid)
        flags.sort(key=lambda f: ({"high": 0, "medium": 1, "low": 2, "info": 3}[f["severity"]], f["rule"], f["name"]))
        if write:
            write_csv(self.out / "qid-flags.csv", flags, QID_FIELDS)
            self.results["qid_flags"] = flags
        self.log(f"C2 flags: {Counter(f['verdict'] for f in flags)}")
        return flags

    # ── C4–C8 ────────────────────────────────────────────────────────────────
    def dups(self) -> list[dict[str, Any]]:
        dups = find_duplicates(self.rows)
        extra = self._qid_resolution_dups()
        dups.extend(extra)
        order = {"same_qid": 0, "qid_resolution": 1, "disambiguator": 2, "same_name": 3}
        dups.sort(key=lambda d: (order.get(d["category"], 9), {"high": 0, "medium": 1, "low": 2}[d["confidence"]],
                                 str(d["survivor_name"])))
        write_csv(self.out / "duplicates.csv", dups, DUP_FIELDS)
        self.results["dups"] = dups
        self.log(f"C4 duplicates: {Counter((d['category'], d['confidence']) for d in dups)}")
        return dups

    def _qid_resolution_dups(self) -> list[dict[str, Any]]:
        """Rows whose correct QID (found in C3) is already on another row."""
        from pipeline.audit.dups import merge_command, survivor_key

        out = []
        for f in self.results.get("qid_flags", []):
            if "duplicate_of:" not in f.get("action", ""):
                continue
            holder_ids = f["action"].split("duplicate_of:")[1].split(",")
            row = self.rows[f["entity_id"]]
            for hid in holder_ids:
                holder = self.rows[hid]
                surv, loser = sorted([row, holder], key=survivor_key, reverse=True)
                out.append({"group": f"Q-{row.id[:8]}", "category": "qid_resolution", "confidence": "medium",
                            "entity_type": row.type, "survivor_id": surv.id, "survivor_name": surv.name,
                            "survivor_qid": surv.qid, "survivor_rels": surv.rels, "survivor_span": surv.span,
                            "loser_id": loser.id, "loser_name": loser.name, "loser_qid": loser.qid,
                            "loser_rels": loser.rels, "loser_span": loser.span, "qids_in_group": [f["proposed_qid"]],
                            "evidence": f"{row.name!r} carries wrong {f['qid']} ({f['rule']}); its QID is "
                                        f"{f['proposed_qid']}, " + ("held by" if holder.qid == f["proposed_qid"]
                                                                     else "also the C3 match of") + f" {holder.name!r}",
                            "moves": f"{loser.rels} relationship ends; {loser.chron} chronicle links",
                            "lost_on_delete": ("MAP STORY " + ",".join(loser.stories)) if loser.stories else "",
                            "merge_command": merge_command(surv.id, loser.id)})
        return out

    def names(self) -> list[dict[str, Any]]:
        conv = conventions(self.rows.values())
        issues = name_issues(self.rows.values(), conv)
        write_csv(self.out / "names.csv", issues, NAME_FIELDS)
        self.results["name_conventions"] = {k: dict(v) for k, v in conv.items()}
        (self.out / "name-conventions.json").write_text(json.dumps(self.results["name_conventions"], indent=1))
        self.results["names"] = issues
        self.log(f"C5 names: {len(issues)} issues, {sum(1 for i in issues if i['apply'])} mechanical renames")
        return issues

    def text(self) -> list[dict[str, Any]]:
        flags = text_flags(self.rows.values())
        flags.sort(key=lambda f: (f["check"], {"high": 0, "medium": 1, "low": 2}[f["severity"]], f["name"]))
        write_csv(self.out / "text-flags.csv", flags, TEXT_FIELDS)
        self.results["text"] = flags
        self.log(f"C6 text flags: {Counter(f['check'] for f in flags)}")
        return flags

    def relations(self) -> list[dict[str, Any]]:
        flags = relation_flags(self.rows, load_relationships(self.conn))
        flags.sort(key=lambda f: (f["check"], {"high": 0, "medium": 1, "low": 2}[f["severity"]], f["relationship_type"]))
        write_csv(self.out / "relation-flags.csv", flags, REL_FIELDS)
        self.results["relations"] = flags
        self.log(f"C7 relation flags: {Counter(f['check'] for f in flags)}")
        return flags

    def places(self) -> list[dict[str, Any]]:
        """C2b: same-name places (report; verified proposals become pins)."""
        from pipeline.audit.places import check_places

        held = {r.qid: r.id for r in self.rows.values() if r.qid}
        flags = check_places(self.rows, self.client, self.closure, held)
        flags.sort(key=lambda f: ({"pin_candidate": 0, "duplicate": 1, "ambiguous": 2, "flag": 3}[f["action"]], f["name"]))
        write_csv(self.out / "place-flags.csv", flags, PLACE_FIELDS)
        self.results["places"] = flags
        self.log(f"C2b place namesakes: {Counter(f['action'] for f in flags)}")
        return flags

    def stories(self) -> list[dict[str, Any]]:
        from pipeline.audit.stories import check_all

        refs = check_all(self.client, self.closure, self.rows)
        write_csv(self.out / "story-refs.csv", refs, STORY_FIELDS)
        self.results["stories"] = refs
        self.log(f"C8 story refs: {len(refs)}, with problems {sum(1 for r in refs if r['problems'])}")
        return refs

    # ── C9 ───────────────────────────────────────────────────────────────────
    def plan_changes(self) -> list[dict[str, Any]]:
        changes: list[dict[str, Any]] = []
        for f in self.results.get("qid_flags", []):
            act = f.get("action", "")
            ev = f"WD {f['qid']} = {f.get('wd_label', '')!r} ({f.get('wd_description', '')}); issues: {f['issues']}"
            if act == "set_qid":
                changes.append({"fix": "set_qid", "id": f["entity_id"], "old_qid": f["qid"],
                                "new_qid": f["proposed_qid"], "reason": f["rule"],
                                "evidence": ev + f"; C3 unique match {f['proposed_qid']} {f.get('proposed_label', '')}"})
            elif act == "set_qid(redirect)":
                changes.append({"fix": "set_qid", "id": f["entity_id"], "old_qid": f["qid"],
                                "new_qid": f["proposed_qid"], "reason": "redirect resolved",
                                "evidence": f"Wikidata redirects {f['qid']} to {f['proposed_qid']}"})
            elif act.startswith("clear_qid"):
                changes.append({"fix": "clear_qid", "id": f["entity_id"], "old_qid": f["qid"], "new_qid": None,
                                "reason": f["rule"], "evidence": ev + f"; C3: {f.get('resolution')}",
                                "flag": "qid_cleared" + (":duplicate" if "duplicate_of" in act else "")})
            elif act.startswith("needs_review"):
                changes.append({"fix": "needs_review", "id": f["entity_id"], "reason": f["rule"], "evidence": ev,
                                "flag": "qid_suspect" + (":duplicate" if "duplicate_of" in act else "")})
        changes.extend(self._pins())
        for n in self.results.get("names", []):
            if n["apply"]:
                old, new = n["name"], n["proposed_name"]
                from pipeline.agent.tools.disambiguation import names_equal
                changes.append({"fix": "rename", "id": n["entity_id"], "old_name": old, "new_name": new,
                                "add_alias": not names_equal(old, new), "reason": "; ".join(n["issues"]),
                                "evidence": "C5 mechanical rename (dominant convention)"})
        # one change per (fix, id): pins override the automatic decision
        seen: dict[tuple[str, str], dict[str, Any]] = {}
        for ch in changes:
            key = ("qid" if ch["fix"] in ("set_qid", "clear_qid", "needs_review") else ch["fix"], ch["id"])
            if ch.get("pinned") or key not in seen:
                seen[key] = ch
        return list(seen.values())

    def _pins(self) -> list[dict[str, Any]]:
        """Hand-verified QID corrections in pins.csv (entity_id, old_qid, new_qid, alias, reason, evidence).

        An empty new_qid clears the QID. A pin is skipped (and noted) when its
        new QID is already on another row: that is a merge, not a QID fix."""
        path = self.out / "pins.csv"
        if not path.exists():
            return []
        held = {r.qid: r.id for r in self.rows.values() if r.qid}
        out = []
        with path.open(encoding="utf-8") as fh:
            for p in csv.DictReader(fh):
                new = (p.get("new_qid") or "").strip() or None
                if new and held.get(new, p["entity_id"]) != p["entity_id"]:
                    self.results.setdefault("notes", []).append(
                        f"pin {p['entity_id']} -> {new} skipped: {new} is on row {held[new]} (merge instead)")
                    continue
                out.append({"fix": "set_qid" if new else "clear_qid", "id": p["entity_id"],
                            "old_qid": (p.get("old_qid") or "").strip() or None, "new_qid": new,
                            "reason": "pin: " + p["reason"], "evidence": p["evidence"], "pinned": True,
                            "flag": None if new else "qid_cleared"})
                if (p.get("alias") or "").strip():
                    out.append({"fix": "add_alias", "id": p["entity_id"], "alias": p["alias"].strip(),
                                "reason": "pin: label of the pinned QID", "evidence": p["evidence"], "pinned": True})
        return out


def _settle_collisions(flags: list[dict[str, Any]], rows: dict[str, Any], by_qid: dict[str, list[str]]) -> None:
    """No two rows may end up with one QID. A redirect target already on
    another row, or a C3 winner that two rows both resolve to, is a duplicate
    for the user, not a set_qid: the row named exactly like the QID keeps the
    set_qid when there is exactly one such row, the others become duplicates."""
    def demote(f: dict[str, Any], holders: list[str]) -> None:
        verb = "clear_qid" if f["action"] == "set_qid" and f["rule"][:2] in CLEAR_RULES else "needs_review"
        f["action"] = f"{verb}+duplicate_of:{','.join(holders)}"

    for f in flags:
        if f.get("action") == "set_qid(redirect)":
            holders = [h for h in by_qid.get(f["proposed_qid"], []) if h != f["entity_id"]]
            if holders:
                demote(f, holders)
    targets: dict[str, list[dict[str, Any]]] = {}
    for f in flags:
        if f.get("action") == "set_qid":
            targets.setdefault(f["proposed_qid"], []).append(f)
    for qid, group in targets.items():
        if len(group) < 2:
            continue
        label = (group[0].get("proposed_label") or "").split(" — ")[0]
        exact = [f for f in group if names_equal(rows[f["entity_id"]].name, label)]
        keep = exact[0] if len(exact) == 1 else None
        for f in group:
            if f is not keep:
                demote(f, [keep["entity_id"]] if keep else [g["entity_id"] for g in group if g is not f])
