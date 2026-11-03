#!/usr/bin/env python3
"""Relationship era fixes, slice C (2026-11-01 cleanup).

Slice: ``output/audit/identity-20261031/relation-flags.csv`` rows with
``check=endpoint_era`` and severity ``medium`` or ``low`` (1,052 rows). The
identity audit (``pipeline/audit/relations.py``, C7) flags a contemporaneous
relationship whose dated endpoints are further apart than the tolerance.

Every row is classified, in this order:

1. ``skip_excluded``  an endpoint is a merge-review row or a user-decision row
                      (RULES.md); never written.
2. ``DECISIONS``      hand-judged rows (keyed by the first 8 hex digits of the
                      relationship id): re-point an endpoint to the right existing
                      row (same name family, type and era, or the QID-canonical
                      row of the same person), reverse a relationship whose
                      direction contradicts its own description, delete a
                      reversed duplicate whose correct twin exists, or leave with
                      a reason.
3. ``ENTITY_DATES``   hand-checked endpoint date fixes: a row whose summary
                      names the person or thing the relationship means but whose
                      dates came from a namesake's Wikidata item, or whose dates
                      contradict its own item. The new dates are the right
                      item's own (cited by QID in the note), never shifted or
                      invented.
4. ``century``        mechanical: a person endpoint whose start year is a
                      Wikidata century-precision birth (``5th century`` stored as
                      500) while the same item gives a year-precision death the
                      row lacks. The century value is not a year: the start is
                      cleared (backfill_dates' convention: century or coarser is
                      never stored) and the end becomes the item's death year.
                      Applied only when that resolves the flagged relationship.
5. ``leave``          everything else, with a reason: a modern state row whose
                      start is its current constitution (France 1958, Germany
                      1990 …: a modelling decision for a human), the Qin row
                      (state and dynasty in one row), century-precision dates
                      with no finer source, ancient chronologies, reign spans,
                      non-contemporaneous relation types used loosely, wrong
                      relation facts or types (listed), and entity gaps (the
                      right namesake has no row).

Stages (dry by default):

  scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit.fix_relation_eras_c plan
  scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit.fix_relation_eras_c apply

``plan`` writes ``planned.csv``. ``apply`` dumps the two tables it writes
(``relationships``, ``entity_temporal_ranges``) with pg_dump, then in one
transaction makes guarded writes (each UPDATE/DELETE matches the values read;
a row another agent changed is skipped), writes ``applied.csv`` and
``rollback.sql`` (guarded inverses), tests the rollback inside a transaction
that is rolled back, and rebuilds the timeline of every touched entity
(``php artisan timeline:rebuild <id>``). Local DB only.

``followup`` (run once, after ``apply``) deletes the wrong-endpoint rows that
``apply`` skipped as ``would_duplicate`` (their corrected twin already exists)
and repairs one mis-sided re-point; it appends to ``applied.csv`` and
``rollback.sql`` and dumps ``relationships`` to ``pre-followup-<stamp>.dump``.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pipeline.audit.common import CACHE_DIR, COMPOSE, REPO, connect, write_csv  # noqa: E402
from pipeline.audit.dates import row_range, text_years, tolerance  # noqa: E402
from pipeline.audit.wd import WikidataClient  # noqa: E402

OUT = REPO / "output" / "audit" / "relfix-era-c-20261101"
FLAGS = REPO / "output" / "audit" / "identity-20261031" / "relation-flags.csv"
VERDICTS = REPO / "output" / "audit" / "merge-review-20261101" / "verdicts.csv"
USER_DECISION_PREFIXES = ("a05afb75", "6255478f", "17d96812", "7baeedc3")
NOTE = "relfix_era_c"

# ── hand-judged relationships ────────────────────────────────────────────────
# rid8 -> (action, args, reason). Entity ids are 8-hex prefixes, resolved to the
# full id (must be unique). Actions:
#   repoint_source / repoint_target  {"to": id8}
#   endpoints                        {"source": id8, "target": id8}
#   reverse                          {}
#   delete                           {"twin": rid8}  (reversed duplicate)
#   leave                            {"why": category}
R = "repoint_target"
S = "repoint_source"
DECISIONS: dict[str, tuple[str, dict[str, str], str]] = {}


def _d(rids: str, action: str, args: dict[str, str] | None, reason: str) -> None:
    for rid in rids.split():
        DECISIONS[rid] = (action, args or {}, reason)


def _leave(rids: str, why: str, reason: str) -> None:
    _d(rids, "leave", {"why": why}, reason)


# Namesake / wrong-era endpoint -> the right existing row.
_d("ddf55f14", R, {"to": "07996349"}, "the description itself: Romanos II was the son of Constantine VII (grandson of Leo VI)")
_d("2850c6bf", S, {"to": "7cdb0050"}, "same admiral Piet Heyn; this row is dated 1577-1629 (the other carries a namesake's 1857)")
_d("115611e6", R, {"to": "6a808a33"}, "the Isere River victor of 121 BCE is Quintus Fabius Maximus Allobrogicus, not Verrucosus")
_d("c9faa90d", R, {"to": "1f79cefd"}, "the 1185 sack of Thessalonica was William II of Sicily's, not William II of England")
_d("870887e1", R, {"to": "983889b6"}, "same James (Jim) Larkin; this row is dated 1876-1947 (the other carries a namesake's 1946-2023)")
_d("d403f566", R, {"to": "2062c84e"}, "same man: Jan Sobieski = John III Sobieski (Q53454, 1629-1696)")
_d("194d70c0", S, {"to": "2062c84e"}, "same man: Jan Sobieski = John III Sobieski (Q53454, 1629-1696)")
_d("39dc887c", S, {"to": "1206ed79"}, "the 743 synod was convened by Carloman, son of Charles Martel (Q310440), not Carloman I")
_d("481d93c3", R, {"to": "df9380f4"}, "al-Ashraf Khalil took Acre in 1291: Siege of Acre (1291), not the 1189-1191 siege")
_d("91c59ac6", R, {"to": "b469eb5b"}, "Menelaus was captured at the Battle of Salamis (306 BCE), on Cyprus, not Salamis 480 BCE")
_d("abd710a4 d26c46cf 816b035f f27b7674 303054c7", R, {"to": "2bbe43e6"},
   "Justinian's Gothic War (535-554), not the Gothic War of 376-382")
_d("4a442fe0 c7dbfb12 1c8f69d1 d73eba4e", S, {"to": "5b568c33"},
   "Galdan Boshugtu Khan (Q1395045, 1644-1697), not the namesake Galdan (Q4132297)")
_d("1d849068 647597d9 0dbaec53 ccc8fc15 9e414aeb", S, {"to": "7257c5dd"},
   "Charles I of England (Q81506, 1600-1649); the 'Charles I' row is Charles V / Charles I of Spain")
_d("f3104011 44e9c5fc 396f2f4f e67c3543 d5c12119 8893c2b2 7dc036b2 fa4eecf4", R, {"to": "7257c5dd"},
   "Charles I of England (Q81506, 1600-1649); the 'Charles I' row is Charles V / Charles I of Spain")
_d("16db01ff b8aa8a9c d29f79dc 79275fb7 36c26bb6", S, {"to": "0d64232f"},
   "the Han dynasty (Q7209, 206 BCE-220 CE), not the Warring States state of Han (ended 230 BCE)")
_d("21e37390 eb9fbdc3 e0aa9d50 0933232d 82b30507 77bf7fe7 4af00c48", R, {"to": "0d64232f"},
   "the Han dynasty (Q7209, 206 BCE-220 CE), not the Warring States state of Han (ended 230 BCE)")
_d("d6778a73 21ae430c", R, {"to": "dd36791d"},
   "in 1839-1848 the United Kingdom (Q145, formed 1801), successor of the Kingdom of Great Britain (1707-1800)")
_d("65cbba1a 6ad5a75f 6bb1eee5 7fb9e869 a8d42f87 617603af", S, {"to": "dd36791d"},
   "in 1827-1875 the United Kingdom (Q145, formed 1801), successor of the Kingdom of Great Britain (1707-1800)")
_d("b4d48947", S, {"to": "dd36791d"}, "The Troubles (1969-1998): the United Kingdom (Q145), not the 1801-1922 United Kingdom of GB and Ireland")
_d("be97c340", S, {"to": "4162c9c5"}, "the 1858 Government of India Act: Parliament of the United Kingdom (Q11010), successor of the Parliament of Great Britain")
_d("bafad53d be970385 100744fc", S, {"to": "8c57d738"},
   "in 1759/1772 the Habsburg Monarchy (Q153136); the Austrian Empire began in 1804")
_d("af8677a8", S, {"to": "8c57d738"},
   "in 1740-1790 the Habsburg Monarchy (Q153136); Austria-Hungary began in 1867")
# Maria Theresa / Joseph II rule the polity: the wrong endpoint is the TARGET. The first apply
# re-pointed d6a6a797's source by mistake; the `followup` stage repairs that (see FOLLOWUP).
_d("d6a6a797 fa95b9ce", R, {"to": "8c57d738"},
   "in 1740-1790 the Habsburg Monarchy (Q153136); Austria-Hungary began in 1867")
_d("0d75bfde 92af4b30", S, {"to": "99974943"}, "in 1914-1918 Austria-Hungary (Q28513); the Austrian Empire ended in 1867")
_d("ea881f10 2ea800ba 20b3e202 bc76a568 70983656 4d4c4e17 e46c867d 9c6f0c4a 1a8f7dea c045e018 c727972a", S,
   {"to": "b643aaa8"}, "the Union of the American Civil War is the United States (Q30), not the Soviet Union")
_d("d35f08cc 9cc81612", R, {"to": "b643aaa8"},
   "the Union of the American Civil War is the United States (Q30), not the Soviet Union")
_d("d580341c 6d81729b", S, {"to": "e835047d"},
   "the Dutch Republic (Q170072, 1581-1795), not the United Provinces of the Rio de la Plata")
_d("82129acd b0be5453 7c828e65", R, {"to": "e835047d"},
   "the Dutch Republic (Q170072, 1581-1795), not the United Provinces of the Rio de la Plata")
_d("ca3ac391 7b3c5a58", S, {"to": "8b55154b"},
   "the SPD (Q49768) of 1912/1914; the SDAP merged into it in 1875")
_d("b1920056", S, {"to": "427f8d53"}, "the Allies of World War II (Q329888), not the WWI Allied Powers")
_d("710b750b", R, {"to": "427f8d53"}, "the Allies of World War II (Q329888), not the WWI Allied Powers")
_d("910684a9", R, {"to": "65b09d4d"}, "the House of Habsburg (Q65968); the 'Habsburgs' row carries a fountain's QID dated 1696")
_d("8e8a22a5", S, {"to": "6539c80d"}, "Alexander III of Scotland (Q211109) fought Haakon IV at Largs, not Pope Alexander III")
_d("d790bbb2 3ed03052", R, {"to": "6539c80d"}, "Alexander III of Scotland (Q211109) made the Treaty of Perth, not Pope Alexander III")
_d("015d343f 5bf5c4d4 70d910b0 c6d73dcf 6707f5e1 307a6e74", R, {"to": "ee6bb2d1"},
   "the city of Rome (Q220), not the Roman Republic polity (509-27 BCE)")
_d("e0be7b06", S, {"to": "71cefb06"}, "Carrhae (53 BCE) was fought by the Roman Republic (Q17167), not the Roman Empire (27 BCE-)")
_d("83778643", S, {"to": "2b90d222"}, "Ivan IV's 1570 massacre hit the city of Novgorod (Q2235); the Novgorod Republic ended in 1478")
_d("1554d653 81c1a03b", R, {"to": "a4670b20"}, "Fiji of 1970- (Q712), not the 1871-1874 Kingdom of Fiji")
_d("1865bb3b", R, {"to": "a4670b20"}, "Fiji of 1970- (Q712), not the 1871-1874 Kingdom of Fiji")
_d("89df06ab", S, {"to": "284afdca"}, "the land of Khorezm (Q11730773), not the 1077-1231 Khwarazmian realm")
_d("0e7bf6d0 2c0b8cef", R, {"to": "284afdca"}, "the land of Khorezm (Q11730773), not the 1077-1231 Khwarazmian realm")
_d("50b9b9cc", R, {"to": "6b8d3396"}, "Lytton's Durbar was the Delhi Durbar of 1877, not the 1911 Durbar")
# Wrong endpoint and reversed direction.
_d("81580c25", "endpoints", {"source": "bd291b9d", "target": "old_source"},
   "per the description al-Qa'im (the Fatimid, Q293549) was al-Mahdi's son: al-Qa'im child_of al-Mahdi, "
   "not al-Mahdi child_of the Abbasid al-Qa'im")
_d("2c4a6117", "reverse", None, "per the description the Vakatakas followed the Satavahanas")
_d("b067dc30", "reverse", None, "per the description Narendrasena succeeded Pravarasena II")
_d("7402d153", "reverse", None, "per the description Ezana followed Wazeba")
# Reversed duplicates whose correct twin exists.
_d("f24dae2f", "delete", {"twin": "6b5c4d1a"}, "reversed duplicate: the Asiatic Company followed the Danish East India Company (twin 6b5c4d1a)")
_d("381bffcb", "delete", {"twin": "bb417ba8"}, "reversed duplicate: Austria-Hungary took Bosnia, not the reverse (twin bb417ba8)")
_d("57a837c4", "delete", {"twin": "a3684828"}, "reversed duplicate: the parent is not the child of the daughter (twin a3684828)")

# Leave: entity gaps (the right namesake has no row).
_leave("fcd6240c", "entity_gap", "Nicanor killed at Adasa in 161 BCE has no row; the row is the governor of Media (d. 310 BCE)")
_leave("23d85c37", "entity_gap", "Pentawer's mother is Tiye, wife of Ramesses III, who has no row")
_leave("3469f41b 2765ae20", "entity_gap", "the 163 CE capture of Artaxata has no row; the row is Corbulo's of 58 CE")
_leave("d54262cd", "entity_gap", "the Ghassanid al-Mundhir III ibn al-Harith has no row (the row is the Lakhmid)")
_leave("09c7ee4d", "entity_gap", "Cornelio Saavedra Rodriguez (1821-1891) has no row (the row is the 1810 junta president)")
_leave("4bf0ca80 5276bfcc", "entity_gap", "the Publius Decius Mus of 295 BCE / 279 BCE (son, grandson) have no rows")
_leave("77d34001 de7a3389", "entity_gap", "the 1217 Battle of Lincoln has no row (the row is 1141)")
_leave("d4d65afb d1aa007d", "entity_gap", "the 1358 Red Turban capture of Kaifeng has no row (the row is 1232)")
_leave("6bc3d1b0", "entity_gap", "the 831-832 Bashmurian revolt has no row (the row is the 749 revolt)")
_leave("6835d478 7fe37a63 134566a8 d14974a3", "entity_gap", "Charles IX of Sweden has no row (the row is Charles IX of France)")
_leave("a998b9a8 f1ee9462", "entity_gap", "Prince Charles Alexander of Lorraine (1712-1780) has no row")
_leave("63a1c0e6", "entity_gap", "Henry VII, Holy Roman Emperor has no row (the row is Henry (VII), son of Frederick II)")
_leave("c27da1e7 c9322219", "entity_gap", "the 502-503 siege of Amida has no row (the row is 359)")
_leave("e9925645 3d33e7bd 5b008b22", "entity_gap", "the 531 Battle of Callinicum has no row (the row is the 296 battle)")
_leave("419b37ab", "entity_gap", "the 1813 Battle of Lutzen has no row (the row is 1632)")
_leave("a2b8ffa6", "entity_gap", "Pyrrhus's 276 BCE siege of Lilybaeum has no row (the row is the 250-241 Roman siege)")
_leave("c07087f2", "entity_gap", "the 1898 Wuxu coup has no row (the row is the 1861 Xinyou coup)")
_leave("c43b413d 18a278ed", "entity_gap", "the Irish Nine Years' War (1593-1603) has no row (the row is 1688-1697)")
_leave("9bbd2a79", "entity_gap", "the Roman Social War (91-87 BCE) has no row (the row is the Greek war of 220-217)")
_leave("81b902f3", "entity_gap", "K'an II's star wars against Naranjo (631) have no row (the row is the 562 star war)")
_leave("2894f510", "entity_gap", "Zisi of Zheng (killed 563 BCE) has no row (the row is Confucius' grandson)")
_leave("cba6fefc", "entity_gap", "the general Demosthenes (d. 413 BCE) has no row (the row is the orator)")
_leave("1b2f6edb", "entity_gap", "Parysatis II, daughter of Artaxerxes III, has no row (the row is Darius II's queen)")
_leave("920401fb", "entity_gap", "Michael Collins the astronaut has no row (the row is the Irish revolutionary)")
_leave("a88f246d", "entity_gap", "the Seljuk sultan Mas'ud (r. 1134-1152) has no row (the row is the Ghaznavid Mas'ud I)")
_leave("350b7485", "entity_gap", "the emperor Tacitus has no row (the row is the historian)")
_leave("54d3ffcf", "entity_gap", "an-Nasir Muhammad ibn Qaitbay has no row (the rows are ibn Qalawun)")
_leave("1ada0fd8 7656a821", "entity_gap", "Maha Chakkraphat of Ayutthaya has no row (the row is Chakkaphat of Lan Xang)")
_leave("e08416c2 01f63178 3729a560", "entity_gap",
       "Simon de Montfort, 6th Earl of Leicester has no row of his own: this row carries his QID but the 5th Earl's dates and summary")
_leave("ec6cea9c 44f0aaa3 41180524", "entity_gap",
       "Henry II of England has no row: the 'Henry II' row mixes Henry II of Jerusalem's QID and the emperor's summary")
_leave("832c2b1c", "entity_gap", "Askia Ismail of Dendi (1639) has no row (the row is the Songhai askia, d. 1537)")
_leave("352f8145", "entity_gap", "Muwatalli of Gurgum (9th c. BCE) has no row (the row is the Hittite Muwatalli II)")
_leave("5e103a1d", "entity_gap", "the Ali Pasha at the 1736 Mughan assembly has no row (the row is Ali Pasha of Ioannina)")
_leave("3aa4558a", "entity_gap", "the German Catholic League (1609-1635) has no row; the row is the French League (its QID is the German one)")
_leave("21a03271", "entity_gap", "Portugal's Estado Novo has no row; the row is Brazil's (its QID is Portugal's)")
_leave("0d296046", "entity_gap", "Poland's 1863 National Government has no row; the row carries the ROC government's QID")
_leave("c4c0fb19", "entity_gap", "Ifriqiya row starts with the 703 province; Mu'awiya ibn Hudayj's 665 raids predate it")
_leave("94d7399f cdcdec4d 15b8d1d2 a958f1ab", "entity_gap",
       "Ibn Saud's Sultanate of Nejd (1921-) has no row; the row is the Second Saudi State")
_leave("ceff11a7", "entity_gap", "the revolutionary Paris Commune of 1792 has no row (the row is 1871)")
_leave("a8c1dc83", "entity_gap", "the Emirate of Afghanistan (1823-) has no row (the row is the 1747-1826 emirate)")
_leave("bcb6297b 9e31254e 2158ac70", "entity_gap", "the Frankish kingdom of Burgundy (534-) has no row (the row is the 411-534 kingdom)")
_leave("5c742ab3", "entity_gap", "the row's dates belong to al-Hurr al-Tamimi (d. 680); the governor al-Hurr al-Thaqafi has no dated source")
_leave("0d094367 a8d2dcfa", "entity_gap", "the League of Venice (1495) has no polity row (the row is the 1684 Holy League)")
_leave("6f6b7a7a", "entity_gap", "the state of Louisiana has no row (the row is French Louisiana, 1682-1804)")
_leave("ec456c5e", "wrong_fact", "the VOC was dissolved in 1799; the description credits it with the 1825-1830 Java War")
# Leave: wrong relation type or fact (listed for a human).
_leave("532bfcec", "wrong_fact", "Elissa (Dido) was the daughter of Mattan I, not Ithobaal I (Mattan I is row 0f23b288)")
_leave("1aaa490f", "wrong_type", "Chandragupta II was Chandragupta I's grandson (son of Samudragupta)")
_leave("e20d9de7", "wrong_type", "Charles I of England was Henry Frederick's brother, not his child (and the endpoint is Charles V)")
_leave("b0c74307", "wrong_type", "George Villiers was Charles I's favourite, not his child")
_leave("3b80c6a8", "wrong_type", "Taj ud-Din Firuz Shah succeeded Ghiyasuddin; he was not his child")
_leave("d3e0cc16", "wrong_type", "Vahan Mamikonian was Vardan's nephew")
_leave("402a7038 b6ab158b", "wrong_fact", "Charibert I and Sigebert I were sons of Chlothar I (row 640c69c0), grandsons of Clovis I")
_leave("971e16a0", "wrong_fact", "Terken Khatun (wife of Malik-Shah I) was not Soltan-Shah's mother")
_leave("8a3a4229", "wrong_type", "Muhammad II al-Mahdi was Abd al-Rahman III's great-grandson")
_leave("5876b329", "wrong_type", "member_of_dynasty pointing at a person (Peter I married Maria Lekapene)")
_leave("436fb86a", "wrong_fact", "Western Qin (385-431) did not exist in 317")
_leave("dfafe60c", "wrong_fact", "Scipio Aemilianus (b. 185 BCE) cannot have fought at Zama (202 BCE)")
_leave("6a3bb649 416c4a78 dfb739d4 9aa46901 1de0e5b5 5148bc9f", "wrong_fact",
       "the succession relation does not hold (different polities or a nonsense pairing)")
_leave("0004e5a4", "wrong_fact", "the Trinh lord defied in 1620 was Trinh Tung, not Trinh Kiem (d. 1570)")
_leave("f6de3a89", "wrong_fact", "Abdallah ibn Yasin died at Krifla in 1059, not at Sagrajas (1086)")
_leave("6895a812", "century_precision", "Kudur-Mabuk's dates are a Wikidata century value")
_leave("21538854", "wrong_type", "resided_in pointing at a person")
_leave("5aa89d3b 03861ba1 1bf8f9e2", "wrong_type", "defeated_at/participated_in between a ruler and a people or person, loosely dated")
# Leave: non-contemporaneous by nature (a historian's account, a later honour).
_leave("96ccd53b 5a924d6e d1acf2c6 1da8819a", "documentary", "a later writer documenting an earlier subject")
_leave("b258780e 476a2822 2d6bc37c 572c0944 4c503f87 8a4aefd1 1c411359", "posthumous",
       "a later honour, rehabilitation or policy toward someone already dead")

_d("e6f1412f", "reverse", None, "per the description Yoshihito succeeded his father Mutsuhito (dates fixed below)")
# Leave: two rows whose QIDs (and so dates) are swapped against their summaries.
_leave("40dcdda8 7e480dfa 3dbf8419", "qid_swap",
       "Brennus rows 401c2793 / c00e024b: each summary describes the other's QID (279 BCE vs Allia); a QID fix, not a re-point")
# Leave: the row's QID and dates are a namesake's, and no clear dates exist for
# the person or thing meant (or the right row is missing): a QID fix for a human.
_leave("83fbd2fd d18c2ed4", "qid_namesake", "Gozlin: QID/dates are the Count of Bidgau's; the bishop of Paris (d. 886) has no dated source")
_leave("1732209e cccb6100", "qid_namesake", "Murshid Quli Khan: QID/dates are the Nawab of Bengal's; the Safavid Ostajlu has no dated source")
_leave("38b724f4 1a6b411e", "qid_namesake", "Khizr Khan: QID/dates are the Sayyid sultan's; Alauddin's son has no dated source")
_leave("5066ba82", "qid_namesake", "Titus Manlius Torquatus: QID/dates are the consul of 235 BCE's; the consul of 340 has no dated source")
_leave("b0ff2e12", "qid_namesake", "Lucius Cornelius Scipio: QID/dates are the consul of 350 BCE's; the consul of 259 has only 'born c. 300'")
_leave("1a53d40c", "qid_namesake", "George Mouzalon: QID/dates are the 1258 regent's; the Bapheus commander has no dated source")
_leave("7bd58a83", "qid_namesake", "the row is the famous Lucullus (118-57/56) with the consul of 151 BCE's QID; the consul has no row")
_leave("67ff9b18", "qid_namesake", "Mahmud Shah of Bengal: QID/dates are Mahmud Shah I's; Ghiyasuddin Mahmud Shah's life dates are not given")
_leave("7834b538", "qid_namesake", "Lucius Antonius: QID/dates are Saturninus'; Mark Antony's brother is only fl. c. 50-41 BCE")
_leave("9d3a7cc7", "qid_namesake", "al-Harith ibn Jabalah (no QID) is dated 600; enwiki gives only his reign (c. 528-569)")
_leave("27841b2d", "qid_namesake", "Nicolas Roze: QID/dates are the composer's (1745-1819); the chevalier Roze of 1720 has no source here")
_leave("28cfc985", "qid_namesake", "Heinrich Huyssen: QID/dates are the 1666-1739 courtier's; the 1810 ironmaster has no source here")
_leave("5421a6a7", "qid_namesake", "Shi Shu: QID is a namesake born 1438; Kublai's official has no dated source")
_leave("b74c76bc", "qid_namesake", "Green Gang: QID is a 2008 item; the Shanghai gang has no dated source")
_leave("3587c20a", "qid_namesake", "Leo Phokas: QID/dates are the Elder's; the 960 victor is the Younger")
_leave("3a604ef6", "qid_namesake", "Publius Cornelius Dolabella: QID/dates are the 69-43 BCE one's; the proconsul of 24 CE has no dated source")
_leave("5fc703f1", "qid_namesake", "Tarabya: QID/dates are Tarabya of Ava's; Tarabya of Pegu has no dated source")
_leave("d2773dd6 181f45cf", "qid_namesake", "Yesuder: QID/dates are a 13th-c. namesake's; Jorightu Khan Yesuder (r. 1388-1391) has no life dates")
_leave("173261ac", "qid_namesake", "the row is the 1913 UVF (summary, dates) with the modern UVF's QID; the 1966 UVF has no row")
_leave("5746d23a 7162540c", "qid_namesake", "Boxers: QID is a 1944 item; the Yihetuan has no dated source")
_leave("195ae93b d419e073", "qid_namesake", "Nandi: a people typed as a person with a 1999 namesake's QID")
_leave("2f789050 8fb6d106", "qid_namesake", "Matumbi: QID is a modern place (1971); the people has no dated source")
_leave("36ad41e7 5a621ce2", "qid_namesake", "Kiowa: QID is Kiowa County (1901); the nation has no dated source")
_leave("4b5a5734", "qid_namesake", "Lakota: QID is a modern place (1892); the nation has no dated source")
_leave("45ea08f7 50c4d64b", "qid_namesake", "La Trinitaria: QID is a municipality (1911); the 1838 secret society has no row of its own")
_leave("d2d4b4ff", "qid_namesake", "US Supreme Court: QID is the 1935 building; the court's 1789 start needs the right item (Q11201)")
_leave("17d1b07b", "qid_namesake", "Group of Seven: QID is the Canadian painters (to 1932); the G7 forum needs the right item (Q1764511)")
_leave("b7736a09", "qid_namesake", "MacDonald: QID is Marshal Macdonald (1765-1840); Clan MacDonald of Glencoe has no row")
_leave("524f5a83", "qid_namesake", "Natalia Republic: typed as an event with a flag's QID (1839)")
_leave("802da2b6", "entity_gap", "the French House of Bourbon has no row (the row is the Spanish Bourbons, 1700-)")
_leave("85acd36f", "polity_span", "Hejaz row is the Ottoman vilayet (1872-1919); the 1803 conquest predates it")
_leave("9bc4399c fd76a16f", "polity_span", "Kingdom of Ireland ended in 1801; Ireland (the island) is a prehistory row")
_leave("278d2a80", "polity_span", "Annam row (1802-1887, Tay Son QID) does not cover the 1932-1945 protectorate")
_d("19eb7422", S, {"to": "df4812d1"}, "Mannai (-1000..-616) is the same kingdom as the 'Mannaeans' row (-1000..-800), which ends before 744 BCE")
_leave("7724b5c6", "qid_namesake", "Holstein-Gottorp carries Duke Charles Frederick's QID and 1700-1739; the duchy (1544-1773) needs its own item")
_leave("037c6f21 73cb7796 e4b481f3 ffb8c162 d480b4da", "reign_span",
       "the endpoint spans are reigns; a father-son or succession link across them is expected")
_leave("2adf38ad 2998962e f76aa201 1c6726aa", "ancient_chronology",
       "Iron Age chronologies (Lydia, Kush) disagree by decades; the row follows one of them")
_leave("7317dfc7 882a08bd 7880b872 2153eaed 86699b63", "century_precision",
       "the person's row is a round century value (-800 / -100) with no finer source date")
_leave("c7f0c8eb", "entity_gap", "Princess Anula of Sanghamitta's time has no row (the row is Queen Anula, d. 42 BCE)")
_leave("113ecc6b", "entity_gap", "the Seleucid general Gorgias has no row (the row is the sophist, 483-375 BCE)")
_leave("3485bbbe", "entity_gap", "the Carthaginian admiral Mago of 278 BCE has no row (the row is Hannibal's brother)")
_leave("77d25bdf", "polity_span", "the Linyi-Funan wars row is dated 390 only; Jayavarman's 484 appeal is a later phase")
_leave("3e33964d", "wrong_type", "'Oba of Benin' is the title (a row typed person dated 1516), not a ruler")
_leave("5f989d19", "wrong_fact", "the Demak Sultanate (c. 1475-) did not exist during Zheng He's voyages (1405-1433)")

# ── hand-checked endpoint date fixes ────────────────────────────────────────
# id8 -> the new primary-range dates (KEEP = leave that field). Each value is the
# cited item's own; 'low' marks a value the source gives as circa.
KEEP = "keep"


def _wp(title: str, qid: str) -> str:
    return f"enwiki '{title}' ({qid})"


ENTITY_DATES: dict[str, dict[str, Any]] = {
    "c9c2d2ca": dict(start=None, end="-0400", conf="low", src=_wp("Stateira (wife of Artaxerxes II)", "Q453117"),
                     why="died about 400 BCE; the row had Stateira II's dates (Q5429464)"),
    "12f1f999": dict(start=None, end="-0069", conf="high", src=_wp("Cleopatra Selene of Syria", "Q40027"),
                     why="Cleopatra Selene I (born c. 135-130, died 69 BCE); the row had Cleopatra Selene II's dates"),
    "dd1d9775": dict(start="0904-09-10", end="0954-02-22", conf="high", src=_wp("Guo Wei", "Q1188860"),
                     why="Later Zhou founder; the row had a namesake's QID and 991"),
    "2ff83423": dict(start="1080", end="1130-11-11", conf="low", src=_wp("Theresa, Countess of Portugal", "Q237987"),
                     why="c. 1080 - 11 Nov 1130; the row had 928 from a namesake's QID"),
    "d237157d": dict(start="1785", end="1865", conf="high", src=_wp("Faisal bin Turki Al Saud (1785–1865)", "Q1393513"),
                     why="the Saudi Faisal; the row had the Omani Faisal's QID and a 1864 start"),
    "7fb2ece6": dict(start="-0320", end="-0254", conf="low", src=_wp("Stratonice of Syria", "Q235061"),
                     why="c. 320 - 254 BCE; the row had a namesake's century dates"),
    "63d4d3fd": dict(start="0750-01-25", end="0780-09-08", conf="high", src=_wp("Leo IV the Khazar", "Q41645"),
                     why="the emperor; the row had Pope Leo IV's QID and 790"),
    "93357cee": dict(start="1619", end="1655", conf="high", src=_wp("John Penruddock", "Q1033690"),
                     why="the 1655 Royalist; the row had a namesake's QID (d. 1601)"),
    "dca0b145": dict(start="1841-04-29", end="1925-01-27", conf="high", src=_wp("Francis Grenfell, 1st Baron Grenfell", "Q335773"),
                     why="the Toski general; the row had a namesake's QID (1938-2011)"),
    "a2395d11": dict(start="1739", end="1794-12-16", conf="low", src=_wp("Alexander Stewart (British Army officer)", "Q17318963"),
                     why="the Eutaw Springs commander (c. 1739-1794); the row had a namesake's QID (1824-1886)"),
    "b1e8c64e": dict(start="1880-05-07", end="1945-05-18", conf="high", src=_wp("William Joseph Simmons", "Q983330"),
                     why="the 1915 Klan founder; the row had a namesake's QID (1849-1890)"),
    "2cebe040": dict(start="1930-09-17", end="2024-03-18", conf="high", src=_wp("Thomas P. Stafford", "Q316417"),
                     why="the astronaut; the row had a namesake's century value (2000)"),
    "da45b830": dict(start="1910-06-22", end="1998-11-07", conf="high", src=_wp("John Hunt, Baron Hunt", "Q335995"),
                     why="the Everest leader; the row had a namesake's QID (1964)"),
    "77a42f54": dict(start="1635", end="1688-08-25", conf="low", src=_wp("Henry Morgan", "Q215502"),
                     why="the privateer (c. 1635-1688); the row had a namesake's QID (1915-1994)"),
    "99abe3ac": dict(start="1789-06-30", end="1857-06-27", conf="high", src=_wp("Hugh Wheeler (East India Company officer)", "Q1634601"),
                     why="the Cawnpore general; the row had a namesake's QID (1912)"),
    "329bcd4c": dict(start="1861-06-19", end="1896-12-30", conf="high", src=_wp("José Rizal", "Q1500"),
                     why="the nationalist; the row had a namesake's QID (1952)"),
    "5a52113c": dict(start="1753-07-25", end="1810-08-26", conf="high", src=_wp("Santiago de Liniers, 1st Count of Buenos Aires", "Q960685"),
                     why="the 1806 reconqueror; the row had a namesake's QID (1842-1908)"),
    "1c8e05d6": dict(start=None, end="1628", conf="high", src=_wp("Robert Shirley", "Q1859875"),
                     why="the Safavid adventurer (d. 1628); the row had a namesake's QID (1673-1699)"),
    "96a15951": dict(start="1946-07-21", end="2022-09-13", conf="high", src=_wp("Ken Starr", "Q708241"),
                     why="the independent counsel; the row had a namesake's QID (1906-1969)"),
    "f0439c69": dict(start="1880-06-24", end="1969-12-06", conf="high", src=_wp("João Cândido", "Q974355"),
                     why="the 1910 revolt leader; the row had a namesake's QID (1934-2019)"),
    "a963d9b9": dict(start="1803-01-29", end="1863-03-11", conf="high", src=_wp("Sir James Outram, 1st Baronet", "Q584416"),
                     why="the Lucknow general; the row had a namesake's QID (1864)"),
    "7e11a721": dict(start="1853-09-04", end="1905-06-15", conf="high", src=_wp("Hermann Wissmann", "Q77401"),
                     why="the Abushiri commander; the row had his son's QID (1895-1979)"),
    "c9721eb8": dict(start="1879-08-31", end="1926-12-25", conf="high", src=_wp("Emperor Taishō", "Q157052"),
                     why="Emperor Taisho; the row had Prince Katsura's QID (1948)"),
    "63b962a1": dict(start="1191-02-08", end="1246-09-30", conf="high", src=_wp("Yaroslav II of Vladimir", "Q359396"),
                     why="Vsevolod III's son at Lipitsa; the row had a namesake's QID (1139-1198)"),
    "e78d17a8": dict(start="1888-12-16", end="1934-10-09", conf="high", src=_wp("Alexander I of Yugoslavia", "Q207384"),
                     why="the 1918 regent and king; the row had Prince Alexander Karadjordjevic's QID (1806-1885)"),
    "c97698cf": dict(start="-0129", end="-0082", conf="low", src=_wp("Gnaeus Papirius Carbo (consul 85 BC)", "Q921658"),
                     why="the Marian leader (c. 129-82 BCE); the row had the consul of 113's QID"),
    "711c3f54": dict(start=None, end="0757", conf="high", src=_wp("Æthelbald of Mercia", "Q272148"),
                     why="the Mercian king (d. 757); the row had Æthelbald of Wessex's QID (835)"),
    "6c5ae9b0": dict(start="1617-10-13", end="1648-08-18", conf="high", src=_wp("Ibrahim of the Ottoman Empire", "Q168776"),
                     why="the sultan; the row had a namesake's QID (1961)"),
    "12998fe4": dict(start="1459-12-22", end="1495-02-25", conf="high", src=_wp("Cem Sultan", "Q441311"),
                     why="the claimant; the row had a namesake's QID (1965)"),
    "a712b341": dict(start="1585-03-05", end="1656-10-08", conf="high", src=_wp("John George I of Saxony", "Q366652"),
                     why="the Elector of Saxony; the row had John George I of Anhalt-Dessau's QID (1567-1618)"),
    "38abc237": dict(start="1831-11-08", end="1891-11-24", conf="high", src=_wp("Robert Bulwer-Lytton, 1st Earl of Lytton", "Q335493"),
                     why="the viceroy; the row's 1803 start is his father's"),
    "2fab639d": dict(start="1933-08-20", end=None, conf="high", src=_wp("George J. Mitchell", "Q368920"),
                     why="the Good Friday chair (born 1933, living); the row had a namesake's QID (1894-1961)"),
    "cb07f6d8": dict(start=None, end="1882", conf="high", src=_wp("Chuma and Susi", "Q5116135"),
                     why="James Chuma (d. 1882); the row had a namesake's QID (1963)"),
    "81216776": dict(start="1086-11-06", end="1157-05-08", conf="high", src=_wp("Ahmad Sanjar", "Q337506"),
                     why="the row's own item; the row ended in 1143"),
    "0f9a54da": dict(start=KEEP, end="0255-03-16", conf=KEEP, src=_wp("Guanqiu Jian", "Q736639"),
                     why="died 16 March 255; the row ended at his 244 campaign"),
    "827e3a13": dict(start=KEEP, end="0940-12-25", conf=KEEP, src=_wp("Makan ibn Kaki", "Q3813860"),
                     why="died 25 December 940; the row ended at his 932 defeat"),
    "80fb76e9": dict(start=KEEP, end="0348-10-25", conf=KEEP, src=_wp("Murong Huang", "Q1069778"),
                     why="died 25 October 348; the row ended in 342"),
    "4429ee39": dict(start=KEEP, end="-1076", conf=KEEP, src=_wp("Tiglath-Pileser I", "Q296295") + "; Wikidata P570",
                     why="reigned 1114-1076 BCE; the row ended in 1007"),
    "385e3495": dict(start=None, end="-0367", conf="low", src="Wikidata Q508188 P570 (died c. 367 BCE)",
                     why="the row's -500/-400 are century values"),
    "665ac497": dict(start="1157", end="1806", conf="high", src=_wp("Margraviate of Brandenburg", "Q148499"),
                     why="the margraviate the summary describes (1157-1806); the row had Brandenburg-Kustrin's QID and dates"),
    "58dae9ac": dict(start="1000", end=KEEP, conf=KEEP, src=_wp("Kingdom of Hungary", "Q171150"),
                     why="the kingdom of 1000-1946 the summary describes; the row started at the 1920 regency (Q600018)"),
    "22bc9d91": dict(start=KEEP, end="1891", conf=KEEP, src=_wp("Second Saudi state", "Q146862"),
                     why="the Emirate of Najd existed 1824-1891; the row ended in 1865"),
    "0f5f3ec9": dict(start=KEEP, end="1729", conf=KEEP, src=_wp("Danish East India Company", "Q826616") + "; Wikidata P576",
                     why="two companies, 1616-1650 and 1670-1729; the row ended with the first"),
    "8623826b": dict(start=KEEP, end="1547", conf=KEEP, src=_wp("Muscovy", "Q3324731") + "; Wikidata Q170770 P576",
                     why="the Grand Principality lasted until 1547; the row ended in 1478"),
    "3937d1cc": dict(start=KEEP, end="0855", conf="low", src=_wp("Karkota dynasty", "Q466433"),
                     why="c. 625-855 CE; the row (and its summary) ended in 662"),
    "c3f9dcc2": dict(start=KEEP, end="0027", conf=KEEP, src="Wikidata Q759985 P582",
                     why="the rebellion lasted until 27 CE; the row was the single year 18"),
    "7fe6d787": dict(start=KEEP, end="1903", conf=KEEP, src=_wp("First Aliyah", "Q933141"),
                     why="the wave lasted until 1903; the row was the single year 1882"),
}

# ── leave categories for the rest ────────────────────────────────────────────
QIN = "10dcfd5d"
# Rows typed political_entity whose QID is a modern state and whose start is
# its current constitution or independence. Earlier relationships need either a
# wider row or a re-point to the era's own polity row: a modelling decision.
MODERN_MIN_START = 1800
DOCUMENTARY = {"authored", "patron_of", "restored_by"}
SUCCESSION = {"succeeded_by", "preceded_by"}
EVENT_LIKE = {"event_war", "event_battle", "event_treaty", "event_rebellion", "event_natural_disaster",
              "event_tech_adoption", "event_legal_reform", "migration", "epidemic_disease"}


# ── loading ──────────────────────────────────────────────────────────────────
def load_flags() -> list[dict[str, str]]:
    with FLAGS.open(newline="", encoding="utf-8") as fh:
        return [r for r in csv.DictReader(fh)
                if r["check"] == "endpoint_era" and r["severity"] in ("medium", "low")]


def load_exclusions() -> set[str]:
    out: set[str] = set()
    with VERDICTS.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out.update(x for x in (r.get("survivor_id"), r.get("loser_id")) if x)
    return out


def excluded(eid: str, ex: set[str]) -> bool:
    return eid in ex or eid.startswith(USER_DECISION_PREFIXES)


REL_COLS = ("rid", "type", "source", "target", "tstart", "tend", "y0", "y1", "description")
ENT_COLS = ("id", "name", "etype", "qid", "summary", "tr_id", "sd", "ed", "s0", "s1", "conf", "method", "notes")


def load_state(conn, rids: list[str]) -> tuple[dict[str, dict], dict[str, dict]]:
    cur = conn.cursor()
    cur.execute("""
        SELECT relationship_id::text, relationship_type::text, source_entity_id::text, target_entity_id::text,
               temporal_start, temporal_end, start_year, end_year, coalesce(description,'')
        FROM relationships WHERE relationship_id = ANY(%s::uuid[])""", (rids,))
    rels = {r[0]: dict(zip(REL_COLS, r)) for r in cur.fetchall()}
    cur.execute("""
        SELECT e.entity_id::text, e.name, e.entity_type::text, e.wikidata_id, coalesce(e.summary,''),
               t.temporal_range_id::text, t.start_date, t.end_date, t.start_year, t.end_year,
               t.date_confidence, t.date_method, t.notes
        FROM entities e LEFT JOIN entity_temporal_ranges t ON t.entity_id = e.entity_id AND t.is_primary""")
    ents = {r[0]: dict(zip(ENT_COLS, r)) for r in cur.fetchall()}
    return rels, ents


def resolve(prefix: str, ents: dict[str, dict]) -> str:
    hits = [e for e in ents if e.startswith(prefix)]
    if len(hits) != 1:
        raise SystemExit(f"entity prefix {prefix!r} matches {len(hits)} rows")
    return hits[0]


def wd_records() -> dict[str, dict]:
    """The identity audit's cached Wikidata records (read-only, no requests)."""
    return WikidataClient(CACHE_DIR, offline=True).entities


