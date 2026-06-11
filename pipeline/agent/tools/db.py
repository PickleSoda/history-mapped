from __future__ import annotations

import os
from typing import Any

try:
    import psycopg
    HAS_PSYCOPG = True
except ImportError:
    HAS_PSYCOPG = False


def _get_db_connection():
    """Get a direct DB connection using DATABASE_URL from env."""
    if not HAS_PSYCOPG:
        return None
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        return None
    try:
        return psycopg.connect(db_url)
    except Exception:
        return None


def search_entity_by_name(
    name: str,
    entity_type: str | None = None,
) -> list[dict[str, Any]]:
    """Search for existing entities by name, optionally filtering by type."""
    conn = _get_db_connection()
    if conn is None:
        return []

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
    except Exception:
        return []
    finally:
        conn.close()


def search_entity_by_wikidata_id(wikidata_id: str) -> list[dict[str, Any]]:
    """Search for existing entity by Wikidata QID."""
    conn = _get_db_connection()
    if conn is None:
        return []

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
    except Exception:
        return []
    finally:
        conn.close()


def search_relationship_by_labels(
    source_label: str,
    target_label: str,
    relationship_type: str,
) -> list[dict[str, Any]]:
    """Search for a relationship by source/target labels and type.

    Returns list with relationship_id if found, or empty list.
    """
    conn = _get_db_connection()
    if conn is None:
        return []

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.id, r.source_id, r.target_id, r.relationship_type
                FROM relationships r
                JOIN entities src ON r.source_id = src.entity_id
                JOIN entities tgt ON r.target_id = tgt.entity_id
                WHERE src.name = %s AND tgt.name = %s AND r.relationship_type = %s
                LIMIT 1
                """,
                (source_label, target_label, relationship_type),
            )
            row = cursor.fetchone()
            if row:
                return [{"relationship_id": row[0], "source_id": row[1], "target_id": row[2], "relationship_type": row[3]}]
            return []
    except Exception:
        return []
    finally:
        conn.close()
