# Data-Quality Runbook

Symptom-indexed guide for fixing bad committed entity/map data — the recurring
classes of problem the early free-model ingestion left behind, and how to fix each
**in place** (preserving `entity_id`, so relationships survive).

All the Python helpers live in `pipeline/` and default to **dry-run**; pass
`--apply` to write. **Take a DB dump first** —
`docker compose -f docker/docker-compose.yml exec db pg_dump -U history-mapped -d history-mapped --clean --if-exists > output/history-mapped-backup-<date>.sql`.

See [entity-reresolution.md](entity-reresolution.md) for the deep dive on QID
re-resolution, merging, and the geometry model. These fixes write **directly to the
DB**, not the JSONL — so to get them to prod, transfer the database, don't
re-import: [content-data-transfer.md](content-data-transfer.md).

---

## The geometry/location data model (read this first)

Two tables, read by **different surfaces** — they can diverge:

| Table | Read by | Role |
|-------|---------|------|
| `geometry_periods` | the **public map** (`MapEntitiesAction`, filtered by year via `int4range(start_year, end_year+1)`) | the rendered, time-sliced geometry |
| `entity_locations.geom` | the **admin** primary-location editor + `entity:backfill` | the canonical own-coordinate; source the periods derive from |

The canonical flow is: write `entity_locations.geom` → run
`php artisan entity:backfill [--entity-id=<id>]` → it materialises
`geometry_periods` from the location + the entity's temporal ranges (+ derived
presence periods from relationships). **Most fixes below set `entity_locations`
then backfill.**

`entity:backfill` gotchas:
- It only deletes/rebuilds periods it owns (`created_by='backfill:entity'` + its
  relationship-inference rows). It does **not** touch `pipeline:*` periods — a
  stale one (e.g. an over-anchored year) must be deleted explicitly.
- It regenerates **presence** periods from **relationship dates** — so a bad year
  on a *relationship* comes back after every backfill until that date is cleared.

---

## 1. Entity shows on the map but admin says "location not set"

**Cause:** a coordinate landed only in `geometry_periods` (e.g. `backfill_geo.py`'s
Wikidata tiers), never in canonical `entity_locations.geom`.

**Fix (one-shot, for the ~all existing):**
```sql
UPDATE entity_locations el SET geom = sub.geom, updated_at = now()
FROM (
  SELECT DISTINCT ON (gp.entity_id) gp.entity_id, gp.geom
  FROM geometry_periods gp
  WHERE gp.geom IS NOT NULL
    AND gp.created_by IN ('geo-backfill:wikidata_p625','geo-backfill:wikidata_place_assoc')
  ORDER BY gp.entity_id, (gp.created_by='geo-backfill:wikidata_p625') DESC
) sub
WHERE el.entity_id = sub.entity_id AND el.is_primary AND el.geom IS NULL AND el.territory_geom IS NULL;
```
The source is already fixed: `pipeline/backfill_geo.py` now writes BOTH tables for
its Wikidata tiers. Never mirror the `relationship_inference` tier — it's a guess.

**Generalised case — "no marker although it's on the map"** (e.g. Reconquista,
"Invention of Gunpowder…"): the entity's *only* geom is a derived `presence`
period, so the canonical table is empty and the detail-panel marker shows nothing.
Copy from ANY geom-bearing period, preferring `territory` over `presence`:
```sql
WITH src AS (
  SELECT DISTINCT ON (gp.entity_id) gp.entity_id, gp.geom FROM geometry_periods gp
  WHERE gp.geom IS NOT NULL ORDER BY gp.entity_id, (gp.period_type='territory') DESC, gp.start_year)
UPDATE entity_locations el SET geom=src.geom, location_method='source_database', updated_at=now()
FROM src WHERE el.entity_id=src.entity_id AND el.is_primary AND el.geom IS NULL AND el.territory_geom IS NULL;
```
(INSERT the same for entities with no primary-location row.) Then `entity:backfill`.

## 2. Entity on the wrong continent (e.g. "Italy" in Texas)

