from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from pipeline.agent.logging import get_logger

logger = get_logger(__name__)


def build_artisan_command(
    command: str,
    *args: str,
    sync: bool = False,
    batch_id: str | None = None,
) -> list[str]:
    """Build a Laravel artisan command as a list of strings for subprocess.

    Example:
        build_artisan_command("pipeline:import", "/tmp/ents.jsonl", sync=True, batch_id="run_123")
        → ["docker", "compose", "-f", "docker/docker-compose.yml", "exec", "app", "php", "artisan", "pipeline:import", "/tmp/ents.jsonl", "--sync", "--batch-id=run_123"]
    """
    cmd = [
        "docker", "compose", "-f", "docker/docker-compose.yml",
        "exec", "app", "php", "artisan",
        command,
    ]
    cmd.extend(args)
    if sync:
        cmd.append("--sync")
    if batch_id:
        cmd.append(f"--batch-id={batch_id}")
    return cmd


def run_artisan_command(cmd: list[str]) -> dict[str, Any]:
    """Run an artisan command and capture output."""
    logger.info("Running: %s", " ".join(cmd))
    t0 = __import__("time").time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = __import__("time").time() - t0
    logger.info("Completed (%.1fs) returncode=%d stdout=%s stderr=%s",
                elapsed, result.returncode, result.stdout[:200], result.stderr[:200])
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