# ── classification ───────────────────────────────────────────────────────────
def rel_years(rel: dict, ) -> tuple[int, int] | None:
    ys = [y for y in (rel["y0"], rel["y1"]) if y is not None] or text_years(rel["description"])
    return (min(ys), max(ys)) if ys else None


def span_of(ent: dict) -> tuple[int, int] | None:
    return row_range(ent["etype"], ent["s0"], ent["s1"])


def fits(rng, window, tol: int) -> bool:
    return bool(rng and window) and not (window[1] < rng[0] - tol or window[0] > rng[1] + tol)


def out_sides(rel: dict, ents: dict) -> list[str]:
    window = rel_years(rel)
    sides = []
    for side in ("source", "target"):
        ent = ents[rel[side]]
        rng = span_of(ent)
        if window and rng and not fits(rng, window, tolerance(ent["etype"]) or 0):
            sides.append(side)
    return sides


def year_text(y: int) -> str:
    return f"-{abs(y):04d}" if y < 0 else f"{y:04d}"


# Spot check against enwiki: the item's death year is not what enwiki says.
CENTURY_SKIP = {
    "Q1350464": "Alonso de Arellano: enwiki says only '16th-century'; the item's 1580 is unsupported",
    "Q4372626": "Fedot Alekseyev: enwiki says he died between 1648 and 1654",
    "Q882691": "Palladius: the item (d. 455) is not enwiki's Palladius of Ireland (Q715209, fl. 5th c.)",
}
# enwiki gives the death as approximate or as one of two years: stored with 'low'.
CENTURY_LOW = {"Q952014": "died 684 or 686", "Q379723": "died 1299/1300", "Q363849": "died ca. 593"}


