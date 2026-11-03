#!/usr/bin/env python3
"""Fix the identity audit's ``endpoint_era`` relation flags, half B.

Slice: ``output/audit/identity-20261031/relation-flags.csv`` rows with
``check=endpoint_era``, ``severity=high`` and a ``relationship_id`` starting
8-f (another agent has 0-7). A flag means the two endpoints' lifetimes lie
more than the C2 tolerance apart, so one endpoint (or the relationship's own
years) belongs to another era.

What this script changes (local DB only, every write guarded on the value it
read, one transaction):

* ``era`` rule (mechanical): one endpoint is a modern-state row used for a
  historical polity -- "France" (Q142, dated 1958), "Egypt" (Q79, 1922),
  "Russia" (1991) ... -- and the relationship's years fall inside exactly one
  historical polity row of that country from the curated ``ERA`` table below
  (Kingdom of France, Tsardom of Russia, New Kingdom of Egypt ...). Nested
  rows (First French Empire inside Kingdom of France) pick the narrowest; two
  overlapping siblings (Wattasid / Saadi Morocco) are ambiguous and skipped.
  The years come from the relationship, else from its description, else from
  the other endpoint when that is a person or event with a short known span.
* ``manual`` decisions: the namesake endpoint is re-pointed to the correct
  existing row (same name/alias, same type, era match), judged by hand per
  row and listed in ``MANUAL``.
* ``set_years``: a relationship year corrected from Wikidata.
* ``redate``: an entity's primary range corrected from the source that
  states it (``REDATE``).

Everything else is listed in planned.csv with a reason (action ``list``):
rows that carry a namesake's QID, missing namesake rows, region/people rows
with unsourced dates, relations that look unreal. Nothing is deleted.

Usage (from the repo root):

    scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit.fix_relation_eras_b            # plan
    scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit.fix_relation_eras_b --apply    # backup + apply
    scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit.fix_relation_eras_b --test-rollback
    scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit.fix_relation_eras_b --rebuild  # timeline:rebuild touched
"""
from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from pipeline.audit.common import COMPOSE, REPO, dsn
from pipeline.audit.dates import row_range, tolerance

FLAGS = REPO / "output" / "audit" / "identity-20261031" / "relation-flags.csv"
VERDICTS = REPO / "output" / "audit" / "merge-review-20261101" / "verdicts.csv"
OUT = REPO / "output" / "audit" / "relfix-era-b-20261101"
SLICE = set("89abcdef")
USER_DECISION_PREFIXES = ("a05afb75", "6255478f", "17d96812", "7baeedc3")
TAG = "relfix-era-b-20261101"

