# Entity Model — Overview

Start with the files in this folder for the live canonical model. Historical proposal material has been moved under `docs/archive/entity-model/` so the current model reference stays focused.

The **Entity** is the central building block of the database. Almost everything that can be studied, mapped, or described in world history is represented as an entity: a kingdom, a city, a person, a battle, a trade route, a religious text, a plague.

## What is an Entity?

An entity is a **named historical thing** that existed in time and, usually, in space. It belongs to one of five broad groups:

| Group | What it covers |
|---|---|
| **POLITY** | States, dynasties, rulers, armies, social classes, diplomatic agreements |
| **PLACE** | Cities, monuments, mines, universities, infrastructure |
| **EVENT** | Wars, battles, treaties, rebellions, disasters, migrations, epidemics |
| **ECONOMY** | Trade routes, natural resources, currencies and monetary systems |
| **CULTURE** | Works of art or literature, intellectual movements, languages, religions, legal codes, technologies |

Within each group there are specific **types** — for example, within POLITY you can have a `political_entity` (the Roman Republic), a `dynasty` (the Julio-Claudian dynasty), or a `person` (Julius Caesar).

## How Entities Connect

Entities are linked to each other through **relationships**. A relationship says: *entity A stands in some defined relation to entity B, during a given time window, with a stated level of confidence.* There are 76 named relationship types, covering political, military, economic, cultural, causal, knowledge-transfer, and diplomatic connections.

**Example — the fall of the Western Roman Empire:**

```
Western Roman Empire  ──[at_war_with]──►  Visigoths
Western Roman Empire  ──[weakened_by]──►  Sack of Rome (410 CE)
Sack of Rome (410 CE) ──[resulted_from]──►  Visigoth Invasion
Romulus Augustulus    ──[rules]──────────►  Western Roman Empire
Odoacer               ──[succeeded_by]───►  Western Roman Empire
```

## Chronicles

On top of entities and relationships there is a **Chronicle** layer (added June 2026): an ordered sequence of narrative
entries, each tied to a primary relationship and a set of secondary entities. Chronicles live in their own tables
(`chronicles`, `chronicle_entries`, `chronicle_entry_entities`) and are documented in [attributes.md](./attributes.md) §6
and [diagrams.md](./diagrams.md) §6.

## Documents in This Folder

| File | Audience |
|---|---|
| [for-historians.md](./for-historians.md) | Historians and researchers — explains what each field means conceptually, with worked examples from world history |
| [for-geodata-contributors.md](./for-geodata-contributors.md) | People entering geographic and spatial data — explains location fields, coordinate systems, and territory geometry |
| [attributes.md](./attributes.md) | Full reference for every attribute (field) on an entity, with allowed values and notes |
| [relationships.md](./relationships.md) | Full reference for all 76 relationship types with examples |
| [../archive/entity-model/schema-proposal-strict-write-derived-timeline.md](../archive/entity-model/schema-proposal-strict-write-derived-timeline.md) | Historical proposal that informed the normalized write model and derived timeline direction |
| [laravel-implementation-checklist.md](./laravel-implementation-checklist.md) | Current implementation status and remaining cleanup items for the canonical entity model |