def century_fix(ent: dict, wd: dict[str, dict]) -> dict | None:
    """Century-precision birth stored as the start, with a year-precision death on the same item."""
    if ent["etype"] != "person" or not ent["qid"] or ent["s0"] is None or ent["qid"] in CENTURY_SKIP:
        return None
    rec = wd.get(ent["qid"])
    if not rec or rec.get("status") != "ok":
        return None
    birth, death = rec["dates"].get("P569"), rec["dates"].get("P570")
    if not birth or birth[1] > 7 or ent["s0"] != birth[0] or not death or death[1] < 9:
        return None
    if ent["s1"] is not None and ent["s1"] != death[0]:
        return None
    return dict(start=None, end=year_text(death[0]) if ent["s1"] is None else ent["ed"],
                conf="low" if ent["qid"] in CENTURY_LOW else KEEP,
                src=f"Wikidata {ent['qid']} P570 ({death[0]})",
                why=f"start {ent['s0']} was a century-precision P569 (precision {birth[1]}), not a year")


def parse_year(text: str | None) -> int | None:
    """The year the DB trigger derives from a date text ('-0400' -> -400, '1130-11-11' -> 1130)."""
    if text is None:
        return None
    m = re.match(r"^-?\d+", text)
    return int(m.group(0)) if m else None


