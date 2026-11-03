"""Fix ``endpoint_era`` relationship flags, slice A (relationship_id 0-7).

Source: ``output/audit/identity-20261031/relation-flags.csv`` rows with
``check=endpoint_era``, ``severity=high`` and a relationship_id starting with
0-7 (another agent has 8-f). The flag means a contemporaneous relationship's
endpoints lie further apart in time than the C2 tolerance
(``pipeline/audit/relations.py``).

Every flag is first re-checked against the live DB (rows fixed since the audit
drop out). Then:

* **Era tables** (mechanical): a modern-state row (France dated 1958, Egypt
  1922, Russia 1991, ...) or a namesake polity row carrying links from another
  era is replaced by the existing row of the era-correct polity, chosen by the
  relationship's own years (else the other endpoint's span, else the years in
  its description). Each table entry is a window of historical years; windows
  leave out transition years (1792, 1804, 1848, ...), so a link dated on a
  regime change is left for a human.
* **Manual decisions** (``MANUAL``): re-point a wrong namesake endpoint
  (an event, person or polity of another era) to the correct existing row,
  reverse an inverted link, or re-type it. Each entry was checked by hand
  against the row texts and the relationship description.

A change is planned only when the new pair passes the same era check, neither
endpoint is excluded (merge-review survivors/losers, user-decision rows) and
the new endpoint is not the other endpoint. When the corrected link already
exists (same source, target and type), the flagged row is a redundant wrong
copy: it is deleted (``delete_duplicate``) and its chronicle entries are moved
to the existing twin. Everything else is listed in ``planned.csv`` with
``action=skip`` and a reason. Entity dates are never written.

Usage (local DB only)::

    scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit.fix_relation_eras            # plan
    scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit.fix_relation_eras --apply    # apply
    scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit.fix_relation_eras --rebuild  # timelines

``--apply`` dumps ``relationships`` and ``chronicle_entries`` first, applies
every planned change in one transaction with writes guarded on the values
read, writes ``applied.csv`` and ``rollback.sql`` (guarded inverses), and tests
the rollback inside a transaction it rolls back. ``--rebuild`` then runs
``php artisan timeline:rebuild`` for each touched entity (old and new endpoints).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from pipeline.audit.common import COMPOSE, REPO, connect, load_relationships, load_rows, write_csv
from pipeline.audit.dates import EVENT_TYPES, row_range, text_years, tolerance
from pipeline.audit.relations import ENDPOINT_RULES, endpoint_problem, era_problem

FLAGS = REPO / "output" / "audit" / "identity-20261031" / "relation-flags.csv"
OUT = REPO / "output" / "audit" / "relfix-era-a-20261101"
MERGE_VERDICTS = REPO / "output" / "audit" / "merge-review-20261101" / "verdicts.csv"
USER_DECISION_PREFIXES = ("a05afb75", "6255478f", "17d96812", "7baeedc3")
SLICE = set("01234567")

# ── era tables ───────────────────────────────────────────────────────────────
# suspect row (id prefix) -> [(first_year, last_year, replacement id prefix, label)]
# Windows are historical years (inclusive) and skip transition years. The
# narrowest window that holds the relationship's whole year range wins.
ERA_TABLES: dict[str, list[tuple[int, int, str, str]]] = {
    "1c3befeb": [  # France (Q142, dated 1958)
        (481, 842, "f05ecc7c", "Frankish kingdom"),
        (844, 986, "fe91f6d0", "West Francia"),
        (988, 1791, "b78831f7", "Kingdom of France"),
        (1793, 1803, "06ddcac7", "French First Republic"),
        (1805, 1813, "8f25d3e1", "First French Empire"),
        (1816, 1847, "b78831f7", "Kingdom of France"),  # Restoration + July Monarchy (row 987-1848)
        (1849, 1851, "bfa2fff5", "French Second Republic"),
        (1853, 1869, "7a5f13d3", "Second French Empire"),
        (1871, 1939, "c50f4e81", "French Third Republic"),
        (1947, 1957, "acf5cb18", "Fourth French Republic"),
    ],
    "9de131ab": [  # Egypt (Q79, dated 1922)
        (-4000, -31, "4aabfa9f", "Ancient Egypt"),
        (-304, -31, "eb7ee15b", "Ptolemaic Kingdom"),
        (-29, 394, "72d3329d", "Roman Egypt"),
        (970, 1170, "37a52557", "Fatimid Caliphate"),
        (1172, 1249, "a7f55ff4", "Ayyubid Sultanate"),
        (1251, 1516, "79953c6d", "Mamluk Sultanate"),
        (1518, 1797, "a5b04899", "Ottoman Egypt"),
        (1802, 1866, "a5b04899", "Ottoman Egypt"),
        (1868, 1913, "fc65419f", "Khedivate of Egypt"),
    ],
    "d6eef6d2": [  # Russia (QID of the Russian Empire, dated 1991)
        (882, 1239, "0c16d6af", "Kievan Rus"),
        (1283, 1546, "8623826b", "Muscovy"),
        (1548, 1720, "2d931bbf", "Tsardom of Russia"),
        (1722, 1916, "bee08f41", "Russian Empire"),
        (1918, 1921, "d9be48b0", "Soviet Russia"),
        (1923, 1990, "cc695213", "Soviet Union"),
    ],
    "376426ae": [  # Austria (Q40, dated 1918)
        (1527, 1803, "8c57d738", "Habsburg Monarchy"),
        (1805, 1866, "b3436059", "Austrian Empire"),
        (1868, 1917, "99974943", "Austria-Hungary"),
    ],
    "2ac323cb": [  # Poland (Q36, dated 1918)
        (1570, 1795, "d36f70ea", "Polish-Lithuanian Commonwealth"),
    ],
    "d7e394ae": [  # Norway (Q20, dated 1905)
        (872, 1396, "3140fc0c", "Kingdom of Norway"),
        (1537, 1813, "a915ca2e", "Denmark-Norway"),
    ],
    "69cb1bf0": [  # Israel (Q801, dated 1948)
        (-935, -720, "27d5cabf", "Kingdom of Israel"),
    ],
    "e6efe4ec": [  # Netherlands (Q55, dated 1795)
        (1581, 1794, "e835047d", "Dutch Republic"),
        (1796, 1805, "598cac90", "Batavian Republic"),
        (1807, 1809, "2547ea95", "Kingdom of Holland"),
    ],
    "98b5080f": [  # United Provinces (QID Rio de la Plata, text British India) carrying Dutch links
        (1568, 1794, "e835047d", "Dutch Republic"),
    ],
    "435bedec": [  # Tibet (Q2444884, 1912-1959)
        (618, 842, "bbb2ec8a", "Tibetan Empire"),
    ],
    "2b102792": [  # China (Q29520, region dated -1000..500)
        (618, 689, "7ddfaf8b", "Tang dynasty"),
        (706, 906, "7ddfaf8b", "Tang dynasty"),
        (1913, 1948, "e4eea5f2", "Republic of China"),
        (1950, 2100, "90f167d3", "People's Republic of China"),
    ],
    "105b9782": [  # Han (Warring States Han, dated -230) carrying Han-dynasty links
        (-205, 219, "0d64232f", "Han Dynasty"),
    ],
    "e021bc9d": [  # Germany (Q183, dated 1990)
        (1872, 1917, "018ffab9", "German Empire"),
    ],
    "df06c8b0": [  # Mali (Q912, dated 1960)
        (1235, 1600, "dd10f12d", "Mali Empire"),
    ],
    "d7d5d32a": [  # Morocco (Q1028, dated 1956)
        (1511, 1630, "28ed2a1c", "Saadi Sultanate"),
        (1660, 1911, "71db5918", "Alawi Sultanate"),
    ],
    "ad66ff5a": [  # Iran (Q794, dated 1979)
        (1790, 1924, "e5dd1837", "Qajar dynasty"),
    ],
    "e992487f": [  # Mexico (Q96, dated 1821)
        (1522, 1820, "1daddfce", "New Spain"),
    ],
    "38b25b9c": [  # Sri Lanka (Q854, dated 1972)
        (-376, 1016, "48da4229", "Anuradhapura Kingdom"),
    ],
    "3dac5cc1": [  # Normandy (region of France, dated 2016)
        (912, 1203, "330f2727", "Normandy (duchy)"),
    ],
    "66064d7b": [  # Bactria (region, dated -20..375): only the Greco-Bactrian kings
        (-249, -131, "d728bcc7", "Greco-Bactrian Kingdom"),
    ],
    "3e2bfbf5": [  # Saxony (Duchy of Saxony 804-1296) carrying Electorate links
        (1357, 1805, "6e3c5b7f", "Electorate of Saxony"),
    ],
    "f73081c3": [  # Mataram (Mataram kingdom 732-1016) carrying Mataram Sultanate links
        (1587, 1754, "3333b121", "Mataram Sultanate"),
    ],
    "8a4f574c": [  # India (Q668, dated 1947): Gupta-era links only
        (320, 549, "f32ba44e", "Gupta Empire"),
    ],
    "530b402b": [  # Ethiopia (Q115, dated 1995)
        (1271, 1973, "b35f2c31", "Ethiopian Empire"),
    ],
    "297965df": [  # Iceland (Q189, dated 1918)
        (931, 1263, "d2f9c2b1", "Icelandic Commonwealth"),
    ],
    "69343323": [  # Ireland (Q27, dated -4500..-4000)
        (1950, 2100, "2184f90c", "Republic of Ireland"),
    ],
}

# ── manual decisions ─────────────────────────────────────────────────────────
# relationship id prefix -> change. Keys: source / target (new endpoint id
# prefix), reverse (swap endpoints first), type (new relationship type),
# note (why). Endpoint prefixes refer to existing rows checked by hand.
MANUAL: dict[str, dict[str, Any]] = {
    # wrong namesake events
    "6081c971": {"target": "5e0eba95", "note": "Sennacherib 701 BCE -> Siege of Jerusalem (701 BCE), not the 1099 siege"},
    "5de287bf": {"target": "a7df3e70", "note": "Zealots overcome 70 CE -> First Jewish-Roman War (no 70 CE siege row)"},
    "3a24a143": {"target": "a7df3e70", "note": "Simon bar Giora lost Jerusalem 70 CE -> First Jewish-Roman War"},
    "3569e554": {"target": "a7df3e70", "note": "Titus took Jerusalem 70 CE -> First Jewish-Roman War"},
    "15a0fbd8": {"target": "44f195fb", "note": "Sidney Smith 1799 -> Siege of Acre (1799)"},
    "25121f1b": {"target": "44f195fb", "note": "Phelippeaux 1799 -> Siege of Acre (1799)"},
    "1f66ff22": {"target": "44f195fb", "note": "Ottoman defence 1799 -> Siege of Acre (1799)"},
    "39bd22af": {"target": "44f195fb", "note": "British support 1799 -> Siege of Acre (1799)"},
    "120a5c62": {"source": "06ddcac7", "target": "44f195fb",
                 "note": "French defeat at Acre 1799 -> French First Republic at Siege of Acre (1799)"},
    "12deca84": {"source": "1aac7bba", "note": "Allenby 1917 -> Capture of Jerusalem (1917)"},
    "1d5a67ea": {"target": "cbf05858", "note": "Sasanian capture 614 -> Persians Capture Jerusalem (614)"},
    "7b650328": {"source": "cbf05858", "type": "succeeded_by",
                 "note": "614 capture was followed by the removal of the True Cross (description); was preceded_by on the 1187 capture"},
    "47f2c7c9": {"source": "02f040b7", "note": "Cimon c. 466 BCE -> Battle of Eurymedon (466 BCE), not 190 BCE"},
    "1eb95b9f": {"target": "02f040b7", "note": "Persian defeat c. 466 BCE -> Battle of Eurymedon (466 BCE)"},
    "608c45a8": {"target": "02f040b7", "note": "Delian League c. 466 BCE -> Battle of Eurymedon (466 BCE)"},
    "755a56a9": {"target": "2bbe43e6", "note": "Belisarius 535-540 -> Gothic War (535-554), not 376-382"},
    "11237306": {"target": "2bbe43e6", "note": "Ostrogothic Kingdom 535-554 -> Gothic War (535-554)"},
    "776698fc": {"target": "2bbe43e6", "note": "Theudebert I 538 -> Gothic War (535-554)"},
    "61fbef23": {"target": "f7e225eb", "note": "Roman forces razed Napata 22 BCE -> Napata (city); the event row is the 592 BCE sack"},
    "2d332a27": {"target": "f7e225eb", "note": "Petronius won at Napata 22 BCE -> Napata (city)"},
    "0e2d2234": {"target": "b469eb5b", "note": "Ptolemy I 306 BCE -> Battle of Salamis (306 BCE), not 480 BCE"},
    "25fe0cd3": {"target": "b469eb5b", "note": "Demetrius 306 BCE -> Battle of Salamis (306 BCE)"},
    "742b1f19": {"target": "db6126e9", "note": "Byzantine loss of Syracuse 878 -> Muslim conquest of Sicily (827-902)"},
    "0096f596": {"target": "db6126e9", "note": "Aghlabid capture of Syracuse 878 -> Muslim conquest of Sicily (827-902)"},
    "68c82d31": {"target": "db6126e9", "note": "Emirate of Sicily took Syracuse 878 -> Muslim conquest of Sicily (827-902)"},
    "3adcaa59": {"target": "f32d675e", "note": "Luther 1521 -> Diet of Worms (1521), not 829"},
    "219107d2": {"target": "f32d675e", "note": "Charles V 1521 -> Diet of Worms (1521)"},
    "7d1851c3": {"target": "e8aa2520", "note": "Artaxerxes III 346 BCE -> Revolt of Sidon (c. 345 BCE), not the 677 BCE destruction"},
    "3a470fdf": {"target": "8649cc89", "note": "Alexios I 1081 -> Battle of Dyrrhachium (1081)"},
    "76ff5316": {"target": "3c406424", "note": "Necho II 609 BCE -> Battle of Megiddo (609 BCE)"},
    "1947eec5": {"target": "86d6433c", "note": "Sargon II 720 BCE -> Levantine Campaign near Rafah (720 BCE), not Raphia 217 BCE"},
    "6d20ee17": {"source": "4aabfa9f", "target": "86d6433c",
                 "note": "Egyptian army with the rebels 720 BCE -> Ancient Egypt at the 720 BCE Rafah campaign"},
    "70a37ee2": {"target": "bedbe25e", "note": "Mongols defeated at Tong Pass 1230 -> Tong Pass (place); the event row is the 211 battle"},
    "73df9533": {"target": "79e59842", "note": "Baibars 1268 -> Capture of Antioch (1268)"},
    "4e083dfc": {"target": "8bcb898a", "note": "Fourth Crusade 1204 -> Sack of Constantinople (1204)"},
    "4ca1de5e": {"target": "1e5e5245", "note": "Zengi 1144 -> Conquest of County of Edessa (1144)"},
    "1f8813d5": {"target": "618729e9", "note": "Sasanian capture of Alexandria 619-621 -> Shahrbaraz Invades Egypt (618-621)"},
    "2d8964fb": {"target": "b87d7766", "note": "Cordoba emirate 902 -> Conquest of the Balearic Islands (902), not 123 BCE"},
    "33e6f3e3": {"source": "58b73930", "note": "Safavid signature 1723 -> Treaty of Saint Petersburg (1723), not 1875"},
    # wrong namesake persons
    "55dc9e5f": {"target": "0374a4bb", "note": "Jack Cade 1450 -> Henry VI of England, not Emperor Henry VI"},
    "5528abc9": {"target": "0374a4bb", "type": "married_to",
                 "note": "Margaret of Anjou married Henry VI of England in 1445 (description); was resided_in Emperor Henry VI"},
    "37ddbcf4": {"source": "86669b8c", "note": "abdicated 1808 -> Charles IV of Spain, not Emperor Charles IV"},
    "61e7ebd3": {"source": "b5529392", "note": "Mahmud born 971, Ghaznavid -> Mahmud of Ghazni (row 'Mahmud' carries a 1965 politician's QID)"},
    "34ccc1ce": {"target": "b5529392", "note": "Sabuktigin's successor -> Mahmud of Ghazni"},
    "7f303370": {"target": "821ee7c2", "note": "1832 Levant invasion -> Ibrahim Pasha of Egypt (1789-1848), not Pargali Ibrahim"},
    "3b541609": {"source": "cbea5a76", "note": "c. 228 BCE Parthia -> Arsaces I of Parthia, not Arsaces I of Armenia"},
    "2b96bfba": {"source": "adb85809", "note": "Hafsid ruler 1249-1277 -> Muhammad I al-Mustansir, not the Fatimid caliph"},
    "48bb28c3": {"source": "7aec0155", "note": "Buyid Adud al-Dawla -> Fanna Khusraw (Adud al-Dawla); row 'Adud al-Dawla' is dated 1381"},
    "6160246b": {"target": "44ee1306", "note": "Hakon IV was succeeded by Magnus VI in 1263 (description), not by 'Norway'"},
    "29bc6999": {"reverse": True, "target": "3140fc0c",
                 "note": "inverted: Olaf II ruled Norway 1015-1030 -> Olaf II Haraldsson rules Kingdom of Norway"},
    "414cd2f4": {"reverse": True, "target": "4aabfa9f",
                 "note": "inverted: the Twenty-fifth Dynasty ruled Egypt -> Twenty-fifth Dynasty rules Ancient Egypt"},
    # wrong namesake polities
    "74911c28": {"source": "d36f70ea", "note": "Poland-Lithuania 1621 -> Polish-Lithuanian Commonwealth, not Venezuela's First Republic"},
    "2273ff92": {"target": "d36f70ea", "note": "Poland-Lithuania 1672 -> Polish-Lithuanian Commonwealth"},
    "035f64e5": {"source": "4ff0d5ed", "note": "1512 conquest -> Kingdom of Navarre, not the Florida town"},
    "6b68b79d": {"target": "4ff0d5ed", "note": "1512 conquest -> Kingdom of Navarre"},
    "0e1efac2": {"target": "8b120f62", "note": "King Wu founded Zhou in 1046 BCE -> Zhou, not Wu Zetian's Zhou (690-705)"},
    "24928a48": {"source": "106739db", "note": "Vandal sack of Rome 455 -> Western Roman Empire, not the Roman Republic"},
    "15c9c341": {"target": "ee6bb2d1", "note": "Valentinian III killed in Rome 455 -> Rome (city)"},
    "529ecb5f": {"target": "ee6bb2d1", "note": "Otto II died at Rome 983 -> Rome (city)"},
    "5e3e3927": {"target": "ee6bb2d1", "note": "Raphael died in Rome 1520 -> Rome (city)"},
    "6932cde3": {"target": "ee6bb2d1", "note": "Michelangelo died in Rome 1564 -> Rome (city)"},
    "6d40dc93": {"target": "ee6bb2d1", "note": "John VIII reigned from Rome -> Rome (city)"},
    "200f6a2d": {"target": "ee6bb2d1", "note": "Leo Africanus lived in Rome -> Rome (city)"},
    "293800ba": {"target": "ee6bb2d1", "note": "Pico in Rome 1486 -> Rome (city)"},
    "4fdc0cb2": {"target": "ee6bb2d1", "note": "Julius II governed from Rome -> Rome (city)"},
    "47e04f2e": {"target": "ee6bb2d1", "note": "Leo X ruled from Rome -> Rome (city)"},
    "7768c09f": {"source": "c980506b", "note": "description: the Holy Roman Empire took part in the Second Crusade under Conrad III"},
    "365b308a": {"target": "04d4a881", "note": "Henry IV ruled Germany as king 1056-1106 -> Kingdom of Germany"},
    "6c39a755": {"target": "c980506b", "note": "description: Conrad III ruled the Holy Roman Empire"},
    "0e2ab631": {"target": "fbfec15d", "note": "Shi Lang's 1683 victory ended the Zheng state -> Kingdom of Tungning, not modern Taiwan"},
    "7a9bd46f": {"source": "131c7d2e", "note": "Uzbek forces at Herat 1598 -> Uzbeks (people), not modern Uzbekistan"},
    "363118d9": {"target": "131c7d2e", "note": "Abbas I fought the Uzbeks at Herat 1598 -> Uzbeks (people)"},
    "38721e88": {"source": "a222cce1", "note": "description: the New Model Army won at Naseby 1645 (row 'British Parliament' is dated 1801)"},
    "0e58c383": {"target": "9a0ec981", "note": "Bhavavarman I ruled Cambodia as king of Chenla 580-598 -> Chenla"},
    "59eb0022": {"target": "8bc8f7bb", "note": "Lascaris, Grandmaster 1643 -> Knights Hospitaller (row 'Order of St John' is dated 1909)"},
    "219bfece": {"target": "039cde8b", "note": "Hisham II, caliph 976-1013 -> Caliphate of Cordoba, not the Umayyad Caliphate of Damascus"},
    "3db10bb5": {"source": "ba74ca53", "note": "description: the Roman Republic lost at the Allia in 387 BCE"},
    "6b73589e": {"target": "c50f4e81", "note": "Cayor under French control 1886 -> French Third Republic (row 'French forces' is dated 1993)"},
    "42f95af5": {"target": "c50f4e81", "note": "France signed the Treaty of Bissandougou 1887 -> French Third Republic"},
    # boundary years and lifetimes checked by hand
    "37f92db3": {"target": "eb7ee15b", "note": "Rome's war on Egypt 32-30 BCE was against the Ptolemaic Kingdom"},
    "6726c806": {"source": "eb7ee15b", "note": "Egypt's Ptolemaic forces defeated in 30 BCE -> Ptolemaic Kingdom"},
    "53230965": {"target": "eb7ee15b", "note": "Ptolemy XV co-ruler 44-30 BCE -> Ptolemaic Kingdom"},
    "1bde2fdb": {"target": "72d3329d", "note": "Augustus ruled Egypt as a Roman province from 30 BCE -> Roman Egypt"},
    "78b4f8a0": {"target": "72d3329d", "note": "Cornelius Gallus, first prefect of Egypt 30-26 BCE -> Roman Egypt"},
    "03acadc9": {"target": "2d931bbf", "note": "Treaty of Nystad, 10 Sep 1721, before Peter I took the imperial title (Nov 1721) -> Tsardom of Russia"},
    "4dcc7b62": {"target": "b78831f7", "note": "Treaty of Paris, 30 May 1814, signed for Louis XVIII -> Kingdom of France"},
    "37be343b": {"source": "b78831f7", "note": "Valmy, 20 Sep 1792, the day before the monarchy was abolished; Wikipedia lists the Kingdom of France"},
    "213ccd02": {"target": "b78831f7", "note": "Sieyes wrote in France in 1789 (description) -> Kingdom of France"},
    "328b7bf3": {"target": "06ddcac7", "note": "Jacques Chastan born 7 Oct 1803 (Wikipedia) -> French First Republic"},
    "6d70cd60": {"target": "06ddcac7", "note": "Laurent Imbert born 23 Mar 1796 (Wikipedia) -> French First Republic"},
    # ST rows (both endpoints off the stated year), Egypt side checked by hand
    "2bfdc4c5": {"target": "4aabfa9f", "note": "Ramesses II ruled New Kingdom Egypt -> Ancient Egypt"},
    "0749229d": {"target": "4aabfa9f", "note": "Tutankhamun ruled Egypt -> Ancient Egypt"},
    "46d9122a": {"target": "4aabfa9f", "note": "Psamtik II pharaoh of Egypt -> Ancient Egypt"},
    "5a3d4a50": {"target": "4aabfa9f", "note": "Pepi II ruled Egypt -> Ancient Egypt"},
    "2346ed48": {"source": "4aabfa9f", "note": "Egypt aided the Sidonian rebels c. 351 BCE -> Ancient Egypt"},
    "0d5090e1": {"reverse": True, "source": "4aabfa9f",
                 "note": "inverted: the Hyksos controlled the Nile Delta (description) -> Ancient Egypt controlled_by Hyksos"},
}

# relationship id prefix -> reason; left unchanged, listed for a human.
MANUAL_SKIP: dict[str, str] = {
    "160164ae": "relation inverted in meaning: Ptolemy I repelled the invasion (description) but the link says defeated_at",
    "42fe13d0": "Nanzhao defeated_at 'Tibet' for the Battle of Shenchuan (Nanzhao won); needs a battle row",
    "6b3204d9": "inverted (France controlled_by Saint-Domingue) and spans several French regimes",
    "1227a4d0": "Teimuraz I (1651-1653) linked to the Teimuraz II row (1700-1762); no Teimuraz I row",
    "064fc180": "Russia participated_in Austrian Empire for Kunersdorf 1759: wrong relation type and target",
    "0b8c9a61": "Harsiesi row is dated -100 (single year); leave until the person's dates are checked",
    "63e76f86": "ACFTU controlled_by China 1925: re-pointing to the Republic of China would claim ROC control of a CCP-led union",
}


# ── notes for what is left (planned.csv ``human_note``) ──────────────────────
# endpoint name -> why its flagged links were left. Keys are the endpoint whose
# span disagrees with the relationship's years.
_NO_ERA_ROW = ("modern-state or region row; no row exists for the polity of that era "
               "(create one, or accept the modern row)")
_REGION = "region/people row with dates no source gives (span invented); needs a dating decision, not a re-point"
_WRONG_QID = "endpoint carries a namesake's QID and the dates that came with it; fix the QID/dates first"
_NO_NAMESAKE_ROW = "wrong namesake endpoint, but the correct row does not exist"
_ODD_DATE = "endpoint row (no QID) has a wrong date and no source in hand for the right one"
_BAD_LINK = "the link itself is wrong (type, direction or target); needs a human rewrite or delete"
ENDPOINT_NOTES: dict[str, str] = {
    **dict.fromkeys(["Armenia", "Poland", "Syria", "Bavaria", "Italy", "Austria", "Cyprus", "Brazil", "Iraq",
                     "Croatia", "Sindh", "India", "Yemen", "Vietnam", "Oman", "Egypt", "Tibet", "Israel",
                     "Sri Lanka", "Greece", "Estonia", "Kyrgyz", "Andhra Pradesh", "Gujarat", "New Zealand",
                     "Republic of the Philippines", "Massachusetts", "Henan", "Libya", "Taiwan", "Iceland",
                     "England", "Burgundy", "Thuringia", "Azerbaijan", "Fergana", "Brunei", "Sudan", "Maldives",
                     "Tamil Nadu", "Pernambuco", "Manchuria", "Inner Mongolia", "Palestine", "Madagascar", "Peru",
                     "Marshall Islands", "Solomon Islands", "East Java", "Faroe Islands", "Deli", "Ōmura",
                     "Morocco", "France", "Russia", "China", "Ireland", "Persia", "Spain", "Britain", "Africa",
                     "Mesopotamia", "Kounta", "Baloch", "Huaixi", "Shaanxi", "Sichuan", "Blekinge", "Malwa",
                     "Magadha", "Babylonia", "Khwarazm", "Chera", "Khmer Empire", "Duchy of Aquitaine",
                     "Brandenburg", "Banat of Temesvár", "Gaochang", "Licchavi", "New Holland", "Australia",
                     "Mauretania", "Fergana"], _NO_ERA_ROW),
    **dict.fromkeys(["Jin", "Qin", "Kingdom of Hungary", "Later Jin", "Dai", "Zeng", "Ba", "Liaodong"],
                    "namesake polity: the row is another state of the same name (QID/dates of that state); "
                    "no row for the state these links mean"),
    **dict.fromkeys(["Iberia", "Bactria", "Lycians", "Saka", "Yuezhi", "Kush", "Anatolia", "Brittany", "Boers",
                     "Massagetae", "Scythians", "Kizzuwatna", "Ahhiyawa", "Meluhha", "Gutians", "Irem", "Mexica",
                     "Dynasty of E", "Karkota dynasty", "Middle Assyrian Empire", "Akkadian Empire"], _REGION),
    "Xia dynasty": "traditional (Liu Xin, 2205 BCE) vs modern (2070 BCE) chronology; the link says which it uses",
    **dict.fromkeys(["Afzal Khan", "Eji", "Ishtar", "George William", "Amin", "Karan Singh", "Lady He", "Li Ting",
                     "Sei", "Suhandi", "Susi", "Ngola", "Ada", "Charles Leclerc", "John Cartier", "Andreas Hofer",
                     "Gabriel", "Galdan", "Aretas", "Yahya ibn Umar", "Stephen", "Abu al-Qasim Ahmad", "Idris II",
                     "Berengar I", "Robert I", "Henry II", "Drogo", "Guntram", "Hilderic", "Empress Wang",
                     "Liu Jing", "Liu Yan", "Damodaragupta", "William Owen", "Ivanko", "Maria Palaiologina",
                     "Vahan Mamikonian", "Peithon", "Vasishka", "Girondins", "Ga", "Ula", "Caeté", "Livonia",
                     "Ioannes", "Ismail Kamil", "Mahmud", "Paulinus", "Conon", "Pammenes", "Gorgias", "Athenaeus",
                     "Xanthippus", "Pantaleon", "Jehoahaz", "Wang Jun", "Marcus Junius Silanus", "Peter",
                     "Nicholas Brady", "Cui Hao", "Olympias", "Count of Enghien", "Hongxi Emperor", "Sinmun",
                     "Wencheng", "Pothinus", "Sematawytefnakht", "Heracleides", "Nimlot", "Li Tiao", "Tiye",
                     "Shaka", "Pelagius", "Nicanor", "Constantine III", "Constantine the Great",
                     "Emperor Shun of Han", "Firmus", "Lucius Antonius", "Teimuraz I"],
                    _WRONG_QID + " (or the namesake has no row of its own)"),
    **dict.fromkeys(["Capture of Damascus", "Sack of Antioch", "Battle of the Nile", "Social War",
                     "Battle of Beth Horon", "Siege of Jerusalem", "Battle of Callinicum", "Siege of Nicaea",
                     "Lateran Council", "Siege of Damascus", "Battle of the Lycus", "Siege of Mérida",
                     "Siege of Seville", "Siege of Tripoli", "Capture of Nanjing", "Destruction of Sidon",
                     "Sack of Napata", "Archbishopric of Magdeburg", "Holy League", "Ismail", "Hasdrubal",
                     "Mithridates V"], _NO_NAMESAKE_ROW),
    **dict.fromkeys(["Shamshi-Adad I", "Pepi I", "Hormizd I", "Ardashir II", "Luong Ky", "Malietoa Savea",
                     "Mara Takla Haymanot", "Zacharias III", "Talakaifaiki", "Adud al-Dawla", "Brennus",
                     "Eweka I", "Gongsun Sui", "Harsiesi"], _ODD_DATE),
    **dict.fromkeys(["Mustafa Kemal Atatürk", "Æthelbald", "Arrian", "Ahmad ibn Hanbal", "Cyril", "Sri Gupta",
                     "Treaty of Zuhab", "Zhao Xie", "Xuanzang", "Phoenicia", "Abdallah ibn Yasin",
                     "Francis, Duke of Guise"], _BAD_LINK),
}

# ── helpers ─────────────────────────────────────────────────────────────────

def load_slice() -> list[dict[str, str]]:
    with FLAGS.open(newline="", encoding="utf-8") as fh:
        return [r for r in csv.DictReader(fh)
                if r["check"] == "endpoint_era" and r["severity"] == "high" and r["relationship_id"][0] in SLICE]


def load_exclusions() -> set[str]:
    out: set[str] = set()
    with MERGE_VERDICTS.open(newline="", encoding="utf-8") as fh:
        for v in csv.DictReader(fh):
            out.update(x for x in (v.get("survivor_id"), v.get("loser_id")) if x)
    return out


def excluded(eid: str, excl: set[str]) -> bool:
    return eid in excl or eid.startswith(USER_DECISION_PREFIXES)


def resolve(prefix: str, rows: dict[str, Any]) -> str:
    hits = [eid for eid in rows if eid.startswith(prefix)]
    if len(hits) != 1:
        raise SystemExit(f"entity prefix {prefix!r} matches {len(hits)} rows")
    return hits[0]


def rel_years(rel: dict[str, Any], other) -> tuple[tuple[int, int] | None, str]:
    """The years a relationship is about: its own years, else the other
    endpoint's span (a person's life, an event's date), else its text."""
    ys = [y for y in (rel["start"], rel["end"]) if y is not None]
    if ys:
        return (min(ys), max(ys)), "relationship"
    if other.type == "person" or other.type in EVENT_TYPES:
        span = row_range(other.type, other.start, other.end)
        if span and other.start is not None and other.end is not None:
            return span, "other_endpoint"
    ys = text_years(rel["description"])
    if ys:
        return (min(ys), max(ys)), "description"
    return None, ""


