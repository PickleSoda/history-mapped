"""Close the era-polity gaps left by the endpoint_era fixers (era-a, era-b, era-c).

Worklist: the relationships the three era agents left on a *modern-state row*
used out of its era ("Armenia" Q399 dated 1991 holding Tigranes the Great,
"Egypt" Q79 dated 1922 holding Saladin, "Germany" Q183 dated 1990 holding the
battles of 1914):

* ``output/audit/relfix-era-a-20261101/planned.csv`` -- ``human_note`` "modern-state
  or region row; no row exists for the polity of that era";
* ``output/audit/relfix-era-b-20261101/planned.csv`` -- ``reason`` ``modern_state_row:*``;
* ``output/audit/relfix-era-c-20261101/planned.csv`` -- ``class`` ``modern_state``
  (the medium/low-severity flags).

Each row is re-checked against the live DB (still the same endpoints, still
flagged by the C2 era check), then decided:

* **Era tables** (``ERA``): modern-state row -> windows of historical years ->
  the era's polity row. Windows hold years the polity row really covers and
  skip transition years. A window is ``land_ok`` when the polity is coextensive
  with the land (Kingdom of France for France), so born_in / resided_in /
  died_in may move to it; otherwise land relations keep the modern row as the
  region (a governor or a traveller "in Egypt" under the Umayyad caliphate).
  ``rule_ok`` is False where the land was a province of a larger state: a
  governor does not "rule" the caliphate.
* **New rows** (``NEW_ROWS``): well-defined polities with their own Wikidata
  item that several links need (Kingdom of Armenia, Duchy of Austria, Colonial
  Brazil, ...), imported through ``pipeline:import`` (``--import``); windows
  refer to them by QID.
* **Manual decisions** (``MANUAL``): per relationship, judged by hand from the
  description: a re-point the windows cannot make (a reign crossing a window
  edge), a reversal, or why the link is left (``keep`` = the modern row stands
  for the land; ``list`` = the link itself is wrong and needs a human).

Year basis: born_in / died_in use the person's own birth / death year (the
relationship's year is sometimes a floruit), everything else the
relationship's years, else its description, else a short dated endpoint.

Nothing is deleted. A re-point whose corrected link already exists is listed
(``duplicate_of``), not applied. Relationships carrying geometry periods are
left alone. Every write is guarded on the value read.

Usage (local DB only, from the repo root)::

    P="scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit.fix_era_gaps"
    $P                 # plan -> planned.csv
    $P --build-spec    # NEW_ROWS -> api/storage/app/pipeline/era-gaps-20261101/entities.jsonl
    $P --backup        # pg_dump relationships, entities, entity_temporal_ranges, entity_aliases
    $P --import        # dedup check + pipeline:import of the new rows -> created-rows.csv
    $P --apply         # re-date + re-point (one transaction) -> applied.csv, rollback.sql (tested)
    $P --redate        # REDATE alone (re-run after a skipped re-date), patches applied.csv / rollback.sql
    $P --rebuild       # timeline:rebuild for every touched entity
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from pipeline.audit.common import COMPOSE, REPO, connect, load_relationships, load_rows, write_csv
from pipeline.audit.dates import EVENT_TYPES, row_range, text_years
from pipeline.audit.fix_relation_eras import _NO_ERA_ROW, ENDPOINT_NOTES
from pipeline.audit.relations import ENDPOINT_RULES, endpoint_problem, era_problem

OUT = REPO / "output" / "audit" / "era-gaps-20261101"
BATCH = "era-gaps-20261101"
BATCH_DIR = REPO / "api" / "storage" / "app" / "pipeline" / BATCH
CONTAINER_BATCH = f"/var/www/html/storage/app/pipeline/{BATCH}"
SOURCES = {
    "A": REPO / "output" / "audit" / "relfix-era-a-20261101" / "planned.csv",
    "B": REPO / "output" / "audit" / "relfix-era-b-20261101" / "planned.csv",
    "C": REPO / "output" / "audit" / "relfix-era-c-20261101" / "planned.csv",
}
MERGE_VERDICTS = REPO / "output" / "audit" / "merge-review-20261101" / "verdicts.csv"
USER_DECISION_PREFIXES = ("a05afb75", "6255478f", "17d96812", "7baeedc3")

LAND_TYPES = {"born_in", "died_in", "resided_in", "located_at", "stationed_at", "recruited_from",
              "spread_to", "passes_through", "taught_at"}
# The modern row is not "the state at the time" in these; only MANUAL may move them.
MANUAL_ONLY_TYPES = {"succeeded_by", "preceded_by", "founded", "member_of_dynasty", "child_of", "parent_of",
                     "sibling_of", "married_to", "built_by", "split_from", "merged_into"}

# ── new rows (imported with pipeline:import, no map point) ───────────────────
# Dates: Wikidata P571/P576, except where the enwiki intro the summary comes
# from gives a different founding year by more than 25 years (noted).
NEW_ROWS: dict[str, dict[str, Any]] = {
    "Q208404": {"enwiki": "Kingdom of Armenia (antiquity)", "name": "Kingdom of Armenia (antiquity)", "start": "-189", "end": "428", "subtype": "kingdom",
                "aliases": ["Kingdom of Greater Armenia", "Greater Armenia"], "date_confidence": "medium",
                "summary": "Kingdom of Greater Armenia in the ancient Near East from 189 BCE to 428 CE, from the reign "
                           "of Artaxias I until the Sasanians abolished the Arsacid monarchy.",
                "note": "dates from the enwiki intro (189 BC-428 AD); Wikidata P571 -553 is the Orontid satrapy"},
    "Q5124786": {"enwiki": "Civitas Schinesghe", "name": "Civitas Schinesghe", "start": "960", "end": "1025", "subtype": "duchy",
                 "aliases": ["Duchy of Poland"], "date_confidence": "medium",
                 "summary": "Early medieval Piast polity centred on Gniezno, known in historiography as the Duchy of "
                            "Poland and the predecessor of the Kingdom of Poland formally established in 1025."},
    "Q2088324": {"enwiki": "Colonial Brazil", "name": "Colonial Brazil", "start": "1500", "end": "1815", "subtype": "colonial_territory",
                 "aliases": ["Portuguese America", "Portuguese Brazil"], "date_confidence": "high",
                 "summary": "Portuguese colony in South America from the arrival of the Portuguese in 1500 until 1815, "
                            "when Brazil was raised to a kingdom in union with Portugal; its economy rested on "
                            "brazilwood, sugar and later gold and diamond mining, worked largely by enslaved Africans."},
    "Q207118": {"enwiki": "Roman Syria", "name": "Roman Syria", "start": "-64", "end": "198", "subtype": "other",
                "aliases": ["Syria (Roman province)"], "date_confidence": "high",
                "summary": "Roman province annexed by Pompey in 64 BCE after the defeat of Tigranes the Great, "
                           "divided into Coele Syria and Syria Phoenice in the late 2nd century CE."},
    "Q3624335": {"enwiki": "Duchy of Austria", "name": "Duchy of Austria", "start": "1156", "end": "1453", "subtype": "duchy",
                 "aliases": [], "date_confidence": "high",
                 "summary": "Medieval principality of the Holy Roman Empire created in 1156 by the Privilegium Minus, "
                            "ruled by the Babenbergs and from 1276 by the Habsburgs, and raised to an archduchy in 1453."},
    "Q47261": {"enwiki": "Duchy of Bavaria", "name": "Duchy of Bavaria", "start": "907", "end": "1805", "subtype": "duchy",
               "aliases": [], "date_confidence": "medium",
               "summary": "Stem duchy of the East Frankish realm and the Holy Roman Empire, formed in the late "
                          "Carolingian period and ruled from 1180 by the House of Wittelsbach."},
    "Q256961": {"enwiki": "Electorate of Bavaria", "name": "Electorate of Bavaria", "start": "1623", "end": "1805", "subtype": "principality",
                "aliases": [], "date_confidence": "high",
                "summary": "Wittelsbach electorate of the Holy Roman Empire from 1623, when the electoral dignity "
                           "passed to Bavaria, until it was succeeded by the Kingdom of Bavaria in 1806."},
    "Q154195": {"enwiki": "Kingdom of Bavaria", "name": "Kingdom of Bavaria", "start": "1806", "end": "1918", "subtype": "kingdom",
                "aliases": [], "date_confidence": "high",
                "summary": "German kingdom that succeeded the Electorate of Bavaria in 1806 under the Wittelsbachs "
                           "and from 1871 was the second-largest state of the German Empire, until 1918."},
    "Q887803": {"enwiki": "Sultanate of Brunei (1368–1888)", "name": "Bruneian Sultanate", "start": "1368", "end": "1888", "subtype": "sultanate",
                "aliases": ["Sultanate of Brunei", "Bruneian Empire"], "date_confidence": "medium",
                "summary": "Malay sultanate centred on Brunei on the northern coast of Borneo that expanded over "
                           "coastal Borneo and the Philippines after the fall of Malacca, declined in the 17th and "
                           "18th centuries and became a British protectorate in 1888."},
    "Q22684779": {"enwiki": "Omani Empire", "name": "Omani Empire", "start": "1696", "end": "1856", "subtype": "empire",
                  "aliases": [], "date_confidence": "medium",
                  "summary": "Omani maritime empire that rivalled Portugal and Britain in the Persian Gulf and Indian "
                             "Ocean, reaching from the Strait of Hormuz to Cape Delgado, and split into Muscat and "
                             "Zanzibar after Said bin Sultan's death in 1856."},
    "Q779011": {"enwiki": "Principality of Montenegro", "name": "Principality of Montenegro", "start": "1852", "end": "1910", "subtype": "principality",
                "aliases": [], "date_confidence": "high",
                "summary": "Principality in Southeastern Europe with its capital at Cetinje from 1852 until Nikola I "
                           "proclaimed it a kingdom in 1910."},
    "Q107258515": {"enwiki": "Pahlavi Iran", "name": "Pahlavi Iran", "start": "1925", "end": "1979", "subtype": "kingdom",
                   "aliases": ["Imperial State of Iran", "Imperial State of Persia"], "date_confidence": "high",
                   "summary": "Iranian state under the Pahlavi dynasty from the deposition of the Qajars in 1925 until "
                              "its overthrow in the Iranian Revolution of 1979."},
    "Q3167772": {"enwiki": "Kingdom of Polonnaruwa", "name": "Kingdom of Polonnaruwa", "start": "1070", "end": "1236", "subtype": "kingdom",
                 "aliases": [], "date_confidence": "medium",
                 "summary": "Sinhalese kingdom ruled from Polonnaruwa that unified Sri Lanka and extended its "
                            "influence overseas under Parakramabahu the Great.",
                 "note": "start from the enwiki intro (1070); Wikidata P571 1017 is the Chola capital move"},
    "Q3185305": {"enwiki": "Kingdom of Israel (united monarchy)", "name": "Kingdom of Israel (united monarchy)", "start": "-1050", "end": "-930", "subtype": "kingdom",
                 "aliases": ["United Monarchy", "United Kingdom of Israel"], "date_confidence": "low",
                 "summary": "Israelite kingdom that, according to the Hebrew Bible, united Israel and Judah under "
                            "Saul, Ish-bosheth, David and Solomon; its extent and nature are debated by scholars."},
}

# ── era tables ───────────────────────────────────────────────────────────────
# modern-state row (id prefix) -> [(first, last, era row prefix or new-row QID,
# label, land_ok, rule_ok)]. Narrowest window holding the whole year range wins.
T, F = True, False
ERA: dict[str, list[tuple[int, int, str, str, bool, bool]]] = {
    "1c3befeb": [  # France (Q142 = the country; dated 1958, the Fifth Republic)
        (481, 842, "f05ecc7c", "Frankish kingdom", T, T),
        (844, 986, "fe91f6d0", "West Francia", T, T),
        (988, 1791, "b78831f7", "Kingdom of France", T, T),
        (1793, 1803, "06ddcac7", "French First Republic", T, T),
        (1805, 1813, "8f25d3e1", "First French Empire", T, T),
        (1816, 1847, "b78831f7", "Kingdom of France", T, T),
        (1849, 1851, "bfa2fff5", "French Second Republic", T, T),
        (1853, 1869, "7a5f13d3", "Second French Empire", T, T),
        (1871, 1939, "c50f4e81", "French Third Republic", T, T),
        (1947, 1957, "acf5cb18", "Fourth French Republic", T, T),
    ],
    "e021bc9d": [  # Germany (Q183, dated 1990)
        (1871, 1918, "018ffab9", "German Empire", T, T),
        (1919, 1932, "e4d0946a", "Weimar Republic", T, T),
        (1933, 1945, "520c212c", "Nazi Germany", T, T),
    ],
    "9de131ab": [  # Egypt (Q79, dated 1922)
        (-4000, -31, "4aabfa9f", "Ancient Egypt", T, T),
        (-304, -31, "eb7ee15b", "Ptolemaic Kingdom", T, T),
        (-29, 394, "72d3329d", "Roman Egypt", T, T),
        (642, 660, "afaee64f", "Rashidun Caliphate (Egypt a province)", F, F),
        (662, 749, "8bbeb213", "Umayyad Caliphate (Egypt a province)", F, F),
        (970, 1170, "37a52557", "Fatimid Caliphate", T, T),
        (1172, 1249, "a7f55ff4", "Ayyubid Sultanate", T, T),
        (1251, 1516, "79953c6d", "Mamluk Sultanate", T, T),
        (1518, 1797, "a5b04899", "Ottoman Egypt", T, T),
        (1802, 1866, "a5b04899", "Ottoman Egypt", T, T),
        (1868, 1913, "fc65419f", "Khedivate of Egypt", T, T),
    ],
    "48d42e2f": [  # Armenia (Q399, dated 1991)
        (-189, 428, "Q208404", "Kingdom of Armenia (antiquity)", T, T),
        (1080, 1375, "4201a1b0", "Cilician Armenia", T, T),
    ],
    "d50b2c9b": [  # Syria (Q858, dated 1920)
        (-301, -65, "0fad94fa", "Seleucid Empire (Syria its core)", F, T),
        (-64, 197, "Q207118", "Roman Syria", T, T),
    ],
    "2ac323cb": [  # Poland (Q36, dated 1918)
        (960, 1024, "Q5124786", "Civitas Schinesghe", T, T),
        (1025, 1384, "054270a3", "Kingdom of Poland", T, T),
        (1570, 1795, "d36f70ea", "Polish-Lithuanian Commonwealth", T, T),
    ],
    "73c5e3d6": [  # Bavaria (Q980 Free State, dated 1919)
        (908, 1622, "Q47261", "Duchy of Bavaria", T, T),
        (1623, 1805, "Q256961", "Electorate of Bavaria", T, T),
        (1806, 1918, "Q154195", "Kingdom of Bavaria", T, T),
    ],
    "931f4d38": [  # Italy (Q38, dated 1946)
        (1861, 1945, "90a5d781", "Kingdom of Italy", T, T),
    ],
    "376426ae": [  # Austria (Q40, dated 1918)
        (1156, 1452, "Q3624335", "Duchy of Austria", T, T),
        (1527, 1803, "8c57d738", "Habsburg Monarchy", T, T),
        (1805, 1866, "b3436059", "Austrian Empire", T, T),
        (1868, 1917, "99974943", "Austria-Hungary", T, T),
    ],
    "d6eef6d2": [  # Russia (carries Q34266, the Russian Empire's item; dated 1991)
        (1283, 1546, "8623826b", "Muscovy", T, T),
        (1548, 1720, "2d931bbf", "Tsardom of Russia", T, T),
        (1722, 1916, "bee08f41", "Russian Empire", T, T),
        (1918, 1921, "d9be48b0", "Soviet Russia", T, T),
        (1923, 1990, "cc695213", "Soviet Union", T, T),
    ],
    "530b402b": [  # Ethiopia (Q115, dated 1995)
        (1271, 1936, "b35f2c31", "Ethiopian Empire", T, T),
        (1941, 1973, "b35f2c31", "Ethiopian Empire", T, T),
    ],
    "dac6634b": [  # Vietnam (Q881, dated 1976)
        (1055, 1803, "bcb8b5d8", "Dai Viet", T, T),
    ],
    "ad66ff5a": [  # Iran (Q794, dated 1979)
        (1790, 1924, "d194d4fe", "Qajar Iran", T, T),
        (1926, 1978, "Q107258515", "Pahlavi Iran", T, T),
    ],
    "8160360a": [  # Republic of the Philippines (Q928, dated 1946)
        (1899, 1901, "75eda824", "First Philippine Republic", T, T),
    ],
    "435bedec": [  # Tibet (Q2444884, 1912-1959)
        (618, 842, "bbb2ec8a", "Tibetan Empire", T, T),
    ],
    "d7d5d32a": [  # Morocco (Q1028, dated 1956)
        (1511, 1630, "28ed2a1c", "Saadi Sultanate", T, T),
        (1660, 1911, "71db5918", "Alawi Sultanate", T, T),
    ],
    "6c855ca3": [  # Oman (Q842, dated 1970)
        (1696, 1856, "Q22684779", "Omani Empire", T, T),
    ],
    "43490188": [  # Brunei (Q921, dated 1984)
        (1368, 1888, "Q887803", "Bruneian Sultanate", T, T),
    ],
    "69cb1bf0": [  # Israel (Q801, dated 1948)
        (-1049, -930, "Q3185305", "Kingdom of Israel (united monarchy)", T, T),
        (-929, -720, "27d5cabf", "Kingdom of Israel", T, T),
    ],
    "bcc8836d": [  # Burma (Q836, dated 1948)
        (1752, 1885, "6de0e00e", "Konbaung Kingdom", T, T),
    ],
    "69343323": [  # Ireland (Q27, dated -4500..-4000)
        (1542, 1800, "cd9ed338", "Kingdom of Ireland", T, T),
    ],
    "38b25b9c": [  # Sri Lanka (Q854, dated 1972)
        (-376, 1016, "48da4229", "Anuradhapura Kingdom", T, T),
        (1070, 1232, "Q3167772", "Kingdom of Polonnaruwa", T, T),
    ],
    "cbd08d23": [  # Montenegro (Q236, dated 2006)
        (1852, 1910, "Q779011", "Principality of Montenegro", T, T),
    ],
    "e6efe4ec": [  # Netherlands (Q55, dated 1795)
        (1581, 1794, "e835047d", "Dutch Republic", T, T),
    ],
    "98b5080f": [  # "United Provinces" (QID = Rio de la Plata) carrying Dutch links
        (1568, 1794, "e835047d", "Dutch Republic", T, T),
    ],
    "3dac5cc1": [  # Normandy (region, dated 2016)
        (912, 1203, "330f2727", "Normandy (duchy)", T, T),
    ],
    "297965df": [  # Iceland (Q189, dated 1918)
        (931, 1262, "d2f9c2b1", "Icelandic Commonwealth", T, T),
    ],
    "d7e394ae": [  # Norway (Q20, dated 1905)
        (872, 1396, "3140fc0c", "Kingdom of Norway", T, T),
    ],
    "797bd0f0": [  # Britain (Q174193, the 1801-1927 United Kingdom)
        (43, 409, "a31c5c49", "Roman Britain", T, T),
    ],
    "4162c9c5": [  # British Parliament (Q11010, from 1801)
        (1215, 1706, "5266361a", "Parliament of England", T, T),
    ],
    "51d0f2cb": [  # Ukraine (Q212, dated 1991)
        (1922, 1990, "dca88dc5", "Ukrainian SSR", T, T),
    ],
    "73c519b8": [  # Belarus (Q184, dated 1991)
        (1922, 1990, "cc78e6a0", "Byelorussian SSR", T, T),
    ],
    "7bd2f2f5": [  # Kenya (Q114, dated 1963)
        (1895, 1919, "d48a460b", "East Africa Protectorate", T, T),
    ],
    "bad55ab0": [  # Uganda (Q1036, dated 1962)
        (1894, 1961, "a78651c4", "Uganda Protectorate", T, T),
    ],
    "7301a7d6": [  # Sindh (Q37211, the 1947 province) -> the QID-less Sindh region row
        (711, 1946, "a08e8feb", "Sindh (region row)", T, T),
    ],
    "1ca4bf89": [  # Brazil (Q155, dated 1822)
        (1500, 1815, "Q2088324", "Colonial Brazil", T, T),
    ],
    "e992487f": [  # Mexico (Q96, dated 1821)
        (1522, 1820, "1daddfce", "New Spain", T, T),
    ],
}

# ── manual decisions (relationship id prefix) ────────────────────────────────
# target: era row prefix / new-row QID for the modern-state side; reverse: swap
# endpoints too; keep: the modern row stands for the land (left); list: the
# link is wrong in itself (left for a human).
_GOV = "a governor/official of a province, not the sovereign: the modern row stands for the land"
_SELF = "the era polity is the other endpoint ('X controlled_by the caliphate'): the modern row stands for the land"
_LAND = "about the land, which was not one polity then: the modern row stands for the region"
_SPAN = "the years cross a regime change; no single era row fits"
_TYPE = "relation type wrong for this person (minister/commander/consort, not ruler); needs a human"
_BAD = "the link itself is wrong (type, direction or target); needs a human"
_PEOPLE = "people/region row with a modern QID, not a modern state of this polity; no era polity to move to"
MANUAL: dict[str, dict[str, Any]] = {
    # France
    "6b3204d9": {"list": "inverted (France controlled_by Saint-Domingue) and spans several French regimes"},
    "228f9bc0": {"keep": _SPAN + " (Louisiana 1682-1803: Kingdom, then Republic)"},
    "fc6841fb": {"keep": _SPAN + " (1792: war declared under the monarchy, fought by the Republic)"},
    "1e82a5b7": {"list": "French First Republic rules France 1793: the republic is the era polity itself"},
    "b08ea1da": {"target": "06ddcac7", "note": "Haitian Revolution ended 1 Jan 1804, before the Empire (May 1804)"},
    "5d54d6fc": {"keep": _SPAN + " (Verny 1837-1908)"},
    "48cde997": {"list": "Pomare IV ruled Tahiti, not France; target should be Tahiti"},
    "fb7e57ef": {"keep": _SPAN + " (1848)"},
    "42cbadfa": {"list": _TYPE + " (admiral)"},
    "bd4da457": {"target": "7a5f13d3", "note": "Tianjin Massacre June 1870, under the Second Empire"},
    "eb597ce4": {"target": "7a5f13d3", "note": "France entered the war in July 1870 under Napoleon III"},
    "2ce3252c": {"target": "7a5f13d3", "note": "Napoleon III, Emperor of the French 1852-1870"},
    "2b2d78cc": {"target": "c50f4e81", "note": "the Third Republic created the Indochinese Union (1887)"},
    "af191854": {"target": "c50f4e81", "note": "the Second Empire was succeeded by the Third Republic (Sept 1870)"},
    "b73e92cc": {"list": "Bugeaud participated_in France: wrong link (colonial conquest of Algeria)"},
    "7c5cc249": {"keep": "the Patenotre Treaty row is 1884; the link says 1893 (date question, not a polity gap)"},
    # Germany
    "0efe1feb": {"list": "the airship Hindenburg linked as the person Paul von Hindenburg (built_by Germany)"},
    # Egypt
    "160164ae": {"list": "relation inverted in meaning: Ptolemy I repelled the invasion"},
    "e4568f90": {"list": "reversed: Ptolemy I controlled Egypt"},
    "f91a9768": {"list": "reversed: Rome controlled Egypt"},
    "f75ba88b": {"list": "reversed: Egypt was controlled by the Byzantine Empire"},
    "d252a3da": {"target": "eb7ee15b", "note": "the Ptolemaic dynasty ruled the Ptolemaic Kingdom (305-30 BCE)"},
    "b3cd77dd": {"target": "eb7ee15b", "note": "Cleopatra VII, last ruler of the Ptolemaic Kingdom"},
    "a5ecf487": {"list": "Egypt participated_in Makuria: wrong link (the Baqt treaty)"},
    "1581a697": {"target": "a7f55ff4", "note": "Saladin founded and ruled the Ayyubid Sultanate (vizier of Egypt from 1169)"},
    "88d25c84": {"target": "37a52557", "note": "Dirgham was Fatimid vizier until 1164"},
    "97422bd5": {"target": "a7f55ff4", "note": "as-Salih Ayyub, Ayyubid sultan until 1249"},
    "879142c0": {"target": "a5b04899", "note": "al-Tahtawi born Oct 1801, after the French left (Sept 1801)"},
    "10636df5": {"list": "Ibrahim Pasha victorious_at Egypt: target should be the Battle of Nezib"},
    "8b7a6032": {"keep": "Pepi I row carries a namesake's date (-1600); fix the person first"},
    # Armenia
    "92390c59": {"target": "Q208404", "reverse": True,
                 "note": "reversed: Antony occupied Armenia (Armenia controlled_by Roman Republic)"},
    "78b39cba": {"target": "Q208404", "reverse": True,
                 "note": "reversed: Vologases IV held Armenia (Armenia controlled_by Vologases IV)"},
    "f8cffbe0": {"target": "Q208404", "reverse": True,
                 "note": "reversed: Parthia controlled Armenia"},
    "de96ca9c": {"target": "Q208404", "reverse": True,
                 "note": "reversed: Armenia became a Roman client kingdom"},
    "636aa837": {"list": "Armenia participated_in Roman Empire: wrong link (Roman influence)"},
    "220422b5": {"list": "Armenia participated_in Sasanian Empire: wrong link (387 partition)"},
    "2b2db138": {"keep": "428: the kingdom was abolished; Sasanian Persarmenia has no row"},
    # Syria
    "3ef6f94e": {"keep": "Tigranes held Seleucid Syria as conqueror; not a Seleucid king"},
    "56f44f44": {"list": "the 'Battle of Beth Horon' row is the 166 BCE battle; 66 CE has no row"},
    # Poland
    "380c2eef": {"target": "Q5124786", "note": "Piast rule 1000-1025, before the 1025 coronation"},
    "126865d2": {"target": "054270a3", "note": "Casimir I restored the Kingdom of Poland (ruled 1034-1058)"},
    # Bavaria
    "2ceb6635": {"keep": "Tassilo III's Agilolfing duchy (to 788); already linked to the 'Bavarians' row"},
    "f196a7fd": {"keep": "788: Charlemagne annexed the Agilolfing duchy; no row for it"},
    "b610300a": {"keep": "817: Carolingian sub-kingdom of Bavaria; no row"},
    "61857566": {"keep": "907: Bavarian levy under Margrave Luitpold, as the stem duchy formed"},
    # Austria
    "7c56cf43": {"target": "8c57d738", "note": "Ferdinand I founded and ruled the Habsburg Monarchy (1526-1564)"},
    "28e02f94": {"target": "8c57d738", "note": "Francis II ruled the Habsburg lands 1792-1835 (row 1526-1918)"},
    "a7d7a3ea": {"list": _TYPE + " (Beaulieu commanded the army)"},
    "d6ff6b0f": {"list": _TYPE + " (Mack commanded the army at Ulm)"},
    "13aa023d": {"list": _TYPE + " (Metternich was foreign minister)"},
    # Russia
    "531945ef": {"target": "2d931bbf", "note": "Ivan IV, first Tsar of Russia (Grand Prince from 1533, Tsar 1547)"},
    "1a9f070a": {"keep": _SPAN + " (Romanovs 1613-1917: Tsardom, then Empire)"},
    "0c0e1455": {"target": "bee08f41", "note": "Peter the Great, Tsar and first Emperor; the description is the 1722 war"},
    "064fc180": {"list": "Russia participated_in Austrian Empire for Kunersdorf 1759: wrong type and target"},
    "5411d758": {"target": "bee08f41", "note": "Nicholas II, Emperor of Russia 1894-1917"},
    "90d1fce9": {"target": "bee08f41", "note": "the Russian Empire fought in WWI from 1914 (until 1917)"},
    "8c76fa34": {"list": _TYPE + " (Witte as finance minister)"},
    "6a0f1268": {"list": _TYPE + " (empress consort)"},
    "04848502": {"list": _TYPE + " (interior minister)"},
    "e98d2482": {"list": _TYPE + " (Brusilov was a general)"},
    # Iran / Oman / Brunei / Brazil / Netherlands
    "a108f560": {"target": "d194d4fe", "note": "Ahmad Shah Qajar reigned 1909-1925 (Qajar Iran)"},
    "c1719587": {"target": "9bb1352d", "note": "Thuwaini bin Said, Sultan of Muscat and Oman 1856-1866"},
    "bb733bb5": {"target": "Q887803", "note": "tradition: Awang Alak Betatar founded the sultanate (c. 1400)"},
    "cc50e42d": {"keep": "Duarte Coelho ruled the captaincy of Pernambuco, not the colony"},
    "a9260c22": {"target": "e835047d", "note": "the Union of Utrecht (1579) founded the Dutch Republic"},
    # Ethiopia
    "3e4f89d2": {"list": "Victor Emmanuel III's 1936 claim to Ethiopia: Italian East Africa, not the Ethiopian Empire"},
    # Vietnam
    "2cfec9ca": {"keep": "the Nguyen lords held southern Dai Viet under nominal Le rule; 'rules Dai Viet' overstates"},
    "c6820f76": {"list": "reversed: Tay Son controlled Vietnam"},
    "d6a97a1b": {"list": "Qing defeated_at a polity; target should be the Battle of Ngoc Hoi-Dong Da"},
    "9f43ff89": {"list": "Qing fought_at a polity; target should be the battle"},
    "5121c342": {"list": "Britain participated_in Vietnam 1945: wrong link (Britain row also 1801-1927)"},
    # Tibet
    "664db13c": {"target": "bbb2ec8a", "note": "the Yarlung dynasty were the Tibetan emperors (to 842)"},
    "42fe13d0": {"list": "Nanzhao defeated_at 'Tibet' for the Battle of Shenchuan (Nanzhao won); needs a battle row"},
    # Morocco
    "6c041140": {"list": "Morocco resided_in Abdallah ibn Yasin: inverted/wrong link"},
    "759f3552": {"list": "Idrisid dynasty resided_in Morocco: wrong type"},
    # Israel
    "3639b6cb": {"keep": "Ebenezer (c. 1050 BCE) predates the monarchy"},
    # Burma
    "e293e014": {"target": "6de0e00e", "note": "Hsinbyushin, Konbaung king 1763-1776"},
    # Sri Lanka
    "f3df7ac7": {"target": "Q3167772", "note": "Vijayabahu I founded the Polonnaruwa kingdom (king from 1070)"},
    # Gujarat / Sindh
    "f2b65309": {"keep": _SELF},
    "e63aa3a1": {"list": "reversed: the Umayyad Caliphate controlled Sindh"},
    # Cyprus
    "8dfb92a7": {"list": "reversed: Tyre controlled part of Cyprus"},
    "9151320b": {"list": "reversed: Rome annexed Cyprus"},
    "131f84bc": {"list": "reversed: Ptolemy I controlled Cyprus"},
    "08a2887c": {"list": "Demetrius defeated_at Cyprus: wrong type (lost control of the island)"},
    # misc
    "8d91437e": {"target": "d36f70ea", "note": "'First Republic' row is Venezuela (1811); Poland-Lithuania signed Karlowitz"},
    "ca81f7d9": {"list": "Magnus Eriksson succeeded_by Norway: wrong link"},
    "34f42661": {"list": "Otto I founded the bishopric of Brandenburg (948), not Brandenburg-Prussia"},
    "52d269be": {"target": "23389a2d", "note": "Endecott governed the Massachusetts Bay colony (row 'Massachusetts Bay Company')"},
    "4a33abde": {"list": "reversed: the East Africa Protectorate was succeeded by Kenya Colony (no row)"},
    "50c3e8ce": {"list": "Jugurtha participated_in Spain: target should be the Siege of Numantia"},
}

# Entity date corrections: (entity_id prefix, field, old, new, source)
REDATE: list[tuple[str, str, int, int, str]] = [
    ("054270a3", "start_year", 1385, 1025,
     "Kingdom of Poland row carries Q8890160, whose P571 is 1025 and whose enwiki article ('Kingdom of Poland') "
     "dates the state 1025-1795; the row's 1385 start is the Jagiellonian union. Needed for the Piast-era links."),
]

FIELDS = ["relationship_id", "source_list", "action", "relationship_type", "years", "years_from",
          "old_source_id", "old_source", "old_target_id", "old_target", "new_source_id", "new_source",
          "new_target_id", "new_target", "reverse", "era_row", "reason", "description"]


# ── helpers ─────────────────────────────────────────────────────────────────

def load_worklist() -> list[dict[str, str]]:
    """(source letter, relationship id, suspect modern-state row id) from the three planned.csv files."""
    out: dict[str, dict[str, str]] = {}
    with SOURCES["A"].open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r.get("human_note", "").startswith("modern-state or region row"):
                out.setdefault(r["relationship_id"], {"src": "A", "rid": r["relationship_id"],
                                                      "pair": (r["old_source_id"], r["old_target_id"])})
    with SOURCES["B"].open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["reason"].startswith("modern_state_row"):
                out.setdefault(r["relationship_id"], {"src": "B", "rid": r["relationship_id"],
                                                      "pair": (r["source_id"], r["target_id"]),
                                                      "bad_side": r["bad_side"]})
    with SOURCES["C"].open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["class"] == "modern_state":
                out.setdefault(r["relationship_id"], {"src": "C", "rid": r["relationship_id"],
                                                      "pair": (r["source_id"], r["target_id"]),
                                                      "suspect_name": r["reason"].split(" (")[0]})
    return list(out.values())


def load_exclusions() -> set[str]:
    with MERGE_VERDICTS.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    return {x for r in rows for x in (r.get("survivor_id", ""), r.get("loser_id", "")) if x}


def excluded(eid: str, excl: set[str]) -> bool:
    return eid in excl or eid.startswith(USER_DECISION_PREFIXES)


def resolve(key: str, rows: dict[str, Any], by_qid: dict[str, str]) -> str | None:
    """Entity id for an id prefix, or for a new row's QID (None until imported)."""
    if key.startswith("Q"):
        return by_qid.get(key)
    hits = [eid for eid in rows if eid.startswith(key)]
    if len(hits) != 1:
        raise SystemExit(f"entity prefix {key!r} matches {len(hits)} rows")
    return hits[0]


