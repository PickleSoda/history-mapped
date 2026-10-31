# Battle-map bulk run readiness — Implementation Plan

> **For agentic workers:** one agent implements this plan. Steps use checkbox (`- [ ]`) syntax.

**Goal:** a Sonnet `battle-author` subagent can turn one battle into a validated map story in about **15 minutes and under 8M billed tokens**. The five Opus samples took 29–47 min and 10–24M each. A reviewer agent checks its work cheaply, and an orchestrator can run batches from a ranked queue.

## Baseline: where the five sample runs spent their time and tokens

Deduplicated with `scripts/agent-costs.py`. The first count double-counted split API responses.

| Battle | Wall | Turns | Billed tokens | Output | Peak context |
|---|---|---|---|---|---|
| Cannae | 36 min | 64 | 11.9M | 169k | 303k |
| Gaugamela | 47 min | 87 | 18.2M | 175k | 321k |
| Salamis | 38 min | 106 | 24.1M | 176k | 361k |
| Hastings | 29 min | 58 | 10.1M | 131k | 254k |
| Waterloo | 39 min | 77 | 19.3M | 167k | 355k |

What drove the cost:
1. **Re-reading context.** Each turn re-reads the whole context, so 58–106 turns at a 250–360k peak dominate the billed total. The fix is fewer turns and a smaller context.
2. **Large reads that stay in context.** Each author read 8–23 preview PNGs. Some read 500–680k-character files (agent transcripts, research dumps) and one read a 1.6M-character session file. Several `cat`ed whole toolkit modules to learn the API.
3. **Model generation, not tools.** Thinking ran 90–113k characters per author. Each builder write cost 17–30k output tokens, and authors often rewrote the whole builder when one edit would have done.
4. **Slow fetches.** Gaugamela spent 13 minutes in WebFetch on slow non-Wikipedia sites. Hastings and Waterloo spent about 3.5 minutes each in rate-limited Nominatim lookups.

Measurement scripts (copy and generalise them in D9):
- `/tmp/claude-1000/-home-pickle-code-history-mapped/599c3775-1c86-4a32-b0e2-9e5fbed750f7/scratchpad/analysis/author_costs.py`
- `/tmp/claude-1000/-home-pickle-code-history-mapped/599c3775-1c86-4a32-b0e2-9e5fbed750f7/scratchpad/analysis/author_detail.py`

## Ground rules

- **Shared checkout.** Work in `/home/pickle/code/history-mapped`; other agents are editing at the same time. Don't commit, and don't run git commands that change state.
- **Files you own:**
  - `pipeline/map_stories/__main__.py` and `preview.py`
  - new modules under `pipeline/map_stories/`: `research.py`, `places.py`, `layout.py`, `lint.py`, `queue.py`, `cheatsheet.py`, or similar
  - `pipeline/tests/test_map_story_tools.py`, a new file
  - `.claude/agents/battle-author.md` and `battle-reviewer.md`
  - `scripts/agent-costs.py`
  - `docs/implementation-docs/battle-map-bulk-run.md`
- **Files you don't own:** `schema.py`, `validate.py`, `geo.py` and `stories/*` belong to the schema-v2 agent, who is adding v2 fields right now. Import from them; don't edit them. Use `resolve_steps` and `validate` as they are. If you need a new geo primitive, put it in your own module.
- **Python:** `scripts/capped.sh pipeline/.venv/bin/python3 …`. Add a dependency only if it is already in `pipeline/requirements*.txt` or the venv. A YouTube transcript venv may exist (look for `ytvenv`). Use it only if it is present; it is optional.
- **HTTP etiquette.** Every request's User-Agent is `history-mapped/1.0 (https://github.com/PickleSoda/history-mapped)`. Never put an email address in it. Cache every response on disk under `output/map-stories/cache/`, which is gitignored, and rate-limit Nominatim to 1 request per second across processes; reuse the lock in `geo.py`.

## Tasks

