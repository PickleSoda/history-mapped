# Entity Attributes — Complete Reference

This document lists every attribute (field) on an entity record, what it contains, and the allowed values where relevant.

---

## Identity

### `name`
**Required.**
The primary name of the entity, in English or the most widely accepted scholarly transliteration.

- Use the most common scholarly English form, not the local-language form, unless the scholarly community consistently uses the local form.
- Do not include dates in the name itself. *"Han Dynasty"* not *"Han Dynasty (206 BCE–220 CE)"*.
- For persons, use the most recognisable form. *"Julius Caesar"* not *"Gaius Julius Caesar"* (the fuller form can be an alternative name).

---

### `alternative_names`
**Optional.** Array of strings.
Other names this entity is known by: local-language names, transliterations, earlier or later names, names in other scholarly traditions.

*Examples:*
- `["Qart-hadasht", "Cartagena", "Karchedon"]` (for Carthage)
- `["Tamerlane", "Timur-i-lang", "Аmir Temur"]` (for Timur)

---

### `wikidata_id`
**Optional.**
The Wikidata entity identifier, in the form `Q` followed by digits. *e.g. `Q6216` for the Han Dynasty.*

This links the record to the broader Linked Open Data ecosystem and avoids duplicating encyclopaedic content that Wikidata already maintains.

---

### `summary`
**Optional.**
One to three sentences describing what the entity *is*. Written in the present tense as a definition, not a narrative.

> *"The Han Dynasty was a Chinese imperial dynasty that ruled from 206 BCE to 220 CE, establishing the foundational institutions of Chinese bureaucratic governance."*

---

### `significance`
**Optional.**
Longer passage explaining why the entity matters and what its historical consequences were. This is the place for interpretive context, causal claims, and discussion of scholarly debates.

---

### `tags`
**Optional.** Array of strings (free-form labels).
Used for thematic filtering and clustering. Lower-case, underscore-separated.

*Common conventions:* `iron_age`, `bronze_age`, `mediterranean`, `steppe`, `nomadic`, `maritime`, `collapse`, `urbanisation`, `religious_conflict`, `trade`, `plague`

---

## Classification

### `entity_group`
**Required.**
The broad category the entity belongs to.

| Value | Covers |
|---|---|
| `POLITY` | Political entities, dynasties, persons, armies, social classes, diplomatic agreements |
| `PLACE` | Cities, monuments, infrastructure, educational institutions |
| `EVENT` | Wars, battles, treaties, rebellions, natural disasters, migrations, epidemics, legal reforms, technology adoptions |
| `ECONOMY` | Trade routes, natural resources, currencies |
| `CULTURE` | Cultural works, intellectual movements, languages, religious movements, legal codes, technologies, archaeological cultures |

---

### `entity_type`
**Required.**
The specific type within the group. Must be consistent with `entity_group`.

**POLITY types:**

| Value | Meaning |
|---|---|
| `political_entity` | A state, republic, empire, kingdom, city-state, or other political unit |
| `dynasty` | A ruling lineage or house |
| `person` | An individual historical figure |
| `military_unit` | An army, fleet, corps, or other organised military force |
| `diplomatic_relationship` | A formal treaty, alliance, or diplomatic arrangement as a standing entity |
| `social_class` | A defined stratum of society (nobility, peasantry, merchant class, etc.) |

**PLACE types:**

| Value | Meaning |
|---|---|
| `city` | A city, town, settlement, or urban agglomeration |
| `infrastructure_monument` | A road, wall, bridge, temple, palace, pyramid, or other constructed landmark |
| `extraction_infra` | A mine, quarry, well, irrigation system, or other resource-extraction installation |
| `educational_institution` | A school, academy, library, madrasa, or centre of learning |

**EVENT types:**

| Value | Meaning |
|---|---|
| `event_war` | A war or prolonged armed conflict |
| `event_battle` | A single battle or military engagement |
| `event_treaty` | A peace treaty or formal agreement ending or regulating conflict |
| `event_rebellion` | A revolt, uprising, or civil war |
| `event_natural_disaster` | An earthquake, flood, drought, famine, or other natural catastrophe |
| `event_tech_adoption` | The adoption or diffusion of a technology by a society |
| `event_legal_reform` | The enactment of a legal code, constitution, or significant legislation |
| `migration` | A large-scale movement of people |
| `epidemic_disease` | An epidemic, pandemic, or significant disease event |

**ECONOMY types:**

