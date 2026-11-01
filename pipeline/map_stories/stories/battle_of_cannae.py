"""Battle of Cannae, 2 August 216 BC — map story builder.

Reconstruction: the right-bank (south-eastern) site most modern historians and
the Cannae site museum favour. The armies fought in the low pocket of plain
between the Aufidus (Ofanto) and the escarpment of the Cannae ridge, the Romans
facing roughly south-west with their right on the river and their left under
the ridge (Polybius 3.113; Goldsworthy, Cannae, 2001; Mahaney 2024, fig. 3).

Everything on the field is placed in a battle frame: `F(u, v)` is `u` metres
from the field's midpoint towards the Carthaginian side (bearing 215) and `v`
metres towards the river side (bearing 305, the Roman right / Carthaginian
left). The river is the modern OSM course; the ancient channel probably lay a
few hundred metres further north-west, so frontages are drawn slightly
compressed to fit today's pocket (see `uncertainty`).

    scripts/capped.sh pipeline/.venv/bin/python -m pipeline.map_stories build battle_of_cannae
"""

from __future__ import annotations

from pipeline.map_stories.geo import arc, clip, lines_of, offset, place_geometry, r6, rel, simplify

# ── anchors ───────────────────────────────────────────────────────────────

#: The atlas entity's point (Wikipedia's coordinates), used as the local origin.
ORIGIN = (16.1325, 41.306389)
#: The Cannae citadel (Canne della Battaglia, OSM).
CANNAE = (16.15128, 41.29661)

#: Roman facing: towards the Carthaginians, roughly south-west.
AX = 215.0
ROMAN_FACING = AX
PUNIC_FACING = AX - 180  # 35, north-east
INWARD_FROM_LEFT = AX - 90  # 125: the river-side African block turning to face the Roman flank
INWARD_FROM_RIGHT = AX + 90  # 305: the ridge-side African block turning the other way

#: Midpoint between the battle lines at deployment, in the pocket of plain
#: between the river's north-flowing bend and the Cannae escarpment.
MID = offset(ORIGIN, east=1000, north=-600)


def L(east: float, north: float) -> list[float]:
    """A point `east`/`north` metres from the atlas point."""
    return offset(ORIGIN, east=east, north=north)


def F(u: float, v: float) -> list[float]:
    """A point in the battle frame: `u` towards the Carthaginians, `v` towards the river."""
    return rel(MID, AX, ahead=u, right=v)


def rect(c: list[float], facing: float, width: float, depth: float) -> list[list[float]]:
    """A rectangular ring (camp outline) `width` across and `depth` deep."""
    return [rel(c, facing, ahead=a, right=b) for a, b in ((depth / 2, -width / 2), (depth / 2, width / 2), (-depth / 2, width / 2), (-depth / 2, -width / 2))]


def river() -> list[list[float]]:
    """The modern Ofanto through the field, from OpenStreetMap."""
    geo = place_geometry("Fiume Ofanto", "waterway")
    centre = L(1000, -300)
    runs = [clip(line, centre, 4200) for line in lines_of(geo or {})]
    return simplify(max(runs, key=len), 20)


# Escarpment edge of the Cannae ridge (≈25 m contour, SRTM), east/north metres from ORIGIN.
RIDGE_EDGE = [(250, -1850), (600, -1700), (850, -1550), (1050, -1400), (1250, -1280), (1420, -1120), (1550, -950), (1680, -750), (1760, -560), (1900, -400), (2100, -250), (2350, -100), (2600, 20)]

# Camp sites (conjectural; Polybius 3.110–111): the main Roman camp on the
# north-western bank, the smaller one across the river ~10 stades away, and
# Hannibal's camp on the same bank as the main Roman camp.
MAIN_CAMP = L(1500, 1100)
SMALL_CAMP = L(3000, 100)
PUNIC_CAMP = L(-1100, -700)

# ── deployment geometry (battle frame) ────────────────────────────────────

R_LINE = -280  # Roman line (centre of the infantry block)
P_LINE = 420  # Carthaginian crescent's anchor (its bulge stands ~95 m ahead of this)
P_VC = -100  # Carthaginian line centre, shifted towards the ridge where the pocket is wider