def resolves(rel: dict, ents: dict, side: str, new: dict) -> bool:
    ent = dict(ents[rel[side]])
    for k, f in (("s0", "start"), ("s1", "end")):
        if new[f] != KEEP:
            ent[k] = parse_year(new[f])
    return fits(span_of(ent), rel_years(rel), tolerance(ent["etype"]) or 0)


def plan(conn) -> tuple[list[dict], dict[str, dict], dict[str, dict], dict[str, dict]]:
    flags = load_flags()
    ex = load_exclusions()
    rels, ents = load_state(conn, [f["relationship_id"] for f in flags])
    wd = wd_records()
    by8 = {f["relationship_id"][:8]: f["relationship_id"] for f in flags}
    unknown = set(DECISIONS) - set(by8)
    if unknown:
        raise SystemExit(f"DECISIONS name rows outside the slice: {sorted(unknown)}")
    date_fixes: dict[str, dict] = {}
    for id8, fix in ENTITY_DATES.items():
        eid = resolve(id8, ents)
        date_fixes[eid] = {**fix, "origin": "hand"}
    rows: list[dict] = []
    for f in flags:
        rid = f["relationship_id"]
        rel = rels.get(rid)
        base = {"relationship_id": rid, "severity": f["severity"], "detail": f["detail"],
                "relationship_type": f["relationship_type"]}
        if not rel:
            rows.append({**base, "class": "gone", "action": "skip", "reason": "relationship no longer exists"})
            continue
        src, tgt = ents[rel["source"]], ents[rel["target"]]
        base.update({"source_id": src["id"], "source_name": src["name"], "source_span": _span_txt(src),
                     "target_id": tgt["id"], "target_name": tgt["name"], "target_span": _span_txt(tgt),
                     "rel_years": _win_txt(rel_years(rel)), "description": rel["description"][:160]})
        if rel["source"] != f["source_id"] or rel["target"] != f["target_id"]:
            rows.append({**base, "class": "changed", "action": "skip", "reason": "endpoints changed since the audit"})
            continue
        if excluded(rel["source"], ex) or excluded(rel["target"], ex):
            rows.append({**base, "class": "excluded", "action": "skip", "reason": "an endpoint is a merge-review or user-decision row"})
            continue
        dec = DECISIONS.get(rid[:8])
        if dec and dec[0] != "leave":
            action, args, reason = dec
            row = {**base, "class": "hand", "action": action, "reason": reason}
            if action in (S, R):
                new = resolve(args["to"], ents)
                if excluded(new, ex):
                    row.update(action="skip", reason="re-point target is excluded: " + reason)
                row["new_" + ("source" if action == S else "target")] = new
                row["new_name"] = ents[new]["name"]
            elif action == "endpoints":
                ns = rel["source"] if args["source"] == "old_source" else resolve(args["source"], ents)
                nt = rel["source"] if args["target"] == "old_source" else resolve(args["target"], ents)
                row.update(new_source=ns, new_target=nt, new_name=f"{ents[ns]['name']} -> {ents[nt]['name']}")
            elif action == "delete":
                row["twin"] = by8[args["twin"]]
            rows.append(row)
            continue
        if dec:
            rows.append({**base, "class": dec[1]["why"], "action": "leave", "reason": dec[2]})
            continue
        # endpoint date fixes (hand-checked, then the mechanical century rule)
        sides = out_sides(rel, ents)
        fixed = [s for s in sides if rel[s] in date_fixes]
        for s in sides:
            eid = rel[s]
            if eid in date_fixes or excluded(eid, ex):
                continue
            cf = century_fix(ents[eid], wd)
            if cf and resolves(rel, ents, s, cf):
                date_fixes[eid] = {**cf, "origin": "century"}
                fixed.append(s)
        if fixed:
            names = ", ".join(ents[rel[s]]["name"] for s in fixed)
            still = [s for s in sides if s not in fixed]
            rows.append({**base, "class": "entity_dates", "action": "fix_dates",
                         "reason": f"endpoint dates fixed: {names}" + (" (other endpoint still out)" if still else ""),
                         "fixed_entities": " ".join(rel[s] for s in fixed)})
            continue
        cls, reason = auto_leave(rel, ents, wd, sides)
        rows.append({**base, "class": cls, "action": "leave", "reason": reason})
    # date fixes are planned per entity, guarded on the values read now
    for eid, fix in date_fixes.items():
        ent = ents[eid]
        fix["entity_id"], fix["name"] = eid, ent["name"]
        fix["old"] = (ent["sd"], ent["ed"], ent["conf"])
        fix["tr_id"] = ent["tr_id"]
        if excluded(eid, ex):
            fix["skip"] = "excluded"
        elif ent["tr_id"] is None:
            fix["skip"] = "no primary temporal range"
    return rows, date_fixes, rels, ents


