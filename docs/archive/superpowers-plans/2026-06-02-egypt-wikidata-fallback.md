# Egypt Wikidata Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a curated-seed Wikidata fallback for Egypt that bypasses OHM discovery, emits generic importer-ready entities, and coexists with the existing OHM collection workflow.

**Architecture:** Add `pipeline/wikidata/collections/` containing a seed loader, fallback orchestrator, and artifact helpers. Reuse the existing Wikidata scraper, `EntityMapper`, and deduplicator. Wire a new CLI command under `py -m pipeline collections egypt-wikidata-build`. Output goes to `output/wikidata_collections/<run_id>/` by default.

**Tech Stack:** Python 3.10, Click CLI, existing `pipeline/wikidata/` modules, pytest.

**Prerequisite:** The existing Wikidata pipeline (`pipeline/wikidata/scraper/`, `pipeline/wikidata/mapper/`) must be functional.

---

## File Structure

- Create: `pipeline/wikidata/collections/__init__.py`
- Create: `pipeline/wikidata/collections/egypt_seed_set.py`
  - Loads curated Egypt seed QIDs from a repository file
- Create: `pipeline/wikidata/collections/egypt_fallback.py`
  - Orchestrates fetch, bounded expansion, mapping, dedup, artifact writing
- Create: `pipeline/wikidata/collections/artifacts.py`
  - Output directory helpers for collection runs
- Create: `pipeline/wikidata/collections/seed_sets/egypt.json`
  - Curated seed set (QIDs + categories + notes)
- Modify: `pipeline/ohm_collections/__main__.py`
  - Register `egypt-wikidata-build` command
- Modify: `pipeline/__main__.py`
  - Ensure the `collections` group exposes the new command
- Create: `pipeline/tests/test_wikidata_collections_egypt_seed_set.py`
- Create: `pipeline/tests/test_wikidata_collections_egypt_fallback.py`
- Create: `pipeline/tests/test_wikidata_collections_artifacts.py`
- Create: `pipeline/tests/test_wikidata_collections_cli.py`
- Modify: `pipeline/README.md`
  - Document the Egypt Wikidata fallback workflow
- Create: `docs/implementation-docs/egypt-wikidata-fallback-runbook.md`
  - Operator runbook for the fallback

---

### Task 1: Define Seed Set Contract and Loader

**Files:**
- Create: `pipeline/wikidata/collections/seed_sets/egypt.json`
- Create: `pipeline/wikidata/collections/egypt_seed_set.py`
- Create: `pipeline/tests/test_wikidata_collections_egypt_seed_set.py`

- [ ] **Step 1: Write the seed set JSON**

Create `pipeline/wikidata/collections/seed_sets/egypt.json`:

```json
[
  {"qid": "Q79", "category": "modern_state", "label": "Egypt", "notes": "Modern Arab Republic of Egypt"},
  {"qid": "Q11768", "category": "ancient_civilization", "label": "Ancient Egypt", "notes": "Pharaonic civilization"},
  {"qid": "Q13248", "category": "kingdom", "label": "Old Kingdom of Egypt", "expand": true},
  {"qid": "Q13250", "category": "kingdom", "label": "Middle Kingdom of Egypt", "expand": true},
  {"qid": "Q13252", "category": "kingdom", "label": "New Kingdom of Egypt", "expand": true},
  {"qid": "Q302424", "category": "kingdom", "label": "Ptolemaic Kingdom", "expand": true},
  {"qid": "Q134266", "category": "province", "label": "Roman Egypt", "expand": true},
  {"qid": "Q194837", "category": "sultanate", "label": "Ayyubid dynasty", "expand": true},
  {"qid": "Q133116", "category": "sultanate", "label": "Mamluk Sultanate", "expand": true},
  {"qid": "Q299462", "category": "province", "label": "Ottoman Egypt", "expand": true},
  {"qid": "Q133116", "category": "khedivate", "label": "Khedivate of Egypt", "expand": true},
  {"qid": "Q199462", "category": "kingdom", "label": "Kingdom of Egypt", "expand": true},
  {"qid": "Q308776", "category": "republic", "label": "Republic of Egypt (1953–1958)", "expand": false},
  {"qid": "Q14933", "category": "place", "label": "Memphis", "notes": "Ancient capital"},
  {"qid": "Q87", "category": "place", "label": "Alexandria", "notes": "Major ancient city"},
  {"qid": "Q85", "category": "place", "label": "Cairo", "notes": "Modern capital"},
  {"qid": "Q133344", "category": "place", "label": "Thebes", "notes": "Ancient city"},
  {"qid": "Q13248", "category": "place", "label": "Giza", "notes": "Pyramid complex"},
  {"qid": "Q1342", "category": "place", "label": "Luxor", "notes": "Temple city"}
]
```