# Roman: horse 200 | infantry 760 | allied horse 240 (≈1.2 km; Goldsworthy's ≈1.95 km needs the ancient river course)
R_INF = dict(at=F(R_LINE, 0), facing=ROMAN_FACING, width=760, depth=80)
R_HORSE = dict(at=F(R_LINE, 490), facing=ROMAN_FACING, width=200, depth=40)
A_HORSE = dict(at=F(R_LINE, -510), facing=ROMAN_FACING, width=240, depth=40)

# Carthaginian: Hasdrubal 220 | Africans 90 | crescent 560 | Africans 90 | Numidians 220
CRESCENT = dict(at=F(P_LINE, P_VC), facing=PUNIC_FACING, width=560, depth=30, shape="crescent", curve=160)
HORN_FRONT = P_LINE + 80 - 15  # u of the crescent's horn tips (front edge)
AFR_L = dict(at=F(HORN_FRONT + 27, P_VC + 335), facing=PUNIC_FACING, width=90, depth=55)
AFR_R = dict(at=F(HORN_FRONT + 27, P_VC - 335), facing=PUNIC_FACING, width=90, depth=55)
HASDRUBAL = dict(at=F(460, 392), facing=PUNIC_FACING, width=210, depth=100)
NUMIDIANS = dict(at=F(460, -600), facing=PUNIC_FACING, width=220, depth=60)

# After the crescent bends back: its horn tips hold, its centre gives ~280 m.
BENT_AT = 560  # anchor of the hollowed crescent (curve -120)
ROMAN_PUSH_AT = 480  # anchor of the Roman mass, bulging into the hollow (curve +120)
REAR_AT = 385  # anchor of Hasdrubal's horse on the Roman rear

ALLIED_FLIGHT = F(-500, -1150)  # over the Cannae ridge to the east


