"""entity_type → Wikidata class rules (C2b).

A QID's *kinds* are the root classes below that its P31 values reach through
P279* (subclass of). For each entity_type the table names the kinds that
confirm it (``allowed``) and the kinds that contradict it (``contradict``):

* ``ok``            — some P31 reaches an allowed kind;
* ``contradiction`` — none does, and some P31 reaches a contradicting kind
                      (a person row whose QID is a ship, a battle row whose
                      QID is a city);
* ``unmatched``     — none does and nothing contradicts (an unusual class);
* ``unknown``       — the QID has no P31.

``allowed=None`` means the type is too broad to confirm (natural resources,
technologies, ideas): only a contradiction counts. Every root QID's label was
checked against Wikidata when the table was written; see the comments.
"""
from __future__ import annotations

from typing import Iterable

HUMAN = {"Q5"}  # human
PERSONLIKE = {
    "Q95074",     # character
    "Q15632617",  # fictional human
    "Q4271324",   # mythical character
    "Q178885",    # deity
    "Q20643955",  # human biblical figure
    "Q21070568",  # human whose existence is disputed
    "Q22988604",  # mythological Greek character
    "Q13002315",  # legendary figure
    "Q6949213",   # mythological king
    "Q3658341",   # literary character
}
BATTLE = {
    "Q178561",   # battle
    "Q188055",   # siege
    "Q645883",   # military operation
    "Q1261499",  # naval battle
    "Q831663",   # military campaign
    "Q3199915",  # massacre
}
WAR = {
    "Q198",      # war
    "Q8465",     # civil war
    "Q350604",   # armed conflict
    "Q103495",   # world war
    "Q467011",   # invasion
    "Q180684",   # conflict
}
REBELLION = {
    "Q124734",   # rebellion
    "Q10931",    # revolution
    "Q45382",    # coup d'état
}
OCCURRENCE = {
    "Q1190554",  # occurrence
    "Q13418847",  # historical event
    "Q1656682",  # planned event
}
TREATY = {
    "Q131569",   # treaty
    "Q625298",   # peace treaty
    "Q321839",   # agreement
    "Q93288",    # contract
}
DOCUMENT = {
    "Q49848",    # document
    "Q7748",     # law
    "Q820655",   # statute
    "Q1284645",  # edict
    "Q2571972",  # decree
}
DISASTER = {
    "Q8065",     # natural disaster
    "Q3839081",  # disaster
    "Q7944",     # earthquake
    "Q8068",     # flood
    "Q168247",   # famine
    "Q8070",     # tsunami
    "Q7692360",  # volcanic eruption
}
DISEASE = {
    "Q12136",    # disease
    "Q18123741",  # infectious disease
    "Q3241045",  # disease outbreak
    "Q44512",    # epidemic
    "Q12184",    # pandemic
    "Q133780",   # plague
}
POLITY = {
    "Q7275",     # state
    "Q6256",     # country
    "Q3024240",  # historical country
    "Q1048835",  # political territorial entity
    "Q56061",    # administrative territorial entity
    "Q48349",    # empire
    "Q417175",   # kingdom
    "Q1250464",  # realm
    "Q7270",     # republic
    "Q3624078",  # sovereign state
    "Q133442",   # city-state
    "Q170156",   # confederation
    "Q1371288",  # vassal state
    "Q3241965",  # tributary state
    "Q164142",   # protectorate
    "Q331644",   # khanate
    "Q131401",   # caliphate
    "Q12759805",  # sultanate
    "Q208500",   # principality
    "Q154547",   # duchy
    "Q133156",   # colony
    "Q1063239",  # polity
    "Q1642488",  # chiefdom
    "Q15642541",  # human-geographic territorial entity
}
PEOPLE = {
    "Q133311",   # tribe
    "Q41710",    # ethnic group
    "Q2472587",  # people
    "Q16334295",  # group of humans
    "Q211503",   # clan
}
REGION = {
    "Q1620908",  # historical region
    "Q82794",    # region
}
CIVILIZATION = {
    "Q28171280",  # ancient civilization
    "Q8432",     # civilization
    "Q465299",   # archaeological culture
    "Q11514315",  # historical period
}
DYNASTY = {
    "Q164950",   # dynasty
    "Q13417114",  # noble family
    "Q1156073",  # royal house
    "Q8436",     # family
}
SETTLEMENT = {
    "Q486972",   # human settlement
    "Q515",      # city
    "Q15661340",  # ancient city
}
PLACE = {
    "Q2221906",  # geographic location
    "Q27096213",  # geographic entity
    "Q618123",   # geographical feature
    "Q839954",   # archaeological site
}
STRUCTURE = {
    "Q811979",   # built structure
    "Q41176",    # building
    "Q4989906",  # monument
    "Q57821",    # fortification
    "Q24398318",  # religious building
    "Q1497364",  # building complex
    "Q2319498",  # architectural landmark
}
EXTRACTION = {
    "Q820477",   # mine
    "Q188040",   # quarry
    "Q131596",   # farm
}
INSTITUTION = {
    "Q2385804",  # educational institution
    "Q3918",     # university
    "Q7075",     # library
    "Q33506",    # museum
}
ORG = {"Q43229"}  # organization
MILITARY = {
    "Q176799",   # military unit
    "Q781132",   # military branch
    "Q8473",     # military
    "Q772547",   # armed forces
}
ALLIANCE = {
    "Q1127126",  # military alliance
    "Q878249",   # alliance
    "Q773711",   # symmachia
}
ROUTE = {
    "Q405155",   # trade route
    "Q1574938",  # trade route
    "Q34442",    # road
    "Q4022",     # river
    "Q15324",    # body of water
}
CURRENCY = {
    "Q8142",     # currency
    "Q41207",    # coin
}
WORK = {
    "Q386724",   # work
    "Q17537576",  # creative work
    "Q838948",   # work of art
    "Q47461344",  # written work
    "Q7725634",  # literary work
    "Q571",      # book
}
RELTEXT = {"Q179461"}  # religious text
MOVEMENT = {
    "Q2198855",  # cultural movement
    "Q49773",    # social movement
    "Q968159",   # art movement
    "Q1387659",  # school of thought
    "Q7257",     # ideology
}
RELIGION = {
    "Q9174",     # religion
    "Q13414953",  # religious denomination
    "Q1530022",  # religious organization
}
LANGUAGE = {
    "Q34770",    # language
    "Q25295",    # language family
    "Q17376908",  # languoid
    "Q20162172",  # human language
    "Q8192",     # writing system
}
TECH = {
    "Q11016",    # technology
    "Q39546",    # physical tool
    "Q16686448",  # artificial object
    "Q2695280",  # technique
    "Q2424752",  # product
}
SOCIAL = {"Q187588", "Q12737077"}  # social class, occupation
PROCESS = {
    "Q3249551",  # process
    "Q900406",   # reform
    "Q177626",   # human migration
    "Q2401485",  # expedition
    "Q61509",    # travel
    "Q6502154",  # exploration
}
MEDIA = {
    "Q11424",    # film
    "Q482994",   # album
    "Q134556",   # single
    "Q5398426",  # television series
    "Q7889",     # video game
    "Q7366",     # song
    "Q215380",   # musical group
    "Q847017",   # sports club
}
TAXON = {"Q16521"}  # taxon
SHIP = {"Q11446"}  # ship
# Never the subject of an atlas row, whatever its type: matched on the DIRECT
# P31 only (their subclass trees are noisy).
JUNK = {
    "Q4167410": "disambiguation page",
    "Q13406463": "list article",
    "Q4167836": "category",
    "Q11266439": "template",
    "Q17442446": "Wikimedia internal item",
    "Q202444": "given name",
    "Q12308941": "male given name",
    "Q11879590": "female given name",
    "Q3409032": "unisex given name",
    "Q101352": "family name",
    "Q3863": "asteroid",
}
DISAMBIGUATION = "Q4167410"