def era_pick(table, years: tuple[int, int]) -> tuple[str, str] | None:
    fits = [(hi - lo, pid, label) for lo, hi, pid, label in table if lo <= years[0] and years[1] <= hi]
    if not fits:
        return None
    fits.sort()
    return fits[0][1], fits[0][2]


def agrees(other, years: tuple[int, int]) -> bool:
    """The kept endpoint fits the relationship's years (within its C2
    tolerance), so the other endpoint is the one that is off."""
    span = row_range(other.type, other.start, other.end)
    tol = tolerance(other.type)
    if span is None or tol is None:
        return True
    return span[0] - tol <= years[1] and years[0] <= span[1] + tol


def would_flag(rtype: str, src, tgt) -> bool:
    return era_problem(rtype, src, tgt) is not None


def inverted(rtype: str, src_type: str, tgt_type: str) -> bool:
    """The link's endpoint types only fit the relationship type reversed."""
    if rtype not in ENDPOINT_RULES:
        return False
    return bool(endpoint_problem(rtype, src_type, tgt_type)) and not endpoint_problem(rtype, tgt_type, src_type)


# ── planning ────────────────────────────────────────────────────────────────

FIELDS = ["relationship_id", "action", "method", "relationship_type", "new_type", "years", "years_from",
          "old_source_id", "old_source", "old_target_id", "old_target", "new_source_id", "new_source",
          "new_target_id", "new_target", "twin_id", "chronicle_entries", "reason", "description"]