def suspect_side(item: dict[str, str], src, tgt) -> str:
    sid = None
    if item["src"] == "B" and item.get("bad_side") in ("S", "T"):
        return "source" if item["bad_side"] == "S" else "target"
    if item["src"] == "C":
        return "source" if src.name == item["suspect_name"] else "target"
    for side, row in (("source", src), ("target", tgt)):
        if row.id[:8] in ERA:
            sid = side
    if sid:
        return sid
    for side, row in (("source", src), ("target", tgt)):
        if ENDPOINT_NOTES.get(row.name) == _NO_ERA_ROW:
            return side
    # the endpoint whose span lies furthest from the relationship's years
    return "source" if (src.start or 0) > (tgt.start or 0) else "target"


def years_for(rel: dict[str, Any], suspect, other) -> tuple[tuple[int, int] | None, str]:
    """The years the link is about (see module doc)."""
    rtype = rel["type"]
    if other.type == "person" and rtype in ("born_in", "died_in"):
        y = other.start if rtype == "born_in" else other.end
        if y is not None:
            return (y, y), "person_" + ("birth" if rtype == "born_in" else "death")
    ys = [y for y in (rel["start"], rel["end"]) if y is not None]
    if ys:
        return (min(ys), max(ys)), "relationship"
    ys = text_years(rel["description"])
    if ys:
        return (min(ys), max(ys)), "description"
    if other.type == "person" or other.type in EVENT_TYPES:
        span = row_range(other.type, other.start, other.end)
        if span and other.start is not None and other.end is not None:
            return span, "other_endpoint"
    return None, ""


