"""Wikipedia content enricher.

Given items with wikipedia_title from Wikidata, fetches summaries,
infobox data, and full-text extracts from the English Wikipedia API.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests
from ratelimit import limits, sleep_and_retry

from pipeline.config import settings

logger = logging.getLogger(__name__)

WIKIPEDIA_API = f"https://{settings.wikipedia_language}.wikipedia.org/w/api.php"


class WikipediaEnricher:
    """Enrich Wikidata items with Wikipedia summaries and infobox data."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": settings.wikidata_user_agent,
        })

    @sleep_and_retry
    @limits(calls=settings.wikipedia_rpm, period=60)
    def _api_call(self, params: dict) -> dict:
        """Make a rate-limited Wikipedia API call."""
        params.setdefault("format", "json")
        params.setdefault("formatversion", "2")
        resp = self.session.get(WIKIPEDIA_API, params=params)
        resp.raise_for_status()
        return resp.json()

    def enrich_batch(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Enrich a list of items with Wikipedia content.

        Modifies items in-place, adding:
        - summary: first paragraph extract
        - full_extract: full article text extract (first 3000 chars)
        - infobox: parsed infobox key-value pairs (via wptools)
        - aliases: additional names from Wikipedia redirects
        """
        # Filter to items that have a Wikipedia title
        enrichable = [(i, item) for i, item in enumerate(items) if item.get("wikipedia_title")]

        if not enrichable:
            return items

        # Batch fetch extracts (up to 20 titles per API call)
        titles_to_idx: dict[str, list[int]] = {}
        for idx, item in enrichable:
            title = item["wikipedia_title"]
            titles_to_idx.setdefault(title, []).append(idx)

        all_titles = list(titles_to_idx.keys())
        batch_size = 20

        for i in range(0, len(all_titles), batch_size):
            batch_titles = all_titles[i : i + batch_size]
            self._fetch_extracts(batch_titles, titles_to_idx, items)

        # Fetch infoboxes individually via wptools (slower, but richer data)
        for idx, item in enrichable:
            if item.get("wikipedia_title"):
                self._fetch_infobox(item)

        return items

    def _fetch_extracts(
        self,
        titles: list[str],
        titles_to_idx: dict[str, list[int]],
        items: list[dict],
    ):
        """Batch fetch plain-text extracts from the Wikipedia API."""
        params = {
            "action": "query",
            "titles": "|".join(titles),
            "prop": "extracts|redirects",
            "explaintext": "1",      # Plain text, no HTML
            "redirects": "1",
            "exchars": str(settings.wikipedia_extract_max_chars),
        }

        data = self._api_call(params)
        pages = data.get("query", {}).get("pages", [])

        for page in pages:
            title = page.get("title", "")
            extract = page.get("extract", "")

            # Map back to items
            for matched_title, indices in titles_to_idx.items():
                # Handle redirects — Wikipedia may have resolved the title
                if title == matched_title or title.replace(" ", "_") == matched_title.replace(" ", "_"):
                    for idx in indices:
                        summary_source = self._first_paragraph(extract)
                        items[idx]["summary"] = self._truncate(summary_source, 900)
                        items[idx]["full_extract"] = self._truncate(extract, settings.wikipedia_extract_max_chars)

            # Collect redirect aliases
            redirects = page.get("redirects", [])
            for redir in redirects:
                redir_from = redir.get("from", "")
                if title in titles_to_idx:
                    for idx in titles_to_idx[title]:
                        if redir_from and redir_from not in items[idx].get("aliases", []):
                            items[idx].setdefault("aliases", []).append(redir_from)

    def _fetch_infobox(self, item: dict):
        """Fetch structured infobox data using wptools.

        Falls back gracefully if wptools parsing fails.
        """
        try:
            import wptools
        except ImportError:
            logger.debug("wptools not available, skipping infobox enrichment")
            return

        title = item.get("wikipedia_title")
        if not title:
            return

        try:
            page = wptools.page(title, silent=True)
            page.get_parse(show=False)

            infobox = page.data.get("infobox") or {}
            item["infobox"] = {
                k: v for k, v in infobox.items()
                if isinstance(v, str) and len(v) < 500  # Filter out markup-heavy values
            }
        except Exception as e:
            logger.debug(f"wptools failed for {title}: {e}")
            item["infobox"] = {}

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        """Truncate text at sentence boundary."""
        if len(text) <= max_len:
            return text
        truncated = text[:max_len]
        # Cut at last sentence end
        last_period = truncated.rfind(". ")
        if last_period > max_len * 0.5:
            return truncated[: last_period + 1]
        return truncated + "…"

    @staticmethod
    def _first_paragraph(text: str) -> str:
        """Extract the first non-empty paragraph from Wikipedia text."""
        for paragraph in text.split("\n"):
            cleaned = paragraph.strip()
            if cleaned:
                return cleaned
        return text
