"""Node wrapper for error capture and structured returns."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from pipeline.agent.schemas.validation import PipelineError

logger = logging.getLogger(__name__)


def with_error_capture(node_fn: Callable) -> Callable:
    """Wrap a node function to catch exceptions and return PipelineError.

    On exception, returns a partial update dict with errors list and _failed flag.
    The workflow should route _failed to an error sink.
    """
    @functools.wraps(node_fn)
    def wrapper(state: dict[str, Any]) -> dict[str, Any]:
        try:
            return node_fn(state)
        except Exception as e:
            logger.exception("Node %s failed: %s", node_fn.__name__, e)
            return {
                "errors": [PipelineError(
                    node=node_fn.__name__,
                    error_type=type(e).__name__,
                    message=str(e),
                )],
                "_failed": True,
            }
    return wrapper