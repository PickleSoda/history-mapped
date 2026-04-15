"""Wikidata type configs — maps our 30 entity types to Wikidata classes + properties.

Each config defines:
- wikidata_classes: QIDs to use in SPARQL (instance_of / subclass_of)
- property_queries: Wikidata property IDs to fetch for relationship extraction
- field_map: how to map Wikidata/Wikipedia fields to our entity attributes JSONB
"""

from __future__ import annotations

# ── Wikidata property reference ──────────────────────────────────────────────
# P17   = country
# P31   = instance of
# P36   = capital
# P131  = located in admin territory
# P150  = contains admin territory
# P155  = follows (predecessor)
# P156  = followed by (successor)
# P279  = subclass of
# P361  = part of
# P527  = has part
# P571  = inception
# P576  = dissolved/abolished
# P580  = start time
# P582  = end time
# P625  = coordinate location
# P1376 = capital of
# P6   = head of government
# P35  = head of state
# P122 = basic form of government
# P37  = official language
# P38  = currency
# P194 = legislative body
# P1082 = population
# P2046 = area
# P22  = father
# P25  = mother
# P26  = spouse
# P40  = child
# P569 = date of birth
# P570 = date of death
# P19  = place of birth
# P20  = place of death
# P39  = position held
# P106 = occupation
# P27  = country of citizenship
# P607 = conflict (participated in)
# P710 = participant
# P1344 = participant of
# P585 = point in time
# P793 = significant event
# P828 = has cause
# P1542 = has effect
# P140 = religion
# P1376 = capital of

