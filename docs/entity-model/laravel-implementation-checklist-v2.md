# Laravel Implementation Checklist — Entity Model V2

This checklist translates the V2 schema proposal into concrete Laravel work in this repository.

Related spec:
- [schema-proposal-v2-strict-write-derived-timeline.md](./schema-proposal-v2-strict-write-derived-timeline.md)

Related plan:
- [2026-04-06-entity-model-v2-migration.md](../superpowers/plans/2026-04-06-entity-model-v2-migration.md)

---

## 1. GitNexus Impact Notes

The legacy temporal-geometry path had medium-risk blast radius in earlier analysis.

Direct depth-1 dependents were concentrated around legacy temporal-geometry actions, controllers, resources, factories, and tests.

Migration guidance:
- remove legacy temporal-geometry compatibility code in controlled phases
- keep replacements centered on `geometry_periods` and timeline projection paths

---

## 2. Database Checklist

### New tables
- [ ] `entity_aliases`
- [ ] `entity_tags`
- [ ] `entity_temporal_ranges`
- [ ] `entity_locations`
- [ ] `geometry_periods`
- [ ] `entity_timeline_entries`
- [ ] normalized citation tables

### Constraints
- [ ] `geometry_periods` requires geometry
- [ ] `geometry_periods` requires valid year range
- [ ] derived periods require provenance
- [ ] presence periods require `relationship_id`
- [ ] manual periods require app-level citation validation

### Backfill order
1. `entity_aliases`
2. `entity_tags`
3. `entity_temporal_ranges`
4. `entity_locations`
5. `geometry_periods`
6. `entity_timeline_entries`

### Legacy retention during rollout
- [ ] keep legacy entity columns readable until backfill verification passes
- [ ] block new writes to legacy structures behind a feature flag before dropping columns

---

## 3. Model Checklist

### `Entity.php`
- [ ] add `aliases()`
- [ ] add `tags()`
- [ ] add `temporalRanges()`
- [ ] add `locations()`
- [ ] add `geometryPeriods()`
- [ ] add `timelineEntries()`
- [ ] audit legacy temporal-geometry helpers and replace with period-aware equivalents

### New models
- [ ] `EntityAlias`
- [ ] `EntityTag`
- [ ] `EntityTemporalRange`
- [ ] `EntityLocation`
- [ ] `GeometryPeriod`
- [ ] `EntityTimelineEntry`

### Old model handling
- [ ] remove any remaining legacy temporal-geometry compatibility code
- [ ] mark legacy temporal-geometry actions/controllers/resources as deprecated

---

## 4. Relationship and Period Creation Checklist

### Replace legacy temporal-geometry semantics
- [ ] stop treating relationship-driven presence as an independently authored geometry row
- [ ] create derived presence geometry periods from supported relationship types
- [ ] reject manual presence periods that do not reference a relationship

### Relationship types needing special handling
- [ ] `signed_by`
- [ ] `commanded`
- [ ] `fought_at`
- [ ] `victorious_at`
- [ ] `defeated_at`
- [ ] `founded`
- [ ] `born_in`
- [ ] `died_in`
- [ ] `resided_in`
- [ ] `mediated_by`
- [ ] `guaranteed_by`

### Edge cases
- [ ] source entity has no geometry
- [ ] target entity has geometry but source does not
- [ ] relationship has `temporal_start` but no `temporal_end`
- [ ] old temporal geometry row had no provenance and becomes manual-review geometry period
- [ ] existing admin UI attempts to create free-form presence records

---

## 5. Controller and API Checklist

### Existing legacy temporal-geometry endpoints
- [ ] decide whether to preserve route names temporarily
- [ ] serve compatibility payloads from `geometry_periods` or timeline projection
- [ ] block forbidden manual writes through validation

### New endpoints
- [ ] add timeline index endpoint per entity
- [ ] decide whether timeline detail endpoint is necessary
- [ ] expose `source_table` and `source_id` on derived entries for traceability

### Resource layer
- [ ] create dedicated timeline resource
- [ ] keep any required compatibility resource stable until frontend switches
- [ ] ensure geometry serialization stays GeoJSON-compatible

---

## 6. Frontend Binding Checklist

Impacted generated or route-adjacent files from GitNexus query:
- [ ] remove or replace legacy temporal-geometry route bindings in generated JS actions/routes

Questions to settle during implementation:
- [ ] do existing clients need a temporary compatibility route?
- [ ] should timeline get a separate route namespace?
- [ ] should entity detail read timeline entries directly or through a derived summary field?

---

## 7. Map and Detail Read Path Checklist

### Map behavior
- [ ] update map territory queries to read `geometry_periods`
- [ ] preserve temporal filtering behavior
- [ ] preserve bbox filtering behavior
- [ ] maintain fallback to base entity geometry if no matching period exists

### Entity detail behavior
- [ ] replace any legacy temporal-geometry count with period or timeline counts
- [ ] avoid breaking any current Inertia/API payload contracts unexpectedly

### Geo-ref cleanup
- [ ] review legacy orphan georef pruning logic
- [ ] distinguish entity-level primary geo refs from period-level refs
- [ ] avoid deleting shared refs still used by entity or another period

---

## 8. Data Policy Checklist

### Manual geometry period allowed
- [ ] border/extents by period
- [ ] route changes by era
- [ ] spread zones by period
- [ ] migration corridors by period
- [ ] archaeological culture extents by period

### Manual geometry period forbidden
- [ ] narrative-only entries with no geometry
- [ ] duplicate periods with same semantics
- [ ] person-presence without relationship provenance
- [ ] event participation entered as a storytelling shortcut

### Review flags
- [ ] mark legacy temporal geometry rows without provenance for manual audit
- [ ] mark suspicious overlaps in periods for same entity/type/date window
- [ ] mark conflicting manual and derived periods for review

---

## 9. Testing Checklist

Minimum focused coverage:
- [ ] schema tests for new tables and constraints
- [ ] relation tests for `Entity`
- [ ] backfill command tests
- [ ] relationship-derived presence tests
- [ ] admin compatibility endpoint tests
- [ ] API compatibility endpoint tests
- [ ] timeline projection tests
- [ ] map threshold tests
- [ ] entity detail tests
- [ ] geo-ref integrity tests

High-value regression files from current codebase:
- [ ] `api/tests/Feature/Admin/RelationshipControllerTest.php`
- [ ] legacy temporal-geometry compatibility controller/api tests (if retained)
- [ ] `api/tests/Feature/Api/MapEntitiesThresholdTest.php`
- [ ] `api/tests/Feature/Api/EntityDetailGeometryPeriodsCountTest.php`
- [ ] `api/tests/Feature/Feature/EntityGeoRefIntegrityTest.php`
- [ ] `api/tests/Unit/GeometryPeriodBuilderTest.php`

---

## 10. Cutover Checklist

### Before cutover
- [ ] backfill completed successfully
- [ ] compatibility reads verified
- [ ] no failing focused tests in impacted areas
- [ ] timeline rebuild command produces stable output

### During cutover
- [ ] enable V2 write flag
- [ ] disable legacy temporal-geometry writes
- [ ] rebuild timeline projection
- [ ] run focused verification suite

### After cutover
- [ ] audit manual geometry periods created from legacy orphan temporal rows
- [ ] check map and entity detail payloads against real sample entities
- [ ] only then schedule removal of legacy temporal-geometry table/columns and moved entity columns