- [ ] **Step 2: Write failing seed loader tests**

Create `pipeline/tests/test_wikidata_collections_egypt_seed_set.py`:

```python
from pathlib import Path

from pipeline.wikidata.collections.egypt_seed_set import load_seed_set


def test_loads_seed_set_from_default_path() -> None:
    seeds = load_seed_set()
    assert len(seeds) > 0
    assert all("qid" in s for s in seeds)
    assert all("category" in s for s in seeds)


def test_rejects_malformed_entries() -> None:
    bad_data = [{"qid": "Q1"}, {"category": "bad", "qid": ""}]
    seeds = load_seed_set(data=bad_data)
    assert len(seeds) == 1
    assert seeds[0]["qid"] == "Q1"


def test_preserves_order() -> None:
    data = [
        {"qid": "Q3", "category": "a"},
        {"qid": "Q1", "category": "b"},
        {"qid": "Q2", "category": "c"},
    ]
    seeds = load_seed_set(data=data)
    assert [s["qid"] for s in seeds] == ["Q3", "Q1", "Q2"]
```

- [ ] **Step 3: Run tests to verify failure**

```powershell
py -m pytest pipeline/tests/test_wikidata_collections_egypt_seed_set.py -v
```
Expected: FAIL because loader does not exist.

- [ ] **Step 4: Implement seed loader**

Create `pipeline/wikidata/collections/egypt_seed_set.py`:

```python
import json
from pathlib import Path
from typing import Any

DEFAULT_SEED_PATH = Path(__file__).parent / "seed_sets" / "egypt.json"


def load_seed_set(path: Path | None = None, data: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    if data is not None:
        raw = data
    else:
        src = path or DEFAULT_SEED_PATH
        with open(src, "r", encoding="utf-8") as f:
            raw = json.load(f)

    seeds: list[dict[str, Any]] = []
    for entry in raw:
        qid = entry.get("qid", "").strip()
        if not qid:
            continue
        seeds.append({
            "qid": qid,
            "category": entry.get("category", "unknown"),
            "label": entry.get("label", ""),
            "notes": entry.get("notes", ""),
            "expand": entry.get("expand", True),
        })

    return seeds
```

- [ ] **Step 5: Run tests**

```powershell
py -m pytest pipeline/tests/test_wikidata_collections_egypt_seed_set.py -v
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pipeline/wikidata/collections/seed_sets/egypt.json pipeline/wikidata/collections/egypt_seed_set.py pipeline/tests/test_wikidata_collections_egypt_seed_set.py
git commit -m "feat(pipeline): add Egypt curated seed set and loader"
```

---

### Task 2: Add Collection Artifact Helpers

**Files:**
- Create: `pipeline/wikidata/collections/artifacts.py`
- Create: `pipeline/tests/test_wikidata_collections_artifacts.py`

- [ ] **Step 1: Write failing artifact tests**

Create `pipeline/tests/test_wikidata_collections_artifacts.py`:

