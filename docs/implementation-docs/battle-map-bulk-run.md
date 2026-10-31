# Battle-map bulk run

How to turn the atlas's battles into map stories in batches, using cheap Sonnet
agents: a **battle-author** writes each story and a **battle-reviewer** checks
it. The authoring format itself is described in
[`map-story-authoring.md`](map-story-authoring.md). The plan behind this runbook is
[`docs/superpowers/plans/2026-10-31-battle-bulk-run-readiness.md`](../superpowers/plans/2026-10-31-battle-bulk-run-readiness.md).

```
queue.tsv ──► battle-author (Sonnet, ~15 min) ──► battle-reviewer (Sonnet) ──► PASS/FIXED ──► sync ──► atlas
   ▲              research · places · build · preview          check · digest · research        │
   └──────────── status todo → wip → done | skip ◄──────── REDO → author again with feedback ◄───┘
```

In the commands below, `CLI` means `scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.map_stories`, run from the repo root.

## The toolkit the agents use

| Command | Prints | Size in the Waterloo dry run |
|---|---|---|
| `CLI cheatsheet` | vocabulary (read live from `schema.py`), helper signatures, builder skeleton, rules | 10.9k chars, 122 lines |
| `CLI research <title\|Qid>` | infobox (date, P625, sides, commanders with Q-ids, strength, losses) and section outline with sizes | 3.4k chars |
| `CLI research <ref> --section A --section B` | plain text of those sections, capped by `--max-chars` (default 6000) | 6.0k chars |
| `CLI research --qids Q…` | label, dates, class and description per Q-id (one batched call) | 0.8k chars for 6 Q-ids |
| `CLI places "A" "B" … --near <Qid> --elevation` | one line per name: coordinates, source (OSM, then Wikidata), distance, AMBIGUOUS | 0.5k chars for 5 names |
| `CLI places "<river>" --near … --geometry river` | simplified line as a Python literal (≤40 points) | 0.8–1k chars |
| `CLI build <module>` / `CLI check <json>` | validate and lint: counts, then issues grouped by step (≤20 lines); `--verbose`, `--json` | 1.2k chars (`--json` 2.1k) |
| `CLI preview <json>` | path of one contact-sheet PNG of every step (360×240 per cell); `--step ID` gives 900×600 | 58 chars, one image |
| `CLI digest <json>` / `--links` | the story's prose without coordinates; every Q-id against its Wikidata label and class | 16.5k / 1.1k chars (the JSON is 74k) |
| `CLI queue --limit N` | writes `output/map-stories/queue.tsv`, prints the top 10 | 1.0k chars |

Every HTTP response is cached under `output/map-stories/cache/`, so a reviewer
re-reading the author's sections costs nothing. OpenStreetMap and OpenTopoData
calls share geo's lock file, which allows one call a second across all
processes. The User-Agent is `history-mapped/1.0 (https://github.com/PickleSoda/history-mapped)`.

The lint checks are in `pipeline/map_stories/lint.py`. They flag:
- same-side blocks overlapping by more than 15%;
- enemy blocks overlapping with neither `engaged`;
- densities outside the plausible range (from `strength_n`);
- units outside an explicit camera;
- colliding note labels;
- arrows that don't start where their unit stood;
- steps framed wider than the kind's spread limit;
- units that stay still for 5 or more steps while their narrative says they advance.

## 1. Build the queue

```bash
CLI queue --limit 200            # battle, siege, naval_battle; add --kinds …,campaign,other to widen
```

`output/map-stories/queue.tsv` has the columns `rank slug name qid year kind score status`.

**Score** (0–100):

| Signal | Weight |
|---|---|
| Wikidata sitelinks | 40 |
| relationships | 25 |
| chronicle entries | 15 |
| description length | 10 |
| a point location | +10 |

Each count is log-scaled against the largest one.

**Kind** comes from Wikidata P31 (naval battle, siege) and the name. Assassinations, bombings, massacres and similar come out as `other` and are left out by default.

**Slugs** are `battle-of-x`. When two battles share a name, the year is appended (`battle-of-x-216-bc`).

**Statuses:**
- Rebuilding keeps every status except `todo`.
- A battle whose story has been synced becomes `done`.
- Before dispatching, read the top of the file and set `skip` on anything that isn't a single field action: multi-year sieges such as Leningrad, "battles" that are really campaigns, or events with no known site.
- The orchestrator sets `wip` when it dispatches a battle.

## 2. Dispatch a batch

Run about **4 authors in parallel** as background subagents. When each author returns, run a reviewer on its slug.

The authors don't collide:
- each touches only `stories/<module>.py`, `map-stories/<slug>.json` and `entity-descriptions/<slug>.md`;
- the previews go to per-slug folders;
- the Nominatim lock serialises their lookups.

Author prompt (one per battle, from the queue row):

```
slug: battle-of-carrhae
qid: Q205887
name: Battle of Carrhae
year: -53
kind: battle
feedback: none
```

Reviewer prompt: `slug: battle-of-carrhae` and `qid: Q205887`.

