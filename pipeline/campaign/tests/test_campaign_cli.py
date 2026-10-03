import json
import os
import subprocess

import pytest

from pipeline.campaign import measure, paths, wiki
from pipeline.campaign.tests.conftest import RUN_ID, SLUG, read


# ── paths ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("arg", [
    SLUG, RUN_ID, f"{SLUG}.txt", f"output/campaign/extractions/{RUN_ID}/candidates.json",
    f"output/campaign/extractions/{RUN_ID}/", f"output/transcripts/campaign/{SLUG}.txt",
])
def test_slug_resolution(arg):
    assert paths.slug_of(arg) == SLUG
    assert paths.run_id_of(arg) == RUN_ID


def test_parse_slug_and_era():
    assert paths.parse_slug("e04__middle-east__achaemenid-persian-empire") == ("e04", "middle-east", "achaemenid-persian-empire")
    assert paths.parse_slug("zz-test__tmp") == ("?", "?", "zz-test__tmp")
    assert paths.era_of(RUN_ID) == "e08"


def test_manifests_dir_follows_agent_config(root):
    assert paths.manifests_dir() == root / "agent_runs"


# ── status ──────────────────────────────────────────────────────────────────

def _manifest(root, run_id, errors):
    d = root / "agent_runs" / run_id
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(json.dumps({"run_id": run_id, "errors_count": len(errors), "errors": errors}))
    return d / "manifest.json"


def test_status_rows_and_footer(invoke, built, root):
    tdir = root / "output/transcripts/campaign"
    (tdir / "e04__aegean__pending.txt").write_text("\n".join(f"{i}. fact {i} BCE" for i in range(1, 71)))
    other = root / "output/campaign/extractions/campaign_e04__aegean__failed"
    other.mkdir(parents=True)
    (other / "candidates.json").write_text(json.dumps({"run_id": "campaign_e04__aegean__failed",
                                                       "candidate_entities": [{"label": "A"}]}))
    _manifest(root, "campaign_e04__aegean__failed", [{"node": "commit_writer"}])
    m = _manifest(root, RUN_ID, [])
    os.utime(m, (built.stat().st_mtime + 10,) * 2)
    invoke("review-record", SLUG, "--verdict", "PASS", "--model", "sonnet")

    res = invoke("status")
    assert res.exit_code == 0
    lines = res.output.splitlines()
    assert lines[0].split() == ["slug", "facts", "ev", "ent", "rel", "r/e", "review", "ingest"]
    row = {line.split()[0]: line.split() for line in lines[1:4]}
    assert row[SLUG] == [SLUG, "3", "3", "5", "7", "1.40", "PASS", "clean"]
    assert row["e04__aegean__pending"] == ["e04__aegean__pending", "70", "-", "-", "-", "-", "-", "-"]
    assert row["e04__aegean__failed"] == ["e04__aegean__failed", "-", "0", "1", "0", "0.00", "-", "failed"]
    assert "runs=3 transcripts=2 handoffs=2 facts=73" in res.output
    assert "ingest clean=1 failed=1 none=1" in res.output
    assert "caucasus" in res.output and "aegean" in res.output
    assert "stale" not in res.output


def test_status_filters_stale_and_json(invoke, built, root):
    m = _manifest(root, RUN_ID, [])
    os.utime(m, (built.stat().st_mtime - 10,) * 2)
    res = invoke("status")
    assert f"re-ingest with --refresh): {SLUG}" in res.output
    assert invoke("status", "--era", "e04").output.startswith("slug")
    assert SLUG not in invoke("status", "--era", "e04").output
    res = invoke("status", "--thin")
    assert "thin: 1 of 1 runs" in res.output
    data = json.loads(invoke("status", "--json").output)
    run = data["runs"][0]
    assert run["slug"] == SLUG and run["facts"] == 3 and run["stale"] is True and run["thin"] is True
    assert data["totals"]["ingest"] == {"clean": 1, "failed": 0, "none": 0}
    assert data["grid"] == {"caucasus": {"e08": 1}}