WIKIDATA_TYPE_CONFIGS: dict[str, dict] = {
    # ═══════════════════════════════════════════════════════════════════════════
    # POLITY group
    # ═══════════════════════════════════════════════════════════════════════════
    "political_entity": {
        "wikidata_classes": [
            "Q3624078",   # sovereign state
            "Q48349",     # empire
            "Q133442",    # city-state
            "Q3024240",   # historical country
            "Q28171280",  # ancient civilization
            "Q208281",    # polity (broad — catches Hittites, Mycenae, etc.)
            "Q1063239",   # polity (alternate QID used by Ugarit, etc.)
            "Q12097",     # tribal confederation (Sea Peoples groupings)
            "Q105543609", # ancient Levantine state (Ugarit, Ebla, etc.)
            "Q6256",      # country (modern + historical both)
            "Q7275",      # state (political entity)
            "Q28513",     # kingdom (ancient kingdoms like Ugarit, Mitanni)
            "Q331644",    # khanate / khaganate (Mongol successor states)
            "Q170770",    # principality (medieval European states)
            "Q79007",     # caliphate (Umayyad, Abbasid, etc.)
            "Q170156",    # sultanate (Mamluk, Delhi, etc.)
            "Q164142",    # feudal state
            "Q3241965",   # tributary state (Ugarit, vassal kingdoms)
            "Q208164",    # vassal state
            "Q1763527",   # confederation / confederacy
            "Q8432",      # civilization (Mycenaean, Indus, etc.)
        ],
        "property_queries": [
            "P36",   # capital
            "P122",  # basic form of government
            "P37",   # official language
            "P38",   # currency
            "P155",  # follows
            "P156",  # followed by
            "P150",  # contains admin territory
            "P140",  # religion
        ],
        "field_map": {
            "P122": "government_type",
            "P36": "capital_history",
            "P37": "official_languages",
            "P38": "currency",
            "P140": "official_religions",
        },
    },

    "dynasty": {
        "wikidata_classes": [
            "Q164950",  # dynasty
        ],
        "property_queries": [
            "P17",   # country
            "P155",  # follows
            "P156",  # followed by
            "P112",  # founded by
        ],
        "field_map": {},
    },

    "person": {
        "wikidata_classes": [
            "Q5",      # human
        ],
        "property_queries": [
            "P19",   # place of birth
            "P20",   # place of death
            "P22",   # father
            "P25",   # mother
            "P26",   # spouse
            "P39",   # position held
            "P106",  # occupation
            "P27",   # country of citizenship
            "P569",  # date of birth
            "P570",  # date of death
            "P607",  # conflict
        ],
        "field_map": {
            "P19": "birth_place_id",
            "P20": "death_place_id",
            "P569": "birth_date",
            "P570": "death_date",
            "P106": "roles",
        },
        # Person queries need heavy filtering — add SPARQL-level constraints
        "extra_sparql_filter": """
          ?item wdt:P106/wdt:P279* wd:Q82955 .  # occupation: politician (broad)
          # OR: wdt:P39 for "position held" to get rulers, generals, etc.
        """,
    },

    "military_unit": {
        "wikidata_classes": [
            "Q176799",   # military unit
            "Q781132",   # military organization
            "Q4508",     # navy
            "Q7270",     # army
            "Q209715",   # military alliance
            "Q329737",   # legions / military formation
        ],
        "property_queries": [
            "P17",   # country
            "P571",  # inception
            "P576",  # dissolved
            "P607",  # conflict
            "P361",  # part of
        ],
        "field_map": {},
    },

    "diplomatic_relationship": {
        "wikidata_classes": [
            "Q4162051",  # diplomatic relations (was Q625298=peace treaty!)
            "Q160016",   # league (Delian League, Hanseatic League, etc.)
            "Q625994",   # alliance (political/military alliances)
        ],
        "property_queries": [
            "P710",  # participant
        ],
        "field_map": {},
    },

    "social_class": {
        "wikidata_classes": [
            "Q187588",   # social class
        ],
        "property_queries": [
            "P17", "P361",
        ],
        "field_map": {},
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # PLACE group
    # ═══════════════════════════════════════════════════════════════════════════
    "city": {
        "wikidata_classes": [
            "Q515",       # city
            "Q1549591",   # big city
            "Q15661340",  # ancient city (was Q262166=municipality in Germany!)
            "Q40364446",  # historic city (was Q2264924=port city!)
            "Q148837",    # polis (Greek city-states)
            "Q486972",    # human settlement (very common Wikidata class)
            "Q3957",      # town (smaller settlements)
            "Q532",       # village
        ],
        "property_queries": [
            "P17",    # country
            "P1082",  # population
            "P131",   # located in admin territory
            "P1376",  # capital of
            "P571",   # inception
        ],
        "field_map": {
            "P1082": "population_estimates",
            "P17": "political_control",
        },
    },

    "infrastructure_monument": {
        "wikidata_classes": [
            "Q811979",    # architectural structure
            "Q4989906",   # monument (was Q12518=tower!)
            "Q839954",    # archaeological site
            "Q57831",     # fortress (was Q35127=website!)
            "Q44539",     # temple (was Q16970=church building!)
            "Q2977",      # cathedral (was Q34627=synagogue!)
            "Q32815",     # mosque
            "Q23413",     # castle (medieval fortifications)
            "Q16560",     # palace (royal residences)
            "Q751876",    # citadel / acropolis
            "Q12518",     # tower (watchtowers, bell towers, etc.)
            "Q34627",     # synagogue
        ],
        "property_queries": [
            "P131",   # located in
            "P17",    # country
            "P84",    # architect
            "P186",   # material used
            "P571",   # inception
            "P576",   # dissolution
            "P2048",  # height
        ],
        "field_map": {
            "P84": "architect_builder",
            "P186": "materials",
        },
    },

    "extraction_infra": {
        "wikidata_classes": [
            "Q820477",   # mine
            "Q188040",   # quarry (was Q188507=apartment!)
        ],
        "property_queries": [
            "P17", "P131", "P571",
        ],
        "field_map": {},
    },

    "educational_institution": {
        "wikidata_classes": [
            "Q3918",    # university
            "Q7075",    # library
            "Q3914",    # school
        ],
        "property_queries": [
            "P17", "P131", "P571", "P112",  # founded by
        ],
        "field_map": {},
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # EVENT group
    # ═══════════════════════════════════════════════════════════════════════════
    "event_war": {
        "wikidata_classes": [
            "Q198",       # war
            "Q831663",    # military campaign
            "Q3042783",   # societal collapse (e.g., Bronze Age Collapse)
            "Q13418847",  # historical event (broad catch-all for major events)
            "Q104212151", # series of wars (used by Crusades)
            "Q13573188",  # holy war (used by Crusades)
            "Q645883",    # military operation
            "Q188055",    # siege (also in event_battle but needed as fallback here)
            "Q180684",    # conflict (broader catch-all)
            "Q891723",    # massacre
            "Q1348006",   # genocide
            "Q350604",    # armed conflict
        ],
        "property_queries": [
            "P710",   # participant
            "P726",   # candidate (commander)
            "P828",   # has cause
            "P1542",  # has effect
            "P585",   # point in time
        ],
        "field_map": {},
    },

    "event_battle": {
        "wikidata_classes": [
            "Q178561",  # battle
            "Q188055",  # siege
            "Q1261499", # naval battle
        ],
        "property_queries": [
            "P710",   # participant
            "P276",   # location
            "P361",   # part of (war)
            "P585",   # point in time
            "P1350",  # number of participants
        ],
        "field_map": {},
    },

    "event_treaty": {
        "wikidata_classes": [
            "Q131569",   # treaty
            "Q625298",   # peace treaty (was Q93288=contract!)
        ],
        "property_queries": [
            "P710",   # participant
            "P276",   # location
            "P585",   # point in time
        ],
        "field_map": {},
    },

    "event_rebellion": {
        "wikidata_classes": [
            "Q124734",   # rebellion (was Q1125818=Raffaella Carrà single!)
            "Q10931",    # revolution
            "Q45382",    # coup d'état
        ],
        "property_queries": [
            "P17", "P710", "P585", "P828", "P1542",
        ],
        "field_map": {},
    },

    "event_natural_disaster": {
        "wikidata_classes": [
            "Q8065",      # natural disaster
            "Q7944",      # earthquake
            "Q7692360",   # volcanic eruption (was Q8070=tsunami!)
            "Q8070",      # tsunami (separate class, not volcanic eruption)
            "Q168247",    # famine
            "Q7257",      # flood
            "Q869569",    # drought
        ],
        "property_queries": [
            "P276", "P585", "P1120",  # number of deaths
        ],
        "field_map": {},
    },

    "event_tech_adoption": {
        # No direct Wikidata class — derived from technology + event intersection
        "wikidata_classes": [
            "Q762702",   # technological change (was Q3505845=abstract 'state'!)
        ],
        "property_queries": [],
        "field_map": {},
    },

    "event_legal_reform": {
        "wikidata_classes": [
            "Q49371",    # legislation (was Q4116455=Battle of Ta'izz!)
            "Q820655",   # statute / legislative act
            "Q4882028",  # edict / decree
            "Q36649",    # charter (Magna Carta etc.)
        ],
        "property_queries": [
            "P17", "P571", "P585",
        ],
        "field_map": {},
    },

    "migration": {
        "wikidata_classes": [
            "Q177626",  # human migration
            "Q33829",   # ethnic group (Sea Peoples, Dorians, etc. — migrating peoples)
            "Q41710",   # people (ethnic sense — catches "Philistines", "Mycenaeans")
            "Q179643",  # tribe
            "Q4204501", # historical ethnic group (Sea Peoples on Wikidata)
        ],
        "property_queries": [
            "P276", "P585",
        ],
        "field_map": {},
    },

    "epidemic_disease": {
        "wikidata_classes": [
            "Q44512",    # epidemic
            "Q12184",    # pandemic
            "Q3241045",  # disease outbreak (used by Black Death)
        ],
        "property_queries": [
            "P276", "P585", "P1120",  # number of deaths
            "P828",  # has cause
        ],
        "field_map": {},
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # ECONOMY group
    # ═══════════════════════════════════════════════════════════════════════════
    "trade_route": {
        "wikidata_classes": [
            "Q405155",   # trade route (was Q123397=The Republic by Plato!)
            "Q445741",   # historic road
        ],
        "property_queries": [
            "P276", "P571", "P576",
        ],
        "field_map": {},
    },

    "natural_resource": {
        "wikidata_classes": [
            "Q188460",   # natural resource
        ],
        "property_queries": [],
        "field_map": {},
    },

    "currency_monetary_system": {
        "wikidata_classes": [
            "Q8142",      # currency
            "Q28783456",  # obsolete/historical currency (was Q131755=bipolar disorder!)
        ],
        "property_queries": [
            "P17", "P571", "P576",
        ],
        "field_map": {},
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # CULTURE group
    # ═══════════════════════════════════════════════════════════════════════════
    "cultural_work": {
        "wikidata_classes": [
            "Q7725634",  # literary work
            "Q838948",   # work of art
            "Q11424",    # film (historical documentaries, epics)
            "Q860861",   # sculpture
            "Q3305213",  # painting
        ],
        "property_queries": [
            "P50",   # author
            "P407",  # language of work
            "P571",  # inception
            "P136",  # genre
        ],
        "field_map": {},
    },

    "intellectual_movement": {
        "wikidata_classes": [
            "Q2198855",   # cultural movement
            "Q2915955",   # philosophical movement (was Q3558693=Paris street!)
            "Q9332",      # art movement (Renaissance, Baroque, etc.)
            "Q171558",    # ideology (political/social ideologies)
            "Q49773",     # social movement
        ],
        "property_queries": [],
        "field_map": {},
    },

    "archaeological_culture": {
        "wikidata_classes": [
            "Q465299",  # archaeological culture
        ],
        "property_queries": [],
        "field_map": {},
    },

    "language": {
        "wikidata_classes": [
            "Q34770",    # language
            "Q45762",    # dead language (was Q33215=constructed language!)
            "Q436240",   # ancient language
        ],
        "property_queries": [
            "P282",   # writing system
            "P1098",  # number of speakers
            "P361",   # part of (language family)
        ],
        "field_map": {},
    },

    "religious_text": {
        "wikidata_classes": [
            "Q179461",   # religious text (also covers "sacred text" alias)
        ],
        "property_queries": [
            "P50", "P407", "P571",
        ],
        "field_map": {},
    },

    "legal_code": {
        "wikidata_classes": [
            "Q922203",  # legal code
        ],
        "property_queries": [
            "P17", "P571", "P50",
        ],
        "field_map": {},
    },

    "religious_movement": {
        "wikidata_classes": [
            "Q9174",     # religion
            "Q13414953", # religious denomination
        ],
        "property_queries": [
            "P112",  # founded by
            "P155",  # follows
            "P156",  # followed by
        ],
        "field_map": {},
    },

    "technology": {
        "wikidata_classes": [
            "Q11019",    # machine
            "Q28877",    # goods (broad)
            "Q2095",     # food (for agricultural tech)
        ],
        "property_queries": [
            "P61",   # discoverer/inventor
            "P571",  # inception
        ],
        "field_map": {},
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# REFERENCE TABLE QID CONFIGS
# ═══════════════════════════════════════════════════════════════════════════════
#
# Items matching these classes are NOT imported as regular entities —
# they belong to curated reference tables (ref_historical_periods,
# ref_geographic_regions, etc.). The pipeline classifies them so they
# don't end up as "untyped" and writes them to a separate JSONL file
# for future reference-table seeding.
#
# Keys here are ref_table names (matching the DB migration).
# Each entry has:
#   - wikidata_classes: list of QIDs that identify this kind of ref item.
#   - ref_table: target reference table name.
# ═══════════════════════════════════════════════════════════════════════════════

WIKIDATA_REF_CONFIGS: dict[str, dict] = {
    # ── Historical period / era / age ────────────────────────────────────────
    "ref_historical_period": {
        "ref_table": "ref_historical_periods",
        "wikidata_classes": [
            "Q15401633",   # historical period (e.g., Early Bronze Age)
            "Q15401699",   # archaeological age (e.g., Stone Age)
            "Q754897",     # geological epoch (e.g., Holocene)
            "Q312468",     # geological age
            "Q200325",     # prehistoric age
            "Q26907166",   # period of human history
            "Q115857096",  # historical period of a region
            "Q11514315",   # historical period
            "Q186081",     # time interval
            "Q6428674",    # geological period
            "Q3516404",    # series of events (periodization concept)
            "Q575",        # historical era (broad era like "medieval")
            "Q11862829",   # academic discipline era (Iron Age, etc.)
        ],
    },

    # ── Geographic region (conceptual / fuzzy — not a city or country) ───────
    "ref_geographic_region": {
        "ref_table": "ref_geographic_regions",
        "wikidata_classes": [
            "Q82794",      # geographic region
            "Q35145263",   # historical region
            "Q3301962",    # geographical feature (broad)
            "Q137186904",  # region concept
            "Q15642541",   # human-geographic territorial entity
            "Q1620908",    # subcontinent
            "Q5107",       # continent
            "Q4835091",    # geographic area
            "Q1496967",    # territorial entity
            "Q58784",      # macroregion
        ],
    },

    # ── Bodies of water (seas, oceans, lakes, gulfs) ─────────────────────────
    "ref_body_of_water": {
        "ref_table": "ref_geographic_regions",   # treated as geographic features
        "wikidata_classes": [
            "Q165",        # sea (e.g., Libyan Sea, Aegean Sea)
            "Q166620",     # marginal sea
            "Q204894",     # gulf / bay
            "Q9430",       # ocean
            "Q23397",      # lake
            "Q12284",      # strait
            "Q37901",      # body of water (broad)
            "Q355304",     # watercourse (river etc.)
            "Q4022",       # river
        ],
    },

    # ── Calendar systems ─────────────────────────────────────────────────────
    "ref_calendar_system": {
        "ref_table": "ref_calendar_systems",
        "wikidata_classes": [
            "Q12132",      # calendar system
        ],
    },

    # ── Writing systems ──────────────────────────────────────────────────────
    "ref_writing_system": {
        "ref_table": "ref_writing_systems",
        "wikidata_classes": [
            "Q8192",       # writing system
            "Q506418",     # script (writing system)
        ],
    },

    # ── Measurement units ────────────────────────────────────────────────────
    "ref_measurement_unit": {
        "ref_table": "ref_measurement_units",
        "wikidata_classes": [
            "Q47574",      # unit of measurement
            "Q3647172",    # monetary unit
        ],
    },
}
