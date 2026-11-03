"""Namesake review (2026-11-01 cleanup): rows that HAVE a QID whose identity is in doubt.

Slice (``select``):

* rows flagged ``namesake_ambiguous`` / ``low_wikidata_match`` (campaign approval
  gate) or ``identity_audit:place_namesake`` (identity audit C2b), with a QID;
* rows ``pipeline/backfill_dates.py`` skipped because the item contradicts the
  row's own dated facts (``start_after_evidence`` and the other QID-doubt
  reasons, plus its ``SPOT_CHECK_REJECTS``), listed in
  ``output/audit/dates-backfill-20261101/planned.csv``;
* Xochimilco (Q20244459), whose point lands in Hidalgo.

Rows flagged ``identity_audit:qid_suspect*`` (another agent's slice), S1 rows of
``qid-flags.csv``, the merge-review rows and the user-decision rows are left out.

Each row gets a hand-checked decision (``DECISIONS``):

* ``confirm``  - the QID is right: drop the doubt flag; restore
                 ``verification_status`` to what it was before the flag (the
                 identity audit's applied.csv for place_namesake, else
                 ``pipeline_draft``) only when no other flag still justifies
                 ``needs_review`` (``missing_geometry`` on a row that still has no
                 geometry, ``no_wikidata_match``, any other ``identity_audit:``);
* ``repoint``  - set the right QID (C3 tools, ``qid.find_correct_qid``; unique,
                 certain and not held by another row); the doubt flag goes too;
* ``clear``    - clear the QID the audit's way (old id to
                 ``attributes._rejected_wikidata_id``, ``needs_review``, flag
                 ``identity_audit:qid_cleared``);
* ``dup``      - the right QID is held by another row: listed in
                 duplicate-candidates.csv; the wrong QID is cleared the audit's way;
* ``leave``    - listed only (``noop``: a dates-backfill row whose QID is right).

A row whose QID changes or is cleared also loses ``attributes.media_refs`` (the
images came from the old QID; the nightly ``entity:fetch-images`` links the new
QID's), unless an admin curated them. A repointed row whose dates, point or
aliases came from the old QID stays (or becomes) ``needs_review`` with the flag
``identity_audit:stale_from_old_qid``; the stale values are named in
``follow_up`` (dates, points and aliases are other tables, not written here).

Stages (dry by default):

  scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit.namesake_review gather   # evidence (read-only)
  scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit.namesake_review plan     # planned.csv
  scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit.namesake_review apply    # backup + guarded writes

Every write is guarded on the value read (QID, attributes, status); a row another
agent changed is skipped. One transaction; applied.csv and rollback.sql come
from what the transaction changed.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import requests

from pipeline.audit import classes as C
from pipeline.audit.common import CACHE_DIR, COMPOSE, REPO, connect, load_relationships, load_rows, write_csv
from pipeline.audit.qid import check_row, find_correct_qid, prefetch_candidates, wd_names
from pipeline.audit.wd import WikidataClient

OUT = REPO / "output" / "audit" / "qid-namesake-20261101"
DATES_PLANNED = REPO / "output" / "audit" / "dates-backfill-20261101" / "planned.csv"
QID_FLAGS = REPO / "output" / "audit" / "identity-20261031" / "qid-flags.csv"
IDENTITY_APPLIED = REPO / "output" / "audit" / "identity-20261031" / "applied.csv"
MERGE_VERDICTS = REPO / "output" / "audit" / "merge-review-20261101" / "verdicts.csv"
USER_DECISION_PREFIXES = ("a05afb75", "6255478f", "17d96812", "7baeedc3")

DOUBT_FLAGS = ("namesake_ambiguous", "low_wikidata_match", "identity_audit:place_namesake")
OTHER_AGENT_FLAGS = ("identity_audit:qid_suspect",)  # prefix: qid_suspect, qid_suspect:duplicate
DATE_REASONS = {"start_after_evidence", "start_far_before_evidence", "start_after_row_end",
                "end_before_evidence", "end_disagrees_with_row", "lifespan_over_120", "lifespan_misses_evidence"}
EXTRA_QIDS = {"Q20244459": "Xochimilco: point lands in Hidalgo, not Mexico City"}


# ── hand-checked decisions (2026-11-01), keyed by entity_id prefix ─────────
# (decision, new QID or None, why). Evidence: the row's own summary and relations
# against the item's label/description/dates; candidates from C3
# (qid.find_correct_qid), wbsearchentities and exact enwiki titles.
DECISIONS: dict[str, tuple[str, str | None, str]] = {
    # ── identity_audit:place_namesake ──
    "6aca8129": ("repoint", "Q2306339", "Bagumbayan: execution field of Rizal (1896) = Rizal Park, formerly Bagumbayan "
                 "(enwiki disambiguation); Q173393 is a municipality in Sultan Kudarat"),
    "31a5379d": ("leave", None, "Charles Town: mixed row. Summary and Carolina relations are Charleston SC (Q47716, held "
                 "by dfcf513d Charleston); John Brown died_in 1859 and part_of Virginia are Charles Town WV (the "
                 "current QID). Split relations before any QID change"),
    "117125aa": ("repoint", "Q2213391", "Croydon: Surrey town (Surrey Iron Railway) = Croydon, South London; "
                 "Q2418825 is a Cambridgeshire village"),
    "a9ccd9cd": ("repoint", "Q3117068", "Grosse Ile: St Lawrence quarantine island = Grosse Isle (enwiki), Quebec; "
                 "Q33440203 is a Michigan settlement"),
    "81400114": ("repoint", "Q273", "Islay: Hebridean island = Q273; Q27995444 is a town in Arequipa, Peru "
                 "(row type city vs island is a type question, not identity)"),
    "b3148abb": ("repoint", "Q214109", "Kea: Greek island with Ayia Irini = Kea (island) in the Cyclades; "
                 "Q2287944 is a Cornish village"),
    "876f5823": ("repoint", "Q1026894", "Lares: town of the Grito de Lares (1868) = Lares, Puerto Rico "
                 "(municipality); Q1805903 is an archaeological site in Tunisia"),
    "eecfc354": ("repoint", "Q38888", "Olympia: Zeus sanctuary, Olympic Games 776 BCE = Olympia, Greece; "
                 "Q42735 is Olympia, Washington"),
    "67ea4266": ("clear", None, "Sopot: the Sopot-culture type site near Vinkovci, Croatia; Q1013179 is a "
                 "municipality of Belgrade. No item for the Croatian site found"),
    "5133839f": ("clear", None, "Udayagiri: mixed row (summary = Udayagiri Caves, Madhya Pradesh; relations = "
                 "Udayagiri and Khandagiri, Bhubaneswar); Q7876995 is the Buddhist complex at Jajpur, neither"),
    "fc2567a1": ("repoint", "Q56036", "West Berlin 1948-1990 = Q56036 (western sectors of Berlin); "
                 "Q7984471 is a Nova Scotia settlement"),
    "17feebed": ("repoint", "Q391620", "Whitehall: London palace complex of the Civil War era = Palace of Whitehall; "
                 "Q2089711 is Whitehall, Ohio"),
    "2acf784f": ("confirm", None, "Xaltocan: Q796347 is P31 city-state with the enwiki article 'Xaltocan' "
                 "(its Spanish description is misleading)"),
    "7a00ce58": ("repoint", "Q643026", "Xochimilco: city south of Tenochtitlan = Xochimilco, Mexico City (enwiki); "
                 "Q20244459 is a settlement in Tianguistengo, Hidalgo"),
    # ── namesake_ambiguous ──
    "6121f459": ("confirm", None, "Battle of Fontenoy 1745 = Q569953 (the 841 battle is row 8957388e, Q1430939)"),
    "336e826f": ("confirm", None, "Charles Townshend, general at Kut 1916 = Q333688 (1861-1924); the "
                 "Chancellor is row cd0a8ae5"),
    "31cc2153": ("confirm", None, "Hernando de Soto = Q60040"),
    "8b4e7782": ("confirm", None, "Liu Yan, founder of Southern Han 917 = Q717972 (889-942)"),
    "ea05c759": ("confirm", None, "Peter the apostle = Q33923 Saint Peter"),
    "8ebdfefe": ("confirm", None, "Ptolemy the geographer = Q34943"),
    "a2a1eb2c": ("confirm", None, "Saud bin Abdulaziz of Diriyah (1748-1814) = Q2227089"),
    "7a0c3940": ("dup", None, "Frederick II who granted Hven to Tycho Brahe is Frederick II of Denmark (Q154041); "
                 "Q702602 is the Elector of Saxony (1412-1464). Q154041 is on b98b2611 (the emperor, being merged "
                 "into 83358225 by merge-review); 1a0dcb48 'Frederick II of Denmark' is the same king"),
    "8c8cd04e": ("clear", None, "Hipparchus the astronomer is Q159905; Q3801668 is an Athenian politician. "
                 "Q159905 is wrongly on f207326f (the tyrant, qid_suspect, another agent's)"),
    "a61eed43": ("repoint", "Q317126", "José de Anchieta, Jesuit (1534-1597) = Q317126 (enwiki 'Joseph of "
                 "Anchieta'); Q102225630 is a 20th-century mathematician"),
    "de2a7548": ("repoint", "Q235061", "Stratonice, wife of Seleucus I then Antiochus I = Stratonice of Syria; "
                 "Q3624248 is Stratonice of Cappadocia"),
    # ── low_wikidata_match: QID right ──
    "2ac06bee": ("confirm", None, "Amazon.com = Q3884"),
    "e3f45ca3": ("confirm", None, "Golden Ambrosian Republic 1447-1450 = Q746443"),
    "aebac6f0": ("confirm", None, "Arsacid dynasty of Parthia = Q12818551"),
    "efd4ed90": ("confirm", None, "Aspasioi = Q11906929 Aspasians"),
    "4eb3fa8b": ("confirm", None, "Prince-Bishopric of Halberstadt (to 1648) = Q15880986"),
    "62f2e578": ("confirm", None, "Brahmadatta of Anga = Q109381477 (enwiki)"),
    "9a8f55bb": ("confirm", None, "People's Republic of Bulgaria 1946-1990 = Q121932"),
    "1c8ca1cf": ("confirm", None, "Chol-khan = Shevkal/Shchelkan (Q4528621), Uzbeg's envoy killed at Tver 1327"),
    "84b76247": ("confirm", None, "Cuman-Kipchak confederation = Q1122052 Cumania (900s-1241)"),
    "2efd2824": ("confirm", None, "David Igorevich = Q2034352 David I of Volhynia (1055-1112)"),
    "9dfc6a7b": ("confirm", None, "Diego de Prado y Tovar, Torres voyage = Q113324329"),
    "b794d64e": ("confirm", None, "First Empire of Haiti 1804-1806 = Q2006756"),
    "5aa8647b": ("confirm", None, "First Cataract of the Nile = Q11942741"),
    "ac5c59e0": ("confirm", None, "Frans Visscher, Tasman's pilot = Q109233000 Francoijs Visscher (Dutch cartographer)"),
    "934ff6c1": ("confirm", None, "Gnaeus Ogulnius, tribune 300 BCE = Q11924415"),
    "f48c126b": ("confirm", None, "Guacri-caur = Q2836423 Guacricur, Chimú ruler"),
    "fe2e010b": ("confirm", None, "Old Hittite Kingdom = Q12406731"),
    "8a9a766f": ("confirm", None, "Hungarian Diet = Q140467953 Hungarian Diet of Estates (enwiki)"),
    "042138c5": ("confirm", None, "Hurin dynasty of Cusco = Q136674386"),
    "6e682a32": ("confirm", None, "Ibn Iyad = Q19289370 Abu Muhammad Abd Allah ibn Iyad (d. 1147)"),
    "282e8cc7": ("confirm", None, "John I of Thessalonica (d. c. 630) = Q3175722"),
    "bac9ec35": ("confirm", None, "Domain of Soissons 457-486 = Q1247508"),
    "98c25ed2": ("confirm", None, "Aikichi Kuboyama 1914-1954 = Q3607106"),
    "3dc3105a": ("confirm", None, "Kyodo Unyu Kaisha = Q11392667"),
    "4e29cb21": ("confirm", None, "Lương Nhữ Hốt (d. 1428) = Q10788355 (vi/zh labels)"),
    "f7614c1a": ("confirm", None, "Mirza Muhammad Hakim 1553-1585 = Q6874895"),
    "1c12e561": ("confirm", None, "Emirate of Granada 1238-1492 = Q238445"),
    "e5fc1d4c": ("confirm", None, "Omaguaca = Q3098388 Humahuaca people"),
    "867a58ae": ("confirm", None, "Pacajes = Q2045310 Pacaje (Aymara lordship, La Paz)"),
    "639201fb": ("confirm", None, "Saint Patrick = Q165479"),
    "a8574765": ("confirm", None, "Peru-Bolivian Confederation 1836-1839 = Q899706"),
    "c0b31253": ("confirm", None, "Provisional Government of Cuba 1906-1909 = Q3374989 (second US occupation)"),
    "ddb3ef06": ("confirm", None, "Real Audiencia of Guadalajara = Q4233721"),
    "3cf154ab": ("confirm", None, "Samgu ibn Wasul al-Miknasi = Q111603350 (enwiki)"),
    "51dcf31a": ("confirm", None, "Second Cataract of the Nile = Q11948049"),
    "13a07a06": ("confirm", None, "Suhi II of Carchemish = Q59274391"),
    "5515904b": ("confirm", None, "Thabit ibn Nu'aym al-Judhami (745 revolt) = Q106773513"),
    "8098752d": ("confirm", None, "Third Cataract of the Nile = Q71108004"),
    "4f1c88a5": ("confirm", None, "Yang Gil = Q14481020 Yang Kil (enwiki)"),
    "6d9dd3f8": ("confirm", None, "Yuji Seki, archaeologist b. 1956 = Q11656492 (ja: 関雄二, archaeologist)"),
    "55599ff7": ("confirm", None, "Zhi Xiangzi = Q5922378 Zhi Yao (d. 453 BCE)"),
    "bc33e716": ("confirm", None, "Yahya al-Ghazal = Q5661762 (es: Andalusi traveller and diplomat)"),
    # ── low_wikidata_match: wrong QID, right one found ──
    "4dfae0f4": ("repoint", "Q3619727", "Antonio Amar y Borbón, viceroy of New Granada = Q3619727 (enwiki); "
                 "Q84089893 is a bare duplicate-like item with another death year"),
    "3ef0487a": ("repoint", "Q141094", "Bahram Shah, Ghaznavid sultan (1148) = Bahram-Shah of Ghazna; "
                 "Q16173544 is Bahram Shah ibn Toghril (d. 1175)"),
    "d746649c": ("repoint", "Q3642718", "Bambatha, Zulu leader 1906 = Bhambatha (1865-1906); "
                 "Q97946943 is Bambatha Mandela (b. 1989)"),
    "5ea65351": ("repoint", "Q1497453", "Gedaliah son of Ahikam = Q1497453; Q120963019 is Gedaliah Zlotowitz"),
    "23ee0a07": ("repoint", "Q25222096", "Gonpo, Tibetan on the 1960 Everest ascent = Gongbu (mountaineer), "
                 "born Gonpo Dorje; Q110249214 is Gonpo Tso (b. 1951)"),
    "7b13717b": ("repoint", "Q3618148", "Row (coup of c. 340 BCE, Magonid, Timoleon's time) = Hanno I the Great, "
                 "4th-century statesman; Q106281127 Hanno III the Great is 2nd-century (Third Punic War)"),
    "c4a30b55": ("repoint", "Q188794", "Isaiah the prophet = Q188794; Q112123823 is Isaiah Norton"),
    "329bcd4c": ("repoint", "Q1500", "José Rizal (Noli Me Tangere 1887) = Q1500; Q114352038 is a man born 1952"),
    "6f169875": ("repoint", "Q17040487", "Lushuihu people of northwest China = Lushuihu (enwiki); "
                 "Q14145737 is a modern subdistrict in Hubei"),
    "6bf3fb15": ("repoint", "Q2059687", "Paulus Fürst, engraver 1608-1666 = Q2059687 (matches both dates); "
                 "Q95330481 gives 1611"),
    "1282f157": ("repoint", "Q58662", "Peter Apian 1495-1552 = Q58662 Petrus Apianus; Q94944411 is 1548-1595"),
    "e3e90b00": ("repoint", "Q586557", "Sanacja regime 1926-1939 = Q586557 Sanation; Q1938241 is corporate "
                 "restructuring"),
    "9bb1352d": ("repoint", "Q157734", "Sultanate of Muscat and Oman (Said bin Sultan, Taimur, Said bin Taimur) = "
                 "Muscat and Oman 1820-1970; Q1885093 is the Mahra Sultanate"),
    "3800bab9": ("repoint", "Q23681", "TRNC 1983 = Northern Cyprus; Q118946511 is a symphony orchestra"),
    "ae2d6bdf": ("repoint", "Q4976493", "Head of the Wei clan of Jin, father of Marquis Wen = Viscount Huan of Wei "
                 "(魏桓子); Q3698792 is Ji Huanzi of Lu (季桓子)"),
    "e5534e3f": ("repoint", "Q2822168", "Hafsid sultan driven out by Barbarossa 1534 = Abu Abdallah Muhammad V "
                 "al-Hasan (r. 1526-1543); Q11904620 is a Bajali sect founder"),
    "a187765a": ("repoint", "Q1740272", "Fatimid caliph al-Zahir 1021-1036 = Q1740272 (1005-1036); Q635423 is "
                 "the Mamluk sultan al-Zahir Qansuh"),
    # ── low_wikidata_match: wrong QID, nothing certain ──
    "163a4f94": ("clear", None, "Mixed row: the explorer of Zimbabwe 1513-15 and the Jesuit sent to Rome by Susenyos "
                 "1613 (Q4777561); Q110224771 (1592-1646) is neither"),
    "f84d3b76": ("clear", None, "Ili region (Qing-Russia dispute 1871-1881); Q16204 is the Province of Mantua. "
                 "The modern Ili Kazakh Autonomous Prefecture (Q848127) is a different entity"),
    "0788d8e9": ("clear", None, "Row is the polity of Lý Nam Đế 544 (Vạn Xuân); Q10797201 is a Vietnamese book "
                 "(Việt Nam khai quốc chí truyện)"),
    "c55ff9c0": ("clear", None, "Yun clan faction of Joseon 1544; Q122464526 'Yun Clan Donates' (1907) is unrelated"),
    "19863a80": ("clear", None, "Zipani king of Kanesh c. 2250 BCE; Q130874776 is 'Zipani Sinkala', a modern "
                 "person; no item for the king"),
    "5e0d5582": ("clear", None, "Vasco Pérez de Meira, Castilian commander at Gibraltar 1333; Q4008872 is "
                 "Vasco Perez Pardal, a Portuguese troubadour; no item found"),
    "a60e4260": ("dup", None, "Na state (gold seal 57 CE) = Nakoku Q600473, held by 0859774a 'Nakoku'; "
                 "Q4712 is the Duchy of Burgundy"),
    # ── low_wikidata_match: left for a human ──
    "5022b382": ("leave", None, "Hamdanid Emirate: row 890-1004 mixes the dynasty (Mosul, from 890) and the "
                 "Aleppo emirate (Q99469759, 944-1024); which entity is meant is a human call"),
    "7037d731": ("leave", None, "Maranhão e Piauí: name matches Q3338842 (1772-1775) but the row says created 1737; "
                 "date vs identity needs a human"),
    "702f7799": ("leave", None, "Nauhyotl: two bare items (Q134985393 'of Culhuacan', Q134985369 'Náuhyotl'), "
                 "nothing to tell them apart"),
    "73be201d": ("leave", None, "NTT: row dated 1985 (NTT, Inc. Q1054787) but its 1979 cellular network belongs "
                 "to the Public Corporation (current QID, 1952-1985); mixed"),
    "19d2a24e": ("leave", None, "Oil Rivers Protectorate: enwiki redirects to Niger Coast Protectorate (Q2566427, "
                 "the current QID), which the QID-less row 5e7aef53 'Niger Coast Protectorate' also is; "
                 "which row keeps the QID is a human call"),
    "bce02a00": ("leave", None, "Sierra Leone Protectorate (1896): Q30059027 is the Colony and Protectorate "
                 "(1808-1961), a broader entity; no item for the protectorate alone"),
    "d46bf8a6": ("clear", None, "Amukan, Mongol commander in Goryeo 1247; Q110119746 has no label and one "
                 "sitelink, mswiki 'Amukan Pocong' (not him); no item found"),
    "5f140a84": ("confirm", None, "Uddyotana Suri = Q118958451 'Uddyotana', the P50 author of Kuvalaya-mālā "
                 "(Q116873502, 779 CE, Jalore)"),
    "0e3d1d0d": ("repoint", "Q4125958", "Victor of Molodi 1572, d. 1573 = Mikhail Ivanovich Vorotynsky (ruwiki "
                 "'Воротынский, Михаил Иванович', b. 1510s, d. 1573); Q4297200 is Mikhail Fyodorovich, a "
                 "15th-century Vorotynsky prince"),
    # ── dates-backfill: start after the row's own facts ──
    "4fb0c93a": ("repoint", "Q209746", "2 Kings = Second Book of Kings; Q19801714 is a 2015 album"),
    "5e31e4aa": ("repoint", "Q178390", "Book of Ezekiel = Q178390; Q765342 is an album"),
    "0f670ffd": ("repoint", "Q243170", "Bunraku puppet theatre = Q243170; Q2702930 is a 2010 film"),
    "3681e140": ("repoint", "Q861986", "Lucretius' De rerum natura = Q861986; Q140306863 is a 2019 album"),
    "8e3cd634": ("repoint", "Q172891", "Euclid's Elements = Q172891; Q87280593 is an In Our Time episode"),
    "8afb18c8": ("repoint", "Q2600166", "Kalidasa's Malavikagnimitram = Q2600166; Q58455564 is a 1929 film"),
    "01d18eec": ("repoint", "Q3062269", "Olmec colossal heads = Q3062269 (enwiki); Q106466843 is an article"),
    "9fc35787": ("repoint", "Q762982", "Ptolemaic admiral Patroclus (Chremonidean War) = Patroclus (admiral); "
                 "Q324018 is a 3rd-century CE martyr"),
    "40a3abeb": ("repoint", "Q2420991", "Ptolemy's Planisphere, translated by Hermann of Carinthia 1143 = "
                 "Planisphaerium; Q7201306 is a 2009 book by John Ashbery"),
    "6c61b1a2": ("repoint", "Q1141990", "Taoist canon (the 1244 printing under Töregene) = Daozang, the Taoist "
                 "canon; Q85705758 is the Ming Zhengtong edition of 1445"),
    "e6093017": ("repoint", "Q965124", "Frans Hals' painting 1624 = Q965124; Q12125632 is a 1917 film"),
    "e0f68e25": ("repoint", "Q215685", "Pali Canon written down c. 29 BCE = Q215685; Q47316744 is an article"),
    "83cdb492": ("repoint", "Q2222", "Stowe's 1852 novel = Q2222; Q3549217 is a 1914 film"),
    "f52ed96e": ("repoint", "Q283127", "Shang oracle bones = Q283127; Q140237140 is an audiobook"),
    "f1ff188f": ("repoint", "Q813031", "Kojiki chronicle = Q813031; Q6426481 is a 1990 album"),
    "44a3ab10": ("repoint", "Q29480", "Founder of the Hafsid dynasty, ruled Ifriqiya 1228-1249 = Abu Zakariya Yahya; "
                 "Q67373648 is an Iraqi scholar (1136-1219)"),
    "e803eaf5": ("repoint", "Q11106578", "Eight Trigrams leader 1813 = Q11106578 Lin Qing, Qing rebel (1770-1813); "
                 "Q16925313 is a politician born 1434"),
    "f4a24ff1": ("repoint", "Q698828", "133-day siege ending 22 March 1915 = Q698828 (1914-15, enwiki 'Siege of "
                 "Przemyśl'); Q1240870 is the 1915 recapture"),
    "5de32c11": ("dup", None, "Boccaccio's Decameron = Q16438, held by 90b24c4a 'Decameron'; Q720159 is the 1971 film"),
    "8507741d": ("dup", None, "Cyprian's treatise on the plague = De mortalitate (Q3704133), held by 0b29c190 "
                 "'De mortalitate'; Q55953632 is a 1901 article"),
    "087d65e4": ("clear", None, "al-Bitruji's astronomical treatise (Michael Scot, 1217); Q2717459 is Archimedes' "
                 "On the Sphere and Cylinder; no item for al-Bitruji's work found"),
    "11bbbb37": ("clear", None, "Kalimullah, last Bahmani sultan; Q12688817 is a Malaysian journalist (b. 1958); "
                 "no item found"),
    "60312b0f": ("leave", None, "Langya: Q373346 Linyi is the modern prefecture-level city (P571 1994) over "
                 "the Han-era Langya area; no certain item for the ancient city (Langya Commandery Q15910280 is a "
                 "commandery)"),
    # ── dates-backfill: QID right, the clash is in the dates or Wikidata ──
    "3437a85a": ("noop", None, "Brigantes Q500393 right; Wikidata's end (60) predates Cerialis 71"),
    "9ea4141b": ("noop", None, "Groswater culture right; only the end year disagrees"),
    "9c2ca0aa": ("noop", None, "Painted Grey Ware culture right; only the end year disagrees"),
    "15d56770": ("noop", None, "Woodstock NY (4'33\" premiere 1952) right; P571 1829 is not the founding"),
    "141e35d1": ("noop", None, "Antikythera mechanism right"),
    "98a4ac58": ("noop", None, "Cisalpine Gaul right (province start 203 BCE vs a 225 BCE battle)"),
    "314f0967": ("noop", None, "Deioces right"),
    "c67b5c49": ("noop", None, "Globular Amphora culture right"),
    "3700ad98": ("noop", None, "History of Yuan right (facts are events it records)"),
    "6e7e0a01": ("noop", None, "Cassiodorus' Institutiones right"),
    "3d304fec": ("noop", None, "Journey to the West right (facts are Xuanzang's journey)"),
    "b3c5975b": ("noop", None, "Kanva dynasty right"),
    "a2e668fd": ("noop", None, "Mycenaean Greece right"),
    "9068fbe4": ("noop", None, "Narva right"),
    "74b4ae9a": ("noop", None, "Rajatarangini right"),
    "5cd26098": ("noop", None, "Records of the Three Kingdoms right"),
    "2b93778f": ("noop", None, "Siyasatnama right"),
    "95f5a7ce": ("noop", None, "Zij-i Sultani right"),
    "5b15b45c": ("noop", None, "cannon right"),
    "48d24d63": ("noop", None, "hand cannon right"),
    "4c4bd398": ("noop", None, "Íslendingabók (book) right; C3's Q14917714 is the genealogy database"),
}

# Repointed rows whose dates, point or aliases came from the old QID (checked by hand)
STALE = {"eecfc354", "fc2567a1", "81400114", "117125aa", "3ef0487a", "d746649c", "329bcd4c", "23ee0a07",
         "ae2d6bdf", "9bb1352d"}
FOLLOW_UPS: dict[str, str] = {
    "eecfc354": "start 1859 and point (Olympia, WA) came from Q42735",
    "fc2567a1": "point (Nova Scotia) came from Q7984471",
    "81400114": "point (Arequipa, Peru) came from Q27995444",
    "117125aa": "point (Cambridgeshire) came from Q2418825",
    "3ef0487a": "end 1175 came from Q16173544 (Bahram-Shah died 1152)",
    "d746649c": "start 1989 came from Q97946943 (Bhambatha 1865-1906)",
    "329bcd4c": "start 1952 came from Q114352038 (Rizal 1861-1896); alias 'Filipino physician Jose Rizal'",
    "23ee0a07": "start 1951 came from Q110249214 (Gongbu 1933-2024)",
    "ae2d6bdf": "start -550 came from Q3698792 (Ji Huanzi)",
    "9bb1352d": "alias 'Sultanate of Qishn and Socotra' and point (Mahra, Yemen) came from Q1885093",
    "7a00ce58": "stale entity_geo_refs row (provider wikidata, external_id Q20244459, fallback, no period)",
    "7b13717b": "row name 'Hanno III' is a misnomer for Hanno I the Great",
    "f84d3b76": "alias 'Provincia di Mantova' and point (Mantua) came from Q16204",
    "a60e4260": "alias 'Ducatus Burgundiae' and point (Burgundy) came from Q4712",
    "7a0c3940": "dates 1412-1464 and point (Leipzig) came from Q702602; Denmark's king was 1534-1588",
    "c55ff9c0": "start 1907 came from Q122464526",
    "8e3cd634": "34bf602c 'Elements' (Euclid's treatise) carries Q1993156, an album",
    "a61eed43": "6b8fc292 'José de Anchieta' (same Jesuit) carries Q10310740, a politician, with dates 1965-2018",
    "de2a7548": "7fb2ece6 'Stratonice' (same queen) carries Q270585, the wife of Antigonus, dates -400..-360",
    "b3148abb": "356eec79 'Keos' (QID-less) is the same island",
    "31cc2153": "a9969f6c 'Hernando de Soto' (same conquistador) carries Q357946, start 1941",
    "8ebdfefe": "3777e2dc 'Ptolemy' (same geographer) carries Q1227416, dates -400..-309",
    "a2a1eb2c": "cc882c23 'Saud bin Abdulaziz' (same emir) carries Q3473086, dates 1897-1920",
}
# (row, other row, QID, category, evidence). qid_held / same_entity get a merge command.
DUPS: list[tuple[str, str, str, str, str]] = [
    ("7a0c3940", "1a0dcb48", "Q154041", "same_entity",
     "Both are Frederick II of Denmark (Tycho Brahe, Hven 1576). 7a0c3940 had Q702602 (Elector of Saxony), cleared; "
     "1a0dcb48 has none (rejected Q154041 at import). Q154041 sits on b98b2611 (the emperor) until merge-review "
     "merges it into 83358225; then set Q154041 on the survivor"),
    ("5de32c11", "90b24c4a", "Q16438", "qid_held", "'The Decameron' (Q720159 film, cleared) is Boccaccio's work, "
     "which 'Decameron' carries"),
    ("8507741d", "0b29c190", "Q3704133", "qid_held", "'On the Plague' by Cyprian (Q55953632 article, cleared) is "
     "De mortalitate"),
    ("a60e4260", "0859774a", "Q600473", "qid_held", "'Na state' (Q4712 Duchy of Burgundy, cleared) is Nakoku; check "
     "the junk alias 'Ducatus Burgundiae' and the Burgundy point before merging"),
    ("8e3cd634", "34bf602c", "Q172891", "same_entity", "Both are Euclid's Elements; 8e3cd634 now carries Q172891, "
     "34bf602c carries Q1993156 (an Atheist album) which must be cleared"),
    ("a61eed43", "6b8fc292", "Q317126", "same_entity", "Both are the Jesuit José de Anchieta; a61eed43 now carries "
     "Q317126, 6b8fc292 carries Q10310740 (a politician, 1965-2018 dates) which must be cleared"),
    ("de2a7548", "7fb2ece6", "Q235061", "same_entity", "Both are Stratonice of Syria (Seleucus I, then Antiochus I); "
     "de2a7548 now carries Q235061, 7fb2ece6 carries Q270585 (wife of Antigonus) with its dates"),
    ("b3148abb", "356eec79", "Q214109", "same_entity", "Kea = Keos (Ayia Irini; Patroclus' base 267 BCE); Keos is "
     "QID-less, start 1839"),
    ("31cc2153", "a9969f6c", "Q60040", "same_entity", "Both are Hernando de Soto; a9969f6c carries Q357946 and "
     "start 1941"),
    ("8ebdfefe", "3777e2dc", "Q34943", "same_entity", "Both are Ptolemy the geographer (90-168 CE); 3777e2dc carries "
     "Q1227416 and dates -400..-309"),
    ("a2a1eb2c", "cc882c23", "Q2227089", "same_entity", "Both are Saud bin Abdulaziz of Diriyah (Mecca 1803); "
     "cc882c23 carries Q3473086 and dates 1897-1920"),
    ("8c8cd04e", "f207326f", "Q159905", "qid_held_wrongly", "Q159905 (Hipparchus the astronomer) is on f207326f, "
     "the Athenian tyrant (qid_suspect, another agent's slice); not a merge. Once f207326f releases it, set it on "
     "8c8cd04e"),
    ("31a5379d", "dfcf513d", "Q47716", "mixed_row", "Charles Town mixes Charleston SC (summary, Carolina 1670) "
     "and Charles Town WV (John Brown 1859, Virginia; current QID). Split before merging the SC part"),
    ("19d2a24e", "5e7aef53", "Q2566427", "shared_item", "Oil Rivers Protectorate (1884-1893) and Niger Coast "
     "Protectorate (1893-1900) are one Wikidata item; the QID sits on the Oil Rivers row"),
]


class PoliteClient(WikidataClient):
    """The audit client plus maxlag=5 (shared quota), backing off on a maxlag error."""

    def _get(self, url, params, timeout=60):
        if "wikidata.org/w/api.php" in url:
            params = {**params, "maxlag": "5"}
        for attempt in range(6):
            resp = super()._get(url, params, timeout)
            if "api.php" in url:
                try:
                    err = (resp.json() or {}).get("error") or {}
                except ValueError:
                    err = {}
                if err.get("code") == "maxlag":
                    time.sleep(min(5 * 2 ** attempt, 120))
                    continue
            return resp
        raise RuntimeError("Wikidata kept reporting maxlag")


def client(offline: bool = False) -> PoliteClient:
    return PoliteClient(CACHE_DIR, max_rps=1.0, workers=1, offline=offline)


# ── selection ───────────────────────────────────────────────────────────────
def excluded_ids() -> set[str]:
    ids: set[str] = set()
    with MERGE_VERDICTS.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            ids.update(x for x in (r.get("survivor_id"), r.get("loser_id")) if x)
    return ids


def s1_ids() -> set[str]:
    with QID_FLAGS.open(encoding="utf-8") as fh:
        return {r["entity_id"] for r in csv.DictReader(fh) if r["rule"].startswith("S1")}


def date_rows() -> dict[str, dict[str, str]]:
    from pipeline.backfill_dates import SPOT_CHECK_REJECTS
    out = {}
    with DATES_PLANNED.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["reason"] in DATE_REASONS or (r["reason"].startswith("spot_check:")
                                               and r["qid"] in SPOT_CHECK_REJECTS):
                out[r["entity_id"]] = r
    return out


def select(rows) -> tuple[list[tuple[Any, str]], list[tuple[str, str, str]]]:
    """[(row, why in slice)], [(entity_id, name, skip reason)]."""
    excl = excluded_ids()
    s1 = s1_ids()
    dates = date_rows()
    picked, skipped = [], []
    for r in rows.values():
        flags = (r.attributes or {}).get("validation_flags") or []
        why = [f for f in flags if f in DOUBT_FLAGS]
        if r.id in dates:
            why.append(f"dates:{dates[r.id]['reason']}")
        if r.qid in EXTRA_QIDS:
            why.append("xochimilco_point")
        if not why:
            continue
        if not r.qid:
            skipped.append((r.id, r.name, "no QID (other agent)"))
        elif any(f.startswith(OTHER_AGENT_FLAGS) for f in flags):
            skipped.append((r.id, r.name, "identity_audit:qid_suspect (other agent)"))
        elif r.id in excl:
            skipped.append((r.id, r.name, "merge-review exclusion"))
        elif r.id.startswith(USER_DECISION_PREFIXES):
            skipped.append((r.id, r.name, "user-decision exclusion"))
        elif r.id in s1:
            skipped.append((r.id, r.name, "S1 row"))
        else:
            picked.append((r, ";".join(why)))
    picked.sort(key=lambda p: (p[1], p[0].name))
    return picked, skipped


# ── gather (read-only) ──────────────────────────────────────────────────────
def gather(out: Path, offline: bool) -> None:
    conn = connect()
    rows = load_rows(conn)
    rels = load_relationships(conn)
    picked, skipped = select(rows)
    cl = client(offline)
    closure_fn = lambda cs: cl.class_roots(cs, C.ALL_ROOTS)  # noqa: E731
    cl.get_entities([r.qid for r, _ in picked])
    closure = closure_fn([c for r, _ in picked for c in (cl.resolved(r.qid)[1] or {}).get("p31", [])])
    by_qid: dict[str, list[str]] = {}
    for r in rows.values():
        if r.qid:
            by_qid.setdefault(r.qid, []).append(r.id)
    by_row: dict[str, list[str]] = {}
    for rel in rels:
        for a, b, arrow in ((rel["source"], rel["target"], "->"), (rel["target"], rel["source"], "<-")):
            o = rows.get(b)
            if o:
                yrs = "-".join(str(y) for y in (rel["start"], rel["end"]) if y is not None)
                by_row.setdefault(a, []).append(f"{arrow}{rel['type']} {o.name} [{o.type}{' ' + o.qid if o.qid else ''}]"
                                                f"{' ' + yrs if yrs else ''}")
    c2 = {r.id: check_row(r, cl, closure) for r, _ in picked}
    want = [(r, {r.qid}) for r, _ in picked]
    if not offline:
        prefetch_candidates(want, cl, closure_fn)
    evidence = []
    for r, why in picked:
        res = c2[r.id]
        _, rec = cl.resolved(r.qid)
        rec = rec or {}
        found = find_correct_qid(r, cl, closure_fn, exclude={r.qid}) if not offline else {}
        winner = found.get("qid", "")
        evidence.append({
            "entity_id": r.id, "name": r.name, "type": r.type, "qid": r.qid, "status": r.status, "why": why,
            "flags": (r.attributes or {}).get("validation_flags") or [], "start": r.start, "end": r.end,
            "aliases": r.aliases[:5], "summary": r.summary, "description": r.description[:400],
            "wd_label": rec.get("label", ""), "wd_desc": rec.get("description", ""), "wd_dates": rec.get("dates"),
            "wd_coord": rec.get("coord"), "wd_enwiki": rec.get("enwiki"),
            "c2": f"{res['verdict']} {res['rule']} {res.get('issues', '')}".strip(),
            "c3": found.get("outcome", ""), "c3_qid": winner,
            "c3_held_by": [h for h in by_qid.get(winner, []) if h != r.id] if winner else [],
            "c3_cands": found.get("candidates", []), "point": r.point, "has_geo": r.has_geo,
            "rels": by_row.get(r.id, [])[:25], "n_rels": len(by_row.get(r.id, [])), "chron": r.chron,
            "stories": r.stories, "qid_holders": [h for h in by_qid.get(r.qid, []) if h != r.id],
        })
    out.mkdir(parents=True, exist_ok=True)
    (out / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=1, default=str))
    (out / "skipped.json").write_text(json.dumps(skipped, ensure_ascii=False, indent=1))
    print(f"gather: {len(picked)} rows in slice, {len(skipped)} skipped; requests made {cl.requests_made}")


# ── plan ────────────────────────────────────────────────────────────────────
PLAN_FIELDS = ["entity_id", "name", "entity_type", "slice", "decision", "change", "old_qid", "old_label",
               "old_description", "new_qid", "new_label", "new_description", "old_status", "new_status",
               "old_flags", "new_flags", "rejected_qid", "c2_new", "reason", "follow_up", "old_attributes",
               "new_attributes"]
DUP_FIELDS = ["group", "category", "confidence", "entity_type", "qid", "wd_label", "wd_description",
              "survivor_id", "survivor_name", "survivor_type", "survivor_qid", "survivor_rels", "survivor_span",
              "loser_id", "loser_name", "loser_type", "loser_qid", "loser_rels", "loser_span", "evidence", "moves",
              "lost_on_delete", "merge_command"]
STALE_FLAG = "identity_audit:stale_from_old_qid"
# flags that still justify needs_review after the doubt flag is gone
KEEP_FLAGS = ("no_wikidata_match", "identity_audit:")
CURATED_KEY = "_media_curated_at"  # FetchEntityImagesAction::CURATED_KEY: admin-picked images, never touched


def _km(point: tuple[float, float], coord: list[float]) -> float:
    """Distance between a (lon, lat) point and a Wikidata [lat, lon] coordinate."""
    import math
    lon1, lat1, (lat2, lon2) = point[0], point[1], coord
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 6371 * 2 * math.asin(math.sqrt(a))


def _wd(cl, qid: str | None) -> dict[str, Any]:
    if not qid:
        return {}
    _, rec = cl.resolved(qid)
    return rec if rec and rec.get("status") == "ok" else {}


def _resolve_keys(picked) -> dict[str, Any]:
    by_prefix: dict[str, Any] = {}
    for r, why in picked:
        by_prefix.setdefault(r.id[:8], []).append((r, why))
    out = {}
    for key in DECISIONS:
        hits = by_prefix.get(key, [])
        if len(hits) != 1:
            raise SystemExit(f"decision key {key} matches {len(hits)} rows in the slice")
        out[key] = hits[0]
    return out


def _restore_status(r) -> str:
    """The status the row had before its doubt flag was set: the identity audit
    recorded it for place_namesake; the campaign gate and the importer set
    needs_review together with their flag, over the default pipeline_draft."""
    with IDENTITY_APPLIED.open(encoding="utf-8") as fh:
        for x in csv.DictReader(fh):
            if x["id"] == r.id and x["column"] == "verification_status" and x["new"] == "needs_review":
                return x["old"]
    return "pipeline_draft"


def plan(out: Path) -> None:
    conn = connect()
    rows = load_rows(conn)
    picked, skipped = select(rows)
    keyed = _resolve_keys(picked)
    undecided = [(r, why) for r, why in picked if r.id[:8] not in DECISIONS]
    cl = client(offline=True)
    closure_fn = lambda cs: cl.class_roots(cs, C.ALL_ROOTS)  # noqa: E731
    new_qids = [d[1] for d in DECISIONS.values() if d[1]]
    cl.get_entities([r.qid for r, _ in picked] + new_qids)
    closure = closure_fn([c for q in new_qids for c in _wd(cl, q).get("p31", [])])
    held: dict[str, list[str]] = {}
    for r in rows.values():
        if r.qid:
            held.setdefault(r.qid, []).append(r.id)
    lines = []
    for key, (r, why) in sorted(keyed.items(), key=lambda kv: (kv[1][1], kv[1][0].name)):
        decision, new_qid, reason = DECISIONS[key]
        attrs = dict(r.attributes or {})
        flags = list(attrs.get("validation_flags") or [])
        old = _wd(cl, r.qid)
        line = {"entity_id": r.id, "name": r.name, "entity_type": r.type, "slice": why, "decision": decision,
                "old_qid": r.qid, "old_label": old.get("label", ""), "old_description": old.get("description", ""),
                "old_status": r.status, "old_flags": flags, "reason": reason, "follow_up": FOLLOW_UPS.get(key, ""),
                "new_qid": r.qid, "new_status": r.status, "new_flags": flags, "change": "no"}
        if decision in ("leave", "noop"):
            lines.append(line)
            continue
        new_flags = [f for f in flags if f not in DOUBT_FLAGS]
        qid_after = r.qid
        if decision == "repoint":
            others = [h for h in held.get(new_qid, []) if h != r.id]
            if others:
                raise SystemExit(f"{r.name}: {new_qid} is held by {others}; make it a dup")
            if attrs.get("_rejected_wikidata_id") == new_qid:
                raise SystemExit(f"{r.name}: {new_qid} was rejected for this row")
            qid_after = new_qid
            rec = _wd(cl, new_qid)
            if not rec:
                raise SystemExit(f"{r.name}: {new_qid} is not a live item")
            line.update(new_label=rec.get("label", ""), new_description=rec.get("description", ""))
            import dataclasses
            c2 = check_row(dataclasses.replace(r, qid=new_qid), cl, closure)
            line["c2_new"] = f"{c2['verdict']} {c2['rule']}".strip() + (f" {c2['issues']}" if c2.get("issues") else "")
            stale = c2.get("date_check") in ("conflict", "out_of_tolerance", "sign") or key in STALE
            if c2.get("date_check") in ("conflict", "out_of_tolerance", "sign"):
                line["follow_up"] = "; ".join(x for x in (line["follow_up"], f"row dates {r.start}..{r.end} vs "
                                                          f"{new_qid} {c2.get('wd_start')}..{c2.get('wd_end')}") if x)
            if stale and STALE_FLAG not in new_flags:
                new_flags.append(STALE_FLAG)
        elif decision in ("clear", "dup"):
            qid_after = None
            attrs["_rejected_wikidata_id"] = r.qid
            line["rejected_qid"] = r.qid
            flag = "identity_audit:qid_cleared" + (":duplicate" if decision == "dup" else "")
            if flag not in new_flags:
                new_flags.append(flag)
        elif decision != "confirm":
            raise SystemExit(f"unknown decision {decision!r} for {r.name}")
        if decision in ("repoint", "clear", "dup") and old:
            from pipeline.agent.tools.disambiguation import names_equal
            keep_names = [r.name, *(wd_names(_wd(cl, new_qid)) if decision == "repoint" else [])]
            junk = [a for a in r.aliases if any(names_equal(a, w) for w in wd_names(old))
                    and not any(names_equal(a, k) for k in keep_names)]
            notes = [f"aliases from {r.qid}: {junk}"] if junk else []
            new_coord = _wd(cl, new_qid).get("coord") if decision == "repoint" else None
            if r.point and old.get("coord") and _km(r.point, old["coord"]) < 2 and not (
                    new_coord and _km(r.point, new_coord) < 50):
                notes.append(f"primary point = {r.qid}'s P625 ({old['coord'][0]:.3f}, {old['coord'][1]:.3f})")
            if notes:
                line["follow_up"] = "; ".join(x for x in (line["follow_up"], *notes) if x)
                if decision == "repoint" and STALE_FLAG not in new_flags:
                    new_flags.append(STALE_FLAG)
        if decision in ("repoint", "clear", "dup") and "media_refs" in attrs and CURATED_KEY not in attrs:
            # the images came from the old QID (entity:fetch-images is QID-based); without the key the
            # nightly fetch links the new QID's images, and a cleared row shows none
            n = len(attrs.pop("media_refs") or [])
            line["follow_up"] = "; ".join(x for x in (line["follow_up"], f"dropped {n} media_refs of {r.qid}") if x)
        keep = any(f.startswith(KEEP_FLAGS) for f in new_flags) or (
            "missing_geometry" in new_flags and not r.has_geo)
        if decision in ("clear", "dup") or STALE_FLAG in new_flags:
            status_after = "needs_review"
        elif keep or r.status != "needs_review":
            status_after = r.status
        else:
            status_after = _restore_status(r)
        if new_flags or "validation_flags" in attrs:
            attrs["validation_flags"] = new_flags
        if new_flags == flags and qid_after == r.qid and status_after == r.status and attrs == (r.attributes or {}):
            lines.append(line)  # nothing to write (a confirmed row without a doubt flag)
            continue
        line.update(new_qid=qid_after, new_status=status_after, new_flags=new_flags, change="yes",
                    old_attributes=json.dumps(r.attributes or {}, ensure_ascii=False, sort_keys=True),
                    new_attributes=json.dumps(attrs, ensure_ascii=False, sort_keys=True))
        lines.append(line)
    for r, why in undecided:
        lines.append({"entity_id": r.id, "name": r.name, "entity_type": r.type, "slice": why, "decision": "leave",
                      "old_qid": r.qid, "new_qid": r.qid, "old_status": r.status, "new_status": r.status,
                      "change": "no", "reason": "undecided"})
    for eid, name, why in skipped:
        lines.append({"entity_id": eid, "name": name, "decision": "skip", "change": "no", "reason": why,
                      "old_qid": rows[eid].qid, "new_qid": rows[eid].qid, "entity_type": rows[eid].type})
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "planned.csv", lines, PLAN_FIELDS)
    dups = duplicate_lines(rows, cl)
    write_csv(out / "duplicate-candidates.csv", dups, DUP_FIELDS)
    from collections import Counter
    print("plan:", dict(Counter((l["decision"], l["change"]) for l in lines)), f"dup lines {len(dups)}")


def duplicate_lines(rows, cl) -> list[dict[str, Any]]:
    from pipeline.audit.dups import merge_command, survivor_key

    full = {r.id[:8]: r for r in rows.values()}
    after = {k: (d[1] if d[0] == "repoint" else None if d[0] in ("clear", "dup") else full[k].qid)
             for k, d in DECISIONS.items()}
    out = []
    for a, b, qid, category, note in DUPS:
        ra, rb = full[a], full[b]
        rec = _wd(cl, qid)
        merge = category in ("qid_held", "same_entity")
        if category == "qid_held":
            surv, loser = rb, ra          # the holder of the right QID survives
        elif category == "same_entity" and after.get(a) == qid:
            surv, loser = ra, rb          # this run's row now carries the right QID
        elif merge:
            surv, loser = sorted([ra, rb], key=survivor_key, reverse=True)
        else:
            surv, loser = rb, ra
        out.append({"group": f"N-{a}", "category": category,
                    "confidence": "high" if merge and ra.type == rb.type else "medium",
                    "entity_type": ra.type, "qid": qid, "wd_label": rec.get("label", ""),
                    "wd_description": rec.get("description", ""),
                    "survivor_id": surv.id, "survivor_name": surv.name, "survivor_type": surv.type,
                    "survivor_qid": after.get(surv.id[:8], surv.qid), "survivor_rels": surv.rels,
                    "survivor_span": surv.span, "loser_id": loser.id, "loser_name": loser.name,
                    "loser_type": loser.type, "loser_qid": after.get(loser.id[:8], loser.qid),
                    "loser_rels": loser.rels, "loser_span": loser.span,
                    "evidence": note, "moves": f"{loser.rels} relationship ends; {loser.chron} chronicle links",
                    "lost_on_delete": ("MAP STORY " + ",".join(loser.stories)) if loser.stories else "",
                    "merge_command": merge_command(surv.id, loser.id) if merge else ""})
    return out


# ── apply ───────────────────────────────────────────────────────────────────
APPLIED_FIELDS = ["ts", "decision", "entity_id", "name", "old_qid", "new_qid", "old_status", "new_status",
                  "old_flags", "new_flags", "rejected_qid", "status"]


def _lit(v: Any) -> str:
    return "NULL" if v is None else "'" + str(v).replace("'", "''") + "'"


def backup(out: Path) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = out / f"backup-entities-{stamp}.sql.gz"
    cmd = [*COMPOSE, "exec", "-T", "db", "pg_dump", "-U", "history-mapped", "-d", "history-mapped",
           "--no-owner", "-t", "public.entities"]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0 or not proc.stdout:
        raise SystemExit(f"pg_dump failed: {proc.stderr.decode()[:500]}")
    with gzip.open(path, "wb") as fh:
        fh.write(proc.stdout)
    return path


def apply(out: Path) -> None:
    with (out / "planned.csv").open(encoding="utf-8") as fh:
        todo = [x for x in csv.DictReader(fh) if x["change"] == "yes"]
    if not todo:
        raise SystemExit("nothing to apply")
    path = backup(out)
    print(f"backup: {path}")
    conn = connect(read_only=False)
    cur = conn.cursor()
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    log, rollback = [], []
    try:
        for x in todo:
            eid = x["entity_id"]
            old_q, new_q = x["old_qid"] or None, x["new_qid"] or None
            old_attrs, new_attrs = json.loads(x["old_attributes"]), json.loads(x["new_attributes"])
            entry = {"ts": ts, "decision": x["decision"], "entity_id": eid, "name": x["name"], "old_qid": old_q,
                     "new_qid": new_q, "old_status": x["old_status"], "new_status": x["new_status"],
                     "old_flags": x["old_flags"], "new_flags": x["new_flags"], "rejected_qid": x["rejected_qid"]}
            cur.execute("SELECT wikidata_id, verification_status::text, attributes, updated_at FROM entities "
                        "WHERE entity_id = %s FOR UPDATE", (eid,))
            got = cur.fetchone()
            if not got:
                log.append({**entry, "status": "skipped: row gone"})
                continue
            qid, status, attrs, updated = got
            if (qid, status, attrs or {}) != (old_q, x["old_status"], old_attrs):
                log.append({**entry, "status": f"skipped: row changed (qid {qid}, status {status})"})
                continue
            if new_q and new_q != old_q:
                cur.execute("SELECT entity_id::text FROM entities WHERE wikidata_id = %s AND entity_id <> %s LIMIT 1",
                            (new_q, eid))
                holder = cur.fetchone()
                if holder:
                    log.append({**entry, "status": f"skipped: {new_q} is on row {holder[0]}"})
                    continue
            cur.execute("""
                UPDATE entities SET wikidata_id = %s, verification_status = %s::verification_status,
                       attributes = %s::jsonb, updated_at = now()
                WHERE entity_id = %s AND wikidata_id IS NOT DISTINCT FROM %s
                  AND verification_status = %s::verification_status AND attributes = %s::jsonb""",
                        (new_q, x["new_status"], json.dumps(new_attrs, ensure_ascii=False), eid, old_q,
                         x["old_status"], json.dumps(old_attrs, ensure_ascii=False)))
            if cur.rowcount != 1:
                log.append({**entry, "status": f"skipped: guard matched {cur.rowcount} rows"})
                continue
            log.append({**entry, "status": "applied"})
            rollback.append(
                f"UPDATE entities SET wikidata_id = {_lit(old_q)}, verification_status = {_lit(x['old_status'])}, "
                f"attributes = {_lit(x['old_attributes'])}::jsonb, updated_at = {_lit(updated)} "
                f"WHERE entity_id = {_lit(eid)} AND wikidata_id IS NOT DISTINCT FROM {_lit(new_q)} "
                f"AND verification_status = {_lit(x['new_status'])} AND attributes = {_lit(x['new_attributes'])}::jsonb;")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    write_csv(out / "applied.csv", log, APPLIED_FIELDS)
    header = ("-- Rollback of pipeline.audit.namesake_review (generated).\n"
              "-- Run: docker compose -f docker/docker-compose.yml exec -T db psql -U history-mapped "
              "-d history-mapped -f - < output/audit/qid-namesake-20261101/rollback.sql\n"
              "-- Each statement fires only while the row still holds what this run wrote.\n"
              "\\set ON_ERROR_STOP on\n")
    (out / "rollback.sql").write_text(header + f"-- batch {ts}: {len(rollback)} changes\nBEGIN;\n"
                                      + "\n".join(reversed(rollback)) + "\nCOMMIT;\n")
    from collections import Counter
    print("apply:", dict(Counter(l["status"].split(":")[0] for l in log)))


def test_rollback(out: Path) -> None:
    """Run rollback.sql's statements in a transaction that is rolled back; each must hit one row."""
    body = (out / "rollback.sql").read_text()
    stmts = [s for s in body.splitlines() if s.startswith("UPDATE entities")]
    conn = connect(read_only=False)
    cur = conn.cursor()
    hits = []
    try:
        for s in stmts:
            cur.execute(s)
            hits.append(cur.rowcount)
    finally:
        conn.rollback()
    bad = [i for i, n in enumerate(hits) if n != 1]
    print(f"rollback test: {len(stmts)} statements, {len(stmts) - len(bad)} hit one row, {len(bad)} did not "
          "(transaction rolled back)")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="pipeline.audit.namesake_review")
    ap.add_argument("stage", choices=("gather", "plan", "apply", "test-rollback"))
    ap.add_argument("--evidence", type=Path, default=OUT, help="where gather writes evidence.json")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args(argv)
    if a.stage == "gather":
        gather(a.evidence, a.offline)
    elif a.stage == "plan":
        plan(a.out)
    elif a.stage == "apply":
        apply(a.out)
    else:
        test_rollback(a.out)


if __name__ == "__main__":
    main()