# ── era table: modern-state row -> historical polity rows of that country ─────
# (entity_id, first year, last year, name). The window is the row's own span,
# narrowed where its QID's Wikidata dates are narrower (Kingdom of Poland
# Q8890160 ends 1569, Tibetan Empire Q2431480 ends 842). Rows left out on
# purpose: "Aegyptus" (QID is the mythological son of Belus), the Old/Middle
# Kingdom and Intermediate Period rows (their spans disagree with their QIDs),
# duplicate rows without a QID ("Second French Republic", "Sultanate of
# Gujarat"), colonies nested inside a mother state (New France).
FRANCE = "1c3befeb-626d-472d-924f-a41d4b3fcc53"
EGYPT = "9de131ab-5534-423b-aed0-127f4728d99b"
RUSSIA = "d6eef6d2-208c-45b2-84e0-478d8ca659f0"
ERA: dict[str, list[tuple[str, int, int, str]]] = {
    FRANCE: [
        ("fe91f6d0-cf18-4fc9-a0d5-061e3d772bf9", 843, 987, "West Francia"),
        ("b78831f7-5989-4ece-8a72-af25a72bb795", 987, 1848, "Kingdom of France"),
        ("06ddcac7-11fd-47a2-b0a7-e1f41c6c9057", 1792, 1804, "French First Republic"),
        ("8f25d3e1-81e4-4ba0-b964-1e50f2c20428", 1804, 1815, "First French Empire"),
        ("bfa2fff5-8f3b-4748-8fbc-074ac624a594", 1848, 1852, "French Second Republic"),
        ("7a5f13d3-5e65-430f-abd8-1b0b01431730", 1852, 1870, "Second French Empire"),
        ("c50f4e81-3787-4514-ad03-0b07b7e62ee8", 1870, 1940, "French Third Republic"),
        ("acf5cb18-f7a4-4203-8357-d2a1842a57be", 1946, 1958, "Fourth French Republic"),
    ],
    EGYPT: [
        ("4aabfa9f-99b6-4363-9e5b-099a43b4002b", -4000, -30, "Ancient Egypt"),
        ("87f1e78a-6bd1-4604-8256-dcbfdd85c371", -1540, -1087, "New Kingdom of Egypt"),  # ±10y margin
        ("51d71ed2-e636-41c9-85bb-e65560370161", -305, -30, "Ptolemaic Egypt"),
        ("72d3329d-51e5-41b1-8dbf-9755ff9283b2", -30, 395, "Roman Egypt"),
        ("a5b04899-d744-4ed4-bbab-fced6f1ebbc6", 1517, 1867, "Ottoman Egypt"),
        ("fc65419f-7f95-4384-907e-3813575ef82e", 1867, 1914, "Khedivate of Egypt"),
    ],
    RUSSIA: [
        ("2d931bbf-31a7-4447-acaf-1aa76f7370a5", 1547, 1721, "Tsardom of Russia"),
        ("bee08f41-6dbc-46fa-8bb7-6cdc4aceabb8", 1721, 1917, "Russian Empire"),
    ],
    "376426ae-ce29-4293-be07-5c7bf934f2b0": [  # Austria (Q40, 1918)
        ("8c57d738-cbba-4ec4-b72b-d8ecd92a8fee", 1526, 1918, "Habsburg Monarchy"),
        ("b3436059-3f8b-4e9f-b145-7aac47defb0c", 1804, 1867, "Austrian Empire"),
        ("99974943-64d3-4846-81db-79ef78e88dc5", 1867, 1918, "Austria-Hungary"),
    ],
    "98b5080f-01b1-4f06-b279-376d2d524ceb": [  # "United Provinces" (QID = Rio de la Plata)
        ("e835047d-cca3-4317-a7f7-4025ec187443", 1581, 1795, "Dutch Republic"),
    ],
    "69cb1bf0-8760-41d1-8f31-be803b8b783e": [  # Israel (Q801, 1948)
        ("27d5cabf-f25e-4808-894e-768dc98b8562", -930, -722, "Kingdom of Israel"),
    ],
    "2ac323cb-6af6-4fd0-a0d3-e1295cf4bb0c": [  # Poland (Q36, 1918)
        ("054270a3-b784-47ac-bb04-979f3653a0dd", 1385, 1569, "Kingdom of Poland"),
        ("d36f70ea-e835-468f-ac3e-336604675343", 1569, 1795, "Polish-Lithuanian Commonwealth"),
    ],
    "df06c8b0-9758-41bc-aa7d-f8050555d92a": [  # Mali (Q912, 1960)
        ("dd10f12d-7727-4e54-b2a8-4e60eb502034", 1235, 1610, "Mali Empire"),
    ],
    "d7e394ae-4616-4299-9b84-bc568b1dbfcc": [  # Norway (Q20, 1905)
        ("3140fc0c-b8ac-49a7-b081-e55c8d45efb0", 872, 1397, "Kingdom of Norway"),
        ("a915ca2e-90ec-4484-9875-b9fe096e62a7", 1536, 1814, "Denmark-Norway"),
    ],
    "435bedec-7cdc-464b-97e2-d82601c0d677": [  # Tibet (Q2444884, 1912-1959)
        ("bbb2ec8a-7d81-4a0d-921b-f9d8f315ecde", 618, 842, "Tibetan Empire"),
    ],
    "38b25b9c-b3ab-4896-a1ae-320c6de0c299": [  # Sri Lanka (Q854, 1972)
        ("48da4229-9173-4c39-a8c6-c4ab13e7b8ba", -377, 1017, "Anuradhapura Kingdom"),
    ],
    "0d03589a-2ee2-497f-afe4-0bb549fbad5a": [  # Lithuania (Q37, 1990)
        ("41e4db71-27b3-49dd-b9d8-6ef37ad9324a", 1236, 1795, "Grand Duchy of Lithuania"),
    ],
    "9a540091-4bdc-4313-b41d-1112e86c86f0": [  # Cyprus (Q229, 1960)
        ("67b3ef53-8d20-439d-89c0-f8b5b16f66ef", 1192, 1489, "Kingdom of Cyprus"),
    ],
    "8160360a-5b7d-45c0-96f7-3e0446a44bdc": [  # Republic of the Philippines (Q928, 1946)
        ("655ccb0a-4654-4c37-9403-4d2a3e7d8df4", 1571, 1898, "Spanish East Indies"),
    ],
    "d7d5d32a-f33f-42a4-beb8-943c29b25f42": [  # Morocco (Q1028, 1956)
        ("cf8b3105-6338-49a6-a30d-9d597c99d0c1", 1420, 1554, "Wattasid dynasty"),
        ("28ed2a1c-5ce8-4531-9798-4f24ff98d23d", 1510, 1659, "Saadi Sultanate"),
    ],
    "a59ab6c1-bc59-49ec-abb4-655d3493133f": [  # Gujarat (Q1061, 1960)
        ("11384d70-10da-4966-ac8b-3fe6a0cfdbe1", 1407, 1573, "Gujarat Sultanate"),
    ],
    "ad66ff5a-3b4d-4930-80e3-b0cd4a36d495": [  # Iran (Q794, 1979)
        ("57943992-50db-405c-9f1f-548c423d96cd", -550, 1978, "Persia"),
    ],
    "bcc8836d-24be-4433-ae9d-9ea99d6089f4": [  # Burma (Q836, 1948)
        ("2f70ca84-54a6-4c4f-b771-11151351469f", 1510, 1599, "Toungoo"),
        ("6de0e00e-74e0-4351-a5b6-37c0c2ee44ac", 1752, 1885, "Konbaung Kingdom"),
    ],
    "48d42e2f-c4e4-4f81-8225-6305eb841c0f": [  # Armenia (Q399, 1991)
        ("4201a1b0-a1d7-47e6-a721-d44d65a40795", 1080, 1375, "Cilician Armenia"),
    ],
}
# Relation types whose modern-state endpoint is not simply "the state at the time".
ERA_SKIP_TYPES = {"succeeded_by", "preceded_by", "founded", "member_of_dynasty", "child_of",
                  "parent_of", "sibling_of", "married_to"}
# Relationships judged by hand to point the wrong way; re-pointing would keep the error.
ERA_SKIP_RIDS = {
    "e4568f90",  # "Ptolemy I controlled_by Egypt": Ptolemy controlled Egypt (reversed)
    "f91a9768",  # "Rome controlled_by Egypt": reversed
    "9151320b",  # "Rome controlled_by Cyprus": reversed
    "8dfb92a7",  # "Ithobaal I controlled_by Cyprus": reversed
    "f2b65309",  # "Gujarat controlled_by Gujarat Sultanate": would loop onto itself
}

