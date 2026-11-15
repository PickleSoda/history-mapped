"""Polite HTTP clients for the Wikidata Query Service and the Wikipedia API."""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

from pipeline.config import settings

logger = logging.getLogger(__name__)

WDQS = "https://query.wikidata.org/sparql"
# Listing (the qids step) may use another Wikidata SPARQL endpoint: big
# person pools that time out on a busy WDQS list in seconds on QLever
# (BULK_LIST_ENDPOINT=https://qlever.dev/api/wikidata). Item data always
# comes from WDQS and the Wikidata API at fetch time.
LIST_ENDPOINT = os.environ.get("BULK_LIST_ENDPOINT", WDQS)
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"

PREFIXES = """PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX ps: <http://www.wikidata.org/prop/statement/>
PREFIX psv: <http://www.wikidata.org/prop/statement/value/>
PREFIX pq: <http://www.wikidata.org/prop/qualifier/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX schema: <http://schema.org/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX bd: <http://www.bigdata.com/rdf#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""


class QueryTimeout(Exception):
    """WDQS gave up on the query (its 60-second limit)."""


class Client:
    def __init__(self, min_interval: float = 1.0, timeout: float = 75.0, endpoint: str = WDQS):
        self.endpoint = endpoint
        self.session = requests.Session()
        self.session.headers["User-Agent"] = settings.wikidata_user_agent
        self.min_interval = min_interval
        self.timeout = timeout
        self._last = 0.0

    def _wait(self) -> None:
        delay = self.min_interval - (time.monotonic() - self._last)
        if delay > 0:
            time.sleep(delay)
        self._last = time.monotonic()

    def sparql(self, query: str, retries: int = 5) -> list[dict[str, Any]]:
        """Bindings of `query`. Raises QueryTimeout when WDQS times out."""
        backoff = 15.0
        for attempt in range(retries):
            self._wait()
            try:
                resp = self.session.post(
                    self.endpoint,
                    data={"query": PREFIXES + query},
                    headers={"Accept": "application/sparql-results+json"},
                    timeout=self.timeout,
                )
            except requests.Timeout:
                raise QueryTimeout("client timeout")
            except requests.RequestException as exc:
                logger.warning("WDQS request failed (%s); retrying in %.0fs", exc, backoff)
                time.sleep(backoff)
                backoff *= 2
                continue
            if resp.status_code == 200:
                try:
                    return resp.json()["results"]["bindings"]
                except ValueError:
                    # A timeout mid-stream truncates the JSON.
                    raise QueryTimeout("truncated response")
            body = resp.text[:2000]
            if "TimeoutException" in body or "java.util.concurrent.TimeoutException" in body:
                raise QueryTimeout("server timeout")
            if resp.status_code in (429, 500, 502, 503, 504):
                wait = float(resp.headers.get("Retry-After") or backoff)
                logger.warning("WDQS %s; waiting %.0fs (attempt %d)", resp.status_code, wait, attempt + 1)
                time.sleep(wait)
                backoff *= 2
                continue
            raise RuntimeError(f"WDQS {resp.status_code}: {body[:300]}")
        raise RuntimeError("WDQS: out of retries")

    def wikipedia(self, params: dict[str, Any], retries: int = 5) -> dict[str, Any]:
        params = {"format": "json", "formatversion": "2", "maxlag": "5", **params}
        backoff = 10.0
        for _ in range(retries):
            self._wait()
            try:
                resp = self.session.get(WIKIPEDIA_API, params=params, timeout=60)
            except requests.RequestException as exc:
                logger.warning("Wikipedia request failed (%s); retrying", exc)
                time.sleep(backoff)
                backoff *= 2
                continue
            if resp.status_code == 200:
                data = resp.json()
                if data.get("error", {}).get("code") == "maxlag":
                    time.sleep(float(resp.headers.get("Retry-After") or 5))
                    continue
                return data
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(float(resp.headers.get("Retry-After") or backoff))
                backoff *= 2
                continue
            resp.raise_for_status()
        raise RuntimeError("Wikipedia: out of retries")


def value(binding: dict[str, Any], key: str) -> str | None:
    v = binding.get(key)
    return v.get("value") if v else None


def qid_of(uri: str | None) -> str | None:
    if uri and "/entity/Q" in uri:
        return uri.rsplit("/", 1)[-1]
    return None
