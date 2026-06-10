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