def era_pick(windows, years):
    fits = [(hi - lo, w) for w in windows for lo, hi in [w[:2]] if lo <= years[0] and years[1] <= hi]
    if not fits:
        return None
    fits.sort(key=lambda x: x[0])
    return fits[0][1]


def inverted(rtype: str, src_type: str, tgt_type: str) -> bool:
    if rtype not in ENDPOINT_RULES:
        return False
    return bool(endpoint_problem(rtype, src_type, tgt_type)) and not endpoint_problem(rtype, tgt_type, src_type)


def new_row_ids(conn) -> dict[str, str]:
    cur = conn.cursor()
    cur.execute("SELECT wikidata_id, entity_id::text FROM entities WHERE wikidata_id = ANY(%s)", (list(NEW_ROWS),))
    return dict(cur.fetchall())


class _Proxy:
    """A planned new row (not imported yet), for the era check."""
    def __init__(self, qid: str):
        s = NEW_ROWS[qid]
        self.id, self.name, self.type = f"NEW:{qid}", s["name"], "political_entity"
        self.start, self.end = int(s["start"]), int(s["end"])


# ── plan ────────────────────────────────────────────────────────────────────

def plan(conn) -> list[dict[str, Any]]:
    rows = load_rows(conn)
    for prefix, field, old, new, _ in REDATE:  # plan as if the re-date is applied
        row = rows[resolve(prefix, rows, {})]
        attr = "start" if field == "start_year" else "end"
        if getattr(row, attr) == old:
            setattr(row, attr, new)
    rels = {r["id"]: r for r in load_relationships(conn)}
    by_qid = new_row_ids(conn)
    excl = load_exclusions()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT relationship_id::text FROM geometry_periods WHERE relationship_id IS NOT NULL")
    with_geom = {r[0] for r in cur.fetchall()}
    triples: dict[tuple[str, str, str], list[str]] = {}
    for r in rels.values():
        triples.setdefault((r["source"], r["target"], r["type"]), []).append(r["id"])
    by_prefix: dict[str, list[str]] = {}
    work = load_worklist()
    for it in work:
        by_prefix.setdefault(it["rid"][:8], []).append(it["rid"])
    for key in MANUAL:
        if len(by_prefix.get(key, [])) != 1:
            raise SystemExit(f"manual key {key!r} matches {len(by_prefix.get(key, []))} worklist rows")

    def ent(key: str):
        eid = resolve(key, rows, by_qid)
        if eid is None:
            return _Proxy(key)
        return rows[eid]

    out: list[dict[str, Any]] = []
    planned: dict[tuple[str, str, str], str] = {}
    for it in work:
        rid = it["rid"]
        rel = rels.get(rid)
        base = {"relationship_id": rid, "source_list": it["src"]}
        if rel is None:
            out.append({**base, "action": "skip", "reason": "relationship_gone"})
            continue
        src, tgt = rows[rel["source"]], rows[rel["target"]]
        base.update({"relationship_type": rel["type"], "old_source_id": src.id, "old_source": src.name,
                     "old_target_id": tgt.id, "old_target": tgt.name, "description": rel["description"],
                     "years": f"{rel['start']}..{rel['end']}"})
        if (src.id, tgt.id) != tuple(it["pair"]):
            out.append({**base, "action": "skip", "reason": "endpoints changed since the era agent's plan"})
            continue
        if excluded(src.id, excl) or excluded(tgt.id, excl):
            out.append({**base, "action": "skip", "reason": "excluded endpoint (merge review / user decision)"})
            continue
        if era_problem(rel["type"], src, tgt) is None:
            out.append({**base, "action": "skip", "reason": "no longer flagged (endpoint re-dated since)"})
            continue
        if rid in with_geom:
            out.append({**base, "action": "skip", "reason": "carries geometry periods; left"})
            continue
        side = suspect_side(it, src, tgt)
        suspect, other = (src, tgt) if side == "source" else (tgt, src)
        key = rid[:8]
        m = MANUAL.get(key, {})
        if "keep" in m or "list" in m:
            act = "keep_region" if "keep" in m else "list"
            out.append({**base, "action": act, "reason": m.get("keep") or m.get("list")})
            continue
        years, years_from = years_for(rel, suspect, other)
        base.update({"years": f"{years[0]}..{years[1]}" if years else base["years"], "years_from": years_from})
        windows = ERA.get(suspect.id[:8])
        reverse = bool(m.get("reverse"))
        if "target" in m:
            new_key, label, note = m["target"], "", m["note"]
        else:
            if not windows:
                out.append({**base, "action": "keep_region",
                            "reason": f"{suspect.name}: no era polity row in the DB for this land; "
                                      "the modern row stands for the region"})
                continue
            if rel["type"] in MANUAL_ONLY_TYPES:
                out.append({**base, "action": "list", "reason": f"{rel['type']}: decided by hand only"})
                continue
            if years is None:
                out.append({**base, "action": "keep_region", "reason": "no year in the link, its text or the other endpoint"})
                continue
            w = era_pick(windows, years)
            if w is None:
                out.append({**base, "action": "keep_region",
                            "reason": f"no era row covers {years[0]}..{years[1]} for {suspect.name}"})
                continue
            new_key, label, land_ok, rule_ok = w[2], w[3], w[4], w[5]
            if rel["type"] in LAND_TYPES and not land_ok:
                out.append({**base, "action": "keep_region", "era_row": label, "reason": _LAND})
                continue
            if rel["type"] == "rules" and other.type == "person" and not rule_ok:
                out.append({**base, "action": "keep_region", "era_row": label, "reason": _GOV})
                continue
            note = f"{suspect.name} {years[0]}..{years[1]} -> {label}"
        new = ent(new_key)
        ns, nt = (new, other) if side == "source" else (other, new)
        if reverse:
            ns, nt = nt, ns
        elif inverted(rel["type"], ns.type, nt.type):
            ns, nt, reverse = nt, ns, True
            note += "; reversed (endpoint types fit only the other way round)"
        row = {**base, "era_row": new.name, "reverse": "yes" if reverse else "",
               "new_source_id": ns.id, "new_source": ns.name, "new_target_id": nt.id, "new_target": nt.name}
        if ns.id == nt.id:
            out.append({**row, "action": "keep_region", "reason": _SELF})
            continue
        if excluded(ns.id, excl) or excluded(nt.id, excl):
            out.append({**row, "action": "skip", "reason": "new endpoint excluded (merge review / user decision)"})
            continue
        if era_problem(rel["type"], ns, nt) is not None:
            out.append({**row, "action": "list", "reason": f"new pair still out of era; proposed: {note}"})
            continue
        triple = (ns.id, nt.id, rel["type"])
        twin = planned.get(triple) or next((t for t in triples.get(triple, []) if t != rid), None)
        if twin:
            out.append({**row, "action": "duplicate_of", "reason": f"corrected link already exists as {twin}; {note}"})
            continue
        planned[triple] = rid
        out.append({**row, "action": "repoint", "reason": note})
    return out


