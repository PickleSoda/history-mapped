from __future__ import annotations

from typing import Any

import requests

from pipeline.config import settings


def fetch_wikipedia_summary(title: str, language: str | None = None) -> dict[str, Any] | None:
    """Fetch Wikipedia article summary for a given title.

    Returns dict with: title, extract, url, or None if not found.
    """
    lang = language or settings.wikipedia_language
    url = f"https://{lang}.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "titles": title,
        "prop": "extracts",
        "explaintext": True,
        "exintro": True,
        "exlimit": 1,
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        pages = data.get("query", {}).get("pages", {})
        for page_id, page_data in pages.items():
            if page_id == "-1":
                return None
            return {
                "title": page_data.get("title"),
                "extract": page_data.get("extract"),
                "url": f"https://{lang}.wikipedia.org/wiki/{page_data.get('title', '').replace(' ', '_')}",
            }
    except Exception:
        return None
    return None
