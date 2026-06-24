# Data-Quality Runbook

Symptom-indexed guide for fixing bad committed entity/map data — the recurring
classes of problem the early free-model ingestion left behind, and how to fix each
**in place** (preserving `entity_id`, so relationships survive).

All the Python helpers live in `pipeline/` and default to **dry-run**; pass
`--apply` to write. **Take a DB dump first** —
`docker compose -f docker/docker-compose.yml exec db pg_dump -U history-mapped -d history-mapped --clean --if-exists > output/history-mapped-backup-<date>.sql`.

See [entity-reresolution.md](entity-reresolution.md) for the deep dive on QID
re-resolution, merging, and the geometry model.

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
| `backfill_geo.py` | bulk Wikidata coordinates (writes both tables) (§1) |
| `locate_events.py` / `hand_locate_events.py` | event locations (§9) |
| `php artisan entity:backfill` | materialise `geometry_periods` from canonical location |