# ── new rows: spec, import ──────────────────────────────────────────────────

def build_spec() -> Path:
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    lines = []
    for q, s in NEW_ROWS.items():
        cites = [{"source_type": "reference", "title": f"Wikidata:{q}", "url": f"https://www.wikidata.org/wiki/{q}",
                  "reliability": "reference"}]
        if s.get("enwiki"):
            cites.append({"source_type": "reference", "title": f"Wikipedia: {s['enwiki']}",
                          "url": "https://en.wikipedia.org/wiki/" + s["enwiki"].replace(" ", "_"),
                          "reliability": "reference"})
        lines.append({"name": s["name"], "entity_type": "political_entity", "entity_group": "POLITY",
                      "wikidata_id": q, "summary": s["summary"], "alternative_names": s["aliases"],
                      "temporal_start": s["start"], "temporal_end": s["end"],
                      "attributes": {"political_subtype": s["subtype"]},
                      "verification_status": "pipeline_draft", "confidence": "medium",
                      "source_citations": cites, "date_method": "source_database",
                      "date_confidence": s["date_confidence"], "duration_type": "period"})
    path = BATCH_DIR / "entities.jsonl"
    path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines), encoding="utf-8")
    print(f"{len(lines)} records -> {path}")
    return path


def artisan(*args: str) -> str:
    res = subprocess.run([*COMPOSE, "exec", "-T", "app", "php", "artisan", *args], capture_output=True, text=True)
    print(f"$ artisan {' '.join(args)[:140]}\n{res.stdout.strip()[-1500:]}{res.stderr.strip()[-800:]}")
    if res.returncode != 0:
        raise SystemExit(f"artisan {args[0]} failed ({res.returncode})")
    return res.stdout