def build() -> dict:
    return {
        "schema": 2,
        "slug": "battle-of-cannae",
        "kind": "battle",
        "entity": {"name": "Battle of Cannae", "wikidata": "Q179591"},
        "title": "Battle of Cannae",
        "date_label": "2 August 216 BC",
        "year": -216,
        "intro": (
            "By the summer of 216 BC Hannibal had spent two years loose in Italy and had already destroyed Roman armies "
            "at the Trebia and Lake Trasimene. Rome answered by sending both consuls of the year, Lucius Aemilius Paullus "
            "and Gaius Terentius Varro, with eight legions and as many allied troops, the largest army the Republic had "
            "ever put into a single field. Hannibal drew it south into Apulia by seizing the hilltop depot at Cannae, and "
            "the two armies camped facing each other along the river Aufidus, the modern Ofanto, a few kilometres from the "
            "Adriatic. The consuls took command on alternate days. On 2 August it was Varro's turn: he crossed the river "
            "and offered battle on the narrow plain below the Cannae ridge, trusting the sheer weight of his infantry. "
            "Hannibal, outnumbered by almost two to one, arranged his army so that this weight would carry the Romans "
            "into a trap."
        ),
        "outcome": (
            "A crushing Carthaginian victory: the Roman army was surrounded and largely destroyed, Paullus was killed and "
            "Varro fled, in one of the bloodiest single days of battle in ancient history."
        ),
        "uncertainty": (
            "Where the battle was fought is disputed. This map follows the view of most modern historians (among them "
            "Goldsworthy) and of the Cannae site museum: the right, south-eastern bank, in the plain between the river and "
            "the Cannae ridge, with the Romans facing roughly south-west and their right on the river. Older scholars such "
            "as Delbrück put it on the left bank. The river is drawn on its modern course, but the Aufidus has moved since "
            "216 BC and probably ran a few hundred metres further north-west, which would have widened the field; the "
            "frontages here are therefore slightly compressed; the river is drawn dashed for that reason. The camp sites, "
            "the crossings and Varro's route are conjectural. The legions are drawn in the usual three lines, though "
            "Connolly thought the triarii stayed behind to guard the camps. Livy's wind, the Volturnus, is usually read as "
            "a south-easterly; Dodge made it easterly. Numbers follow Polybius and Goldsworthy; Livy's differ, and modern "
            "estimates of the Roman dead vary widely."
        ),
        "alt_sites": [
            {
                "at": L(200, 700),
                "label": "Left-bank theory",
                "note": "Some reconstructions put the battle on the north-western (left) bank of the Aufidus; the point is approximate.",
            }
        ],
        "sources": [
            {"title": "Polybius, Histories 3.107–118", "kind": "primary"},
            {"title": "Livy, History of Rome 22.40–52", "kind": "primary"},
            {"title": "Adrian Goldsworthy, Cannae (Cassell Fields of Battle, 2001)", "url": "https://erenow.org/ww/cannae-fields-of-battle/13.php", "kind": "secondary"},
            {
                "title": "W. C. Mahaney, Cannae battlefield: a geomorphic-geoarchaeologic perspective, Studia Quaternaria 41 (2024)",
                "url": "https://journals.pan.pl/Content/130738/PDF/04_Mahaney-1.pdf",
                "kind": "secondary",
            },
            {"title": "Battle of Cannae — Wikipedia", "url": "https://en.wikipedia.org/wiki/Battle_of_Cannae", "kind": "web"},
            {"title": "OpenStreetMap (course of the Ofanto) and SRTM heights", "url": "https://www.openstreetmap.org/", "kind": "web"},
        ],
        "sides": [
            {
                "id": "rome",
                "name": "Roman and allied army",
                "color": "#b91c1c",
                "polity": {"name": "Roman Republic", "wikidata": "Q17167"},
                "commanders": [
                    {"name": "Gaius Terentius Varro", "wikidata": "Q315274", "role": "consul, in command on the day; left wing"},
                    {"name": "Lucius Aemilius Paullus", "wikidata": "Q432244", "role": "consul, right wing; killed"},
                    {"name": "Gnaeus Servilius Geminus", "wikidata": "Q554632", "role": "proconsul, centre; killed"},
                ],
                "strength": "c. 86,000 (c. 76,000 on the field, 10,000 guarding the camps)",
                "losses": "c. 48,000–70,000 killed; c. 10,000–19,000 captured",
            },
            {
                "id": "carthage",
                "name": "Carthaginian army",
                "color": "#6d28d9",
                "polity": {"name": "Carthage", "wikidata": "Q2429397"},
                "commanders": [
                    {"name": "Hannibal", "wikidata": "Q36456", "role": "commander-in-chief, centre"},
                    {"name": "Mago", "wikidata": "Q335604", "role": "centre, with Hannibal"},
                    {"name": "Hasdrubal", "role": "heavy cavalry, left wing"},
                    {"name": "Hanno", "role": "Numidian cavalry, right wing (Livy names Maharbal)"},
                ],
                "strength": "c. 50,000 (40,000 foot, 10,000 horse)",
                "losses": "c. 5,700–8,000 killed",
            },
        ],
        "units": [
            {"id": "velites", "side": "rome", "kind": "light_infantry", "label": "Velites", "strength": "c. 15,000", "note": "Young and poor citizens with javelins, screening the legions"},
            {
                "id": "roman-infantry",
                "side": "rome",
                "kind": "heavy_infantry",
                "label": "Legions & allied foot",
                "strength": "c. 55,000",
                "commander": "Gnaeus Servilius Geminus",
                "note": "Maniples closed up and stacked perhaps 70 ranks deep",
            },
            {"id": "roman-horse", "side": "rome", "kind": "cavalry", "label": "Roman cavalry", "strength": "c. 2,400", "commander": "Paullus"},
            {"id": "allied-horse", "side": "rome", "kind": "cavalry", "label": "Allied cavalry", "strength": "c. 3,600", "commander": "Varro"},
            {"id": "paullus", "side": "rome", "kind": "commander", "label": "Paullus", "wikidata": "Q432244"},
            {"id": "varro", "side": "rome", "kind": "commander", "label": "Varro", "wikidata": "Q315274"},
            {"id": "slingers", "side": "carthage", "kind": "light_infantry", "label": "Slingers & spearmen", "strength": "c. 8,000", "note": "Balearic slingers and light spearmen"},
            {
                "id": "hasdrubal-horse",
                "side": "carthage",
                "kind": "heavy_cavalry",
                "label": "Spanish & Gallic horse",
                "strength": "c. 6,500",
                "commander": "Hasdrubal",
                "note": "Massed deep on the river flank",
            },
            {"id": "africans-left", "side": "carthage", "kind": "heavy_infantry", "label": "African foot", "strength": "c. 5,000", "note": "Libyan veterans in captured Roman armour"},
            {
                "id": "gauls-spaniards",
                "side": "carthage",
                "kind": "infantry",
                "label": "Gauls & Spaniards",
                "strength": "c. 22,000",
                "commander": "Hannibal and Mago",
                "note": "Alternating Gallic and Spanish companies",
            },
            {"id": "africans-right", "side": "carthage", "kind": "heavy_infantry", "label": "African foot", "strength": "c. 5,000", "note": "Libyan veterans in captured Roman armour"},
            {
                "id": "numidians",
                "side": "carthage",
                "kind": "light_cavalry",
                "label": "Numidian horse",
                "strength": "c. 3,500",
                "commander": "Hanno",
            },
            {"id": "hannibal", "side": "carthage", "kind": "commander", "label": "Hannibal", "wikidata": "Q36456"},
        ],
        "terrain": [
            {"id": "aufidus", "kind": "river", "label": "Aufidus (Ofanto), modern course", "line": river(), "conjectural": True},
            {"id": "cannae-ridge", "kind": "ridge", "label": "Cannae ridge", "line": [L(e, n) for e, n in RIDGE_EDGE]},
            {"id": "cannae", "kind": "town", "label": "Cannae", "at": r6(CANNAE)},
            {"id": "main-camp", "kind": "camp", "label": "Main Roman camp", "area": rect(MAIN_CAMP, 35, 700, 600), "conjectural": True},
            {"id": "small-camp", "kind": "camp", "label": "Smaller Roman camp", "area": rect(SMALL_CAMP, 35, 450, 420), "conjectural": True},
            {"id": "punic-camp", "kind": "camp", "label": "Hannibal's camp", "area": rect(PUNIC_CAMP, 35, 650, 550), "conjectural": True},
        ],
        "steps": steps(),
    }


