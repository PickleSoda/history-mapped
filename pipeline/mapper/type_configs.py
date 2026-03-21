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
            "Q123480",    # empire (historical)
            "Q133311",    # city-state
            "Q3024240",   # historical country
            "Q28171280",  # ancient civilization
            "Q839954",    # archaeological site → only if subclass leads here
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
            "Q625298",   # diplomatic relation
            "Q131569",   # treaty
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
            "Q515",      # city
            "Q1549591",  # big city
            "Q262166",   # ancient city
            "Q2264924",  # historical city
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
            "Q811979",   # architectural structure
            "Q12518",    # monument
            "Q839954",   # archaeological site
            "Q35127",    # fortress
            "Q16970",    # temple
            "Q34627",    # cathedral
            "Q32815",    # mosque
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
            "Q188507",   # quarry
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
            "Q198",     # war
            "Q831663",  # military campaign
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
            "Q131569",  # treaty
            "Q93288",   # peace treaty
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
            "Q1125818",  # rebellion
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
            "Q8065",    # natural disaster
            "Q7944",    # earthquake
            "Q8070",    # volcanic eruption
        ],
        "property_queries": [
            "P276", "P585", "P1120",  # number of deaths
        ],
        "field_map": {},
    },

    "event_tech_adoption": {
        # No direct Wikidata class — derived from technology + event intersection
        "wikidata_classes": [
            "Q3505845",  # technological change
        ],
        "property_queries": [],
        "field_map": {},
    },

    "event_legal_reform": {
        "wikidata_classes": [
            "Q4116455",  # legislation
            "Q820655",   # legislative act
        ],
        "property_queries": [
            "P17", "P571", "P585",
        ],
        "field_map": {},
    },

    "migration": {
        "wikidata_classes": [
            "Q177626",  # human migration
        ],
        "property_queries": [
            "P276", "P585",
        ],
        "field_map": {},
    },

    "epidemic_disease": {
        "wikidata_classes": [
            "Q44512",   # epidemic
            "Q12184",   # pandemic
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
            "Q123397",   # trade route
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
            "Q8142",     # currency
            "Q131755",   # historical currency
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
            "Q2198855",  # cultural movement
            "Q3558693",  # philosophical movement
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
            "Q34770",   # language
            "Q33215",   # dead language
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
            "Q179461",   # religious text
            "Q3744559",  # sacred text
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
