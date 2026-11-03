"""Fix C7 endpoint_type relationship flags, ids 8-f half (cleanup 2026-11-01).

Slice: ``output/audit/identity-20261031/relation-flags.csv`` rows with
check=endpoint_type, severity=high and relationship_id starting 8-f.

Each row gets one action, from a mechanical rule (M1-M9 below) or from the
hand-judged DECISIONS table (which wins). An action is a ';'-separated list:

  src=<uuid> / tgt=<uuid>   re-point that endpoint (original orientation) to
                            the right existing row (wrong namesake)
  swap                      exchange source and target
  type=<relationship_type>  retype
  delete <reason>           remove the link (last resort; backed up)
  leave <reason>            no change; listed for a human

Re-points apply first, then swap, then type. A planned fix whose result still
fails ``endpoint_problem`` is refused. A fix that would duplicate an existing
link (same type and endpoints, or the symmetric/inverse equivalent, same
start year) becomes a delete of the duplicate.

    scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit.fix_relation_types_b          # plan
    scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit.fix_relation_types_b --apply  # backup + apply

Writes output/audit/relfix-type-b-20261101/{planned.csv, applied.csv,
pre-apply.dump, rollback.sql, touched-entities.txt}. Local DB only.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from pipeline.audit.common import COMPOSE, REPO, connect
from pipeline.audit.relations import (ACTORS, AGREEMENTS, EVENTS, TERRITORY, endpoint_problem, era_problem)

SRC_CSV = REPO / "output" / "audit" / "identity-20261031" / "relation-flags.csv"
VERDICTS = REPO / "output" / "audit" / "merge-review-20261101" / "verdicts.csv"
OUT = REPO / "output" / "audit" / "relfix-type-b-20261101"
EXCLUDED_PREFIXES = ("a05afb75", "6255478f", "17d96812", "7baeedc3")

SYMMETRIC = {"at_war_with", "allied_with", "married_to", "sibling_of", "trades_with"}
INVERSE = {"rules": "governed_by", "governed_by": "rules", "commanded": "commanded_by",
           "commanded_by": "commanded", "parent_of": "child_of", "child_of": "parent_of",
           "mentor_of": "student_of", "student_of": "mentor_of", "vassal_of": "suzerain_of",
           "suzerain_of": "vassal_of", "caused": "resulted_from", "resulted_from": "caused"}

AUTHOR_VERB = re.compile(r"\b(wrote|written|writes|authored|co-authored|composed|painted|published|"
                         r"co-published|issued|drafted|proposed|sent|compiled|delivered|printed)\b", re.I)
TEXT_TYPES = {"cultural_work", "religious_text", "legal_code", "event_legal_reform", "event_treaty"}

# Re-point targets (existing canonical rows).
MALIK_SHAH_I = "b36ee0a7-e11c-42d7-ac88-29d8b83a1275"
ANCIENT_EGYPT = "4aabfa9f-99b6-4363-9e5b-099a43b4002b"
RUSSIAN_EMPIRE = "bee08f41-6dbc-46fa-8bb7-6cdc4aceabb8"
NAZI_GERMANY = "520c212c-87f6-4d40-bc64-08590be1b446"
HABSBURG_MONARCHY = "8c57d738-cbba-4ec4-b72b-d8ecd92a8fee"
AUSTRIAN_EMPIRE = "b3436059-3f8b-4e9f-b145-7aac47defb0c"
KINGDOM_OF_FRANCE = "b78831f7-5989-4ece-8a72-af25a72bb795"
SECOND_FRENCH_EMPIRE = "7a5f13d3-5e65-430f-abd8-1b0b01431730"
GALDAN_BOSHUGTU = "5b568c33-5fe6-41db-89cd-40fe26e97851"
CHARLES_I_ENGLAND = "7257c5dd-ca89-4728-b6c3-48cfb4318e38"
SURO = "a4689d35-aea2-4af4-8125-823957c1a3f3"
WU_ZHOU = "95c3539a-cdbb-41a4-839d-f99037f2c75c"
WU_ZETIAN = "2909351f-eb37-41fe-a12d-90569673195f"

# Hand-judged decisions, keyed by relationship_id prefix (8 hex chars).
DECISIONS_TEXT = f"""
# --- participated_in -> person
aac67d55 type=allied_with
89ee90cf type=at_war_with
988fc243 type=at_war_with
eed7d4a7 type=at_war_with
b5ce2897 type=mentor_of
95effe01 swap;type=commanded_by
f74fe8c0 leave untypable
918d25ed leave untypable
e2c4a9c8 type=allied_with
c644bf75 leave untypable
d0a41698 swap;type=patron_of
b6203424 leave unsure
f0217d1b type=at_war_with
e2b0f73f type=at_war_with
8702c59f type=allied_with
e4e2cf54 type=patron_of
a88f246d leave namesake: target is the Ghaznavid Mas'ud I; the Seljuk sultan Mas'ud has no row
ad4bc035 type=commanded_by
9884bbc7 leave untypable
e5bb3018 type=student_of
eecd3dfb swap;type=fought_at
9e5aea0d leave untypable
d54fac55 leave untypable
df346d6d swap;type=rules
ddc3aacb leave untypable
e02cad66 leave untypable
e8f6870c type=allied_with
9706391e tgt={MALIK_SHAH_I};type=sibling_of
a172c242 tgt={MALIK_SHAH_I};swap;type=patron_of
ae019af9 leave untypable
e088c636 type=commanded_by
aa489c6f swap;type=fought_at
af542692 type=destroyed_by
f566cc38 type=at_war_with
c767298a leave unsure
b00d9761 type=at_war_with
edbedb4b leave s1: 'Nepherites I Supplies Agesilaus II' typed event_war
d6620de9 swap;type=rules
e5a70534 delete attestation
cd281bfc type=commanded_by
e0de877a leave untypable
c205970c delete namesake-nofix: Athenaeus row is the 2nd-c. CE writer, not Antigonus' officer
c95a8595 type=allied_with
b945bb96 type=allied_with
8c828a2a type=at_war_with
bf87534a type=commanded_by
a7b9229b type=commanded_by
93a0d1c2 type=commanded_by
951d82cb leave untypable
be1a3018 type=assassinated_by
b045389b type=commanded_by
ce8bb0fb type=at_war_with
8c6e1bcd type=commanded_by
8e261c71 leave s1: 'Septimius Severus born' typed event_war
ea2c3949 type=married_to
93e78676 type=commanded_by
98c47ec3 delete bogus: Cologne was named for Agrippina; no relation type fits
db736c83 swap;type=fought_at
cab38066 type=married_to
973557a5 swap
eea922d4 leave untypable
e5408657 leave untypable
ab96dfbb leave untypable
9573d96d leave untypable
eb51c9d8 type=at_war_with
a24d6bbc type=commanded_by
ab51e651 leave untypable
daef58fb delete namesake-nofix: 'Tibet' row is the 1912-1959 state, and no type fits a peace
f40249a0 leave untypable
eca2386b type=sibling_of
ef16854d swap;type=vassal_of
b5a913a3 type=allied_with
cad7ccba leave untypable
8ad54e0b type=allied_with
a6f46adb leave untypable
9ac06796 type=allied_with
9453fc06 leave untypable
f34c9776 leave untypable
cbdcebc3 leave untypable
9b914193 leave untypable
95795ddc leave unsure
9121af21 type=allied_with
82b1e628 type=commanded_by
9a7c8577 leave untypable
8088e0ef leave untypable
c6ab9dc3 delete bogus
b19ae53a type=allied_with
992a9528 swap
cb6f595d leave untypable
f32a3150 type=married_to
9ad363dc type=sibling_of
baadba9d type=allied_with
e82ac173 type=commanded_by
f042fddb leave untypable
9195b24a leave untypable
fba3d0fe type=sibling_of
9cd32021 leave untypable
f81c2584 type=commanded_by
f30a136f swap;type=fought_at
9c5e94e9 leave untypable
a5f8a979 delete namesake-nofix: 'Cyril' row is Cyril of Alexandria; missionary request has no type
cf148ddf type=commanded_by
9a14061d leave untypable
c9df5668 leave untypable
863bbd9a type=allied_with
d5c761ca leave untypable
e4da54f1 leave untypable
ec4f953e leave untypable
a0f96fbd leave untypable
87aaa72a leave s1: 'Death of Frederick I Barbarossa' typed event_war
99d04e32 leave untypable
a95922b6 delete bogus
aceff9b7 leave untypable
d790bbb2 delete redundant: target is Pope Alexander III (wrong namesake); 'Treaty of Perth signed_by Magnus VI' already exists
f3104011 tgt={CHARLES_I_ENGLAND};swap
b54a1d51 type=commanded_by
e95be6a3 leave untypable
c9d9750b leave untypable
82949505 leave untypable
be691aef leave untypable
86457b78 leave untypable
e7e314c8 leave untypable
f37da824 leave untypable
bcf09c65 type=at_war_with
9fae0e2f leave untypable
f49c9f2a leave untypable
82a9f6a0 swap
b6316647 swap
c33538c1 swap;type=persecuted_by
ae63d570 type=married_to
d1f87342 type=allied_with
e64a69e0 leave untypable
a22cd509 leave untypable
9bc86249 type=parent_of
# --- defeated_at -> person (default M9: at_war_with)
e3f57db3 swap;type=fought_at
9890fad0 swap;type=fought_at
c77e9da8 delete bogus: al-Mustakfi was installed by Tuzun; description garbled
f40f3f2f swap;type=fought_at
e9a59243 type=destroyed_by
93e9afdf src={ANCIENT_EGYPT};type=at_war_with
8dd1150e leave untypable
a219caaf leave untypable
ab83f38c delete bogus: Murong Tuyuhun was already dead
b3e32743 type=persecuted_by
d5e6be97 delete bogus
ee07cc8d swap;type=assassinated_by
a29824ff delete bogus
c946a429 type=assassinated_by
bb3cf312 delete namesake-nofix: target is Ahmad ibn Hanbal (d. 855), not the Kara-Khanid ruler of 1134
cbb1266f delete namesake-nofix: source is Henry II (b. 1271); Emperor Henry II has no row
91e31743 src={GALDAN_BOSHUGTU};type=at_war_with
ee43d8e7 type=destroyed_by
b248ce14 type=destroyed_by
ddc8b899 delete bogus
872ceedb leave untypable
97df4d30 type=sibling_of
f2f6f9f8 leave untypable
fb0ef3c0 leave untypable
b56ce593 type=vassal_of
8fbf2da2 type=assassinated_by
baea899b swap;type=assassinated_by
cf666a7b leave untypable
99a572b4 leave untypable
93912bfa swap
e7d9d75a type=assassinated_by
a7893943 leave untypable
# --- defeated_at, other
c56989b9 leave s1: Red Eyebrows (rebel group) typed event_rebellion
ef2c5a3f leave s1: Baekje restoration movement typed event_rebellion
8a8f4202 swap;type=participated_in
a75df4d6 tgt={RUSSIAN_EMPIRE};swap;type=victorious_at
aecfd5f8 leave s1: Arianism typed intellectual_movement
94f6c7e5 delete bogus
92b88b03 leave untypable
e68ac136 delete bogus: Otto IV was a Welf, not Hohenstaufen
87dd43e1 delete namesake-nofix: target is the Egyptian Free Officers (1949-52), not Libya's of 1969
9c72608d leave untypable
d166384e leave untypable
d7a11d2a leave untypable
c6b67c99 src={NAZI_GERMANY};type=at_war_with
960b4e00 type=at_war_with
c5e9536e leave s1: Abbasid Revolution typed religious_movement
a69d2ea6 leave untypable
# --- participated_in -> city
87ec2647 leave untypable
8e7ac57e leave untypable
86cb2711 delete bogus
a01e46ab type=fought_at
ed511a66 type=founded
a9a34fda type=fought_at
f2a87e25 leave untypable
a02e52e6 leave untypable
fb558af6 leave untypable
cb29c7e7 type=fought_at
ec8e6c29 leave untypable
c9d0c882 leave untypable
d591ba79 leave untypable
a65a14fc leave untypable
a202bffe leave untypable
eff18e35 leave namesake: Dahlak taken 702 by the Umayyads, not the Rashidun
cb2b5656 type=fought_at
a99fc4a4 leave untypable
de8bbd6b type=fought_at
b930010b leave untypable
e9539c6d leave untypable
c976ecd0 type=founded
b19601db leave untypable
e68a1555 delete attestation
8a3788c0 leave untypable
ce0ce958 leave untypable
9d94a926 leave untypable
a4cbe5ba type=rules
f0a78c07 leave untypable
fb9d88e3 type=fought_at
d432e1c0 type=fought_at
d3a63ace leave untypable
d340d001 type=fought_at
c00e683d leave untypable
9c73c7dc leave untypable
f9dca1b5 delete bogus
82584cbb leave untypable
a4d83316 type=fought_at
fc90220c type=fought_at
e7de2b9a leave untypable
94a59e8c type=fought_at
e7f5362f type=fought_at
ee418630 type=fought_at
e321de5b type=fought_at
ee8c5705 leave untypable
9c9c6566 type=fought_at
b22b4913 leave untypable
f7f9cd7b type=fought_at
b0ae5eaf type=fought_at
d4ab2780 leave untypable
d5d90d5e leave untypable
e4b5dbec type=fought_at
af9e38d0 type=fought_at
b8855f03 leave untypable
d29c7f66 delete bogus
c880cbd5 leave untypable
d4a53725 leave untypable
a6b94891 leave untypable
93085744 type=fought_at
e4d09d19 leave untypable
e4cd4443 leave untypable
d93f5b94 leave untypable
c55cbe48 leave untypable
a917c01a leave untypable
86a2e770 leave untypable
cb2a459f leave untypable
d128fa80 delete bogus
8d685c8f delete bogus
8a5b8b3e leave untypable
93d1375a type=fought_at
f9397c6f type=fought_at
92790808 type=fought_at
c4f05b4f type=fought_at
a6a6105a type=resided_in
8d205de6 type=fought_at
f4e16150 type=founded
f15ee10c type=fought_at
a5d2dae8 leave unsure: Thomas Peters row dated 1969-
f545cdf5 leave untypable
dbf40b09 delete bogus: Konigsberg named after Ottokar; no type fits
a0e0e305 type=fought_at
c328a32c type=fought_at
b8c7842a type=fought_at
aed6b0ca type=fought_at
# --- commanded_by (default M2: person -> event swapped)
b622e3f3 delete namesake-nofix: target is Cannae 216 BCE; Cannae 1018 has no row
ca1f1cbd type=participated_in
b16b75d0 src={GALDAN_BOSHUGTU};swap
d54262cd leave namesake: source is the Lakhmid al-Mundhir III, not the Ghassanid al-Mundhir of 580
ed6139b0 type=participated_in
aed72c6c type=participated_in
8809b147 type=participated_in
fe2b8597 type=participated_in
b6be7593 swap;type=participated_in
bd9909a6 swap;type=victorious_at
e769bfd8 swap;type=participated_in
cb9a4037 leave untypable
d8a6a31b tgt={KINGDOM_OF_FRANCE};swap;type=participated_in
858bcd3e swap
bd1b8d99 swap;type=participated_in
ffb53d0a swap;type=participated_in
a463c17a swap;type=participated_in
c45b0c77 swap;type=participated_in
af62cd6a swap;type=participated_in
cb2c8d3d swap;type=participated_in
8f13e534 swap;type=participated_in
85607488 swap;type=participated_in
d335a962 swap;type=founded
ceb835e4 type=built_by
81cf3640 swap;type=fought_at
c2bdbd2c type=governed_by
e795ac5e type=governed_by
8cd18e2b leave s1: Spanish treasure fleet typed trade_route
973bfe67 leave s1: the ship Nonsuch typed infrastructure_monument
8a4e6adb leave untypable
f10b95c4 type=governed_by
c5e6540b swap;type=authored
b6982a4c swap;type=participated_in
# --- signed_by (default M1: swap)
f823ef4a leave untypable
d7591320 leave untypable
f019b2a0 type=resulted_from
c44592fd leave untypable
b1a3afcc leave untypable
c9841433 delete redundant: Molotov-Ribbentrop Pact signed_by Nazi Germany and Soviet Union already exist
835d2af6 leave untypable: suggest 'Burney Treaty signed_by East India Company'
987f365d leave untypable
937c66a2 src={HABSBURG_MONARCHY};swap
d3188ba8 src={KINGDOM_OF_FRANCE};swap
db38a291 src={KINGDOM_OF_FRANCE};swap
b3a8e011 src={SECOND_FRENCH_EMPIRE};swap
c49a3f88 src={RUSSIAN_EMPIRE};swap
9a9bf06c src={AUSTRIAN_EMPIRE};swap
# --- authored (default M7: work -> person swapped when the description names authorship)
b50ee557 delete attestation
d57efb83 delete attestation
8c5138c5 delete attestation
f205fe9b delete attestation
b78e5d82 delete attestation
d4924c47 delete attestation
db45978c delete attestation
91b144cb delete attestation
ab708140 swap
eed3cdc8 delete attestation
d2dbcb3f delete attestation
ac009d57 delete attestation
c838e0c1 delete attestation
baf52af3 delete attestation
e461cb2e delete attestation
bee5264c delete attestation
c9aa47f5 delete attestation
e2fb2614 delete attestation
d23c21ff delete attestation
b7b3e4be delete attestation
e6063f03 swap
83d750a5 swap
bce72653 leave s1: Alphabet of Lugano typed language
add297cb delete attestation
c3cb11fb leave s1: Mahavihara (monastery) typed infrastructure_monument
8e45820e delete attestation
d04e2b6f delete attestation
b4c29fd4 delete attestation
96ccd53b delete attestation
f22dee9d delete attestation
e9f89b36 delete attestation
e270121b delete attestation
bc28d6ae delete attestation
8b16dbb0 delete attestation
b9e77c72 leave untypable
9be70fe7 delete attestation
91064818 delete attestation
dd6ac006 delete attestation
cbecc3e3 delete attestation
ac25a59e type=inspired
ea4924e8 delete attestation
da09f575 delete attestation
c9d0c551 swap
90254200 swap
9adfba54 delete bogus
adc3c849 leave namesake: description is the 1917 declaration, the row is the 1926 one
ad906ff9 delete attestation
94a7ea23 delete attestation
a7f999d0 swap
95414c3b swap;type=resulted_from
a71db353 leave unsure: Muteferrika printed, did not write, the Vankulu Lugati
b8e503dc leave untypable
d3ad5cab leave untypable
8db2e676 leave untypable
dc3eb4ef delete attestation
b428b250 delete attestation
b5a66df9 leave s1: The Beatles typed intellectual_movement
d7501cf6 swap
b9374b62 swap
b5848a63 swap
9c49072d swap
# --- located_at (default M4: place -> event swapped)
d84cd95f delete attestation
b6408a88 leave untypable
a21b051e swap;type=stationed_at
92479a6b delete attestation
ccd81a25 delete attestation
8794d08c leave untypable
d1f28e24 type=strengthened
a557dab3 leave untypable
a560eed0 delete attestation
de9c53da delete attestation
ad0c3c52 delete bogus
e2d184c3 leave untypable
85cda921 leave unsure
84539900 leave untypable
fde7a295 swap;type=died_in
ae95e9ab swap
82c63935 type=commanded_by
bbc1e996 delete bogus: Terra Australis is legendary
c83d1740 leave unsure
ec0c1797 type=commanded_by
a30d5f80 leave untypable
910e01e7 leave untypable
fb923610 leave s1: 'Tertullian composes Apologeticum' typed event_legal_reform
ff145f2c swap;type=fought_at
87491905 delete attestation
b6cbe85d swap;type=fought_at
cc6e04ab delete attestation
f234f754 swap;type=resided_in
c991dc3b delete bogus
f34bbb0a leave untypable
ec17f7d3 type=authored
d674b02b leave untypable
ef54fc54 leave untypable
d53ff209 leave untypable
b1eefe43 leave untypable
c0a232a0 type=founded
915262dd delete bogus: Adad-guppi is Nabonidus' mother, not the god Adad
a49db3a0 delete bogus: Shala is a goddess (statue seized); no type fits
d553e466 leave untypable
a485f923 swap;type=participated_in
9843cbce delete bogus: description is Song Jiaoren 1913, not the May Fourth Movement
d101f99c swap;type=resided_in
e9825c9e delete bogus: Shahu became Chhatrapati at Satara, not Kolhapur
a43ce68f delete bogus: Aurangzeb died at Ahmednagar, was buried at Khuldabad
c7441b1c leave untypable
dc219d26 leave untypable
f401f1a7 swap;type=died_in
eb652a7b leave namesake: Isabella row is the 1503-1539 empress, not the Duchess of Burgundy
dac7784a leave s1: Witwatersrand typed natural_resource
915631a9 delete namesake-nofix: 'Abdulaziz' row is a modern person; the Ottoman sultan has no row
bf40c073 delete namesake-nofix: Xinyou Coup is 1861; Tan Sitong died in the 1898 coup
bc5dc631 leave untypable
befe3fa3 delete attestation
f6a169c4 delete attestation
c29964b3 swap
a8be44cb delete attestation
8e5ccefe leave untypable
9c6f307c leave untypable
c0519020 delete bogus
fd9e7803 leave untypable
d4c4db6d leave untypable
d00cfa59 leave untypable
8002a4e4 type=participated_in
cb9e503e type=participated_in
aeb7b6bf swap
a752e97e swap;type=weakened
8ccbc62b delete attestation
ba203af0 leave unsure: raiders only came within sight of Chang'an
# --- fought_at
a9e93691 type=allied_with
bb160649 delete bogus: Kidin-Hutran fought against the Kassites
b1c0c600 type=at_war_with
bb4398f0 type=at_war_with
a994a2f6 type=at_war_with
ea7efd16 swap
cd06181f type=at_war_with
9173d2d6 type=commanded_by
95d882e4 swap
88d9cd3e swap
89bf9966 leave untypable
f836eec1 type=at_war_with
e045098e type=at_war_with
e89e9c02 leave untypable
b3f17eb0 type=at_war_with
c089d54c leave untypable
8a5aa6e5 type=commanded_by
8fa760a8 delete namesake-nofix: 'Drogo' row is a 9th-c. person; Drogo of Hauteville has no row
95b83630 type=at_war_with
c7855c29 type=married_to
c6b985d7 leave untypable
d0c0293f type=at_war_with
ea902a76 type=at_war_with
cbc2ed9d leave untypable
a1d46227 type=at_war_with
e777aad4 leave untypable
ebf3aead swap;type=participated_in
cfe77cef swap;type=participated_in
ac7274e6 type=participated_in
a0ddc129 swap;type=victorious_at
91368685 type=at_war_with
9c612471 type=at_war_with
ccb0731a leave untypable
c06edc9d leave untypable
bb5b94c0 leave untypable
9797c66a type=at_war_with
f6e5dcf3 type=participated_in
a9a28b54 leave untypable
# --- assassinated_by
a523c9c9 swap;type=died_in
f1afe3cb swap;type=died_in
bdacc180 swap;type=participated_in
ed688aef swap
895ba41f type=died_in
b55c77c6 type=died_in
8b37e8b0 type=died_in
# --- born_in
af3265de type=located_at
# --- capital_of
da63d121 swap
ee58ae61 type=rules
a95ff64d type=resided_in
f15d3aad type=rules
9f72bcc5 type=rules
cda915ab type=resided_in
e3dda0a3 delete bogus
c2cf16a2 type=rules
e7914a99 swap;type=located_at
879c69a4 swap
98cca2bd swap;type=located_at
9d13bfcd swap;type=resided_in
cc5d24e9 swap;type=rules
# --- child_of
d85c52ce type=born_in
867b401f delete bogus
d1c83d22 leave untypable
93e4eb73 type=member_of_dynasty
d667bc34 type=member_of_dynasty
cfd08c68 type=rules
87fbd0e7 leave untypable
a18565a1 leave untypable: suggest member_of_dynasty a Plantagenet row (none exists)
# --- commanded
ab9648fd swap
a51c86d9 type=adopted
9c981de0 type=governed_by
cc0d17a5 type=commissioned
ffa23f57 leave s1: airship Graf Zeppelin typed cultural_work
944db2c1 leave s1: Achaean League typed diplomatic_relationship
d52e7914 type=founded
ff5e95ea swap;type=commanded_by
9bbf7e23 swap;type=commanded_by
8e63d54f swap;type=commanded_by
84f2f905 type=participated_in
# --- died_in / enforced_by / governed_by / guaranteed_by / married_to / mediated_by
995f5f34 swap
f1dffb8f leave s1: White Ship typed cultural_work
a356df18 leave untypable
dd48e625 type=authored
9fb5e06f swap
a48d37d6 type=commanded_by
e8f083e6 leave untypable
d97b1a36 leave untypable
96e41db7 leave untypable
8fd5c3b1 type=participated_in
82a4cb58 type=rules
bc1b09cd leave untypable
e03b30b4 leave untypable
a3bf9b79 leave untypable
8badfd5b leave namesake: Khuzistan row is the Sasanian province (224-642)
fcc4e64e leave untypable
9882025a type=rules
c9081540 type=rules
bad9caf8 type=commanded_by
d94e5ea1 type=commanded_by
f2278a32 leave untypable
9a137be2 leave untypable
df31ed2f leave untypable
90d16beb type=rules
84cec257 leave untypable
a7df9822 type=rules
aa45ee26 leave untypable
abf25c86 leave untypable
8bec7c88 type=rules
ff59b695 type=rules
914588f9 type=rules
8e27620b leave untypable
b73d95b9 leave untypable
d4f71753 leave untypable
b66d68b1 leave untypable
ff635cf3 type=allied_with
912432b0 type=allied_with
cfcd049b tgt={SURO}
ac02f6ba swap;type=signed_by
de7e8440 leave untypable
e3792e0e leave untypable
facc0172 leave untypable
# --- member_of_dynasty (default M3: dynasty -> person swapped)
8de67a1e src={WU_ZHOU};tgt={WU_ZETIAN};swap;type=rules
e751d148 swap;type=founded
c51f26ed swap;type=founded
964b946f type=adheres_to
e95383dd leave untypable
9a968292 type=strengthened
f455cafa delete attestation
bf21962e delete attestation
bd5b774b leave untypable
f96cfdbe type=child_of
f21f07cd type=child_of
ad0cbb9f type=married_to
ef8d1e4f leave untypable
e9a9f95f leave untypable
f781b6ea leave untypable
ff4322f1 type=sibling_of
8039967a leave untypable
a3cf38e9 type=child_of
a9dea97d type=child_of
8524d1de type=child_of
b064b404 type=child_of
bc3088d7 type=commanded_by
9e0b9b19 type=commanded_by
a9a2e2a1 type=child_of
ee7d7e68 leave untypable
8c4ea907 type=child_of
a6bbdbb9 leave untypable
c08cf63a type=married_to
c180e423 type=founded
c18886f7 type=adheres_to
cc0fb4fa leave untypable
c6d1cde7 type=adheres_to
8fb6d106 leave untypable
# --- participated_in, other
e082224d delete attestation
8460d52d delete attestation
f04ebdb0 delete attestation
89fb3da2 delete bogus
c0eb9373 type=authored
c641140d leave s1: JPL typed educational_institution, Explorer 1 launch typed event_battle
f00bc61a delete bogus: 'Mali' row is the 1960 state; link is vague
9ebdcf25 leave untypable
cc8afc42 leave untypable
b689e232 leave untypable
cc5d67fa leave untypable
8e21588b leave untypable
f64d316d leave s1: Isthmian Games typed cultural_work
f721c1fc delete attestation
843fd0dc delete attestation
a0357dd4 delete attestation
f3d7e15f leave s1: Nobel Peace Prize typed cultural_work
b24a730b leave s1: Nobel Peace Prize typed cultural_work
908b4eca leave untypable
ccfe862c leave s1: Fete de la Federation typed cultural_work
bddecc80 leave s1: Fete de la Federation typed cultural_work
f4b4d7df leave s1: ballet performance typed cultural_work
e8c30c03 leave s1: ballet performance typed cultural_work
d2e2b580 swap;type=patron_of
c123eb77 leave untypable
c5ae10bd type=rules
fefd71d7 delete bogus
89d5cab0 leave untypable: membership of an academy has no type
c024f821 leave untypable: membership of an academy has no type
99b08607 leave untypable: membership of an academy has no type
bb6bf140 leave untypable: membership of an academy has no type
d6942606 leave untypable: membership of an academy has no type
b828cfa2 leave untypable: membership of an academy has no type
8f3b7f57 leave untypable: membership of an academy has no type
bcf46bff leave untypable
bb65f533 type=fought_at
d0ba1c20 type=fought_at
88dee2f0 type=fought_at
99720216 delete attestation
bf5e4d44 leave s1: 'Death of Juba II' typed infrastructure_monument
dc9526e0 leave untypable
b5c526ca leave untypable
f56ca68c type=fought_at
9f9ecea1 type=fought_at
d2d78e24 leave s1: Council of Pisa typed infrastructure_monument
f14a645d type=fought_at
b0733e6d delete bogus
ad73ac54 leave untypable
d5a2cb65 leave untypable
9ba0b2e2 delete attestation
adcad73a leave s1: spaceflight typed technology
c2e0b63f leave s1: spaceflight typed technology
aaedd722 leave s1: spaceflight typed technology
f2cacdd2 leave untypable
# --- rules (default M6: polity -> person swapped)
db9c912c leave s1: Iberian Union typed diplomatic_relationship
c8bdfe56 leave s1: NAWSA typed diplomatic_relationship
d56607ce leave s1: WSPU typed diplomatic_relationship
87852f00 type=participated_in
a2c8b0ab leave untypable
e0f260c7 leave untypable
f2b83de7 type=child_of
ab09d277 leave untypable
cbc0cabf leave untypable
8d7a17da leave untypable
ff181f79 src={AUSTRIAN_EMPIRE};swap
# --- victorious_at (default M5 swap / M9 at_war_with)
d8d25913 tgt={KINGDOM_OF_FRANCE};swap
a1022f13 tgt={RUSSIAN_EMPIRE};swap
b0910670 tgt={RUSSIAN_EMPIRE};swap
938a9859 tgt={RUSSIAN_EMPIRE};swap
e7224cb5 swap;type=part_of
a4c29e4b swap;type=part_of
f468ce0e swap;type=participated_in
fc878226 leave s1: Committee of Union and Progress typed intellectual_movement
e6e7802f leave s1: Committee of Union and Progress typed intellectual_movement
dfe57307 leave s1: City Dionysia typed cultural_work
d49fcef3 type=at_war_with
c423c11c type=at_war_with
8f62a171 type=at_war_with
e5e478fe delete bogus: Ishbi-Erra died ~1985 BCE, over a century earlier
b61c6865 leave untypable
830e5d75 leave untypable
968cfe86 leave s1: Abbasid Revolution typed religious_movement
994203de leave untypable
"""


def parse_decisions(text: str) -> dict[str, str]:
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, action = line.split(None, 1)
        if key in out:
            raise SystemExit(f"duplicate decision for {key}")
        out[key] = action
    return out


DECISIONS = parse_decisions(DECISIONS_TEXT)


def mechanical(rtype: str, s: dict, t: dict, desc: str) -> tuple[str, str] | None:
    """(rule, action) for the classes that need no judgement."""
    st, tt = s["type"], t["type"]
    if rtype in {"signed_by", "violated_by", "guaranteed_by", "mediated_by", "enforced_by"} \
            and st in ACTORS and tt in AGREEMENTS | EVENTS:
        return "M1 agreement stored backwards", "swap"
    if rtype == "commanded_by" and st == "person" and tt in EVENTS - {"event_legal_reform"}:
        return "M2 commanded_by stored backwards", "swap"
    if rtype == "member_of_dynasty" and st == "dynasty" and tt == "person":
        return "M3 member_of_dynasty stored backwards", "swap"
    if rtype == "located_at" and st in TERRITORY and tt in EVENTS:
        return "M4 place located_at event stored backwards", "swap"
    if rtype in {"defeated_at", "victorious_at"} and st in EVENTS and tt in ACTORS:
        return "M5 battle outcome stored backwards", "swap"
    if rtype == "rules" and st in {"political_entity", "city"} and tt == "person":
        return "M6 rules stored backwards", "swap"
    if rtype == "authored" and st in TEXT_TYPES and tt == "person" and AUTHOR_VERB.search(desc):
        return "M7 authored stored backwards", "swap"
    if rtype == "minted_by" and tt == "currency_monetary_system":
        return "M8 minted_by stored backwards", "swap"
    if rtype in {"defeated_at", "victorious_at"} and tt == "person" and st in ACTORS:
        return "M9 actor vs person outcome -> at_war_with", "type=at_war_with"
    return None


def load_slice() -> list[dict]:
    rows = [r for r in csv.DictReader(SRC_CSV.open(encoding="utf-8"))
            if r["check"] == "endpoint_type" and r["severity"] == "high"
            and r["relationship_id"][:1] in "89abcdef"]
    return rows


def excluded_ids() -> set[str]:
    ids = set()
    for v in csv.DictReader(VERDICTS.open(encoding="utf-8")):
        ids.update(x for x in (v["survivor_id"], v["loser_id"]) if x)
    return ids


def is_excluded(eid: str, excl: set[str]) -> bool:
    return eid in excl or eid.startswith(EXCLUDED_PREFIXES)


def fetch(conn, rel_ids: list[str], extra_entities: set[str]):
    cur = conn.cursor()
    cur.execute("""SELECT relationship_id::text, relationship_type::text, source_entity_id::text,
                          target_entity_id::text, start_year, end_year, coalesce(description,'')
                   FROM relationships WHERE relationship_id = ANY(%s::uuid[])""", (rel_ids,))
    rels = {r[0]: dict(zip(("id", "type", "src", "tgt", "start", "end", "desc"), r)) for r in cur.fetchall()}
    eids = {x for r in rels.values() for x in (r["src"], r["tgt"])} | extra_entities
    cur.execute("""SELECT e.entity_id::text, e.name, e.entity_type::text, e.wikidata_id, t.start_year, t.end_year
                   FROM entities e LEFT JOIN entity_temporal_ranges t ON t.entity_id = e.entity_id AND t.is_primary
                   WHERE e.entity_id = ANY(%s::uuid[])""", (list(eids),))
    ents = {r[0]: dict(zip(("id", "name", "type", "qid", "start", "end"), r)) for r in cur.fetchall()}
    return rels, ents


def era_gap(rtype: str, a: dict, b: dict) -> str:
    """Report-only: the C7 endpoint_era result for the fixed link ('gap/tolerance')."""
    ns = lambda e: SimpleNamespace(type=e["type"], start=e["start"], end=e["end"])  # noqa: E731
    hit = era_problem(rtype, ns(a), ns(b))
    return f"{hit[0]}/{hit[1]}" if hit else ""


def existing_equivalent(cur, rtype: str, src: str, tgt: str, start, self_id: str) -> str | None:
    cands = [(rtype, src, tgt)]
    if rtype in SYMMETRIC:
        cands.append((rtype, tgt, src))
    if rtype in INVERSE:
        cands.append((INVERSE[rtype], tgt, src))
    for t, s, g in cands:
        cur.execute("""SELECT relationship_id::text FROM relationships
                       WHERE relationship_type = %s::relationship_type AND source_entity_id = %s AND target_entity_id = %s
                         AND relationship_id <> %s AND (start_year IS NOT DISTINCT FROM %s)
                       ORDER BY relationship_id LIMIT 1""", (t, s, g, self_id, start))
        hit = cur.fetchone()
        if hit:
            return hit[0]
    return None


def plan(conn) -> list[dict]:
    flags = load_slice()
    excl = excluded_ids()
    ids = [f["relationship_id"] for f in flags]
    prefixes = Counter(i[:8] for i in ids)
    clash = [p for p, n in prefixes.items() if n > 1]
    if clash:
        raise SystemExit(f"ambiguous id prefixes: {clash}")
    unknown = set(DECISIONS) - set(prefixes)
    if unknown:
        raise SystemExit(f"decisions for ids outside the slice: {sorted(unknown)}")
    extra = {v for a in DECISIONS.values() for v in re.findall(r"(?:src|tgt)=([0-9a-f-]{36})", a)}
    rels, ents = fetch(conn, ids, extra)
    cur = conn.cursor()
    out, seen, missing = [], {}, []
    for f in flags:
        rid = f["relationship_id"]
        row = {"relationship_id": rid, "flag_detail": f["detail"]}
        rel = rels.get(rid)
        if not rel:
            out.append({**row, "status": "skip", "reason": "relationship gone"})
            continue
        s, t = ents[rel["src"]], ents[rel["tgt"]]
        row.update(old_type=rel["type"], old_source_id=s["id"], old_source=f"{s['name']} [{s['type']}]",
                   old_target_id=t["id"], old_target=f"{t['name']} [{t['type']}]",
                   start_year=rel["start"], description=rel["desc"])
        if (rel["type"], s["id"], t["id"]) != (f["relationship_type"], f["source_id"], f["target_id"]):
            out.append({**row, "status": "skip", "reason": "changed since audit"})
            continue
        if not endpoint_problem(rel["type"], s["type"], t["type"]):
            out.append({**row, "status": "skip", "reason": "no longer flagged"})
            continue
        if is_excluded(s["id"], excl) or is_excluded(t["id"], excl):
            out.append({**row, "status": "skip", "reason": "excluded entity (merge review / user decision)"})
            continue
        if rid[:8] in DECISIONS:
            rule, action = "hand", DECISIONS[rid[:8]]
        else:
            m = mechanical(rel["type"], s, t, rel["desc"])
            if not m:
                missing.append(f"{rid[:8]} {rel['type']} {s['name']} [{s['type']}] -> {t['name']} [{t['type']}] :: {rel['desc'][:120]}")
                continue
            rule, action = m
        row.update(rule=rule, action=action)
        verb = action.split(None, 1)[0]
        if verb in ("leave", "delete"):
            row["reason"] = action.split(None, 1)[1] if " " in action else ""
        touched = {s["id"], t["id"]}
        if verb == "leave":
            out.append({**row, "status": "leave"})
            continue
        new_src, new_tgt, new_type = s["id"], t["id"], rel["type"]
        if verb != "delete":
            for tok in action.split(";"):
                k, _, v = tok.partition("=")
                if k == "src":
                    new_src = v
                elif k == "tgt":
                    new_tgt = v
                elif k == "swap":
                    new_src, new_tgt = new_tgt, new_src
                elif k == "type":
                    new_type = v
                else:
                    raise SystemExit(f"bad action token {tok!r} for {rid}")
            touched |= {new_src, new_tgt}
        if any(is_excluded(e, excl) for e in touched):
            out.append({**row, "status": "skip", "reason": "excluded entity (merge review / user decision)"})
            continue
        if verb == "delete":
            out.append({**row, "status": "planned", "op": "delete"})
            continue
        ns, nt = ents[new_src], ents[new_tgt]
        problem = endpoint_problem(new_type, ns["type"], nt["type"])
        row.update(new_type=new_type, new_source_id=ns["id"], new_source=f"{ns['name']} [{ns['type']}]",
                   new_target_id=nt["id"], new_target=f"{nt['name']} [{nt['type']}]",
                   era_gap_after=era_gap(new_type, ns, nt))
        if problem:
            missing.append(f"INVALID {rid[:8]} {action}: {problem}")
            continue
        dup = existing_equivalent(cur, new_type, new_src, new_tgt, rel["start"], rid)
        key = (new_type, *(sorted((new_src, new_tgt)) if new_type in SYMMETRIC else (new_src, new_tgt)), rel["start"])
        if dup:
            out.append({**row, "status": "planned", "op": "delete", "reason": f"duplicate of {dup} after fix"})
            continue
        if key in seen:
            out.append({**row, "status": "planned", "op": "delete",
                        "reason": f"duplicate within plan: {seen[key]} gets the same fix"})
            continue
        seen[key] = rid
        out.append({**row, "status": "planned", "op": "update"})
    if missing:
        raise SystemExit("no decision for:\n" + "\n".join(missing))
    moving = {r["relationship_id"] for r in out if r.get("status") == "planned"}
    for r in out:
        reason = r.get("reason") or ""
        if reason.startswith("duplicate of ") and reason.split()[2] in moving:
            raise SystemExit(f"{r['relationship_id']} duplicates {reason.split()[2]}, which is itself being changed")
    return out


FIELDS = ["relationship_id", "status", "op", "rule", "action", "reason", "flag_detail",
          "old_type", "old_source_id", "old_source", "old_target_id", "old_target",
          "new_type", "new_source_id", "new_source", "new_target_id", "new_target",
          "era_gap_after", "start_year", "description"]


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in fields})


def sql_lit(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, (dict, list)):
        v = json.dumps(v, ensure_ascii=False)
    return "'" + str(v).replace("'", "''") + "'"


def backup(path: Path) -> None:
    cmd = [*COMPOSE, "exec", "-T", "db", "pg_dump", "-U", "history-mapped", "-Fc",
           "-t", "public.relationships", "-t", "public.chronicle_entries", "history-mapped"]
    with path.open("wb") as fh:
        subprocess.run(cmd, stdout=fh, check=True)
    if path.stat().st_size < 1000:
        raise SystemExit("backup looks empty; refusing to apply")


def survivor_of(reason: str) -> str | None:
    """The link a duplicate-delete keeps (its chronicle entries move there)."""
    m = re.match(r"duplicate (?:of|within plan:) ([0-9a-f-]{36})", reason or "")
    return m.group(1) if m else None


def fingerprint(cur, rel_ids: list[str], chron_ids: list[str]) -> str:
    cur.execute("""SELECT md5(coalesce(string_agg(row_to_json(r)::text, '|' ORDER BY r.relationship_id), ''))
                   FROM relationships r WHERE relationship_id = ANY(%s::uuid[])""", (rel_ids,))
    a = cur.fetchone()[0]
    cur.execute("""SELECT md5(coalesce(string_agg(entry_id::text || ':' || coalesce(primary_relationship_id::text, ''),
                                              '|' ORDER BY entry_id), ''))
                   FROM chronicle_entries WHERE entry_id = ANY(%s::uuid[])""", (chron_ids,))
    return a + cur.fetchone()[0]


def apply(conn, rows: list[dict]) -> tuple[list[dict], list[str]]:
    """Run the planned changes in the open transaction; return (applied rows, rollback statements)."""
    cur = conn.cursor()
    applied, rollback = [], []
    for r in rows:
        if r.get("status") != "planned":
            continue
        rid = r["relationship_id"]
        guard = (rid, r["old_source_id"], r["old_target_id"], r["old_type"])
        if r["op"] == "update":
            cur.execute("""UPDATE relationships SET source_entity_id = %s, target_entity_id = %s,
                                  relationship_type = %s::relationship_type
                           WHERE relationship_id = %s AND source_entity_id = %s AND target_entity_id = %s
                             AND relationship_type = %s::relationship_type""",
                        (r["new_source_id"], r["new_target_id"], r["new_type"], *guard))
            if cur.rowcount != 1:
                applied.append({**r, "status": "skipped", "reason": "changed concurrently"})
                continue
            rollback.append(
                f"UPDATE relationships SET source_entity_id = {sql_lit(r['old_source_id'])}, "
                f"target_entity_id = {sql_lit(r['old_target_id'])}, relationship_type = {sql_lit(r['old_type'])} "
                f"WHERE relationship_id = {sql_lit(rid)} AND source_entity_id = {sql_lit(r['new_source_id'])} "
                f"AND target_entity_id = {sql_lit(r['new_target_id'])} AND relationship_type = {sql_lit(r['new_type'])};")
            applied.append({**r, "status": "applied"})
            continue
        cur.execute("SELECT * FROM relationships WHERE relationship_id = %s AND source_entity_id = %s "
                    "AND target_entity_id = %s AND relationship_type = %s::relationship_type", guard)
        full = cur.fetchone()
        if not full:
            applied.append({**r, "status": "skipped", "reason": "changed concurrently"})
            continue
        cols = [d.name for d in cur.description]
        keep = survivor_of(r.get("reason"))
        if keep:
            cur.execute("SELECT 1 FROM relationships WHERE relationship_id = %s", (keep,))
            if not cur.fetchone():
                applied.append({**r, "status": "skipped", "reason": f"duplicate's survivor {keep} is gone"})
                continue
        cur.execute("SELECT entry_id::text FROM chronicle_entries WHERE primary_relationship_id = %s "
                    "ORDER BY 1", (rid,))
        chron = [x[0] for x in cur.fetchall()]
        if keep and chron:
            cur.execute("UPDATE chronicle_entries SET primary_relationship_id = %s WHERE primary_relationship_id = %s",
                        (keep, rid))
        cur.execute("DELETE FROM relationships WHERE relationship_id = %s AND source_entity_id = %s "
                    "AND target_entity_id = %s AND relationship_type = %s::relationship_type", guard)
        if cur.rowcount != 1:
            raise SystemExit(f"delete of {rid} hit {cur.rowcount} rows")
        vals = []
        for c, x in zip(cols, full):
            if x is not None and c.endswith("_id"):
                x = str(x)
            elif hasattr(x, "isoformat"):
                x = x.isoformat()
            vals.append(sql_lit(x))
        rollback.append(f"INSERT INTO relationships ({', '.join(cols)}) VALUES ({', '.join(vals)}) ON CONFLICT DO NOTHING;")
        if chron:
            was = f"primary_relationship_id = {sql_lit(keep)}" if keep else "primary_relationship_id IS NULL"
            rollback.append(f"UPDATE chronicle_entries SET primary_relationship_id = {sql_lit(rid)} "
                            f"WHERE entry_id IN ({', '.join(sql_lit(c) for c in chron)}) AND {was};")
        applied.append({**r, "status": "applied", "chronicle_entries": " ".join(chron),
                        "chronicle_moved_to": keep if chron else ""})
    return applied, rollback


def touched_entities(rows: list[dict]) -> list[str]:
    ids = set()
    for r in rows:
        if r.get("status") == "applied":
            ids |= {x for x in (r.get("old_source_id"), r.get("old_target_id"),
                                r.get("new_source_id"), r.get("new_target_id")) if x}
    return sorted(ids)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--trial", action="store_true",
                      help="apply, then run the rollback, check the rows are restored, and roll everything back")
    mode.add_argument("--apply", action="store_true", help="back up, then apply planned rows in one transaction")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    conn = connect(read_only=not (args.apply or args.trial))
    rows = plan(conn)
    if not args.trial:
        write_csv(OUT / "planned.csv", rows, FIELDS)
    c = Counter((r["status"], r.get("op") or (r.get("reason") or "").split(":")[0].split(" ")[0]) for r in rows)
    for k, n in sorted(c.items()):
        print(f"{n:5d}  {k[0]:8s} {k[1]}")
    if not (args.apply or args.trial):
        print(f"plan written to {OUT / 'planned.csv'} (dry run)")
        return
    cur = conn.cursor()
    rel_ids = [r["relationship_id"] for r in rows if r.get("status") == "planned"]
    rel_ids += [s for s in (survivor_of(r.get("reason")) for r in rows) if s]
    cur.execute("SELECT entry_id::text FROM chronicle_entries WHERE primary_relationship_id = ANY(%s::uuid[])",
                (rel_ids,))
    chron_ids = [x[0] for x in cur.fetchall()]
    before = fingerprint(cur, rel_ids, chron_ids)
    if args.apply:
        backup(OUT / "pre-apply.dump")
    applied, rollback = apply(conn, rows)
    if args.trial:
        for stmt in rollback:
            cur.execute(stmt)
        after = fingerprint(cur, rel_ids, chron_ids)
        conn.rollback()
        print(Counter(r["status"] for r in applied), "rollback restores rows:", before == after)
        return
    conn.commit()
    (OUT / "rollback.sql").write_text(
        "-- rollback for relfix-type-b-20261101: guarded inverses, in apply order\nBEGIN;\n"
        + "\n".join(rollback) + "\nCOMMIT;\n", encoding="utf-8")
    write_csv(OUT / "applied.csv", applied, FIELDS + ["chronicle_entries", "chronicle_moved_to"])
    ents = touched_entities(applied)
    (OUT / "touched-entities.txt").write_text("\n".join(ents) + "\n", encoding="utf-8")
    print(Counter(r["status"] for r in applied), f"{len(ents)} touched entities")


if __name__ == "__main__":
    sys.exit(main())