def plan(conn) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = load_rows(conn)
    rels = {r["id"]: r for r in load_relationships(conn)}
    triples: dict[tuple[str, str, str], list[str]] = {}
    for r in rels.values():
        triples.setdefault((r["source"], r["target"], r["type"]), []).append(r["id"])
    cur = conn.cursor()
    cur.execute("SELECT primary_relationship_id::text, count(*) FROM chronicle_entries "
                "WHERE primary_relationship_id IS NOT NULL GROUP BY 1")
    chron = dict(cur.fetchall())
    excl = load_exclusions()
    tables = {resolve(k, rows): [(lo, hi, resolve(p, rows), lab) for lo, hi, p, lab in v]
              for k, v in ERA_TABLES.items()}
    flags = load_slice()
    by_prefix = {}
    for f in flags:
        by_prefix.setdefault(f["relationship_id"][:8], []).append(f["relationship_id"])
    for key in list(MANUAL) + list(MANUAL_SKIP):
        if len(by_prefix.get(key, [])) != 1:
            raise SystemExit(f"manual key {key!r} matches {len(by_prefix.get(key, []))} flagged relationships")

    out: list[dict[str, Any]] = []
    planned_triples: dict[tuple[str, str, str], str] = {}
    for f in flags:
        rid = f["relationship_id"]
        rel = rels.get(rid)
        base = {"relationship_id": rid, "relationship_type": f["relationship_type"],
                "old_source_id": f["source_id"], "old_source": f["source_name"],
                "old_target_id": f["target_id"], "old_target": f["target_name"],
                "description": f["description"]}
        if rel is None:
            out.append({**base, "action": "skip", "reason": "relationship_gone"})
            continue
        src, tgt = rows[rel["source"]], rows[rel["target"]]
        base.update({"relationship_type": rel["type"], "old_source_id": src.id, "old_source": src.name,
                     "old_target_id": tgt.id, "old_target": tgt.name, "description": rel["description"],
                     "years": f"{rel['start']}..{rel['end']}"})
        if excluded(src.id, excl) or excluded(tgt.id, excl):
            out.append({**base, "action": "skip", "reason": "excluded_endpoint (merge review / user decision)"})
            continue
        if not would_flag(rel["type"], src, tgt):
            out.append({**base, "action": "skip", "reason": "resolved_since_audit"})
            continue

        key = rid[:8]
        new_src, new_tgt, new_type, method, note, years_from = src.id, tgt.id, rel["type"], "", "", ""
        if key in MANUAL_SKIP:
            out.append({**base, "action": "skip", "method": "manual", "reason": MANUAL_SKIP[key]})
            continue
        if key in MANUAL:
            m = MANUAL[key]
            method, note = "manual", m["note"]
            if m.get("reverse"):
                new_src, new_tgt = new_tgt, new_src
            if "source" in m:
                new_src = resolve(m["source"], rows)
            if "target" in m:
                new_tgt = resolve(m["target"], rows)
            new_type = m.get("type", new_type)
        else:
            # which endpoint is off: the one an era table knows
            side = "source" if src.id in tables else "target" if tgt.id in tables else None
            if side is None:
                out.append({**base, "action": "skip", "reason": "no_rule (see report: namesake/date/no era row)"})
                continue
            other = tgt if side == "source" else src
            suspect = src if side == "source" else tgt
            years, years_from = rel_years(rel, other)
            if years is None:
                out.append({**base, "action": "skip", "reason": "no_year"})
                continue
            # only when the kept endpoint agrees with those years
            if not agrees(other, years):
                out.append({**base, "action": "skip", "years_from": years_from,
                            "reason": f"kept endpoint {other.name} also off the years {years[0]}..{years[1]}"})
                continue
            pick = era_pick(tables[suspect.id], years)
            if pick is None:
                out.append({**base, "action": "skip", "years_from": years_from,
                            "reason": f"no_era_row for {years[0]}..{years[1]} ({suspect.name})"})
                continue
            new_id, label = pick
            if side == "source":
                new_src = new_id
            else:
                new_tgt = new_id
            method, note = "era_table", f"{suspect.name} {years[0]}..{years[1]} -> {label}"
            # an inverted link (e.g. 'France signed_by Treaty') is reversed too
            if inverted(rel["type"], rows[new_src].type, rows[new_tgt].type):
                new_src, new_tgt = new_tgt, new_src
                note += "; reversed (endpoint types fit only the other way round)"

        ns, nt = rows[new_src], rows[new_tgt]
        row = {**base, "method": method, "new_type": new_type if new_type != rel["type"] else "",
               "years_from": years_from, "new_source_id": ns.id, "new_source": ns.name,
               "new_target_id": nt.id, "new_target": nt.name}
        reason = None
        if new_src == new_tgt:
            reason = "self_link"
        elif excluded(new_src, excl) or excluded(new_tgt, excl):
            reason = "new endpoint excluded (merge review / user decision)"
        elif would_flag(new_type, ns, nt):
            reason = "new pair still out of era"
        if reason:
            out.append({**row, "action": "skip", "reason": f"{reason}; proposed: {note}"})
            continue
        triple = (new_src, new_tgt, new_type)
        twin = planned_triples.get(triple) or next(iter(t for t in triples.get(triple, []) if t != rid), None)
        if twin:
            # the corrected link already exists: this row is a redundant wrong
            # copy. Delete it; its chronicle entries move to the twin.
            out.append({**row, "action": "delete_duplicate", "twin_id": twin, "chronicle_entries": chron.get(rid, 0),
                        "reason": f"corrected link already exists as {twin[:8]}; {note}"})
            continue
        planned_triples[triple] = rid
        out.append({**row, "action": "update", "chronicle_entries": chron.get(rid, 0), "reason": note})
    meta = {"rows": rows}
    return out, meta


