"""Entity mapper — converts raw Wikidata/Wikipedia data to the history-mapped entity schema.

Produces dicts matching the EntityData DTO structure:
{
    "name": str,
    "entity_type": str,
    "entity_group": str,
    "wikidata_id": str,
    "summary": str,
    "significance": str,
    "alternative_names": [str],
    "temporal_start": str,
    "temporal_end": str,
    "location_name": str,
    "geojson": {"type": "Point", "coordinates": [lon, lat]} | null,
    "attributes": {type-specific fields},
    "tags": [str],
    "date_method": "source_database",
    "location_method": "wikidata",
    "date_confidence": "medium",
    "location_confidence": "medium",
    "confidence": "medium",
    "verification_status": "pipeline_draft",
    "source_citations": [{...}],
    ...
}
"""

from __future__ import annotations

import logging
from typing import Any

from pipeline.config import TYPE_TO_GROUP, settings
from pipeline.wikidata.mapper.type_configs import WIKIDATA_TYPE_CONFIGS

logger = logging.getLogger(__name__)


class EntityMapper:
    """Map raw Wikidata/Wikipedia data to our entity schema."""

    def __init__(self) -> None:
        self._summary_cache: dict[str, str] = {}

    def map(self, raw: dict[str, Any], entity_type: str) -> dict[str, Any] | None:
        """Convert a raw scraped item to the history-mapped entity format.

        Returns None if the item lacks minimum required data (name).
        """
        label = raw.get("label", "").strip()
        if not label:
            return None

        entity_group = TYPE_TO_GROUP.get(entity_type)
        if not entity_group:
            logger.warning(f"Unknown entity_type: {entity_type}")
            return None

        # ── Base fields ──────────────────────────────────────────────────────

        entity = {
            "name": label,
            "entity_type": entity_type,
            "entity_group": entity_group,
            "wikidata_id": raw.get("qid"),
            "summary": self._build_summary(raw),
            "significance": None,  # Filled by LLM enrichment in v2
            "alternative_names": self._build_alternative_names(raw),
            "verification_status": "pipeline_draft",
            "confidence": "medium",
            "source_citations": self._build_source_citations(raw),
        }

        # ── Temporal fields ──────────────────────────────────────────────────

        temporal_start, temporal_end, duration_type = self._extract_temporal_bounds(raw)

        if temporal_start or temporal_end:
            entity["temporal_start"] = temporal_start
            entity["temporal_end"] = temporal_end
            entity["date_method"] = "source_database"
            entity["date_confidence"] = "medium"
            entity["duration_type"] = duration_type

        # ── Spatial fields ───────────────────────────────────────────────────

        location_name = raw.get("location_name") or self._derive_location_name(raw)
        if location_name:
            entity["location_name"] = location_name
            entity["location_method"] = "wikidata"
            entity["location_confidence"] = "medium"

        coords = self._derive_coords(raw)
        if coords:
            entity["geojson"] = {
                "type": "Point",
                "coordinates": [coords["lon"], coords["lat"]],
            }
            entity["location_method"] = "wikidata"
            entity["location_confidence"] = "medium"

        territory_geojson = raw.get("territory_geojson")
        if territory_geojson:
            entity["territory_geojson"] = territory_geojson

        # ── Type-specific attributes ─────────────────────────────────────────

        config = WIKIDATA_TYPE_CONFIGS.get(entity_type, {})
        attributes = self._extract_attributes(raw, config)

        # Add infobox fields to attributes
        infobox = raw.get("infobox", {})
        if infobox:
            attributes["_infobox"] = infobox  # Raw infobox preserved for review

        full_extract = raw.get("full_extract")
        if full_extract:
            attributes["_wikipedia_extract"] = full_extract[: settings.wikipedia_extract_max_chars]

        geoshape = raw.get("geoshape")
        if geoshape:
            attributes["geoshape"] = geoshape

        if attributes:
            entity["attributes"] = attributes

        # ── Tags (derived from description + type) ───────────────────────────

        entity["tags"] = self._derive_tags(raw, entity_type, entity_group)

        # ── Impact score (rough heuristic) ───────────────────────────────────

        entity["impact_score"] = self._estimate_impact(raw)

        # ── Relationship hints (stored temporarily, resolved at import) ──────

        if raw.get("properties"):
            entity["_relationship_hints"] = self._extract_relationship_hints(
                raw["properties"], entity_type
            )

        return entity

    def _build_summary(self, raw: dict[str, Any]) -> str | None:
        """Build a concise summary using rule-based truncation with optional LLM fallback."""
        qid = raw.get("qid")
        cached = self._summary_cache.get(qid) if qid else None
        if cached:
            return cached

        summary_source = (
            raw.get("summary")
            or raw.get("description")
            or raw.get("full_extract")
            or ""
        ).strip()
        if not summary_source:
            return None

        summary = self._truncate_sentence(summary_source, settings.summary_max_chars)

        long_text = raw.get("full_extract") or summary_source
        if (
            settings.summary_use_llm
            and settings.openai_api_key
            and len(long_text) > settings.summary_max_chars * 2
        ):
            llm_summary = self._llm_shorten_summary(long_text)
            if llm_summary:
                summary = self._truncate_sentence(llm_summary, settings.summary_max_chars)

        if qid and summary:
            self._summary_cache[qid] = summary

        return summary or None

    @staticmethod
    def _truncate_sentence(text: str, max_len: int) -> str:
        """Truncate text to max length, preferring sentence boundaries."""
        if len(text) <= max_len:
            return text.strip()

        trimmed = text[:max_len].strip()
        cut_at = max(trimmed.rfind(". "), trimmed.rfind("; "), trimmed.rfind(": "))
        if cut_at >= int(max_len * 0.55):
            return trimmed[: cut_at + 1].strip()

        return f"{trimmed}…"

    def _llm_shorten_summary(self, text: str) -> str | None:
        """Optionally shorten text via OpenAI; returns None on any failure."""
        try:
            from openai import OpenAI

            client = OpenAI(api_key=settings.openai_api_key)
            prompt = (
                "Rewrite the following historical description as a concise, factual summary. "
                f"Keep it under {settings.summary_max_chars} characters, neutral tone, no bullet points."
            )
            response = client.chat.completions.create(
                model=settings.openai_summary_model,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": "You summarize historical entities for a structured data pipeline."},
                    {"role": "user", "content": f"{prompt}\n\n{text[:8000]}"},
                ],
            )
            content = response.choices[0].message.content if response.choices else None
            return content.strip() if content else None
        except Exception as exc:
            logger.debug(f"LLM summary shortening failed: {exc}")
            return None

    def _extract_temporal_bounds(self, raw: dict[str, Any]) -> tuple[str | None, str | None, str]:
        """Normalize temporal fields from multiple Wikidata date properties."""
        start = raw.get("inception") or raw.get("start_time")
        end = raw.get("dissolution") or raw.get("end_time")
        point = raw.get("point_in_time")

        # For persons: use birth_date as start, death_date as end
        if not start and not end:
            start = raw.get("birth_date")
            end = raw.get("death_date")

        if not start and point:
            start = point
        if not end and point and not raw.get("dissolution") and not raw.get("end_time") and not raw.get("death_date"):
            end = point

        if start and end and start == end:
            duration_type = "point"
        elif start and end:
            duration_type = "period"
        elif start and not end:
            duration_type = "ongoing"
        else:
            duration_type = "uncertain"

        return start, end, duration_type

    def _derive_location_name(self, raw: dict[str, Any]) -> str | None:
        """Derive a location name from linked location-like properties."""
        properties = raw.get("properties", {})
        for prop in ("P276", "P131", "P17"):
            values = properties.get(prop, [])
            for value in values:
                label = (value.get("label") or "").strip()
                if label:
                    return label
        return None

    def _derive_coords(self, raw: dict[str, Any]) -> dict[str, float] | None:
        """Derive coordinates from entity coords or linked location coords."""
        coords = raw.get("coords")
        if coords and "lon" in coords and "lat" in coords:
            return {"lon": float(coords["lon"]), "lat": float(coords["lat"])}

        properties = raw.get("properties", {})
        for prop in ("P276", "P131", "P17"):
            values = properties.get(prop, [])
            for value in values:
                vcoords = value.get("coords")
                if isinstance(vcoords, dict) and "lon" in vcoords and "lat" in vcoords:
                    return {"lon": float(vcoords["lon"]), "lat": float(vcoords["lat"])}

        return None

    def _build_alternative_names(self, raw: dict) -> list[str]:
        """Collect alternative names from aliases and Wikipedia redirects."""
        names = set()
        for alias in raw.get("aliases", []):
            if alias and alias != raw.get("label"):
                names.add(alias)
        return sorted(names)[:20]  # Cap at 20

    def _build_source_citations(self, raw: dict) -> list[dict]:
        """Build source citations for the entity."""
        citations = []
        qid = raw.get("qid")
        if qid:
            citations.append({
                "source_type": "reference",
                "title": f"Wikidata:{qid}",
                "url": f"https://www.wikidata.org/wiki/{qid}",
                "reliability": "reference",
            })
        wp_title = raw.get("wikipedia_title")
        if wp_title:
            citations.append({
                "source_type": "reference",
                "title": f"Wikipedia: {wp_title}",
                "url": f"https://en.wikipedia.org/wiki/{wp_title.replace(' ', '_')}",
                "reliability": "user_contributed",
            })
        return citations

    def _extract_attributes(self, raw: dict, config: dict) -> dict:
        """Map Wikidata properties to type-specific attributes."""
        attributes = {}
        field_map = config.get("field_map", {})
        properties = raw.get("properties", {})

        for prop_id, attr_key in field_map.items():
            if prop_id in properties:
                values = properties[prop_id]
                if len(values) == 1:
                    val = values[0]
                    # Store as QID reference or label depending on type
                    if val.get("qid"):
                        attributes[attr_key] = {
                            "wikidata_id": val["qid"],
                            "label": val.get("label", ""),
                        }
                    else:
                        attributes[attr_key] = val.get("label", "")
                else:
                    attributes[attr_key] = [
                        {
                            "wikidata_id": v.get("qid"),
                            "label": v.get("label", ""),
                        }
                        for v in values
                    ]

        return attributes

    def _derive_tags(self, raw: dict, entity_type: str, entity_group: str) -> list[str]:
        """Derive tags from entity description and type."""
        tags = [entity_group.lower(), entity_type]
        desc = (raw.get("description") or "").lower()

        # Historical era heuristics based on dates
        inception = raw.get("inception")
        if inception:
            try:
                year = int(inception)
                if year < -3000:
                    tags.append("prehistoric")
                elif year < -500:
                    tags.append("ancient")
                elif year < 500:
                    tags.append("classical")
                elif year < 1500:
                    tags.append("medieval")
                elif year < 1800:
                    tags.append("early_modern")
                else:
                    tags.append("modern")
            except ValueError:
                pass

        # Geographic hints from description
        geo_keywords = {
            "roman": "mediterranean", "greek": "mediterranean",
            "persian": "middle_east", "ottoman": "middle_east",
            "chinese": "east_asia", "mongol": "central_asia",
            "indian": "south_asia", "african": "africa",
            "european": "europe", "american": "americas",
        }
        for keyword, tag in geo_keywords.items():
            if keyword in desc:
                tags.append(tag)

        return list(set(tags))

    def _estimate_impact(self, raw: dict) -> int:
        """Rough impact score heuristic (1–100)."""
        score = 30  # baseline

        # Wikipedia article length is a decent proxy for notability
        extract = raw.get("full_extract", "")
        if len(extract) > 3000:
            score += 20
        elif len(extract) > 1000:
            score += 10

        # Number of Wikidata properties = interconnectedness
        props = raw.get("properties", {})
        prop_count = sum(len(v) for v in props.values())
        score += min(prop_count * 2, 30)

        # Has coordinates = more useful for map display
        if raw.get("coords"):
            score += 5

        return min(score, 100)

    def _extract_relationship_hints(
        self, properties: dict, entity_type: str
    ) -> list[dict]:
        """Extract relationship hints from Wikidata properties.

        These are NOT resolved relationships. They contain Wikidata QIDs
        of the target entities which must be matched to existing entities
        at import time. Stored as _relationship_hints in the JSONL output,
        consumed by the Laravel ImportEntityJob.

        Format:
        [
            {
                "relationship_type": "capital_of",
                "target_wikidata_id": "Q220",
                "target_label": "Rome",
                "confidence": "medium",
                "source": "wikidata:P36"
            }
        ]
        """
        hints = []

        # Map Wikidata properties → our relationship types
        PROPERTY_TO_RELATIONSHIP = {
            # Political
            "P36":   "capital_of",        # capital → City
            "P1376": "capital_of",        # capital of ← reverse
            "P17":   "part_of",           # country
            "P131":  "part_of",           # located in admin territory
            "P150":  "contains",          # contains admin territory
            "P155":  "preceded_by",       # follows
            "P156":  "succeeded_by",      # followed by
            "P361":  "part_of",           # part of
            "P527":  "contains",          # has part / has parts

            # Person
            "P19":   "born_in",           # place of birth
            "P20":   "died_in",           # place of death
            "P22":   "child_of",          # father (reverse: parent_of)
            "P25":   "child_of",          # mother (reverse: parent_of)
            "P26":   "married_to",        # spouse
            "P39":   "rules",             # position held (pharaoh, king, etc.)
            "P40":   "parent_of",         # child
            "P607":  "participated_in",   # conflict
            "P1344": "participated_in",   # participant of

            # Economic
            "P37":   "official_religion_of",  # official language (remapped in context)
            "P38":   "used_currency",     # currency

            # Culture
            "P50":   "authored",          # author
            "P112":  "founded",           # founded by
            "P84":   "built_by",          # architect

            # Causal
            "P828":  "resulted_from",     # has cause
            "P1542": "caused",            # has effect
            "P1478": "resulted_from",     # has immediate cause

            # Military
            "P710":  "participated_in",   # participant
        }

        for prop_id, values in properties.items():
            rel_type = PROPERTY_TO_RELATIONSHIP.get(prop_id)
            if not rel_type:
                continue

            for val in values:
                if val.get("qid"):
                    hints.append({
                        "relationship_type": rel_type,
                        "target_wikidata_id": val["qid"],
                        "target_label": val.get("label", ""),
                        "confidence": "medium",
                        "source": f"wikidata:{prop_id}",
                    })

        return hints