# ── manual decisions (judged row by row) ──────────────────────────────────────
ENT = {  # short names for re-point targets
    "arsaces_i_parthia": "cbea5a76-a007-46a2-a28c-3baeb1754e75",
    "boniface_missionary": "f2ae71d4-d3b0-403f-9b4e-01e39e6f17ff",
    "charles_leclerc_general": "5110f7fb-c19a-4b67-917f-a45ddadc118e",
    "sciarra_colonna": "a17a4aa4-45a5-458b-b0a3-4ded95f60bd0",
    "galdan_boshugtu": "5b568c33-5fe6-41db-89cd-40fe26e97851",
    "han_dynasty": "0d64232f-a5e9-43d4-bfb1-c859e7455321",
    "ibrahim_pasha_egypt": "821ee7c2-0537-4ed5-b35f-acca874ab575",
    "mahmud_of_ghazni": "b5529392-b75d-4875-818b-c000879f55ce",
    "mataram_sultanate": "3333b121-fac7-4491-bda3-dda4aff7413c",
    "piet_heyn_admiral": "7cdb0050-6c8e-424a-9a25-92a9694e4a51",
    "rome_city": "ee6bb2d1-30c8-43dd-9449-67544851f0ce",
    "sultanate_of_rum": "9ebf6bee-3d78-4a23-b260-4500e1af2197",
    "electorate_of_saxony": "6e3c5b7f-2c4f-484f-a321-c8d749e0985b",
    "dyrrhachium_1081": "8649cc89-3f90-4523-af32-c2e7169ee1a7",
    "megiddo_609bce": "3c406424-c0bf-415b-b7a2-a86d78fd4ee6",
    "siege_of_acre_1799": "44f195fb-0cdf-46b9-b8c0-93ea1c661a0d",
    "capture_jerusalem_1917": "1aac7bba-8a20-4c5b-8763-b0c077e6e55a",
    "persians_capture_jerusalem": "cbf05858-f864-44c3-8ff2-a28300aa1313",
    "diet_of_worms_829": "8052d2a5-8880-46e3-913f-137b81cc5cec",
    "gothic_war_535": "2bbe43e6-4aa4-48b2-9e69-e488ab0a0dcc",
    "conquest_county_edessa": "1e5e5245-92a0-4c55-bd77-7cdba0214e99",
    "henry_vi_england": "0374a4bb-b3ab-4c7a-87bf-fecdbbdf4f72",
    "philip_v_spain": "5cac379b-77c3-4913-af9b-ded59084b127",
    "caliphate_of_cordoba": "039cde8b-557c-4fe9-9918-778baa142c67",
    "middle_kingdom_egypt": "7ccd0ab9-9d0d-4dea-b203-46a128a7208c",
    "prc": "90f167d3-dbad-4b2f-84fa-49670b25b0a8",
    "roc": "e4eea5f2-e346-47de-947f-00a5f810b52e",
    "qing": "e06c397a-8faf-4f40-a527-23b9a81a10a8",
    "tang": "7ddfaf8b-6264-4c66-a873-00548eb4dc7b",
    "lusitanians": "13f94693-d5ae-4aef-84f6-c37460258fc9",
    "uyghurs": "fe013fc2-a6d3-4034-9760-0bca311282d6",
    "massachusetts_bay_company": "23389a2d-e95b-42d3-b93a-43ff0e3ff49d",
}
# rid prefix -> (side to re-point, target key, swap direction afterwards, why)
MANUAL: dict[str, tuple[str, str, bool, str]] = {
    "b7c7899a": ("S", "arsaces_i_parthia", False, "Arsaces I row carries Arsaces I of Armenia (Q2716107, d. 35 CE)"),
    "ee82ba5c": ("T", "arsaces_i_parthia", False, "Arsaces I row carries Arsaces I of Armenia (Q2716107, d. 35 CE)"),
    "91f88936": ("S", "boniface_missionary", False, "row is Pope Boniface I (d. 422); 747 is Saint Boniface"),
    "ff1f5f86": ("S", "sciarra_colonna", False, "row carries painter Angelo Michele Colonna; Anagni 1303 was Sciarra Colonna"),
    "b16b75d0": ("S", "galdan_boshugtu", True, "row 'Galdan' dated 1795; also reversed: the battle is commanded_by Galdan"),
    "eac71878": ("S", "han_dynasty", False, "'Han' row is the Han people / Warring States Han; 125 BCE is the Han dynasty"),
    "ba449c28": ("S", "han_dynasty", False, "'Han' row is the Warring States Han (ended 230 BCE)"),
    "e307cc24": ("S", "han_dynasty", False, "'Han' row is the Warring States Han (ended 230 BCE)"),
    "86ff8677": ("S", "han_dynasty", False, "'Han' row is the Warring States Han (ended 230 BCE)"),
    "a473acd7": ("S", "han_dynasty", False, "'Han' row is the Warring States Han (ended 230 BCE)"),
    "d3821508": ("T", "han_dynasty", False, "'Han' row is the Warring States Han (ended 230 BCE)"),
    "f763f513": ("S", "ibrahim_pasha_egypt", False, "row is Pargali Ibrahim Pasha (d. 1536)"),
    "c6933576": ("S", "mahmud_of_ghazni", False, "row 'Mahmud' carries an Indonesian politician (Q123885325)"),
    "b542d9ab": ("S", "mahmud_of_ghazni", False, "row 'Mahmud' carries an Indonesian politician (Q123885325)"),
    "96e63221": ("S", "mahmud_of_ghazni", False, "row 'Mahmud' carries an Indonesian politician (Q123885325)"),
    "847c3175": ("S", "mahmud_of_ghazni", False, "row 'Mahmud' carries an Indonesian politician (Q123885325)"),
    "9a53dbcd": ("T", "mahmud_of_ghazni", False, "row 'Mahmud' carries an Indonesian politician (Q123885325)"),
    "fcfc15ae": ("S", "mataram_sultanate", False, "'Mataram' row is the Hindu-Buddhist kingdom (716-1016)"),
    "b3359b40": ("S", "mataram_sultanate", False, "'Mataram' row is the Hindu-Buddhist kingdom (716-1016)"),
    "99b0bd80": ("T", "mataram_sultanate", False, "'Mataram' row is the Hindu-Buddhist kingdom (716-1016)"),
    "9c2f0776": ("T", "mataram_sultanate", False, "'Mataram' row is the Hindu-Buddhist kingdom (716-1016)"),
    "e7420e8a": ("T", "mataram_sultanate", False, "'Mataram' row is the Hindu-Buddhist kingdom (716-1016)"),
    "b31dd9f8": ("S", "piet_heyn_admiral", False, "row carries architect Piet Heyn (1857-1929)"),
    "8462bb62": ("T", "piet_heyn_admiral", False, "row carries architect Piet Heyn (1857-1929)"),
    "90d83d84": ("S", "rome_city", False, "'Rome' polity row is the Roman Republic (Q17167); 410 is the city"),
    "af7912f4": ("T", "rome_city", False, "died in the city of Rome; polity row is the Roman Republic"),
    "cce30e4e": ("T", "rome_city", False, "died in the city of Rome; polity row is the Roman Republic"),
    "a5f7717e": ("T", "rome_city", False, "died in the city of Rome; polity row is the Roman Republic"),
    "8e0fc898": ("T", "rome_city", False, "Romulus founded the city; polity row is the Republic (509-27 BCE)"),
    "fd03140e": ("T", "rome_city", False, "resided in the city of Rome"),
    "9d4ba437": ("T", "rome_city", False, "resided in the city of Rome"),
    "9e717efc": ("T", "rome_city", False, "resided in the city of Rome"),
    "94b4576a": ("T", "rome_city", False, "resided in the city of Rome"),
    "f4bfa912": ("T", "rome_city", False, "resided in the city of Rome"),
    "fcd00527": ("T", "rome_city", False, "resided in the city of Rome"),
    "c79eb676": ("T", "rome_city", False, "resided in the city of Rome"),
    "c9fc5b38": ("T", "rome_city", False, "resided in the city of Rome"),
    "f6c5af42": ("S", "sultanate_of_rum", False, "'Rum' row carries the drink (Q83376)"),
    "9b8e0823": ("T", "sultanate_of_rum", False, "'Rum' row carries the drink (Q83376)"),
    "93f0409f": ("S", "electorate_of_saxony", False, "'Saxony' row is the Duchy (804-1296)"),
    "c42187d7": ("S", "electorate_of_saxony", False, "'Saxony' row is the Duchy (804-1296)"),
    "ee7a6942": ("S", "electorate_of_saxony", False, "'Saxony' row is the Duchy (804-1296)"),
    "be0f0d41": ("T", "electorate_of_saxony", False, "'Saxony' row is the Duchy (804-1296)"),
    "e2325a84": ("T", "dyrrhachium_1081", False, "'Battle of Dyrrhachium' row is 48 BCE"),
    "e8c382ae": ("T", "megiddo_609bce", False, "'Battle of Megiddo' row is 1457 BCE"),
    "f9aa8843": ("T", "megiddo_609bce", False, "'Battle of Megiddo' row is 1457 BCE"),
    "b183909c": ("T", "siege_of_acre_1799", False, "'Siege of Acre' QID row is 1189-1191"),
    "aa06c490": ("T", "siege_of_acre_1799", False, "'Siege of Acre' QID row is 1189-1191"),
    "82233a0f": ("T", "capture_jerusalem_1917", False, "'Capture of Jerusalem' row is dated 1187"),
    "e4b566b1": ("T", "capture_jerusalem_1917", False, "'Capture of Jerusalem' row is dated 1187"),
    "a36e7f99": ("T", "persians_capture_jerusalem", False, "the 614 Sasanian capture has its own row"),
    "eb2b5747": ("T", "diet_of_worms_829", False, "'Diet of Worms' QID row is 1521"),
    "f61029ef": ("T", "gothic_war_535", False, "'Gothic War' QID row is 457-458 (row 376-382); Totila's is 535-554"),
    "c61564b9": ("S", "conquest_county_edessa", False, "'Siege of Edessa' row is 544; Zengi's 1144 siege has its own row"),
    "d16649c2": ("T", "conquest_county_edessa", False, "'Siege of Edessa' row is 544; Zengi's 1144 siege has its own row"),
    "a13bddca": ("T", "henry_vi_england", False, "'Henry VI' row is the Holy Roman Emperor (d. 1197)"),
    "9eb92beb": ("T", "philip_v_spain", False, "'Philip of Anjou' row is the despot of Romania (d. 1331)"),
    "a7f028de": ("T", "caliphate_of_cordoba", False, "al-Hakam II was caliph of Cordoba, not of the Umayyad Caliphate (661-750)"),
    "b215d2df": ("T", "middle_kingdom_egypt", False, "description: succeeded by the Middle Kingdom; target was 'China'"),
    "b4b7601c": ("S", "prc", False, "'China' row is the cultural region (-1000..500); 1988 is the PRC"),
    "b73e5f86": ("S", "prc", False, "'China' row is the cultural region; 1980 is the PRC"),
    "e484b5bc": ("S", "prc", False, "'China' row is the cultural region; 1979 is the PRC"),
    "b0f57bde": ("S", "prc", False, "'China' row is the cultural region; 1979 is the PRC"),
    "cb91eaa6": ("S", "prc", False, "'China' row is the cultural region; 1950 is the PRC"),
    "890710a5": ("T", "prc", False, "'China' row is the cultural region; 1988 is the PRC"),
    "ec6d09ee": ("T", "prc", False, "'China' row is the cultural region; 1979 is the PRC"),
    "ff304fd5": ("T", "prc", False, "'China' row is the cultural region; 1969 is the PRC"),
    "ec3015e2": ("T", "prc", False, "'China' row is the cultural region; 1992-1999 is the PRC"),
    "b75b8302": ("T", "roc", False, "'China' row is the cultural region; 1943 is the Republic of China"),
    "eebb2c8f": ("T", "qing", False, "'China' row is the cultural region; 1807 is Qing China"),
    "ef9537e1": ("T", "tang", False, "'China' row is the cultural region; Yijing was born in Tang China"),
    "862a8b99": ("T", "lusitanians", False, "'Lusitania' row is the Roman province (27 BCE-409); Viriathus led the Lusitanians"),
    "cd61aa6c": ("T", "uyghurs", True, "description: the Turkic Khaganate controlled the Uyghur people; "
                                         "target was the Uyghur Khaganate (744-840) and the direction was reversed"),
    "d2d098c6": ("T", "massachusetts_bay_company", False, "'Massachusetts' row is the US state (1788); "
                                                           "Winthrop governed the Massachusetts Bay Company's colony"),
}
# Relationship years corrected from a source: rid prefix -> (start, end, source).
SET_YEARS: dict[str, tuple[str, str, str]] = {
    "ef9537e1": ("635", "635", "born_in year = Yijing's birth, Wikidata Q457629 P569 635 (was 700)"),
}
# Entity primary-range corrections: (entity_id, field, old, new, source).
REDATE: list[tuple[str, str, str, str, str]] = [
    ("bcb8b5d8-73c2-4676-83ec-692b82c84e07", "end_date", "1400", "1804",
     "Dai Viet end 1400->1804: enwiki 'Đại Việt' ('lasted until ... the name was changed to Việt Nam in 1804'); "
     "Wikidata Q430309 '(1054 - 1400; 1428 - 1804)'. The 1400-1428 Ho/Ming interval is inside the span."),
]
# Rows judged by hand that need a human decision (relation looks unreal as typed).
NOT_REAL = {
    "b5316792": "Alexander the Great child_of Herod: Herod's son Alexander (executed 7 BCE) has no row",
    "e5a70534": "Athenaeus (c. 200 CE) 'participated_in' Posidonius: a citation, not a contemporaneous relation",
    "cabf8af7": "Kangxi resided_in Confucius: the target should be Qufu / the Temple of Confucius",
    "d33cc40a": "Mustafa Kemal Ataturk succeeded_by Suleiman: about Sehzade Mustafa (d. 1553); not a succession",
    "9c7545d8": "Treaty of Bucharest (1913) signed_by ancient Macedonia: the region was partitioned, not a signatory",
    "dc35dc5b": "Sinn Fein participated_in Kingdom of Ireland (1542-1801): wrong target",
    "e228446d": "Queen Victoria parent_of Victorinus: the mother is Victoria of the Gallic Empire (no row)",
    "bc5d41d9": "Livonian Order controlled_by Prussia (1701-1947): wrong target/direction",
    "8d9c6542": "Bayezid II succeeded_by Cem: Cem was his rival (and the 'Cem' row is Cem Ozdemir)",
    "9b56179f": "Kingdom of Italy controlled_by Cyrenaica: reversed; Cyrenaica row is the ancient region",
    "fbe8f67c": "Gaozu succeeded_by Emperor Cheng: not a direct succession",
    "9ff6166b": "Mahmud participated_in the Moroccan occupation (1594): neither Mahmud row fits the description",
    "d4c2c70a": "deposition of Romanos I (944) was by Constantine Lekapenos (no row), not Constantine the Great",
    "e1778156": "Fehrbellin 1675 was led by Waldemar von Wrangel (no row); 'Wrangel' row is the 19th-c. admiral",
    "bea4f1b7": "Revolt of 366 BCE was led by Ariobarzanes of Phrygia (no row); candidate Ariobarzanes of Persis is another man",
    "e5fe0761": "Jehoahaz of Judah (609 BCE) has no row; 'Jehoahaz' is the king of Israel (814-798 BCE)",
    "a9b2aaf9": "Jehoahaz of Judah (609 BCE) has no row; 'Jehoahaz' is the king of Israel (814-798 BCE)",
    # judged by hand: re-pointing would clear the era flag but leave a wrong relation behind
    "946e960b": "Charles Leclerc assassinated_by Toussaint: reversed and not an assassination (Toussaint died "
                "in a French prison); the 'Charles Leclerc' row carries the racing driver (correct row 5110f7fb)",
    "91e31743": "Galdan defeated_at Chechen Tayiji: Galdan was the victor and the target is a person; the "
                "'Galdan' row is dated 1795 (correct row Galdan Boshugtu Khan 5b568c33)",
    "e4f54742": "John George I rules Saxony 1645: 'John George I' row carries the Prince of Anhalt-Dessau "
                "(d. 1618); the Elector of Saxony has no row ('Saxony' target should be Electorate of Saxony)",
}