| Value | Meaning |
|---|---|
| `trade_route` | An overland, maritime, or river trade route or network |
| `natural_resource` | A deposit of metal, mineral, timber, crop, or other economically significant resource |
| `currency_monetary_system` | A coin, currency, or monetary system |

**CULTURE types:**

| Value | Meaning |
|---|---|
| `cultural_work` | A text, artwork, building as cultural object, musical tradition, or other cultural product |
| `intellectual_movement` | A school of thought, philosophical tradition, or scholarly movement |
| `archaeological_culture` | A material-culture complex defined archaeologically |
| `language` | A language or dialect |
| `religious_text` | A scripture, religious canon, or sacred text |
| `legal_code` | A law code or body of jurisprudence as a cultural artefact |
| `religious_movement` | A religion, denomination, sect, or organised religious movement |
| `technology` | An invention, technique, or technological system |

---

## Time

### `temporal_start`
**Optional.**
The year the entity began, as a number. BCE years are negative. Year 1 CE = `1`. Year 1 BCE = `-1`.

*Note: there is no year 0 in the historical calendar; the system follows the astronomical convention where year 0 = 1 BCE.*

---

### `temporal_end`
**Optional.**
The year the entity ended. Leave blank for ongoing entities.

---

### `date_raw`
**Optional.**
The date as it appears in the source you are drawing on, preserved verbatim.

*Examples:* `"264 to 241 BC"`, `"r. 27 BC – AD 14"`, `"fl. 9th century"`, `"c. 1206"`, `"after 1258"`

This is important for traceability — it lets a future researcher check your interpretation against the original source.

---

### `temporal_display_range`
**Optional.**
A human-readable version of the date range, formatted for display.

*Examples:* `"264–241 BCE"`, `"r. 27 BCE – 14 CE"`, `"c. 9th century"`, `"1206–1368"`

---

### `era_label`
**Optional.**
A shorthand era name meaningful to historians of the relevant tradition.

*Examples:* `"Late Republic"`, `"Tang Dynasty"`, `"Abbasid Golden Age"`, `"Early Iron Age"`, `"Warring States period"`

---

### `duration_type`
**Optional.**
Whether the entity is a point event, a period, ongoing, or of uncertain duration.

| Value | Meaning |
|---|---|
| `point` | Occurred at a single moment or within a single year |
| `period` | Lasted for a defined span of years |
| `ongoing` | Has not ended (or had not ended as of the latest known date) |
| `uncertain` | Duration is not known or cannot be established |

---

### `date_confidence`
**Optional.**
How precise and reliable the temporal start/end dates are.

| Value | Meaning |
|---|---|
| `high` | Dates are attested in primary sources with year-level precision |
| `medium` | Dates are established within a decade |
| `low` | Dates are known only within a century |
| `unresolved` | Dates are not known or are subject to fundamental scholarly disagreement |

---

### `date_method`
**Optional.**
How the date was determined.

| Value | Meaning |
|---|---|
| `nlp_direct` | Extracted directly from a text by natural language processing |
| `nlp_approximate` | Approximated from text by NLP |
| `llm_reign_resolution` | Inferred from a ruler's known reign |
| `era_table_lookup` | Looked up in the Era Date Lookup reference table |
| `llm_contextual_inference` | Inferred from surrounding context by a language model |
| `human_assigned` | Set by a human researcher |
| `source_database` | Taken directly from an external trusted dataset |

---

## Location

## Migration Flags (V2 Cutover)

During the v2 migration, write behavior is controlled by two app flags:

- `ENTITY_MODEL_V2_WRITE_ENABLED`:
	- `false` (default): legacy `entities` temporal/location columns continue to be written.
	- `true`: create/update paths stop writing legacy temporal/location columns (`temporal_*`, `location_*`).
- `GEOMETRY_SNAPSHOT_COMPAT_READ_ENABLED`:
	- `true` (default): compatibility read endpoints remain available.
	- `false`: compatibility reads can be turned off after clients migrate.

### `location_name`
**Optional.**
Plain-text description of the location, for human readers. See [for-geodata-contributors.md](./for-geodata-contributors.md) for guidance.

---

### `geom`
**Optional.** PostGIS point geometry (WGS 84).
The primary geographic coordinate of the entity. Longitude before latitude in decimal degrees. See [for-geodata-contributors.md](./for-geodata-contributors.md) for full guidance.

---

