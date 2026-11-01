# Identity audit runbook

The identity audit finds entities whose identity is wrong or inconsistent: a
QID that names another thing, a namesake from another era, a duplicate row, a
name that breaks the house style, text that describes something else, or a
relationship that cannot be right. It applies only the fixes that are safe
(non-destructive, high-confidence and reversible) and lists the rest (merges,
deletes, type changes, text rewrites) for a human.

Code: `pipeline/audit/`. Plan: `docs/superpowers/plans/2026-10-31-identity-audit.md`.
It reuses the pipeline's name and namesake guards (`names_conflict`,
`candidate_name_ok`, `temporal_fit` in `pipeline/agent/tools/disambiguation.py`);
earlier one-off repairs live in `output/campaign/audit/`.

## Running it

Run it against the **local** dev DB only. The CLI refuses a non-local
`DATABASE_URL`.

```bash
# read-only: every section, report in output/audit/identity-20261031/
scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit identity

# one or more sections (comma-separated)
scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit identity --only qid,stories

# trial run on 500 QID rows, cache only (no network)
scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit identity --only qid --limit 500 --offline

# apply the safe fixes (backup first, then one transaction)
scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit identity --apply-safe

# rebuild report.md from the outputs on disk (after --apply-safe, a re-run
# would see the fixed DB; this keeps the before/after view)
scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit identity --report-only
```

Options: `--out DIR` (default `output/audit/identity-20261031`), `--workers N`
(parallel Wikidata batches; all workers share one 4 requests/s limit),
`--no-resolve` (skip the C3 searches).

Tests (fixtures only, no network or DB):
`scripts/capped.sh pipeline/.venv/bin/python3 -m pytest pipeline/audit/tests`.

### Wikidata use

- Entities come from `wbgetentities`, 50 ids per call, and are cached in
  `output/audit/cache/wd-entities.jsonl`. Each record keeps the label, aliases,
  description, P31, P279, dates and enwiki title. A re-run makes no request for
  an id it has already seen. Delete a line, or the whole file, to refresh.
- Searches use `wbsearchentities` and are cached in `wd-search.jsonl`.
- Subclass closure (does a P31 class reach "battle" through P279*?) comes from
  the query service, 200 classes per query, cached in `wd-class-roots.json`.
  This is cheaper than walking P279 with `wbgetentities`.
- Every request sends `User-Agent: history-mapped/1.0
  (https://github.com/PickleSoda/history-mapped)`. It never carries an e-mail
  address. The client keeps to 4 requests/s and backs off on 429/503,
  honouring `Retry-After`.

A full first run fetches about 27,000 QIDs, which takes roughly 30 to 40
minutes. A cached re-run takes about a minute.

## What each section checks

| Section | Plan | Output | Writes? |
|---|---|---|---|
| inventory | C1 | `inventory-before.json`, `inventory-after.json` | no |
| `qid` | C2 + C3 | `qid-flags.csv` | QID set/clear, needs_review |
| `places` | C2b | `place-flags.csv` | never (verified proposals become pins) |
| `dups` | C4 | `duplicates.csv` | never (merge commands for the user) |
| `names` | C5 | `names.csv`, `name-conventions.json` | mechanical renames only |
| `text` | C6 | `text-flags.csv` | never |
| `relations` | C7 | `relation-flags.csv` | never |
| `stories` | C8 | `story-refs.csv`, `story-fixes.md` | never (story files are not edited) |
| `--apply-safe` | C9 | `applied.csv`, `qid-fixes-applied.csv`, `qid-recheck.csv`, `rollback.sql`, `backup-*.sql.gz` | yes |

`report.md` is the one-page summary. It gives the counts per category, the
before and after numbers, and the top 20 items of each category.

### C2: QID identity

Each row with a QID is compared with its Wikidata item on four axes.

- **Name.** `candidate_name_ok(row name + aliases, label + aliases)` gives
  `exact`, `compatible`, `markers` (World War I vs II), `near_miss`
  (Qi vs Qing) or `unrelated`. Names equal up to a plural or demonym ending
  ("Khokhars" / "Khokhar") count as `inflected`, which agrees.
- **Class.** The P31 classes are taken through P279* to the root classes in
  `pipeline/audit/classes.py`. `TYPE_RULES` says which roots confirm each
  entity type and which contradict it (a person must be human; a battle must
  be a battle, siege, military operation or campaign). The result is `ok`,
  `unmatched` (an unusual class) or `contradiction` (a person row whose QID is a
  ship). A QID that is itself a class (it has P279) on an individual-type row
  is flagged `generic`, for example "imperial guard" the concept on a specific
  guard unit.