def test_status_validate_column(invoke, built):
    res = invoke("status", "--validate")
    assert res.output.splitlines()[1].split()[-1] == "OK"
    assert "valid OK=1 FAIL=0" in res.output


# ── review-record / validate-all ────────────────────────────────────────────

def test_review_record_appends_history(invoke, built):
    res = invoke("review-record", RUN_ID, "--verdict", "FIXED", "--model", "opus",
                 "--issue", "orphan Tamar", "--issue", "density low", "--fixed", "added 3 relations")
    assert res.exit_code == 0
    assert "FIXED by opus (issues=2 fixed=1 history=1)" in res.output
    invoke("review-record", SLUG, "--verdict", "PASS", "--model", "sonnet")
    data = read(built.with_name("review.json"))
    assert [h["verdict"] for h in data["history"]] == ["FIXED", "PASS"]
    assert data["history"][0]["issues"] == ["orphan Tamar", "density low"]
    assert data["history"][0]["fixed"] == ["added 3 relations"]
    assert data["history"][1]["timestamp"].endswith("+00:00")


def test_review_record_rejects_unknown_run_and_verdict(invoke, root):
    assert invoke("review-record", "e01__x__y", "--verdict", "PASS", "--model", "m").exit_code == 1
    assert invoke("review-record", SLUG, "--verdict", "MAYBE", "--model", "m").exit_code == 2


def test_validate_all(invoke, built, root):
    res = invoke("validate-all")
    assert res.exit_code == 0 and res.output.strip() == "1 ok, 0 failed"
    bad = root / "output/campaign/extractions/campaign_e04__aegean__bad"
    bad.mkdir(parents=True)
    (bad / "candidates.json").write_text(json.dumps({
        "run_id": "campaign_e04__aegean__bad", "summaries_precomputed": False,
        "candidate_entities": [{"label": "A", "entity_type": "person"}],
        "candidate_relations": [{"source_label": "A", "target_label": "B", "relationship_type": "rules"}],
    }))
    res = invoke("validate-all")
    assert res.exit_code == 1
    assert "FAIL campaign_e04__aegean__bad: 1 error(s)" in res.output
    assert "relation endpoint 'B' has no extracted entity" in res.output
    assert res.output.strip().endswith("1 ok, 1 failed")
    assert invoke("validate-all", "--era", "e08").exit_code == 0


# ── types ───────────────────────────────────────────────────────────────────

def test_types_lists_code_sets(invoke):
    out = invoke("types").output
    assert out.splitlines()[0].startswith("entity POLITY: ")
    assert " capital_of " in out and "event_battle" in out
    assert "relation direction" not in out
    out = invoke("types", "--relations-help").output
    assert "  capital_of: City → Political entity" in out


# ── wiki ────────────────────────────────────────────────────────────────────

EXTRACT = """The Battle of Manzikert was fought on 26 August 1071. It was a disaster.
About 5,000 troops marched. Alp Arslan led the Seljuks.

== Background ==
In 1068, Romanos IV took power. He campaigned widely.

=== Prelude ===
The army reached Theodosiopolis in June 1071.

== Aftermath ==
Turks entered Anatolia in the 11th century. Nobody cared.

== References ==
Smith, John (1999). A book.
"""


@pytest.fixture
def fake_http(root, monkeypatch):
    calls = []

    def fake(params):
        calls.append(params)
        if params.get("list") == "search":
            return {"query": {"search": [
                {"title": "Battle of Manzikert", "snippet": 'The <span class="searchmatch">Battle</span> &amp; more'}]}}
        if params["titles"] == "Nope":
            return {"query": {"pages": [{"title": "Nope", "missing": True}]}}
        return {"query": {"pages": [{"title": "Battle of Manzikert", "extract": EXTRACT}]}}

    monkeypatch.setattr(wiki, "_http_get", fake)
    return calls


