"""Entity deduplicator.

Three-layer dedup strategy:

1. **Exact QID match** — Two items with the same wikidata_id are always duplicates.
   First-seen wins; later duplicates merge their alternative_names into the first.

2. **Fuzzy name + temporal overlap** — Items without QIDs (or different QIDs) are
   compared by name similarity (thefuzz token_sort_ratio ≥ 88) AND temporal overlap.
   This catches cases like "Roman Empire" vs "The Roman Empire" or inconsistent
   Wikidata QID assignment.

3. **Database check (optional)** — If --check-db is set, each item is checked
   against existing entities in PostgreSQL by wikidata_id and fuzzy name within
   the same entity_type. Requires DATABASE_URL in .env.
"""

from __future__ import annotations

import logging
from typing import Any

from thefuzz import fuzz

from pipeline.config import settings

logger = logging.getLogger(__name__)


class Deduplicator:
    """Deduplicate entity records within a batch and optionally against the DB."""

    def __init__(self, check_db: bool = False):
        self.check_db = check_db
        self._db_conn = None

    def deduplicate(self, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Deduplicate a list of entity dicts.

        Returns a new list with duplicates removed. When duplicates are found,
        the first occurrence is kept and enriched with alternative_names from
        the duplicate.
        """
        # Phase 1: QID-based dedup
        seen_qids: dict[str, int] = {}  # qid → index in result
        result: list[dict[str, Any]] = []
        skipped_qid = 0

        for entity in entities:
            qid = entity.get("wikidata_id")
            if qid and qid in seen_qids:
                # Merge alternative names into the kept entity
                idx = seen_qids[qid]
                self._merge_names(result[idx], entity)
                skipped_qid += 1
                continue

            result.append(entity)
            if qid:
                seen_qids[qid] = len(result) - 1

        if skipped_qid:
            logger.info(f"QID dedup: removed {skipped_qid} duplicates")

        # Phase 2: Fuzzy name + temporal dedup (within same entity_type)
        result = self._fuzzy_dedup(result)

        # Phase 3: DB dedup (optional)
        if self.check_db:
            result = self._db_dedup(result)

        return result

    def _fuzzy_dedup(self, entities: list[dict]) -> list[dict]:
        """Remove items where name is near-identical AND entity_type matches AND
        temporal ranges overlap.
        """
        if len(entities) <= 1:
            return entities

        kept: list[dict] = []
        kept_names: list[tuple[str, str, int | None, int | None]] = []  # (name_lower, type, start, end)
        skipped = 0

        for entity in entities:
            name = entity.get("name", "").lower().strip()
            etype = entity.get("entity_type", "")
            start = self._parse_year(entity.get("temporal_start"))
            end = self._parse_year(entity.get("temporal_end"))

            is_dup = False
            for i, (kname, ktype, kstart, kend) in enumerate(kept_names):
                if ktype != etype:
                    continue

                # Fuzzy name match
                ratio = fuzz.token_sort_ratio(name, kname)
                if ratio < 88:
                    continue

                # Temporal overlap check (if both have dates)
                if self._temporal_overlap(start, end, kstart, kend):
                    self._merge_names(kept[i], entity)
                    is_dup = True
                    skipped += 1
                    break

            if not is_dup:
                kept.append(entity)
                kept_names.append((name, etype, start, end))

        if skipped:
            logger.info(f"Fuzzy dedup: removed {skipped} duplicates")

        return kept

    def _db_dedup(self, entities: list[dict]) -> list[dict]:
        """Check each entity against the existing database."""
        if not settings.database_url:
            logger.warning("DATABASE_URL not set, skipping DB dedup")
            return entities

        try:
            import psycopg
            self._db_conn = psycopg.connect(settings.database_url)
        except Exception as e:
            logger.error(f"Cannot connect to DB for dedup: {e}")
            return entities

        result = []
        skipped = 0

        for entity in entities:
            qid = entity.get("wikidata_id")
            if qid:
                # Check by QID
                with self._db_conn.cursor() as cur:
                    cur.execute(
                        "SELECT entity_id FROM entities WHERE wikidata_id = %s LIMIT 1",
                        (qid,),
                    )
                    if cur.fetchone():
                        skipped += 1
                        continue

            # Check by fuzzy name within same entity_type
            name = entity.get("name", "")
            etype = entity.get("entity_type", "")
            if name and etype:
                with self._db_conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT entity_id, name FROM entities
                        WHERE entity_type = %s
                          AND similarity(name, %s) > 0.6
                        LIMIT 5
                        """,
                        (etype, name),
                    )
                    matches = cur.fetchall()
                    if matches:
                        # Double-check with Python fuzzy matching
                        for _eid, ename in matches:
                            if fuzz.token_sort_ratio(name.lower(), ename.lower()) >= 88:
                                skipped += 1
                                break
                        else:
                            result.append(entity)
                        continue

            result.append(entity)

        if self._db_conn:
            self._db_conn.close()

        if skipped:
            logger.info(f"DB dedup: removed {skipped} already-existing entities")

        return result

    @staticmethod
    def _merge_names(kept: dict, duplicate: dict):
        """Merge alternative_names from duplicate into kept entity."""
        kept_names = set(kept.get("alternative_names") or [])
        dup_names = set(duplicate.get("alternative_names") or [])
        # Also add the duplicate's primary name if different
        if duplicate.get("name") and duplicate["name"] != kept.get("name"):
            dup_names.add(duplicate["name"])
        kept["alternative_names"] = sorted(kept_names | dup_names)[:20]

    @staticmethod
    def _parse_year(val) -> int | None:
        """Parse a year value that might be string or int."""
        if val is None:
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _temporal_overlap(
        s1: int | None, e1: int | None,
        s2: int | None, e2: int | None,
    ) -> bool:
        """Check if two temporal ranges overlap.

        If either entity has no dates, assume overlap (can't disprove).
        """
        if s1 is None and e1 is None:
            return True
        if s2 is None and e2 is None:
            return True

        # Normalize: treat missing end as "ongoing"
        start1 = s1 if s1 is not None else -10000
        end1 = e1 if e1 is not None else 9999
        start2 = s2 if s2 is not None else -10000
        end2 = e2 if e2 is not None else 9999

        return start1 <= end2 and start2 <= end1
