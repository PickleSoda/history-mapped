from __future__ import annotations

import json
import sqlite3
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import unicodedata

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover - fallback for environments without optional dependency installed yet.
    fuzz = None


_LINK_TAG_KEYS: tuple[str, ...] = (
    "predecessor:wikidata",
    "preceded_by:wikidata",
    "successor:wikidata",
    "succeeded_by:wikidata",
    "start_event:wikidata",
    "end_event:wikidata",
)


class SeedResolutionError(ValueError):
    pass


@dataclass(frozen=True)
class _TraversalSeed:
    relation_ids: tuple[int, ...]
    wikidata_id: str | None
    name: str | None


def extract_country_subgraph(
    overpass_payload: dict[str, Any],
    *,
    seed_qid: str | None = None,
    seed_name: str | None = None,
    max_depth: int,
    max_nodes: int,
) -> dict[str, Any]:
    if max_depth < 0:
        raise ValueError("max_depth must be >= 0")
    if max_nodes < 1:
        raise ValueError("max_nodes must be >= 1")

    relation_index = _relation_index(overpass_payload.get("elements", []))
    chronology_members = _chronology_members(relation_index)
    qid_index = _qid_index(relation_index)
    seed = _resolve_seed(relation_index, qid_index, seed_qid=seed_qid, seed_name=seed_name)

    included_ids, truncation_reasons = _walk_subgraph(
        relation_index,
        chronology_members,
        qid_index,
        seed,
        max_depth=max_depth,
        max_nodes=max_nodes,
    )
    included_relations = [relation_index[relation_id] for relation_id in included_ids]
    missing_wikidata_ids = _missing_linked_wikidata_ids(included_relations, qid_index)

    closure_report = {
        "included_relation_ids": list(included_ids),
        "included_relation_count": len(included_ids),
        "truncated": bool(truncation_reasons),
        "truncation_reasons": truncation_reasons,
        "missing_wikidata_ids": missing_wikidata_ids,
        "unresolved_references": missing_wikidata_ids,
        "traversal": {
            "seed_qid": seed.wikidata_id,
            "seed_name": seed.name,
            "max_depth": max_depth,
            "max_nodes": max_nodes,
        },
    }

    return {
        "seed": {
            "wikidata_id": seed.wikidata_id,
            "name": seed.name,
            "relation_ids": list(seed.relation_ids),
        },
        "reduced_payload": {
            **{key: value for key, value in overpass_payload.items() if key != "elements"},
            "elements": included_relations,
        },
        "graph_edges": _graph_edges(included_relations, qid_index),
        "closure_report": closure_report,
    }


def extract_country_subgraph_from_index(
    index_path: str | Path,
    *,
    seed_qid: str | None = None,
    seed_name: str | None = None,
    max_depth: int,
    max_nodes: int,
    auto_select_fuzzy: bool = False,
) -> dict[str, Any]:
    if max_depth < 0:
        raise ValueError("max_depth must be >= 0")
    if max_nodes < 1:
        raise ValueError("max_nodes must be >= 1")

    with sqlite3.connect(Path(index_path)) as connection:
        seed = _resolve_index_seed_from_connection(
            connection,
            seed_qid=seed_qid,
            seed_name=seed_name,
            auto_select_fuzzy=auto_select_fuzzy,
        )
        included_ids, truncation_reasons, relation_cache = _walk_indexed_subgraph(
            connection,
            seed,
            max_depth=max_depth,
            max_nodes=max_nodes,
        )
        included_relations = [relation_cache[relation_id] for relation_id in included_ids]
        qid_index = _qid_index_for_included_relations(connection, included_relations)
        missing_wikidata_ids = _missing_linked_wikidata_ids(included_relations, qid_index)

    closure_report = {
        "included_relation_ids": list(included_ids),
        "included_relation_count": len(included_ids),
        "truncated": bool(truncation_reasons),
        "truncation_reasons": truncation_reasons,
        "missing_wikidata_ids": missing_wikidata_ids,
        "unresolved_references": missing_wikidata_ids,
        "traversal": {
            "seed_qid": seed.wikidata_id,
            "seed_name": seed.name,
            "max_depth": max_depth,
            "max_nodes": max_nodes,
        },
    }

    return {
        "seed": {
            "wikidata_id": seed.wikidata_id,
            "name": seed.name,
            "relation_ids": list(seed.relation_ids),
        },
        "reduced_payload": {"elements": included_relations},
        "graph_edges": _graph_edges(included_relations, qid_index),
        "closure_report": closure_report,
    }