def _span_txt(ent: dict) -> str:
    return f"{ent['s0'] if ent['s0'] is not None else ''}..{ent['s1'] if ent['s1'] is not None else ''}"


def _win_txt(w) -> str:
    return "" if not w else f"{w[0]}..{w[1]}"


def auto_leave(rel: dict, ents: dict, wd: dict, sides: list[str]) -> tuple[str, str]:
    src, tgt = ents[rel["source"]], ents[rel["target"]]
    window = rel_years(rel)
    if QIN in (rel["source"][:8], rel["target"][:8]):
        return "qin_state_dynasty", ("the Qin row carries the dynasty's QID and dates (221-206 BCE) but stands for the "
                                     "Warring States kingdom too; widen or split it (a modelling decision)")
    for s in sides:
        e = ents[rel[s]]
        if (e["etype"] == "political_entity" and e["s0"] is not None and e["s0"] >= MODERN_MIN_START
                and window and window[1] < e["s0"]):
            return "modern_state", (f"{e['name']} ({e['qid'] or 'no QID'}) starts at its modern state's founding "
                                    f"({e['s0']}); the relationship is earlier. Widen the row or re-point to the "
                                    f"era's polity (a modelling decision)")
    if rel["type"] in DOCUMENTARY:
        return "documentary", "not contemporaneous by nature (a later account or honour)"
    if rel["type"] in SUCCESSION and src["etype"] in EVENT_LIKE and tgt["etype"] in EVENT_LIKE:
        return "event_sequence", "one event followed another; a gap is expected"
    for s in sides or ("source", "target"):
        e = ents[rel[s]]
        rec = wd.get(e["qid"] or "")
        if e["etype"] == "person" and rec and rec.get("status") == "ok":
            b, d = rec["dates"].get("P569"), rec["dates"].get("P570")
            coarse = [v for v in (b, d) if v and v[1] <= 7 and v[0] in (e["s0"], e["s1"])]
            if coarse:
                return "century_precision", (f"{e['name']}'s dates are Wikidata century-precision values; "
                                             f"no finer source date")
    oldest = min([y for y in (window or ()) if y is not None]
                 + [y for e in (src, tgt) for y in (e["s0"], e["s1"]) if y is not None] or [0])
    if oldest < -1000:
        return "ancient_chronology", "Bronze Age dates: the chronologies disagree by decades"
    if not sides:
        return "reign_span", "both endpoints fit the relationship's years; their spans (often reigns) just do not touch"
    worst = 0
    for s in sides:
        e = ents[rel[s]]
        rng = span_of(e)
        if rng and window:
            worst = max(worst, window[0] - rng[1] if window[0] > rng[1] else rng[0] - window[1])
    if worst <= 15:
        return "near_miss", f"off by {worst} years: a reign span, a rounded date or a few years past a death"
    for s in sides:
        if ents[rel[s]]["etype"] in ("political_entity", "dynasty", "diplomatic_relationship", "military_unit"):
            return "polity_span", (f"{ents[rel[s]]['name']}'s row span is narrower than the polity's life "
                                   f"(no single clear source date to widen it)")
    return "unresolved", "needs research: no rule or hand decision"


