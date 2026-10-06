# History-Data Campaign — Orchestration Runbook

How the main Claude Code session drives the history-data campaign. It dispatches five subagents (`.claude/agents/campaign-*.md`) and does no content work itself.

**Normative sources**
- Spec: [`2026-08-23-history-data-campaign-design.md`](../superpowers/specs/2026-08-23-history-data-campaign-design.md). §3 covers the corpus and authoring rules, §4 the handoff contract and §7 acceptance.
- Plan: [`2026-08-23-history-data-campaign.md`](../superpowers/plans/2026-08-23-history-data-campaign.md)
- Content style: [`pipeline/agent/style_guide.md`](../../pipeline/agent/style_guide.md)
- Tooling: the `pipeline.campaign` CLI; see `agentic-pipeline-runbook.md` → *Handoff Mode*.

`CLI` below means `pipeline/.venv/bin/python -m pipeline.campaign`, run from the repo root.

## Roster (v2 tiering)

Each model gets the work it is good at: authoring, slice extraction and review (Sonnet), and Opus only on escalation. See *Canary findings* for why.

| Agent | Model | Role | Dispatch when |
|-------|-------|------|---------------|
| `campaign-author` | sonnet | Writes or extends the transcript only. Every fact is discrete, dated, in-era and wiki-grounded (`wiki --dated`); no filler. A sparse topic stops short (floor 60) instead of padding. Records Spillover, Corrections and Uncertain in notes.md and gates on `transcript-check` | Every run: `new` or `extend` |
| `campaign-gatherer` | sonnet (haiku until 2026-10-05) | Extraction-only worker. `extract` handles one fact slice: events tagged `fact`, entities, summaries and relations, gated by `check --facts`. `close` runs the whole-handoff critic pass (orphans, density, near-duplicates) and then `finalize` | Per slice, sequentially, after the author; then one `close` |
| `campaign-reviewer` | sonnet | Audits accuracy, coverage, fidelity, direction and style. Fixes ≤ ~15 items (transcript or handoff). Returns REGATHER for extraction problems, naming slices; ESCALATE when the transcript needs more than ~15 fact fixes | Right after `close` |
| `campaign-fixer` | opus | Repairs the root cause (may rebuild the run); fixes `pipeline/campaign/` bugs with tests; reports pipeline/validator changes | On ESCALATE, a second failure, or an ingestion failure caused by a handoff defect |
| `campaign-ops` | sonnet | Docker bring-up, detached ingestion and polling, single-run debug, `measure` vs §7, repair passes | Per wave, and on ingestion failures |

## Non-negotiables

1. **Never shift dates.** A fact outside its transcript's era span is dropped from that transcript. It is logged in the run's `notes.md` under `## Spillover` as `- [eNN] <true date> — <fact> (from <slug>)`. It is never re-dated or rounded toward the boundary. Reviewers diff `transcript.prev.txt` to catch shifted years.
2. **Textbook consensus only.** Transcripts and handoffs never contain QIDs, coordinates or confidence numbers. Month and day appear only when genuinely known. JSON years are signed strings (`"-490"`).
3. **Only runs whose latest verdict is PASS or FIXED get ingested.**
4. **Destructive operations need explicit user approval.** This covers `migrate:fresh`, DB deletes, `merge_entities --apply` and `reresolve_entities --apply`. Ops runs them only when its dispatch names the operation in `destructive:`.
5. **The orchestrator stays low-context.**
   - It reads only the agents' returns (author and gatherer ≤2 lines, reviewer ≤3, fixer ≤5, ops ≤15), plus `CLI status` and `CLI validate-all`.
   - It never opens transcripts or handoffs itself; it dispatches a reviewer or fixer instead.
6. **Fact numbers are the join key** between transcript and handoff: every event carries `"fact": N`.
   - The author may renumber, because extraction always follows it from scratch (slice 1 runs `init --force`).
   - After extraction nobody renumbers. Facts are edited in place, appended at the end, or dropped with a gap plus `handoff rm-slice`.