- **Dates.** Birth/death for people. For everything else: inception/dissolved,
  start/end time, or point in time. The tolerance is people ±5 years, events
  ±2 and polities ±25. It widens with a coarse Wikidata precision (decade +10,
  century +100) and by 25 years before 1000 BCE. Beyond the tolerance the
  result is `out_of_tolerance`. When the spans miss each other by more than
  `CONFLICT_GAP` (people and battles 10 years, wars 25, polities 150) it is
  `conflict`, a different era. When only the row's BCE/CE sign is wrong it is
  `sign`.
- **State.** The QID is deleted (`missing`), a `redirect` (resolved to its
  target), or a disambiguation, list, given-name or family-name item.

The signals combine into a verdict. A QID is **wrong** only when the row's own
identity (name, type, dates, text) disagrees with it decisively:

| Rule | When |
|---|---|
| W1 | the QID is deleted |
| W2 | the QID is a disambiguation page, list, category, given or family name |
| W3 | the names conflict: `markers` with a hard signal or dates outside tolerance; `near_miss` only with a hard signal (a decisive class contradiction, a non-polity era conflict, or a concept QID) |
| W4 | the class contradicts the type **decisively** (`DECISIVE` in `classes.py`: a person row whose QID is a film, an article, a ship, a place). An exact name with agreeing dates, or a compatible name with the QID's own dates matching a dated row ("Montaperti", a city row dated 1260, carrying the Battle of Montaperti), softens it to S1, since then the row's type is more likely wrong. Deities and mythical figures don't count as fiction |
| W5 | a different era **and** the names are not compatible |
| W6 | a different era, compatible names (a namesake), **and** the row's text names years of the row's era and none of the QID's (not for polities, whose rows often span many eras) |
| W7 | a concept QID (a lower-case class such as "imperial guard") on a proper-named individual row, unless the row is named exactly like the concept and the class fits |
| W8 | a far era: the spans miss by more than `FAR_GAP` (people and events 50 years, diplomatic relations 100, units and dynasties 150; not polities), and the text does not point to the QID's era |

Any other disagreement is a **suspect** (S1–S9 in `qid-flags.csv`) for a
human. S1 is a class contradiction with agreeing names, so the type may be
wrong. S3 is a namesake whose era differs but where the text doesn't decide.
S5 is a mis-signed date. S6 is dates slightly outside tolerance.

### C3: finding the correct QID

For each wrong row the audit searches Wikidata for the row's name and up to
two aliases. Each candidate is scored on four checks: name (the guard), class
(`ok` and not generic), dates (within tolerance; required for dated types) and
an enwiki sitelink. Two extra limits keep the winner honest: the dates that
confirm it must be year- or month-precise (a "13th century" date confirms
nothing to ±5 years), and a one-word non-person name ("Majlis") must match a
label or alias exactly, not just share a word. A film, album, band, article or
fiction never passes the class check (except media for a `cultural_work` row).
A candidate is accepted only
when it is the **only** one passing all four **and** no other candidate passes
name+class+dates, where a rival's dates may be coarse. If the
winning QID already sits on another row, the row is a duplicate. It goes to
`duplicates.csv` (category `qid_resolution`) instead of getting the QID.

No two rows end up with one QID. If two wrong rows resolve to the same
winner, the row named exactly like it gets the QID and the others become
duplicates. If no row matches it exactly, all of them become duplicates. A
redirect whose target is already on another row is a duplicate too. For an
undated row, a match through one of the row's aliases is not enough: the
primary name must match ("Valabhi" carries the alias "Bhati", a Delhi town).
A city row never takes an administrative district ("Kumbakonam Taluk").

### C2b: same-name places

C2 can't see a city that carries a namesake's QID. The name is exact, the
class fits, and places have no dates to compare. Examples: "Boston" (the
Puritan colony capital) carried Boston, Lincolnshire, and "Montevideo"
carried Montevideo, Minnesota. C2b reads the place names in the QID's
description ("in Lincolnshire, England") and flags the row when none of
them appears in the row's text. It searches the row's name. When exactly
one other same-named place with an enwiki article is described where the
text says, the line is `pin_candidate`. A flag alone is noisy, because a
description and a summary often name different levels ("Hesse, Germany" vs
"East Francia"). So nothing here is written automatically. Verified
candidates go to `pins.csv`.

### C4: duplicates

There are three categories.

- `same_qid`: two or more rows carry the same QID.
- `same_name`: the same normalised name and type, compatible dates (or places
  within 25 km), and no two different QIDs.
- `disambiguator`: "Battle of Salamis" against "Battle of Salamis (480 BCE)",
  where the qualifier's year fits the bare row.

The survivor is the row with the most relationships, then the one with a QID,
then geometry, then the most text. Each line gives the exact command, which
uses `pipeline.merge_entities.merge(cur, survivor, loser)` by id; the
name-based CLI would merge every row of that name. Each line also says what
moves and what the delete drops.

> **Before merging:** `map_stories.entity_id` is `ON DELETE CASCADE`. If the
> loser has a map story (`lost_on_delete` says so), re-point the story first.

### C5: names