ARTICLE = {
    "Q191067",   # article
    "Q13442814",  # scholarly article
    "Q17329259",  # encyclopedia article
    "Q13433827",  # encyclopedia article
    "Q1580166",  # dictionary entry
    "Q1002697",  # periodical
}
FICTION = {
    "Q14897293",  # fictional entity
    "Q1145276",  # fictional country
}
_ANTI_EVENT = HUMAN | PERSONLIKE | SETTLEMENT | POLITY | STRUCTURE | MEDIA | TAXON | SHIP | DYNASTY | LANGUAGE | PEOPLE
_ANTI_PLACE = HUMAN | PERSONLIKE | BATTLE | WAR | REBELLION | TREATY | MEDIA | TAXON | SHIP | DISEASE | LANGUAGE

# entity_type -> (allowed kinds | None, contradicting kinds)
TYPE_RULES: dict[str, tuple[set[str] | None, set[str]]] = {
    "person": (HUMAN | PERSONLIKE, set()),  # contradiction = any other kind (see classify)
    "dynasty": (DYNASTY | PEOPLE | POLITY | CIVILIZATION,
                HUMAN | BATTLE | WAR | SETTLEMENT | STRUCTURE | WORK | MEDIA | TAXON | SHIP),
    "political_entity": (POLITY | PEOPLE | REGION | CIVILIZATION | ORG | DYNASTY | ALLIANCE,
                         HUMAN | PERSONLIKE | BATTLE | WAR | REBELLION | TREATY | WORK | MEDIA
                         | TAXON | SHIP | LANGUAGE | TECH | DISEASE),
    "military_unit": (MILITARY | ORG | PEOPLE | ALLIANCE,
                      HUMAN | PERSONLIKE | BATTLE | WAR | SETTLEMENT | STRUCTURE | WORK | MEDIA | TAXON | LANGUAGE),
    "diplomatic_relationship": (ALLIANCE | TREATY | ORG | POLITY | OCCURRENCE | DOCUMENT,
                                HUMAN | SETTLEMENT | STRUCTURE | MEDIA | TAXON | LANGUAGE),
    "social_class": (SOCIAL | PEOPLE | ORG,
                     HUMAN | BATTLE | WAR | SETTLEMENT | STRUCTURE | MEDIA | TAXON),
    "city": (SETTLEMENT | PLACE | POLITY | STRUCTURE | REGION, _ANTI_PLACE | WORK | PEOPLE),
    "infrastructure_monument": (STRUCTURE | PLACE | SETTLEMENT | INSTITUTION | ROUTE, _ANTI_PLACE),
    "extraction_infra": (EXTRACTION | STRUCTURE | PLACE | SETTLEMENT, _ANTI_PLACE),
    "educational_institution": (INSTITUTION | ORG | STRUCTURE | PLACE, _ANTI_PLACE),
    "event_battle": (BATTLE | WAR | REBELLION, _ANTI_EVENT | WORK),
    "event_war": (WAR | BATTLE | REBELLION, _ANTI_EVENT | WORK),
    "event_rebellion": (REBELLION | WAR | BATTLE | OCCURRENCE, _ANTI_EVENT | WORK),
    "event_treaty": (TREATY | DOCUMENT | ALLIANCE | OCCURRENCE | WORK, _ANTI_EVENT),
    "event_natural_disaster": (DISASTER | DISEASE | OCCURRENCE, _ANTI_EVENT | WORK),
    "event_tech_adoption": (OCCURRENCE | TECH | PROCESS, HUMAN | PERSONLIKE | SETTLEMENT | POLITY | MEDIA | DYNASTY),
    "event_legal_reform": (OCCURRENCE | DOCUMENT | TREATY | PROCESS | WORK, _ANTI_EVENT),
    "migration": (OCCURRENCE | PROCESS | PEOPLE | WAR,
                  HUMAN | PERSONLIKE | SETTLEMENT | STRUCTURE | MEDIA | DYNASTY),
    "epidemic_disease": (DISEASE | DISASTER | OCCURRENCE | TAXON,
                         HUMAN | PERSONLIKE | SETTLEMENT | POLITY | STRUCTURE | MEDIA | DYNASTY),
    "trade_route": (ROUTE | PLACE | STRUCTURE, HUMAN | PERSONLIKE | BATTLE | WAR | MEDIA | TAXON | DYNASTY),
    "natural_resource": (None, HUMAN | PERSONLIKE | BATTLE | WAR | REBELLION | TREATY | SETTLEMENT
                         | POLITY | DYNASTY | MEDIA),
    "currency_monetary_system": (CURRENCY | TECH, HUMAN | BATTLE | WAR | SETTLEMENT | POLITY | DYNASTY | MEDIA | TAXON),
    "cultural_work": (WORK | STRUCTURE | RELTEXT | DOCUMENT | TECH,
                      HUMAN | PERSONLIKE | BATTLE | WAR | SETTLEMENT | POLITY | DYNASTY | TAXON),
    "intellectual_movement": (None, HUMAN | BATTLE | WAR | SETTLEMENT | STRUCTURE | POLITY | DYNASTY
                              | MEDIA | TAXON | SHIP),
    "archaeological_culture": (CIVILIZATION | PEOPLE | PLACE | POLITY, HUMAN | BATTLE | WAR | MEDIA | TAXON),
    "language": (LANGUAGE, HUMAN | BATTLE | WAR | SETTLEMENT | STRUCTURE | POLITY | MEDIA | TAXON | DYNASTY | PEOPLE),
    "religious_text": (RELTEXT | WORK | DOCUMENT,
                       HUMAN | BATTLE | WAR | SETTLEMENT | POLITY | DYNASTY | MEDIA | TAXON),
    "legal_code": (DOCUMENT | TREATY | WORK | OCCURRENCE | PROCESS,
                   HUMAN | BATTLE | WAR | SETTLEMENT | STRUCTURE | DYNASTY | MEDIA | TAXON),
    "religious_movement": (RELIGION | MOVEMENT | ORG | PEOPLE,
                           HUMAN | BATTLE | WAR | SETTLEMENT | STRUCTURE | POLITY | DYNASTY | MEDIA | TAXON),
    "technology": (None, HUMAN | PERSONLIKE | BATTLE | WAR | SETTLEMENT | POLITY | DYNASTY | PEOPLE | MEDIA),
}