**Cause:** stale/wrong `entity_locations.geom` from a wrong-namesake QID, or a fix
that updated only `geometry_periods`.

**Fix:** `pipeline/reresolve_entities.py` re-resolves the QID (patched P31 +
popularity resolver), then re-derives type/geo/date and writes `entity_locations`.
For a vague name pin the QID: `reresolve_entities --apply Pyramids=Q13217298`.
Then `entity:backfill --entity-id=<id>`.

## 3. Two of the same place (split-entity duplicate)

E.g. "Italy" exists as a `city` row holding ALL the relationships (wrong QID) AND a
`political_entity` row with the right QID but zero relationships.

**Fix:** merge, then fix the survivor's QID:
```bash
pipeline/.venv/bin/python3 -m pipeline.merge_entities --apply Italy England
pipeline/.venv/bin/python3 -m pipeline.reresolve_entities --apply Italy=Q38 England=Q21
```
`merge_entities` keeps the relation-rich row and re-points relationships +
`chronicle_entry_entities`. For name-VARIANT dups ("United States" vs "United
States of America"), call `merge(cur, survivor_id, loser_id)` directly with ids.

## 4. A wrong year all over the map (over-anchor cascade, e.g. -753)

A bad date propagates into **four** tables. Clearing only some lets
`entity:backfill` regenerate it. Clear all, keeping legitimately-dated entities:
```sql
WITH legit AS (SELECT entity_id FROM entities WHERE name IN ('Rome','Roman Kingdom','ancient Rome'))
-- 1. entity dates
UPDATE entity_temporal_ranges SET start_year=NULL, start_date=NULL
  WHERE start_year=-753 AND entity_id NOT IN (SELECT entity_id FROM legit);
-- 2. map geometry
DELETE FROM geometry_periods WHERE start_year=-753 AND entity_id NOT IN (SELECT entity_id FROM legit);
-- 3. RELATIONSHIP dates  ← the one people forget; backfill rebuilds presence periods from these
UPDATE relationships SET start_year=NULL, end_year=NULL, temporal_start=NULL, temporal_end=NULL WHERE start_year=-753 OR end_year=-753;
-- 4. chronicle entries (keep the genuinely-that-year ones)
UPDATE chronicle_entries SET start_year=NULL, end_year=NULL WHERE start_year=-753 AND narrative_text NOT ILIKE '%founding of rome%';
```

## 5. Entity only appears at ONE year on the map (e.g. gunpowder at 800)

**Cause:** an ongoing entity (`entity_temporal_ranges.end_year IS NULL`) had its
geometry period collapsed to a single year. The map's `int4range` then matches only
that year.

**Fixed in code** (`BackfillGeometryPeriodsAction`: keep `end_year` NULL = ongoing,
only require `start_year`). **Data repair for existing rows:**
```sql
UPDATE geometry_periods gp SET end_year = NULL, updated_at = now()
FROM entity_temporal_ranges t
WHERE t.entity_id=gp.entity_id AND t.is_primary
  AND gp.period_type='territory' AND gp.start_year=gp.end_year
  AND t.end_year IS NULL AND t.start_year=gp.start_year;
```
(Point-in-time events keep `start_year=end_year` — they have a non-null entity end.)

### 5b. An EVENT spans from its date to the present (the inverse)

**Cause:** the §5 "keep NULL = ongoing" rule is right for a polity/monument that
still exists, but **wrong for an event** — a battle in −334 with `end_year IS NULL`
then renders on the map for *every* year from −334 to today.

**Fixed in code** (`BackfillGeometryPeriodsAction`): for `entity_group='EVENT'`,
an open end collapses to a point (`end_year = start_year`). Non-events keep
NULL = ongoing. **Data repair** = just re-run backfill on the affected events:
```sql
SELECT DISTINCT e.entity_id FROM entities e
JOIN geometry_periods gp ON gp.entity_id=e.entity_id
WHERE gp.period_type='territory' AND gp.end_year IS NULL AND e.entity_group='EVENT';
-- then: php artisan entity:backfill --entity-id=<id>  (per id)
```

**Display side (decade-sticky).** A point event would only appear at its exact year
on the continuous timeline. `MapEntitiesAction` + `MapEntitiesByYearAction` pad an
EVENT's effective `int4range` by ±10y at query time (`start_year-10` ..
`COALESCE(end_year,start_year)+11`), so it surfaces near its time without bleeding
across a century. The stored period stays a precise point — only the match widens.