`name-conventions.json` counts the conventions in use: era suffixes, year
qualifiers, the epithet article, battle naming and lower-case first words.
The audit applies only mechanical renames, and only where one convention
dominates (≥ 90%) and no same-type row has the new name:

- whitespace;
- a whole name wrapped in quotes;
- `The Battle of X` / `Battle Of X` → `Battle of X`;
- `Alexander The Great` → `Alexander the Great`;
- BC→BCE and AD→CE.

When the normalised tokens change, the old name is kept as an alias.
Everything else (acronyms in capitals, Wikipedia disambiguators such as
"(general)", media disambiguators such as "(film)", non-standard battle names)
is report-only.

### C6 and C7: text and relationships (report only)

- **C6 `text_era`.** The text names years, and none of them is within the
  row's dates ± tolerance.
- **C6 `text_type`.** The summary's leading descriptor is another kind of thing
  ("City in …" on a battle row).
- **C6 `dup_text`.** The summary is identical to another row's.
- **C7 `endpoint_type`.** The relationship type can never join these entity
  types (`ENDPOINT_RULES`, derived from `docs/entity-model/relationships.md`,
  kept loose so that only impossible pairs remain).
- **C7 `endpoint_era`.** A contemporaneous relationship (rules, commanded,
  born_in, …) joins dated endpoints further apart than the tolerance.

### C8: battle maps

Every QID in `api/resources/map-stories/*.json` (entity, side polities,
commanders, units) is checked three ways:

- against Wikidata: name, class, and era (a commander alive at the battle, a
  polity existing then);
- against the DB row the API resolves it to (`SyncMapStoryFileAction::byQid`,
  highest impact first): same name family, the expected type, dated in the
  battle's era;
- commanders without a QID get a proposal when exactly one Wikidata human of
  that name was alive at the battle.

`story-fixes.md` lists `file: path → old QID → new QID (evidence)`, the DB-side
problems, and the rows to create.

## Fix policy (C9)

Applied by `--apply-safe`, nothing else:

| Fix | When |
|---|---|
| `set_qid` | C3 found a unique high-confidence QID not held by another row; or a redirect target; or a hand-verified pin |
| `clear_qid` | the QID is wrong by W1–W5 or W7 (`CLEAR_RULES` in `identity.py`) and C3 found nothing. The old id goes to `attributes._rejected_wikidata_id` (the importer's convention, so it is not re-attached) and the row becomes `needs_review` |
| `needs_review` | W6 or W8 with no C3 winner (the QID is kept: a namesake judged on dates alone is flagged, not cleared), or a wrong QID whose correct id is on another row. The status changes and `identity_audit:<reason>` is appended to `attributes.validation_flags` |
| `rename` / `add_alias` | C5 mechanical renames; aliases from pins |

**Pins** are hand-verified corrections for cases the rules can't settle on
their own. They live in `output/audit/identity-20261031/pins.csv`
(`entity_id, old_qid, new_qid, alias, reason, evidence`; an empty `new_qid`
clears the QID). A pin whose QID is already on another row is skipped and
noted.

The audit never writes the following; they are listed for the user:

- merges and deletes (`duplicates.csv`);
- relationship deletes (`relation-flags.csv`);
- `entity_type` changes (S1 rows);
- summary and description rewrites (`text-flags.csv`);
- story files (`story-fixes.md`);
- new rows (the "rows to create" list in `story-fixes.md`).

Every write is guarded on the value the audit read, so a row someone changed
in the meantime is skipped rather than overwritten. All writes run in one
transaction.

## Rollback

Before the first write, `pg_dump` saves `entities` and `entity_aliases` to
`backup-<time>.sql.gz`. `rollback.sql` holds a guarded inverse of every
applied change, newest batch first:

```bash
docker compose -f docker/docker-compose.yml exec -T db \
  psql -U history-mapped -d history-mapped -f - < output/audit/identity-20261031/rollback.sql
```

Each statement only fires while the column still holds the value the audit
wrote, so later edits survive. For a full restore of the two tables, load the
backup into a scratch database and copy the rows back. Don't restore
`entities` wholesale over a live DB, because its foreign keys cascade.

## Reading the outputs

- `qid-flags.csv`: one line per non-clean QID row. The key columns are
  `verdict` (wrong/suspect/redirect), `rule`, `issues`, `wd_label`,
  `wd_description`, the date columns, `resolution` (the C3 outcome),
  `candidates` (the top 5 with the checks each passed) and `action` (what
  `--apply-safe` does).
- `duplicates.csv`: one line per proposed merge, giving survivor, loser,
  evidence, `moves`, `lost_on_delete` and `merge_command`.
- `names.csv`, `text-flags.csv`, `relation-flags.csv`: one line per finding,
  each with `severity`.
- `story-fixes.md`: the story-side QID changes, the DB-side problems and the
  rows to create.

Production gets these fixes through the normal content transfer from the local
DB (`content-data-transfer.md`). Never run the audit against production.
