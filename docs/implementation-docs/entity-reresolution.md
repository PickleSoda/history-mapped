# Entity Re-resolution Runbook

How to fix already-committed entities whose Wikidata QID, type, location, or dates
are wrong — **in place**, without breaking the relationships that point at them.

This exists because of a specific failure mode: the first ingestion batch ran on
free OpenRouter models, which produced a lot of low-quality entity data — wrong
QIDs (generic "forum" the concept instead of the Roman Forum), wrong types
(countries typed `city`), wrong locations (chronicle-centroid points), and
over-anchored dates (dozens of Roman-associated entities pinned to **753 BCE**,
the legendary founding of Rome). The pipeline has since been fixed (P31-aware
resolver, `reasoning_effort`, JSON-retry), but the **already-committed** rows keep
their old values.

## Why you can't just re-run the transcript

The obvious fix — re-run the pipeline over the same transcript — does **not**
reliably work, and it's worth understanding why before reaching for it:

- **Dedup-skip (default mode):** `db_lookup` matches an existing entity and the
  pipeline skips it entirely, so the stale row is never re-resolved.
- **Refresh mode (`--refresh`, see below):** even when you force re-resolution,
  the run only touches the entities the LLM *happens to re-extract that run*.
  Extraction is non-deterministic — a second run of `roman_republic` produced a
  different set of 41 entities and never re-surfaced "Italy"/"Forum"/"Senate", so
  they kept their -753 dates. You cannot guarantee coverage of a *specific* bad
  row by re-running the text.

The reliable approach is to iterate the **actual committed rows** and re-resolve
each one by `entity_id`. That's what `reresolve_entities.py` does.

## Two tools, two jobs

| Tool | Keyed on | Use when |
|------|----------|----------|
| `pipeline agent --refresh` | transcript re-extraction | You want to re-process a *transcript* and force in-place updates of whatever it re-extracts (broad, coverage not guaranteed). |
| `pipeline.reresolve_entities` | **`entity_id`** (by name) | You have *specific* broken entities to fix and need every one of them handled. **Preferred for targeted cleanup.** |

Both preserve `entity_id`, so relationships survive. `--refresh` force-updates via
the import's `findExisting` (QID / OHM id / name+type+era); `reresolve_entities`
updates the exact row it loaded.

## reresolve_entities.py

For each named entity it:

1. **Re-resolves the QID** with the patched resolver (`search_wikidata_by_name` →
   `_rank_candidates` → `fetch_entity_meta` → `rerank_by_type` + `rerank_by_era`),
   so "Forum" → Roman Forum (Q180212), "Norway" → the country (Q20), not a stray
   namesake.
2. **Re-derives `entity_type` (+ group)** from the corrected QID's P31 (`P31_TO_TYPE`,
   built by inverting `EXPECTED_P31` plus hand-curated place/monument/education
   classes). Falls back to the existing type when nothing maps — it never
   downgrades a good type to a guess.
3. **Re-derives geo** — direct `P625` coordinate, else a place-of-association
   coordinate (birthplace/located-in/…).
4. **Re-derives dates** — see policy below.
5. **`UPDATE`s the row by `entity_id`** (and `updateOrCreate`s the temporal range /
   geometry period). `entity_id` is untouched, so every relationship pointing at
   it is preserved.

### Date policy

Overwrite the committed date from Wikidata **only when Wikidata has one**;
otherwise **keep the existing year**. This fixes wrong dates the corrected QID
knows about (Forum -753 → -800) without nulling a correct one the QID happens to
omit (the Giza pyramids genuinely date to ~2600 BCE even though `Q13217298` has no
`P571`). The trade-off: an over-anchor like a Roman institution's 753 BCE persists
when its QID has no Wikidata date — but for Roman institutions that date is the
*traditional* founding and defensible; pin a better QID if you disagree.

### Confidence guard + manual override

- A QID **change** is only accepted at score ≥ `RERESOLVE_ACCEPT` (0.6), and never
  to a creative-work/taxon P31 for a place/polity/event (so "Pyramids" never
  becomes a painting named "Pyramids"). Below the bar, the existing QID is kept
  and only its type/geo/date are refreshed.
- Vague names the resolver can't disambiguate take a **pinned QID**:
  `Name=QID`, e.g. `Pyramids=Q13217298` (Giza Necropolis). Everything is then
  derived from the pinned QID.

### Usage

```bash
# dry run (prints a before/after table, writes nothing)
pipeline/.venv/bin/python3 -m pipeline.reresolve_entities Italy England Norway

# pin a QID for a vague name, then apply
pipeline/.venv/bin/python3 -m pipeline.reresolve_entities --apply \
    Pyramids=Q13217298 England Italy Norway Lebanon Kiev Forum "ancient Rome"

# no args → the built-in known-broken set (DEFAULT_TARGETS)
pipeline/.venv/bin/python3 -m pipeline.reresolve_entities --apply
```

Always dry-run first and read the plan. `--apply` runs in a single transaction and
rolls back on any error.

### Safety / gotchas

- **Take a DB dump first** (`pg_dump … > output/history-mapped-backup-<date>-prereresolve.sql`).
  The repo keeps these snapshots.
