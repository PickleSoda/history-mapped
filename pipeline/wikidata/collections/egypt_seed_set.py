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