## Run lifecycle

```
planned ─author─▶ authored (transcript-check OK)
        ─gatherer extract 1-20 ─▶ extract 21-40 ─▶ … (sequential)  ─gatherer close─▶ extracted (validator OK)
        ─reviewer─▶ PASS | FIXED ─ops ingest─▶ ingested ─ops measure─▶ wave accepted
                    ├─ REGATHER slices=… ─▶ gatherer extract (those slices, feedback: review.json) ─▶ close ─▶ reviewer   (max once per run)
                    └─ ESCALATE ─▶ fixer ─▶ FIXED | BLOCKED (→ user)
```

State lives on disk, so you can resume any time with `CLI status`. To see how far a run's extraction got, run `CLI handoff show <run> --part events`: each event line is prefixed `#<fact>`.

| File | Contents |
|------|----------|
| `output/transcripts/campaign/<slug>.txt` | Transcript |
| `output/campaign/extractions/campaign_<slug>/candidates.json` (+ `.prev.json`) | Handoff; `handoff init --force` backs up the previous one |
| `…/review.json` | Verdict history (`review-record`) |
| `…/notes.md` | Spillover, Corrections, Uncertain, Sources, Log |
| `…/transcript.prev.txt` | Transcript as it stood before the latest `extend` |

## Slice plan

- **Slice size 20.** Cut the author's `facts=N` into 1-20, 21-40, …. If the last remainder is under 10 facts, merge it into the previous slice; for example, 85 facts → 1-20, 21-40, 41-60, 61-85.
- A 20-fact slice is about 20–25 events, 30–40 new entities, 60–80 relations and 10 `add` calls. That stays well inside Haiku's reliable range; the canary's Haiku collapse happened once a single pass carried 100 facts and 280 entities.
- Run one run's slices **strictly in order**. Each slice reuses the labels earlier slices created, and they all write the same file. Different runs can go in parallel.

## Dispatch templates

Use the Agent tool with `subagent_type` set to the agent name and a 3–5 word `description`. The prompt is exactly the block shown, with the `{placeholders}` filled in.

**Author** (`campaign-author`)

```
run: {run}
mode: {new|extend}
scope: {scope}
target_facts: {target}
feedback: {none | what to fix}
```

- `scope` needs four things: the era id and span, the region track and topic, the must-cover anchors, and the neighbours. Example:
  ```
  scope: e04 (750–330 BCE; 330 BCE belongs to e05) | Anatolia & Aegean | Archaic & Classical Greece.
    anchors: Greek colonisation; Lycurgus and the Spartan system; Draco and Solon; the Peisistratids; Cleisthenes;
    Ionian Revolt; Marathon; Thermopylae, Salamis, Plataea; Delian League; Pericles and the Parthenon;
    Peloponnesian War; Plague of Athens; Sicilian Expedition; trial of Socrates; Leuctra and Theban hegemony;
    Philip II of Macedon and Chaeronea.
    neighbours (do not duplicate): e04__middle-east__achaemenid-persian-empire (Persian court, satrapies);
    e04__europe__etruscans-and-birth-of-rome (western Mediterranean).
  ```
- `target_facts` defaults to 80. Use 90–110 for dense backbone cells. The accepted range is 60–120; the author may return fewer, with `sparse=yes`.
- The author returns: `AUTHOR <run> facts=<N> prev=<M> spillover=<n> corrections=<n> sparse=<no|yes|below-floor> transcript-check=<OK|FAIL>`.

**Extract slice** (`campaign-gatherer`)

```
run: {run}
mode: extract
slice: {a}-{b}
feedback: {none | review.json | rerun: <first error>}
```

- Use `feedback: none` only on a run's first extraction pass; slice 1 with `none` re-initialises the handoff.
- Every re-dispatch (a crash, a failed check, or a REGATHER) passes a non-`none` feedback, so the slice starts with `rm-slice` instead of `init`.
- It returns: `RESULT <run> slice=<a-b> facts=… events=… new_entities=… relations=… rel/fact=… rel/new_ent=… check=<OK|FAIL>`.