- `geometry_periods` has NOT-NULL `start_year` + `provenance_mode` and a
  `gp_derived_requires_source` check — new points are inserted as
  `provenance_mode='manual'` with the entity's start year, and skipped when there
  is no year to anchor them to.
- **Duplicate namesake rows** (e.g. "England" the country *and* "England, Arkansas"
  the city; an "Italy" region vs the country) are left as distinct rows — the tool
  resolves each independently. Merging duplicates is a separate, manual step
  (re-point relations, delete the loser).
- **Same QID on two rows** can result when two rows for one real-world thing get
  pinned to the same QID (e.g. two "Pyramids" rows → Giza). They are not auto-merged.

## Verifying a run

```sql
-- entity_id stable (relations safe) + fixed values
SELECT e.name, e.entity_type, e.wikidata_id, t.start_year
FROM entities e LEFT JOIN entity_temporal_ranges t ON t.entity_id = e.entity_id
WHERE e.name IN ('Forum','Norway','Pyramids');

-- relation count unchanged (nothing orphaned by the update)
SELECT COUNT(*) FROM relationships;
```

## Split-entity duplicates (merge first)

The free-model batch sometimes split one subject into **two rows**: e.g. "Italy"
the country existed as a `city` row carrying *all* the real relationships (Rome
capital_of Italy, Marco Polo born_in Italy, …) but a wrong QID, **plus** a
separate `political_entity` row with the correct QID (Q38) and *zero*
relationships. Re-resolving doesn't collapse these — merge them first:

```bash
# keeps the row with the MOST relationships, folds the duplicate(s) into it
pipeline/.venv/bin/python3 -m pipeline.merge_entities --apply Italy England
# then point the survivor at the right QID/type
pipeline/.venv/bin/python3 -m pipeline.reresolve_entities --apply Italy=Q38 England=Q21
```

`merge_entities` re-points relationships (with dedup + self-loop removal) and
`chronicle_entry_entities` (the one RESTRICT FK), then deletes the loser — whose
`relationships` are CASCADE-cleaned (so **never** merge *away* the relation-rich
row; the tool always keeps it).

## Geometry: write the canonical location, then backfill

Geometry lives in two tables that read by **different surfaces**, and they can
diverge:

| Table | Read by | Role |
|-------|---------|------|
| `geometry_periods` | the **public map** (`MapEntitiesAction`, filtered by year) | time-sliced geometry — the rendered borders/points |
| `entity_locations.geom` | the **admin** "primary location" editor + `entity:backfill` | canonical own-coordinate, source for the derived periods |

Two failure modes come from the split:
- **Coordinate only in `geometry_periods`** → the map shows the entity but admin
  says "location not set" (e.g. China — a real Wikidata point on the map, null
  `entity_locations.geom`). `pipeline/backfill_geo.py` now writes BOTH for its
  Wikidata tiers; the one-shot repair for existing rows is the
  `UPDATE entity_locations … FROM geometry_periods … WHERE created_by IN
  ('geo-backfill:wikidata_p625','geo-backfill:wikidata_place_assoc')` copy.
- **Stale `entity_locations`** → admin/map disagree. `reresolve_entities` writes
  `entity_locations` (an earlier version wrote only `geometry_periods`, which left
  "Italy" canonically at *Italy, Texas* even though the derived points looked
  right). Never mirror the `relationship_inference` tier — it's a neighbour guess,
  not the entity's own location.

After re-resolving, rebuild the periods from the corrected location + dates:

```bash
docker compose -f docker/docker-compose.yml exec app \
  php artisan entity:backfill --entity-id=<entity_id>
```

`entity:backfill` (`BackfillGeometryPeriodsAction`) rebuilds only the periods it
owns (`created_by='backfill:entity'` + relationship-inference). **It does not
delete pipeline-created periods** — so an over-anchored `pipeline:*` territory
period (e.g. an entity pinned to 753 BCE) survives and must be cleared explicitly:

```sql
-- clear -753 over-anchors, keeping entities legitimately founded then
WITH legit AS (SELECT entity_id FROM entities WHERE name IN ('Rome','Roman Kingdom','ancient Rome'))
DELETE FROM geometry_periods WHERE start_year=-753 AND entity_id NOT IN (SELECT entity_id FROM legit);
UPDATE entity_temporal_ranges SET start_year=NULL, start_date=NULL
WHERE start_year=-753 AND entity_id NOT IN (SELECT entity_id FROM legit);
```

### End-to-end recipe for a broken duplicate

1. `merge_entities --apply <Name>` — collapse duplicate rows.
2. `reresolve_entities --apply <Name>=<QID>` — fix QID/type/date + write `entity_locations`.
3. `php artisan entity:backfill --entity-id=<id>` — rebuild `geometry_periods`.
4. (If an over-anchored pipeline period remains) the `-753` cleanup SQL above.

## Related

- `pipeline/repair_committed_data.py` — broader, automatic QID/geo/date *repair*
  pass (fills gaps, only overwrites on high-precision signals). Re-resolution is
  the more aggressive, operator-driven cousin for known-bad rows.
- `pipeline/agent/tools/disambiguation.py` — the P31 + popularity resolver the
  re-resolution reuses.
- Resolver/JSON fixes that stop new bad data: see `pipeline/agent/llm.py`
  (`invoke_json`) and `AgentConfig.reasoning_effort`.
