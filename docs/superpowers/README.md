# Superpowers — Agent-Driven Specs & Plans (Current Cycle)

Design specs and implementation plans produced by the agent-driven workflow
(brainstorm → spec → plan → subagent execution). **Only the current cycle lives here** —
shipped work moves to [../archive/superpowers-plans/](../archive/superpowers-plans/) and
[../archive/superpowers-specs/](../archive/superpowers-specs/).

Execution status for everything in this folder is tracked in
[../plans/STATUS.md](../plans/STATUS.md) (checkboxes inside plan files are not authoritative).

## Layout & naming

| Folder | Contents | Naming |
|--------|----------|--------|
| [specs/](specs/) | Design specs — the *what and why*, agreed before implementation. | `YYYY-MM-DD-<topic>-design.md` |
| [plans/](plans/) | Implementation plans — ordered, testable tasks executed by subagents. | `YYYY-MM-DD-<feature>.md` |

A plan is normally paired with a same-topic spec. Some specs are forward-looking and have no
plan yet — STATUS.md lists these under "Design specs without an active plan".

## Lifecycle

1. Spec written and approved → `specs/YYYY-MM-DD-<topic>-design.md`.
2. Plan written from the spec → `plans/YYYY-MM-DD-<feature>.md`.
3. Plan executed task-by-task (subagent-driven), merged to `develop`.
4. On ship: move the plan **and its spec** to `../archive/`, update `../plans/STATUS.md`.
