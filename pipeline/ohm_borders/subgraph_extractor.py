from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any


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


def _normalize_optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None