**Handling the verdicts:**

| Verdict | Then |
|---|---|
| `PASS` / `FIXED` | Mark the row `done` after the sync (step 3). |
| `REDO` | Re-dispatch the author once with `feedback:` set to the reviewer's `redo:` line, then review again. |
| a second `REDO` | Set `skip`, and log the reasons in the batch notes. |
| author returns `build=FAILED` | Treat it as `REDO`. |

## 3. Sync to the atlas

After a batch's reviews:

```bash
docker compose -f docker/docker-compose.yml exec app php artisan map-stories:sync
docker compose -f docker/docker-compose.yml exec app php artisan entities:sync-descriptions
CLI queue --limit 200            # marks the synced battles done and keeps every other status
```

Spot-check one story in the atlas (`:5173`) per batch. Commit the builders,
JSON and descriptions together. Pushing `main` deploys, and production needs
the same two sync commands.

## 4. Measure every batch

```bash
scripts/capped.sh pipeline/.venv/bin/python3 scripts/agent-costs.py \
  ~/.claude-personal/projects/-home-pickle-code-history-mapped/<session-id> --match "battle|map story"
```

It reads the session's `subagents/agent-*.jsonl`, filtered by each agent's task
description. For each agent it prints:
- wall time and turns;
- billed tokens: uncached input, cache read, cache write and output;
- peak context;
- the tool categories that took the most time (e.g. `ms:preview` or `webfetch:other`);
- the largest tool results.

`--detail` lists every category.

**Turns** are counted once per API response. A response that the transcript
splits over several lines (thinking, then tool use) is still one turn.

### Baseline: the five Opus sample authors (2026-10-31)

| Battle | Wall | Turns | Billed | Cache read | Output | Peak context |
|---|---|---|---|---|---|---|
| Hastings | 29 min | 58 | 10.1M | 9.7M | 131k | 254k |
| Cannae | 36 min | 64 | 11.9M | 11.3M | 169k | 303k |
| Salamis | 38 min | 106 | 24.1M | 23.5M | 176k | 361k |
| Waterloo | 39 min | 77 | 19.3M | 18.8M | 167k | 355k |
| Gaugamela | 47 min | 87 | 18.2M | 17.7M | 175k | 321k |
| **mean** | **38 min** | **78** | **16.7M** | | **164k** | **319k** |

The readiness plan's first table (112–181 turns, 19.5–40.3M billed) counted
every transcript line, so split responses were counted twice. These are the
deduplicated figures.

**Where the time went:**
- About 80% was model time, not tools. Hastings spent 23 of its 29 minutes generating.
- Of the tool time, slow WebFetch was the biggest item: Gaugamela spent 13 minutes on non-Wikipedia sites.
- Rate-limited Nominatim lookups cost 3–3.5 minutes each for Hastings and Waterloo.

**What filled the context:**
- whole toolkit modules read with `cat` (about 16k characters each);
- research dumps of 40–50k characters;
- in one case a 1.6M-character PDF.

The toolkit replaces each of these: the cheatsheet instead of the modules, sectioned `research` instead of dumps, batched `places` instead of one lookup at a time, and a single contact sheet instead of 8–23 PNGs.

## 5. Expected cost per battle

**Target per battle (author plus reviewer):**

| | Author | Reviewer |
|---|---|---|
| Wall time | ≤ 15 min | about 5 min |
| Turns | ≤ 60 | ≤ 30 |
| Billed tokens | **under 8M** | about 2M |

The author's figure assumes ≤ 60 turns at about 120k average context. The context
starts at about 25k (agent definition, cheatsheet, research) and grows with the
builder. `Story` and the layout helpers should keep a builder to roughly 250–350
lines instead of the samples' 600–930. That is an estimate: the samples each
hand-wrote their own step recorder and placement maths.

These are targets, not measurements. Re-measure after the pilot batch and replace
this section with the real numbers.

## 6. Stop rules

Halt the batch, let running agents finish, and investigate before dispatching more, when:
- two consecutive authors exceed **12M billed tokens**;
- two consecutive authors come back `build=FAILED` or `REDO`;
- any author's "largest" results show a read over 200 KB, a transcript read, or WebFetch: the agent definition is being ignored, so tighten it;
- reviewers keep removing the same kind of wrong Q-id link: fix the tooling or the definition rather than the stories.

## Troubleshooting

| Problem | Cause and fix |
|---|---|
| `places` is slow | Nominatim allows one call a second shared by every author. The first batch of names costs about 1 s each; repeats come from the cache. |
| `places --geometry` returns a 2-point stub | Nominatim returned a single way, not the river relation. Try the full local name ("Fiume Ofanto", "La Lasne") or draw the feature by hand from the preview. |
| `research` says "no article" | Pass the Q-id instead of the title. `--lang de` reads another Wikipedia. |
| `preview` fails | It needs `google-chrome` on PATH and network access for the OpenTopoMap tiles. |
| `queue` says "psql failed" | Start the stack with `pnpm dev`. The queue reads the `db` container and never writes to it. |