### `territory_geom`
**Optional.** PostGIS geometry (polygon, line, or multipart).
The spatial extent of the entity. See [for-geodata-contributors.md](./for-geodata-contributors.md) for full guidance.

---

### `location_confidence`
**Optional.** Same four values as `date_confidence`: `high`, `medium`, `low`, `unresolved`.

---

### `location_method`
**Optional.**
How the location was determined. See [for-geodata-contributors.md](./for-geodata-contributors.md) for the full list of values.

---

## Hierarchy and Succession

### `parent_entity_id`
**Optional.**
The UUID of a parent entity, representing a strict part-of or sub-unit relationship.

- The Battle of Cannae is a child of the Second Punic War
- The Duchy of Burgundy is a child of the Kingdom of France
- Use this sparingly — complex overlapping hierarchies are better expressed through `part_of` and `contains` relationships

---

### `successor_entity_id`
**Optional.**
The UUID of the entity that directly replaced this one.

- The Roman Principate is the successor of the Roman Republic
- The Abbasid Caliphate is the successor of the Umayyad Caliphate
- Do not use this for gradual transitions; it is for a clear moment of replacement

---

## Quantitative and Display Fields

### `impact_score`
**Optional.** Integer.
A rough measure of historical significance used for search ranking and map display priority. Higher values surface the entity more prominently. This is not a precise academic judgement — it is a practical ranking signal.

Rough guide: `100` for a world-historical turning point (e.g. the Black Death, the invention of printing), `50` for a significant regional event, `10` for a local or minor entity.

---

### `display_priority`
**Optional.** Integer.
Controls rendering order when entities overlap on a map. Higher values render on top.

---

### `icon_class`
**Optional.**
A visual icon associated with the entity type, used in map markers and UI display.

Common values: `crown` (ruler/state), `person` (individual), `sword` (military), `city` (settlement), `scroll` (text/code), `trade_ship` (trade route), `gem` (resource), `coin` (currency), `plague` (epidemic), `earthquake` (disaster), `handshake` (treaty), `temple` (religion).

---

### `entity_color`
**Optional.** Hex colour string, e.g. `#c0392b`.
Used for map visualisation and timeline display to colour-code the entity's civilisational or cultural sphere.

---

## Quality and Provenance

### `confidence`
**Optional.** `high` / `medium` / `low` / `unresolved`.
Overall confidence in the entity record as a whole.

---

### `confidence_notes`
**Optional.**
Free-text notes explaining uncertainty, recording which sources were used, or flagging known problems with the record.

---

### `confidence_breakdown`
**Optional.** JSON object.
A structured breakdown of confidence by dimension (date, location, type attribution, significance score, etc.).

---

### `verification_status`
**Required.** Default: `pipeline_draft`.
The review workflow stage of the record. See [for-historians.md](./for-historians.md) for a full explanation of each status.

---

### `validation_flags`
**Optional.** Array of strings.
Machine-generated flags indicating potential problems. *e.g. `["date_out_of_range", "missing_location", "duplicate_candidate"]`*. These prompt human review.

---

### `source_citations`
**Optional.** JSON array.
Structured citations supporting the entity record. Each citation records source type, title, author, page, and reliability tier.

---

### `source_diversity_score`
**Optional.** Integer.
An automated score reflecting how many independent source types support this record. Higher values indicate better corroboration.

---

### `media_refs`
**Optional.** JSON array.
References to images, maps, or other media associated with the entity.

---

## Derived and Computed Fields

These fields are typically populated automatically; human contributors should not need to set them manually.

### `attributes`
**Optional.** JSON object.
Type-specific structured data that does not fit the standard columns. The schema varies by `entity_type`. For example, a `person` entity might store birth/death dates, titles, and offices here; a `trade_route` might store cargo types and documented passage points.

---

### `relationship_summary`
**Optional.** JSON object.
A cached summary of the entity's most important relationships, pre-computed for performance.

---

### `nearby_entity_count`
**Optional.** Integer.
Number of other entities within a defined radius, pre-computed for map clustering.

---

### `cluster_id`
**Optional.** Integer.
The cluster this entity belongs to in a spatial or thematic clustering analysis.

---

### `embedding` / `embedding_version`
**Optional.**
A 1536-dimension vector embedding of the entity's text fields, used for semantic similarity search. Not set by human contributors — generated automatically by the pipeline.

---

### `created_by`
**Optional.**
Identifier of the pipeline process or contributor that created the record.

---

### `created_at` / `updated_at`
Timestamps set automatically by the system.