def resolve_country_subgraph_seed_from_index(
    index_path: str | Path,
    *,
    seed_qid: str | None = None,
    seed_name: str | None = None,
    auto_select_fuzzy: bool = False,
) -> dict[str, Any]:
    with sqlite3.connect(Path(index_path)) as connection:
        seed = _resolve_index_seed_from_connection(
            connection,
            seed_qid=seed_qid,
            seed_name=seed_name,
            auto_select_fuzzy=auto_select_fuzzy,
        )

    return {
        "wikidata_id": seed.wikidata_id,
        "name": seed.name,
        "relation_ids": list(seed.relation_ids),
    }


def validate_bundle_closure(
    *,
    main_entities: list[dict[str, Any]],
    relation_entities: list[dict[str, Any]],
    relation_hints: list[dict[str, Any]],
) -> dict[str, Any]:
    known_wikidata_ids = sorted(
        {
            wikidata_id
            for wikidata_id in [_extract_wikidata_id(record) for record in [*main_entities, *relation_entities]]
            if wikidata_id is not None
        }
    )
    known_set = set(known_wikidata_ids)

    referenced_ids = {
        wikidata_id
        for hint in relation_hints
        for wikidata_id in (
            _normalize_optional_string(hint.get("source_wikidata_id")),
            _normalize_optional_string(hint.get("target_wikidata_id")),
        )
        if wikidata_id is not None
    }
    missing_wikidata_ids = sorted(referenced_ids - known_set)

    return {
        "import_ready": not missing_wikidata_ids,
        "known_wikidata_ids": known_wikidata_ids,
        "missing_wikidata_ids": missing_wikidata_ids,
    }


def _relation_index(elements: Any) -> dict[int, dict[str, Any]]:
    relation_index: dict[int, dict[str, Any]] = {}
    if not isinstance(elements, list):
        return relation_index

    for element in elements:
        if not isinstance(element, dict) or element.get("type") != "relation" or "id" not in element:
            continue
        try:
            relation_id = int(element["id"])
        except (TypeError, ValueError):
            continue
        relation_index[relation_id] = {**element, "id": relation_id}

    return relation_index


def _chronology_members(relation_index: dict[int, dict[str, Any]]) -> dict[int, set[int]]:
    memberships: dict[int, set[int]] = {}

    for relation_id, relation in relation_index.items():
        tags = relation.get("tags", {}) or {}
        if tags.get("type") != "chronology":
            continue

        memberships.setdefault(relation_id, set())
        for member in relation.get("members", []) or []:
            if member.get("type") != "relation" or "ref" not in member:
                continue
            try:
                member_id = int(member["ref"])
            except (TypeError, ValueError):
                continue

            memberships[relation_id].add(member_id)
            memberships.setdefault(member_id, set()).add(relation_id)

    return memberships


def _qid_index(relation_index: dict[int, dict[str, Any]]) -> dict[str, list[int]]:
    mapping: dict[str, list[int]] = {}

    for relation_id, relation in relation_index.items():
        wikidata_id = _normalize_optional_string((relation.get("tags", {}) or {}).get("wikidata"))
        if wikidata_id is None:
            continue
        mapping.setdefault(wikidata_id, []).append(relation_id)

    for relation_ids in mapping.values():
        relation_ids.sort()

    return mapping