**Close** (`campaign-gatherer`)

```
run: {run}
mode: close
```

- It returns: `RESULT <run> close facts=… events=… entities=… relations=… r/e=… orphans=… validator=<OK|FAIL>`.

**Reviewer**

```
run: {run}
scope: {the exact scope line the author got}
focus: {optional, e.g. "validator FAIL: event 'X' year -320 outside e04" | "post-fix verification" | "shifted dates"}
```

- It returns `REVIEW <run> verdict=<V> … slices=<ranges|->`.
- On REGATHER, the slices to re-extract are in `slices=`, and also in the first review.json issue as `slices: 21-40,61-80`.

**Fixer**

```
run: campaign_<slug>
reason: <the escalating agent's return lines, verbatim>
scope: <the exact scope line>
```

**Ops**

```
task: ingest                      # bringup | ingest | ingest-status | debug | measure | repair (combinable)
runs: ONLY='e0[1-3]__'            # regex, or explicit run ids
options: RUN_TIMEOUT=1800 RETRY_FAILED=1     # EXTRA_AGENT_FLAGS=--refresh only to re-ingest changed handoffs in place (never for first-time ingests; the continuous loop applies it automatically to clean-manifest runs only)
destructive: no                   # or the exact approved op, e.g. "migrate:fresh --force (user approved 2026-10-05)"
```

- `ingest` starts the driver detached and returns `INGEST STARTED pid=… log=…`.
- To check on it later, dispatch `task: ingest-status pid=<pid>`. Each check is cheap.

## Escalation rules

| Signal | Next dispatch |
|--------|---------------|
| Author `transcript-check=FAIL`, or no AUTHOR line (crash/timeout) | Re-dispatch the author once, `mode: extend`, with `feedback:` set to the first error (or `resume after crash`); the partial transcript is kept. A second failure goes to the fixer. |
| Author `sparse=below-floor` | Don't extract. Re-scope instead: widen the region or topic, or merge into a neighbour. Surface it to the user if unclear. `sparse=yes` (60 or more facts) proceeds normally. |
| Extract `check=FAIL`, or no RESULT line | Re-dispatch the same slice once with `feedback: rerun: <first error>`; it starts with `rm-slice`, so nothing duplicates. If it fails again, carry on with the remaining slices and `close`, then give the reviewer `focus: slice <a-b> failed twice: <error>`. |
| Close `validator=FAIL` | Reviewer with `focus: validator FAIL: <first error>`. It fixes the problem or decides REGATHER/ESCALATE. |
| Reviewer `REGATHER slices=…` | For each range, in order: extract with `feedback: review.json`. Then `close`, then the reviewer again. **Max 1 REGATHER per run.** Any further non-PASS/FIXED becomes ESCALATE. |
| Reviewer `ESCALATE` | Fixer. This includes transcript problems beyond ~15 facts, which are never sent back to Haiku. |
| Fixer `FIXED` | The run is ready to ingest. Re-review is optional (`focus: post-fix verification`). |
| Fixer `BLOCKED` | Park the run and surface the proposed change to the user; it needs approval for HIGH-risk pipeline edits. |
| Fixer `cause: tooling` or `pipeline` that affects many runs | Pause new dispatches. After the fix lands, run `CLI validate-all`, then re-review the affected runs. |
| Ops `failed:` | `handoff` → fixer. `infra` → ops retries. `external` (Wikidata/OHM) → later pass with `RETRY_FAILED=1`. `pipeline` → fixer (diagnosis). |

## Batch guidance

- **Parallelism**
  - Run 4–6 runs at once, one agent per run at a time. Wave 0 saw subagent OOM with larger fan-out.
  - Within a run the chain is strictly sequential: author → slices → close → reviewer.
  - Pipeline across runs: while one run's slices extract, another run's author can write.
  - Keep at most 6 agents running at once.
  - Never put two agents on the same run at the same time.
