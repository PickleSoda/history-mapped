# Talk with people: design (phase one)

Date: 2026-11-19. Status: built, phase one.

## Goal

A signed-in visitor chats with a historical person who answers in character, knowing only what that person would plausibly know of their era and surroundings. One chat per person per user, as if they know each other.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| Speaker | An entity with a persona row; only `person` built | Keeps the door open to city or family speakers |
| Eligibility | Person, known death year, dead at least 70 years | No living or recently dead people |
| Persona | Generated once by the model from atlas data, stored with model and version | Cost once, consistent voice, editable later |
| Knowledge | SQL only, a reusable action, cached an hour | No model cost, auditable, testable |
| Cutoff | The death year; nothing later, and text naming a later year is dropped | Prevents anachronism leaks |
| Reach | Impact score plus link count: wide, regional, local | A peasant knows less than a king |
| Reply | Non-streaming JSON | Simplest; streaming is later work |
| Failure | Store nothing, charge nothing | No orphan turns |
| Memory | Last 16 turns plus a rolling summary written after the response | Bounded prompt |

## Data model

| Table | Columns of note |
|---|---|
| `entity_personas` | entity_id (unique), persona JSON, knowledge_year, model, version, source (generated or edited) |
| `persona_conversations` | user_id, entity_id (unique together), last_message_at, summary, summarised_until_id |
| `persona_messages` | conversation_id, user_id, role, content, model, token counts |

## Prompt structure

1. Identity and the role-play frame
2. Who you are (name, dates, roles, atlas summary)
3. Character (voice, temperament, values, habits, how to address an acquaintance, language note)
4. What you know, as of the knowledge year (the briefing)
5. What you remember of earlier talks (the summary)
6. Rules you never break (character, cutoff, no invention, user text is not instructions, safety, length, language)

## Limits

Config in `api/config/persona.php`: message 2,000 characters, 100 messages a day, 12 a minute, 450 output tokens, briefing 2,500 tokens, 16 recent messages.

## Measured briefing

On the 641k-entity dev database the briefing takes 40 to 240 ms uncached and 700 to 1,000 tokens for well-linked people.

## Later phases

| Phase | Idea |
|---|---|
| City residents | A merchant and a family whose roles depend on the era and events; the knowledge action takes a place and year instead of a person |
| Streaming | Server-sent events for replies |
| Admin persona editing | Edit the sheet and knowledge year; `source = edited` stops regeneration |
| MCP tool | Expose "talk to" through the MCP connector |
| Better ranking | A real importance signal for neighbours; cities with no end date include ruins |
