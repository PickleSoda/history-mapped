# The Entity Model — A Guide for Geodata Contributors

This document is for people entering or correcting **geographic and spatial data** in the database. It explains what the location fields mean, what format coordinates should be in, and how to handle the different situations you will encounter — from a well-attested Roman city to a disputed tribal territory.

---

## The Two Geometry Fields

## Migration Note (V2 Geometry Periods)

Legacy snapshot-style write paths are compatibility-only during migration. Once `ENTITY_MODEL_V2_WRITE_ENABLED=true`, new writes should flow through geometry periods and normalized location records rather than deprecated legacy columns.

Every entity can have up to two geometry fields. They serve different purposes.

### `geom` — The Point Location

This is a **single coordinate** representing the most meaningful geographic position for this entity.

- For a **city**, it is the city centre (or the ancient city centre if the modern city has moved).
- For a **battle**, it is the approximate location where the fighting occurred.
- For a **person**, this field is usually left blank — use relationships (`born_in`, `resided_in`, `died_in`) instead.
- For a **trade route**, this field is also usually left blank — use `territory_geom` for the route line, or use relationships to connect the route to the cities it passes through.
- For a **state or empire**, `geom` typically marks the capital city or the political heartland, not the full extent. The full extent goes in `territory_geom`.

**Format:** Longitude, latitude in decimal degrees (WGS 84 / EPSG:4326). Longitude comes first.

```
Correct:   [39.8261, 21.4225]   (longitude, latitude — Mecca)
Incorrect: [21.4225, 39.8261]   (latitude first — this is a common mistake)
```

Positive longitude = East. Negative longitude = West.
Positive latitude = North. Negative latitude = South.

**Precision:** Use as many decimal places as the evidence supports, but do not invent false precision.

| Situation | Appropriate precision | Example |
|---|---|---|
| Modern city with known ancient core | 4–5 decimal places | `44.4268, 26.1025` (Bucharest) |
| Excavated ancient site | 3–4 decimal places | Site known from archaeology |
| Location known to within ~5 km | 2 decimal places | |
| Location known only to nearest region | 1 decimal place or omit | |
| Location genuinely unknown | Leave `geom` blank | |

---

### `territory_geom` — The Territorial Extent

This is a **polygon, multipolygon, or line** representing the spatial extent of the entity.

Use this for:
- The borders of a **state or empire** at a given time
- The route of a **trade route** (as a line or polyline)
- The catchment area of a **natural resource**
- The approximate zone of spread of a **migration** or **epidemic**
- The area of an **archaeological culture**

**Format:** GeoJSON geometry objects. The system stores these as PostGIS geometry. You do not need to write raw SQL — the input form accepts standard GeoJSON.

```json
{
  "type": "Polygon",
  "coordinates": [
    [
      [12.45, 41.90],
      [13.00, 41.90],
      [13.00, 41.50],
      [12.45, 41.50],
      [12.45, 41.90]
    ]
  ]
}
```

For multi-part territories (e.g. an empire with disconnected holdings), use `MultiPolygon`.

For routes, use `LineString` or `MultiLineString`.

---

## Location Confidence and Method

Two fields document how reliable the location is and how it was determined.

### `location_confidence`

| Value | Meaning |
|---|---|
| `high` | Location is attested in primary sources or confirmed by archaeology. Coordinates are within the actual site. |
| `medium` | Location is well-established by scholarship but precise coordinates are estimated. |
| `low` | Location is disputed, known only approximately, or inferred from context. |
| `unresolved` | Location is genuinely unknown or there is no scholarly consensus. |

### `location_method`

| Value | Meaning |
|---|---|
| `ohm_nominatim` | Geocoded from OpenHistoricalMap or Nominatim |
| `ohm_overpass` | Matched directly to OHM node/way/relation via Overpass |
| `ohm_rest_api` | Matched by explicit OHM element lookup in `/api/0.6` |
| `wikidata` | Taken from a Wikidata coordinate claim |
| `geonames` | Taken from the GeoNames database |
| `pleiades` | Taken from the Pleiades gazetteer of ancient places |
| `llm_disambiguation` | An automated tool resolved an ambiguous place name |
| `human_assigned` | A researcher manually set the coordinates |
| `source_database` | Taken directly from a trusted external source dataset |

---

## The `location_name` Field

This is a **plain-text description** of where the entity is located, written for human readers. It is not a structured address — it is a label.

Good examples:
- *"Near modern Mosul, Iraq"*
- *"Northern India, Ganges plain"*
- *"Atlantic coast of West Africa, roughly modern Senegal to Guinea"*
- *"Central Anatolia"*

It should be consistent with the actual coordinates. If the coordinates place a battle in northern Syria, do not write *"Mesopotamia"* in the location name.

---

## Common Situations and How to Handle Them

### The location has moved or been renamed

Use the **ancient or contemporary name** in `location_name`, and add the modern equivalent in parentheses for orientation.

> *"Carthage (near modern Tunis, Tunisia)"*
> *"Ctesiphon (near modern Salman Pak, Iraq)"*

The coordinates should point to the **ancient site**, not the modern city.

### The location is debated

Set `location_confidence` to `low` or `unresolved`. Record the competing claims in `confidence_notes`:

> *"Ancient sources give two possible locations: one near the Granicus River (modern Biga Çayı) and one further east. Coordinates follow the majority scholarly view."*

Do not average competing coordinates or pick arbitrarily without noting the debate.

### The entity covers a vast and changing area

For empires and states whose borders shifted substantially over time, the `territory_geom` should represent the entity's **maximum extent** or **most typical extent**, with the time period noted in `confidence_notes`:

> *"Territory polygon represents approximate maximum extent c. 120 CE under Trajan. Earlier and later extents were significantly different."*

For time-varying geometries, this field should map into multiple geometry periods. For now, document the time it refers to.

### The entity has no meaningful single point

Some entities are inherently spatial in extent — a trade route, a migration, a nomadic confederation — and a single point would be misleading. In these cases:

- Leave `geom` blank, or place it at the most important node (e.g. the origin point of a trade route, the political heartland of a confederacy).
- Use `territory_geom` for the full extent.
- Use relationships to connect the entity to the cities, regions, or routes it passes through.

### The entity is a person

Persons generally should **not** have coordinates in `geom`. Instead:

- Use `born_in` relationship → birthplace entity
- Use `died_in` relationship → death location entity
- Use `resided_in` relationship → residence entity (with temporal start/end on the relationship)

The exception: if a person's movements are themselves historically significant (e.g. Ibn Battuta's travels, Marco Polo's route), a `territory_geom` line can represent the journey.

### The entity is an event

**Battles and localised events:** Place the `geom` point at the battle site. If a specific location is known to within a few kilometres, set `location_confidence` to `high` or `medium`.

**Wars (which span multiple locations):** Leave `geom` blank. Use relationships to link the war to the battles it comprised (`contains` relationship) and to the states involved (`at_war_with`).

**Migrations:** Use `territory_geom` as a line or broad polygon representing the route or zone of movement. Set `location_confidence` to reflect how well the route is established.

**Epidemics:** Use `territory_geom` as a polygon representing the known or estimated extent of spread. Note the time the polygon applies to in `confidence_notes`.

---

## Coordinate Reference System

All coordinates must be in **WGS 84 (EPSG:4326)** — the same system used by GPS devices, Google Maps, and OpenStreetMap. Decimal degrees only; do not use degrees-minutes-seconds notation.

| Wrong | Right |
|---|---|
| `41°54'N, 12°27'E` | `41.900, 12.450` |
| `EPSG:3857` projected coordinates | Convert to WGS 84 first |

---

## A Worked Example: The Silk Road

The Silk Road is an entity of type `trade_route` in the ECONOMY group. Here is how its spatial data should be populated.

**`geom` (point):** The conventional western terminus, Antioch / Seleucia on the Orontes (near modern Antakya, Turkey): `[36.2021, 36.2021]`. Alternatively, leave blank and rely on `territory_geom`.

**`territory_geom` (line):** A `MultiLineString` tracing the major routes from Chang'an westward through Central Asia, branching through Persia to the Levant, and through Sogdia to the Black Sea. This should reflect the **combined network**, not a single path.

**`location_name`:** *"Overland network connecting Chang'an (China) to the eastern Mediterranean, via Central Asia and Persia"*

**`location_confidence`:** `medium` — the general route is well-established; precise paths for particular periods are debated.

**`location_method`:** `human_assigned`

**`confidence_notes`:** *"Route geometry represents the approximate combined network of the classical period (c. 1st–8th centuries CE). Northern steppe variants and sea routes not included."*

**Relationships:**
```
Silk Road  ──[connects]──────►  Chang'an
Silk Road  ──[connects]──────►  Samarkand
Silk Road  ──[connects]──────►  Ctesiphon
Silk Road  ──[connects]──────►  Antioch
Silk Road  ──[passes_through]►  Kushan Empire
Silk Road  ──[controlled_by]─►  Han Dynasty      (−130 to 220)
Silk Road  ──[controlled_by]─►  Tang Dynasty     (618 to 907)
```

---

## OHM-First Resolution Policy

For map interaction and provenance, resolve locations in this order:

1. **Wikidata seed**: start from QID and any coordinates/place hints.
2. **OHM match**: try OHM Nominatim, then OHM Overpass/REST to get a concrete `node`, `way`, or `relation`.
3. **Fallback geometry source**: if no OHM match, use trusted external border datasets or manual digitization.
4. **Empty geometry**: if both fail, leave `geom` and `territory_geom` empty and mark `location_confidence` as `unresolved`.

When possible, attach and keep the external reference ID (especially OHM relation IDs) so clicking an entity can open the underlying map feature directly.

---

## Checklist Before Submitting a Location

- [ ] Longitude comes **before** latitude in all coordinate pairs
- [ ] Coordinates are in WGS 84 decimal degrees
- [ ] `location_name` matches the actual coordinates (spot-check on a map)
- [ ] `location_confidence` honestly reflects the evidence
- [ ] `location_method` is filled in
- [ ] OHM lookup was attempted before fallback geometry sources
- [ ] If the location is disputed or estimated, this is noted in `confidence_notes`
- [ ] Persons use relationships (`born_in`, `died_in`, `resided_in`) rather than `geom`
- [ ] Wars and wide-area events use `territory_geom` rather than a misleading single point
- [ ] `territory_geom` notes the time period it represents if the extent was time-varying