# an article about a thing, a fictional thing or a film/album never is the
# historical thing itself
for _t, (_allowed, _contra) in TYPE_RULES.items():
    _contra |= ARTICLE | FICTION | (set() if _t == "cultural_work" else MEDIA)

ALL_ROOTS: set[str] = (
    HUMAN | PERSONLIKE | BATTLE | WAR | REBELLION | OCCURRENCE | TREATY | DOCUMENT | DISASTER | DISEASE
    | POLITY | PEOPLE | REGION | CIVILIZATION | DYNASTY | SETTLEMENT | PLACE | STRUCTURE | EXTRACTION
    | INSTITUTION | ORG | MILITARY | ALLIANCE | ROUTE | CURRENCY | WORK | RELTEXT | MOVEMENT | RELIGION
    | LANGUAGE | TECH | SOCIAL | PROCESS | MEDIA | TAXON | SHIP | ARTICLE | FICTION
)

# Wikidata's upper ontology is tangled ("historical country" is an
# organization; an Orthodox church reaches "built structure"), so most
# contradictions only make a row *suspect*. These kinds are DECISIVE: a QID of
# that kind can never be a row of the type (a city row whose QID is an
# encyclopedia article, a technology row whose QID is a village).
_BASE = HUMAN | PERSONLIKE | MEDIA | ARTICLE | FICTION
DECISIVE: dict[str, set[str]] = {
    "dynasty": _BASE | SETTLEMENT | BATTLE | WAR | STRUCTURE | TAXON | SHIP,
    "political_entity": _BASE | BATTLE | WAR | TAXON | SHIP | LANGUAGE,
    "military_unit": _BASE | SETTLEMENT | BATTLE | WAR | TAXON,
    "diplomatic_relationship": _BASE | SETTLEMENT | TAXON,
    "social_class": _BASE | SETTLEMENT | BATTLE | WAR | TAXON,
    "city": _BASE | BATTLE | WAR | TAXON | DISEASE,
    "infrastructure_monument": _BASE | BATTLE | WAR | TAXON | DISEASE,
    "extraction_infra": _BASE | BATTLE | WAR | TAXON,
    "educational_institution": _BASE | BATTLE | WAR | TAXON,
    "event_battle": _BASE | SETTLEMENT | STRUCTURE | TAXON | SHIP | DYNASTY | POLITY,
    "event_war": _BASE | SETTLEMENT | STRUCTURE | TAXON | SHIP | DYNASTY,
    "event_rebellion": _BASE | SETTLEMENT | STRUCTURE | TAXON | SHIP | DYNASTY,
    "event_treaty": _BASE | SETTLEMENT | STRUCTURE | TAXON | SHIP | DYNASTY | POLITY,
    "event_natural_disaster": _BASE | SETTLEMENT | STRUCTURE | DYNASTY,
    "event_tech_adoption": _BASE | SETTLEMENT | DYNASTY,
    "event_legal_reform": _BASE | SETTLEMENT | STRUCTURE | DYNASTY,
    "migration": _BASE | SETTLEMENT | STRUCTURE | DYNASTY,
    "epidemic_disease": _BASE | SETTLEMENT | STRUCTURE,
    "trade_route": _BASE | BATTLE | TAXON,
    "natural_resource": HUMAN | MEDIA | ARTICLE | FICTION | SETTLEMENT | POLITY | BATTLE | WAR,
    "currency_monetary_system": _BASE | SETTLEMENT | BATTLE | WAR | TAXON,
    "cultural_work": HUMAN | ARTICLE | FICTION | SETTLEMENT | BATTLE | WAR | TAXON,
    "intellectual_movement": _BASE | SETTLEMENT | BATTLE | WAR | TAXON,
    "archaeological_culture": _BASE | BATTLE | WAR | TAXON,
    "language": _BASE | SETTLEMENT | BATTLE | WAR | TAXON,
    "religious_text": _BASE | SETTLEMENT | BATTLE | WAR | TAXON,
    "legal_code": _BASE | SETTLEMENT | BATTLE | WAR | TAXON,
    "religious_movement": _BASE | SETTLEMENT | BATTLE | WAR | TAXON,
    "technology": _BASE | SETTLEMENT | POLITY | BATTLE | WAR,
}
# a person row whose QID is a group (people, dynasty, organization) may be a
# mistyped group row: not decisive
_PERSON_SOFT = PEOPLE | DYNASTY | MILITARY | PERSONLIKE
_PERSON_NEVER = SETTLEMENT | STRUCTURE | MEDIA | ARTICLE | FICTION | TAXON | SHIP | BATTLE | WAR | LANGUAGE | DISEASE
# types whose rows are proper-named individuals: a lower-case concept QID
# ('acropolis', 'patina') decides that the QID is wrong
GENERIC_DECISIVE_TYPES = {"person", "city", "political_entity", "dynasty", "infrastructure_monument",
                          "educational_institution", "event_battle"}