def import_rows() -> None:
    path = f"{CONTAINER_BATCH}/entities.jsonl"
    check = artisan("tinker", "--execute", f"""foreach (file("{path}") as $l) {{ $r = json_decode($l, true);
        $x = (new App\\Jobs\\ImportEntityJob($r, "dedup-check"))->findExisting($r);
        echo "DEDUP ", $r["wikidata_id"], " ", $x["entity"]?->entity_id ?? "-", " ", $x["rejected_qid"] ?? "-", " ", $x["namesake"] ?? "-", PHP_EOL; }}""")
    clashes = [ln for ln in check.splitlines() if ln.startswith("DEDUP") and ln.split()[2:] != ["-", "-", "-"]]
    if clashes:
        raise SystemExit("would merge into or clash with existing rows; fix NEW_ROWS first:\n" + "\n".join(clashes))
    artisan("pipeline:import", path, "--sync", "--skip-relationships", "--skip-images", f"--batch-id={BATCH}")
    conn = connect()
    cur = conn.cursor()
    cur.execute("""SELECT e.wikidata_id, e.entity_id::text, e.name, e.verification_status::text, t.start_year, t.end_year,
                          t.date_method::text, t.date_confidence::text, e.created_by
                   FROM entities e LEFT JOIN entity_temporal_ranges t ON t.entity_id = e.entity_id AND t.is_primary
                   WHERE e.created_by = %s ORDER BY e.name""", (f"pipeline:{BATCH}",))
    got = cur.fetchall()
    rows = [{"qid": q, "entity_id": i, "name": n, "verification_status": v, "start_year": s, "end_year": e,
             "date_method": dm, "date_confidence": dc, "created_by": cb, "note": NEW_ROWS.get(q, {}).get("note", "")}
            for q, i, n, v, s, e, dm, dc, cb in got]
    write_csv(OUT / "created-rows.csv", rows, list(rows[0]) if rows else ["qid"])
    print(f"{len(rows)} rows created -> created-rows.csv")
    for r in rows:
        if str(r["start_year"]) != NEW_ROWS[r["qid"]]["start"] or str(r["end_year"]) != NEW_ROWS[r["qid"]]["end"]:
            print(f"  WARNING dates differ for {r['name']}: {r['start_year']}..{r['end_year']}")


