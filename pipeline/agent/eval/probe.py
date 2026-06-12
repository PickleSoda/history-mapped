"""Database probes for the eval harness.

Reads the persisted entities / relationships / chronicles back out of Postgres
so the report reflects what ACTUALLY landed in the database — the ground truth
that exposes false-success (committed_count says N, DB has 0).

Connects with DATABASE_URL (loaded from pipeline/.env via pipeline.config).
"""
from __future__ import annotations

import os
from typing import Any

import psycopg


def _connect():
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError(
            "DATABASE_URL is not set. Import pipeline.config first (loads pipeline/.env)."
        )
    return psycopg.connect(dsn)


def _rows(cursor) -> list[dict[str, Any]]:
    cols = [c.name for c in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def probe_entities() -> list[dict[str, Any]]:
    sql = """
        SELECT
            e.name,
            e.entity_type AS entity_type,
            e.entity_group AS entity_group,
            e.wikidata_id,
            e.verification_status AS verification_status,
            (
                SELECT tr.start_date
                FROM entity_temporal_ranges tr
                WHERE tr.entity_id = e.entity_id AND tr.is_primary
                LIMIT 1
            ) AS temporal_start,
            (
                EXISTS (
                    SELECT 1 FROM entity_locations l
                    WHERE l.entity_id = e.entity_id
                      AND (l.geom IS NOT NULL OR l.territory_geom IS NOT NULL)
                )
                OR EXISTS (
                    SELECT 1 FROM geometry_periods g
                    WHERE g.entity_id = e.entity_id
                      AND (g.geom IS NOT NULL OR g.territory_geom IS NOT NULL)
                )
            ) AS has_geometry
        FROM entities e
        ORDER BY e.name
    """
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql)
        return _rows(cur)


def probe_relationships() -> list[dict[str, Any]]:
    sql = """
        SELECT
            s.name AS source_name,
            s.entity_type AS source_entity_type,
            t.name AS target_name,
            t.entity_type AS target_entity_type,
            r.relationship_type AS relationship_type,
            r.confidence AS confidence,
            r.created_by AS created_by
        FROM relationships r
        JOIN entities s ON s.entity_id = r.source_entity_id
        JOIN entities t ON t.entity_id = r.target_entity_id
        ORDER BY s.name, r.relationship_type, t.name
    """
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql)
        return _rows(cur)


def probe_chronicles() -> list[dict[str, Any]]:
    sql = """
        SELECT
            c.title,
            c.slug,
            c.status,
            (SELECT count(*) FROM chronicle_entries ce
                WHERE ce.chronicle_id = c.chronicle_id) AS entry_count,
            (SELECT count(*) FROM chronicle_entries ce
                WHERE ce.chronicle_id = c.chronicle_id
                  AND ce.primary_relationship_id IS NULL) AS orphan_count,
            (SELECT count(*) FROM chronicle_entries ce
                JOIN chronicle_entry_entities cee ON cee.entry_id = ce.entry_id
                WHERE ce.chronicle_id = c.chronicle_id) AS secondary_links
        FROM chronicles c
        ORDER BY c.title
    """
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql)
        return _rows(cur)


def probe_counts() -> dict[str, int]:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                (SELECT count(*) FROM entities) AS entities,
                (SELECT count(*) FROM relationships) AS relationships,
                (SELECT count(*) FROM chronicles) AS chronicles,
                (SELECT count(*) FROM chronicle_entries) AS chronicle_entries,
                (SELECT count(*) FROM chronicle_entry_entities) AS chronicle_entry_entities
            """
        )
        return _rows(cur)[0]