# polity roots that municipalities and parishes also reach; they do not confirm a polity
WEAK_POLITY = {"Q56061", "Q15642541", "Q1048835"}
STRONG_POLITY = (POLITY - WEAK_POLITY) | PEOPLE | CIVILIZATION | DYNASTY | ALLIANCE

# Kinds named in reports (first match wins).
KIND_NAMES: list[tuple[str, set[str]]] = [
    ("human", HUMAN), ("person-like", PERSONLIKE), ("battle", BATTLE), ("war", WAR),
    ("article", ARTICLE), ("fiction", FICTION), ("media", MEDIA),
    ("rebellion", REBELLION), ("treaty", TREATY), ("disaster", DISASTER), ("disease", DISEASE),
    ("dynasty", DYNASTY), ("settlement", SETTLEMENT), ("polity", POLITY), ("people", PEOPLE),
    ("military", MILITARY), ("alliance", ALLIANCE), ("structure", STRUCTURE), ("institution", INSTITUTION),
    ("route", ROUTE), ("currency", CURRENCY), ("religious text", RELTEXT), ("media", MEDIA),
    ("work", WORK), ("document", DOCUMENT), ("religion", RELIGION), ("movement", MOVEMENT),
    ("language", LANGUAGE), ("technology", TECH), ("social", SOCIAL), ("process", PROCESS),
    ("civilization", CIVILIZATION), ("region", REGION), ("taxon", TAXON), ("ship", SHIP),
    ("organization", ORG), ("place", PLACE), ("occurrence", OCCURRENCE), ("extraction", EXTRACTION),
    ("article", ARTICLE), ("fiction", FICTION),
]