# ── apply ───────────────────────────────────────────────────────────────────

def _sql_lit(v: Any) -> str:
    return "NULL" if v is None else "'" + str(v).replace("'", "''") + "'"


def backup(out_dir: Path) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = out_dir / f"backup-relationships-chronicle_entries-{stamp}.dump"
    with path.open("wb") as fh:
        subprocess.run([*COMPOSE, "exec", "-T", "db", "pg_dump", "-U", "history-mapped", "-Fc",
                        "-t", "relationships", "-t", "chronicle_entries", "history-mapped"], stdout=fh, check=True)
    if path.stat().st_size < 1000:
        raise SystemExit(f"backup {path} looks empty")
    return path


def apply(conn, planned: list[dict[str, Any]], out_dir: Path) -> None:
    todo = [p for p in planned if p["action"] == "update"]
    bk = backup(out_dir)
    print(f"backup: {bk}")
    applied, rollback_upd, rollback_del = [], [], []
    cur = conn.cursor()
    with conn.transaction():
        for p in todo:
            new_type = p["new_type"] or p["relationship_type"]
            cur.execute(
                """UPDATE relationships SET source_entity_id = %s, target_entity_id = %s,
                          relationship_type = %s::relationship_type
                   WHERE relationship_id = %s AND source_entity_id = %s AND target_entity_id = %s
                         AND relationship_type = %s::relationship_type""",
                (p["new_source_id"], p["new_target_id"], new_type, p["relationship_id"],
                 p["old_source_id"], p["old_target_id"], p["relationship_type"]))
            if cur.rowcount != 1:
                applied.append({**p, "action": "skipped_changed_concurrently"})
                continue
            applied.append({**p, "action": "applied"})
            rollback_upd.append(
                f"UPDATE relationships SET source_entity_id = {_sql_lit(p['old_source_id'])}, "
                f"target_entity_id = {_sql_lit(p['old_target_id'])}, "
                f"relationship_type = {_sql_lit(p['relationship_type'])}::relationship_type "
                f"WHERE relationship_id = {_sql_lit(p['relationship_id'])} "
                f"AND source_entity_id = {_sql_lit(p['new_source_id'])} "
                f"AND target_entity_id = {_sql_lit(p['new_target_id'])} "
                f"AND relationship_type = {_sql_lit(new_type)}::relationship_type;")
        # redundant wrong copies whose corrected twin exists (after the updates)
        for p in planned:
            if p["action"] != "delete_duplicate":
                continue
            new_type = p["new_type"] or p["relationship_type"]
            cur.execute(
                """SELECT row_to_json(r)::text FROM relationships r
                   WHERE relationship_id = %s AND source_entity_id = %s AND target_entity_id = %s
                         AND relationship_type = %s::relationship_type
                         AND NOT EXISTS (SELECT 1 FROM geometry_periods g WHERE g.relationship_id = r.relationship_id)
                         AND EXISTS (SELECT 1 FROM relationships t WHERE t.relationship_id = %s
                                     AND t.source_entity_id = %s AND t.target_entity_id = %s
                                     AND t.relationship_type = %s::relationship_type)
                   FOR UPDATE""",
                (p["relationship_id"], p["old_source_id"], p["old_target_id"], p["relationship_type"],
                 p["twin_id"], p["new_source_id"], p["new_target_id"], new_type))
            got = cur.fetchone()
            if not got:
                applied.append({**p, "action": "skipped_changed_concurrently"})
                continue
            cur.execute("""UPDATE chronicle_entries SET primary_relationship_id = %s
                           WHERE primary_relationship_id = %s RETURNING entry_id::text""",
                        (p["twin_id"], p["relationship_id"]))
            moved = [r[0] for r in cur.fetchall()]
            cur.execute("DELETE FROM relationships WHERE relationship_id = %s", (p["relationship_id"],))
            applied.append({**p, "action": "deleted_duplicate", "chronicle_entries": len(moved)})
            stmts = [f"INSERT INTO relationships SELECT * FROM json_populate_record(NULL::relationships, "
                     f"{_sql_lit(got[0])}::json) ON CONFLICT (relationship_id) DO NOTHING;"]
            if moved:
                ids = ", ".join(_sql_lit(m) for m in moved)
                stmts.append(f"UPDATE chronicle_entries SET primary_relationship_id = {_sql_lit(p['relationship_id'])} "
                             f"WHERE entry_id IN ({ids}) AND primary_relationship_id = {_sql_lit(p['twin_id'])};")
            rollback_del.append(stmts)
    rollback = rollback_upd + [s for stmts in rollback_del for s in stmts]
    rb = out_dir / "rollback.sql"
    rb.write_text(f"-- fix_relation_eras slice A, applied {dt.datetime.now().isoformat(timespec='seconds')}\n"
                  f"-- backup: {bk.name}\n-- re-inserts deleted duplicates, moves chronicle entries back, "
                  f"restores re-pointed endpoints (each guarded on the value written)\nBEGIN;\n"
                  + "\n".join(rollback) + "\nCOMMIT;\n", encoding="utf-8")
    write_csv(out_dir / "applied.csv", applied, FIELDS)
    n_ok = Counter(a["action"] for a in applied)
    print(f"applied: {dict(n_ok)}")

    # test the rollback: every inverse must hit exactly one row; then roll back
    bad = 0
    try:
        with conn.transaction():
            for stmt in rollback:
                cur.execute(stmt)
                bad += cur.rowcount < 1
            raise _Rollback
    except _Rollback:
        pass
    print(f"rollback test: {len(rollback) - bad}/{len(rollback)} statements hit their rows (rolled back)")

    print("next: --rebuild (timeline:rebuild for every touched entity)")


