from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pipeline.agent.config import AgentConfig
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.relations import CommittedChange
from pipeline.agent.schemas.validation import AuditEvent
from pipeline.agent.logging import get_logger

logger = get_logger(__name__)


def chronicle_writer(state: AgentRunState) -> AgentRunState:
    """Write the chronicle as a JSON artifact.

    Writes to output/agent_runs/<run_id>/chronicle.json
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

    state["committed"].append(
        CommittedChange(
            change_type="chronicle",
            record={"path": str(chronicle_path), "entry_count": len(chronicle.entries)},
            committed_at=datetime.now(timezone.utc).isoformat(),
            batch_id=state["run_id"],
        )
    )

    state["audit_log"].append(
        AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            node="chronicle_writer",
            action="chronicle_written",
            output_summary=f"Wrote chronicle with {len(chronicle.entries)} entries to {chronicle_path}",
        )
    )
    return state
