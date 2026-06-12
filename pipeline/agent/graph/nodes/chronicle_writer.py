from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pipeline.agent.config import AgentConfig
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.relations import CommittedChange
from pipeline.agent.schemas.validation import AuditEvent, PipelineError
from pipeline.agent.log_config import get_logger
from pipeline.agent.tools.app_api import build_artisan_command, run_artisan_command

logger = get_logger(__name__)


def chronicle_writer(state: AgentRunState) -> AgentRunState:
    """Write the chronicle as a JSON artifact and import to DB.

    Writes to api/storage/app/pipeline/agent_runs/<run_id>/chronicle.json
    then invokes `chronicles:import` to persist to database.
    """
    cfg = AgentConfig()
    output_root = Path(cfg.output_dir) / state["run_id"]
    output_root.mkdir(parents=True, exist_ok=True)

    chronicle = state.get("chronicle")
    if chronicle is None:
        return state

    chronicle_path = output_root / "chronicle.json"
    with chronicle_path.open("w", encoding="utf-8") as f:
        f.write(chronicle.model_dump_json(indent=2))

    # Use container-visible absolute path for artisan command
    container_path = cfg.container_output_dir
    container_chronicle_path = f"{container_path}/{state['run_id']}/chronicle.json"

    cmd = build_artisan_command("chronicles:import", container_chronicle_path, sync=True)
    logger.info("Importing chronicle: %s", " ".join(cmd))
    result = run_artisan_command(cmd)
    logger.info("Chronicle import result: returncode=%d stdout=%s stderr=%s",
                result["returncode"], result["stdout"][:200], result["stderr"][:200])

    # Gate on returncode - only record committed if successful
    if result["returncode"] == 0:
        state["committed"].append(
            CommittedChange(
                change_type="chronicle",
                record={"path": str(chronicle_path), "entry_count": len(chronicle.entries)},
                committed_at=datetime.now(timezone.utc).isoformat(),
                batch_id=state["run_id"],
            )
        )
    else:
        state["errors"].append(PipelineError(
            node="chronicle_writer",
            error_type="import_failed",
            message=f"Chronicle import failed with returncode {result['returncode']}",
            context={"stderr": result["stderr"][:500]},
        ))

    state["audit_log"].append(
        AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            node="chronicle_writer",
            action="chronicle_written",
            output_summary=f"Wrote chronicle with {len(chronicle.entries)} entries to {chronicle_path}",
        )
    )
    return state