def touched_entities(out_dir: Path) -> list[str]:
    with (out_dir / "applied.csv").open(newline="", encoding="utf-8") as fh:
        applied = list(csv.DictReader(fh))
    return sorted({x for a in applied if a["action"] in ("applied", "deleted_duplicate")
                   for x in (a["old_source_id"], a["old_target_id"], a["new_source_id"], a["new_target_id"])})


class _Rollback(Exception):
    pass


def rebuild_timelines(ids: list[str]) -> None:
    """``php artisan timeline:rebuild <id>`` per entity, batched into one
    container shell per 50 ids."""
    fails: list[str] = []
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        script = " ; ".join(f"php artisan timeline:rebuild {e} >/dev/null || echo FAIL {e}" for e in chunk)
        res = subprocess.run([*COMPOSE, "exec", "-T", "app", "sh", "-c", script], capture_output=True, text=True)
        fails += [ln for ln in res.stdout.splitlines() if ln.startswith("FAIL")]
        print(f"  timelines {min(i + 50, len(ids))}/{len(ids)}", flush=True)
    print(f"timeline:rebuild for {len(ids)} entities, {len(fails)} failed")
    for ln in fails:
        print(" ", ln)


def human_note(p: dict[str, Any]) -> str:
    """A note for a skipped row from ENDPOINT_NOTES (either endpoint)."""
    if p["action"] != "skip":
        return ""
    for name in (p["old_source"], p["old_target"]):
        if name in ENDPOINT_NOTES:
            return ENDPOINT_NOTES[name]
    if p["reason"].startswith("excluded_endpoint"):
        return "endpoint is being merged or awaits a user decision; re-check after that lands"
    if p["reason"].startswith("self_link"):
        return "the era-correct row is the other endpoint itself (e.g. 'Fatimid Caliphate rules Egypt'); needs a region row or a rewrite"
    return ""