_ERA_YEAR = re.compile(r"\b(\d{1,4})(?:\s*(?:–|-|to|and)\s*(\d{1,4}))?\s*(BCE|BC|CE|AD)\b")
_PLAIN_YEAR = re.compile(r"\b(1[0-9]{3}|[5-9][0-9]{2})\b")


def desc_years(text: str | None) -> list[int]:
    """Years named in a description: era-marked first, else plain CE years >= 500."""
    ys: list[int] = []
    for m in _ERA_YEAR.finditer(text or ""):
        sign = -1 if m.group(3) in ("BCE", "BC") else 1
        ys.append(sign * int(m.group(1)))
        if m.group(2):
            ys.append(sign * int(m.group(2)))
    if not ys:
        ys = [int(m.group(1)) for m in _PLAIN_YEAR.finditer(text or "")]
    return ys


def connect(read_only: bool = True):
    conn = psycopg.connect(dsn(), row_factory=dict_row)
    conn.read_only = read_only
    return conn


def load_slice() -> list[dict[str, str]]:
    rows = []
    with FLAGS.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["check"] == "endpoint_era" and r["severity"] == "high" and r["relationship_id"][:1] in SLICE:
                rows.append(r)
    return rows


def load_exclusions() -> set[str]:
    ex: set[str] = set()
    with VERDICTS.open(encoding="utf-8") as fh:
        for v in csv.DictReader(fh):
            ex.update(x for x in (v["survivor_id"], v["loser_id"]) if x)
    return ex