# Types whose rows are one individual thing: a QID that is itself a class
# (carries P279 "subclass of") cannot be them.
INDIVIDUAL_TYPES = {
    "person", "event_battle", "event_war", "event_treaty", "event_rebellion",
    "city", "political_entity", "dynasty", "infrastructure_monument", "educational_institution",
    "military_unit",  # rows are mostly specific units; a concept QID is only a suspect (rule W7 needs more)
}


# deities and mythical figures reach 'fictional entity' in Wikidata; myth and
# cult are not fiction (Astarte the goddess is no novel's invention)
MYTH = {"Q4271324", "Q178885", "Q22988604", "Q13002315", "Q6949213"}
# a film, album, band, article or fiction is never the historical thing (C3)
NEVER_HISTORICAL = MEDIA | ARTICLE | FICTION


def kinds_of(p31: Iterable[str], closure: dict[str, set[str]]) -> set[str]:
    """Root classes reached by any of the P31 values."""
    out: set[str] = set()
    for cls in p31:
        out |= closure.get(cls, set())
        if cls in ALL_ROOTS:
            out.add(cls)
    if out & MYTH:
        out -= FICTION
    return out


def admin_area_for_city(entity_type: str, p31: list[str], closure: dict[str, set[str]]) -> bool:
    """An administrative district or region proposed for a city row (C3):
    'Kumbakonam Taluk' is not the town of Kumbakonam."""
    kinds = kinds_of(p31, closure)
    return (entity_type == "city" and bool(kinds & (WEAK_POLITY | REGION))
            and not kinds & (SETTLEMENT | STRONG_POLITY))