def _resolve_seed(
    relation_index: dict[int, dict[str, Any]],
    qid_index: dict[str, list[int]],
    *,
    seed_qid: str | None,
    seed_name: str | None,
) -> _TraversalSeed:
    normalized_seed_qid = _normalize_optional_string(seed_qid)
    if normalized_seed_qid is not None:
        relation_ids = tuple(qid_index.get(normalized_seed_qid, []))
        if not relation_ids:
            raise SeedResolutionError(f"No seed relation found for Wikidata ID: {normalized_seed_qid}")
        name = _normalize_optional_string((relation_index[relation_ids[0]].get("tags", {}) or {}).get("name"))
        return _TraversalSeed(relation_ids=relation_ids, wikidata_id=normalized_seed_qid, name=name)

    normalized_seed_name = _normalize_optional_string(seed_name)
    if normalized_seed_name is None:
        raise SeedResolutionError("A seed_qid or seed_name is required")

    matches = [
        relation_id
        for relation_id, relation in relation_index.items()
        if _normalize_optional_string((relation.get("tags", {}) or {}).get("name")) == normalized_seed_name
    ]

    if not matches:
        raise SeedResolutionError(f"No seed relation found for exact name: {normalized_seed_name}")
    if len(matches) > 1:
        raise SeedResolutionError(f"Ambiguous seed name: {normalized_seed_name}")

    relation = relation_index[matches[0]]
    return _TraversalSeed(
        relation_ids=(matches[0],),
        wikidata_id=_normalize_optional_string((relation.get("tags", {}) or {}).get("wikidata")),
        name=normalized_seed_name,
    )


def _resolve_index_seed(
    relation_index: dict[int, dict[str, Any]],
    qid_index: dict[str, list[int]],
    *,
    seed_qid: str | None,
    seed_name: str | None,
    auto_select_fuzzy: bool,
) -> _TraversalSeed:
    normalized_seed_qid = _normalize_optional_string(seed_qid)
    if normalized_seed_qid is not None:
        relation_ids = tuple(qid_index.get(normalized_seed_qid, []))
        if not relation_ids:
            raise SeedResolutionError(f"No seed relation found for Wikidata ID: {normalized_seed_qid}")
        name = _normalize_optional_string((relation_index[relation_ids[0]].get("tags", {}) or {}).get("name"))
        return _TraversalSeed(relation_ids=relation_ids, wikidata_id=normalized_seed_qid, name=name)

    normalized_seed_name = _normalize_search_name(seed_name)
    if normalized_seed_name is None:
        raise SeedResolutionError("A seed_qid or seed_name is required")

    exact_matches = [
        relation_id
        for relation_id, relation in relation_index.items()
        if _normalize_search_name((relation.get("tags", {}) or {}).get("name")) == normalized_seed_name
    ]
    if exact_matches:
        if len(exact_matches) > 1:
            raise SeedResolutionError(f"Ambiguous seed name: {seed_name.strip() if isinstance(seed_name, str) else normalized_seed_name}")
        relation = relation_index[exact_matches[0]]
        resolved_name = _normalize_optional_string((relation.get("tags", {}) or {}).get("name"))
        resolved_wikidata_id = _normalize_optional_string((relation.get("tags", {}) or {}).get("wikidata"))
        resolved_relation_ids = (
            tuple(qid_index.get(resolved_wikidata_id, [])) if resolved_wikidata_id is not None else (exact_matches[0],)
        )
        return _TraversalSeed(
            relation_ids=resolved_relation_ids or (exact_matches[0],),
            wikidata_id=resolved_wikidata_id,
            name=resolved_name,
        )

    candidates = _fuzzy_seed_candidates(relation_index, normalized_seed_name)
    if auto_select_fuzzy and candidates:
        selected_relation = relation_index[candidates[0]["relation_id"]]
        return _TraversalSeed(
            relation_ids=(candidates[0]["relation_id"],),
            wikidata_id=_normalize_optional_string((selected_relation.get("tags", {}) or {}).get("wikidata")),
            name=_normalize_optional_string((selected_relation.get("tags", {}) or {}).get("name")),
        )

    if candidates:
        suggestion_names = ", ".join(candidate["name"] for candidate in candidates)
        raise SeedResolutionError(f"No seed relation found for exact name: {seed_name}. Suggestions: {suggestion_names}")

    raise SeedResolutionError(f"No seed relation found for exact name: {seed_name}")