def excluded(eid: str, ex: set[str]) -> bool:
    return eid in ex or eid.startswith(USER_DECISION_PREFIXES)


def load_state(conn, rids: list[str]) -> tuple[dict[str, dict], dict[str, dict], dict[tuple[str, str, str], str]]:
    rels = {r["rid"]: r for r in conn.execute(
        """select relationship_id::text rid, relationship_type::text rtype, source_entity_id::text sid,
                  target_entity_id::text tid, temporal_start, temporal_end, start_year, end_year, description
           from relationships where relationship_id = any(%s::uuid[])""", (rids,))}
    ents = {e["id"]: e for e in conn.execute(
        """select e.entity_id::text id, e.name, e.entity_type::text type, e.wikidata_id qid,
                  e.attributes->>'_rejected_wikidata_id' rejected, t.start_year s, t.end_year e
           from entities e left join entity_temporal_ranges t on t.entity_id = e.entity_id and t.is_primary""")}
    triples = {(r["s"], r["t"], r["k"]): r["id"] for r in conn.execute(
        """select relationship_id::text id, source_entity_id::text s, target_entity_id::text t,
                  relationship_type::text k from relationships""")}
    return rels, ents, triples


def ref_years(rel: dict, other: dict | None) -> tuple[list[int], str]:
    ys = [y for y in (rel["start_year"], rel["end_year"]) if y is not None]
    if ys:
        return ys, "relationship"
    if other and other["type"] == "person" and rel["rtype"] in ("born_in", "died_in"):
        y = other["s"] if rel["rtype"] == "born_in" else other["e"]
        if y is not None:
            return [y], "person's birth/death"
    ys = desc_years(rel["description"])
    if ys:
        return ys, "description"
    if other and other["s"] is not None and other["e"] is not None and other["id"] not in ERA \
            and (other["type"] == "person" or other["type"].startswith("event_")) and other["e"] - other["s"] <= 120:
        return [other["s"], other["e"]], "other endpoint"
    return [], "none"


def pick_era(hub: str, years: list[int]) -> tuple[tuple[str, int, int, str] | None, str]:
    cands = [c for c in ERA[hub] if all(c[1] <= y <= c[2] for y in years)]
    if not cands:
        return None, "no era polity row covers " + ",".join(map(str, sorted(set(years))))
    cands.sort(key=lambda c: c[2] - c[1])
    for inner, outer in zip(cands, cands[1:]):
        if not (outer[1] <= inner[1] and inner[2] <= outer[2]):
            return None, "ambiguous: " + " / ".join(c[3] for c in cands)
    pick = cands[0]
    if len(cands) > 1 and any(y in (pick[1], pick[2]) for y in years):
        # a year on the narrower row's first/last year (France 1792, 1815) may
        # still belong to the wider one
        return None, f"ambiguous: boundary year of {pick[3]} ({pick[1]}..{pick[2]}) inside {cands[1][3]}"
    return pick, ""


def gap(ents: dict, sid: str, tid: str) -> int | None:
    a, b = ents[sid], ents[tid]
    ra, rb = row_range(a["type"], a["s"], a["e"]), row_range(b["type"], b["s"], b["e"])
    if not ra or not rb:
        return None
    return max(0, max(ra[0], rb[0]) - min(ra[1], rb[1]))


