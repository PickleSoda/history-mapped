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