# ── backup, apply, rollback ─────────────────────────────────────────────────

def backup() -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = OUT / f"backup-{stamp}.dump"
    with path.open("wb") as fh:
        subprocess.run([*COMPOSE, "exec", "-T", "db", "pg_dump", "-U", "history-mapped", "-Fc",
                        "-t", "relationships", "-t", "entities", "-t", "entity_temporal_ranges", "-t", "entity_aliases",
                        "history-mapped"], stdout=fh, check=True)
    if path.stat().st_size < 1000:
        raise SystemExit(f"backup {path} looks empty")
    print(f"backup: {path}")
    return path


def _lit(v: Any) -> str:
    return "NULL" if v is None else "'" + str(v).replace("'", "''") + "'"


class _Rollback(Exception):
    pass


def _redate(cur, rows) -> tuple[list[dict[str, Any]], list[str]]:
    """REDATE, guarded. The table's trigger derives start_year/end_year from the
    start_date/end_date text, so both are written (and checked afterwards)."""
    applied, rb = [], []
    for prefix, field, old, new, why in REDATE:
        eid = resolve(prefix, rows, {})
        text = "start_date" if field == "start_year" else "end_date"
        cur.execute(f"""UPDATE entity_temporal_ranges SET {text} = %s, {field} = %s, date_method = 'source_database'
                        WHERE entity_id = %s AND is_primary AND {field} = %s AND {text} = %s
                        RETURNING {field}""", (str(new), new, eid, old, str(old)))
        res = cur.fetchall()
        ok = len(res) == 1 and res[0][0] == new
        applied.append({"relationship_id": "", "action": "redated_entity" if ok else "redate_skipped_changed",
                        "old_source_id": eid, "old_source": rows[eid].name,
                        "reason": f"{field} {old} -> {new}: {why}"})
        if ok:
            rb.append(f"UPDATE entity_temporal_ranges SET {text} = {_lit(str(old))}, {field} = {old} "
                      f"WHERE entity_id = {_lit(eid)} AND is_primary AND {field} = {new} AND {text} = {_lit(str(new))};")
    return applied, rb


