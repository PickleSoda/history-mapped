"""Fixtures: offline Wikidata client and Row factory (no network, no DB)."""
from __future__ import annotations

import pytest

from pipeline.audit.common import Row
from pipeline.audit.wd import WikidataClient


def make_row(name, etype="person", qid=None, start=None, end=None, *, id=None, aliases=(), rels=0, summary="",
             point=None, has_geo=False, group=None, created_at="2026-10-01 00:00:00"):
    groups = {"person": "POLITY", "political_entity": "POLITY", "dynasty": "POLITY", "military_unit": "POLITY",
              "city": "PLACE", "infrastructure_monument": "PLACE"}
    return Row(id=id or f"id-{name}-{qid}-{start}", name=name, type=etype,
               group=group or groups.get(etype, "EVENT" if etype.startswith("event") else "CULTURE"),
               qid=qid, status="pipeline_draft", summary=summary, description="", attributes={}, impact=None,
               created_at=created_at, start=start, end=end, aliases=list(aliases), rels=rels, point=point,
               has_geo=has_geo)


def rec(label, p31=("Q5",), dates=None, aliases=(), description="", enwiki=True, p279=()):
    return {"status": "ok", "label": label, "aliases": list(aliases), "description": description,
            "p31": list(p31), "p279": list(p279), "dates": dict(dates or {}), "enwiki": label if enwiki else None}


@pytest.fixture
def client(tmp_path):
    return WikidataClient(tmp_path, offline=True)


# a tiny subclass closure: class -> roots it reaches
CLOSURE = {
    "Q5": {"Q5"},
    "Q178561": {"Q178561"},
    "Q1261499": {"Q178561"},          # naval battle ⊂ battle
    "Q515": {"Q515", "Q486972", "Q2221906"},
    "Q3024240": {"Q3024240", "Q43229", "Q2221906"},
    "Q176799": {"Q176799", "Q43229"},
    "Q11446": {"Q11446"},             # ship
    "Q16521": {"Q16521"},             # taxon
    "Q773711": {"Q773711", "Q43229", "Q1127126"},
    "Q17329259": {"Q17329259", "Q191067"},  # encyclopedia article
    "Q16970": {"Q811979"},            # church building ⊂ built structure
    "Q99999": set(),                  # some obscure class
}