- **Batching by era and region:** dispatch runs from the same era and region track together, so the `neighbours:` lines are accurate and spillover lands in a sibling run.
- **After each batch:** run `CLI status --era eNN --validate` and `CLI status --thin`. These show runs below target, failing validation, or without a verdict.
- **Scope lines are the orchestrator's main job.** Each one needs:
  - the era id and span
  - the region track and topic
  - 8–15 must-cover anchors
  - the neighbours that own adjacent facts
- **Permissions:** agents that hit permission prompts stall batches. Before a big batch, ask the user to allowlist the following in `.claude/settings.local.json`:
  - `Bash(pipeline/.venv/bin/python -m pipeline.campaign *)`
  - the `cp`/`grep`/`diff`/`head` commands the author, gatherer and reviewer use
  - `docker compose -f docker/docker-compose.yml *` for ops

## Wave procedure

### Wave R: redo Wave 0 + Wave 1 (72 existing runs, `extend`)

The existing transcripts are thin: a median of 10 facts against the 60–150 the spec calls for. Some have dates that an earlier orchestrator shifted to fit era bounds.

1. **Back up.** `output/campaign-backups/wave01-v1-20261002.tar.gz` already exists. Take a fresh one if anything has changed since (see Backups).
2. **Dispatch.** For every run in `CLI status` that isn't already FIXED by the fixer (the canary runs e01 mesopotamia and e10 global are):
   1. Author with `mode: extend` and `target_facts` 80–110.
   2. Extract slices with `feedback: none`, then close.
   3. Reviewer.

   Loop until all 72 runs are PASS or FIXED.
3. **Spillover sweep.** Run `grep -rh '^- \[e' output/campaign/extractions/*/notes.md | sort`. Feed the items into the matching era's scope as anchors, or keep them as seeds for Wave 2 cells. (Authors also grep spillover for their own era.)
4. **Ingest.** The DB holds the earlier thin, label-inconsistent rows. Decide with the user:
   - **Fresh (recommended).** This matches the spec §2 fresh-start decision. Run ops `bringup` and back up, then `migrate:fresh --force` with `destructive:` naming it, then `ingest` all runs.
   - **In place.** Use `ingest` with `options: EXTRA_AGENT_FLAGS=--refresh`. Rows whose labels changed stay behind as orphans to repair.
5. **Measure.** Run ops `measure` and check the §7 table. All green means the wave is accepted. A red metric goes to ops (repair dry-run) or the fixer (diagnosis) before Wave 2.

### Wave 2: fine grid (~240 new runs, `new`)

1. **Plan the cells** from spec §3.1: era × 13 region tracks, plus about 20 thematic overlays, only where history is dense enough.
   - Slugs are `eNN__<region>__<topic>`, kebab-case, e.g. `e08__europe__crusader-states`.
   - Keep the plan as `output/campaign/grid.tsv` (`slug<TAB>scope line`) so scopes and neighbours are reproducible.
2. **Run in era order** (e01 → e10) so dedup anchors build forward. Every run's author gets `mode: new` with `target_facts: 80`.
3. **Ingest per era** after review, e.g. `runs: ONLY='e05__'`. Measure after each era or after about every 40 runs.
4. **Post-wave.** Ops `repair` dry-run, then the user approves `--apply` for the listed names, then the final `measure`. Embeddings are a separate follow-up (spec §10).

## Canary findings (2026-10-03)

Three pilot runs used v1 tiering, where Haiku gathered (authored and extracted), Sonnet reviewed and Opus fixed:

| Run | Outcome |
|-----|---------|
| e01 mesopotamia neolithic-settlements | REGATHER → ESCALATE → Opus rebuild |
| e10 global modern-revolutions | REGATHER → ESCALATE → Opus rebuild |
| e04 aegean classical-greece | Unreviewed v1 output |

