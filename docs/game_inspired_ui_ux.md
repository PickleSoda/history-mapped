m# Historical Atlas Project — Game-Inspired UI/UX Design Guide

> **Version:** 1.0 — March 2026
> **Companion to:** Data Pipeline Architecture, Entity Specification v2.0, Reference Tables
> **Purpose:** Visual patterns from Civilization VI & Total War: Rome II applied to the Historical Atlas frontend

---

## Table of Contents

1. [PART I: Game UI Visual Analysis](#part-i-game-ui-visual-analysis)
   - [1. Civilization VI: UI Architecture](#1-civilization-vi-ui-architecture)
   - [2. Total War: Rome II: UI Architecture](#2-total-war-rome-ii-ui-architecture)
   - [3. Summary: Game Patterns → Atlas Equivalents](#3-summary-game-ui-patterns-mapped-to-historical-atlas)

---

## PART I: Game UI Visual Analysis

This section deconstructs the key UI/UX patterns from Sid Meier's Civilization VI and Creative Assembly's Total War: Rome II that are most relevant to the Historical Atlas project. Both games solve a fundamentally similar problem to ours: presenting dense, multi-layered historical and geographic data on a map interface while keeping it navigable, understandable, and visually compelling.

---

### 1. Civilization VI: UI Architecture

#### 1.1 The HUD Philosophy: Information Density at the Edges

Civilization VI uses a classic strategy-game layout: the map dominates the center of the screen, and all statistical information is pushed to screen edges. The top bar serves as a persistent dashboard showing macro-level metrics (science output, gold, culture, faith, tourism) as icon-plus-number pairs. These metrics update every turn, giving the player a constant heartbeat of their civilization's health without ever obscuring the map.

**Key insight for the Historical Atlas:** Statistics should be ambient, not modal. Players rarely click into the top bar; they glance at it. Our entity density overlays, confidence distributions, and coverage metrics should follow this pattern — always visible in a slim panel, never requiring a dedicated screen.

#### 1.2 The Civilopedia: Structured Encyclopedia Browsing

The Civilopedia is Civ VI's in-game encyclopedia. It uses a tabbed top navigation (Units, Buildings, Technologies, Civics, Leaders, etc.) with a left-hand nav column listing entries. Each entry contains structured data (stats, bonuses, requirements) alongside narrative "Historical Context" paragraphs.

**Pattern we should adopt:** Every entity in our database has both structured fields (dates, coordinates, type, confidence) and narrative content (summary, significance). The Civilopedia model of *stats-block-plus-prose* is exactly the right way to present an entity detail panel. The structured data answers "what/when/where," while the LLM-generated summary answers "why it matters."

#### 1.3 Map Overlays and Lenses

Civ VI's map lens system lets players toggle between different views: political (color by owner), religious (color by dominant religion), cultural (tourism influence), settler (resource visibility), and more. Each lens re-colors the same hex grid to show a different data dimension. Crucially, only one lens is active at a time to prevent visual overload.

**Atlas translation:** Instead of "religion" and "culture" lenses, we offer "political control," "trade networks," "religious spread," "military conflicts," and "demographic shifts." The user selects one lens at a time, and the map re-renders entities colored/sized by that dimension.

#### 1.4 Resource Bar and Yield Icons

Civ VI uses a consistent icon language for resources and yields: a beaker for science, a lyre for culture, a coin for gold, a dove for faith, a food icon for growth. These icons are small (16–24px), color-coded, and instantly recognizable. They appear everywhere: the top bar, city panels, tile tooltips, technology trees, and policy cards.

**Atlas translation:** Develop an equivalent SVG icon set for entity types and statistical categories — a sword for military entities, a temple for religious, a coin for economic, a crown for political, a scroll for cultural, a wheat sheaf for agricultural/demographic. Used consistently across the map, detail panels, search results, and dashboard.

#### 1.5 The Report Screen: Tabular Data Drill-Down

Civ VI's Report Screen (especially the modded "Better Report Screen") presents sortable tables of cities, units, deals, resources, and policies. Each row represents an entity (a city, a unit, a trade deal) and columns show key metrics. Clicking a row navigates to that entity on the map. The screen supports tabs for different entity types and column-header sorting.

**Atlas translation:** This is the model for our "Entity Explorer" view — a tabular interface where users can browse all entities for a region/period, sort by date, type, or confidence, and click through to the map. The pipeline's `entity_type` field (30 types) maps naturally to tabs, and the structured fields (dates, coordinates, confidence, `verification_status`) map to sortable columns.

#### 1.6 Turn-Based Timeline as Navigation

Civ VI's core mechanic is turn-based progression through time. The "Era Score" system (from Rise & Fall) tracks historic moments: founding cities, winning battles, discovering technologies. These moments are displayed on a timeline with icons, grouped by era, and summarized with a score.

**Atlas translation:** Replace "turns" with a continuous timeline scrubber. The Era Score concept is powerful: when a user scrubs to a new century, show a "Period Highlights" panel listing the most significant entities (high `display_priority`) with their icons and one-line summaries — essentially the thematic clustering output from pgvector (Section 12.6 of the pipeline doc).

---

### 2. Total War: Rome II: UI Architecture

#### 2.1 The Campaign Map: Province-Level Data

Total War: Rome II organizes its campaign map around provinces. Each province contains settlements, and clicking a settlement opens an overlay panel showing: wealth and income breakdown, public order indicators, food production, culture influence, and building slots. The key pattern is **progressive disclosure**: the map shows faction colors and settlement icons at the zoomed-out level, then reveals statistical detail when you click.

**Atlas translation:** Zoomed out, entities appear as clustered icons with density indicators. Clicking a region opens a province-style overview showing entity count by type, dominant political entity, key events, and aggregate confidence scores. Clicking deeper opens individual entity detail.

#### 2.2 Faction Summary Panel

Rome II's Faction Summary is a multi-tab panel showing: faction details (culture, capital, territory count), political parties (loyalty, senator count), imperium level (army/fleet/agent caps), diplomacy status (allies, wars, treaties), and trade/finance breakdown (income sources, expenditure, trade partners). Each section uses small icon+number pairs for quick scanning, with hover tooltips for detail.

**Atlas translation:** The "Faction Summary" becomes the "Political Entity Detail Panel." When a user selects the Roman Empire in the 3rd century, they should see: territory extent, capital city, key rulers (linked Person entities), vassal/successor states, economic indicators (trade routes passing through), military conflicts in the period, and religious composition. All of this data already exists in our entity model and relationship tables.

#### 2.3 Province Details: The Statistics Breakdown

The Province Details screen in Rome II is where the deepest statistical data lives. It shows: wealth by source (subsistence, commerce, agriculture, industry, culture), tax rate and its effects, slave population percentage and impact, corruption levels, public order modifiers (a stacked bar showing positive and negative contributors), and cultural influence pie chart. Every number is hoverable for a breakdown tooltip.

**Key pattern — stacked modifier bars:** Public order in Rome II isn't just a number; it's a bar showing +3 from temples, +2 from garrison, -4 from taxes, -2 from cultural unrest, netting to -1. This "explained metric" pattern is exactly what we need for entity confidence: instead of just showing "medium," show what contributes — "geocoding: high, date: medium, source count: low" as a stacked indicator.

#### 2.4 The Technology Tree: Linear Progression Visualization

Rome II's technology tree visualizes research as a directed graph: nodes for technologies, edges for prerequisites, grouped into branches (military, civil, philosophy). Each node shows an icon, name, and tooltip with effects. Already-researched nodes are highlighted; available ones pulse; locked ones are grayed.

**Atlas translation:** This pattern maps to our "related entities" and "causal chains." When viewing a historical event, the user could see a cause-effect chain visualized as a horizontal tree: the Crisis of the Third Century leads to Diocletian's Reforms, which leads to the Tetrarchy, which leads to Constantine's reunification. The relationship data from Stage 6 of the pipeline (`relationship_type`, `temporal_range`) provides exactly this structure.

#### 2.5 The Balance of Power Indicator

In Rome II battles, a horizontal bar at the top of the screen shows the relative strength of allied vs. enemy forces. It shifts in real-time as units take casualties. This is a simple but extremely effective visualization of a single comparative metric.

**Atlas translation:** When comparing two political entities (e.g., Roman Empire vs. Sassanid Empire at 260 CE), a balance-of-power bar could show relative territory, military strength, population, or trade volume — drawn from the structured fields on their respective entity records.

#### 2.6 Character Panels and Trait Systems

Both Civ VI (leaders with agendas) and Rome II (generals/governors with traits) attach rich metadata to person entities. Rome II's character panel shows: portrait, traits as icon badges (e.g., "severe", "good commander"), stats as small bars (authority, cunning, zeal), and a list of associated actions/missions.

**Atlas translation:** Our Person entity type should render similarly. The LLM-generated summary provides the narrative, but we can also display structured attributes as trait badges: "Military Leader," "Religious Reformer," "Dynasty Founder." These could be derived from `entity_type` sub-classifications or from relationship types (e.g., a person who has "commanded" relationships to military units gets a "Military Leader" badge).

---

### 3. Summary: Game UI Patterns Mapped to Historical Atlas

| Game Pattern | Source | Atlas Equivalent | Priority |
|---|---|---|---|
| Top-bar ambient metrics | Civ VI | Persistent stats ribbon: entity count, coverage %, avg confidence | High |
| Map lenses / overlays | Civ VI | Thematic overlays: political, trade, religion, military, demographic | High |
| Civilopedia entity pages | Civ VI | Entity detail panel: stats block + narrative summary + source citations | High |
| Report screen with sortable tables | Civ VI | Entity Explorer: tabular browse with sort, filter, click-to-map | High |
| Era Score / period highlights | Civ VI | Period Highlights from pgvector thematic clustering | Medium |
| Consistent yield icon language | Civ VI | SVG icon set for 30 entity types + stat categories | High |
| Province overview panel | Rome II | Region overview: entity density, dominant polity, key events, confidence | High |
| Faction summary multi-tab | Rome II | Political Entity Detail: territory, rulers, economy, military, religion | High |
| Stacked modifier bars | Rome II | Confidence breakdown: geocoding + date + source count indicators | Medium |
| Technology / cause-effect tree | Rome II | Causal chain visualization from relationship data | Medium |
| Balance of power bar | Rome II | Comparative entity view: side-by-side metric bars | Low |
| Character traits as badges | Rome II | Person entity trait badges derived from relationships | Medium |
| Hover tooltips everywhere | Both | Contextual tooltips on every stat, date, coordinate, and confidence score | High |
| Progressive disclosure (zoom) | Both | Zoom-level detail: clusters → region overview → entity detail | High |

---
