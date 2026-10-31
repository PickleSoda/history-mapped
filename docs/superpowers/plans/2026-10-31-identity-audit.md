# Identity audit: names, QIDs and inconsistencies — Implementation Plan

> **For agentic workers:** one agent implements this plan. Steps use checkbox (`- [ ]`) syntax.

**Goal:** a repeatable, committed audit that finds every entity whose identity is wrong or inconsistent, then applies only the safe fixes. An identity can be wrong through its QID, name, type, dates or the text that describes it. A fix is safe when it is non-destructive, high-confidence and reversible. The audit hands the user an exact list of the destructive fixes (merges and deletes) to run.

**Why now:** battle maps link commanders and polities by QID, so a wrong QID shows up as the wrong person in the player. The samples turned up these problems:
- **Wrong QIDs:**
  - "Jean-Baptiste Drouet" carries Q1531906, a postmaster, instead of the comte d'Erlon.
  - "Hans von Bülow" carries Q155540, a conductor, instead of Friedrich Wilhelm Bülow von Dennewitz.
  - "Imperial Guard" carries Q11010841, which is Ethiopian.
- **Swapped Salamis QIDs**, now fixed locally.
- **Hellenic League:** its summary describes the 323 BC league, but its QID is Q386893, the 481 BC alliance.
- **Duplicate rows:** two "Battle of Salamis (306 BCE)".

Earlier repair passes are recorded in memory and under `output/campaign/audit/`. Read `qid_corruption_audit.py`, the `qid-repair-applied-*.csv` files and `namesake-needs-review-dups-20261006.csv` before you design anything; reuse what works.

## Ground rules

- **Shared checkout.** Work in `/home/pickle/code/history-mapped`; other agents are editing at the same time. Don't commit, and don't run git commands that change state.
- **Files you own:**
  - new `pipeline/audit/` (package, CLI and tests)
  - `docs/implementation-docs/identity-audit.md`
  - outputs under `output/audit/identity-20261031/`
- **Files you don't touch:** the map-story files (`pipeline/map_stories/**`, `api/resources/map-stories/**`, `api/resources/entity-descriptions/**`). Report story-side fixes instead, and the orchestrator applies them.
- **Database:** only the local dev DB. Use `docker compose -f docker/docker-compose.yml exec -T db psql -U history-mapped history-mapped`, or connect from Python with the same credentials the pipeline uses (`pipeline/.env`). Never touch production.
- **Before your first write:** take a backup with `pg_dump` of the affected tables to `output/audit/identity-20261031/backup-<time>.sql.gz`.
- **Logging every write:** write each change in one transaction, and log it to `applied.csv` (table, id, column, old, new, reason, evidence) together with a generated `rollback.sql`.
- **Allowed writes:**
  - set a QID that is missing or wrong;
  - clear a wrong QID when no correct one is found with high confidence;
  - rename for formatting consistency;
  - fix an alias;
  - set `verification_status = needs_review` with a reason.
