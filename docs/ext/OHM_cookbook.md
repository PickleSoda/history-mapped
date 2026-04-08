# OHM Borders & Country Names — Cookbook

A practical guide to extracting administrative boundaries and their names from OpenHistoricalMap (OHM) for ingestion into WikiGlobe's PostGIS database.

---

## 1. What OHM gives you

OHM is OSM's data model with a time dimension bolted on. Boundaries are **relations** of type `boundary=administrative` with an `admin_level` tag. Every feature can carry `start_date` and `end_date` tags, which is how OHM filters the map by year.

**Key facts:**

- Data model is identical to OSM: nodes, ways, relations, tags.
- Boundaries are **multipolygon-like relations** — a set of `way` members with `outer`/`inner` roles forming closed rings. You must assemble the geometry yourself from the member ways.
- Dates follow **ISO 8601 in the proleptic Gregorian calendar**. BCE years are negative: `0000` = 1 BCE, `-0001` = 2 BCE, `-0500-01-01` = 501 BCE. Range is roughly `-4000-01-01` through the current year.
- Licensing is **per-feature** — mostly CC0, but some features are ODbL or CC-BY-SA. You need to respect this at ingestion time.
- A boundary that has evolved over time is represented as **multiple independent boundary relations**, one per stage, tied together by a **`type=chronology`** super-relation. San Marino has five; the Roman Empire has many.

---

## 2. The tag schema you actually care about

For any `relation` with `type=boundary` + `boundary=administrative`:

| Tag | Meaning | Example |
|---|---|---|
| `admin_level` | Hierarchical level. `2` = sovereign state, `4` = state/province, `6` = county, etc. | `2` |
| `name` | Canonical name, usually in the local language/script | `Българско царство` |
| `name:en`, `name:fr`, `name:ar`, … | Localized names | `Kingdom of Bulgaria` |
| `name:etymology`, `old_name`, `alt_name` | Variants, historic spellings | — |
| `start_date` | ISO 8601, inclusive. Feature is valid **from** this date. | `1908-10-05` |
| `end_date` | ISO 8601, inclusive. Feature is valid **through** this date. Absent = still current. | `1946-09-15` |
| `start_event`, `end_event` | Short description of why the feature began/ended | `Declaration of independence` |
| `wikidata` | QID — your hook into Wikidata for everything else | `Q219` |
| `wikipedia` | `lang:Article title` | `en:Kingdom of Bulgaria` |
| `ISO3166-1`, `ISO3166-1:alpha2`, `ISO3166-1:alpha3` | On modern countries only | `BG`, `BGR` |

**Date quirks to handle in code:**

- `start_date` may be just a year (`1908`), year-month (`1908-10`), or full date. Parse accordingly.
- Negative years: `-0500` is valid, and string comparisons will lie to you (`"-0500" < "1000"` is true lexically and temporally, but `"-0500" < "-1000"` is lexically true and temporally **false**). Always parse to a signed integer year before comparing.
- A feature with no `end_date` is still extant.
- The end date is **inclusive** (the feature is valid "through" that date), so when filtering "what existed on date X", use `start_date <= X AND (end_date IS NULL OR end_date >= X)`.

---

## 3. How to bring the data — three paths

### Path A — Overpass API (selective, tens of MB)

Endpoint: `https://overpass-api.openhistoricalmap.org/api/interpreter`

Good for: testing, single-period snapshots, a handful of countries, iterating on schema mapping.

Bad for: "all borders, all time, worldwide" — it will time out or blow the server's memory budget. Overpass is tuned for selective queries, not bulk dumps. The OSM wiki explicitly recommends planet dumps for country-sized-or-larger extracts.

### Path B — Planet dump (the one you want for full coverage)

URL pattern: `https://planet.openhistoricalmap.org/planet/` — browse for the latest file.

Two flavors:
- **Daily snapshot** — current state of the database, every feature at its latest version. This is what you want.
- **Weekly full-history** — every version of every feature, for tracking edits to the database itself. You do **not** want this unless you're auditing contributor changes.

The daily snapshot is a `.osm.pbf` file (Protocol Buffers, compact binary OSM format). Full planet is in the low GBs — totally manageable.

### Path C — Vector tiles

OHM publishes MapLibre-compatible vector tilesets. These are for **rendering**, not extraction. Geometries are simplified per zoom level and clipped to tile boundaries. Do not use them as your ingestion source. Use them only in the frontend for display.

**Recommendation for WikiGlobe:** Path B for the bulk ingest, Path A for targeted refreshes and ad-hoc queries.

---

## 4. Overpass cookbook

### 4.1 Endpoint and conventions

```
POST https://overpass-api.openhistoricalmap.org/api/interpreter
Content-Type: text/plain
Body: <OverpassQL query>
```

You can also POST via `wget`/`curl` with `--post-file=query.ql`. Output format is controlled by the `[out:...]` header: `json` (default, easiest), `xml`, or `csv`.