def redate_only(conn) -> None:
    """Run REDATE alone (after --apply) and patch applied.csv / rollback.sql."""
    rows = load_rows(conn)
    conn.commit()
    conn.autocommit = True
    cur = conn.cursor()
    with conn.transaction():
        got, rb = _redate(cur, rows)
    print(f"redate: {[g['action'] for g in got]}")
    path = OUT / "applied.csv"
    with path.open(newline="", encoding="utf-8") as fh:
        applied = [a for a in csv.DictReader(fh) if not a["action"].startswith(("redate", "redated"))]
    write_csv(path, got + applied, FIELDS)
    sql = (OUT / "rollback.sql").read_text(encoding="utf-8").splitlines()
    sql = [ln for ln in sql if not ln.startswith("UPDATE entity_temporal_ranges")]
    at = sql.index("COMMIT;") if not any(ln.startswith("-- rows created") for ln in sql) else \
        next(i for i, ln in enumerate(sql) if ln.startswith("-- rows created"))
    (OUT / "rollback.sql").write_text("\n".join(sql[:at] + rb + sql[at:]) + "\n", encoding="utf-8")
    bad = 0
    try:
        with conn.transaction():
            for st in rb:
                cur.execute(st)
                bad += cur.rowcount < 1
            raise _Rollback
    except _Rollback:
        pass
    print(f"rollback test: {len(rb) - bad}/{len(rb)} date statements hit their rows (rolled back)")