def annotate(out_dir: Path) -> None:
    """Add ``human_note`` to planned.csv without re-planning (after --apply the
    live DB no longer shows the planned state)."""
    path = out_dir / "planned.csv"
    with path.open(newline="", encoding="utf-8") as fh:
        planned = list(csv.DictReader(fh))
    for p in planned:
        p["human_note"] = human_note(p)
    write_csv(path, planned, FIELDS + ["human_note"])
    left = [p for p in planned if p["action"] == "skip"]
    print(f"annotated {sum(1 for p in left if p['human_note'])}/{len(left)} skipped rows")


# ── main ────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true", help="backup, apply, applied.csv, rollback.sql (+ tested)")
    ap.add_argument("--rebuild", action="store_true", help="timeline:rebuild every entity in applied.csv")
    ap.add_argument("--annotate", action="store_true", help="add human_note to planned.csv (no DB access)")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    if args.rebuild:
        rebuild_timelines(touched_entities(args.out))
        return 0
    if args.annotate:
        annotate(args.out)
        return 0

    conn = connect(read_only=not args.apply)
    planned, _ = plan(conn)
    write_csv(args.out / "planned.csv", planned, FIELDS)
    counts = Counter((p["action"], p.get("method") or "") for p in planned)
    reasons = Counter(p["reason"].split(";")[0].split(" for ")[0] for p in planned if p["action"] == "skip")
    print(f"flags in slice: {len(planned)}")
    for k, v in sorted(counts.items()):
        print(f"  {k[0]:7s} {k[1]:10s} {v}")
    print("skip reasons:")
    for k, v in reasons.most_common():
        print(f"  {v:4d} {k}")
    if args.apply:
        conn.commit()          # end the read transaction; each write block is its own transaction
        conn.autocommit = True
        apply(conn, planned, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