# ── outputs ──────────────────────────────────────────────────────────────────
PLAN_FIELDS = ["relationship_id", "severity", "detail", "relationship_type", "class", "action", "reason",
               "source_id", "source_name", "source_span", "target_id", "target_name", "target_span",
               "rel_years", "new_source", "new_target", "new_name", "twin", "fixed_entities", "description"]
DATE_FIELDS = ["relationship_id", "class", "action", "entity_id", "name", "origin", "old_start", "old_end",
               "old_confidence", "new_start", "new_end", "new_confidence", "source", "reason"]


def date_rows(date_fixes: dict[str, dict]) -> list[dict]:
    out = []
    for eid, fx in sorted(date_fixes.items(), key=lambda kv: kv[1]["name"]):
        old_s, old_e, old_c = fx["old"]
        out.append({"relationship_id": "", "class": "entity_dates:" + fx["origin"],
                    "action": "skip:" + fx["skip"] if fx.get("skip") else "set_dates",
                    "entity_id": eid, "name": fx["name"], "origin": fx["origin"],
                    "old_start": old_s, "old_end": old_e, "old_confidence": old_c,
                    "new_start": old_s if fx["start"] == KEEP else fx["start"],
                    "new_end": old_e if fx["end"] == KEEP else fx["end"],
                    "new_confidence": old_c if fx["conf"] == KEEP else fx["conf"],
                    "source": fx["src"], "reason": fx["why"]})
    return out


def write_plan(rows: list[dict], date_fixes: dict[str, dict]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT / "planned.csv", rows, PLAN_FIELDS)
    write_csv(OUT / "planned-entity-dates.csv", date_rows(date_fixes), DATE_FIELDS)
    c = Counter((r["action"], r["class"]) for r in rows)
    for (a, k), n in sorted(c.items(), key=lambda kv: (kv[0][0], -kv[1])):
        print(f"  {a:12s} {k:22s} {n}")
    print(f"  entity date fixes: {sum(1 for f in date_fixes.values() if not f.get('skip'))} "
          f"({Counter(f['origin'] for f in date_fixes.values() if not f.get('skip'))})")


# ── apply ────────────────────────────────────────────────────────────────────
def sql_lit(v: Any) -> str:
    if v is None:
        return "NULL"
    return "'" + str(v).replace("'", "''") + "'"


def backup(stamp: str) -> Path:
    path = OUT / f"pre-apply-{stamp}.dump"
    with path.open("wb") as fh:
        subprocess.run([*COMPOSE, "exec", "-T", "db", "pg_dump", "-U", "history-mapped", "-Fc",
                        "-t", "relationships", "-t", "entity_temporal_ranges", "history-mapped"],
                       stdout=fh, check=True)
    if path.stat().st_size < 1000:
        raise SystemExit("backup looks empty")
    return path


