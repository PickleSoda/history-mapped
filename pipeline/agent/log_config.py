"""Shared logging configuration for the agent pipeline.

Call configure_logging() once at startup. Import get_logger(name) in each module.
"""

from __future__ import annotations

import logging
import sys
import time
from functools import wraps
from typing import Callable, Any

_configured = False


def configure_logging(level: int = logging.INFO) -> None:
    """Set up root logging with a clean format. Idempotent."""
    global _configured
    if _configured:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    # Avoid duplicate handlers
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        root.addHandler(handler)

    # Suppress noisy third-party logs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("langgraph").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a module."""
    return logging.getLogger(name)


def log_node_start_end(logger: logging.Logger) -> Callable:
    """Decorator that logs node entry/exit with timing."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(state, *args, **kwargs):
            node_name = func.__name__
            event_count = len(state.get("parsed_events", []))
            entity_count = len(state.get("candidate_entities", []))
            enriched_count = len(state.get("enriched_entities", []))
            logger.info(
                ">>> ENTER %s (events=%d entities=%d enriched=%d)",
                node_name, event_count, entity_count, enriched_count,
            )
            t0 = time.time()
            try:
                result = func(state, *args, **kwargs)
            except Exception as exc:
                logger.error(
                    "!!! ERROR %s after %.1fs: %s: %s",
                    node_name, time.time() - t0,
                    type(exc).__name__, exc,
                )
                raise
            elapsed = time.time() - t0
            logger.info(
                "<<< EXIT  %s (%.1fs) errors=%d",
                node_name, elapsed, len(result.get("errors", [])),
            )
            return result
        return wrapper
    return decorator