def bad_side(rel: dict, ents: dict, years: list[int]) -> str:
    def inside(eid: str) -> bool:
        e = ents[eid]
        rr = row_range(e["type"], e["s"], e["e"])
        tol = tolerance(e["type"]) or 0
        return rr is None or all(rr[0] - tol <= y <= rr[1] + tol for y in years)
    if not years:
        return "?"
    s_ok, t_ok = inside(rel["sid"]), inside(rel["tid"])
    return {(True, True): "none", (True, False): "T", (False, True): "S", (False, False): "both"}[(s_ok, t_ok)]


def list_reason(rel: dict, ents: dict, side: str, wd: dict[str, dict]) -> str:
    """Why a row is left for a human (best guess from the data)."""
    rid8 = rel["rid"][:8]
    if rid8 in NOT_REAL:
        return "not_real_as_typed: " + NOT_REAL[rid8]
    sides = [side] if side in ("S", "T") else ["S", "T"]
    out = []
    for sd in sides:
        e = ents[rel["sid"] if sd == "S" else rel["tid"]]
        rec = wd.get(e["qid"] or "") or {}
        if e["id"] in ERA or (e["type"] == "political_entity" and e["s"] is not None and e["s"] >= 1789):
            out.append(f"modern_state_row:{e['name']}")
        elif e["qid"] and rec.get("label") and _norm(rec["label"]) != _norm(e["name"]) \
                and not any(_norm(a) == _norm(e["name"]) for a in rec.get("aliases", [])):
            out.append(f"endpoint_carries_other_qid:{e['name']}={e['qid']} ({rec.get('label')}: "
                       f"{(rec.get('description') or '')[:50]})")
        elif e["qid"] and rec.get("status") == "ok" and not rec.get("dates") and e["s"] is not None:
            out.append(f"unsourced_dates:{e['name']} ({e['s']}..{e['e']}; {e['qid']} has no dates)")
        elif not e["qid"] and e["rejected"]:
            out.append(f"dates_from_rejected_qid:{e['name']} (rejected {e['rejected']}, {e['s']}..{e['e']})")
        elif not e["qid"]:
            out.append(f"no_qid_row_dates:{e['name']} ({e['s']}..{e['e']})")
        else:
            out.append(f"namesake_or_era:{e['name']} ({e['s']}..{e['e']}); correct row not in DB")
    return "; ".join(out)


