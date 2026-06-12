"""Node wrapper for error capture and structured returns."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from pipeline.agent.schemas.validation import PipelineError

logger = logging.getLogger(__name__)


def with_error_capture(node_fn: Callable) -> Callable:
    """Wrap a node function to catch exceptions and record a PipelineError.

    On exception, appends the error to the state's ``errors`` list and returns
    the FULL state. The state channels use replace semantics (no operator.add
    reducer — see state.py), so returning the full state preserves every other
    channel and avoids the per-node list duplication that a partial update would
    cause. Downstream nodes still run; callers inspect ``errors`` to decide on
    failure handling.
    """
    @functools.wraps(node_fn)
    def wrapper(state: dict[str, Any]) -> dict[str, Any]:
        try:
            return node_fn(state)
        except Exception as e:
            logger.exception("Node %s failed: %s", node_fn.__name__, e)
            errors = state.get("errors")
            if errors is None:
                errors = []
                state["errors"] = errors
            errors.append(PipelineError(
                node=node_fn.__name__,
                error_type=type(e).__name__,
                message=str(e),
            ))
            return state
    return wrapper