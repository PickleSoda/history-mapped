#!/usr/bin/env python3
"""Create the atlas entities that map stories link but the DB lacks.

Run from the repo root with the Docker stack up, through the pipeline venv:

    P="scripts/capped.sh pipeline/.venv/bin/python3 scripts/map-story-missing-entities.py"
    $P missing [--tracked-only] [--spec-stub api/storage/app/pipeline/<batch>/spec.json]
    $P build   --batch <batch>          # spec.json -> entities.jsonl + relations.jsonl
    $P import  --batch <batch>          # dedup check, import, relations, timeline, images, tags:sync
    $P csv     --batch <batch> [--out output/audit/<audit>/created-entities.csv]

1. `missing` collects every `"wikidata"` Q-id in api/resources/map-stories/*.json,
   lists those no `entities.wikidata_id` matches, and prints same-name rows
   (name or alias equal, trigram similarity >= 0.5, or containing the
   last word of the story's name, e.g. a surname). A same-name
   row that is the same thing must be reported, not duplicated: leave it out of
   the spec. `--spec-stub` writes a spec skeleton with the story context.
2. Fill in api/storage/app/pipeline/<batch>/spec.json by hand, one object per Q-id:
   {"Q123": {"name", "type" (entity_type), "start", "end" (year strings, "-480",
   "1815-06-18", or null), "date_confidence", "duration" (point|period|ongoing|
   uncertain), "attributes" (subtype per docs/entity-model/entity-specification.md,
   gender, date_raw…), "aliases", "story" (slug), "summary" (one sentence),
   "location" ("p625" = Wikidata's own point, [lon, lat] = a hand-set point, or
   null), "relations": [{"type": "participated_in", "target": "Q48314",
   "target_name": "Battle of Waterloo", "date": "1815", "description": "…"}]}}
   Confirm facts with `python -m pipeline.map_stories research --qids …` (cached).
3. `build` adds Wikidata coordinates and the enwiki citation (cached
   wbgetentities) and writes the docs/schemas/pipeline-entity-record.md JSONL.
4. `import` runs the importer's own dedup lookup first and stops if any record
   would merge into an existing row, then pipeline:import (created_by
   `pipeline:<batch>`), pipeline:import-relations, timeline:rebuild per entity,
   entity:fetch-images for the batch only, and tags:sync. Embeddings (remote
   OpenAI) are left to `pipeline:embeddings --pending`.
5. `csv` appends the batch's rows (qid, entity_id, name, type, story).
Then run `php artisan map-stories:relink`.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
COMPOSE = ["docker", "compose", "-f", str(ROOT / "docker/docker-compose.yml"), "exec", "-T"]
STORIES = ROOT / "api/resources/map-stories"
BATCHES = ROOT / "api/storage/app/pipeline"
CONTAINER_BATCHES = "/var/www/html/storage/app/pipeline"
GROUP = {
    "political_entity": "POLITY", "dynasty": "POLITY", "person": "POLITY", "military_unit": "POLITY",
    "diplomatic_relationship": "POLITY", "social_class": "POLITY",
    "city": "PLACE", "infrastructure_monument": "PLACE", "extraction_infra": "PLACE", "educational_institution": "PLACE",
    "event_war": "EVENT", "event_battle": "EVENT", "event_treaty": "EVENT", "event_rebellion": "EVENT",
    "event_natural_disaster": "EVENT", "event_tech_adoption": "EVENT", "event_legal_reform": "EVENT",
    "migration": "EVENT", "epidemic_disease": "EVENT",
    "trade_route": "ECONOMY", "natural_resource": "ECONOMY", "currency_monetary_system": "ECONOMY",
    "cultural_work": "CULTURE", "intellectual_movement": "CULTURE", "archaeological_culture": "CULTURE",
    "language": "CULTURE", "religious_text": "CULTURE", "legal_code": "CULTURE",
    "religious_movement": "CULTURE", "technology": "CULTURE",
}


def sql(query: str) -> list[list[str]]:
    out = subprocess.run(COMPOSE + ["db", "psql", "-U", "history-mapped", "history-mapped", "-At", "-F", "\t", "-c", query],
                         check=True, capture_output=True, text=True).stdout
    return [line.split("\t") for line in out.splitlines() if line]


def lit(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def artisan(*args: str) -> str:
    res = subprocess.run(COMPOSE + ["app", "php", "artisan", *args], capture_output=True, text=True)
    print(f"$ artisan {' '.join(args)[:140]}\n{res.stdout.strip()[-1500:]}{res.stderr.strip()[-800:]}")
    if res.returncode != 0:
        sys.exit(f"artisan {args[0]} failed ({res.returncode})")
    return res.stdout


def story_refs(tracked_only: bool) -> list[tuple[str, str, str, str]]:
    """(qid, story slug, JSON path, name) for every `"wikidata"` value."""
    if tracked_only:
        files = subprocess.run(["git", "ls-files", "api/resources/map-stories/*.json"], cwd=ROOT,
                               check=True, capture_output=True, text=True).stdout.split()
        files = [str(ROOT / f) for f in files]
    else:
        files = sorted(glob.glob(str(STORIES / "*.json")))
    refs: list[tuple[str, str, str, str]] = []

    def walk(o, path: str, slug: str) -> None:
        if isinstance(o, dict):
            q = o.get("wikidata")
            if isinstance(q, str) and q.startswith("Q"):
                refs.append((q, slug, path, str(o.get("name") or o.get("label") or "")))
            for k, v in o.items():
                walk(v, f"{path}.{k}", slug)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]", slug)

    for f in files:
        if not f.endswith(".build-hashes.json"):
            walk(json.loads(Path(f).read_text()), "", Path(f).stem)
    return refs


def cmd_missing(args) -> None:
    refs = story_refs(args.tracked_only)
    qids = sorted({r[0] for r in refs})
    present = {r[0] for r in sql(f"select distinct wikidata_id from entities where wikidata_id in ({','.join(map(lit, qids))})")}
    missing = [q for q in qids if q not in present]
    print(f"{len(qids)} story Q-ids, {len(missing)} without an entity")
    stub = {}
    for q in missing:
        uses = [r for r in refs if r[0] == q]
        name = uses[0][3]
        print(f"\n{q}  {name}  [{', '.join(sorted({u[1] for u in uses}))}]  {uses[0][2]}")
        words = [w.strip(",.()") for w in name.split() if len(w.strip(",.()")) >= 4]
        last = lit("%" + words[-1] + "%") if words else "''"
        rows = sql(f"""select e.entity_id, e.name, e.entity_type, coalesce(e.wikidata_id, '-'), left(coalesce(e.summary, ''), 90)
            from entities e where e.entity_id in (select entity_id from entities where lower(name) = lower({lit(name)})
                or similarity(name, {lit(name)}) >= 0.5 or name ilike {last}
              union select entity_id from entity_aliases where lower(name) = lower({lit(name)}) or name ilike {last})
            order by similarity(e.name, {lit(name)}) desc limit 6""")
        for r in rows:
            print("   same-name row: " + " | ".join(r))
        stub[q] = {"name": name, "type": None, "start": None, "end": None, "date_confidence": None, "duration": None,
                   "attributes": {}, "aliases": [], "story": uses[0][1], "summary": None, "location": None, "relations": [],
                   "_uses": [f"{u[1]}{u[2]}" for u in uses], "_same_name_rows": [" | ".join(r) for r in rows]}
    if args.spec_stub and stub:
        Path(args.spec_stub).parent.mkdir(parents=True, exist_ok=True)
        Path(args.spec_stub).write_text(json.dumps(stub, indent=1, ensure_ascii=False) + "\n")
        print(f"\nspec stub -> {args.spec_stub}")


def cmd_build(args) -> None:
    from pipeline.map_stories.net import wd_entities

    out = BATCHES / args.batch
    spec = {q: s for q, s in json.loads((out / "spec.json").read_text()).items() if not q.startswith("_")}
    wd = wd_entities(list(spec))
    entities, relations = [], []
    for q, s in spec.items():
        row = wd.get(q) or {}
        if not row or row.get("missing"):
            sys.exit(f"{q} is not a Wikidata item")
        rec = {"name": s["name"], "entity_type": s["type"], "entity_group": GROUP[s["type"]], "wikidata_id": q,
               "summary": s["summary"], "alternative_names": s.get("aliases", []),
               "temporal_start": s.get("start"), "temporal_end": s.get("end"), "attributes": s.get("attributes", {}),
               "verification_status": "pipeline_draft", "confidence": "medium",
               "source_citations": [{"source_type": "reference", "title": f"Wikidata:{q}",
                                     "url": f"https://www.wikidata.org/wiki/{q}", "reliability": "reference"}]}
        if row.get("enwiki"):
            rec["source_citations"].append({"source_type": "reference", "title": f"Wikipedia: {row['enwiki']}",
                                            "url": "https://en.wikipedia.org/wiki/" + row["enwiki"].replace(" ", "_"),
                                            "reliability": "reference"})
        if s.get("start") or s.get("end"):
            rec["date_method"] = "source_database"
            rec["date_confidence"] = s.get("date_confidence") or "medium"
        if s.get("duration"):
            rec["duration_type"] = s["duration"]
        loc = s.get("location")
        if loc == "p625":
            if not row.get("coord"):
                sys.exit(f"{q} has no P625; give [lon, lat] or null")
            rec.update(location_method="wikidata", location_confidence="high", _geo_resolution={
                "status": "matched",
                "geo_ref": {"provider": "wikidata", "external_type": "qid", "external_id": q, "match_role": "primary",
                            "retrieval_method": "rest", "match_score": 1.0, "external_tags": {},
                            "source_meta": {"source": "wikidata_p625"}},
                "provenance": {"resolver": "wikidata_coords", "query": q, "candidates": 1, "reason": "own_p625"},
                "geometry": {"type": "Point", "coordinates": row["coord"]}})
        elif isinstance(loc, list):
            rec.update(location_method="human_assigned", location_confidence="medium",
                       geojson={"type": "Point", "coordinates": loc})
        entities.append(rec)
        for r in s.get("relations", []):
            relations.append({"source_name": s["name"], "target_name": r["target_name"], "relationship_type": r["type"],
                              "start_date": r.get("date"), "end_date": r.get("date"),
                              "description": r.get("description") or f"{s['name']} {r['type'].replace('_', ' ')} {r['target_name']}.",
                              "source_citations": {"created_by": args.batch, "story": s["story"]},
                              "source_wikidata_id": q, "target_wikidata_id": r["target"]})
    (out / "entities.jsonl").write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entities))
    (out / "relations.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in relations))
    (out / "stories.json").write_text(json.dumps({q: s["story"] for q, s in spec.items()}, indent=1) + "\n")
    print(f"{len(entities)} entities, {len(relations)} relations -> {out}")


def cmd_import(args) -> None:
    path = f"{CONTAINER_BATCHES}/{args.batch}"
    check = artisan("tinker", "--execute", f"""foreach (file("{path}/entities.jsonl") as $l) {{ $r = json_decode($l, true);
        $x = (new App\\Jobs\\ImportEntityJob($r, "dedup-check"))->findExisting($r);
        echo "DEDUP ", $r["wikidata_id"], " ", $x["entity"]?->entity_id ?? "-", " ", $x["rejected_qid"] ?? "-", " ", $x["namesake"] ?? "-", PHP_EOL; }}""")
    clashes = [line for line in check.splitlines() if line.startswith("DEDUP") and line.split()[2:] != ["-", "-", "-"]]
    if clashes:
        sys.exit("would merge into or clash with existing rows, fix the spec first:\n" + "\n".join(clashes))
    artisan("pipeline:import", f"{path}/entities.jsonl", "--sync", "--skip-relationships", "--skip-images", f"--batch-id={args.batch}")
    if (BATCHES / args.batch / "relations.jsonl").stat().st_size:
        artisan("pipeline:import-relations", f"{path}/relations.jsonl", f"--batch-id={args.batch}")
    ids = [r[0] for r in sql(f"select entity_id from entities where created_by = {lit('pipeline:' + args.batch)}")]
    for i in ids:
        artisan("timeline:rebuild", i)
    artisan("entity:fetch-images", *[f"--entity-id={i}" for i in ids])
    artisan("tags:sync")


def cmd_csv(args) -> None:
    stories = json.loads((BATCHES / args.batch / "stories.json").read_text())
    rows = sql(f"select wikidata_id, entity_id, name, entity_type from entities where created_by = {lit('pipeline:' + args.batch)} order by name")
    out = Path(args.out) if Path(args.out).is_absolute() else ROOT / args.out
    exists = out.exists()
    seen = {r["qid"] for r in csv.DictReader(out.open())} if exists else set()
    with out.open("a", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["qid", "entity_id", "name", "type", "story"])
        added = 0
        for q, i, n, t in rows:
            if q not in seen:
                w.writerow([q, i, n, t, stories.get(q, "")])
                added += 1
    print(f"{added} rows appended to {out}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("missing")
    m.add_argument("--tracked-only", action="store_true", help="only story files committed to git")
    m.add_argument("--spec-stub", help="write a spec skeleton for the missing Q-ids here")
    for name in ("build", "import", "csv"):
        s = sub.add_parser(name)
        s.add_argument("--batch", required=True, help="batch id; files live in api/storage/app/pipeline/<batch>/")
        if name == "csv":
            s.add_argument("--out", default="output/audit/identity-20261031/created-entities.csv")
    args = p.parse_args()
    {"missing": cmd_missing, "build": cmd_build, "import": cmd_import, "csv": cmd_csv}[args.cmd](args)


if __name__ == "__main__":
    main()