def test_wiki_plain_cached_and_skips_references(invoke, fake_http, root):
    res = invoke("wiki", "Manzikert")
    assert res.exit_code == 0
    assert "=== Manzikert (-> Battle of Manzikert) ===" in res.output
    assert "## Background" in res.output and "Smith, John" not in res.output
    invoke("wiki", "Manzikert")
    assert len(fake_http) == 1
    assert list((root / "output/campaign/cache/wiki").glob("page_*.json"))


def test_wiki_dated_section_and_truncation(invoke, fake_http):
    out = invoke("wiki", "--dated", "Battle of Manzikert").output
    assert "- The Battle of Manzikert was fought on 26 August 1071." in out
    assert "5,000" not in out and "Nobody cared" not in out and "He campaigned" not in out
    assert "## Aftermath\n- Turks entered Anatolia in the 11th century." in out
    out = invoke("wiki", "--section", "background", "Battle of Manzikert").output
    assert "Romanos IV" in out and "Theodosiopolis" in out and "Anatolia" not in out
    out = invoke("wiki", "--max-chars", "80", "Battle of Manzikert").output
    assert out.rstrip().endswith("[truncated]")


def test_wiki_missing_page_exits_1(invoke, fake_http):
    res = invoke("wiki", "Nope")
    assert res.exit_code == 1 and "no such page" in res.output


def test_wiki_search(invoke, fake_http):
    res = invoke("wiki-search", "manzikert", "battle", "--limit", "3")
    assert res.output.strip() == "Battle of Manzikert — The Battle & more"
    assert fake_http[0]["srsearch"] == "manzikert battle" and fake_http[0]["srlimit"] == "3"


def test_sentence_split_keeps_circa():
    assert wiki.split_sentences("Founded c. 750 BCE by Greeks. Later it grew.") == [
        "Founded c. 750 BCE by Greeks.", "Later it grew."]


# ── measure ─────────────────────────────────────────────────────────────────

def test_db_setting_resolution(root, monkeypatch):
    monkeypatch.delenv("POSTGRES_USER", raising=False)
    (root / "docker").mkdir()
    (root / "docker/docker-compose.yml").write_text("POSTGRES_USER: '${POSTGRES_USER:-from-compose}'\n")
    assert measure.db_setting("POSTGRES_USER") == "from-compose"
    assert measure.db_setting("POSTGRES_DB") == "history-mapped"
    (root / ".env").write_text("POSTGRES_USER=from-env-file\n")
    assert measure.db_setting("POSTGRES_USER") == "from-env-file"
    monkeypatch.setenv("POSTGRES_USER", "from-env")
    assert measure.db_setting("POSTGRES_USER") == "from-env"


def test_measure_exits_2_when_db_down(invoke, monkeypatch):
    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 0, stdout="redis\n", stderr="")

    monkeypatch.setattr(measure.subprocess, "run", fake_run)
    res = invoke("measure")
    assert res.exit_code == 2
    assert res.output.startswith("measure: db service is not running")


def test_measure_report(invoke, monkeypatch):
    out = (
        "entities|200\nqid|190|200\ntype|person|80\ntype|city|40\n"
        "geo|EVENT|60|10|50|55\ngeo|PLACE|40|30|38|39\njan1_ranges|0\njan1_relations|2\n"
        "orphans|20|200\nrelations|300\nchronicles|5|5\nofftax|0\n"
    )
    seen = []

    def fake_run(cmd, **kw):
        seen.append(cmd)
        if "ps" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="app\ndb\n", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

    monkeypatch.setattr(measure.subprocess, "run", fake_run)
    res = invoke("measure")
    assert res.exit_code == 0, res.output
    assert "-U" in seen[1] and "exec" in seen[1]
    text = res.output
    assert "with QID                  190/200 (95%)" in text
    assert "orphan entities           20/200 (10%)" in text
    assert "PLACE     39/40 (98%)  georef=30 located=38   (target >80%)" in text
    assert "ranges=0 relations=2" in text
    assert "top entity types: person=80, city=40" in text