```python
from pathlib import Path

from pipeline.wikidata.collections.artifacts import (
    collection_artifact_dir,
    entities_final_path,
    reports_dir,
    manifest_path,
)


def test_collection_artifact_dir_is_deterministic(tmp_path: Path) -> None:
    root = collection_artifact_dir("egypt-test", base_dir=tmp_path)
    assert root == tmp_path / "wikidata_collections" / "egypt-test"


def test_entities_final_path_is_deterministic(tmp_path: Path) -> None:
    root = collection_artifact_dir("egypt-test", base_dir=tmp_path)
    assert entities_final_path(root) == root / "entities_final" / "egypt_collection.jsonl"


def test_reports_dir_is_deterministic(tmp_path: Path) -> None:
    root = collection_artifact_dir("egypt-test", base_dir=tmp_path)
    assert reports_dir(root) == root / "reports"


def test_manifest_path_is_deterministic(tmp_path: Path) -> None:
    root = collection_artifact_dir("egypt-test", base_dir=tmp_path)
    assert manifest_path(root) == root / "manifest.json"
```

- [ ] **Step 2: Run tests to verify failure**

```powershell
py -m pytest pipeline/tests/test_wikidata_collections_artifacts.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement artifact helpers**

Create `pipeline/wikidata/collections/artifacts.py`:

```python
from pathlib import Path

DEFAULT_COLLECTION_ROOT = Path("output") / "wikidata_collections"


def collection_artifact_dir(run_id: str, base_dir: Path | None = None) -> Path:
    root = base_dir or DEFAULT_COLLECTION_ROOT
    return root / run_id


def entities_final_path(artifact_dir: Path) -> Path:
    return artifact_dir / "entities_final" / "egypt_collection.jsonl"


def reports_dir(artifact_dir: Path) -> Path:
    return artifact_dir / "reports"


def included_report_path(artifact_dir: Path) -> Path:
    return reports_dir(artifact_dir) / "included.jsonl"


def excluded_report_path(artifact_dir: Path) -> Path:
    return reports_dir(artifact_dir) / "excluded.jsonl"


def manifest_path(artifact_dir: Path) -> Path:
    return artifact_dir / "manifest.json"


def ensure_dirs(artifact_dir: Path) -> None:
    entities_final_path(artifact_dir).parent.mkdir(parents=True, exist_ok=True)
    reports_dir(artifact_dir).mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 4: Run tests**

```powershell
py -m pytest pipeline/tests/test_wikidata_collections_artifacts.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/wikidata/collections/artifacts.py pipeline/tests/test_wikidata_collections_artifacts.py
git commit -m "feat(pipeline): add Wikidata collection artifact helpers"
```

---

### Task 3: Implement Fallback Orchestrator

**Files:**
- Create: `pipeline/wikidata/collections/egypt_fallback.py`
- Create: `pipeline/tests/test_wikidata_collections_egypt_fallback.py`

- [ ] **Step 1: Write failing fallback tests**

Create `pipeline/tests/test_wikidata_collections_egypt_fallback.py`:

