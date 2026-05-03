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

Use GitNexus for impact-aware edits and safe refactors.

> If GitNexus reports a stale index, run `npx gitnexus analyze` (or `npx gitnexus analyze --embeddings` when embeddings are already in use).

## Required checks
- Before editing any function/class/method, run: `gitnexus_impact({target: "symbolName", direction: "upstream"})`.
- If impact risk is HIGH/CRITICAL, warn first and update all d=1 dependents before proceeding.
- Before commit, run: `gitnexus_detect_changes({scope: "staged"})`.

## Recommended usage
- Explore by concept: `gitnexus_query({query: "concept"})`
- Full symbol context: `gitnexus_context({name: "symbolName"})`
- Safe rename: `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})`, review, then `dry_run: false`

## Quick map
- Debugging: `query` -> `context` -> `gitnexus://repo/history-mapped/process/{name}`
- Refactoring: `context` -> `impact` -> edit -> `detect_changes`

## Core resources
- `gitnexus://repo/history-mapped/context`
- `gitnexus://repo/history-mapped/processes`
- `gitnexus://repo/history-mapped/process/{name}`

<!-- gitnexus:end -->
