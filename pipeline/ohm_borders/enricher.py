"""Batch Wikidata enrichment for OHM relation wikidata QIDs."""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
_USER_AGENT = "WikiGlobe-Pipeline/1.0 (https://wikiglobe.example)"

_SPARQL_TEMPLATE = """
SELECT ?polity ?polityLabel ?polityDescription
       (GROUP_CONCAT(DISTINCT ?altLabelVal; SEPARATOR=\"||\") AS ?altLabel)
       ?inception ?dissolution
WHERE {{
  VALUES ?polity {{ {qid_list} }}
  OPTIONAL {{ ?polity wdt:P571 ?inception. }}
  OPTIONAL {{ ?polity wdt:P576 ?dissolution. }}
  OPTIONAL {{ ?polity skos:altLabel ?altLabelVal. FILTER(LANG(?altLabelVal)=\"en\") }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language \"en\". }}
}}
GROUP BY ?polity ?polityLabel ?polityDescription ?inception ?dissolution
"""


def _build_sparql_query(qids: list[str]) -> str:
    qid_list = " ".join(f"wd:{qid}" for qid in qids)
    return _SPARQL_TEMPLATE.format(qid_list=qid_list)


def _sparql_query(query: str) -> list[dict[str, Any]]:
    # Lazy import keeps tests lightweight when SPARQLWrapper is not installed.
    from SPARQLWrapper import JSON, SPARQLWrapper

    sparql = SPARQLWrapper(WIKIDATA_SPARQL)
    sparql.addCustomHttpHeader("User-Agent", _USER_AGENT)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    return results["results"]["bindings"]


def _extract_year(iso_val: str | None) -> str | None:
    if not iso_val:
        return None

    match = re.match(r"(-?\d+)", iso_val)
    return match.group(1) if match else None


def batch_enrich_qids(qids: list[str], batch_size: int = 50) -> dict[str, dict[str, Any]]:
    """Return a metadata dict keyed by QID."""
    results: dict[str, dict[str, Any]] = {}
    deduped_qids = list(dict.fromkeys(qids))

    for i in range(0, len(deduped_qids), batch_size):
        batch = deduped_qids[i : i + batch_size]
        try:
            bindings = _sparql_query(_build_sparql_query(batch))
        except Exception as exc:
            logger.warning("SPARQL batch failed for batch starting at %s: %s", i, exc)
            continue

        for row in bindings:
            uri = row.get("polity", {}).get("value", "")
            qid = uri.rsplit("/", 1)[-1]
            aliases_raw = row.get("altLabel", {}).get("value", "")
            aliases = [alias.strip() for alias in aliases_raw.split("||") if alias.strip()] if aliases_raw else []

            results[qid] = {
                "name_en": row.get("polityLabel", {}).get("value"),
                "description": row.get("polityDescription", {}).get("value"),
                "aliases_en": aliases,
                "temporal_start": _extract_year(row.get("inception", {}).get("value")),
                "temporal_end": _extract_year(row.get("dissolution", {}).get("value")),
            }

    return results
