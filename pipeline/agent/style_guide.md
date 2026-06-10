# Historical Entity Content Style Guide

This guide defines how generated historical entity summaries and relation descriptions should be written. The goal is to produce concise, accurate, readable content that works well in a graph-based historical map interface.

## General Principles

Generated content should be:

- **Historically grounded**: avoid speculation unless uncertainty is explicitly required.
- **Concise**: write for quick reading in a map or entity panel.
- **Temporal**: include dates, reign periods, eras, or approximate timeframes when available.
- **Relational**: naturally mention important connected people, places, events, states, cultures, or wars.
- **Neutral**: avoid heroic, nationalist, emotional, or judgmental language.
- **Readable**: prefer clear narrative prose over database-like phrasing.

Do not write content that sounds like a raw graph edge, search result, or Wikidata label dump.

---

# Entity Summaries

## Purpose

An entity summary should explain what the entity was, when it existed or was active, and why it matters.

## Length

- Maximum: **1–2 sentences**.
- Preferred: **one strong sentence**.
- Avoid long background explanations.

## Required Content

A good entity summary should include:

1. **Temporal scope** — Reign dates, lifespan, event date, active period, founding/dissolution dates, or era.
   - If dates are approximate, use wording like "around," "by," "during," or "in the early 12th century."
2. **Entity role or type** — Explain whether it was a person, kingdom, city, battle, dynasty, culture, treaty, war, migration, or institution.
3. **Historical significance** — State what made it important in the surrounding historical sequence.
4. **Natural connections** — Mention relevant connected entities only when they add meaning. Do not list connections mechanically.

## Style Rules

- Do **not** begin by repeating the entity's own name.
- Do **not** say "This entity…" or "This person…"
- Do **not** overuse "was."
- Prefer active, specific verbs.
- Avoid vague phrases like "played a role," "was involved," or "was important."
- Avoid modern political framing unless the entity is modern.
- Avoid overstating certainty when evidence is uncertain.

## Recommended Verbs

Use precise historical verbs where appropriate:

- ruled, founded, conquered, defended, expanded, unified, governed, succeeded, resisted
- led, commanded, established, displaced, emerged, declined, controlled
- allied with, rebelled against, fought against, was absorbed into

## Entity Summary Patterns

### Person

```
Ruled [polity] from [start] to [end] and [major achievement/event].
```

Example:

```
Ruled the Kingdom of Georgia from 1089 to 1125 and led the Georgian victory at the Battle of Didgori in 1121.
```

### State / Kingdom / Empire

```
Existed from [start] to [end] as [type of polity], reaching prominence through [major process/event].
```

Example:

```
Emerged as a unified Georgian monarchy in 1008 and became a major regional power during the reign of David IV in the early 12th century.
```

### City / Settlement

```
Served as [role] during [period], linking it to [state/event/culture].
```

Example:

```
Served as a major political and cultural center of eastern Georgia during the medieval period, especially under the Kingdom of Georgia.
```

### Battle / Event

```
Occurred on [date] near/in [place], where [participants] [result/significance].
```

Example:

```
Took place near Didgori on August 12, 1121, where David IV's Georgian forces defeated a larger Seljuk-led army.
```

### Culture / Civilization

```
Flourished during [period] in [region], known for [defining feature/significance].
```

Example:

```
Flourished along the Nile Valley for millennia, forming one of the ancient world's most influential political, religious, and architectural traditions.
```

### Dynasty

```
Ruled [state/region] from [start] to [end], shaping [political/cultural/military development].
```

Example:

```
Ruled Georgia from the medieval period into the early modern era, overseeing the kingdom's political consolidation and later fragmentation.
```

---

# Relation Descriptions

## Purpose

A relation description should explain how two entities are connected in a specific historical context. It should be understandable even without seeing the relation type label.

## Length

- Usually **one sentence**.
- Maximum: **two short sentences** only if the relation requires context.

## Required Content

A good relation description should include:

1. **The action or relationship** — Use a clear verb that matches the relation type.
2. **Directionality** — Make it obvious who acted on whom or what depended on what.
3. **Temporal qualifier** — Include a year, date, reign, war, era, or approximate timeframe when available.
4. **Historical context** — Mention the relevant event, period, reign, campaign, treaty, or conflict.

## Style Rules

- Use active voice when possible.
- Avoid vague wording like "was related to," "was connected with," or "was involved in."
- Do not merely restate the relation type.
- Do not write dry graph language like "Entity A has relation commander_of Entity B."
- Do not over-explain obvious relations.
- Use "during," "after," "before," "under," or "following" to express time clearly.

## Relation Description Patterns

### Person → Event

```
Commanded [side/group] during [event] in [date/year].
```

Example:

```
Commanded the Georgian forces at the Battle of Didgori on August 12, 1121.
```

### Person → State

```
Ruled [state] from [start] to [end], during [major period/event].
```

Example:

```
Ruled the Kingdom of Georgia from 1089 to 1125 during its major period of military and political expansion.
```

### State → Event

