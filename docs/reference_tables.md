# Historical Atlas — Reference Tables

> **Companion to:** Entity Specification v2.0, Data Pipeline Architecture
> **Storage:** All reference tables live in PostgreSQL. They are manually curated, not pipeline-generated. They serve as lookup data for entity resolution, display formatting, and analytical grouping.
> **Key principle:** Reference tables describe *how we organize and interpret* history, not history itself. They don't have embeddings, don't appear on the map as clickable entities, and don't flow through the 8-stage pipeline.

---

## Table of Contents

1. [Historical Periods / Eras](#1-historical-periods--eras)
2. [Historiographical Schools](#2-historiographical-schools)
3. [Geographic Regions (Standardized)](#3-geographic-regions)
4. [Calendar Systems](#4-calendar-systems)
5. [Era-to-Date Resolution Table](#5-era-to-date-resolution-table)
6. [Writing Systems](#6-writing-systems)
7. [Religious Tradition Taxonomy](#7-religious-tradition-taxonomy)
8. [Unit and Measurement Standards](#8-unit-and-measurement-standards)
9. [Language Families](#9-language-families)
10. [Source Type Definitions](#10-source-type-definitions)

---

## 1. Historical Periods / Eras

Formerly entity #28 in v1.0. Demoted to reference table because periods don't have coordinates, don't appear on the map, and are interpretive frameworks rather than historical facts. Multiple overlapping periodization schemes exist for the same time and place.

Used by:
- **Stage 4 (Temporal Extraction):** Tier 4 date resolution ("during the Late Bronze Age" → lookup this table)
- **Frontend:** `era_label` computed field on entities, era-based navigation, period overview panels
- **Thematic clustering:** Providing context labels for pgvector cluster summaries

```sql
CREATE TABLE ref_historical_periods (
  period_id           SERIAL PRIMARY KEY,
  name                TEXT NOT NULL,           -- "Late Bronze Age"
  alternative_names   TEXT[],                  -- ["LBA", "Late Bronze Age Collapse period"]
  
  -- Temporal bounds (EDTF)
  start_date          TEXT NOT NULL,           -- "-1600" (1600 BCE)
  end_date            TEXT NOT NULL,           -- "-1200"
  date_precision      TEXT,                    -- "approximate", "conventional", "debated"
  
  -- Scope
  geographic_scope    TEXT NOT NULL,           -- "Eastern Mediterranean" or "Global"
  region_id           INTEGER REFERENCES ref_geographic_regions(region_id),
  
  -- Classification
  periodization_scheme TEXT NOT NULL,          -- "Western conventional", "Chinese dynastic",
                                              -- "Islamic", "Archaeological", "Art Historical"
  parent_period_id    INTEGER REFERENCES ref_historical_periods(period_id),
                                              -- "Classical Antiquity" → parent of "Hellenistic"
  depth_level         INTEGER DEFAULT 0,       -- 0 = broadest (Ancient), 1 = (Classical), 2 = (Late Republic)
  
  -- Metadata
  defining_characteristics TEXT,               -- What makes this period distinct
  conventional_start_event TEXT,               -- "Fall of Troy" / "Battle of Actium"
  conventional_end_event   TEXT,               -- "Sea Peoples invasions" / "Fall of Rome"
  historiographical_notes  TEXT,               -- Scholarly debates about boundaries
  value_judgments          TEXT,               -- e.g., "Dark Ages" is considered pejorative
  
  -- Display
  color_hex           TEXT,                    -- Period-specific color for timeline rendering
  sort_order          INTEGER                  -- For deterministic display ordering
);

CREATE INDEX idx_periods_dates ON ref_historical_periods(start_date, end_date);
CREATE INDEX idx_periods_scheme ON ref_historical_periods(periodization_scheme);
CREATE INDEX idx_periods_region ON ref_historical_periods(region_id);
```

### Seed Data (representative, not exhaustive)

```
scheme: "Western conventional"
├── Ancient (before 500 CE)
│   ├── Prehistoric
│   │   ├── Paleolithic (-3000000 / -10000)
│   │   ├── Mesolithic (-10000 / -8000)
│   │   └── Neolithic (-8000 / -3300)
│   ├── Bronze Age (-3300 / -1200)
│   │   ├── Early Bronze Age (-3300 / -2000)
│   │   ├── Middle Bronze Age (-2000 / -1600)
│   │   └── Late Bronze Age (-1600 / -1200)
│   ├── Iron Age (-1200 / -500)
│   ├── Classical Antiquity (-500 / 500)
│   │   ├── Archaic Greece (-800 / -480)
│   │   ├── Classical Greece (-480 / -323)
│   │   ├── Hellenistic Period (-323 / -31)
│   │   ├── Roman Republic (-509 / -27)
│   │   │   ├── Early Republic (-509 / -264)
│   │   │   ├── Middle Republic (-264 / -133)
│   │   │   └── Late Republic (-133 / -27)
│   │   ├── Roman Empire (-27 / 476)
│   │   │   ├── Principate (-27 / 284)
│   │   │   ├── Crisis of the Third Century (235 / 284)
│   │   │   ├── Dominate (284 / 476)
│   │   │   └── Tetrarchy (293 / 313)
│   │   └── Late Antiquity (284 / 700)
│   └── ...
├── Medieval (500 / 1500)
│   ├── Early Medieval (500 / 1000)
│   ├── High Medieval (1000 / 1300)
│   └── Late Medieval (1300 / 1500)
├── Early Modern (1500 / 1800)
├── Modern (1800 / present)
│   ├── Long 19th Century (1789 / 1914)
│   ├── World Wars (1914 / 1945)
│   └── Contemporary (1945 / present)
└── ...

scheme: "Chinese dynastic"
├── Three Sovereigns and Five Emperors (mythical)
├── Xia Dynasty (-2070 / -1600)
├── Shang Dynasty (-1600 / -1046)
├── Zhou Dynasty (-1046 / -256)
│   ├── Western Zhou (-1046 / -771)
│   └── Eastern Zhou (-771 / -256)
│       ├── Spring and Autumn (-771 / -476)
│       └── Warring States (-476 / -221)
├── Qin Dynasty (-221 / -206)
├── Han Dynasty (-206 / 220)
│   ├── Western Han (-206 / 9)
│   ├── Xin Dynasty (9 / 23)
│   └── Eastern Han (25 / 220)
├── Three Kingdoms (220 / 280)
├── ...

scheme: "Islamic"
├── Pre-Islamic Arabia (jahiliyyah)
├── Prophetic Period (610 / 632)
├── Rashidun Caliphate (632 / 661)
├── Umayyad Caliphate (661 / 750)
├── Abbasid Caliphate (750 / 1258)
│   ├── Early Abbasid Golden Age (750 / 847)
│   └── Late Abbasid / Fragmentation (847 / 1258)
├── ...

scheme: "South Asian"
├── Indus Valley Civilization (-3300 / -1300)
├── Vedic Period (-1500 / -500)
├── Mahajanapadas (-600 / -345)
├── Maurya Empire (-322 / -185)
├── ...

scheme: "Mesoamerican"
├── Preclassic / Formative (-2000 / 250)
├── Classic (250 / 900)
├── Postclassic (900 / 1521)
├── ...

scheme: "Archaeological"
├── Stone Age
├── Bronze Age (region-specific dates)
├── Iron Age (region-specific dates)
├── ...
```

### Usage in Pipeline

**Stage 4 (Temporal Extraction), Tier 4 resolution:**
```
Input:  "during the Late Bronze Age"
Lookup: SELECT start_date, end_date FROM ref_historical_periods
        WHERE name ILIKE '%Late Bronze Age%'
        AND periodization_scheme = 'Western conventional'
Output: date_resolved = "-1600/-1200"
        date_method = "era_table_lookup"
        date_confidence = "medium-low"
```

**Frontend — era_label computation:**
```sql
SELECT p.name
FROM ref_historical_periods p
WHERE p.start_date <= entity.temporal_start
  AND p.end_date >= entity.temporal_end
  AND p.region_id = entity_region_id
  AND p.depth_level = 2  -- most specific matching period
ORDER BY p.depth_level DESC
LIMIT 1;
```

---

## 2. Historiographical Schools

Formerly entity #29 in v1.0. Demoted because these describe modern scholarly frameworks, not historical entities. They're used to tag interpretive biases in source material and entity assessments.

Used by:
- **Stage 8 (Human Review):** Reviewers can tag entities with the interpretive framework informing the source
- **Frontend:** "Interpretation" badge on entity detail panels; filter for scholarly perspective
- **Quality assessment:** Flagging when all sources for an entity come from one school

```sql
CREATE TABLE ref_historiographical_schools (
  school_id           SERIAL PRIMARY KEY,
  name                TEXT NOT NULL,            -- "Annales School"
  alternative_names   TEXT[],                   -- ["Annales historians", "Annales tradition"]
  
  -- Temporal scope
  active_from         TEXT,                     -- "1929"
  active_to           TEXT,                     -- NULL if still active
  
  -- Description
  interpretive_framework TEXT NOT NULL,         -- Core analytical approach
  methodological_approach TEXT,                 -- What methods they favor
  evidence_emphasized    TEXT,                  -- What evidence they prioritize
  evidence_downplayed    TEXT,                  -- What they tend to ignore
  political_commitments  TEXT,                  -- Known ideological leanings
  
  -- Influence
  geographic_center   TEXT,                     -- Where scholars are based
  dominant_regions    TEXT[],                   -- Regions where this school dominates
  dominant_periods    TEXT[],                   -- Periods they're strongest on
  
  -- Key figures (text references, not FK — these are modern scholars, not historical persons)
  key_historians      TEXT[],                   -- ["Fernand Braudel", "Marc Bloch"]
  foundational_works  TEXT[],                   -- ["The Mediterranean and the Mediterranean World"]
  
  -- Relationships
  influenced_by       INTEGER[],               -- school_ids
  opposed_to          INTEGER[],               -- school_ids
  
  sort_order          INTEGER
);
```

### Seed Data

| Name | Framework | Evidence Emphasized | Known For |
|------|-----------|-------------------|-----------|
| Annales School | Long-duration structural history (longue durée) | Geography, climate, demography, economic structures | De-emphasizing events and individuals in favor of deep structures |
| Marxist Historiography | Class struggle and economic base as drivers of change | Economic relations, labor, class conflict | Material conditions determine political/cultural superstructure |
| Postcolonial Studies | Power dynamics of colonialism and its legacies | Subaltern voices, colonial archives read against the grain | Challenging Eurocentric narratives |
| World-Systems Theory | Core-periphery economic relationships | Trade flows, resource extraction, labor division | Wallerstein's hierarchy of global economic zones |
| Rankean Empiricism | "How it actually happened" — primary source criticism | Official documents, diplomatic archives | Foundational source-critical method |
| Cultural/Intellectual History | Ideas, mentalities, and meaning-making | Texts, art, symbols, discourse | How people understood their world |
| Environmental History | Human-environment interaction over time | Climate data, ecology, disease, agriculture | Nature as historical actor, not just backdrop |
| Cliometrics / New Economic History | Quantitative analysis of economic history | Statistical data, econometric models | Numbers over narrative |
| Gender History | Gender as a category of historical analysis | Women's experiences, masculinity, sexuality | Expanding who counts as a historical subject |
| Big History | Very long timescales including pre-human | Archaeological, geological, astronomical evidence | History from Big Bang to present |
| Military History (New) | War in social, cultural, and economic context | Soldiers' experiences, logistics, home front | Moving beyond battles and generals |
| Microhistory | Intensive study of small units (village, trial, individual) | Local archives, court records, personal papers | Revealing large patterns through small cases |

---

## 3. Geographic Regions (Standardized)

A hierarchical region taxonomy for batch organization, geographic filtering, and spatial context. Not map boundaries — these are fuzzy conceptual regions used for organizing data, not drawing borders.

```sql
CREATE TABLE ref_geographic_regions (
  region_id           SERIAL PRIMARY KEY,
  name                TEXT NOT NULL,            -- "Eastern Mediterranean"
  alternative_names   TEXT[],                   -- ["Levant and Aegean", "Near East coast"]
  
  -- Hierarchy
  parent_region_id    INTEGER REFERENCES ref_geographic_regions(region_id),
  depth_level         INTEGER DEFAULT 0,        -- 0 = continental, 1 = sub-continental, 2 = regional
  
  -- Spatial (approximate, for batch assignment and filtering)
  bounding_box        GEOMETRY(POLYGON, 4326),  -- PostGIS rough bounding polygon
  center_point        GEOMETRY(POINT, 4326),    -- For distance calculations
  
  -- Context
  modern_countries    TEXT[],                   -- For user orientation: ["Turkey", "Syria", "Lebanon"]
  historical_names    TEXT[],                   -- ["Asia Minor", "Anatolia", "Rum"]
  
  -- Pipeline usage
  typical_periods     TEXT[],                   -- Periods commonly associated with this region
  batch_priority      INTEGER DEFAULT 0,        -- Processing priority (higher = sooner)
  
  sort_order          INTEGER
);

CREATE INDEX idx_regions_bbox ON ref_geographic_regions USING GIST(bounding_box);
CREATE INDEX idx_regions_parent ON ref_geographic_regions(parent_region_id);
```

### Seed Data (hierarchy)

```
World
├── Africa
│   ├── North Africa
│   │   ├── Egypt and Nile Valley
│   │   ├── Maghreb
│   │   └── Sahara
│   ├── West Africa
│   │   ├── Sahel
│   │   ├── Guinea Coast
│   │   └── Niger River Basin
│   ├── East Africa
│   │   ├── Horn of Africa
│   │   ├── Great Lakes Region
│   │   └── Swahili Coast
│   ├── Central Africa
│   │   └── Congo Basin
│   └── Southern Africa
├── Europe
│   ├── Mediterranean Europe
│   │   ├── Italian Peninsula
│   │   ├── Iberian Peninsula
│   │   ├── Greece and Balkans
│   │   └── Mediterranean Islands
│   ├── Western Europe
│   │   ├── France / Gaul
│   │   ├── Low Countries
│   │   └── British Isles
│   ├── Central Europe
│   │   ├── Germanic Lands
│   │   └── Danubian Region
│   ├── Eastern Europe
│   │   ├── Slavic Lands
│   │   ├── Pontic Steppe
│   │   └── Baltic Region
│   └── Scandinavia
├── Asia
│   ├── Near East / Western Asia
│   │   ├── Mesopotamia
│   │   ├── Levant
│   │   ├── Anatolia
│   │   ├── Arabian Peninsula
│   │   ├── Iranian Plateau
│   │   └── Caucasus
│   ├── Central Asia
│   │   ├── Transoxiana
│   │   ├── Steppe Belt
│   │   └── Tarim Basin
│   ├── South Asia
│   │   ├── Indus Valley
│   │   ├── Gangetic Plain
│   │   ├── Deccan
│   │   └── Sri Lanka
│   ├── East Asia
│   │   ├── China — North (Yellow River)
│   │   ├── China — South (Yangtze)
│   │   ├── Korean Peninsula
│   │   ├── Japanese Archipelago
│   │   └── Mongolian Plateau
│   └── Southeast Asia
│       ├── Mainland Southeast Asia
│       └── Maritime Southeast Asia
├── Americas
│   ├── North America
│   ├── Mesoamerica
│   ├── Caribbean
│   ├── Andean Region
│   └── Southern Cone
├── Oceania
│   ├── Australia
│   ├── Melanesia
│   ├── Micronesia
│   └── Polynesia
└── Oceans and Maritime Zones
    ├── Mediterranean Sea
    ├── Indian Ocean
    ├── Atlantic (pre-Columbian)
    ├── Pacific
    ├── Red Sea
    ├── Black Sea
    └── South China Sea
```

---

## 4. Calendar Systems

For converting and displaying dates from non-Gregorian sources. The pipeline stores all dates in EDTF (Gregorian-based), but `date_raw` preserves the original calendar expression.

```sql
CREATE TABLE ref_calendar_systems (
  calendar_id         SERIAL PRIMARY KEY,
  name                TEXT NOT NULL,            -- "Islamic (Hijri)"
  code                TEXT UNIQUE NOT NULL,     -- "hijri", "hebrew", "chinese_era", etc.
  
  -- Type
  calendar_type       TEXT NOT NULL,            -- "solar", "lunar", "lunisolar", "regnal"
  
  -- Epoch
  epoch_description   TEXT,                     -- "Migration of Muhammad to Medina, 622 CE"
  epoch_gregorian     TEXT,                     -- "0622-07-16"
  
  -- Conversion
  conversion_formula  TEXT,                     -- Description or reference to conversion algorithm
  conversion_notes    TEXT,                     -- Edge cases, ambiguities
  
  -- Usage
  used_by_regions     TEXT[],                   -- ["Middle East", "North Africa", "South Asia"]
  used_by_periods     TEXT[],                   -- ["Medieval Islamic", "Ottoman"]
  still_in_use        BOOLEAN DEFAULT FALSE,
  
  -- Display
  month_names         JSONB,                    -- [{number, name, days}] if applicable
  special_cycles      TEXT                      -- "12-year animal cycle", "60-year sexagenary cycle"
);
```

### Seed Data

| Name | Code | Type | Epoch | Used By |
|------|------|------|-------|---------|
| Gregorian | `gregorian` | Solar | Christ's birth (1 CE) | Modern global standard |
| Julian | `julian` | Solar | Same but different leap rules | Roman Republic through 1582 CE (some regions later) |
| Islamic (Hijri) | `hijri` | Lunar | 622 CE Hijra | Islamic world |
| Hebrew | `hebrew` | Lunisolar | Creation (3761 BCE) | Jewish communities |
| Chinese (Sexagenary Cycle) | `chinese_era` | Lunisolar | Varies by dynasty | East Asia |
| Roman (AUC) | `auc` | Solar | 753 BCE founding of Rome | Roman Republic and Empire |
| Egyptian Civil | `egyptian` | Solar (365 days, no leap) | Varies | Ancient Egypt |
| Seleucid Era | `seleucid` | Solar | 312 BCE | Hellenistic Near East |
| Regnal Years | `regnal` | Variable | Accession of current ruler | Universal (nearly all monarchies) |
| Olympiad Dating | `olympiad` | 4-year cycles | 776 BCE first Olympics | Ancient Greece |
| Indiction Cycle | `indiction` | 15-year cycles | 312 CE | Byzantine Empire, medieval Europe |
| Buddhist Era | `buddhist` | Solar | 543 BCE (Buddha's death) | Southeast Asia |
| Vikram Samvat | `vikram` | Lunisolar | 57 BCE | South Asia |
| Saka Era | `saka` | Solar | 78 CE | India (official Indian national calendar) |
| Ethiopian | `ethiopian` | Solar | ~8 CE offset from Gregorian | Ethiopia |

### Usage in Pipeline

**Stage 4, Tier 3 resolution (regnal dates):**
```
Input:   "in the third year of Justinian's reign"
Step 1:  LLM resolves "Justinian" → entity with accession date 527 CE
Step 2:  Calendar lookup: regnal → Gregorian
Step 3:  527 + 3 = 529 CE (approximate, as regnal years don't align to Jan 1)
Output:  date_resolved = "529~" (EDTF approximate)
         date_method = "llm_reign_resolution"
```

---

## 5. Era-to-Date Resolution Table

A flat lookup table optimized for Stage 4 Tier 4 date resolution. Avoids the overhead of hierarchical period queries for common era references.

```sql
CREATE TABLE ref_era_date_lookup (
  lookup_id           SERIAL PRIMARY KEY,
  search_term         TEXT NOT NULL,            -- Lowercased, normalized: "late bronze age"
  search_variants     TEXT[],                   -- ["lba", "late bronze age collapse", "lba collapse"]
  
  -- Resolution
  resolved_start      TEXT NOT NULL,            -- EDTF: "-1600"
  resolved_end        TEXT NOT NULL,            -- EDTF: "-1200"
  
  -- Scope (to disambiguate regional usage)
  geographic_scope    TEXT,                     -- "Eastern Mediterranean" or NULL for global
  
  -- Metadata
  confidence          TEXT DEFAULT 'medium-low', -- Tier 4 default
  notes               TEXT,                     -- "Exact dates debated; some scholars use -1150 for end"
  period_id           INTEGER REFERENCES ref_historical_periods(period_id)
);

CREATE INDEX idx_era_lookup_term ON ref_era_date_lookup(search_term);
CREATE INDEX idx_era_lookup_variants ON ref_era_date_lookup USING GIN(search_variants);
```

### Seed Data (examples)

| search_term | variants | start | end | scope |
|-------------|----------|-------|-----|-------|
| late bronze age | lba, bronze age collapse | -1600 | -1200 | Eastern Mediterranean |
| hellenistic period | hellenistic age, hellenistic era | -323 | -31 | Mediterranean |
| roman republic | republican rome, republican period | -509 | -27 | Mediterranean |
| pax romana | roman peace | -27 | 180 | Mediterranean |
| crisis of the third century | 3rd century crisis, military anarchy | 235 | 284 | Roman Empire |
| migration period | völkerwanderung, barbarian invasions | 375 | 568 | Europe |
| viking age | norse expansion | 793 | 1066 | Northern Europe |
| tang dynasty | tang period | 618 | 907 | China |
| abbasid golden age | islamic golden age | 750 | 1258 | Islamic world |
| warring states | warring states period | -476 | -221 | China |
| meiji era | meiji period, meiji restoration | 1868 | 1912 | Japan |

---

## 6. Writing Systems

Referenced by Language entities and Cultural Work entities. Affects NLP processing strategy (Stage 2 model selection).

```sql
CREATE TABLE ref_writing_systems (
  system_id           SERIAL PRIMARY KEY,
  name                TEXT NOT NULL,            -- "Latin alphabet"
  code                TEXT UNIQUE,              -- ISO 15924 code if available: "Latn"
  
  -- Classification
  system_type         TEXT NOT NULL,            -- "alphabet", "abjad", "abugida", "syllabary",
                                               -- "logographic", "mixed", "undeciphered"
  direction           TEXT,                     -- "ltr", "rtl", "ttb", "boustrophedon"
  
  -- History
  origin_date         TEXT,                     -- EDTF approximate
  origin_location     TEXT,
  derived_from        INTEGER REFERENCES ref_writing_systems(system_id),
  
  -- Usage
  languages_using     TEXT[],                   -- Major languages (text, not FK — too many)
  still_in_use        BOOLEAN DEFAULT FALSE,
  
  -- Technical (affects pipeline)
  unicode_block       TEXT,                     -- For NLP model selection
  ocr_support_level   TEXT                      -- "excellent", "good", "poor", "none"
);
```

### Seed Data (examples)

| Name | Type | Direction | Origin | Derived From |
|------|------|-----------|--------|-------------|
| Proto-Sinaitic | Abjad | LTR | ~-1800, Sinai | Egyptian hieroglyphs |
| Phoenician | Abjad | RTL | ~-1050, Byblos | Proto-Sinaitic |
| Greek | Alphabet | LTR | ~-800, Greece | Phoenician |
| Latin | Alphabet | LTR | ~-700, Italy | Greek (via Etruscan) |
| Cyrillic | Alphabet | LTR | 893, Bulgaria | Greek |
| Arabic | Abjad | RTL | ~400, Arabia | Nabataean (from Aramaic) |
| Hebrew | Abjad | RTL | ~-200 | Aramaic |
| Devanagari | Abugida | LTR | ~700, India | Brahmi |
| Chinese characters | Logographic | TTB/LTR | ~-1200, China | Oracle bone script |
| Cuneiform | Mixed (logo-syllabic) | LTR | ~-3400, Mesopotamia | Proto-cuneiform |
| Egyptian hieroglyphs | Mixed (logo-consonantal) | Variable | ~-3200, Egypt | — |
| Linear B | Syllabary | LTR | ~-1450, Crete | Linear A |
| Rongorongo | Undeciphered | Boustrophedon | pre-1860, Easter Island | — |

---

## 7. Religious Tradition Taxonomy

A hierarchical classification for religious movements. Entities of type `religious_movement` reference this for structured categorization beyond the flat `religious_movement_subtype` enum.

```sql
CREATE TABLE ref_religious_traditions (
  tradition_id        SERIAL PRIMARY KEY,
  name                TEXT NOT NULL,
  parent_tradition_id INTEGER REFERENCES ref_religious_traditions(tradition_id),
  depth_level         INTEGER DEFAULT 0,
  
  origin_date         TEXT,                     -- EDTF approximate
  origin_region       TEXT,
  founder             TEXT,                     -- Text name, not FK (may predate Person entities)
  
  tradition_type      TEXT,                     -- "monotheistic", "polytheistic", "nontheistic",
                                               -- "animistic", "philosophical"
  
  -- For display
  sort_order          INTEGER,
  color_hex           TEXT                      -- For religious spread overlay
);
```

### Seed Data (partial hierarchy)

```
Abrahamic Traditions
├── Judaism
│   ├── Second Temple Judaism
│   ├── Rabbinic Judaism
│   ├── Karaite Judaism
│   └── ...
├── Christianity
│   ├── Pre-Nicene Christianity
│   ├── Oriental Orthodoxy
│   ├── Eastern Orthodoxy
│   ├── Roman Catholicism
│   ├── Protestantism
│   │   ├── Lutheranism
│   │   ├── Calvinism/Reformed
│   │   ├── Anglicanism
│   │   └── ...
│   └── Restorationist movements
├── Islam
│   ├── Sunni
│   │   ├── Hanafi
│   │   ├── Maliki
│   │   ├── Shafi'i
│   │   └── Hanbali
│   ├── Shia
│   │   ├── Twelver
│   │   ├── Ismaili
│   │   └── Zaydi
│   ├── Ibadi
│   └── Sufi orders
├── Mandaeism
├── Druze
└── Bahá'í

Dharmic Traditions
├── Hinduism
│   ├── Vaishnavism
│   ├── Shaivism
│   ├── Shaktism
│   └── Smartism
├── Buddhism
│   ├── Theravada
│   ├── Mahayana
│   │   ├── Chan/Zen
│   │   ├── Pure Land
│   │   └── Nichiren
│   └── Vajrayana
├── Jainism
│   ├── Digambara
│   └── Shvetambara
└── Sikhism

East Asian Traditions
├── Confucianism
│   └── Neo-Confucianism
├── Taoism
│   ├── Philosophical Taoism
│   └── Religious Taoism
└── Shinto

Iranian / Zoroastrian
├── Zoroastrianism
├── Manichaeism
├── Mazdakism
└── Zurvanism

Ancient / Reconstructed
├── Mesopotamian religion
├── Egyptian religion
├── Greek religion
├── Roman religion
├── Norse religion
├── Celtic religion
└── ...

Indigenous / Traditional
├── Animistic traditions (regional)
├── Shamanic traditions (regional)
└── Ancestor worship traditions (regional)
```

---

## 8. Unit and Measurement Standards

For normalizing quantitative data across sources that use different measurement systems.

```sql
CREATE TABLE ref_measurement_units (
  unit_id             SERIAL PRIMARY KEY,
  name                TEXT NOT NULL,            -- "Roman mile"
  symbol              TEXT,                     -- "mille passuum"
  
  -- Classification
  measurement_type    TEXT NOT NULL,            -- "distance", "weight", "area", "volume",
                                               -- "currency_weight", "time", "population"
  
  -- Conversion
  si_equivalent       NUMERIC,                 -- In SI base unit (meters, grams, m², liters)
  si_unit             TEXT,                     -- "m", "g", "m2", "L"
  conversion_notes    TEXT,                     -- Variability, uncertainty
  
  -- Historical context
  used_by_region      TEXT,
  used_by_period      TEXT,
  approximate         BOOLEAN DEFAULT TRUE,     -- Most ancient measurements are approximate
  
  sort_order          INTEGER
);
```

### Seed Data (examples)

| Name | Type | SI Equivalent | SI Unit | Region/Period |
|------|------|--------------|---------|---------------|
| Roman mile (mille passuum) | distance | 1480 | m | Roman Empire |
| Greek stadion | distance | 185 | m | Classical Greece (varies) |
| Persian parasang | distance | 5500 | m | Achaemenid Empire |
| Chinese li (traditional) | distance | 500 | m | Imperial China (varied over time) |
| Roman foot (pes) | distance | 0.296 | m | Roman Empire |
| Egyptian royal cubit | distance | 0.524 | m | Ancient Egypt |
| Roman pound (libra) | weight | 327 | g | Roman Empire |
| Greek talent (Attic) | weight | 26200 | g | Classical Greece |
| Mesopotamian shekel | weight | 8.3 | g | Mesopotamia |
| Roman iugerum | area | 2523 | m2 | Roman Empire |
| Chinese mu (traditional) | area | 614 | m2 | Imperial China |
| Roman amphora | volume | 26.2 | L | Roman Empire |
| Modius (Roman grain measure) | volume | 8.7 | L | Roman Empire |
| Artaba (Egyptian) | volume | 39 | L | Ptolemaic Egypt |

---

## 9. Language Families

A hierarchical classification for the `language` entity type. Provides structure beyond the flat `language_family` text field.

```sql
CREATE TABLE ref_language_families (
  family_id           SERIAL PRIMARY KEY,
  name                TEXT NOT NULL,
  parent_family_id    INTEGER REFERENCES ref_language_families(family_id),
  depth_level         INTEGER DEFAULT 0,
  
  proto_language      TEXT,                     -- "Proto-Indo-European"
  estimated_origin    TEXT,                     -- EDTF: "-4500~"
  estimated_homeland  TEXT,                     -- "Pontic-Caspian steppe" (often debated)
  
  living_languages    INTEGER,                  -- Approximate count
  status              TEXT,                     -- "major", "minor", "extinct", "isolate"
  
  sort_order          INTEGER
);
```

### Seed Data (partial)

```
Indo-European
├── Indo-Iranian
│   ├── Indo-Aryan (Sanskrit, Hindi, Bengali, ...)
│   └── Iranian (Persian, Avestan, Kurdish, Pashto, ...)
├── Hellenic (Greek)
├── Italic
│   └── Romance (Latin → French, Spanish, Italian, Portuguese, Romanian, ...)
├── Celtic (Irish, Welsh, Breton, ...)
├── Germanic
│   ├── North Germanic (Old Norse → Norwegian, Swedish, Danish, Icelandic)
│   └── West Germanic (English, German, Dutch, ...)
├── Balto-Slavic
│   ├── Baltic (Lithuanian, Latvian)
│   └── Slavic (Russian, Polish, Czech, Serbian, ...)
├── Armenian
├── Albanian
├── Tocharian (extinct)
└── Anatolian (Hittite, Luwian — extinct)

Afro-Asiatic
├── Semitic (Arabic, Hebrew, Aramaic, Akkadian, Ge'ez, ...)
├── Egyptian (Ancient Egyptian → Coptic)
├── Berber
├── Cushitic (Somali, Oromo, ...)
└── Chadic (Hausa, ...)

Sino-Tibetan
├── Sinitic (Chinese varieties: Mandarin, Cantonese, ...)
└── Tibeto-Burman

Uralic (Finnish, Hungarian, Estonian, ...)
Altaic (controversial: Turkic, Mongolic, Tungusic)
Austronesian (Malay, Tagalog, Maori, Hawaiian, ...)
Niger-Congo (Swahili, Yoruba, Zulu, ...)
Dravidian (Tamil, Telugu, Kannada, Malayalam)
Kartvelian (Georgian)

Isolates: Basque, Sumerian, Elamite, Etruscan
```

---

## 10. Source Type Definitions

Defines what each `reliability_tier` and `document_type` means in practice. Used by the pipeline (Stage 1 metadata assignment) and by reviewers (Stage 8 source evaluation).

```sql
CREATE TABLE ref_source_type_definitions (
  definition_id       SERIAL PRIMARY KEY,
  
  -- Which enum value this defines
  enum_name           TEXT NOT NULL,            -- "reliability_tier" or "document_type"
  enum_value          TEXT NOT NULL,            -- "authoritative", "academic_paper", etc.
  
  -- Definition
  description         TEXT NOT NULL,
  examples            TEXT[],
  
  -- Pipeline behavior
  default_confidence  TEXT,                     -- Default confidence when only this tier available
  requires_corroboration BOOLEAN DEFAULT FALSE, -- Should be cross-checked against other sources
  weight_in_scoring   NUMERIC DEFAULT 1.0,      -- Multiplier in entity resolution scoring
  
  -- Review guidance
  reviewer_notes      TEXT                      -- What reviewers should watch for with this type
);
```

### Seed Data

**reliability_tier definitions:**

| Value | Description | Examples | Default Confidence | Weight |
|-------|-------------|----------|-------------------|--------|
| `authoritative` | Primary sources written during the events, peer-reviewed archaeological reports, inscriptions, coins | Res Gestae Divi Augusti, cuneiform tablets, excavation reports from accredited institutions | high | 1.5 |
| `scholarly` | Academic secondary sources from university presses, peer-reviewed journals | Journal of Roman Studies articles, Cambridge Ancient History volumes, monographs | high | 1.3 |
| `reference` | Curated reference databases and well-maintained encyclopedias | Pleiades, Wikidata, Encyclopaedia Britannica, Princeton Encyclopedia of Classical Sites | medium | 1.0 |
| `user_contributed` | Community-edited sources, blogs, non-peer-reviewed publications | Wikipedia, history blogs, student papers, forum posts | low | 0.5 |

**document_type definitions:**

| Value | Description | Examples | Review Notes |
|-------|-------------|----------|-------------|
| `academic_paper` | Peer-reviewed journal article or conference paper | JRS, AJA, Past & Present | Check publication date — older scholarship may be superseded |
| `encyclopedia` | Entry in a reference encyclopedia | Oxford Classical Dictionary, EI2 | Generally reliable but may be outdated |
| `primary_source` | Historical document from the period described | Herodotus, Thucydides, Chinese dynastic histories | Consider author bias, contemporaneity, genre conventions |
| `database_export` | Structured data from a curated scholarly database | Pleiades JSON, DARE export, Pelagios data | High reliability for coordinates; may lack context |
| `web_article` | Online article from a non-academic source | Wikipedia, Livius.org, World History Encyclopedia | Cross-reference; useful for discovery but needs verification |

---

## Appendix: How Reference Tables Connect to the Pipeline

```
Stage 1 (Ingestion)
  └── ref_source_type_definitions → assigns reliability_tier and document_type

Stage 3 (Geocoding)
  └── ref_geographic_regions → batch assignment, regional disambiguation context

Stage 4 (Temporal Extraction)
  ├── ref_era_date_lookup → Tier 4 era-relative date resolution
  ├── ref_historical_periods → fallback for complex period references
  └── ref_calendar_systems → converting non-Gregorian dates

Stage 5 (Entity Resolution)
  └── ref_geographic_regions → constraining spatial matching to same region

Stage 6 (LLM Synthesis)
  ├── ref_historical_periods → era_label for entity context
  └── ref_religious_traditions → structured religion classification

Stage 8 (Human Review)
  ├── ref_historiographical_schools → tagging interpretive bias
  ├── ref_measurement_units → normalizing quantitative claims
  └── ref_source_type_definitions → evaluating source quality

Frontend
  ├── ref_historical_periods → timeline era labels, period navigation
  ├── ref_geographic_regions → region filtering, map zoom targets
  ├── ref_religious_traditions → religious spread overlay legend
  └── ref_language_families → language distribution overlay
```