def _resolve_index_seed_from_connection(
    connection: sqlite3.Connection,
    *,
    seed_qid: str | None,
    seed_name: str | None,
    auto_select_fuzzy: bool,
) -> _TraversalSeed:
    normalized_seed_qid = _normalize_optional_string(seed_qid)
    if normalized_seed_qid is not None:
        relation_ids = tuple(_relation_ids_for_qid(connection, normalized_seed_qid))
        if not relation_ids:
            raise SeedResolutionError(f"No seed relation found for Wikidata ID: {normalized_seed_qid}")
        name = _relation_name_for_id(connection, relation_ids[0])
        return _TraversalSeed(relation_ids=relation_ids, wikidata_id=normalized_seed_qid, name=name)

    normalized_seed_name = _normalize_search_name(seed_name)
    if normalized_seed_name is None:
        raise SeedResolutionError("A seed_qid or seed_name is required")

    exact_matches = [
        int(relation_id)
        for (relation_id,) in connection.execute(
            "SELECT relation_id FROM relations WHERE normalized_name = ? ORDER BY relation_id",
            (normalized_seed_name,),
        )
    ]
    if exact_matches:
        if len(exact_matches) > 1:
            raise SeedResolutionError(f"Ambiguous seed name: {seed_name.strip() if isinstance(seed_name, str) else normalized_seed_name}")
        relation_id = exact_matches[0]
        row = connection.execute(
            "SELECT name, wikidata_id FROM relations WHERE relation_id = ?",
            (relation_id,),
        ).fetchone()
        if row is None:
            raise SeedResolutionError(f"No seed relation found for exact name: {seed_name}")
        resolved_name = _normalize_optional_string(row[0])
        resolved_wikidata_id = _normalize_optional_string(row[1])
        resolved_relation_ids = (
            tuple(_relation_ids_for_qid(connection, resolved_wikidata_id)) if resolved_wikidata_id is not None else (relation_id,)
        )
        return _TraversalSeed(
            relation_ids=resolved_relation_ids or (relation_id,),
            wikidata_id=resolved_wikidata_id,
            name=resolved_name,
        )

    fuzzy_threshold = _read_fuzzy_threshold(connection)
    candidates = _fuzzy_seed_candidates_from_connection(
        connection,
        normalized_seed_name,
        limit=5,
        minimum_score=fuzzy_threshold,
    )
    if auto_select_fuzzy and candidates and _has_clear_best_candidate(candidates):
        selected_candidate = candidates[0]
        resolved_wikidata_id = _normalize_optional_string(selected_candidate.get("wikidata_id"))
        resolved_relation_ids = (
            tuple(_relation_ids_for_qid(connection, resolved_wikidata_id))
            if resolved_wikidata_id is not None
            else (int(selected_candidate["relation_id"]),)
        )
        return _TraversalSeed(
            relation_ids=resolved_relation_ids or (int(selected_candidate["relation_id"]),),
            wikidata_id=resolved_wikidata_id,
            name=_normalize_optional_string(selected_candidate.get("name")),
        )

    if candidates:
        suggestion_names = ", ".join(str(candidate["name"]) for candidate in candidates)
        raise SeedResolutionError(f"No seed relation found for exact name: {seed_name}. Suggestions: {suggestion_names}")

    raise SeedResolutionError(f"No seed relation found for exact name: {seed_name}")


def _walk_subgraph(
    relation_index: dict[int, dict[str, Any]],
    chronology_members: dict[int, set[int]],
    qid_index: dict[str, list[int]],
    seed: _TraversalSeed,
    *,
    max_depth: int,
    max_nodes: int,
) -> tuple[list[int], list[str]]:
    visited: set[int] = set()
    ordered_ids: list[int] = []
    truncation_reasons: list[str] = []
    queue: deque[tuple[int, int]] = deque((relation_id, 0) for relation_id in seed.relation_ids)

    while queue:
        relation_id, depth = queue.popleft()
        if relation_id in visited:
            continue

        if len(ordered_ids) >= max_nodes:
            truncation_reasons.append(f"max_nodes:{max_nodes}")
            break

        visited.add(relation_id)
        ordered_ids.append(relation_id)

        if depth >= max_depth:
            continue

        for neighbor_id in _neighbor_relation_ids(relation_index[relation_id], chronology_members, qid_index):
            if neighbor_id in relation_index and neighbor_id not in visited:
                queue.append((neighbor_id, depth + 1))

    if any(depth >= max_depth and relation_id not in visited for relation_id, depth in queue):
        truncation_reasons.append(f"max_depth:{max_depth}")
    elif queue:
        truncation_reasons.append(f"max_depth:{max_depth}")

    return sorted(ordered_ids), sorted(set(truncation_reasons))