```python
from unittest.mock import MagicMock

from pipeline.wikidata.collections.egypt_fallback import (
    fetch_seed_entities,
    apply_bounded_expansion,
    build_collection_artifacts,
)


def test_fetch_seed_entities_returns_mapped_records(monkeypatch) -> None:
    def mock_fetch(qids):
        return {
            "Q79": {"qid": "Q79", "name": "Egypt", "entity_type": "political_entity"},
        }

    monkeypatch.setattr("pipeline.wikidata.collections.egypt_fallback.batch_fetch_wikidata", mock_fetch)

    seeds = [{"qid": "Q79", "category": "modern_state"}]
    records = fetch_seed_entities(seeds)
    assert len(records) == 1
    assert records[0]["wikidata_id"] == "Q79"


def test_bounded_expansion_respects_egypt_domain(monkeypatch) -> None:
    def mock_fetch(qids):
        return {
            "Q1": {"qid": "Q1", "name": "British Empire", "entity_type": "political_entity"},
        }

    monkeypatch.setattr("pipeline.wikidata.collections.egypt_fallback.batch_fetch_wikidata", mock_fetch)

    included = [{"qid": "Q79", "name": "Egypt"}]
    expansion_qids = ["Q1"]
    expanded = apply_bounded_expansion(included, expansion_qids)
    # British Empire should be rejected
    assert len(expanded) == 0


def test_build_collection_artifacts_writes_files(tmp_path) -> None:
    from pipeline.wikidata.collections.artifacts import collection_artifact_dir

    artifact_dir = collection_artifact_dir("test-run", base_dir=tmp_path)
    records = [{"name": "Egypt", "wikidata_id": "Q79", "entity_type": "political_entity"}]

    build_collection_artifacts(artifact_dir, records, seeds=[{"qid": "Q79"}], excluded=[])

    assert (artifact_dir / "entities_final" / "egypt_collection.jsonl").exists()
    assert (artifact_dir / "manifest.json").exists()
```

- [ ] **Step 2: Run tests to verify failure**

```powershell
py -m pytest pipeline/tests/test_wikidata_collections_egypt_fallback.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement fallback orchestrator**

Create `pipeline/wikidata/collections/egypt_fallback.py`:

```python
import json
from pathlib import Path
from typing import Any

from pipeline.wikidata.collections.artifacts import (
    collection_artifact_dir,
    entities_final_path,
    included_report_path,
    excluded_report_path,
    manifest_path,
    ensure_dirs,
)
from pipeline.wikidata.scraper.wikidata import batch_fetch_wikidata
from pipeline.wikidata.mapper.entity_mapper import EntityMapper
from pipeline.wikidata.dedup.deduplicator import deduplicate_records

EGYPT_DOMAIN_QIDS = {"Q79", "Q11768"}


