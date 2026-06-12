from __future__ import annotations

import os
import logging
from typing import Any

try:
    import psycopg
    HAS_PSYCOPG = True
except ImportError:
    HAS_PSYCOPG = False

logger = logging.getLogger(__name__)


class DbUnavailable(Exception):
    """Raised when the database connection or query fails."""
    pass


def _get_db_connection():
    """Get a direct DB connection using DATABASE_URL from env."""
    if not HAS_PSYCOPG:
        return None
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        return None
    try:
        return psycopg.connect(db_url)
    except Exception as e:
        logger.warning("Database connection failed: %s", e)
        return None


def ensure_schema() -> None:
    """Verify required columns exist. Raises DbUnavailable if schema is missing."""
    conn = _get_db_connection()
    if conn is None:
        raise DbUnavailable("Cannot connect to database")

    try:
        with conn.cursor() as cursor:
            # Check entities table has entity_id
            cursor.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'entities' AND column_name = 'entity_id'
            """)
            if not cursor.fetchone():
                raise DbUnavailable("entities.entity_id column missing")

            # Check relationships table has required columns
            cursor.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'relationships' AND column_name IN ('source_entity_id', 'target_entity_id', 'relationship_type')
            """)
            cols = {row[0] for row in cursor.fetchall()}
            if not {"source_entity_id", "target_entity_id", "relationship_type"}.issubset(cols):
                raise DbUnavailable("relationships missing required columns")
    except psycopg.Error as e:
        raise DbUnavailable(f"Schema check failed: {e}") from e
    finally:
        conn.close()


def search_entity_by_name(
    name: str,
    entity_type: str | None = None,
) -> list[dict[str, Any]]:
    """Search for existing entities by name, optionally filtering by type.

    Raises DbUnavailable on connection/query failure.
    """
    conn = _get_db_connection()
    if conn is None:
        raise DbUnavailable("No database connection available")

    try:
        with conn.cursor() as cursor:
            if entity_type:
                cursor.execute(
                    """
                    SELECT entity_id, name, entity_type, wikidata_id
                    FROM entities
                    WHERE name ILIKE %s AND entity_type = %s
                    LIMIT 10
                    """,
                    (f"%{name}%", entity_type),
                )
            else:
                cursor.execute(
                    """
                    SELECT entity_id, name, entity_type, wikidata_id
                    FROM entities
                    WHERE name ILIKE %s
                    LIMIT 10
                    """,
                    (f"%{name}%",),
                )
            rows = cursor.fetchall()
            return [
                {
                    "entity_id": row[0],
                    "name": row[1],
                    "entity_type": row[2],
                    "wikidata_id": row[3],
                }
                for row in rows
            ]
    except psycopg.Error as e:
        logger.warning("DB query failed for search_entity_by_name: %s", e)
        raise DbUnavailable(f"Query failed: {e}") from e
    finally:
        conn.close()


def search_entity_by_wikidata_id(wikidata_id: str) -> list[dict[str, Any]]:
    """Search for existing entity by Wikidata QID.

    Raises DbUnavailable on connection/query failure.
    """
    conn = _get_db_connection()
    if conn is None:
        raise DbUnavailable("No database connection available")

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT entity_id, name, entity_type, wikidata_id
                FROM entities
                WHERE wikidata_id = %s
                LIMIT 1
                """,
                (wikidata_id,),
            )
            row = cursor.fetchone()
            if row:
                return [{"entity_id": row[0], "name": row[1], "entity_type": row[2], "wikidata_id": row[3]}]
            return []
    except psycopg.Error as e:
        logger.warning("DB query failed for search_entity_by_wikidata_id: %s", e)
        raise DbUnavailable(f"Query failed: {e}") from e
    finally:
        conn.close()


def search_relationship_by_labels(
    source_label: str,
    target_label: str,
    relationship_type: str,
) -> list[dict[str, Any]]:
    """Search for a relationship by source/target labels and type.

    Raises DbUnavailable on connection/query failure.
    Returns list with relationship_id if found, or empty list.
    """
    conn = _get_db_connection()
    if conn is None:
        raise DbUnavailable("No database connection available")

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.relationship_id, r.source_entity_id, r.target_entity_id, r.relationship_type
                FROM relationships r
                JOIN entities src ON r.source_entity_id = src.entity_id
                JOIN entities tgt ON r.target_entity_id = tgt.entity_id
                WHERE src.name = %s AND tgt.name = %s AND r.relationship_type = %s
                LIMIT 1
                """,
                (source_label, target_label, relationship_type),
            )
            row = cursor.fetchone()
            if row:
                return [{"relationship_id": row[0], "source_entity_id": row[1], "target_entity_id": row[2], "relationship_type": row[3]}]
            return []
    except psycopg.Error as e:
        logger.warning("DB query failed for search_relationship_by_labels: %s", e)
        raise DbUnavailable(f"Query failed: {e}") from e
    finally:
        conn.close()