- **Writes that need the user** (list them, don't do them): merging or deleting rows, deleting relationships, changing `entity_type`, rewriting a summary or description.
- **Wikidata:**
  - Use batched `wbgetentities`, 50 ids per call, cached on disk under `output/audit/cache/`.
  - User-Agent: `history-mapped/1.0 (https://github.com/PickleSoda/history-mapped)`. Never put an email address in it.
  - Keep to at most 5 requests per second, with backoff on 429.
- **Python:** `scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit …`.
- **Reuse the name guard:** `names_conflict`, `candidate_name_ok`, `temporal_fit` and `pick_namesake` in `pipeline/agent/tools/disambiguation.py`. Don't fork them.

## Tasks

- [ ] **C1. Inventory.**
  - Count the entities by type, with and without a QID, and by `verification_status`.
  - Save a snapshot of the counts to compare after the fixes.
- [ ] **C2. QID identity check** for every entity with a QID. Fetch the Wikidata label, aliases, description, P31/P279 class, and dates (P569/P570 for people; P571/P576, P580/P582 or P585 otherwise).
  - **Flag** a row when:
    - (a) its name conflicts with the label and aliases under the name guard;
    - (b) the Wikidata class contradicts the entity type, using an explicit mapping table from type to allowed P31 roots (for example, a person must be Q5; a battle must be Q178561 or a subclass), kept in code with tests;
    - (c) its dates are outside a tolerance (people ±5 years, events ±2 years, polities ±25 years);
    - (d) the QID is a disambiguation page, redirected or deleted.
  - **Resolve redirects** to their target.
- [ ] **C3. Find the correct QID** for each flagged row. Search Wikidata by name, type class and date window, using `wbsearchentities` plus a batched fetch. Score each candidate on name, class, dates and enwiki sitelink. Accept a candidate as high-confidence only when exactly one passes every check and the runner-up is clearly worse.
- [ ] **C4. Duplicates.**
  - **(a)** Two or more rows with the same QID.
  - **(b)** The same normalised name and type, with overlapping dates and no conflicting QIDs.
  - **(c)** Rows that are one entity under a disambiguator variant, for example "Battle of Salamis" against "Battle of Salamis (480 BC)".

  For each group, propose a survivor: the row with the most relationships, a QID, geometry, and the most complete text. For each merge, give the exact command (`pipeline.merge_entities` or whatever that tool's CLI is, so check its `--help`) and say what moves.
- [ ] **C5. Name consistency** across all entities. Report the conventions in use, then normalise only where one convention clearly dominates and the change is mechanical:
  - era suffix style: BC/BCE/AD/CE, and parenthesised years in disambiguators;
  - whitespace and double spaces;
  - stray quotes;
  - capitalisation, such as an all-caps name or a lower-case first word;
  - Wikipedia disambiguators left in names, such as "(general)", "(city)" or "(film)";
  - the "Battle of X" format for battles, and the "Siege of X" format for sieges;
  - person name forms: regnal number and epithet.

  Leave borderline cases in the report.
- [ ] **C6. Text consistency** (report only). Flag rows where:
  - the summary or description names years that fall outside the entity's dates by more than the C2 tolerance;
  - the text describes something of another type, for example "was a city" on a battle row;
  - the summary is identical to another entity's summary.
- [ ] **C7. Relationship sanity** (report only).
  - Relationships whose types are impossible for the endpoint types, using the rules in `docs/entity-model/entity-specification.md` or the relationship enum's constraints. Examples: a non-person commanding a battle, a battle participating in a person.
  - Relationships whose endpoints don't overlap in time by more than the tolerance.
- [ ] **C8. Battle-map identity check.** For the five stories in `api/resources/map-stories/*.json`, check every `entity`, `sides[].polity`, `sides[].commanders[]` and `units[]` QID:
  - against Wikidata, under C2's rules;
  - against the DB entity the API resolves it to: same name family, right era;
  - by the polity's era: for example, Carthage at Cannae must be the ancient polity.

  Write the story-side fixes as a list of `file: path → old QID → new QID (evidence)`. Don't edit those files.
- [ ] **C9. Apply the safe fixes.** Apply the high-confidence QID corrections and clears, the redirect resolutions and the mechanical renames.
  - Fix the known wrong QIDs above. If the comte d'Erlon, Bülow von Dennewitz and the French Imperial Guard rows don't exist, list them as rows to create; don't create them yourself.
  - Then re-run C2 on the changed rows to confirm, and re-take the C1 counts.
- [ ] **C10. Tooling and docs.**
  - **CLI:** `python -m pipeline.audit identity [--only qid|dups|names|text|relations|stories] [--apply-safe] [--limit N]`.
  - **Tests:** cover the type→class mapping, the date tolerance, name normalisation and the duplicate grouping. Use fixtures only, with no network.
  - **Doc:** `docs/implementation-docs/identity-audit.md`, covering how to run the audit, how to read its output, the fix policy, and rollback.

## Outputs

All outputs go under `output/audit/identity-20261031/`:

- `report.md`: a one-page summary with the counts per category and before/after numbers. It points to the CSVs, giving the top 20 items of each category inline.
- `qid-flags.csv` and `qid-fixes-applied.csv`
- `duplicates.csv`, with proposed merge commands
- `names.csv`
- `text-flags.csv`
- `relation-flags.csv`
- `story-fixes.md`
- `rollback.sql` and `backup-*.sql.gz`

**Report** in at most 20 lines:
- the counts flagged and fixed per category;
- the merges and deletes the user needs to run (count and file);
- the story-side QID fixes;
- the test count;
- anything that looked systemic, such as one pipeline stage that keeps producing the same error.
