from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from pipeline.agent.config import AgentConfig
from pipeline.agent.log_config import get_logger

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


def run_artisan_command(cmd: list[str], timeout: int | None = None) -> dict[str, Any]:
    """Run an artisan command and capture output.

    Returns a dict with returncode, stdout, stderr. On timeout, returns
    returncode=124 with stderr="timeout".
    """
    cfg = AgentConfig()
    timeout = timeout or cfg.artisan_timeout
    logger.info("Running: %s (timeout=%ds)", " ".join(cmd), timeout)
    t0 = __import__("time").time()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        elapsed = __import__("time").time() - t0
        logger.warning("Timeout after %.1fs", elapsed)
        return {"returncode": 124, "stdout": "", "stderr": "timeout"}
    elapsed = __import__("time").time() - t0
    logger.info("Completed (%.1fs) returncode=%d stdout=%s stderr=%s",
                elapsed, result.returncode, result.stdout[:200], result.stderr[:200])
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