```
Participated in [event/conflict] during [date/period], opposing/supporting [other entity].
```

Example:

```
Fought in the Battle of Didgori in 1121 against the Seljuk-led coalition.
```

### Place → Event

```
Hosted or marked the location of [event] in [date/year].
```

Example:

```
Marked the battlefield where Georgian forces defeated the Seljuk-led army in 1121.
```

### State → State

```
Controlled, opposed, succeeded, or bordered [other state] during [period].
```

Example:

```
Opposed the Seljuk Empire during the early 12th century as Georgian power expanded in the Caucasus.
```

### Culture → Region

```
Developed in or spread across [region] during [period].
```

Example:

```
Developed along the Nile Valley during the ancient period, shaping political and religious life in Egypt.
```

---

# Temporal Wording Rules

Use exact dates only when reliable.

| Type | Example |
|------|---------|
| Exact date | `on August 12, 1121` |
| Year | `in 1121` |
| Range | `from 1089 to 1125` |
| Approximate | `around 2000 BCE` |
| Century | `in the early 12th century` |
| Era/period | `during the Middle Kingdom period` |

## BCE Dates

Use **BCE** in public-facing text.

Good:

```
around 2000 BCE
```

Avoid exposing internal negative-year notation in generated prose.

Bad:

```
in -2000
```

---

# Handling Uncertainty

When evidence is uncertain, use cautious language.

## Good uncertainty wording

- Likely served as…
- Traditionally associated with…
- Probably developed during…
- May have corresponded to…
- Is commonly identified with…

## Bad uncertainty wording

- Definitely…
- Certainly…
- Obviously…
- Without doubt…

Use uncertainty only when needed. Do not make every sentence sound doubtful.

---

# Naming Rules

## Do

- Use the most historically appropriate label for the period.
- Prefer the entity's display name unless the temporal context requires a different name.
- Include alternate or ancient names only when useful.
- Use English-readable names for general summaries.

## Do Not

- Mix modern and ancient names without explanation.
- Use modern state names for ancient polities unless referring to geography.
- Use raw Wikidata labels blindly.
- Use internal database labels in prose.

Example:

Good:

```
Flourished in the Nile Valley around 2000 BCE, during the Middle Kingdom period of Ancient Egypt.
```

Bad:

```
Egypt existed in -2000 as Egypt.
```

---

# Entity-Type Specific Guidance

## Person

Focus on role, active period, and major historical impact.

Good:

```
Ruled the Kingdom of Georgia from 1089 to 1125 and led its expansion after the victory at Didgori.
```

Bad:

```
David IV was a person from Georgia.
```

## Polity / Country / Kingdom / Empire

Focus on temporal existence, region, political role, and major transitions.

Good:

```
United much of Georgia from 1008 and became a dominant Caucasian kingdom during the 11th and 12th centuries.
```

Bad:

```
The Kingdom of Georgia was a country.
```

## Event / Battle

Focus on date, location, participants, and outcome.

Good:

```
Took place near Didgori in 1121, where Georgian forces defeated a Seljuk-led coalition.
```

Bad:

```
The Battle of Didgori was a battle.
```

## City / Place

Focus on location, historical role, and connected polity or event.

Good:

```
Served as a major urban center in the Caucasus and became closely tied to the medieval Georgian monarchy.
```

Bad:

```
Tbilisi is a city.
```

## Culture / Civilization

Focus on region, period, and defining contribution or influence.

Good:

```
Developed along the Nile Valley and shaped ancient northeastern Africa through its political institutions, religion, and monumental architecture.
```

Bad:

```
Ancient Egypt was a civilization.
```

---

# Quality Checklist

Before accepting generated content, verify that it:

- [ ] Includes a date, period, or temporal clue when available.
- [ ] Explains why the entity or relation matters.
- [ ] Avoids repeating the entity name at the start.
- [ ] Uses active and specific verbs.
- [ ] Sounds like historical prose, not database metadata.
- [ ] Does not invent facts not supported by sources.
- [ ] Does not expose internal IDs, negative years, confidence scores, or implementation details.
- [ ] Keeps summaries short enough for UI display.
- [ ] Uses BCE/CE formatting in public text.
- [ ] Flags uncertainty when required.

---

# Good vs Bad Examples

## Entity Summary

Good:

```
Ruled the Kingdom of Georgia from 1089 to 1125 and led the decisive victory at the Battle of Didgori in 1121.
```

Bad:

```
David IV was a king of Georgia.
```

Why bad: It repeats the obvious identity, lacks narrative significance, and gives no strong historical context.

## Relation Description

Good:

```
Commanded the Georgian forces at the Battle of Didgori on August 12, 1121.
```

Bad:

```
Was involved in the battle.
```

Why bad: It is vague, passive, and does not explain the nature of the relationship.

## Ancient Naming Example

Good:

```
Flourished along the Nile Valley around 2000 BCE, during the Middle Kingdom period of Ancient Egypt.
```

Bad:

```
Egypt existed in -2000.
```

Why bad: It exposes internal date notation, lacks historical specificity, and ignores the period context.