def _neighbor_relation_ids(
    relation: dict[str, Any],
    chronology_members: dict[int, set[int]],
    qid_index: dict[str, list[int]],
) -> set[int]:
    relation_id = int(relation["id"])
    neighbors = set(chronology_members.get(relation_id, set()))
    tags = relation.get("tags", {}) or {}

    for tag_key in _LINK_TAG_KEYS:
        linked_qid = _normalize_optional_string(tags.get(tag_key))
        if linked_qid is None:
            continue
        neighbors.update(qid_index.get(linked_qid, []))

    return neighbors


def _missing_linked_wikidata_ids(included_relations: list[dict[str, Any]], qid_index: dict[str, list[int]]) -> list[str]:
    missing: set[str] = set()

    for relation in included_relations:
        tags = relation.get("tags", {}) or {}
        for tag_key in _LINK_TAG_KEYS:
            linked_qid = _normalize_optional_string(tags.get(tag_key))
            if linked_qid is None:
                continue
            if linked_qid not in qid_index:
                missing.add(linked_qid)

    return sorted(missing)


def _graph_edges(included_relations: list[dict[str, Any]], qid_index: dict[str, list[int]]) -> list[dict[str, Any]]:
    included_ids = {int(relation["id"]) for relation in included_relations}
    edges: list[dict[str, Any]] = []

    for relation in included_relations:
        relation_id = int(relation["id"])
        tags = relation.get("tags", {}) or {}
        for tag_key in _LINK_TAG_KEYS:
            linked_qid = _normalize_optional_string(tags.get(tag_key))
            if linked_qid is None:
                continue
            for target_relation_id in qid_index.get(linked_qid, []):
                if target_relation_id in included_ids:
                    edges.append(
                        {
                            "source_relation_id": relation_id,
                            "target_relation_id": target_relation_id,
                            "source_tag_key": tag_key,
                            "target_wikidata_id": linked_qid,
                        }
                    )

    return sorted(edges, key=lambda edge: (edge["source_relation_id"], edge["source_tag_key"], edge["target_relation_id"]))


def _extract_wikidata_id(record: dict[str, Any]) -> str | None:
    return _normalize_optional_string(record.get("wikidata_id"))


def _walk_indexed_subgraph(
    connection: sqlite3.Connection,
    seed: _TraversalSeed,
    *,
    max_depth: int,
    max_nodes: int,
) -> tuple[list[int], list[str], dict[int, dict[str, Any]]]:
    visited: set[int] = set()
    ordered_ids: list[int] = []
    truncation_reasons: list[str] = []
    queue: deque[tuple[int, int]] = deque((relation_id, 0) for relation_id in seed.relation_ids)
    relation_cache: dict[int, dict[str, Any]] = {}

    while queue:
        relation_id, depth = queue.popleft()
        if relation_id in visited:
            continue

        if len(ordered_ids) >= max_nodes:
            truncation_reasons.append(f"max_nodes:{max_nodes}")
            break

        relation = _fetch_relation_payload(connection, relation_id, relation_cache)
        if relation is None:
            continue

        visited.add(relation_id)
        ordered_ids.append(relation_id)

        if depth >= max_depth:
            continue

        for neighbor_id in _indexed_neighbor_relation_ids(connection, relation_id):
            if neighbor_id not in visited:
                queue.append((neighbor_id, depth + 1))

    if any(depth >= max_depth and relation_id not in visited for relation_id, depth in queue):
        truncation_reasons.append(f"max_depth:{max_depth}")
    elif queue:
        truncation_reasons.append(f"max_depth:{max_depth}")

    return sorted(ordered_ids), sorted(set(truncation_reasons)), relation_cache


