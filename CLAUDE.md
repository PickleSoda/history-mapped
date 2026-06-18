<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **history-mapped** (9921 symbols, 18824 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> Index stale? Run `node .gitnexus/run.cjs analyze` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? `npx gitnexus analyze` (npm 11 crash → `npm i -g gitnexus`; #1939).

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows. For regression review, compare against the default branch: `detect_changes({scope: "compare", base_ref: "main"})`.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit changes without running `detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/history-mapped/context` | Codebase overview, check index freshness |
| `gitnexus://repo/history-mapped/clusters` | All functional areas |
| `gitnexus://repo/history-mapped/processes` | All execution flows |
| `gitnexus://repo/history-mapped/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->

# Documentation Map

Project docs live under [`docs/`](docs/) and are kept tidy — start at [`docs/README.md`](docs/README.md),
the master index. Layout:

| Folder | What's there |
|--------|--------------|
| [`docs/architecture/`](docs/architecture/) | How it's built: `system-overview`, `frontend-app`, `data-pipeline`, `admin-map-editor`, `ohm-integration`. |
| [`docs/implementation-docs/`](docs/implementation-docs/) | Operator runbooks: setup, deployment, agentic + OHM pipelines, data contribution. |
| [`docs/entity-model/`](docs/entity-model/) | Canonical data model — `entity-specification.md` is the single source of truth for the 30 types / 5 groups. |
| [`docs/schemas/`](docs/schemas/) | Pipeline-artifact and API payload contracts. |
| [`docs/plans/`](docs/plans/) | Live roadmap/backlog. [`docs/plans/STATUS.md`](docs/plans/STATUS.md) is the **verified** per-plan status index. |
| [`docs/superpowers/`](docs/superpowers/) | Agent-driven design `specs/` + implementation `plans/` (current cycle only). |
| [`docs/reference/`](docs/reference/) | Forward-looking design references — **not** the live app. |
| [`docs/archive/`](docs/archive/) | Completed/superseded docs; history only, not source of truth. |
| [`docs/TODO.md`](docs/TODO.md) | Fine-grained engineering backlog not owned by a plan. |

Conventions when writing docs here:

- New design specs → `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`; implementation plans → `docs/superpowers/plans/YYYY-MM-DD-<feature>.md` (per the `brainstorming` / `writing-plans` skills).
- When a plan ships, move it (and its spec) to `docs/archive/` and update `docs/plans/STATUS.md`.
- Filenames are kebab-case. Code is the source of truth; then the relevant doc; then `STATUS.md`.