- [ ] **D1. `research` command.** Usage: `python -m pipeline.map_stories research <Wikipedia title | Qid> [--section NAME …] [--outline] [--lang en]`.
  - **Source:** the MediaWiki API, not WebFetch, returning plain text per section (`action=parse&prop=sections` and `wikitext`/`text`, then strip markup, or `extracts` with `explaintext`).
  - **Default output:** an outline of section names with character counts, plus the infobox basics: date, location coordinates, belligerents, commanders, strength, casualties, result. Pull these from Wikidata where they exist: P585/P580, P625, P710, P1120.
  - **`--section`:** prints only the named sections.
  - **`--max-chars`:** a hard cap on output, default 6000.
  - **Wikidata lookups:** `--qids Q1 Q2 …` resolves the commanders' and polities' QIDs in one batched `wbgetentities` call (label, description, P31 and dates) so the author can link them correctly.
- [ ] **D2. `places` command.** Usage: `python -m pipeline.map_stories places "Hougoumont" "La Haye Sainte" … --near LON,LAT [--radius-km 15]`.
  - **Lookup:** one batched gazetteer lookup, Nominatim first and Wikidata P625 second, through the cached, rate-limited helpers.
  - **Output:** one table line per name: the best coordinates, the source, and the distance from `--near`. Mark ambiguous results.
  - **Geometry:** `--geometry river|ridge|coast|woods` returns simplified lines or areas for terrain (reuse `geo.place_geometry`).
  - **Elevation:** `--elevation` adds the height at each point.
- [ ] **D3. `layout.py` helpers** for writing builders. Each helper returns placement dicts that use the v1 fields only, so they work while v2 lands:
  - `deploy_line(left, right, specs, depth=…, gap=…)`: spread units along a front by their share of the width.
  - `wing(anchor, facing, specs)`
  - `crescent(centre, facing, width, bulge)`
  - `column(path, units, spacing)`, for a march
  - `behind(placement, metres)`
  - `echelon(…)`
  - `facing_toward(a, b)`
  - `screen(…)`

  Keep each helper's docstring short. The cheatsheet prints them.
- [ ] **D4. `lint.py` — numeric checks that replace most preview reading.** Run it from `check` after `validate`. Per step, it flags:
  - formations of the same side that overlap by more than 15% of the smaller one's area;
  - formations of opposing sides that overlap while neither is `engaged`;
  - formations with absurd density: width×depth against `strength_n`, skipped if `strength_n` is unset;
  - a unit outside the step's camera, when the step has an explicit camera;
  - notes whose label boxes collide at the step's framing zoom (estimate them from character count);
  - arrows that don't start within 300 m of the unit's position in the previous frame;
  - steps whose framing exceeds the kind's spread limit;
  - units that never move across five or more steps while their side's narrative says they "advance".
  
  Make each check a small function, with tests.
- [ ] **D5. Concise `check` output.** By default, print at most 20 lines: the counts, then the issues grouped by step with ids, so an author can act without reading JSON. `--verbose` prints everything, and `--json` gives machine output for the reviewer. Exit 1 on errors, and 0 when there are only warnings.
- [ ] **D6. Cheaper previews.**
  - **Contact sheet:** the default `preview` output is one image: a grid of every step at about 360×240 per cell, labelled with the step id. `--step ID` renders one step at 900×600.
  - **Rendering fixes:** scale arrowheads to the zoom and include notes in the framing.
  - **Robustness:** ignore v2 fields the preview doesn't understand rather than crash. Optionally draw dashed outlines for `conjectural`.
  - **Rename** the old per-step mode to `--all-steps`.
- [ ] **D7. `cheatsheet` command.** `python -m pipeline.map_stories cheatsheet` prints in under 150 lines:
  - the vocabulary from `schema.py`, read at runtime so it picks up v2;
  - the `geo` and `layout` helper signatures with one-line docs;
  - the builder skeleton;
  - the CLI commands.

  Authors read this instead of the modules.
