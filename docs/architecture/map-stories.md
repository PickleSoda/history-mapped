# Map stories

A map story replays one subject step by step on the map. A battle shows its units, positions and
manoeuvres. An epidemic shows its spread, and a trade network its routes and ports. Each step has a
date, a short narrative and a camera, and the story as a whole states its sources and its
uncertainty. This page covers the document format, the story's life from builder to database, and
how the public app plays it.

> **Audience:** developers, editors, historians, product · **Read time:** 9 minutes ·
> **Last reviewed:** 2026-11-14 · **Code:** `pipeline/map_stories/`, `api/app/Actions/MapStory/*`,
> `api/app/Support/MapStory/*`, `web/src/lib/map-story/*` · **How-to:** [Authoring map stories](../implementation-docs/map-story-authoring.md)

## At a glance

```mermaid
flowchart TB
    R["Research tools: cached Wikipedia, Wikidata, places"] --> B["Builder module (Python)"]
    B -->|"build: validate and lint"| F[/"map-stories/slug.json"/]
    F -->|"map-stories:sync"| S["SaveMapStoryAction: check, resolve, revision"]
    ED["Admin story editor"] --> S
    AI["AI assistant: JSON Patch"] --> S
    S --> DB[("map_stories: the live copy")]
    DB -->|"map-stories:export"| F
    DB --> API["GET /api/v1/map-stories"]
    API --> P["Story player"]
    API --> AMB["Ambient layer"]
```

- **The database row is the live copy.** The JSON files are seeds and exports. `map-stories:sync`
  loads changed files and keeps rows that an editor changed, unless `--force`. `map-stories:export`
  writes edited rows back to the files.
- **There is one write path.** The editor, the AI, sync and restores all go through
  `SaveMapStoryAction`. It checks the document, resolves it against the atlas, and writes a
  revision and the row in one transaction. The newest 50 revisions are kept.

## What exists

There are 12 stories. 8 are battles, two of them naval: Blenheim, Cannae, Carrhae, Gaugamela,
Hastings, Navarino, Salamis and Waterloo. The other 4 are wide stories: the Black Death, the 1918
influenza pandemic, the Hanseatic League and the Indian Ocean dhow trade. The 4 wide stories are
also ambient, and the dhow-trade story is the map layer of a chronicle.

| Kind | Scale | Since schema |
|---|---|---|
| `battle`, `naval_battle`, `siege` | A battlefield: units, formations, arrows, terrain, light and wind | 1 |
| `campaign` | A theatre of operations | 1 |
| `war`, `expansion`, `migration`, `exploration`, `diffusion`, `event` | A region or continent: routes, regions, places | 3 |
| `trade_route` | Routes, ports and markets | 3 |
| `epidemic` | Outbreaks and spreading regions, with infected, peak and recovered states | 3 |

## The document

```mermaid
classDiagram
    class Story {
        schema, slug, kind
        title, year, date_label
        intro, outcome, uncertainty
        sources, camera, alt_sites
        schema 3: period, ambient, legend
    }
    class Side {
        id, name, color
        polity: name, wikidata
        commanders, strength, losses
    }
    class Unit {
        id, side, kind
        label, strength
    }
    class Feature {
        id, kind
        at, line or area
        entity, route or region kind
    }
    class Step {
        id, title, time, narrative
        camera, notes, focus
        positions, moves
        schema 3: date, entry, entities
        schema 2: beats, light, wind
    }
    Story "1" --> "*" Unit
    Story "1" --> "*" Feature
    Story "1" --> "1..*" Step
    Story "1" --> "*" Side
    Unit "*" --> "1" Side : belongs to
```

| Part | Purpose | Examples |
|---|---|---|
| **Sides** | The parties, with their polity's QID, commanders, strength and losses. Battles, naval battles and sieges need two | Carthage and Rome at Cannae |
| **Units** | What moves on the map | `heavy_infantry`, `cavalry`, `elephants`, `warship`, `caravan`, `fleet` |
| **Features** | The fixed map: points, lines and areas | a `river`, a `ridge`, `woods`, a `port`, a trade `route`, a spreading `region` |
| **Steps** | One moment each. Unit positions, moves (`advance`, `charge`, `rout`, `sail`, `spread`…), notes, and, in schema 3, the entities shown and the feature states | "Hannibal's centre gives way" |
| **Sources and uncertainty** | At least one source, typed `primary`, `secondary`, `web` or `video`, plus a statement of what is uncertain. Alternative sites can be listed where the location is disputed | Polybius, Livy; the site on the Aufidus is debated |