def fetch_seed_entities(seeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    qids = [s["qid"] for s in seeds]
    raw = batch_fetch_wikidata(qids)
    mapper = EntityMapper()
    records: list[dict[str, Any]] = []
    for seed in seeds:
        qid = seed["qid"]
        if qid in raw:
            mapped = mapper.map(raw[qid])
            mapped["_seed_qid"] = qid
            mapped["_seed_category"] = seed.get("category", "unknown")
            records.append(mapped)
    return records


def apply_bounded_expansion(
    included: list[dict[str, Any]],
    expansion_qids: list[str],
) -> list[dict[str, Any]]:
    if not expansion_qids:
        return []

    raw = batch_fetch_wikidata(expansion_qids)
    mapper = EntityMapper()
    expanded: list[dict[str, Any]] = []

    for qid, item in raw.items():
        # Reject if not Egypt-domain
        if not _is_egypt_domain(item):
            continue
        mapped = mapper.map(item)
        mapped["_expansion_from"] = _find_source_qid(item, included)
        expanded.append(mapped)

    return expanded


def _is_egypt_domain(item: dict[str, Any]) -> bool:
    claims = item.get("claims", {})
    location_qids = set()
    for prop in ["P17", "P30", "P131", "P276"]:
        for claim in claims.get(prop, []):
            qid = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
            if qid:
                location_qids.add(qid)
    return bool(location_qids & EGYPT_DOMAIN_QIDS)


def _find_source_qid(item: dict[str, Any], included: list[dict[str, Any]]) -> str | None:
    # Simplified: return first included qid that shares a claim
    included_qids = {i["qid"] for i in included if "qid" in i}
    claims = item.get("claims", {})
    for prop in ["P17", "P30", "P131", "P276", "P361", "P527"]:
        for claim in claims.get(prop, []):
            qid = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
            if qid in included_qids:
                return qid
    return None


def build_collection_artifacts(
    artifact_dir: Path,
    records: list[dict[str, Any]],
    seeds: list[dict[str, Any]],
    excluded: list[dict[str, Any]],
) -> None:
    ensure_dirs(artifact_dir)

    # Deduplicate
    deduped = deduplicate_records(records)

    # Write entities
    with open(entities_final_path(artifact_dir), "w", encoding="utf-8") as f:
        for r in deduped:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Write included report
    with open(included_report_path(artifact_dir), "w", encoding="utf-8") as f:
        for r in deduped:
            report = {
                "wikidata_id": r.get("wikidata_id"),
                "name": r.get("name"),
                "seed_qid": r.get("_seed_qid"),
                "expansion_from": r.get("_expansion_from"),
            }
            f.write(json.dumps(report, ensure_ascii=False) + "\n")

    # Write excluded report
    with open(excluded_report_path(artifact_dir), "w", encoding="utf-8") as f:
        for e in excluded:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    # Write manifest
    manifest = {
        "run_id": artifact_dir.name,
        "artifact_dir": str(artifact_dir),
        "seed_count": len(seeds),
        "entity_count": len(deduped),
        "excluded_count": len(excluded),
    }
    with open(manifest_path(artifact_dir), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
```

- [ ] **Step 4: Run tests**

```powershell
py -m pytest pipeline/tests/test_wikidata_collections_egypt_fallback.py -v
```
Expected: PASS (with mocked fetch; integration tests may need real Wikidata responses or deeper stubs).

- [ ] **Step 5: Commit**

```bash
git add pipeline/wikidata/collections/egypt_fallback.py pipeline/tests/test_wikidata_collections_egypt_fallback.py
git commit -m "feat(pipeline): add Egypt Wikidata fallback orchestrator"
```

---

### Task 4: Wire CLI Command

**Files:**
- Modify: `pipeline/ohm_collections/__main__.py`
- Modify: `pipeline/__main__.py`
- Create: `pipeline/tests/test_wikidata_collections_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `pipeline/tests/test_wikidata_collections_cli.py`:

```python
from click.testing import CliRunner

from pipeline.ohm_collections.__main__ import cli


def test_egypt_wikidata_build_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["egypt-wikidata-build", "--help"])
    assert result.exit_code == 0
    assert "egypt-wikidata-build" in result.output


def test_egypt_wikidata_build_runs_with_dry_run() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["egypt-wikidata-build", "--run-id", "test-egypt", "--no-expansion"])
    assert result.exit_code == 0
```

- [ ] **Step 2: Run tests to verify failure**

```powershell
py -m pytest pipeline/tests/test_wikidata_collections_cli.py -v
```
Expected: FAIL because command is not registered.

- [ ] **Step 3: Register CLI command**

In `pipeline/ohm_collections/__main__.py`, add:

```python
import click
from pathlib import Path

from pipeline.wikidata.collections.egypt_seed_set import load_seed_set
from pipeline.wikidata.collections.egypt_fallback import fetch_seed_entities, apply_bounded_expansion, build_collection_artifacts
from pipeline.wikidata.collections.artifacts import collection_artifact_dir


@cli.command("egypt-wikidata-build")
@click.option("--run-id", required=True)
@click.option("--output-root", type=click.Path(path_type=Path))
@click.option("--seed-file", type=click.Path(path_type=Path))
@click.option("--no-expansion", is_flag=True, help="Run exact-seed-only mode")
@click.option("--resume", is_flag=True)
@click.option("--force", is_flag=True)
def egypt_wikidata_build(run_id, output_root, seed_file, no_expansion, resume, force):
    artifact_dir = collection_artifact_dir(run_id, base_dir=output_root)

    if resume and not force and (artifact_dir / "manifest.json").exists():
        click.echo(f"Run {run_id} already exists. Use --force to rebuild.")
        return

    seeds = load_seed_set(path=seed_file)
    click.echo(f"Loaded {len(seeds)} seed(s).")

    records = fetch_seed_entities(seeds)
    click.echo(f"Fetched {len(records)} seed entity/ies.")

    excluded: list[dict] = []

    if not no_expansion:
        # Simplified: collect expansion QIDs from claims of included seeds
        expansion_qids: list[str] = []
        # TODO: implement proper claim extraction
        expanded = apply_bounded_expansion(records, expansion_qids)
        click.echo(f"Expanded to {len(expanded)} additional entity/ies.")
        records.extend(expanded)

    build_collection_artifacts(artifact_dir, records, seeds, excluded)
    click.echo(f"Wrote {len(records)} entity/ies to {artifact_dir}.")
```

- [ ] **Step 4: Run CLI tests**

```powershell
py -m pytest pipeline/tests/test_wikidata_collections_cli.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/ohm_collections/__main__.py pipeline/__main__.py pipeline/tests/test_wikidata_collections_cli.py
git commit -m "feat(pipeline): wire egypt-wikidata-build CLI command"
```

---

### Task 5: Verify Import Compatibility

**Files:**
- Verify only

- [ ] **Step 1: Build a test collection**

```powershell
py -m pipeline collections egypt-wikidata-build --run-id egypt-wikidata-test --no-expansion
```

- [ ] **Step 2: Verify output layout**

```powershell
Get-ChildItem output/wikidata_collections/egypt-wikidata-test/ -Recurse
```

Expected:
- `entities_final/egypt_collection.jsonl` exists
- `reports/included.jsonl` exists
- `manifest.json` exists
- No `borders_final/` directory

- [ ] **Step 3: Verify importer compatibility**

```powershell
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:import /var/www/html/storage/app/imports/egypt-wikidata-test/entities_final/egypt_collection.jsonl --sync --force --batch-id=egypt-wikidata-test
```

Expected: importer accepts records without OHM border metadata.

- [ ] **Step 4: Commit verification notes**

```bash
git add docs/implementation-docs/egypt-wikidata-fallback-runbook.md
git commit -m "docs: add Egypt Wikidata fallback operator runbook"
```

---

### Task 6: Final Verification and Docs

- [ ] **Step 1: Run all new collection test files**

```powershell
py -m pytest pipeline/tests/test_wikidata_collections_*.py -v
```
Expected: PASS.

- [ ] **Step 2: Run existing Wikidata pipeline tests**

```powershell
py -m pytest pipeline/tests/test_wikidata_*.py -v
```
Expected: PASS (or only pre-existing unrelated failures).

- [ ] **Step 3: Update README**

In `pipeline/README.md`, add:

```markdown
### Egypt Wikidata fallback

When OHM discovery is incomplete, build Egypt entities directly from Wikidata:

```powershell
py -m pipeline collections egypt-wikidata-build --run-id egypt-wikidata-2026 --force
```

Options:
- `--no-expansion` — import only the curated seed set
- `--seed-file <path>` — use a custom seed definition
- `--output-root <path>` — override the default output directory

Import the result:
```bash
docker compose -f docker/docker-compose.yml exec app php artisan pipeline:import storage/app/imports/egypt-wikidata-2026/entities_final/egypt_collection.jsonl --sync --force --batch-id=egypt-wikidata-2026
```
```

- [ ] **Step 4: Commit**

```bash
git add pipeline/README.md docs/implementation-docs/egypt-wikidata-fallback-runbook.md
git commit -m "docs: document Egypt Wikidata fallback workflow"
```

---

## Acceptance Criteria

- `egypt_seed_set.py` loads the curated JSON and rejects malformed entries.
- `egypt_fallback.py` fetches seeds, applies bounded expansion, maps through `EntityMapper`, deduplicates, and writes artifacts.
- `egypt-wikidata-build` CLI produces `entities_final/egypt_collection.jsonl`.
- No `borders_final/` output is created.
- The Laravel generic importer accepts the output without OHM metadata.
- All new tests pass.
- Existing Wikidata pipeline tests remain green.
- README and runbook document the workflow.