**Important:** OHM uses the same Overpass server software as OSM but a separate instance. The public Overpass turbo at `overpass-turbo.eu` queries OSM by default — use `https://overpass-turbo.openhistoricalmap.org/` for OHM, or inject `{{data:overpass,server=https://overpass-api.openhistoricalmap.org/api/}}` into your query.

### 4.2 Query — all sovereign-state boundaries at a given date

```overpassql
[out:json][timeout:600];
relation["boundary"="administrative"]["admin_level"="2"]
  (if: t["start_date"] <= "1914-07-28"
      && (!is_tag("end_date") || t["end_date"] >= "1914-07-28"));
out geom;
```

The `(if: ...)` filter is OHM's time-filtering idiom. `out geom;` emits each relation with the full coordinate geometry of its member ways inlined — critical, because otherwise you just get way IDs and have to round-trip.

### 4.3 Query — every admin-level-2 boundary ever, worldwide

This is the "max range" query — no bbox, no date filter.

```overpassql
[out:json][timeout:1800];
relation["boundary"="administrative"]["admin_level"="2"];
out geom;
```

Expect this to be slow and possibly to hit server limits. If it fails, either (a) fall back to the planet dump, or (b) shard by continent bbox and union the results client-side.

### 4.4 Query — all admin levels in a bbox, at a date

```overpassql
[out:json][timeout:600];
relation(35,-12,60,40)["boundary"="administrative"]
  (if: t["start_date"] <= "1000-01-01"
      && (!is_tag("end_date") || t["end_date"] >= "1000-01-01"));
out geom;
```

Bbox order is `(south, west, north, east)`.

### 4.5 Query — just the chronology super-relations for polities

```overpassql
[out:json][timeout:300];
relation["type"="chronology"]["boundary"="administrative"];
out body;
(._;>;);
out geom;
```

The `(._;>;);` recursion pulls in all members (the constituent boundary relations) so you get the full chronology tree.

### 4.6 GeoJSON export from Overpass turbo