def steps() -> list[dict]:
    s: list[dict] = []

    # 1 ── the camps, 1 August ───────────────────────────────────────────
    raid_at = L(2650, 430)
    s.append(
        {
            "id": "camps",
            "title": "Camps on the Aufidus",
            "time": "1 August",
            "narrative": (
                "The Romans had shadowed Hannibal south and built two camps astride the Aufidus: the main one, holding about "
                "two-thirds of the army, on the north-western bank, and a smaller one across the river some two kilometres "
                "away to cover foraging on that side. Hannibal pitched his camp on the same bank as the main Roman camp. On 1 "
                "August he drew up his army and offered battle, but Paullus, in command that day, would not be hurried. "
                "Hannibal then sent his Numidian horsemen across the river to fall on the water parties of the smaller camp."
            ),
            "camera": {"center": L(900, 150), "zoom": 13.0},
            "positions": {
                "numidians": {"at": raid_at, "facing": 60, "width": 260, "depth": 70, "state": "engaged"},
            },
            "moves": [
                {"unit": "numidians", "type": "attack", "path": [PUNIC_CAMP, L(400, -500), L(1700, -150), raid_at], "label": "raid"},
            ],
            "notes": [
                {"at": L(2900, 650), "text": "Numidians strike the water parties", "kind": "event"},
            ],
            "focus": ["numidians"],
        }
    )

    # 2 ── Varro crosses, dawn 2 August ──────────────────────────────────
    s.append(
        {
            "id": "varro-crosses",
            "title": "Varro crosses the river",
            "time": "2 August, dawn",
            "narrative": (
                "Command passed to Varro, who meant to fight. At first light the army marched out of the main camp, forded "
                "the river and joined the troops of the smaller camp on the south-eastern bank. He formed it facing roughly "
                "south-west across a cramped plain: the citizen cavalry under Paullus on the right against the river, the "
                "allied cavalry under Varro himself on the left beneath the Cannae ridge, and between them the heavy infantry "
                "under Gnaeus Servilius Geminus. The maniples were closed up and stacked many times deeper than their width, "
                "so some 55,000 men held only about a kilometre of front, screened by the light-armed velites. About 10,000 "
                "men stayed behind to hold the camps."
            ),
            "light": "dawn",
            "positions": {
                "numidians": {"state": "hidden"},
                "roman-infantry": {**R_INF, "lines": 3},
                "roman-horse": dict(R_HORSE),
                "allied-horse": dict(A_HORSE),
                "velites": {"at": F(-140, 0), "facing": ROMAN_FACING, "width": 900, "depth": 15},
                "paullus": {"with": "roman-horse"},
                "varro": {"with": "allied-horse"},
            },
            "moves": [
                {"unit": "roman-infantry", "type": "march", "path": [MAIN_CAMP, L(1350, 250), R_INF["at"]], "conjectural": True},
                {"unit": "roman-horse", "type": "march", "path": [MAIN_CAMP, L(1150, 200), R_HORSE["at"]], "conjectural": True},
                {"unit": "allied-horse", "type": "march", "path": [SMALL_CAMP, L(2300, -350), A_HORSE["at"]], "conjectural": True},
            ],
            "notes": [
                {"at": MAIN_CAMP, "text": "About 10,000 men left to guard the camps", "kind": "event"},
            ],
            "focus": ["roman-infantry", "roman-horse", "allied-horse"],
        }
    )

    # 3 ── Hannibal crosses and forms the crescent ───────────────────────
    s.append(
        {
            "id": "crescent",
            "title": "Hannibal forms the crescent",
            "time": "Early morning",
            "narrative": (
                "Hannibal answered by sending his Balearic slingers and light spearmen over the river as a screen and "
                "following with the rest of the army at two crossings. Beside the river he massed the Spanish and Gallic "
                "heavy horse under Hasdrubal, opposite the Roman cavalry; on the far right, under the ridge, stood the "
                "Numidians. The centre was Gallic and Spanish foot in alternating companies, which he pushed forward into a "
                "thin convex crescent, while the veteran African infantry waited in deep blocks on either side of it, held "
                "back from the bulge. Hannibal and his brother Mago took post in the centre. Livy says a wind the locals "
                "called the Volturnus rose against the Romans and drove dust into their faces, while the morning sun fell "
                "side-on to both armies."
            ),
            "light": "day",
            "wind": {"from": 135, "label": "Volturnus: dust in Roman faces (Livy)"},
            "sun": {"from": 95, "label": "Morning sun, side-on to both lines (Livy)"},
            "positions": {
                "slingers": {"at": F(225, P_VC), "facing": PUNIC_FACING, "width": 860, "depth": 15},
                "gauls-spaniards": dict(CRESCENT),
                "africans-left": dict(AFR_L),
                "africans-right": dict(AFR_R),
                "hasdrubal-horse": dict(HASDRUBAL),
                "numidians": {**NUMIDIANS, "state": "ready"},
                "hannibal": {"with": "gauls-spaniards"},
            },
            "moves": [
                {"side": "carthage", "type": "march", "path": [PUNIC_CAMP, L(-350, -620), L(150, -660), HASDRUBAL["at"]], "label": "first crossing", "conjectural": True},
                {"side": "carthage", "type": "march", "path": [PUNIC_CAMP, L(-500, -1000), L(80, -1050), CRESCENT["at"]], "label": "second crossing", "conjectural": True},
            ],
            "notes": [
                {"at": F(80, 520), "text": "Volturnus wind blows dust at the Romans", "kind": "event"},
            ],
            "focus": ["gauls-spaniards", "africans-left", "africans-right", "hasdrubal-horse", "numidians"],
        }
    )

    # 4 ── skirmishers ───────────────────────────────────────────────────
    s.append(
        {
            "id": "skirmish",
            "title": "The skirmishers open the battle",
            "time": "Morning",
            "narrative": (
                "The light troops opened the battle in the space between the lines. Hannibal's slingers and spearmen were "
                "far better trained than the velites, but neither screen could drive off the other, and the exchange of "
                "stones and javelins settled nothing and killed few. Livy says Paullus was badly hurt by a sling-stone at "
                "the outset yet stayed with his horsemen. Behind the screens the heavy troops finished forming up."
            ),
            "positions": {
                "velites": {"at": F(40, 0), "state": "engaged"},
                "slingers": {"at": F(130, P_VC), "state": "engaged"},
                "paullus": {"state": "wounded"},
            },
            "moves": [
                {"unit": "velites", "type": "advance", "path": [F(-140, 0), F(40, 0)]},
                {"unit": "slingers", "type": "advance", "path": [F(225, P_VC), F(130, P_VC)]},
            ],
            "notes": [
                {"at": F(-280, 490), "text": "Paullus hit by a sling-stone (Livy)", "kind": "event"},
            ],
            "focus": ["velites", "slingers"],
        }
    )

    # 5 ── the cavalry by the river ──────────────────────────────────────
    hasdrubal_clash = F(-205, 492)
    numidian_screen = F(40, -545)
    allied_fwd = F(-80, -510)
    s.append(
        {
            "id": "river-cavalry",
            "title": "Hasdrubal charges by the river",
            "time": "Morning",
            "narrative": (
                "As the skirmishers fell back through the gaps in their own lines, Hasdrubal led his heavy horsemen straight "
                "at the Roman cavalry along the river. Hemmed in between the water and the infantry, neither side had room "
                "to wheel, so the clash turned into a savage standing fight in which many riders dismounted and grappled on "
                "foot. Outnumbered nearly three to one, the Roman citizen cavalry was being cut to pieces. On the opposite "
                "wing the Numidians rode out against the allied horse and kept it busy, darting in to throw javelins and "
                "wheeling away before it could close."
            ),
            "positions": {
                "velites": {"at": F(-345, 0), "width": 700, "state": "ready"},
                "slingers": {"at": F(780, P_VC), "width": 600, "state": "ready"},
                "hasdrubal-horse": {"at": hasdrubal_clash, "width": 200, "state": "engaged"},
                "roman-horse": {"state": "engaged"},
                "numidians": {"at": numidian_screen, "state": "engaged"},
                "allied-horse": {"at": allied_fwd, "state": "engaged"},
            },
            "moves": [
                {"unit": "velites", "type": "retreat", "path": [F(40, 0), F(-345, 0)]},
                {"unit": "slingers", "type": "retreat", "path": [F(130, P_VC), F(780, P_VC)]},
                {"unit": "hasdrubal-horse", "type": "charge", "path": [HASDRUBAL["at"], F(150, 450), hasdrubal_clash]},
                {"unit": "numidians", "type": "advance", "path": [NUMIDIANS["at"], numidian_screen]},
                {"unit": "allied-horse", "type": "advance", "path": [A_HORSE["at"], allied_fwd]},
            ],
            "notes": [
                {"at": F(-240, 610), "text": "Riders dismount and fight on foot", "kind": "clash"},
            ],
            "focus": ["hasdrubal-horse", "roman-horse"],
        }
    )

    # 6 ── the infantry clash: the crescent bends back ───────────────────
    roman_rout = F(-500, 140)
    hasdrubal_rally = F(-380, 250)
    roman_contact = F(270, -50)  # the legions' front against the bulge of the crescent
    roman_mass = F(ROMAN_PUSH_AT, P_VC)
    s.append(
        {
            "id": "crescent-bends",
            "title": "The crescent bends back",
            "time": "Late morning",
            "narrative": (
                "The broken Roman horsemen fled along the riverbank and were hunted down, while Hasdrubal rallied his "
                "squadrons instead of chasing far. Paullus escaped the wreck of his wing and joined the infantry in the "
                "centre. The legions now advanced and struck the bulge of the crescent, which gave ground slowly, as Hannibal "
                "intended, until its centre had been pressed back into a hollow. Pouring after it, the Romans crowded in "
                "towards the middle, losing their order and pushing ever deeper between the two African blocks, which had "
                "not yet moved."
            ),
            "positions": {
                "velites": {"state": "hidden"},
                "roman-horse": {"at": roman_rout, "width": 140, "depth": 30, "state": "routed"},
                "hasdrubal-horse": {"at": hasdrubal_rally, "width": 220, "state": "ready"},
                "paullus": {"with": "roman-infantry"},
            },
            "moves": [
                {"unit": "roman-horse", "type": "rout", "path": [R_HORSE["at"], F(-420, 330), roman_rout]},
                {"unit": "hasdrubal-horse", "type": "pursuit", "path": [hasdrubal_clash, F(-330, 400), hasdrubal_rally]},
                {"unit": "paullus", "type": "march", "path": [R_HORSE["at"], F(-330, 240), R_INF["at"]]},
            ],
            "beats": [
                {
                    "label": "The legions strike the bulge of the crescent",
                    "positions": {
                        "roman-infantry": {"at": roman_contact, "state": "engaged"},
                        "gauls-spaniards": {"state": "engaged"},
                    },
                    "moves": [{"unit": "roman-infantry", "type": "attack", "path": [R_INF["at"], roman_contact]}],
                },
                {
                    "label": "The centre gives ground into a hollow",
                    "positions": {
                        "roman-infantry": {"at": roman_mass, "width": 560, "depth": 120, "shape": "crescent", "curve": 120, "lines": 1},
                        "gauls-spaniards": {"at": F(BENT_AT, P_VC), "curve": -120},
                        "hannibal": {"at": F(700, P_VC)},
                    },
                    "moves": [
                        {"unit": "roman-infantry", "type": "attack", "path": [roman_contact, roman_mass]},
                        {"unit": "gauls-spaniards", "type": "retreat", "path": [CRESCENT["at"], F(BENT_AT, P_VC)]},
                    ],
                    "notes": [{"at": F(660, 120), "text": "The centre gives ground on purpose", "kind": "event"}],
                },
            ],
            "focus": ["roman-infantry", "gauls-spaniards"],
        }
    )

    # 7 ── Hasdrubal rides behind the Roman army ─────────────────────────
    behind_allies = F(-230, -500)
    numidian_chase = F(-350, -1000)
    # Livy: Varro fell in with the fleeing allied horse. Venusia lies ~45 km
    # off on a bearing of ~215°, beyond the Carthaginian army, so he rides
    # south over the ridge first; the arrow stops near the field and the note
    # carries the rest of the journey.
    varro_path = [allied_fwd, F(-190, -860), L(2350, -1250), L(2050, -1750)]
    s.append(
        {
            "id": "hasdrubal-ride",
            "title": "Hasdrubal rides behind the Roman army",
            "time": "Around midday",
            "narrative": (
                "Hasdrubal now led his rallied horsemen right across the field behind the backs of the struggling legions to "
                "the far wing. The allied cavalry, still tangled with the Numidians, saw this mass of heavy horse bearing "
                "down on its rear and broke without waiting for the blow. Varro fled with them and, with some seventy "
                "riders, eventually reached Venusia, about 45 km to the south-west. Hasdrubal left the chase to the "
                "Numidians, who were ideal for running down fugitives, and kept his own squadrons in hand for the decisive "
                "stroke."
            ),
            "sun": {"from": 180, "label": "Midday sun"},
            "positions": {
                "roman-horse": {"state": "hidden"},
                "hasdrubal-horse": {"at": behind_allies, "facing": ROMAN_FACING, "state": "ready"},
                "allied-horse": {"at": ALLIED_FLIGHT, "facing": 100, "state": "routed"},
                "numidians": {"at": numidian_chase, "facing": 100, "state": "engaged"},
                "varro": {"at": varro_path[-1]},
            },
            "moves": [
                {"unit": "hasdrubal-horse", "type": "flank", "path": arc(hasdrubal_rally, behind_allies, -220)},
                {"unit": "allied-horse", "type": "rout", "path": [allied_fwd, F(-260, -800), ALLIED_FLIGHT]},
                {"unit": "numidians", "type": "pursuit", "path": [numidian_screen, F(-150, -760), numidian_chase]},
                {"unit": "varro", "type": "retreat", "path": varro_path, "label": "to Venusia", "conjectural": True},
            ],
            "notes": [
                {"at": F(-60, -720), "text": "Allied cavalry breaks without a fight", "kind": "clash"},
                {"at": varro_path[-1], "text": "Varro flees towards Venusia, c. 45 km", "kind": "event"},
            ],
            "focus": ["hasdrubal-horse", "allied-horse", "varro"],
        }
    )

    # 8 ── the Africans turn inward ──────────────────────────────────────
    afr_l_turned = F(420, P_VC + 300)
    afr_r_turned = F(420, P_VC - 300)
    s.append(
        {
            "id": "africans-turn",
            "title": "The Africans turn inward",
            "time": "Early afternoon",
            "narrative": (
                "With the Roman mass now deep inside the hollow, the African infantry on each wing turned to face inward and "
                "advanced against its open flanks, the block by the river wheeling to its right and the block under the "
                "ridge to its left. These were seasoned troops, many of them wearing armour stripped from Roman dead at the "
                "Trebia and Trasimene. The legionaries, packed so tightly that men in the middle could barely use their "
                "weapons, could not turn to meet them."
            ),
            "positions": {
                "allied-horse": {"state": "hidden"},
                "numidians": {"state": "hidden"},
                "varro": {"state": "hidden"},
                "africans-left": {"at": afr_l_turned, "facing": INWARD_FROM_LEFT, "width": 220, "depth": 30, "state": "engaged"},
                "africans-right": {"at": afr_r_turned, "facing": INWARD_FROM_RIGHT, "width": 220, "depth": 30, "state": "engaged"},
            },
            "moves": [
                {"unit": "africans-left", "type": "attack", "path": [AFR_L["at"], F(470, P_VC + 320), afr_l_turned]},
                {"unit": "africans-right", "type": "attack", "path": [AFR_R["at"], F(470, P_VC - 320), afr_r_turned]},
            ],
            "notes": [
                {"at": F(330, P_VC + 380), "text": "Africans strike the Roman flanks", "kind": "clash"},
            ],
            "focus": ["africans-left", "africans-right"],
        }
    )

    # 9 ── the ring closes ───────────────────────────────────────────────
    rear_attack = F(REAR_AT, P_VC)
    s.append(
        {
            "id": "ring-closes",
            "title": "The cavalry closes the ring",
            "time": "Early afternoon",
            "narrative": (
                "Hasdrubal's horsemen fell on the rear of the legions and completed the ring: Gauls and Spaniards in front, "
                "Africans on both flanks, cavalry behind. The Roman army, still more numerous than its enemy, was now "
                "trapped on a front of a few hundred metres. Its outer ranks had to fight in every direction while the men "
                "inside were crushed together, unable to reach the enemy or to escape, and repeated charges against the "
                "rear stopped the mass from turning to break out."
            ),
            "positions": {
                "hasdrubal-horse": {"at": rear_attack, "width": 560, "depth": 60, "shape": "crescent", "curve": 120, "state": "engaged"},
            },
            "moves": [
                {"unit": "hasdrubal-horse", "type": "charge", "path": arc(behind_allies, rear_attack, -150)},
            ],
            "notes": [
                {"at": F(300, P_VC - 470), "text": "Encirclement complete", "kind": "event"},
            ],
            "focus": ["hasdrubal-horse", "roman-infantry"],
        }
    )

    # 10 ── the slaughter; Paullus dies ──────────────────────────────────
    s.append(
        {
            "id": "slaughter",
            "title": "The slaughter",
            "time": "Afternoon to evening",
            "narrative": (
                "For hours the trapped army was cut down from the edges inward. Livy tells how Paullus, wounded and sitting "
                "on a stone, refused a horse that would have let him escape and died with his men; Servilius Geminus and "
                "Marcus Minucius Rufus fell too, with dozens of senators and military tribunes. Polybius puts the Roman dead "
                "at about 70,000 and Livy at about 48,000, against 5,700 to 8,000 on Hannibal's side, most of them Gauls of "
                "the centre. Only a few thousand Romans cut their way out and scattered to the camps and nearby towns."
            ),
            "sun": {"from": 255, "label": "Afternoon sun"},
            "positions": {
                "roman-infantry": {"state": "destroyed"},
                "paullus": {"state": "killed"},
            },
            "moves": [],
            "notes": [
                {"at": F(560, P_VC + 60), "text": "Paullus, Servilius and Minucius killed", "kind": "death"},
            ],
            "focus": ["roman-infantry", "paullus"],
        }
    )

    # 11 ── the camps ────────────────────────────────────────────────────
    s.append(
        {
            "id": "camps-fall",
            "title": "The camps surrender",
            "time": "Night and 3 August",
            "narrative": (
                "The men left to guard the main camp had attacked Hannibal's camp during the battle, Polybius says, and were "
                "driven back once the fighting on the plain was over. That night a group from the smaller camp under the "
                "tribune Publius Sempronius Tuditanus cut its way through to the main camp, and from there several thousand "
                "survivors slipped away to Canusium. The next day both camps surrendered. Within weeks Capua and much of "
                "southern Italy went over to Hannibal, but Rome refused to treat with him and fought on."
            ),
            "positions": {
                "slingers": {"state": "hidden"},
            },
            "moves": [
                {"side": "rome", "type": "attack", "path": [MAIN_CAMP, L(300, 250), PUNIC_CAMP], "label": "camp guard"},
                {"side": "rome", "type": "retreat", "path": [SMALL_CAMP, L(2300, 650), MAIN_CAMP], "label": "Tuditanus"},
            ],
            "notes": [
                {"at": L(1500, 1500), "text": "Both camps surrender the next day", "kind": "capture"},
                {"at": L(3000, -250), "text": "Tuditanus breaks out; survivors reach Canusium", "kind": "event"},
            ],
        }
    )
    return s