def apply(conn, rows: list[dict], date_fixes: dict[str, dict], rels: dict, ents: dict) -> None:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bpath = backup(stamp)
    print(f"  backup: {bpath}")
    cur = conn.cursor()
    applied: list[dict] = []
    rollback: list[str] = []
    touched: set[str] = set()

    # entity dates
    for eid, fx in date_fixes.items():
        if fx.get("skip"):
            continue
        old_s, old_e, old_c = fx["old"]
        new_s = old_s if fx["start"] == KEEP else fx["start"]
        new_e = old_e if fx["end"] == KEEP else fx["end"]
        new_c = old_c if fx["conf"] == KEEP else fx["conf"]
        note = f"{NOTE}: {fx['src']}; {fx['why']}"
        cur.execute("SELECT notes, updated_at::text FROM entity_temporal_ranges WHERE temporal_range_id = %s",
                    (fx["tr_id"],))
        old_notes, old_upd = cur.fetchone()
        cur.execute("""
            UPDATE entity_temporal_ranges
               SET start_date = %s, end_date = %s, date_confidence = %s,
                   notes = CASE WHEN notes IS NULL OR notes = '' THEN %s ELSE notes || ' | ' || %s END,
                   updated_at = now()
             WHERE temporal_range_id = %s AND is_primary
               AND start_date IS NOT DISTINCT FROM %s AND end_date IS NOT DISTINCT FROM %s
               AND date_confidence IS NOT DISTINCT FROM %s
            RETURNING start_year, end_year""",
                    (new_s, new_e, new_c, note, note, fx["tr_id"], old_s, old_e, old_c))
        got = cur.fetchone()
        status = "applied" if got else "skipped:changed"
        applied.append({"kind": "entity_dates", "id": eid, "name": fx["name"], "status": status,
                        "old": f"{old_s}..{old_e} ({old_c})", "new": f"{new_s}..{new_e} ({new_c})",
                        "detail": note})
        if got:
            touched.add(eid)
            rollback.append(
                f"UPDATE entity_temporal_ranges SET start_date = {sql_lit(old_s)}, end_date = {sql_lit(old_e)}, "
                f"date_confidence = {sql_lit(old_c)}, notes = {sql_lit(old_notes)}, updated_at = {sql_lit(old_upd)} "
                f"WHERE temporal_range_id = {sql_lit(fx['tr_id'])} AND start_date IS NOT DISTINCT FROM {sql_lit(new_s)} "
                f"AND end_date IS NOT DISTINCT FROM {sql_lit(new_e)} AND notes LIKE {sql_lit(NOTE + ':%')} "
                f"OR temporal_range_id = {sql_lit(fx['tr_id'])} AND start_date IS NOT DISTINCT FROM {sql_lit(new_s)} "
                f"AND end_date IS NOT DISTINCT FROM {sql_lit(new_e)} AND notes LIKE {sql_lit('%| ' + NOTE + ':%')};")

    # relationships
    for r in rows:
        action = r["action"]
        if action not in (S, R, "endpoints", "reverse", "delete"):
            continue
        rid = r["relationship_id"]
        rel = rels[rid]
        old_s, old_t, rtype = rel["source"], rel["target"], rel["type"]
        if action == S:
            new_s, new_t = r["new_source"], old_t
        elif action == R:
            new_s, new_t = old_s, r["new_target"]
        elif action == "endpoints":
            new_s, new_t = r["new_source"], r["new_target"]
        elif action == "reverse":
            new_s, new_t = old_t, old_s
        else:
            new_s = new_t = None
        refs = refs_of(cur, rid)
        if action == "delete":
            twin = rels.get(r["twin"])
            cur.execute("""SELECT 1 FROM relationships WHERE relationship_id = %s AND source_entity_id = %s
                           AND target_entity_id = %s AND relationship_type = %s""",
                        (r["twin"], old_t, old_s, rtype))
            if not twin or not cur.fetchone():
                status = "skipped:twin_changed"
            elif refs:
                status = "skipped:" + refs
            else:
                cur.execute("SELECT row_to_json(r)::text FROM relationships r WHERE relationship_id = %s", (rid,))
                snap = cur.fetchone()[0]
                cur.execute("""DELETE FROM relationships WHERE relationship_id = %s AND source_entity_id = %s
                               AND target_entity_id = %s AND relationship_type = %s""", (rid, old_s, old_t, rtype))
                status = "applied" if cur.rowcount == 1 else "skipped:changed"
                if cur.rowcount == 1:
                    rollback.append(
                        f"INSERT INTO relationships SELECT * FROM json_populate_record(NULL::relationships, "
                        f"{sql_lit(snap)}) WHERE NOT EXISTS (SELECT 1 FROM relationships WHERE relationship_id = "
                        f"{sql_lit(rid)});")
            applied.append({"kind": "delete", "id": rid, "name": f"{ents[old_s]['name']} -{rtype}-> {ents[old_t]['name']}",
                            "status": status, "old": f"{old_s} -> {old_t}", "new": "", "detail": r["reason"]})
            if status == "applied":
                touched.update((old_s, old_t))
            continue
        cur.execute("""SELECT relationship_id::text FROM relationships WHERE source_entity_id = %s
                       AND target_entity_id = %s AND relationship_type = %s AND relationship_id <> %s""",
                    (new_s, new_t, rtype, rid))
        dup = cur.fetchone()
        if dup:
            status = f"skipped:would_duplicate:{dup[0]}"
        elif refs.startswith("geometry"):
            status = "skipped:" + refs
        else:
            cur.execute("""UPDATE relationships SET source_entity_id = %s, target_entity_id = %s
                           WHERE relationship_id = %s AND source_entity_id = %s AND target_entity_id = %s
                             AND relationship_type = %s""", (new_s, new_t, rid, old_s, old_t, rtype))
            status = "applied" if cur.rowcount == 1 else "skipped:changed"
            if cur.rowcount == 1:
                rollback.append(
                    f"UPDATE relationships SET source_entity_id = {sql_lit(old_s)}, target_entity_id = {sql_lit(old_t)} "
                    f"WHERE relationship_id = {sql_lit(rid)} AND source_entity_id = {sql_lit(new_s)} "
                    f"AND target_entity_id = {sql_lit(new_t)};")
                touched.update((old_s, old_t, new_s, new_t))
        applied.append({"kind": action, "id": rid,
                        "name": f"{ents[old_s]['name']} -{rtype}-> {ents[old_t]['name']}", "status": status,
                        "old": f"{old_s} -> {old_t}", "new": f"{new_s} -> {new_t}", "detail": r["reason"]})

    n_ok = sum(1 for a in applied if a["status"] == "applied")
    print(f"  writes applied: {n_ok}, skipped: {len(applied) - n_ok}")
    rb_text = (f"-- fix_relation_eras_c {stamp}: undo {len(rollback)} writes (guarded; a row changed since is left)\n"
               "BEGIN;\n" + "\n".join(reversed(rollback)) + "\nCOMMIT;\n"
               "-- then: php artisan timeline:rebuild <entity_id> for each id in applied.csv\n")
    test_rollback(conn, rollback)
    conn.commit()
    print("  committed")
    with (OUT / "rollback.sql").open("a", encoding="utf-8") as fh:
        fh.write(rb_text)
    write_csv(OUT / "applied.csv", applied, ["kind", "id", "name", "status", "old", "new", "detail"])
    (OUT / "touched-entities.txt").write_text("\n".join(sorted(touched)) + "\n")
    rebuild(sorted(touched))


def refs_of(cur, rid: str) -> str:
    cur.execute("SELECT count(*) FROM geometry_periods WHERE relationship_id = %s", (rid,))
    g = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM chronicle_entries WHERE primary_relationship_id = %s", (rid,))
    c = cur.fetchone()[0]
    if g:
        return f"geometry_periods:{g}"
    if c:
        return f"chronicle_entries:{c}"
    return ""


def test_rollback(conn, statements: list[str]) -> None:
    """Run the inverses inside a savepoint and check each one hits its row, then undo them."""
    cur = conn.cursor()
    cur.execute("SAVEPOINT rb_test")
    bad = 0
    for st in reversed(statements):
        cur.execute(st)
        if cur.rowcount != 1:
            bad += 1
            print(f"  rollback test: {cur.rowcount} rows for: {st[:140]}")
    cur.execute("ROLLBACK TO SAVEPOINT rb_test")
    if bad:
        conn.rollback()
        raise SystemExit(f"rollback test failed for {bad} statements; nothing committed")
    print(f"  rollback test: {len(statements)} inverses each matched one row (rolled back)")


def rebuild(entity_ids: list[str]) -> None:
    failed = []
    for i, eid in enumerate(entity_ids, 1):
        res = subprocess.run([*COMPOSE, "exec", "-T", "app", "php", "artisan", "timeline:rebuild", eid],
                             capture_output=True, text=True)
        if res.returncode != 0:
            failed.append(eid)
        if i % 25 == 0:
            print(f"  timeline:rebuild {i}/{len(entity_ids)}", flush=True)
    print(f"  timeline:rebuild done for {len(entity_ids) - len(failed)} entities"
          + (f"; failed: {failed}" if failed else ""))