def apply(conn) -> None:
    planned = plan(conn)
    write_csv(OUT / "planned.csv", planned, FIELDS)
    todo = [p for p in planned if p["action"] == "repoint"]
    if any(p["new_source_id"].startswith("NEW:") or p["new_target_id"].startswith("NEW:") for p in todo):
        raise SystemExit("new rows not imported yet: run --import first")
    rows = load_rows(conn)
    conn.commit()
    conn.autocommit = True
    cur = conn.cursor()
    applied: list[dict[str, Any]] = []
    rb_rels: list[str] = []
    rb_dates: list[str] = []
    with conn.transaction():
        got, rb_dates = _redate(cur, rows)
        applied += got
        for p in todo:
            cur.execute("""UPDATE relationships SET source_entity_id = %s, target_entity_id = %s
                           WHERE relationship_id = %s AND source_entity_id = %s AND target_entity_id = %s
                                 AND relationship_type = %s::relationship_type""",
                        (p["new_source_id"], p["new_target_id"], p["relationship_id"],
                         p["old_source_id"], p["old_target_id"], p["relationship_type"]))
            if cur.rowcount != 1:
                applied.append({**p, "action": "skipped_changed_concurrently"})
                continue
            applied.append({**p, "action": "applied"})
            rb_rels.append(
                f"UPDATE relationships SET source_entity_id = {_lit(p['old_source_id'])}, "
                f"target_entity_id = {_lit(p['old_target_id'])} WHERE relationship_id = {_lit(p['relationship_id'])} "
                f"AND source_entity_id = {_lit(p['new_source_id'])} AND target_entity_id = {_lit(p['new_target_id'])};")
    applied.append({"relationship_id": "", "action": "note",
                    "reason": "Russia d6eef6d2 / Russian Empire bee08f41 QID swap NOT done (not needed for the "
                              "re-points); leave it to the leftovers pass"})
    created = []
    if (OUT / "created-rows.csv").exists():
        with (OUT / "created-rows.csv").open(newline="", encoding="utf-8") as fh:
            created = [r["entity_id"] for r in csv.DictReader(fh)]
    rb_new = []
    if created:
        ids = ", ".join(_lit(c) for c in created)
        rb_new = [f"-- rows created by pipeline:import ({BATCH}); deleted only if nothing else links them",
                  f"DELETE FROM entities e WHERE e.entity_id IN ({ids}) AND e.created_by = 'pipeline:{BATCH}' "
                  f"AND NOT EXISTS (SELECT 1 FROM relationships r WHERE r.source_entity_id = e.entity_id "
                  f"OR r.target_entity_id = e.entity_id);"]
    (OUT / "rollback.sql").write_text(
        f"-- fix_era_gaps, applied {dt.datetime.now().isoformat(timespec='seconds')}\n"
        "-- restores re-pointed endpoints and the re-dated range (each guarded on the value written),\n"
        "-- then removes the imported rows that no longer carry links\nBEGIN;\n"
        + "\n".join(rb_rels + rb_dates + rb_new) + "\nCOMMIT;\n", encoding="utf-8")
    write_csv(OUT / "applied.csv", applied, FIELDS)
    print(f"applied: {dict(Counter(a['action'] for a in applied))}")
    stmts = rb_rels + rb_dates
    bad = 0
    try:
        with conn.transaction():
            for s in stmts:
                cur.execute(s)
                bad += cur.rowcount < 1
            for s in rb_new[1:]:
                cur.execute(s)
                deleted = cur.rowcount
            raise _Rollback
    except _Rollback:
        pass
    print(f"rollback test: {len(stmts) - bad}/{len(stmts)} statements hit their rows"
          + (f", {deleted}/{len(created)} created rows removable" if rb_new else "") + " (rolled back)")


def touched() -> list[str]:
    with (OUT / "applied.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    ids = {x for a in rows if a["action"] == "applied"
           for x in (a["old_source_id"], a["old_target_id"], a["new_source_id"], a["new_target_id"]) if x}
    ids |= {a["old_source_id"] for a in rows if a["action"] == "redated_entity"}
    if (OUT / "created-rows.csv").exists():
        with (OUT / "created-rows.csv").open(newline="", encoding="utf-8") as fh:
            ids |= {r["entity_id"] for r in csv.DictReader(fh)}
    return sorted(ids)


def rebuild(ids: list[str]) -> None:
    fails: list[str] = []
    for i in range(0, len(ids), 40):
        chunk = ids[i:i + 40]
        script = " ; ".join(f"php artisan timeline:rebuild {e} >/dev/null 2>&1 || echo FAIL {e}" for e in chunk)
        res = subprocess.run([*COMPOSE, "exec", "-T", "app", "sh", "-c", script], capture_output=True, text=True)
        fails += [ln for ln in res.stdout.splitlines() if ln.startswith("FAIL")]
        print(f"  timelines {min(i + 40, len(ids))}/{len(ids)}", flush=True)
    (OUT / "rebuild.log").write_text(f"timeline:rebuild {len(ids)} entities, {len(fails)} failed\n"
                                     + "\n".join(fails) + "\n")
    print(f"timeline:rebuild for {len(ids)} entities, {len(fails)} failed")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    for flag in ("build-spec", "backup", "import", "apply", "redate", "rebuild"):
        ap.add_argument(f"--{flag}", dest=flag.replace("-", "_") + ("_" if flag == "import" else ""),
                        action="store_true")
    args = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    if args.build_spec:
        build_spec()
        return 0
    if args.backup:
        backup()
        return 0
    if args.import_:
        import_rows()
        return 0
    if args.rebuild:
        rebuild(touched())
        return 0
    conn = connect(read_only=not (args.apply or args.redate))
    if args.redate:
        redate_only(conn)
        return 0
    if args.apply:
        apply(conn)
        return 0
    planned = plan(conn)
    write_csv(OUT / "planned.csv", planned, FIELDS)
    print(f"worklist: {len(planned)}")
    for k, v in sorted(Counter(p["action"] for p in planned).items()):
        print(f"  {k:14s} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