A story belongs to an entity (named with its QID), to a chronicle (by slug, schema 3), or to both.
In schema 3 a step can also name the chronicle entry it illustrates. There are 30 unit kinds, 31
feature kinds and 19 move types.

The vocabulary is defined three times and kept in step: `api/app/Support/MapStory/MapStoryVocabulary.php`,
`pipeline/map_stories/schema.py` and `web/src/lib/schemas/map-story.ts`. Schemas 1 to 3 are all
accepted.

## How a story is linked to the atlas

When a story is saved, `ResolveMapStoryAction` resolves every reference to an id, so the player can
link to the atlas pages:

```mermaid
flowchart TB
    D["Authored document"] --> C{"MapStoryDocument: valid?"}
    C -->|no| X["Errors by field; nothing written"]
    C -->|yes| R["ResolveMapStoryAction"]
    R --> R1["Story entity and chronicle; steps to entries"]
    R --> R2["Every QID gets an entity_id"]
    R --> R3["Shown entities: geometry and OHM borders"]
    R --> R4["Period, extent, ambient layer"]
    R1 & R2 & R3 & R4 --> W["Revision, then the map_stories row"]
```

A QID whose entity is clearly from another era resolves to nothing rather than to a namesake. After
new entities are imported, `map-stories:relink` resolves the stored stories again without losing
edits.

## Playing a story

```mermaid
sequenceDiagram
    autonumber
    actor U as Reader
    participant SP as StoryPlayer
    participant API as /api/v1
    participant O as StoryOverlay
    participant M as Map

    U->>SP: Play (an entity's story button, a battle map, an ambient card, or a link)
    SP->>API: GET /map-stories/{slug}
    API-->>SP: the resolved document
    SP->>O: start at step 0 (URL story=slug, sstep=0)
    O->>M: hide the entity layers, set the year to the step's year
    O->>M: battle kinds: add hillshade relief and modern water and names
    loop each step (Next, Prev, arrow keys or autoplay)
        O->>M: fly to the step's camera, or fit its extent
        O->>M: animate units along their moves, fade regions, flow route dashes
        O->>API: GET /entities/{id} for the step's shown entities
        O->>M: outline their OpenHistoricalMap borders at that date
    end
    U->>SP: Exit
    O->>M: remove the story layers, the entity layers come back
```

- **Autoplay** waits 6 to 22 seconds per step, depending on the length of the narrative, plus 1.2
  seconds for each beat.
- **As a chronicle's map layer,** the story draws only its own layers under the chronicle player.
  Each chronicle step shows the matching story step.
- **Ambient stories** draw a faint layer of routes, regions, outbreaks and ports on the atlas for
  the current year whenever nothing is playing (`GET /map-stories/ambient?year=&bbox=`). The card
  on that layer has a "Play" button.
- **Where readers find stories:** the swords marker on the map (the tile property
  `has_map_story`), the entity panel and page, the landing page, `/browse` and `/browse/stories`.
- **Admin preview:** the admin story editor shows this same player in an iframe
  (`/app?story=<slug>&sstep=0&preview=1`) and sends it the draft as you type. See
  [Admin and editing](admin-map-editor.md#the-map-story-editor).

## Authoring

```mermaid
sequenceDiagram
    autonumber
    participant Q as map_stories queue
    participant A as battle-author
    participant T as Research tools
    participant B as build
    participant R as battle-reviewer
    participant L as Laravel

    Q->>A: a battle with a QID and no story
    A->>T: research (sections, QIDs), places near the site, elevation
    A->>B: builder module, then build: validate and lint (up to 4 rounds)
    B-->>A: errors and layout warnings
    A->>T: preview: a contact sheet of every step
    A->>A: write the long description (entity-descriptions/slug.md)
    A->>R: review
    R->>T: fact-check each step, verify every QID
    alt PASS or FIXED
        R-->>L: map-stories:sync, entities:sync-descriptions
    else REDO
        R-->>A: reasons, rewrite
    end
```

- Builder modules use layout helpers, so formations and arrows are computed rather than typed in.
  `build` refuses to overwrite a file that was exported from the admin until its edits are ported
  into the builder module (or `--force`).
- Research is cached under `output/map-stories/cache/`. Place and elevation lookups (OSM Nominatim,
  OpenTopoData) are limited to one call per second.
- The step-by-step guide, including the checks, the agents and the bulk run, is
  [Authoring map stories](../implementation-docs/map-story-authoring.md).

## Where next

- [Chronicles](chronicles.md): stories as a chronicle's map layer
- [Maps, tiles and OHM](ohm-integration.md): the basemap and borders the player draws on
- [REST API](../schemas/rest-api.md#map-stories-collections-tags-reference-data): the endpoints