- **Haiku authoring padded.** The second half of its transcripts filled with generic, undated or inferred facts. `transcript-check` finds 25 undated facts in Haiku's e01 transcript and 0 in Opus's rewrite; e04 has 5 undated facts plus out-of-order blocks. Haiku also got dates wrong (Abu Hureyra, Uruk, Susa, Tepe Gawra), kept out-of-era items, and duplicated neighbour tracks (Opium War, Meiji, Sepoy and Bolívar inside the e10 global survey).
- **Haiku extraction collapsed at scale.** In a single 100-fact pass, e10 produced 284 entities but only 39 relations, and 111 entities had no summary. e04 ended at r/e 1.00 with 29 orphans and 24 mentions of non-entities.
- **Directions and types came out reversed or confused.**
  - Reversed directions:
    - `commanded_by` person → battle (×8 in e04)
    - culture `part_of` site
    - resource `produces` place
    - technology `adopted` polity
    - `victorious_at` battle → polity
    - city `located_at` battle
    - institution `founded` person
  - Mistyped entities: rivers, the Persian Gulf and the Zagros typed as `city`; Manchuria and Taiwan typed as `city`.
  - These patterns are now the WRONG column of the gatherer's direction sheet.
- **Regathers didn't recover.** Two Haiku regathers failed. Opus rebuilt e01 and e10 well (r/e 1.88 and 2.24, 0 orphans), but at about 1.6M tokens for the three runs.
- **v2 response:**
  - Sonnet authors; the author has no handoff work and a deterministic `transcript-check` gate.
  - Haiku only extracts, in 20-fact slices with per-slice gates (`check --facts`: rel/fact ≥ 2, rel/new_ent ≥ 1.5, orphans, mentions).
  - REGATHER re-extracts named slices only (`rm-slice`, so nothing duplicates).
  - Transcript trouble beyond ~15 facts goes straight to Opus.
- **e04** still holds the unreviewed v1 output. Redo it under v2: author `mode: extend`, then the slices.
- **Wave 2 (2026-10-05): Sonnet now extracts by default.** Even in 20-fact slices, Haiku's relations kept failing review. Reviewers sent many runs back for whole-run REGATHER, citing reversed `part_of`, nonsense links between unrelated sites, and battle sites typed as cities, so most runs paid for two extractions and two reviews. Every slice is now extracted with Sonnet.

## Backups

- **Corpus**
  - Before each wave and before any bulk regather, run `tar czf output/campaign-backups/<label>-$(date +%Y%m%d).tar.gz output/transcripts/campaign output/campaign/extractions`.
  - To restore, extract over the tree.
- **Per run:** `candidates.prev.json` (from `handoff init --force`) and `transcript.prev.txt` (from the author).
- **DB:** ops writes `output/history-mapped-backup-<ts>-<label>.sql` via `pg_dump` before any destructive or `--apply` operation.

## 2026-10-05 QID repair

Applied `output/campaign/audit/qid-repair-plan.md` to the live DB with ingestion paused (`INGEST_STOP`).

- **Repaired:**
  - clear-qid: 306 rows (299 high/medium plus the 7 collapsed split rows). The wrong QID moved to `attributes._rejected_wikidata_id`; Wikidata geo-refs were deactivated. The 38 low-confidence rows are untouched.
  - rename: 10 rows restored from their QID's own record via `UpdateEntityAction`; the 7 skip-list rows were left alone. The "Mithridates V" row became Mithridates VI of Pontus: the e04 "Mithridates" is a different person, so it was split out too.
  - split: 39 rows. 46 new rows came through `pipeline:import` (batch `qid-repair-20261005-split`); 6 movers re-pointed to existing rows. 84 relations and 244 chronicle links moved by exact attribution; 11 links were added where an entry names both; 0 were ambiguous.
  - backfill: 1,205 entities the approval gate had held, imported via `pipeline:import` (batch `qid-repair-20261005-backfill`, `needs_review` plus `validation_flags`). None has geometry.
  - re-link: `--additive-recovery` and `--link-missing` over the 72 runs (batch `recovery-20261005:<run>`) added 2,964 relations and 1,449 links. For runs whose links moved, `--link-missing` read patched copies of `chronicle.json`, so the old UUIDs could not re-attach moved links.