## 6. Geometry silently won't materialise after setting a location

**Cause:** `entity_locations.location_method` is cast to the
`LocationResolutionMethod` enum. An invalid value (e.g. `'manual'`) throws inside
`BackfillLocationsAction` and aborts the backfill for that entity — no geometry,
no obvious error in the summary.

**Valid values:** `ohm_nominatim`, `wikidata`, `geonames`, `pleiades`,
`llm_disambiguation`, `human_assigned`, `source_database`. Use `'human_assigned'`
for hand-set points, `'wikidata'` for Wikidata-derived.
```sql
UPDATE entity_locations SET location_method='human_assigned' WHERE location_method='manual';
```

## 7. Odd date range strings (e.g. "unknown", "1st century", "present")

`EntityResource` exposes `start_date`/`end_date` verbatim; the UI expects a signed
year string (it formats `-563` → "563 BCE"). Normalise to the int year or null:
```sql
UPDATE entity_temporal_ranges SET start_date = CASE WHEN start_year IS NULL THEN NULL ELSE start_year::text END
  WHERE start_date IS NOT NULL AND start_date !~ '^-?[0-9]+$';
UPDATE entity_temporal_ranges SET end_date = CASE WHEN end_year IS NULL THEN NULL ELSE end_year::text END
  WHERE end_date IS NOT NULL AND end_date !~ '^-?[0-9]+$';
```

## 8. A "century" was parsed into a tiny year (e.g. "7th century" → year 7)

**Detect:** entities with `start_year`/`end_year` in ~1–21 that are clearly from
another era (Greek fire=7, Iliad=8, Byzantium=7). Distinguish from legitimately
early-CE entities (Jesus, Paul, Augustus) by knowing the entity. Wikidata usually
can't auto-fix these (no `P571`), so **hand-correct** with a `VALUES` join:
```sql
UPDATE entity_temporal_ranges t SET start_year=v.sy, end_year=v.ey, start_date=v.sy::text,
  end_date=CASE WHEN v.ey IS NULL THEN NULL ELSE v.ey::text END
FROM (VALUES ('Byzantium','city',-667,330), ('Iliad','cultural_work',-750,-750)) AS v(name,etype,sy,ey)
JOIN entities e ON e.name=v.name AND e.entity_type::text=v.etype
WHERE t.entity_id=e.entity_id AND t.is_primary;
```
Then `entity:backfill --entity-id=<id>` per entity.

## 9. Event types not on the map

Events (battles, wars, treaties, …) often lack geometry. Located in priority order:
1. `pipeline/locate_events.py` — own Wikidata `P625` (battles), else a *located
   place-neighbour* via relationships (guarded against borrowing from
   persons/concepts, whose own location is often a wrong-namesake guess).
2. `pipeline/hand_locate_events.py` — hand-assigned representative coordinates +
   years for the well-known abstract events (COVID→Wuhan, Holocaust→Poland, …).

Both write `entity_locations`; run `entity:backfill` after. An event needs **both
a coordinate and a year** — the backfill skips year-less rows.

## 10. Malformed entity names (named just by a year, e.g. "1666 CE")

Artifacts of list-style transcripts. Identify from the summary/QID, then rename +
re-type + re-QID:
```sql
UPDATE entities SET name='Great Fire of London', wikidata_id='Q164679', entity_type='event_natural_disaster'
  WHERE entity_id='<id>';
```
Find them: `WHERE name ~ '^[0-9]{3,4}( CE)?$'`. Set a location and backfill as in §9.

---

