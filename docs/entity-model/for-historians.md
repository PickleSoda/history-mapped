# The Entity Model — A Guide for Historians

This document explains how historical knowledge is structured in this database. No technical background is needed. If you can write a footnote or a dictionary entry, you already think in the right way.

---

## The Core Idea: Everything is an Entity

History is full of things that existed in time and space and that mattered. We call all of them **entities**. An entity can be:

- A **state** — the Achaemenid Empire, the Venetian Republic, the Qing dynasty
- A **person** — Cleopatra VII, Ibn Battuta, Tokugawa Ieyasu
- A **city** — Carthage, Samarkand, Tenochtitlan
- A **battle or war** — the Battle of Gaugamela, the Thirty Years' War
- A **migration** — the Bantu expansion, the Great Migration of the 20th century
- A **trade route** — the Silk Road, the trans-Saharan gold–salt route
- A **religious movement** — the Protestant Reformation, Mahayana Buddhism
- A **plague** — the Black Death, the Antonine Plague
- A **legal code** — the Code of Hammurabi, Justinian's *Corpus Juris Civilis*
- A **technology** — the stirrup, the printing press, iron-smelting

If it has a name, existed in a place and time, and influenced something else, it belongs here.

---

## The Five Groups

Every entity belongs to one of five broad groups. Think of them as the major departments of a historical encyclopaedia.

### POLITY — Power and People
Political entities, rulers, dynasties, armies, social classes, and formal agreements between powers.

*Examples:* Macedonian Empire, Julius Caesar, the Janissaries, the aristocracy of Han China, the Treaty of Westphalia

### PLACE — Where History Happened
Cities, ports, fortresses, monuments, mines, universities — the physical stages of history.

*Examples:* Alexandria, the Grand Canal of China, the Library of Nalanda, the salt mines of Wieliczka

### EVENT — What Happened
Wars, battles, treaties, rebellions, natural disasters, technological adoptions, legal reforms, migrations, epidemics.

*Examples:* the Mongol invasion of Khwarezm, the Plague of Justinian, the Meiji Restoration, the expulsion of Jews from Spain in 1492

### ECONOMY — How Wealth Moved
Trade routes, natural resources, currencies, and monetary systems.

*Examples:* the Silk Road, the silver mines of Potosí, Roman *denarius*, the cowrie-shell currency zone of sub-Saharan Africa

### CULTURE — Ideas, Beliefs, and Works
Intellectual movements, languages, religions, texts, legal codes, archaeological cultures, technologies.

*Examples:* the Abbasid Translation Movement, Classical Arabic, the Quran, the Justinian Code, the invention of the compass

---

## Describing an Entity

Each entity has a set of fields. Here are the ones historians care about most.

### Identity

**Name** — The primary name, usually in English or the most scholarly convention. *Carthage*, not *Qart-hadasht*, unless a case can be made.

**Alternative names** — Other names the entity is known by, including transliterations, local names, and names in other languages. *Carthage / Qart-hadasht / Cartagena (Latin)*

**Wikidata ID** — If this entity has a Wikidata page, its identifier (e.g. `Q6216`). This helps link the database to the wider web of knowledge without duplicating work.

**Summary** — A short, neutral description of one to three sentences. Think of it as the opening sentence of a good encyclopaedia entry. It should state what the entity *is*, not what it *did* (that goes in significance).

**Significance** — A longer passage explaining why this entity matters historically. This is where you can discuss causes, consequences, and interpretive debates.

**Tags** — Free-form labels for thematic searching. *e.g. `iron_age`, `mediterranean`, `collapse`, `nomadic`*

---

### Time

Dates are recorded as **years relative to the Common Era**, where negative numbers are BCE. This system avoids the ambiguities of different calendar systems.

| Field | Meaning | Example |
|---|---|---|
| `temporal_start` | When the entity began | `-264` (264 BCE — start of the First Punic War) |
| `temporal_end` | When the entity ended | `-241` (241 BCE — end of the First Punic War) |
| `date_raw` | The date as it appears in your source | *"264 to 241 BC"* |
| `temporal_display_range` | A human-readable version | *"264–241 BCE"* |
| `era_label` | A shorthand era name | *"Late Republic"*, *"Tang Dynasty"* |
| `duration_type` | Whether the entity is a point, a period, ongoing, or uncertain | `period` |

