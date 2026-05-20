"""Compatibility facade for OHM border stage entrypoints."""

from pipeline.ohm_borders.stage_build import run_build_stage
from pipeline.ohm_borders.stage_common import (
    default_parallelism,
    manifest_path_for,
    plan_parsed_shards,
    resolve_artifact_dir,
    resolve_run_id,
)
from pipeline.ohm_borders.stage_enrich import run_enrich_stage
from pipeline.ohm_borders.stage_extract_subgraph import run_extract_subgraph_stage
from pipeline.ohm_borders.stage_fetch import run_fetch_stage
from pipeline.ohm_borders.stage_parse import run_parse_stage
from pipeline.ohm_borders.stage_relations import (
    run_relations_build_stage,
    run_relations_enrich_stage,
    run_relations_scan_stage,
)

__all__ = [
    "default_parallelism",
    "manifest_path_for",
    "plan_parsed_shards",
    "resolve_artifact_dir",
    "resolve_run_id",
    "run_build_stage",
    "run_enrich_stage",
    "run_extract_subgraph_stage",
    "run_fetch_stage",
    "run_parse_stage",
    "run_relations_build_stage",
    "run_relations_enrich_stage",
    "run_relations_scan_stage",
]