In the OHM Overpass turbo UI, run the query and use **Export → GeoJSON**. Under the hood it runs [`osmtogeojson`](https://github.com/tyrasd/osmtogeojson) on the result. For programmatic use, call `osmtogeojson` yourself — see §5.

---

## 5. Parsing the output

### 5.1 From Overpass JSON

Overpass JSON for a `relation` with `out geom` looks roughly like this:

```json
{
  "version": 0.6,
  "elements": [
    {
      "type": "relation",
      "id": 2790811,
      "tags": {
        "boundary": "administrative",
        "admin_level": "2",
        "name": "Българско царство",
        "name:en": "Kingdom of Bulgaria",
        "start_date": "1908-10-05",
        "end_date": "1946-09-15",
        "wikidata": "Q219",
        "type": "boundary"
      },
      "members": [
        {
          "type": "way",
          "ref": 123456,
          "role": "outer",
          "geometry": [
            {"lat": 44.21, "lon": 22.67},
            {"lat": 44.10, "lon": 22.98}
          ]
        }
      ]
    }
  ]
}
```

Two things matter:

1. **Geometry assembly.** A boundary relation has N `outer` ways and M `inner` ways. You need to stitch ways that share endpoints into closed rings, then build a MultiPolygon with outer rings as shells and inner rings as holes. **Do not write this yourself.** Use `osmtogeojson` (Node/browser) or `osmium export` (CLI) — they handle gaps, reversed ways, and multi-ring outers correctly.
2. **Tags become properties** — flat key/value map. Lift the ones you care about into typed columns during ingestion.

### 5.2 From a planet PBF

The canonical tool is **[Osmium](https://osmcode.org/osmium-tool/)**. Install: `apt install osmium-tool` or `brew install osmium-tool`.

**Step 1 — filter to just administrative boundaries:**

```bash
osmium tags-filter planet-ohm-latest.osm.pbf \
  r/boundary=administrative \
  -o admin-boundaries.osm.pbf
```

The `r/` prefix means "relations only". This drops ~99% of the planet and gets you a small file with only the relations you want plus their referenced ways and nodes (osmium pulls referenced members automatically).

**Step 2 — export to GeoJSONSeq (one feature per line, streamable):**

```bash
osmium export admin-boundaries.osm.pbf \
  --geometry-types=polygon \
  --output-format=geojsonseq \
  -o admin-boundaries.geojsonseq
```

This is where osmium does the hard work: assembling rings, handling inners, producing valid MultiPolygons, and attaching all tags as properties.

**Step 3 — load into PostGIS** with `ogr2ogr`:

```bash
ogr2ogr -f PostgreSQL \
  PG:"dbname=wikiglobe user=..." \
  admin-boundaries.geojsonseq \
  -nln ohm_admin_raw \
  -lco GEOMETRY_NAME=geom \
  -lco FID=ohm_id \
  -nlt MULTIPOLYGON \
  -t_srs EPSG:4326
```

You now have a raw table with all OHM admin boundaries, their tags as columns (or a single `hstore`/`jsonb` column depending on ogr flags), and valid PostGIS geometry. From here you transform into your domain schema.

### 5.3 Filtering by date after ingestion

Once loaded, the time filter is a SQL predicate, not an Overpass query. Parse `start_date` / `end_date` into signed-integer years (or into two `date` columns with a sentinel for BCE) and index them. Then:

```sql
-- Everything that existed on 1914-07-28
SELECT *
FROM ohm_admin_raw
WHERE start_year <= 1914
  AND (end_year IS NULL OR end_year >= 1914)
  AND admin_level = 2;
```

This is the right place to do temporal filtering once data is local. Push date filters to Overpass only when you're doing one-off pulls.

---

## 6. Date parsing — the painful details

OHM's dates are ISO 8601 but with three traps:

1. **Partial dates.** `1908` is valid and means "some time in 1908". `1908-10` means "some time in October 1908". Decide up front how you normalize: typically, for `start_date` treat partial as the earliest possible instant (`1908-01-01`), and for `end_date` the latest (`1908-12-31`). Store the original string somewhere so you don't lose precision.
2. **BCE years.** `-0500-01-01` is 501 BCE in the proleptic Gregorian calendar. Python's `datetime` doesn't support negative years. Use a library like [`edtf`](https://pypi.org/project/edtf/) or just parse into a signed `(year, month, day)` tuple and a signed integer year for indexing.
3. **End-date inclusivity.** OHM's time slider treats `end_date` as the last date the feature is valid — inclusive. Your query must use `>=`, not `>`. The OHM wiki has a subtle warning about this related to string comparison of year prefixes (`"1975-01-01"` sorts after `"1975"`), which is why they always compare against a year one greater than the target when using string compare in Overpass. In SQL with parsed dates you don't have this problem.

---

## 7. Chronology relations — evolving polities

A single polity that changes borders over time is modeled as:

- N boundary relations, each valid for a date range, each with its own geometry and `start_date`/`end_date`.
- One `type=chronology` relation whose members are those N boundary relations.

**Ingestion implication for WikiGlobe:** a WikiGlobe *POLITY* entity corresponds to the **chronology relation**, and each boundary-version-in-time becomes a row in your multi-temporal geometry table keyed back to that polity. When you ingest, you should:

1. Pull all `type=chronology` relations with `boundary=administrative` in their members.
2. For each chronology, treat the chronology's own tags (`name`, `wikidata`, etc.) as the canonical entity identity.
3. For each member boundary relation, insert a geometry-version row with its own start/end and geometry.
4. Polities without a chronology (the common case — a country whose borders never changed, or was only mapped once) get a single geometry-version row.

Not every evolving polity has a chronology yet — OHM coverage is uneven. Plan for polities where you'll need to infer the chronology from date-overlapping boundary relations that share a `wikidata` tag.

---

## 8. Recommended pipeline for WikiGlobe

```
[daily OHM planet PBF]
        │
        │  osmium tags-filter  (r/boundary=administrative)
        ▼
[admin-only PBF, ~tens of MB]
        │
        │  osmium export --geometry-types=polygon  (assembles multipolygons)
        ▼
[GeoJSONSeq, one feature per line]
        │
        │  ogr2ogr → PostGIS staging table (ohm_admin_raw)
        ▼
[Laravel ingestion job]
        │
        │  - parse start_date/end_date → (start_year, start_date_precise, end_year, end_date_precise)
        │  - resolve wikidata QID → link/create POLITY entity
        │  - group by chronology relation OR by shared wikidata
        │  - insert into polity + polity_geometry_version tables
        │  - mark verification_status = 'ohm_imported' (needs editorial review)
        ▼
[WikiGlobe canonical schema]
```

**Refresh strategy:** nightly `osmium` filter against the latest planet, diff against your staging table by OHM relation ID, and only re-ingest changed relations. OHM assigns stable relation IDs, so diffing works.

**For targeted updates** (a single country, a specific period), skip the planet entirely and go straight to Overpass with a bbox + date filter — much faster than re-downloading the planet for one fix.

---

## 9. Quick reference — tools

| Tool | Use for |
|---|---|
| `osmium-tool` | Filter PBF, convert to GeoJSON, assemble multipolygons |
| `ogr2ogr` (GDAL) | Load GeoJSON into PostGIS |
| `osmtogeojson` | Convert Overpass JSON → GeoJSON in Node/browser |
| Overpass turbo (OHM instance) | Interactive query authoring, export |
| `edtf` (Python) | Parse partial and BCE dates |
| `curl` + `.ql` file | Scripted Overpass pulls |

## 10. Sources worth bookmarking

- `https://wiki.openstreetmap.org/wiki/OpenHistoricalMap/Overpass` — query cookbook with date-filter idioms
- `https://wiki.openstreetmap.org/wiki/OpenHistoricalMap/Tags` — tagging conventions
- `https://wiki.openstreetmap.org/wiki/OpenHistoricalMap/Reuse` — planet dumps, tile URLs, licensing
- `https://planet.openhistoricalmap.org/planet/` — daily and weekly planet files
- `https://overpass-turbo.openhistoricalmap.org/` — interactive query UI