def never_historical(entity_type: str, p31: list[str], closure: dict[str, set[str]]) -> bool:
    """The QID is a film/album/band/article/fiction (a cultural_work row may be media)."""
    kinds = kinds_of(p31, closure)
    return bool(kinds & (ARTICLE | FICTION if entity_type == "cultural_work" else NEVER_HISTORICAL))


def kind_label(kinds: set[str]) -> str:
    names = [name for name, roots in KIND_NAMES if kinds & roots]
    return "/".join(names[:3]) if names else "-"


def junk_label(p31: Iterable[str]) -> str | None:
    for cls in p31:
        if cls in JUNK:
            return JUNK[cls]
    return None


def classify(entity_type: str, p31: list[str], closure: dict[str, set[str]]) -> str:
    """'ok' | 'contradiction' | 'unmatched' | 'unknown' for a QID's P31 vs a row type."""
    if not p31:
        return "unknown"
    if junk_label(p31):
        return "contradiction"
    kinds = kinds_of(p31, closure)
    allowed, contradict = TYPE_RULES.get(entity_type, (None, set()))
    if entity_type == "person":
        return "ok" if kinds & allowed else "contradiction"
    if entity_type == "political_entity" and kinds & SETTLEMENT and not kinds & STRONG_POLITY:
        # every village/parish reaches 'administrative territorial entity': a
        # settlement QID that reaches no real polity class is not a polity
        return "contradiction"
    if allowed is not None and kinds & allowed:
        return "ok"
    if _contra_kinds(kinds) & contradict:
        return "contradiction"
    return "ok" if allowed is None else "unmatched"