def _norm(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def load_wd(qids: set[str]) -> dict[str, dict]:
    """Cached Wikidata records (no network: the identity audit cache has them all)."""
    import json
    path = REPO / "output" / "audit" / "cache" / "wd-entities.jsonl"
    out: dict[str, dict] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("qid") in qids:
                out[rec["qid"]] = rec
    return out


# ── planning ─────────────────────────────────────────────────────────────────
def plan() -> tuple[list[dict[str, Any]], dict, list[dict[str, Any]]]:
    flags = load_slice()
    ex = load_exclusions()
    with connect() as conn:
        rels, ents, triples = load_state(conn, [f["relationship_id"] for f in flags])
        ranges = {r["entity_id"]: r for r in conn.execute(
            """select entity_id::text, temporal_range_id::text, start_date, end_date, notes
               from entity_temporal_ranges where is_primary and entity_id = any(%s::uuid[])""",
            ([r[0] for r in REDATE],))}
    wd = load_wd({ents[x]["qid"] for r in rels.values() for x in (r["sid"], r["tid"]) if ents[x]["qid"]})
    planned_triples: set[tuple[str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for f in flags:
        rid = f["relationship_id"]
        rel = rels.get(rid)
        row: dict[str, Any] = {"relationship_id": rid, "relationship_type": f["relationship_type"],
                               "source_id": f["source_id"], "source_name": f["source_name"],
                               "target_id": f["target_id"], "target_name": f["target_name"],
                               "rel_years": "", "years_from": "", "bad_side": "", "action": "", "side": "",
                               "old_entity_id": "", "old_entity_name": "", "new_entity_id": "",
                               "new_entity_name": "", "swap": "", "old_years": "", "new_years": "",
                               "gap_before": "", "gap_after": "", "rule": "", "reason": "",
                               "description": (f["description"] or "")[:160]}
        out.append(row)
        if rel is None:
            row.update(action="skip", reason="relationship no longer exists")
            continue
        row.update(source_id=rel["sid"], target_id=rel["tid"], source_name=ents[rel["sid"]]["name"],
                   target_name=ents[rel["tid"]]["name"], relationship_type=rel["rtype"],
                   rel_years=f"{rel['start_year']}..{rel['end_year']}", gap_before=gap(ents, rel["sid"], rel["tid"]))
        if excluded(rel["sid"], ex) or excluded(rel["tid"], ex):
            row.update(action="skip", reason="endpoint excluded (merge review / user decision)")
            continue
        rid8 = rid[:8]
        years, src = ref_years(rel, None)
        side = bad_side(rel, ents, years)
        row.update(years_from=src, bad_side=side)

        if rid8 in MANUAL:
            sd, key, swap, why = MANUAL[rid8]
            new = ENT[key]
            old = rel["sid"] if sd == "S" else rel["tid"]
            if old != (f["source_id"] if sd == "S" else f["target_id"]):
                row.update(action="list", rule="manual", reason=f"endpoint changed since the audit; not re-judged; {why}")
                continue
            new_s, new_t = (new, rel["tid"]) if sd == "S" else (rel["sid"], new)
            if swap:
                new_s, new_t = new_t, new_s
            problem = _check_repoint(rel, new_s, new_t, ents, ex, triples, planned_triples)
            row.update(side=sd, old_entity_id=old, old_entity_name=ents[old]["name"], new_entity_id=new,
                       new_entity_name=ents[new]["name"], swap="y" if swap else "", rule="manual", reason=why)
            if problem:
                row.update(action="list", reason=f"{problem}; {why}")
                continue
            row.update(action="repoint_swap" if swap else "repoint", gap_after=gap(ents, new_s, new_t),
                       new_source_id=new_s, new_target_id=new_t)
            planned_triples.add((new_s, new_t, rel["rtype"]))
            if rid8 in SET_YEARS:
                st, en, why2 = SET_YEARS[rid8]
                row.update(old_years=f"{rel['temporal_start']}|{rel['temporal_end']}", new_years=f"{st}|{en}",
                           reason=f"{why}; {why2}")
            continue

        # mechanical era rule: a modern-state endpoint
        hubs = [(sd, eid) for sd, eid in (("S", rel["sid"]), ("T", rel["tid"])) if eid in ERA]
        if hubs:
            if rid8 in ERA_SKIP_RIDS:
                row.update(action="list", rule="era", reason="modern_state_row: relation reversed or self-referential "
                                                               "(judged by hand); not re-pointed")
                continue
            if rel["rtype"] in ERA_SKIP_TYPES:
                row.update(action="list", rule="era",
                           reason=f"modern_state_row:{ents[hubs[0][1]]['name']}; type {rel['rtype']} not re-pointed")
                continue
            new_s, new_t, notes, fail = rel["sid"], rel["tid"], [], ""
            for sd, hub in hubs:
                other = ents[rel["tid"] if sd == "S" else rel["sid"]]
                yrs, ysrc = ref_years(rel, other)
                hub_e = ents[hub]
                rr = row_range(hub_e["type"], hub_e["s"], hub_e["e"])
                if yrs and rr and all(rr[0] - 25 <= y <= rr[1] + 25 for y in yrs):
                    continue  # this hub is in its own era here
                if not yrs:
                    fail = f"modern_state_row:{hub_e['name']}; no years to place the relation"
                    break
                pick, why = pick_era(hub, yrs)
                if not pick:
                    fail = f"modern_state_row:{hub_e['name']}; {why}"
                    break
                if sd == "S":
                    new_s = pick[0]
                else:
                    new_t = pick[0]
                notes.append(f"{hub_e['name']} -> {pick[3]} ({pick[1]}..{pick[2]}) by {ysrc} years "
                             f"{','.join(map(str, sorted(set(yrs))))}")
                row.update(years_from=ysrc)
            if fail or (new_s, new_t) == (rel["sid"], rel["tid"]):
                row.update(action="list", rule="era", reason=fail or "modern_state_row: hub already in era")
                continue
            problem = _check_repoint(rel, new_s, new_t, ents, ex, triples, planned_triples)
            if problem:
                row.update(action="list", rule="era", reason=f"{problem}; " + "; ".join(notes))
                continue
            changed = [("S", rel["sid"], new_s), ("T", rel["tid"], new_t)]
            changed = [c for c in changed if c[1] != c[2]]
            row.update(action="repoint", rule="era", side="+".join(c[0] for c in changed),
                       old_entity_id="+".join(c[1] for c in changed),
                       old_entity_name="+".join(ents[c[1]]["name"] for c in changed),
                       new_entity_id="+".join(c[2] for c in changed),
                       new_entity_name="+".join(ents[c[2]]["name"] for c in changed),
                       new_source_id=new_s, new_target_id=new_t, gap_after=gap(ents, new_s, new_t),
                       reason="; ".join(notes))
            planned_triples.add((new_s, new_t, rel["rtype"]))
            continue

        if rid8 in SET_YEARS:
            st, en, why2 = SET_YEARS[rid8]
            row.update(action="set_years", rule="manual", old_years=f"{rel['temporal_start']}|{rel['temporal_end']}",
                       new_years=f"{st}|{en}", reason=why2)
            continue
        redated = {r[0] for r in REDATE}
        if rel["sid"] in redated or rel["tid"] in redated:
            row.update(action="covered_by_redate", rule="redate",
                       reason="endpoint re-dated (see REDATE); relation unchanged")
            continue
        row.update(action="list", reason=list_reason(rel, ents, side, wd))

    redates = []
    for eid, field, old, new, why in REDATE:
        rg = ranges.get(eid)
        if not rg or excluded(eid, ex):
            redates.append({"entity_id": eid, "action": "skip", "reason": "no primary range / excluded"})
            continue
        redates.append({"entity_id": eid, "entity_name": ents[eid]["name"], "temporal_range_id": rg["temporal_range_id"],
                        "field": field, "old": old, "current": rg[field], "new": new, "old_notes": rg["notes"],
                        "action": "redate" if rg[field] == old else "skip",
                        "reason": why if rg[field] == old else f"value changed to {rg[field]!r}"})
    return out, ents, redates


def _check_repoint(rel, new_s, new_t, ents, ex, triples, planned) -> str:
    if new_s == new_t:
        return "would point the relation at itself"
    for eid in (new_s, new_t):
        if eid not in ents:
            return f"target entity {eid} missing"
        if excluded(eid, ex):
            return f"target entity {eid} excluded"
    key = (new_s, new_t, rel["rtype"])
    if key in triples:
        return f"duplicate: the same relation already exists on the correct rows ({triples[key]})"
    if key in planned:
        return "duplicate: another flagged relation is re-pointed to the same rows"
    return ""


# ── output ───────────────────────────────────────────────────────────────────
PLAN_FIELDS = ["relationship_id", "relationship_type", "source_id", "source_name", "target_id", "target_name",
               "rel_years", "years_from", "bad_side", "action", "rule", "side", "old_entity_id", "old_entity_name",
               "new_entity_id", "new_entity_name", "swap", "old_years", "new_years", "gap_before", "gap_after",
               "reason", "description"]


def write_plan(rows: list[dict[str, Any]], redates: list[dict[str, Any]], applying: bool) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    # once applied, planned.csv is the record of what was applied; a later
    # plan-only run writes planned-rerun.csv instead of overwriting it
    name = "planned-rerun.csv" if (OUT / "applied.csv").exists() and not applying else "planned.csv"
    with (OUT / name).open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, PLAN_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
        for r in redates:
            w.writerow({"action": r["action"] if r["action"] == "skip" else "redate_entity", "rule": "redate",
                        "source_id": r["entity_id"], "source_name": r.get("entity_name", ""),
                        "old_years": f"{r.get('field')}={r.get('old')}", "new_years": f"{r.get('field')}={r.get('new')}",
                        "reason": r["reason"]})


def summarize(rows: list[dict[str, Any]], redates: list[dict[str, Any]]) -> None:
    c = Counter(r["action"] for r in rows)
    print("actions:", dict(c), "| redates:", Counter(r["action"] for r in redates))
    print("rules:", dict(Counter((r["action"], r["rule"]) for r in rows if r["action"].startswith("repoint"))))
    lr = Counter(r["reason"].split(":")[0].split(";")[0] for r in rows if r["action"] == "list")
    print("list reasons:", dict(lr.most_common()))


def sql_lit(v: Any) -> str:
    if v is None:
        return "NULL"
    return "'" + str(v).replace("'", "''") + "'"


def apply(rows: list[dict[str, Any]], redates: list[dict[str, Any]]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = subprocess.run(["date", "+%Y%m%d-%H%M%S"], capture_output=True, text=True).stdout.strip()
    dump = OUT / f"pre-apply-{stamp}.dump"
    with dump.open("wb") as fh:
        subprocess.run([*COMPOSE, "exec", "-T", "db", "pg_dump", "-U", "history-mapped", "-Fc",
                        "-t", "relationships", "-t", "entity_temporal_ranges", "history-mapped"],
                       stdout=fh, check=True)
    print("backup:", dump, dump.stat().st_size, "bytes")
    applied: list[dict[str, Any]] = []
    rollback: list[str] = [f"-- rollback for {TAG}: guarded inverses; run inside BEGIN ... COMMIT", "BEGIN;"]
    with connect(read_only=False) as conn:
        with conn.transaction():
            for r in rows:
                if not r["action"].startswith("repoint") and r["action"] != "set_years":
                    continue
                rid = r["relationship_id"]
                if r["action"].startswith("repoint"):
                    cur = conn.execute(
                        """update relationships set source_entity_id = %s, target_entity_id = %s
                           where relationship_id = %s and source_entity_id = %s and target_entity_id = %s
                             and relationship_type::text = %s""",
                        (r["new_source_id"], r["new_target_id"], rid, r["source_id"], r["target_id"],
                         r["relationship_type"]))
                    ok = cur.rowcount == 1
                    if ok:
                        rollback.append(
                            f"UPDATE relationships SET source_entity_id = {sql_lit(r['source_id'])}, "
                            f"target_entity_id = {sql_lit(r['target_id'])} WHERE relationship_id = {sql_lit(rid)} "
                            f"AND source_entity_id = {sql_lit(r['new_source_id'])} "
                            f"AND target_entity_id = {sql_lit(r['new_target_id'])};")
                    applied.append({**r, "result": "applied" if ok else "skipped: row changed since read"})
                    if not ok or not r.get("new_years"):
                        continue
                # set_years (alone, or after a re-point)
                old_s, old_e = r["old_years"].split("|")
                new_s, new_e = r["new_years"].split("|")
                old_s, old_e = (None if v == "None" else v for v in (old_s, old_e))
                cur = conn.execute(
                    """update relationships set temporal_start = %s, temporal_end = %s
                       where relationship_id = %s and temporal_start is not distinct from %s
                         and temporal_end is not distinct from %s""", (new_s, new_e, rid, old_s, old_e))
                ok = cur.rowcount == 1
                if ok:
                    rollback.append(
                        f"UPDATE relationships SET temporal_start = {sql_lit(old_s)}, temporal_end = {sql_lit(old_e)} "
                        f"WHERE relationship_id = {sql_lit(rid)} AND temporal_start = {sql_lit(new_s)} "
                        f"AND temporal_end = {sql_lit(new_e)};")
                applied.append({**r, "action": "set_years", "result": "applied" if ok else "skipped: years changed"})
            for d in redates:
                if d["action"] != "redate":
                    continue
                note = f"[{TAG}] {d['field']} {d['old']}->{d['new']}: {d['reason']}"
                new_notes = (d["old_notes"] + "\n" + note) if d["old_notes"] else note
                cur = conn.execute(
                    f"""update entity_temporal_ranges set {d['field']} = %s, notes = %s, updated_at = now()
                        where temporal_range_id = %s and {d['field']} is not distinct from %s
                          and notes is not distinct from %s""",
                    (d["new"], new_notes, d["temporal_range_id"], d["old"], d["old_notes"]))
                ok = cur.rowcount == 1
                if ok:
                    rollback.append(
                        f"UPDATE entity_temporal_ranges SET {d['field']} = {sql_lit(d['old'])}, "
                        f"notes = {sql_lit(d['old_notes'])} WHERE temporal_range_id = {sql_lit(d['temporal_range_id'])} "
                        f"AND {d['field']} = {sql_lit(d['new'])};")
                applied.append({"relationship_id": "", "action": "redate_entity", "rule": "redate",
                                "source_id": d["entity_id"], "source_name": d["entity_name"],
                                "old_years": f"{d['field']}={d['old']}", "new_years": f"{d['field']}={d['new']}",
                                "reason": d["reason"], "result": "applied" if ok else "skipped: value changed"})
    rollback.append("COMMIT;")
    (OUT / "rollback.sql").write_text("\n".join(rollback) + "\n", encoding="utf-8")
    with (OUT / "applied.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, PLAN_FIELDS + ["result"], extrasaction="ignore")
        w.writeheader()
        w.writerows(applied)
    print("applied:", Counter(a["result"] for a in applied))


def touched_entities() -> list[str]:
    ids: set[str] = set()
    with (OUT / "applied.csv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["result"] != "applied":
                continue
            for col in ("source_id", "target_id", "old_entity_id", "new_entity_id"):
                ids.update(x for x in (r.get(col) or "").split("+") if x)
    return sorted(ids)


def rebuild() -> None:
    ids = touched_entities()
    print(f"timeline:rebuild for {len(ids)} entities")
    script = "for id in " + " ".join(ids) + "; do php artisan timeline:rebuild $id || echo FAIL $id; done"
    res = subprocess.run([*COMPOSE, "exec", "-T", "app", "sh", "-c", script], capture_output=True, text=True)
    lines = res.stdout.splitlines()
    fails = [ln for ln in lines if ln.startswith("FAIL")]
    print(f"rebuilt {sum(1 for ln in lines if ln.startswith('Rebuilt'))}, failed {len(fails)}", fails[:5],
          res.stderr[-500:] if res.returncode else "")


def test_rollback() -> None:
    sql = (OUT / "rollback.sql").read_text(encoding="utf-8")
    stmts = [s for s in sql.splitlines() if s.startswith("UPDATE")]
    with connect(read_only=False) as conn:
        conn.autocommit = False
        n = 0
        for s in stmts:
            n += conn.execute(s).rowcount
        conn.rollback()
    print(f"rollback test: {len(stmts)} statements matched {n} rows (rolled back)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true", help="backup, apply the planned changes, write rollback.sql")
    ap.add_argument("--rebuild", action="store_true", help="timeline:rebuild every entity touched by applied.csv")
    ap.add_argument("--test-rollback", action="store_true", help="run rollback.sql in a transaction and roll back")
    args = ap.parse_args(argv)
    if args.rebuild:
        rebuild()
        return 0
    if args.test_rollback:
        test_rollback()
        return 0
    rows, _ents, redates = plan()
    write_plan(rows, redates, args.apply)
    summarize(rows, redates)
    if args.apply:
        apply(rows, redates)
    return 0


if __name__ == "__main__":
    sys.exit(main())