def _fetch_relation_payload(
    connection: sqlite3.Connection,
    relation_id: int,
    relation_cache: dict[int, dict[str, Any]],
) -> dict[str, Any] | None:
    if relation_id in relation_cache:
        return relation_cache[relation_id]

    row = connection.execute(
        "SELECT payload_json FROM relations WHERE relation_id = ?",
        (relation_id,),
    ).fetchone()
    if row is None:
        return None

    relation_cache[relation_id] = json.loads(row[0])
    return relation_cache[relation_id]


def _indexed_neighbor_relation_ids(connection: sqlite3.Connection, relation_id: int) -> set[int]:
    neighbors = {
        int(member_relation_id)
        for (member_relation_id,) in connection.execute(
            "SELECT member_relation_id FROM chronology_edges WHERE chronology_relation_id = ?",
            (relation_id,),
        )
    }
    neighbors.update(
        int(chronology_relation_id)
        for (chronology_relation_id,) in connection.execute(
            "SELECT chronology_relation_id FROM chronology_edges WHERE member_relation_id = ?",
            (relation_id,),
        )
    )

    linked_qids = [
        str(target_wikidata_id)
        for (target_wikidata_id,) in connection.execute(
            "SELECT target_wikidata_id FROM qid_edges WHERE source_relation_id = ?",
            (relation_id,),
        )
    ]
    if linked_qids:
        placeholders = ", ".join("?" for _ in linked_qids)
        neighbors.update(
            int(target_relation_id)
            for (target_relation_id,) in connection.execute(
                f"SELECT relation_id FROM qid_to_relations WHERE wikidata_id IN ({placeholders})",
                tuple(linked_qids),
            )
        )

    return neighbors


def _qid_index_for_included_relations(
    connection: sqlite3.Connection,
    included_relations: list[dict[str, Any]],
) -> dict[str, list[int]]:
    referenced_qids = {
        linked_qid
        for relation in included_relations
        for linked_qid in [
            _normalize_optional_string((relation.get("tags", {}) or {}).get(tag_key)) for tag_key in _LINK_TAG_KEYS
        ]
        if linked_qid is not None
    }
    for relation in included_relations:
        relation_wikidata_id = _normalize_optional_string((relation.get("tags", {}) or {}).get("wikidata"))
        if relation_wikidata_id is not None:
            referenced_qids.add(relation_wikidata_id)

    if not referenced_qids:
        return {}

    placeholders = ", ".join("?" for _ in sorted(referenced_qids))
    mapping: dict[str, list[int]] = {}
    for wikidata_id, relation_id in connection.execute(
        f"SELECT wikidata_id, relation_id FROM qid_to_relations WHERE wikidata_id IN ({placeholders}) ORDER BY wikidata_id, relation_id",
        tuple(sorted(referenced_qids)),
    ):
        mapping.setdefault(str(wikidata_id), []).append(int(relation_id))

    return mapping


def _relation_ids_for_qid(connection: sqlite3.Connection, wikidata_id: str) -> list[int]:
    return [
        int(relation_id)
        for (relation_id,) in connection.execute(
            "SELECT relation_id FROM qid_to_relations WHERE wikidata_id = ? ORDER BY relation_id",
            (wikidata_id,),
        )
    ]


def _relation_name_for_id(connection: sqlite3.Connection, relation_id: int) -> str | None:
    row = connection.execute(
        "SELECT name FROM relations WHERE relation_id = ?",
        (relation_id,),
    ).fetchone()
    if row is None:
        return None
    return _normalize_optional_string(row[0])


def _read_fuzzy_threshold(connection: sqlite3.Connection) -> float:
    row = connection.execute("SELECT fuzzy_threshold FROM index_metadata LIMIT 1").fetchone()
    if row is None:
        return 0.85
    return float(row[0])


