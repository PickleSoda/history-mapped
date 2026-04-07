# Entity Model — Overview

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

## Documents in This Folder

| File | Audience |
|---|---|
| [for-historians.md](./for-historians.md) | Historians and researchers — explains what each field means conceptually, with worked examples from world history |
| [for-geodata-contributors.md](./for-geodata-contributors.md) | People entering geographic and spatial data — explains location fields, coordinate systems, and territory geometry |
| [attributes.md](./attributes.md) | Full reference for every attribute (field) on an entity, with allowed values and notes |
| [relationships.md](./relationships.md) | Full reference for all 76 relationship types with examples |
| [schema-proposal-v2-strict-write-derived-timeline.md](./schema-proposal-v2-strict-write-derived-timeline.md) | Proposed V2 model: strict normalized write model, derived timeline projection, and manual geometry period policy |
| [laravel-implementation-checklist-v2.md](./laravel-implementation-checklist-v2.md) | Repository-specific implementation checklist covering migrations, models, APIs, read paths, tests, and cutover concerns |