## Tool index (`pipeline/`)

| Tool | Fixes |
|------|-------|
| `reresolve_entities.py` | wrong QID/type/geo/date, in place (§2, §3, §8) |
| `merge_entities.py` | split-entity duplicates (§3) |
| `repair_committed_data.py` | bulk QID verify + gap-fill geo/dates |
| `backfill_summaries.py` | entities missing a summary |
| `backfill_geo.py` | map points from the entity's own OHM feature (QID-tagged; admin_centre/label for polities), else its own Wikidata P625 for point-like types; writes both tables, ties the period to the OHM ref; plan CSV in `output/audit/geo-backfill-*/` (§1) |
| `backfill_dates.py` | start/end years for undated entities from their own Wikidata item (per-type properties; year or decade precision; no conflicting or part-scoped values; never before the entity's own dated DB facts); writes `entity_temporal_ranges` only, then rebuilds those entities' timelines; run before `backfill_geo.py`; plan CSV, pre-apply dump and rollback in `output/audit/dates-backfill-*/` |
| `audit_ohm_refs.py` | name-only OHM refs that fail backfill_geo's QID-tag rule: WRONG / OK / UNSURE per ref (other item's tag, name, kind, distance from own P625 or capital, dates); `--apply` deactivates WRONG refs without geometry (`source_meta.deactivated_by`), moves their `primary_geo_ref_id`; verdicts, backup and rollback in `output/audit/ohm-refs-*/` |
| `locate_events.py` / `hand_locate_events.py` | event locations (§9) |
| `php artisan entity:backfill` | materialise `geometry_periods` from canonical location |

---

## OHM link backfill (2026-10-31)

This run filled temporal years and tags on the existing OHM geo-refs. It also linked OHM features to entities by Wikidata id. The run was against the dev DB, from the `feat/martin-tiles-ohm-correlation` worktree.

### Commands

```bash
WT=/home/pickle/code/history-mapped/.claude/worktrees/martin-tiles
PHP="docker run --rm --network history-mapped_default -v $WT/api:/var/www/html -v history-mapped_api_vendor:/var/www/html/vendor -w /var/www/html history-mapped-app"

# 1. Export the OHM ids already referenced by entity_geo_refs (the container mounts only api/)
$PHP php artisan pipeline:export-ohm-ref-ids storage/app/ohm_ref_ids.txt
cp $WT/api/storage/app/ohm_ref_ids.txt $WT/output/ohm_ref_ids.txt

# 2. Tags-only Overpass fetch (boundaries, places with wikidata, then the exported ids)
cd $WT && uv run python -m pipeline ohm-links fetch --run-id 2026-10-31 --ids-file output/ohm_ref_ids.txt

# 3. Import (each chunk commits on its own, so queue/scheduler can keep running)
mkdir -p $WT/api/storage/app/ohm_links/2026-10-31
cp $WT/output/ohm_links/2026-10-31/ohm_links.jsonl $WT/api/storage/app/ohm_links/2026-10-31/
$PHP php artisan pipeline:import-ohm-links storage/app/ohm_links/2026-10-31/ohm_links.jsonl --run-id=2026-10-31 --dry-run
$PHP php artisan pipeline:import-ohm-links storage/app/ohm_links/2026-10-31/ohm_links.jsonl --run-id=2026-10-31
```

### Fetch (`output/ohm_links/2026-10-31/manifest.json`)

- **Export:** 3,255 distinct ids (1,496 node, 1,142 relation, 617 way). These come from 3,305 refs, because some entities share an OHM feature.
- **Overpass fetch:** 40 s wall time, no retries. Boundaries took 18.6 s, places 12.4 s, and 7 id batches about 1 s each.

| Source | Elements |
|--------|---------:|
| boundaries (`relation["boundary"="administrative"]`) | 78,828 |
| places (`nwr["place"]["wikidata"]`) | 52,209 |
| ids (exported refs) | 3,248 of 3,255 |
| **elements / merged records / duplicates** | 134,285 / **111,567** / 22,718 |

