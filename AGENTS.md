# history-mapped Development Playbook

## Core workflow (Obra Superpowers)
- Start every task with `using-superpowers` and invoke the relevant skills before implementation.
- For any feature/behavior change, run `brainstorming` first and get design agreement.
- After design, create the implementation plan with `writing-plans` in `docs/superpowers/plans/`.
- Execute plans with `subagent-driven-development` (preferred) or `executing-plans`.
- Before declaring done, run `verification-before-completion` and include command evidence.

## Runtime and environment
- Default backend runtime is Docker Compose. Prefer containerized commands over host-local PHP/Composer execution.
- Start services with: `docker compose -f docker/docker-compose.yml up -d`.
- Use `docker compose -f docker/docker-compose.yml exec app ...` for `php artisan`, PHPUnit, and framework scripts.
- Keep database-dependent work inside containers to avoid host/container drift.

## Package and workspace conventions
- This is a pnpm monorepo; use `pnpm` (not npm/yarn).
- Locate a package with: `pnpm dlx turbo run where <project_name>`.
- Install deps with package scoping when needed: `pnpm install --filter <project_name>`.
- Confirm package identity from each package-local `package.json` `name` field.

## Implementation expectations
- Prefer small, focused changes that preserve existing architecture and naming conventions.
- Use TDD for feature/bug work: write a failing test first, implement minimal fix, then expand coverage.
- Do not refactor unrelated areas while implementing scoped tasks.
- Update docs when behavior, APIs, or workflows change.

## Testing policy
- Check CI expectations in `.github/workflows` before finalizing.
- For frontend packages, run targeted checks first, then broader checks:
	- `pnpm vitest run -t "<test name>"`
	- `pnpm lint --filter <project_name>`
	- `pnpm turbo run test --filter <project_name>`
- For backend/Laravel work, run focused then suite-level tests via Docker Compose:
	- `docker compose -f docker/docker-compose.yml exec app php artisan test <path-or-filter>`
	- `docker compose -f docker/docker-compose.yml exec app php artisan test`
- Resolve all test/type/lint failures before merge.
- Add or update tests for every functional change, even if not explicitly requested.

## Planning and docs artifacts
- Design specs: `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
- Implementation plans: `docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md`
- Keep plans task-oriented with explicit files, commands, and expected outcomes.

## PR and commit standards
- PR title format: `[<project_name>] <Title>`
- Keep commits scoped and descriptive; avoid mixed-purpose commits.
- Before committing, run required lint/test commands and summarize verification in PR notes.

## Agent behavior notes
- Prefer read/verify/edit cycles with clear checkpoints.
- Use parallel reads/searches when gathering context, then apply minimal patches.
- If instructions conflict, follow explicit user instructions first, then repo playbook.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **history-mapped** (8347 symbols, 15508 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

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