- **Files:**
  - backup: `output/campaign-backups/db-pre-qid-repair-20261005.sql.gz`;
  - per-change log with before/after values: `output/campaign/audit/qid-repair-applied-20261005.csv`;
  - ambiguous links: `output/campaign/audit/qid-split-ambiguous-links.csv`;
  - post-repair audit: `output/campaign/audit/qid-corruption-20261005-post-repair.csv`;
  - ops, inputs and re-link logs: `api/storage/app/pipeline/qid-repair-20261005/` and `output/campaign/logs/relation-recovery-20261005/`.
- **Reverse:**
  - Replay the change log backwards: set each `before` value back. For an `(insert)` row, delete the inserted link.
  - Created rows carry `created_by = pipeline:qid-repair-20261005-{split,backfill}`.
  - Re-linked relations carry `created_by LIKE 'pipeline:recovery-20261005:%'`.
  - A full rollback is a restore of the backup. That is destructive and needs the user's approval.
- **Open items:**
  - The "Suleiman" row (Q8474) holds the Safavid Suleiman I's content and was not in the audit.
  - The e08 "Qi" (the 1130s puppet state) shares the Zhou-era "Qi" row.
  - 371 relation records (74 endpoint names) and 3 chronicle refs remain unresolved. Their QID sits on a differently named row that the guard rejects (Tell Halaf→Guzana, Middle Kingdom→China), or their record merged into another row.

## 2026-10-06 namesake/date/geometry repair

Applied with ingestion paused (`INGEST_STOP`, 2026-10-06 00:05–01:57 +04, after the 61-run Wave 3 batch drained). Inputs: `output/campaign/audit/namesake-repair-plan.md` and its SQL, `fabricated-jan1-20261005.csv`, and `geometry:derive-located-at`.

- **Namesake repair.** All 506 guarded forward statements were re-checked against the live DB just before applying. None had drifted. Each part ran in one transaction, and inside it every statement was re-checked to match exactly one row before it ran.
  - PART 1: 106 entity fixes (QIDs, date ranges, 4 renames).
  - New people: 27 created through `pipeline:import --sync --skip-relationships --batch-id=namesake-repair-20261005` (`needs_review`, `created_by = pipeline:namesake-repair-20261005`). The importer skipped 5 as duplicates of rows that campaign runs created after the dry run, with the same QID and dates: Arghun `4bfa9291`, Charles VI HRE `fd1f6fa3`, Francis II of France `fa8f9bf8`, Henry IV of England `d0eb6810`, Liu Yan `8b4e7782`. Their relations and links were re-pointed to those rows (`namesake-repair-adopted-20261006.json`).
  - PART 2: 342 re-points and date fixes (192 relations, 150 chronicle links) and the 14 approved relation deletes.
  - dateless-first: the 31 date updates. The 3 flagged rows were not touched.
  - Timelines were rebuilt for the 348 touched entities, because raw SQL bypasses the observers.
- **Held back** (deletes beyond the 14 approved; still guarded in the plan SQL, apply only with approval):
  - the 4 alias removals A0021, A0044, A0056, A0109;
  - the 8 collateral duplicate/self-loop relation deletes A0366–A0369, A0379, A0383, A0389, A0434;
  - the duplicate chronicle link A0529.