- **Record breakdown:** relation 82,772, node 27,791, way 1,004.
- **Wikidata ids:** 85,190 records carry a `wikidata_id` (51,146 distinct).
- **Boundaries:** 79,012 records have `admin_level`.
- **Overlap with the dev DB:** 5,826 records have a QID found in `entities.wikidata_id` (1,815 of 27,177 distinct entity QIDs).
- **Not returned by Overpass** (probably deleted or redacted in OHM; their refs keep no years):
  - node/2108692917, node/2108734354
  - relation/2694198, relation/2694201, relation/2828418, relation/2848338, relation/2957565

### Import counters

The dry run and the real run returned identical counters. Each took 19 s wall time.

| Counter | Value |
|---------|------:|
| records | 111,567 |
| refs_updated | 3,120 |
| refs_created | 4,476 |
| skipped_existing | 1,350 |
| invalid_years | 40 |
| qid_duplicates | 0 |
| unmatched | 103,896 |
| malformed | 0 |

The 4,476 new refs (`source_meta->>'run_id' = '2026-10-31'`) break down as follows. The "with years" column counts refs that have a `temporal_start_year`.

| Type | Role | Refs | With years |
|------|------|-----:|-----------:|
| relation | candidate | 3,448 | 3,440 |
| relation | primary | 180 | 178 |
| node | candidate | 740 | 730 |
| node | primary | 108 | 107 |

They cover 288 entities that had no OHM ref before. Most new refs are `candidate`: OHM keeps one boundary relation per period, so a single QID often matches many relations.

### Before / after (dev DB)

| Metric | Before | After |
|--------|-------:|------:|
| Entities with an active OHM ref | 3,305 | 3,593 |
| Polities linked to an OHM relation | 766 / 17,515 | 958 / 17,515 |
| OHM refs with `temporal_start_year` | 0 / 3,305 | 7,391 / 7,781 |
| OHM refs by role (all active) | primary 3,305 | primary 3,593, candidate 4,188 |
| Tile features with `ohm_osm_id` (`tiles.atlas_entity_features`) | 62 / 20,676 | 299 / 20,676 |
| Linked entities without a geometry period (gap) | 3,243 | 3,294 |
| Gap entities with a primary location point **and** a primary temporal range | 1 | 1 |

Sanity sample of new refs:

| Entity | Role | OHM ref | OHM `name` | OHM years | Entity years |
|--------|------|---------|-----------|-----------|--------------|
| Rozvi Empire | primary | relation/2914608 | Rozvi | 1681–1822 | 1683–1866 |
| Kingdom of León | candidate | node/2100809014 | Reino de León | 910–1071 | 910–1833 |
| Confederation of the Rhine | candidate | relation/2914481 | Rheinbund | 1810–1810 | 1806–1813 |
| British Empire | candidate | relation/2831545 | British Empire | 1890–1890 | 1707–1997 |
| Israel | candidate | relation/2863758 | ישראל | 1982–1994 | 1948– |

### The linked-but-unmapped gap (not addressed by this run)

After the run, 3,294 entities have an active OHM ref but no `geometry_periods` row, so they cannot appear in the tiles.

- **By group:** 1,993 PLACE, 1,218 POLITY, 80 EVENT, 3 CULTURE.
- **Existing backfill path:** `php artisan entity:backfill` (`BackfillEntityAction` → `App\Actions\Entity\BackfillGeometryPeriodsAction`). It turns an entity's primary `entity_locations` geometry plus its temporal ranges into geometry periods.
- **Why it would place few entities:** the action writes nothing when the primary location has no geometry. All 3,294 entities have an `entity_locations` row, but:
  - only 41 have a primary location with geometry;
  - 2,032 have a primary temporal range with a start year;
  - only 1 has both.

  So the backfill would give at most 41 of them a period.
- **What the rest need:** a location from the place-repair tools, or geometry derived from the linked OHM feature.

Both options are a separate decision. `entity:backfill` was **not** run as part of this backfill.