**Confidence in dates** is separate from confidence in other facts. A date can be `high` confidence (attested in multiple primary sources with year-level precision), `medium` (known within a decade), `low` (within a century), or `unresolved` (we only know the approximate era).

**How was the date determined?**  The `date_method` field records this — for instance, `source_database` (taken directly from a trusted dataset), `llm_reign_resolution` (inferred from a ruler's known reign), or `human_assigned` (a researcher made the call).

---

### Hierarchy and Succession

Entities can have a **parent** and can have **children**. This is for strict part-of or sub-unit relationships:

- The Battle of Cannae is a **child** of the Second Punic War
- The Duchy of Burgundy is a **child** of the Kingdom of France (in a given period)
- The Western Roman Empire and the Eastern Roman Empire are both **children** of the Roman Empire

The **successor** field records the entity that directly replaced this one:
- The successor of the Roman Republic is the Roman Principate
- The successor of the Umayyad Caliphate is the Abbasid Caliphate

---

### Relationships Between Entities

The richest part of the model is its **relationship system**. A relationship connects two entities with a named type and, optionally, a time window and a confidence level.

**Directed relationships** — Every relationship has a *source* and a *target*. The direction matters:

> *Julius Caesar* **[rules]** *Roman Republic*  (Caesar is the source; the Republic is the target)

This is distinct from:

> *Roman Republic* **[governed_by]** *Julius Caesar*  (the inverse — but both can be stored)

See [relationships.md](./relationships.md) for all 76 types.

---

### Geometry Snapshots — Where Entities Were, and Why

Every entity has a location on the map. But many entities moved, expanded, or appeared at places they are not normally associated with. The **geometry snapshot** system records these time-bound locations.

A snapshot answers: **"Where was this entity during this period, and why?"**

#### What a snapshot records

| Field | Meaning | Example |
|---|---|---|
| **Location** | A point, line, or polygon on the map | Münster, or the borders of the Western Roman Empire |
| **Year range** | When this location was valid | 1648–1648, or 395–476 |
| **Label** | A short title for the map | "At Münster" |
| **Description** | Why the entity was there | "Present as French representative for the signing of the Treaty of Westphalia" |
| **Confidence** | How certain we are | `high`, `medium`, `low` |

#### Two kinds of snapshot

**Presence snapshots** — A person or group was *at a place* because of a specific relationship. These are tied to the relationship that put them there.

> Cardinal Mazarin was in Münster in 1648 *because* he signed the Treaty of Westphalia. If we later determine that Mazarin did not actually attend the signing, we remove the `signed_by` relationship and the snapshot disappears automatically.

**Territory snapshots** — A state's borders changed because of an event. These are tied to the event that caused the change.

> The Roman Empire's borders contracted after 395 CE *because* of the division under Theodosius I. Even if we delete the event entity for that division, the territory snapshot survives — we still know what the borders looked like.

#### How you create snapshots in the application

You do not usually create snapshots in isolation. They are produced as a natural side effect of the relationships you build.

**From the event page (most common):**

1. You open the **Peace of Westphalia** entity
2. You add a `signed_by` relationship pointing to **Cardinal Mazarin**
3. The system asks: *"Create a presence snapshot for Cardinal Mazarin at this location?"*
4. You fill in the description: *"Present as French representative for the signing"*
5. The system creates the snapshot — Mazarin now appears on the map at Münster in 1648

You can repeat this for every signatory. Each gets their own snapshot with their own description.

**From the referenced entity page:**

If you open **Cardinal Mazarin**'s entity page, you will see all his snapshots listed — every place he appeared on the map and why. Each snapshot links back to the relationship (and therefore the event) that put him there. You can edit the description or adjust the dates from either side.

**Manually (for territory changes):**

For empire borders, you draw the polygon directly on the map for a given year range and write a description explaining the change. These are not tied to a single relationship — they are tied to an event (a conquest, a treaty, a division).

#### When snapshots are useful

| Situation | What you do |
|---|---|
| A treaty was signed at a specific location | Add `signed_by` relationships → system offers snapshots for each signatory |
| A battle involved specific commanders | Add `fought_at` or `commanded` relationships → snapshots for commanders at the battle site |
| A person founded a city | Add `founded` relationship → snapshot for the founder at the city |
| A person was born or died somewhere | Add `born_in` / `died_in` relationship → snapshot at the city |
| An empire's borders changed over centuries | Draw territory polygons for each period on the map |
| A trade route shifted over time | Draw the route's path for different eras |

#### What this looks like on the map

When a user moves the time slider to **1648**, Cardinal Mazarin appears at Münster — even though his "home" location might be Paris. The map tooltip shows: *"At Münster — Present as French representative for the signing of the Treaty of Westphalia"*. Clicking through takes the user to the Treaty of Westphalia entity.

For an empire like Rome, moving the time slider shows borders expanding and contracting smoothly, with each snapshot carrying a description of what caused the change.

---

## Three Worked Historical Examples

### Example 1 — The Rise and Fall of the Han Dynasty

This example shows how a single historical arc produces a network of entities and relationships.

**Entities:**

| Name | Type | Group | Start | End |
|---|---|---|---|---|
| Han Dynasty | `political_entity` | POLITY | −206 | 220 |
| Liu Bang (Emperor Gaozu) | `person` | POLITY | −256 | −195 |
| Xiongnu Confederacy | `political_entity` | POLITY | −209 | 93 |
| Battle of Baideng | `event_battle` | EVENT | −200 | −200 |
| Silk Road | `trade_route` | ECONOMY | −130 | 1450 |
| Chang'an | `city` | PLACE | −202 | 904 |
| Confucianism (Han State Adoption) | `intellectual_movement` | CULTURE | −136 | 220 |
| Yellow Turban Rebellion | `event_rebellion` | EVENT | 184 | 205 |

**Relationships:**

```
Liu Bang        ──[founded]──────────►  Han Dynasty
Liu Bang        ──[rules]────────────►  Han Dynasty         (−206 to −195)
Han Dynasty     ──[at_war_with]──────►  Xiongnu Confederacy  (−200 to −133)
Han Dynasty     ──[fought_at]────────►  Battle of Baideng
Xiongnu         ──[victorious_at]────►  Battle of Baideng
Han Dynasty     ──[controls]─────────►  Silk Road            (−130 to 220)
Chang'an        ──[capital_of]───────►  Han Dynasty
Han Dynasty     ──[adheres_to]───────►  Confucianism (Han)   (−136 to 220)
Yellow Turban   ──[weakened]─────────►  Han Dynasty
Han Dynasty     ──[succeeded_by]─────►  Three Kingdoms Period
```

---

### Example 2 — The Mongol Conquests and the Il-Khanate

This example shows how conquest, succession, and cultural transmission work.

**Entities:**

| Name | Type | Group | Start | End |
|---|---|---|---|---|
| Mongol Empire | `political_entity` | POLITY | 1206 | 1368 |
| Genghis Khan | `person` | POLITY | 1162 | 1227 |
| Abbasid Caliphate | `political_entity` | POLITY | 750 | 1258 |
| Sack of Baghdad | `event_battle` | EVENT | 1258 | 1258 |
| Il-Khanate | `political_entity` | POLITY | 1256 | 1335 |
| Hulagu Khan | `person` | POLITY | 1217 | 1265 |
| House of Wisdom | `educational_institution` | PLACE | 830 | 1258 |
| Black Death | `epidemic_disease` | EVENT | 1346 | 1353 |

**Relationships:**

```
Genghis Khan   ──[founded]──────────►  Mongol Empire
Hulagu Khan    ──[member_of_dynasty]─►  Mongol Empire (Toluid line)
Hulagu Khan    ──[commanded]─────────►  Mongol invasion of Abbasid Caliphate
Mongol Empire  ──[caused]────────────►  Sack of Baghdad
Sack of Baghdad ─[resulted_from]─────►  Mongol invasion of Abbasid Caliphate
Sack of Baghdad ─[destroyed_by]──────►  House of Wisdom
Abbasid Caliphate ─[succeeded_by]────►  Il-Khanate       (for Mesopotamia)
Hulagu Khan    ──[rules]─────────────►  Il-Khanate        (1256 to 1265)
Mongol Empire  ──[spread_to]─────────►  Black Death        (via trade routes)
```

---

### Example 3 — The Protestant Reformation

This example shows how a cultural movement interacts with political, military, and diplomatic entities.

**Entities:**

| Name | Type | Group | Start | End |
|---|---|---|---|---|
| Protestant Reformation | `religious_movement` | CULTURE | 1517 | 1648 |
| Martin Luther | `person` | POLITY | 1483 | 1546 |
| Ninety-Five Theses | `cultural_work` | CULTURE | 1517 | 1517 |
| Holy Roman Empire | `political_entity` | POLITY | 962 | 1806 |
| Thirty Years' War | `event_war` | EVENT | 1618 | 1648 |
| Peace of Westphalia | `event_treaty` | EVENT | 1648 | 1648 |
| Printing Press | `technology` | CULTURE | 1440 | — |
| Lutheran Church | `religious_movement` | CULTURE | 1521 | — |

**Relationships:**

```
Martin Luther   ──[authored]──────────►  Ninety-Five Theses
Ninety-Five Theses ─[caused]───────────►  Protestant Reformation
Printing Press  ──[enabled]───────────►  Protestant Reformation
Protestant Reformation ─[caused]───────►  Thirty Years' War
Holy Roman Empire ─[at_war_with]────────►  Protestant Princes     (in Thirty Years' War)
Thirty Years' War ─[resulted_from]──────►  Protestant Reformation
Peace of Westphalia ─[ended]─────────────►  Thirty Years' War
Peace of Westphalia ─[signed_by]─────────►  Holy Roman Empire
Peace of Westphalia ─[signed_by]─────────►  Kingdom of France
Peace of Westphalia ─[signed_by]─────────►  Kingdom of Sweden
Peace of Westphalia ─[mediated_by]───────►  Pope Innocent X (attempted)
Martin Luther   ──[founded]───────────►  Lutheran Church
Lutheran Church ──[schism_from]───────►  Catholic Church
```

**Geometry Snapshots (auto-generated from relationships above):**

When the `signed_by` and `mediated_by` relationships are created on the Peace of Westphalia (located at Münster), the system offers to create presence snapshots:

| Entity | Location | Year | Label | Description | Via relationship |
|---|---|---|---|---|---|
| Holy Roman Empire | Münster | 1648 | At Münster | Imperial delegation present for the signing of the Peace of Westphalia | `signed_by` |
| Kingdom of France | Münster | 1648 | At Münster | French delegation led by the Duc de Longueville | `signed_by` |
| Kingdom of Sweden | Osnabrück | 1648 | At Osnabrück | Swedish delegation present for the Treaty of Osnabrück | `signed_by` |

Notice that the Swedish delegation's location can be corrected to **Osnabrück** — the historian fills in the actual location when creating the snapshot, rather than blindly copying the treaty's coordinates.

**Territory snapshot (manual):**

The Peace of Westphalia also redrew the map of Europe. A historian can draw territory snapshots on the affected polities:

| Entity | Year range | Description | Linked event |
|---|---|---|---|
| Holy Roman Empire | 1648–1806 | Borders after the Peace of Westphalia; Swiss Confederacy and United Provinces formally independent | Peace of Westphalia |

On Martin Luther's entity page, a historian sees his existing snapshots — born in Eisleben (1483), at Wittenberg posting the Theses (1517), at the Diet of Worms (1521) — each with a description and a link to the event or relationship that placed him there.

---

## Quality and Confidence

The database is honest about uncertainty. Every entity carries:

**Overall confidence** — `high`, `medium`, `low`, or `unresolved`. This reflects how well-attested the entity is across independent sources.

**Confidence notes** — A free-text field where you can record *why* you have doubts, or which source you are relying on. *"Date of birth uncertain; sources range from 69 to 63 BCE."*

**Verification status** — Reflects how far the record has been reviewed:

| Status | Meaning |
|---|---|
| `pipeline_draft` | Auto-generated, not yet reviewed |
| `needs_review` | Flagged for a human to check |
| `in_review` | Currently being reviewed |
| `human_verified` | A researcher has checked it |
| `expert_verified` | A domain expert has signed off |
| `flagged` | Something looks wrong — needs attention |
| `rejected` | Determined to be incorrect or a duplicate |
| `merged` | Combined with another record |

The aim is that by the time a record reaches `expert_verified`, every date, location, and relationship carries a proper source citation.

---

## Source Citations

Every entity and every relationship can carry **source citations** as structured data. A citation records:
- The source type (primary source, scholarly monograph, database, etc.)
- The title and author
- The specific page or passage
- A reliability tier

This is the same logic as a footnote — it just lives in a machine-readable form alongside the fact it supports.