# ── followup (after the first apply) ───────────────────────────────────────────
# Rows the first apply could not re-point because the corrected relation already existed
# (skipped:would_duplicate), plus d6a6a797, whose source was re-pointed instead of its target.
# Each is a wrong-endpoint copy of a correct row, so it is deleted (last resort) when the
# twin still has the corrected endpoints and nothing references the row.
# (rid, current source, current target, type, twin rid, twin source, twin target, reason)
FOLLOWUP_DELETES = [
    ("ddf55f14-231b-42d7-b858-70b8a77d3b84", "585a325c-9b8b-4ff0-b97d-fc02ddc56131", "ad6501d3-e775-4d73-9f29-333227a31431",
     "child_of", "24149803-626f-490a-819f-fbb40c2db8b7", None, "07996349-de54-41e4-8772-7007282dd951",
     "Romanos II's father was Constantine VII (row exists); Leo VI was his grandfather"),
    ("115611e6-189c-41b2-99ff-1f5c57b34475", "639e4606-a799-485a-8f8b-1f0f34f2189c", "53956ba7-b4bd-47e6-b355-dcc2c538ad58",
     "commanded_by", "7b115810-63c0-434d-a0aa-54ac0bbaea29", None, "6a808a33-1e3e-4010-9f3c-17547ca67652",
     "the Isere River (121 BCE) commander Fabius Maximus Allobrogicus already linked; Verrucosus died 203 BCE"),
    ("0d75bfde-caee-4aab-a8a1-4b273c317754", "b3436059-3f8b-4e9f-b145-7aac47defb0c", "14b9a61a-89ed-4641-acb9-c7a7e5887230",
     "defeated_at", "8043f9b9-2b12-49b5-9b0f-f8fbb489c750", "99974943-64d3-4846-81db-79ef78e88dc5", None,
     "Austria-Hungary at the Brusilov Offensive already linked; the Austrian Empire ended in 1867"),
    ("af8677a8-49bc-478d-80f4-72dfbb4de99c", "99974943-64d3-4846-81db-79ef78e88dc5", "08d7eb35-5f55-4519-89c5-e3496dc8329b",
     "participated_in", "62a277c4-fd34-4e0f-8f7a-4695f85f7c08", "8c57d738-cbba-4ec4-b72b-d8ecd92a8fee", None,
     "Habsburg Monarchy in the 1772 partition already linked; Austria-Hungary began in 1867"),
    ("100744fc-b68d-4371-99f9-ad09532e6044", "b3436059-3f8b-4e9f-b145-7aac47defb0c", "08d7eb35-5f55-4519-89c5-e3496dc8329b",
     "participated_in", "62a277c4-fd34-4e0f-8f7a-4695f85f7c08", "8c57d738-cbba-4ec4-b72b-d8ecd92a8fee", None,
     "Habsburg Monarchy in the 1772 partition already linked; the Austrian Empire began in 1804"),
    ("c6d73dcf-5891-4cdc-90ea-a4315006cd76", "5a4a883c-7cfc-40ce-82a5-cb1ac67b7345", "71cefb06-6358-49fe-bc9a-ebd8b98f40f4",
     "resided_in", "aeff1609-3634-435d-860d-f87f77f4dc80", None, "ee6bb2d1-30c8-43dd-9449-67544851f0ce",
     "Nero resided_in the city of Rome already linked; this copy points at the Roman Republic polity"),
    ("307a6e74-8038-4474-8c36-8c034577947e", "3f8058ca-8eb6-44db-be8c-7e6c56cf00e9", "71cefb06-6358-49fe-bc9a-ebd8b98f40f4",
     "resided_in", "b11b0b2a-ad1e-44f7-b373-bc3da5333d82", None, "ee6bb2d1-30c8-43dd-9449-67544851f0ce",
     "Servius Tullius resided_in the city of Rome already linked; this copy points at the Roman Republic polity"),
    ("c7dbfb12-432d-4550-a387-b4680f63cf2a", "76e6d5c4-2b72-43fa-abd6-90e09640c77b", "0a45be64-b5d9-43dc-9c2b-9b600b5890c3",
     "rules", "8a445115-f31a-4921-a02b-0da5f98e7ea1", "5b568c33-5fe6-41db-89cd-40fe26e97851", None,
     "Galdan Boshugtu Khan rules Dzungar already linked; this copy uses the namesake Galdan (Q4132297)"),
    ("77bf7fe7-2645-44e2-a119-8788e588a467", "efd03d45-8e54-4ce1-9b1d-48cba6a13572", "105b9782-8aad-4e2f-afa6-c7b487eaf9e8",
     "rules", "41632eed-1b96-4418-b8bb-5dc1e2395586", None, "0d64232f-a5e9-43d4-bfb1-c859e7455321",
     "Emperor Wu rules the Han dynasty already linked; this copy points at the Warring States state of Han"),
    ("be970385-4bf6-4f80-a5c0-805685e31cf4", "b3436059-3f8b-4e9f-b145-7aac47defb0c", "59bf2484-b730-4aa7-bc9c-3cd1cf2396c7",
     "victorious_at", "750e2060-f436-4ee0-b258-88656a34fc04", "8c57d738-cbba-4ec4-b72b-d8ecd92a8fee", None,
     "Habsburg Monarchy victorious at Kunersdorf (1759) already linked; the Austrian Empire began in 1804"),
    ("d6a6a797-55a4-4a1c-aaf4-022c496943af", "8c57d738-cbba-4ec4-b72b-d8ecd92a8fee", "99974943-64d3-4846-81db-79ef78e88dc5",
     "rules", "3dee9169-48be-478e-abf9-a9c78d6d1e76", "75fd6c71-24a5-49a2-a7e2-07338116c56a",
     "8c57d738-cbba-4ec4-b72b-d8ecd92a8fee",
     "first apply re-pointed the source (Maria Theresa) instead of the target; Maria Theresa rules "
     "Habsburg Monarchy already exists, so this mis-repointed copy goes"),
]
# (rid, source, old target, type, new target, reason)
FOLLOWUP_REPOINTS = [
    ("fa95b9ce-3a9b-44ae-a6fa-fafc9716bbc6", "2fa72901-6d8d-4843-8944-48651341d048", "99974943-64d3-4846-81db-79ef78e88dc5",
     "rules", "8c57d738-cbba-4ec4-b72b-d8ecd92a8fee",
     "Joseph II (1780-1790) ruled the Habsburg Monarchy (Q153136); Austria-Hungary began in 1867"),
]


def followup(conn) -> None:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = OUT / f"pre-followup-{stamp}.dump"
    with path.open("wb") as fh:
        subprocess.run([*COMPOSE, "exec", "-T", "db", "pg_dump", "-U", "history-mapped", "-Fc",
                        "-t", "relationships", "history-mapped"], stdout=fh, check=True)
    if path.stat().st_size < 1000:
        raise SystemExit("backup looks empty")
    print(f"  backup: {path}")
    cur = conn.cursor()
    cur.execute("SELECT entity_id::text, name FROM entities")
    names = dict(cur.fetchall())
    applied: list[dict] = []
    rollback: list[str] = []
    touched: set[str] = set()
    for rid, src, tgt, rtype, twin, tw_s, tw_t, why in FOLLOWUP_DELETES:
        cur.execute("""SELECT 1 FROM relationships WHERE relationship_id = %s AND relationship_type = %s
                       AND source_entity_id = %s AND target_entity_id = %s""", (rid, rtype, src, tgt))
        if not cur.fetchone():
            continue  # already handled by an earlier followup run (or changed since): nothing to record
        refs = refs_of(cur, rid)
        cur.execute("""SELECT 1 FROM relationships WHERE relationship_id = %s AND relationship_type = %s
                       AND source_entity_id = %s AND target_entity_id = %s""",
                    (twin, rtype, tw_s or src, tw_t or tgt))
        if not cur.fetchone():
            status = "skipped:twin_changed"
        elif refs:
            status = "skipped:" + refs
        else:
            cur.execute("SELECT row_to_json(r)::text FROM relationships r WHERE relationship_id = %s", (rid,))
            snap = cur.fetchone()
            cur.execute("""DELETE FROM relationships WHERE relationship_id = %s AND source_entity_id = %s
                           AND target_entity_id = %s AND relationship_type = %s""", (rid, src, tgt, rtype))
            status = "applied" if cur.rowcount == 1 else "skipped:changed"
            if cur.rowcount == 1:
                rollback.append(
                    f"INSERT INTO relationships SELECT * FROM json_populate_record(NULL::relationships, "
                    f"{sql_lit(snap[0])}) WHERE NOT EXISTS (SELECT 1 FROM relationships WHERE relationship_id = "
                    f"{sql_lit(rid)});")
                touched.update((src, tgt))
        applied.append({"kind": "followup_delete", "id": rid,
                        "name": f"{names.get(src)} -{rtype}-> {names.get(tgt)}", "status": status,
                        "old": f"{src} -> {tgt}", "new": "", "detail": f"twin {twin}; {why}"})
    for rid, src, old_t, rtype, new_t, why in FOLLOWUP_REPOINTS:
        cur.execute("""SELECT 1 FROM relationships WHERE relationship_id = %s AND relationship_type = %s
                       AND source_entity_id = %s AND target_entity_id = %s""", (rid, rtype, src, old_t))
        if not cur.fetchone():
            continue  # already handled by an earlier followup run (or changed since)
        cur.execute("""SELECT relationship_id::text FROM relationships WHERE source_entity_id = %s
                       AND target_entity_id = %s AND relationship_type = %s AND relationship_id <> %s""",
                    (src, new_t, rtype, rid))
        dup = cur.fetchone()
        refs = refs_of(cur, rid)
        if dup:
            status = f"skipped:would_duplicate:{dup[0]}"
        elif refs.startswith("geometry"):
            status = "skipped:" + refs
        else:
            cur.execute("""UPDATE relationships SET target_entity_id = %s WHERE relationship_id = %s
                           AND source_entity_id = %s AND target_entity_id = %s AND relationship_type = %s""",
                        (new_t, rid, src, old_t, rtype))
            status = "applied" if cur.rowcount == 1 else "skipped:changed"
            if cur.rowcount == 1:
                rollback.append(
                    f"UPDATE relationships SET target_entity_id = {sql_lit(old_t)} WHERE relationship_id = "
                    f"{sql_lit(rid)} AND source_entity_id = {sql_lit(src)} AND target_entity_id = {sql_lit(new_t)};")
                touched.update((src, old_t, new_t))
        applied.append({"kind": "followup_repoint_target", "id": rid,
                        "name": f"{names.get(src)} -{rtype}-> {names.get(old_t)}", "status": status,
                        "old": f"{src} -> {old_t}", "new": f"{src} -> {new_t}", "detail": why})
    n_ok = sum(1 for a in applied if a["status"] == "applied")
    print(f"  followup writes applied: {n_ok}, skipped: {len(applied) - n_ok}")
    test_rollback(conn, rollback)
    conn.commit()
    print("  committed")
    with (OUT / "rollback.sql").open("a", encoding="utf-8") as fh:
        fh.write(f"-- fix_relation_eras_c followup {stamp}: undo {len(rollback)} writes. For a full undo run THIS "
                 "block first, then the earlier apply block.\nBEGIN;\n" + "\n".join(reversed(rollback))
                 + "\nCOMMIT;\n")
    with (OUT / "applied.csv").open("a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["kind", "id", "name", "status", "old", "new", "detail"])
        w.writerows(applied)
    with (OUT / "touched-entities.txt").open("a", encoding="utf-8") as fh:
        fh.write("\n".join(sorted(touched)) + "\n")
    rebuild(sorted(touched))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("stage", choices=("plan", "apply", "followup"))
    args = ap.parse_args()
    if args.stage == "followup":
        conn = connect(read_only=False)
        followup(conn)
        conn.close()
        return
    conn = connect(read_only=args.stage == "plan")
    rows, date_fixes, rels, ents = plan(conn)
    write_plan(rows, date_fixes)
    if args.stage == "apply":
        apply(conn, rows, date_fixes, rels, ents)
    conn.close()


if __name__ == "__main__":
    main()