- [ ] **D8. Queue.** `python -m pipeline.map_stories queue [--limit N] [--kinds battle,siege,naval_battle]` reads the local DB through `docker compose -f docker/docker-compose.yml exec -T db psql -U history-mapped history-mapped -At -c …`.
  - **Candidates:** battle-like events (find the entity types and subtypes in `api/app/Enums/EntityType.php` and `BattleSubtype.php`) that have a QID and no `map_stories` row.
  - **Ranking:**
    - relationship count
    - chronicle membership
    - description length
    - Wikidata sitelink count (batched, cached)
    - a bonus if the entity has a point location
  - **Output:** `output/map-stories/queue.tsv` with the columns `rank slug name qid year kind score status`. Use `status` values `todo|done|skip` and keep existing statuses when rebuilding.
  - **Slugs:** derive them as `battle-of-x` the way the existing stories do. If two names collide, add the year to the slug.
- [ ] **D9. `scripts/agent-costs.py`.** Generalise the two analysis scripts. Input is a session jsonl, or a directory of `subagents/agent-*.jsonl`, plus an optional `--match <description regex>`. Output is a table of wall time, turns, billed tokens (input, cache read, cache write, output), peak context, the top tool categories by time, and the largest tool results. The orchestrator uses it after each batch.
- [ ] **D10. Agent definitions.**
  - **`battle-author.md`:**
    - Front matter: `model: sonnet`; tools Bash, Read, Write, Edit, Grep, Glob. No WebFetch: research goes through D1.
    - Input: `slug`, `qid`, `name`, `year`.
    - Workflow: cheatsheet → `research --outline` → read 2–4 sections → `places` in one batch → write the builder with `layout` helpers → `build` + `check` → fix what the lints flag → one contact sheet → at most 2 `--step` renders → done.
    - Budgets: at most 60 turns, 3 image reads, and 3 full rewrites of the builder file. Make every other change with Edit.
    - Hard rules:
      - never Read a file over 200 KB, and never read transcripts or session jsonl;
      - never cat toolkit modules;
      - don't invent facts, and mark reconstructed positions `conjectural`;
      - link only QIDs that `research --qids` confirmed.
    - Output: `api/resources/map-stories/<slug>.json` and `api/resources/entity-descriptions/<slug>.md` (follow the existing description files' format), plus a return report of at most 4 lines.
  - **`battle-reviewer.md`:**
    - Front matter: `model: sonnet`.
    - Input: a slug.
    - Steps:
      1. `check --json`;
      2. a fact check of each step's claims against the research cache, using `research --section`;
      3. a check that the QIDs match their names;
      4. one look at the contact sheet;
      5. fix up to about 10 issues in place with Edit, then rebuild and `check`.
    - Verdict: PASS, FIXED or REDO, with reasons, in at most 4 lines.

  Model both on `.claude/agents/campaign-*.md` for tone and length.
- [ ] **D11. Runbook** at `docs/implementation-docs/battle-map-bulk-run.md`:
  - how to build the queue;
  - dispatching batches: about 4 authors in parallel, each followed by a reviewer;
  - syncing (`map-stories:sync`, `entities:sync-descriptions`);
  - measuring with `agent-costs.py`, with the baseline table above;
  - expected cost per battle;
  - stop rules: halt the batch if two consecutive authors exceed 12M tokens.

  Link it from `docs/README.md` and `map-story-authoring.md`. For the link in `map-story-authoring.md`, ask the schema-v2 agent through your report to add it; don't edit that file yourself.
- [ ] **D12. Dry run** of each command against Waterloo, which already exists:
  - `research "Battle of Waterloo" --outline`
  - `places` for five anchors
  - `queue --limit 20`
  - `check` (concise)
  - `preview` (contact sheet)
  - `cheatsheet`

  Run `pytest pipeline/tests/test_map_story_tools.py pipeline/tests/test_map_stories.py`. Don't run an actual Sonnet author: the orchestrator runs the pilot after schema v2 lands.

**Report** in at most 15 lines: the commands added, the sizes of their outputs (characters) in the dry run, the test count, the paths of the contact sheet and queue files, and the change you need from the schema-v2 agent.