- **Dates.**
  - `handoff fix-dates --apply` de-padded 140 values in 7 handoffs:
    - `e09__europe__hundred-years-war-and-hussites`;
    - `e10__americas__us-civil-war-and-reconstruction`;
    - `e10__anatolia__late-ottoman-reform-and-turkey`;
    - `e10__east-asia__meiji-restoration-industrial-japan`;
    - `e10__oceania__australia-new-zealand-and-pacific`;
    - `e10__south-asia__post-independence-south-asia`;
    - `e10__southeast-asia__khmer-rouge-asean-new-order`.
  - The originals are in `output/campaign-backups/handoffs-pre-fixdates-20261006/`. Each `candidates.json` mtime was restored, so the loop does not re-ingest these runs with `--refresh`.
  - The DB list came from `measure --jan1-csv` (`fabricated-jan1-20261006.csv`), regenerated from the current DB *before* the handoffs were fixed. Entity ranges are judged by matching handoff values, so a fixed handoff would misclassify them.
  - Applied: 98 values on 61 rows (74 relation values, 24 range values), only `PADDED` with a fact that names the year. The bare year (`1873`), or `YYYY-01` when the fact names January, matches the DB convention; the trigger keeps `start_year`/`end_year` in sync.
  - Skipped: 28 values whose cited fact names another year, and the Gregorian-calendar 1 January 1873 KEEPs.
- **Geometry:** `geometry:derive-located-at --apply --precise-only` inserted 947 periods (`created_by = derive:located_at`): 417 battles, 228 monuments, 77 rebellions, 76 wars, 39 legal reforms, 34 cities, 23 treaties, 20 natural disasters, 13 educational institutions and 20 others. The dry run on 2026-10-05 planned 619; the DB has grown since.
- **Files** (`output/campaign/audit/` unless noted):
  - backup: `output/campaign-backups/db-pre-namesake-dates-geo-20261006.sql.gz` (32.9 MB);
  - logs: `namesake-repair-applied-20261006.csv` (every statement, with status and full before/after rows), `jan1-repair-applied-20261006.csv`;
  - ids: `namesake-repair-created-20261006.json` (created rows), `geometry-derived-ids-20261006.json` (inserted periods);
  - `namesake-needs-review-dups-20261006.csv`: `needs_review` rows from campaign runs after 2026-10-05 21:00 +04 that are now same-name and date-compatible with a repaired row. They are reported, not merged.
- **Reverse:**
  - Run `repair-rollback-20261006.sql` through `psql -f -`. It undoes, in reverse order: geometry → dates → dateless → PART 2 → created entities → PART 1. Every statement is guarded on the value the repair wrote. A test run inside a rolled-back transaction touched exactly 577 updates, 14 re-inserts, 27 entities and 947 periods.
  - Then run `timeline:rebuild` for the ids in `api/storage/app/pipeline/namesake-repair-20261005/timeline-ids-20261006.json`.
  - Restore the handoffs with `cp -p` from the backup folder.
  - The prepared `namesake-repair-rollback.sql` is still valid for PART 1/2. Its created-entity step does not cover the 5 adopted rows, which were not created by this repair.
  - A full restore of the dump is destructive and needs the user's approval.
- **Open items:**
  - Merges listed in plan §B are still pending (e.g. `bdc385a2` ← `6537823e`, `a287d544`; `f43eb5ec` ← `c48c586e`).
  - There is no Charles V of France row. His France relations (rules France 1364–1380, Kingdom of France, parent of Charles VI) are still on the Emperor row `6537823e`.
  - 4 re-pointed relations now duplicate a relation the adopted row already had: Arghun rules Ilkhanate, Henry IV of England rules England, and Liu Yan rules / founded Southern Han.
  - `fa8f9bf8` and `d0eb6810` keep their correct QID in `_rejected_wikidata_id`. It is now free to restore.
  - `needs_review` "Muhammad Ali" `ca866502` carries the boxer's QID Q36107, which is also on `6e744003`.
  - The Meiji handoff's "Gregorian calendar adoption" was de-padded to `1873` by fix-dates. The DB keeps the real 1 January 1873. Amend fact 49 to "On 1 January 1873 CE".
  - The 4 renamed rows need fresh embeddings.
