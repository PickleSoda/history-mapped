"""Slice specs: what one bulk slice imports and how its QID listing is sharded."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipeline.wikidata.mapper.type_configs import WIKIDATA_TYPE_CONFIGS

SLICES_DIR = Path(os.environ.get("BULK_SLICES_DIR", Path(__file__).parent / "slices"))
QID = re.compile(r"^Q[1-9]\d*$")
SLICE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{2,60}$")


@dataclass
class Window:
    """A year window [start, end) on one date property (astronomical years)."""

    prop: str
    start: int
    end: int

    def clause(self) -> str:
        return (
            f"?item wdt:{self.prop} ?hm_d . "
            f"FILTER(YEAR(?hm_d) >= {self.start} && YEAR(?hm_d) < {self.end})"
        )

    @property
    def label(self) -> str:
        return f"{self.prop}:{self.start}..{self.end}"

    def halves(self) -> tuple["Window", "Window"] | None:
        if self.end - self.start <= 1:
            return None
        mid = (self.start + self.end) // 2
        return Window(self.prop, self.start, mid), Window(self.prop, mid, self.end)


@dataclass
class ValueShard:
    """One value of a VALUES-style shard, e.g. one country or one subclass."""

    pattern: str  # uses ?hm_v
    value: str

    def clause(self) -> str:
        return f"VALUES ?hm_v {{ wd:{self.value} }} {self.pattern}"

    @property
    def label(self) -> str:
        return f"v:{self.value}"


@dataclass
class Slice:
    id: str
    entity_type: str
    where: str
    description: str = ""
    min_sitelinks: int = 0
    enwiki: bool = True
    shards: dict[str, Any] = field(default_factory=dict)
    exclude_p31: list[str] = field(default_factory=list)
    require: list[str] = field(default_factory=list)  # "dates", "coords"
    require_dates_p31: list[str] = field(default_factory=list)  # rows of these classes need a date
    # ...unless their point lies in this [lon_min, lat_min, lon_max, lat_max] box
    # (old undated cathedrals in Europe are medieval; elsewhere mostly modern)
    require_dates_except_bbox: list[float] | None = None
    year_min: int | None = None  # historical years, applied to the start date
    year_max: int | None = None
    max_items: int | None = None
    priority: int = 2
    notes: str = ""

    @classmethod
    def load(cls, slice_id: str, directory: Path = SLICES_DIR) -> "Slice":
        return cls.from_dict(json.loads((directory / f"{slice_id}.json").read_text()))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Slice":
        known = {f for f in cls.__dataclass_fields__}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"unknown slice keys: {sorted(unknown)}")
        s = cls(**data)
        s.validate()
        return s

    def validate(self) -> None:
        if not SLICE_ID.match(self.id):
            raise ValueError(f"bad slice id {self.id!r}")
        if self.entity_type not in WIKIDATA_TYPE_CONFIGS or self.entity_type.startswith("ref_"):
            raise ValueError(f"{self.id}: unknown entity_type {self.entity_type!r}")
        if "?item" not in self.where:
            raise ValueError(f"{self.id}: where must bind ?item")
        if re.search(r"\b(SELECT|LIMIT|OFFSET|GROUP BY)\b", self.where, re.I):
            raise ValueError(f"{self.id}: where is a graph pattern, not a query")
        for key in ("exclude_p31", "require_dates_p31"):
            for q in getattr(self, key):
                if not QID.match(q):
                    raise ValueError(f"{self.id}: {key} {q!r} is not a QID")
        box = self.require_dates_except_bbox
        if box is not None and (len(box) != 4 or not (box[0] < box[2] and box[1] < box[3])):
            raise ValueError(f"{self.id}: require_dates_except_bbox is [lon_min, lat_min, lon_max, lat_max]")
        bad = set(self.require) - {"dates", "coords"}
        if bad:
            raise ValueError(f"{self.id}: unknown require {sorted(bad)}")
        kinds = set(self.shards) - {"years", "values"}
        if kinds:
            raise ValueError(f"{self.id}: unknown shard kinds {sorted(kinds)}")

    def initial_shards(self) -> list[Window | ValueShard | None]:
        """The shards to list. None is the single unsharded query."""
        if "years" in self.shards:
            y = self.shards["years"]
            step = int(y.get("step", 50))
            prop = y.get("prop", "P571")
            return [Window(prop, a, min(a + step, y["to"])) for a in range(y["from"], y["to"], step)]
        if "values" in self.shards:
            v = self.shards["values"]
            return [ValueShard(v["pattern"], q) for q in v["values"]]
        return [None]

    def qid_query(self, shard: Window | ValueShard | None) -> str:
        parts = [self.where.strip(), shard.clause() if shard else ""]
        parts.append(f"?item wikibase:sitelinks ?hm_sl . FILTER(?hm_sl >= {self.min_sitelinks})")
        if self.enwiki:
            parts.append("?hm_wp schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> .")
        body = "\n  ".join(p for p in parts if p)
        return f"SELECT DISTINCT ?item ?hm_sl WHERE {{\n  {body}\n}}"


def all_slices(directory: Path = SLICES_DIR, errors: list[str] | None = None) -> list[Slice]:
    """Every valid slice, priority order. With `errors`, an invalid spec is
    reported there and skipped (several slicers edit specs at once);
    without it, the first invalid spec raises."""
    out: list[Slice] = []
    for path in sorted(directory.glob("*.json")):
        try:
            out.append(Slice.load(path.stem, directory))
        except (ValueError, TypeError, KeyError) as exc:
            if errors is None:
                raise
            errors.append(f"{path.name}: {exc}")
    return sorted(out, key=lambda s: (s.priority, s.id))