def _indexed_graph(index_path: Path) -> tuple[dict[int, dict[str, Any]], dict[int, set[int]], dict[str, list[int]]]:
    relation_index: dict[int, dict[str, Any]] = {}
    chronology_members: dict[int, set[int]] = {}
    qid_index: dict[str, list[int]] = {}

    with sqlite3.connect(index_path) as connection:
        for relation_id, payload_json in connection.execute("SELECT relation_id, payload_json FROM relations"):
            relation_index[int(relation_id)] = json.loads(payload_json)

        for chronology_relation_id, member_relation_id in connection.execute(
            "SELECT chronology_relation_id, member_relation_id FROM chronology_edges"
        ):
            chronology_id = int(chronology_relation_id)
            member_id = int(member_relation_id)
            chronology_members.setdefault(chronology_id, set()).add(member_id)
            chronology_members.setdefault(member_id, set()).add(chronology_id)

        for wikidata_id, relation_id in connection.execute(
            "SELECT wikidata_id, relation_id FROM qid_to_relations ORDER BY wikidata_id, relation_id"
        ):
            qid_index.setdefault(str(wikidata_id), []).append(int(relation_id))

    return relation_index, chronology_members, qid_index


def _fuzzy_seed_candidates(
    relation_index: dict[int, dict[str, Any]],
    normalized_seed_name: str,
    *,
    limit: int = 3,
    minimum_score: float = 0.7,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    for relation_id, relation in relation_index.items():
        relation_name = _normalize_optional_string((relation.get("tags", {}) or {}).get("name"))
        normalized_relation_name = _normalize_search_name(relation_name)
        if relation_name is None or normalized_relation_name is None:
            continue

        score = _similarity_score(normalized_seed_name, normalized_relation_name)
        if score < minimum_score:
            continue

        candidates.append(
            {
                "relation_id": relation_id,
                "name": relation_name,
                "score": score,
            }
        )

    candidates.sort(key=lambda candidate: (-candidate["score"], candidate["name"], candidate["relation_id"]))
    return candidates[:limit]


def _fuzzy_seed_candidates_from_connection(
    connection: sqlite3.Connection,
    normalized_seed_name: str,
    *,
    limit: int,
    minimum_score: float,
    candidate_limit: int = 1000,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    prefixes = []
    if len(normalized_seed_name) >= 3:
        prefixes.append(normalized_seed_name[:3])
    if len(normalized_seed_name) >= 2:
        prefixes.append(normalized_seed_name[:2])
    if not prefixes:
        prefixes.append(normalized_seed_name)

    seen_relation_ids: set[int] = set()
    for prefix in prefixes:
        rows = connection.execute(
            """
            SELECT relation_id, name, normalized_name, wikidata_id
            FROM relations
            WHERE normalized_name LIKE ?
            ORDER BY relation_id
            LIMIT ?
            """,
            (f"{prefix}%", candidate_limit),
        ).fetchall()
        if not rows:
            continue

        for relation_id, name, normalized_name, wikidata_id in rows:
            if int(relation_id) in seen_relation_ids or normalized_name is None:
                continue
            score = _similarity_score(normalized_seed_name, str(normalized_name))
            if score < minimum_score:
                continue
            seen_relation_ids.add(int(relation_id))
            candidates.append(
                {
                    "relation_id": int(relation_id),
                    "name": str(name),
                    "wikidata_id": _normalize_optional_string(wikidata_id),
                    "score": score,
                }
            )

        if candidates:
            break

    candidates.sort(key=lambda candidate: (-candidate["score"], str(candidate["name"]), int(candidate["relation_id"])))
    return candidates[:limit]


def _has_clear_best_candidate(candidates: list[dict[str, Any]]) -> bool:
    if len(candidates) <= 1:
        return True
    return float(candidates[0]["score"]) > float(candidates[1]["score"])


def _normalize_search_name(value: Any) -> str | None:
    normalized = _normalize_optional_string(value)
    if normalized is None:
        return None
    return " ".join(unicodedata.normalize("NFC", normalized).casefold().split())


def _similarity_score(left: str, right: str) -> float:
    if fuzz is not None:
        return float(fuzz.ratio(left, right)) / 100.0

    # Fallback only if rapidfuzz is unavailable.
    from difflib import SequenceMatcher

    return SequenceMatcher(None, left, right).ratio()


def _normalize_optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None