def _contra_kinds(kinds: set[str]) -> set[str]:
    """Kinds that may contradict a type: the weak polity roots that any
    museum piece or parish reaches (a 'human-geographic territorial entity')
    count only alongside a real polity class."""
    return kinds if kinds & STRONG_POLITY else kinds - WEAK_POLITY


def contradiction_strength(entity_type: str, p31: list[str], closure: dict[str, set[str]]) -> str | None:
    """'decisive' | 'soft' for a contradicting class, else None."""
    if classify(entity_type, p31, closure) != "contradiction":
        return None
    if junk_label(p31):
        return "decisive"
    kinds = kinds_of(p31, closure)
    if entity_type == "person":
        if kinds & _PERSON_NEVER:
            return "decisive"  # a place/thing, even if its tree also reaches a group class
        return "soft" if kinds & _PERSON_SOFT else "decisive"
    return "decisive" if _contra_kinds(kinds) & DECISIVE.get(entity_type, _BASE) else "soft"


# Types whose rows are places (a settlement/region QID may be the row itself).
PLACE_TYPES = {"city", "infrastructure_monument", "extraction_infra", "educational_institution", "trade_route",
               "political_entity", "archaeological_culture", "dynasty"}


def absolute_contradiction(entity_type: str, record: dict, row_name: str, closure: dict[str, set[str]]) -> bool:
    """For a row named exactly like its QID: does the QID's kind still rule it
    out? Only kinds that are never a mistyped version of the row count: media,
    articles, ships, taxa, languages, diseases, a human for a non-person row, a
    place for a non-place row, and fiction unless the QID is the English
    Wikipedia primary topic of that name (Jomsvikings, Terra Australis).
    Myth, works, processes, wars and organisations are left to a human: a
    'Chinese Rites controversy' typed intellectual_movement is a mistyped row,
    not a wrong QID."""
    kinds = _contra_kinds(kinds_of(record.get("p31", []), closure))
    hard = ARTICLE | SHIP
    if entity_type != "cultural_work":
        hard |= MEDIA
    if entity_type not in ("natural_resource", "epidemic_disease"):
        hard |= TAXON
    if entity_type != "language":
        hard |= LANGUAGE
    if entity_type not in ("epidemic_disease", "event_natural_disaster"):
        hard |= DISEASE
    if entity_type != "person":
        hard |= HUMAN
    if entity_type not in PLACE_TYPES:
        hard |= SETTLEMENT | PLACE | REGION | ROUTE
    primary = (record.get("enwiki") or "").casefold() == row_name.casefold()
    if not primary:
        hard |= FICTION
    return bool(kinds & hard) or bool(junk_label(record.get("p31", [])))


def org_kind(p31: list[str], closure: dict[str, set[str]]) -> bool:
    return bool(kinds_of(p31, closure) & ORG)


def is_generic_class(entity_type: str, record: dict) -> bool:
    """The QID is a concept ('imperial guard', 'acropolis'), not one thing:
    a lower-case label on a class item (P279, or no P31), for a type whose rows
    are individual things."""
    label = record.get("label") or ""
    is_class = bool(record.get("p279")) or not record.get("p31")
    return (entity_type in INDIVIDUAL_TYPES and is_class and label[:1].isalpha() and label[:1].islower()
            and "Q5" not in (record.get("p31") or []))


def generic_decides(entity_type: str, row_name: str, record: dict) -> bool:
    """A concept QID on a proper-named row of an individual type is wrong."""
    return (entity_type in GENERIC_DECISIVE_TYPES and row_name[:1].isupper()
            and is_generic_class(entity_type, record))
