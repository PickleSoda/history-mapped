"""Battle of Salamis (September 480 BC) — the naval sample story.

Reconstruction: Herodotus's line across the western end of the strait, from
St George's islet (left, Athenians) to the Kynosoura peninsula (right,
Spartans), facing the Attic shore; the Persians close the eastern exits round
Psyttaleia by night (and, after Diodorus, send the Egyptians round Salamis to
the Megara channel), then row in along the Attic shore at dawn and deploy
opposite, Phoenicians on their right toward Eleusis, Ionians on their left
toward Piraeus.

Everything is placed in metres from real anchors (OSM coastline, islets and
peaks, looked up while writing; see the story's `uncertainty`). The Greek and
Persian battle lines share one frame: `line(s, g)` is the point `s` metres
along the Greek baseline from its left end and `g` metres forward of it
(toward the Attic shore).
"""

from __future__ import annotations

from pipeline.map_stories.geo import bearing, dest, ellipse, offset, path

# ── anchors (OSM / Nominatim / Overpass, October 2026) ─────────────────────

O = (23.565, 37.9575)  # middle of the strait between Perama and Kynosoura
KYNOSOURA_TIP = (23.579257, 37.94703)  # end of the "dog's tail"
PROMONTORY = (23.552021, 37.953904)  # point north of the bay of Ambelaki
PSYTTALEIA = (23.58822, 37.94058)
XERXES_SEAT = (23.5565, 37.96853)  # "Throne of Xerxes" site, Perama
AKROKERAMOS = (23.60739, 37.94756)  # cape on the Attic side of the strait mouth
PHALERUM = (23.6952, 37.9283)  # Palaio Faliro
ATHENS = (23.7257, 37.9715)  # Acropolis
ELEUSIS = (23.53487, 38.04761)
MUNYCHIA = (23.65589, 37.94065)  # Kastella hill, Piraeus

ST_GEORGE = [
    [23.536987, 37.963328], [23.537845, 37.963768], [23.538352, 37.965505], [23.538523, 37.963619],
    [23.539957, 37.963498], [23.541339, 37.964567], [23.542214, 37.964756], [23.543208, 37.96352],
    [23.543253, 37.962949], [23.542617, 37.961332], [23.542282, 37.961099], [23.539931, 37.960784],
    [23.53848, 37.961034], [23.537356, 37.961569], [23.536485, 37.961606], [23.536485, 37.963194],
]
PSYTTALEIA_OUTLINE = [
    [23.580624, 37.936957], [23.581047, 37.938317], [23.583061, 37.94015], [23.583306, 37.940876],
    [23.584741, 37.941071], [23.58593, 37.941792], [23.586583, 37.941829], [23.590332, 37.943518],
    [23.590677, 37.94404], [23.591194, 37.944505], [23.591667, 37.944682], [23.594567, 37.944821],
    [23.595871, 37.943764], [23.595814, 37.942257], [23.591914, 37.94051], [23.591433, 37.939908],
    [23.590249, 37.939799], [23.589227, 37.938337], [23.58681, 37.93796], [23.585725, 37.937051],
    [23.583348, 37.93632], [23.580708, 37.936652],
]


def at(east: float, north: float) -> list[float]:
    """A point `east`/`north` metres from the middle of the strait."""
    return offset(O, east=east, north=north)


#: The Attic side of the strait, Perama to Cape Akrokeramos (480 BC, approx.).
ATTIC_SHORE = path(
    (23.5534, 37.9797), (23.5539, 37.9687), (23.5566, 37.9625), (23.5641, 37.9614), (23.5734, 37.9614), (23.5799, 37.9607),
    (23.5891, 37.9592), (23.5975, 37.9585), (23.6049, 37.9600), (23.6077, 37.9534), (23.6073, 37.9482),
)


def sea_area() -> list[list[float]]:
    """The water the fleets used, as one conjectural ring: the north channel,
    the strait along the Attic shore, round Piraeus into the bay of Phalerum,
    the open gulf to the south, and back up the east coast of Salamis past
    Kynosoura, the bay of Ambelaki and Paloukia. The Salamis and Piraeus
    shores are traced from the anchors above, a little to seaward; Psyttaleia
    and St George's islet are islands within it."""
    north = [at(-1200, 3900)]
    piraeus = [at(3650, -1150), at(3900, -1700), at(4100, -2400), at(4400, -3000), at(5000, -3500), at(6500, -3600), at(7600, -3400), at(8400, -2900), at(8800, -2500)]
    phalerum = [at(9600, -2500), at(10500, -2700), at(10900, -2900), at(11150, -3300), at(11300, -4100), at(11700, -6500)]
    gulf = [at(-2500, -6500), at(-1200, -4000), at(100, -2100), at(300, -1500)]
    kynosoura = [at(1100, -1350), at(1400, -1150), at(1100, -1100), at(300, -1130), at(-400, -1140), at(-850, -1150)]
    ambelaki = [at(-1300, -1050), at(-1800, -1150), at(-2150, -1000), at(-2150, -750), at(-1800, -650), at(-1450, -650), at(-1120, -450)]
    paloukia = [at(-1400, -300), at(-1700, -150), at(-2100, -100), at(-2600, -50), at(-3100, 150), at(-3150, 700), at(-2900, 1300), at(-2000, 2500), at(-1900, 3900)]
    return [*north, *ATTIC_SHORE, *piraeus, *phalerum, *gulf, *kynosoura, *ambelaki, *paloukia]


# The Greek baseline: left end just south of St George's islet, right end just
# north of the Kynosoura tail. Greek ships face FACING (toward the Attic shore).
LEFT_END = at(-2050, 250)
RIGHT_END = at(900, -950)
ALONG = bearing(LEFT_END, RIGHT_END)  # ~112°
FACING = round((ALONG - 90) % 360, 1)  # ~22°: the Greeks face north-north-east
P_FACING = round((FACING + 180) % 360, 1)  # the Persians face them


def line(s: float, g: float = 0.0) -> list[float]:
    """`s` metres along the Greek baseline from its left end, `g` metres forward."""
    return dest(dest(LEFT_END, ALONG, s), FACING, g)


# Greek blocks along the baseline (two ranks, ~110 m deep). Centre `s` of each.
G_DEPTH = 110
G = {
    "athenians": (825, 1650),
    "greek-centre": (1950, 520),
    "aeginetans": (2440, 380),
    "spartans": (2930, 520),
}
# Persian blocks (three ranks, ~190 m deep), same frame.
P_DEPTH = 190
P = {
    "phoenicians": (1150, 1100),
    "persian-centre": (2175, 900),
    "carians": (2810, 280),
    "ionians": (3400, 800),
}


def g_pos(uid: str, g: float, **extra) -> dict:
    s, w = G[uid]
    return {"at": line(s, g), "facing": FACING, "width": w, "depth": G_DEPTH, **extra}


def p_pos(uid: str, g: float, ds: float = 0.0, **extra) -> dict:
    s, w = P[uid]
    return {"at": line(s + ds, g), "facing": P_FACING, "width": w, "depth": P_DEPTH, **extra}


# ── fixed positions off the battle line ───────────────────────────────────

# Beached / at anchor before the battle.
G_BEACH = {
    "athenians": {"at": [23.542168, 37.957814], "facing": 20, "width": 1400, "depth": 100},
    "corinthians": {"at": at(-2950, 470), "facing": 90, "width": 380, "depth": 110},
    "greek-centre": {"at": [23.5440, 37.9489], "facing": 0, "width": 500, "depth": 110},
    "aeginetans": {"at": at(-500, -1080), "facing": 8, "width": 380, "depth": 110},
    "spartans": {"at": at(200, -1060), "facing": 8, "width": 520, "depth": 110},
}
CORINTH_LINE = {"at": at(-2350, 1150), "facing": 70, "width": 380, "depth": 110}
CORINTH_NORTH = {"at": at(-1650, 3600), "facing": 0, "width": 200, "depth": 260}

PHALERUM_BAY = {
    "phoenicians": {"at": [23.6720, 37.9300], "facing": 205, "width": 1000, "depth": 190},
    "persian-centre": {"at": [23.682214, 37.927618], "facing": 215, "width": 900, "depth": 190},
    "egyptians": {"at": [23.689909, 37.92253], "facing": 240, "width": 900, "depth": 190},
    "ionians": {"at": [23.6700, 37.9240], "facing": 205, "width": 800, "depth": 190},
    "carians": {"at": [23.6800, 37.9225], "facing": 215, "width": 280, "depth": 190},
}
PERSIAN_BASE = [23.6915, 37.9335]
# Round the south of the Piraeus headland, westbound (reverse it to go home).
ROUND_PIRAEUS = [[23.6550, 37.9190], [23.6320, 37.9160], [23.6160, 37.9250]]

# Night stations round Psyttaleia (west, mouth, east) and in the Megara channel.
NIGHT = {
    "ionians": {"at": at(650, -1880), "facing": 340, "width": 800, "depth": 190},
    "carians": {"at": at(1250, -2150), "facing": 330, "width": 280, "depth": 190},
    "persian-centre": {"at": at(2150, -1150), "facing": 340, "width": 900, "depth": 190},
    "phoenicians": {"at": at(3250, -1320), "facing": 315, "width": 1000, "depth": 190},
}
MEGARA_CHANNEL = {"at": [23.4340, 37.9700], "facing": 330, "width": 800, "depth": 220}


def _round_salamis() -> list[list[float]]:
    """The Egyptian squadron's night row from Phalerum round the south of Salamis."""
    return path(
        PHALERUM_BAY["egyptians"]["at"],
        [23.6300, 37.9050],
        [23.5600, 37.8870],
        [23.4900, 37.8580],
        [23.4300, 37.8570],
        [23.3920, 37.8850],
        [23.3880, 37.9300],
        [23.4050, 37.9580],
        [23.4320, 37.9620],
        MEGARA_CHANNEL["at"],
    )


def _phalerum_to(uid: str, target: list[float], via: list[list[float]] | None = None) -> list[list[float]]:
    return path(PHALERUM_BAY[uid]["at"], *(via or []), target)


def build() -> dict:
    # Greek line placements for each phase (g = metres forward of the baseline).
    g_form, g_back, g_strike = 0, -130, 60
    # Persian line: deployed, pressed in, in contact.
    p_deploy, p_press, p_contact = 430, 330, 240
    deploy_ds = {"phoenicians": 120, "persian-centre": 60, "carians": 30, "ionians": 0}

    athenian_push = line(G["athenians"][0] + 100, 245)
    # Artemisia's flight (Herodotus 8.87-88); where in the strait it happened is not known.
    artemisia_flight = line(3300, 700)
    calyndian_at = line(3480, 760)
    artemisia_ram = line(3450, 750)
    # Where the broken Persian squadrons are as the front collapses.
    centre_broken = line(2550, 470)
    carians_flight = line(3150, 560)
    phoenicians_aground = line(P["phoenicians"][0] + 200, 430)
    centre_wedge = line(1950, 330)

    # Where the beaten squadrons are by mid-afternoon (south of Piraeus) and at nightfall.
    off_piraeus = {
        "persian-centre": [23.6280, 37.9180],
        "carians": [23.6450, 37.9170],
        "ionians": [23.6150, 37.9250],
        "phoenicians": [23.6050, 37.9320],
    }
    phalerum_return = {
        "phoenicians": {"at": [23.6720, 37.9300], "facing": 205, "width": 700, "depth": 220},
        "persian-centre": {"at": [23.682083, 37.927471], "facing": 215, "width": 650, "depth": 220},
        "carians": {"at": [23.6800, 37.9225], "facing": 215, "width": 200, "depth": 160},
        "ionians": {"at": [23.6700, 37.9240], "facing": 205, "width": 600, "depth": 200},
    }

    strait_cam = {"center": at(-300, -350), "zoom": 13.1}

    doc: dict = {
        "schema": 2,
        "slug": "battle-of-salamis",
        "kind": "naval_battle",
        "entity": {"name": "Battle of Salamis", "wikidata": "Q178850"},
        "title": "Battle of Salamis",
        "date_label": "September 480 BC",
        "year": -480,
        "intro": (
            "By September 480 BC the Persian invasion of Greece under Xerxes had reached Attica. Thermopylae "
            "had fallen, the allied fleet had given up the straits of Artemisium, and Athens, emptied of its "
            "people, had been taken and burned. Roughly 370 triremes of the Greek alliance, more than half of "
            "them Athenian, lay on the beaches of Salamis, the island that closes the bay of Eleusis, while the "
            "larger Persian fleet of Phoenician, Egyptian, Cypriot, Cilician and Ionian Greek squadrons rode at "
            "Phalerum a few kilometres to the east. The Peloponnesian captains wanted to fall back on the "
            "Isthmus of Corinth; the Athenian Themistocles held out for a fight in the narrow channel between "
            "Salamis and the mainland, where Persian numbers and seamanship would count for less than the "
            "weight of the Greek ships and their armoured marines. A message he sent to the king convinced "
            "Xerxes that the Greeks were about to slip away, and the Persian fleet spent the night closing the "
            "exits before rowing into the strait at dawn."
        ),
        "outcome": (
            "Decisive Greek victory: the Persians lost perhaps 200 to 300 ships to the Greeks' 40, Xerxes "
            "returned to Asia with much of his army, and the invasion lost command of the sea."
        ),
        "uncertainty": (
            "The ancient accounts are brief and disagree, so this is one reconstruction. It follows Herodotus: "
            "the Greek line runs across the western end of the strait from St George's islet to the Kynosoura "
            "peninsula rather than inside the bay of Ambelaki, which at about 400 m wide could shelter the fleet "
            "(its anchorage was found there in 2017) but not hold a line of 300-plus ships. Diodorus's Egyptian "
            "detour round Salamis is disputed but shown. Fleet sizes are modern estimates (c. 370 Greek, perhaps "
            "600 to 800 Persian, not Herodotus's 1,207); blocks assume two Greek and three Persian ranks at "
            "about 17 to 25 m a ship. The coast is today's, less the modern quays at Perama, Keratsini and "
            "Piraeus. Proposed dates run from about 22 to 29 September."
        ),
        "sources": [
            {"title": "Herodotus, Histories 8.40–96", "kind": "primary"},
            {"title": "Aeschylus, The Persians 353–471", "kind": "primary"},
            {"title": "Diodorus Siculus, Library 11.17–19", "kind": "primary"},
            {"title": "Plutarch, Life of Themistocles 12–15", "kind": "primary"},
            {"title": "Battle of Salamis — Wikipedia", "url": "https://en.wikipedia.org/wiki/Battle_of_Salamis", "kind": "web"},
            {"title": "D. Potter, review of Wallinga, BMCR 2006.03.29", "url": "https://bmcr.brynmawr.edu/?p=25119", "kind": "web"},
            {"title": "The Naval Battle of Salamis — Hellenic Ministry of Culture, 2500 Years", "url": "https://2500years.culture.gov.gr/en/chapters/i-naumachia-tis-salaminas", "kind": "web"},
        ],
        "camera": {"center": at(800, -600), "zoom": 12.6, "bearing": 0},
        "sides": [
            {
                "id": "greeks",
                "name": "Greek allied fleet",
                "color": "#1d4ed8",
                "polity": {"name": "Hellenic League", "wikidata": "Q386893"},
                "commanders": [
                    {"name": "Themistocles", "wikidata": "Q179552", "role": "Athenian commander, architect of the battle"},
                    {"name": "Eurybiades", "wikidata": "Q499025", "role": "allied commander-in-chief (Sparta)"},
                    {"name": "Adeimantus", "wikidata": "Q353577", "role": "Corinthian commander"},
                    {"name": "Aristides", "wikidata": "Q294942", "role": "led the landing on Psyttaleia"},
                ],
                "strength": "c. 370 triremes (Herodotus: 378)",
                "losses": "c. 40 ships",
            },
            {
                "id": "persia",
                "name": "Persian fleet",
                "color": "#b91c1c",
                "polity": {"name": "Achaemenid Empire", "wikidata": "Q389688"},
                "commanders": [
                    {"name": "Xerxes I", "wikidata": "Q129165", "role": "king, watching from Mount Aigaleo"},
                    {"name": "Ariabignes", "wikidata": "Q2861160", "role": "admiral, killed in the battle"},
                    {"name": "Achaemenes", "wikidata": "Q561925", "role": "admiral of the Egyptian squadron"},
                    {"name": "Artemisia I of Caria", "wikidata": "Q232128", "role": "queen of Halicarnassus, Carian ships"},
                ],
                "strength": "c. 600–800 ships (Herodotus: 1,207)",
                "losses": "c. 200–300 ships",
            },
        ],
        "units": [
            {"id": "athenians", "side": "greeks", "kind": "warship", "label": "Athenians", "strength": "200 triremes", "strength_n": 200,
             "commander": "Themistocles", "note": "180 Athenian triremes and 20 more lent to crews from Chalcis"},
            {"id": "corinthians", "side": "greeks", "kind": "warship", "label": "Corinthians", "strength": "40 triremes", "strength_n": 40,
             "commander": "Adeimantus", "note": "Said by the Athenians to have fled north; the other Greeks denied it"},
            {"id": "greek-centre", "side": "greeks", "kind": "warship", "label": "Megarians & islanders", "strength": "c. 47 triremes",
             "note": "Megara 20, Eretria 7, Ambracia 7, Naxos 4, Leucas 3 and small island crews"},
            {"id": "aeginetans", "side": "greeks", "kind": "warship", "label": "Aeginetans", "strength": "30 triremes", "strength_n": 30,
             "note": "Judged the bravest of the Greeks that day"},
            {"id": "spartans", "side": "greeks", "kind": "warship", "label": "Spartans & Peloponnesians", "strength": "c. 49 triremes",
             "commander": "Eurybiades", "note": "Sparta 16, Sicyon 15, Epidaurus 10, Troezen 5, Hermione 3"},
            {"id": "hoplites", "side": "greeks", "kind": "heavy_infantry", "label": "Aristides' hoplites",
             "commander": "Aristides", "note": "Athenian hoplites posted along the Salamis shore"},
            {"id": "themistocles", "side": "greeks", "kind": "commander", "label": "Themistocles", "wikidata": "Q179552"},
            {"id": "eurybiades", "side": "greeks", "kind": "commander", "label": "Eurybiades", "wikidata": "Q499025"},
            {"id": "greek-base", "side": "greeks", "kind": "camp", "label": "Greek base, Salamis"},
            {"id": "phoenicians", "side": "persia", "kind": "warship", "label": "Phoenicians", "strength": "300 at the muster",
             "note": "The best squadrons of the fleet, from Sidon, Tyre and Arwad"},
            {"id": "persian-centre", "side": "persia", "kind": "warship", "label": "Cypriots, Cilicians & others",
             "strength": "330 at the muster", "note": "Cyprus 150, Cilicia 100, Lycia 50, Pamphylia 30"},
            {"id": "carians", "side": "persia", "kind": "warship", "label": "Carians & Artemisia", "strength": "c. 75 at the muster",
             "commander": "Artemisia", "note": "70 Carian ships, with Artemisia's five from Halicarnassus and nearby islands"},
            {"id": "ionians", "side": "persia", "kind": "warship", "label": "Ionians & Asian Greeks", "strength": "c. 300 at the muster",
             "note": "Ionians 100, Hellespontines 100, Aeolians 60, Dorians 30"},
            {"id": "egyptians", "side": "persia", "kind": "warship", "label": "Egyptians", "strength": "200 at the muster",
             "commander": "Achaemenes", "note": "Sent round Salamis to close the Megara channel (Diodorus)"},
            {"id": "artemisia", "side": "persia", "kind": "ship", "label": "Artemisia's ship", "commander": "Artemisia",
             "note": "Chased by the Athenian Ameinias, she escaped by ramming a ship of her own side"},
            {"id": "calyndian", "side": "persia", "kind": "ship", "label": "Calyndian ship",
             "note": "Carrying Damasithymus, king of Calynda; rammed and sunk by Artemisia (Herodotus 8.87)"},
            {"id": "psyttaleia-troops", "side": "persia", "kind": "infantry", "label": "Persian troops",
             "strength": "c. 400", "note": "Landed on Psyttaleia to kill or take Greeks washed ashore"},
            {"id": "xerxes", "side": "persia", "kind": "commander", "label": "Xerxes", "wikidata": "Q129165"},
            {"id": "persian-base", "side": "persia", "kind": "camp", "label": "Persian base, Phalerum"},
        ],
        "terrain": [
            {"id": "psyttaleia", "kind": "island", "label": "Psyttaleia", "area": PSYTTALEIA_OUTLINE},
            {"id": "st-george", "kind": "island", "label": "St George's islet", "area": ST_GEORGE},
            {"id": "kynosoura", "kind": "label", "label": "Kynosoura", "at": [23.5640, 37.9447]},
            {"id": "salamis-town", "kind": "town", "label": "Salamis (old town)", "at": [23.5340, 37.9515]},
            {"id": "ambelaki-bay", "kind": "label", "label": "Bay of Ambelaki", "at": [23.5440, 37.9480]},
            {"id": "salamis-island", "kind": "label", "label": "SALAMIS", "at": [23.4700, 37.9180]},
            {"id": "sea", "kind": "sea", "label": "Sea, 480 BC (approx.)", "area": sea_area(), "conjectural": True},
            {"id": "megara-water", "kind": "sea", "area": ellipse(MEGARA_CHANNEL["at"], 450, 250, rotate=-30), "conjectural": True},
            {"id": "aigaleo", "kind": "ridge", "label": "Mount Aigaleo",
             "line": path((23.5638, 37.9733), (23.5766, 37.9713), (23.5895, 37.9685), (23.6126, 37.9765), (23.6195, 37.9971))},
            {"id": "attic-shore", "kind": "coast", "label": "Attic shore, 480 BC (approx.)", "line": ATTIC_SHORE},
            {"id": "piraeus", "kind": "label", "label": "Piraeus (Munychia)", "at": list(MUNYCHIA)},
            {"id": "phalerum", "kind": "town", "label": "Phalerum", "at": list(PHALERUM)},
            {"id": "athens", "kind": "town", "label": "Athens (sacked)", "at": list(ATHENS)},
            {"id": "eleusis", "kind": "town", "label": "Eleusis", "at": list(ELEUSIS)},
            {"id": "megara-channel", "kind": "label", "label": "Channel to Megara", "at": [23.4180, 37.9790]},
        ],
        "steps": [],
    }

    steps = doc["steps"]

    # 1 ── the fleets at Salamis and Phalerum
    steps.append({
        "id": "two-shores",
        "title": "Two fleets, two shores",
        "time": "Late September 480 BC",
        "narrative": (
            "After Artemisium the Greek fleet rowed south to Salamis to cover the evacuation of Athens and drew "
            "its ships up on the island's east coast, around the bay of Ambelaki below the old town of Salamis. "
            "Xerxes' army marched into the empty city and burned the Acropolis, and his fleet, refitted after "
            "the storms and fighting off Euboea, anchored in the open bay of Phalerum. In the allied council "
            "the Peloponnesians pressed to withdraw to the Isthmus, where their army was walling the road. "
            "Themistocles argued that in open water the Greeks would be beaten ship by ship, and that only in "
            "the narrows of Salamis could they fight on equal terms."
        ),
        "camera": {"center": [23.6220, 37.9440], "zoom": 11.05},
        "positions": {
            **{uid: dict(pl) for uid, pl in G_BEACH.items()},
            "themistocles": {"with": "athenians"},
            "eurybiades": {"with": "spartans"},
            "greek-base": {"at": [23.5370, 37.9488]},
            "hoplites": {"at": at(-900, -1330), "facing": 20, "width": 250, "depth": 40},
            **{uid: dict(pl) for uid, pl in PHALERUM_BAY.items()},
            "persian-base": {"at": PERSIAN_BASE},
            "xerxes": {"with": "persian-base"},
        },
        "notes": [{"at": list(ATHENS), "text": "Athens taken and burned", "kind": "event"}],
    })

    # 2 ── Sicinnus
    sicinnus = path([23.5460, 37.9505], [23.5750, 37.9510], [23.6000, 37.9380], *ROUND_PIRAEUS[::-1], [23.6800, 37.9330])
    steps.append({
        "id": "sicinnus",
        "title": "Themistocles' message to the king",
        "time": "Evening before the battle",
        "narrative": (
            "With the allies still quarrelling, Themistocles sent Sicinnus, a slave who tutored his sons, across "
            "by boat to the Persian camp. The message said that Themistocles secretly wished the king well, that the "
            "Greeks were at odds and meant to escape during the night, and that the Persians had only to close "
            "the exits to destroy them. Xerxes, eager to finish the campaign before winter, believed it. At an "
            "earlier council at Phalerum Artemisia, queen of Halicarnassus, had warned him that he could win "
            "without risking a sea battle at all; the king and his other advisers chose to fight."
        ),
        "camera": {"center": [23.6200, 37.9420], "zoom": 11.35},
        "light": "dusk",
        "moves": [{"side": "greeks", "type": "march", "path": sicinnus, "label": "Sicinnus' boat"}],
        "notes": [
            {"at": [23.6800, 37.9330], "text": "\"The Greeks will flee tonight\"", "kind": "event"},
            {"at": [23.5420, 37.9530], "text": "Council: Peloponnesians want the Isthmus", "kind": "label"},
        ],
    })

    # 3 ── the night blockade
    night_moves = [
        {"unit": "phoenicians", "type": "march", "path": _phalerum_to("phoenicians", NIGHT["phoenicians"]["at"], ROUND_PIRAEUS), "orient": "path"},
        {"unit": "persian-centre", "type": "march", "path": _phalerum_to("persian-centre", NIGHT["persian-centre"]["at"], [*ROUND_PIRAEUS[:2], at(3000, -1950)]), "orient": "path"},
        {"unit": "carians", "type": "march", "path": _phalerum_to("carians", NIGHT["carians"]["at"], [*ROUND_PIRAEUS[:2], at(2600, -2600)]), "orient": "path"},
        {"unit": "ionians", "type": "march", "path": _phalerum_to("ionians", NIGHT["ionians"]["at"], [*ROUND_PIRAEUS[:2], at(1600, -2700)]), "orient": "path"},
        {"unit": "egyptians", "type": "march", "path": _round_salamis(), "label": "Egyptians round Salamis", "orient": "path", "conjectural": True},
        {"unit": "psyttaleia-troops", "type": "landing", "path": path([23.6650, 37.9290], *ROUND_PIRAEUS[:2], at(2700, -2000), PSYTTALEIA)},
        # The cordon across the eastern exits, from off Kynosoura past Psyttaleia to the Attic shore.
        {"side": "persia", "type": "blockade", "path": path(at(1350, -1300), at(2150, -1350), at(3550, -1250))},
    ]
    steps.append({
        "id": "night-blockade",
        "title": "The exits are closed by night",
        "time": "Night",
        "narrative": (
            "After dark the Persian squadrons rowed out of Phalerum and took station across the eastern exits "
            "of the strait, on either side of the islet of Psyttaleia, where some 400 picked soldiers were "
            "landed to kill or capture any Greeks cast ashore there. According to Diodorus the Egyptian "
            "squadron was sent right round Salamis to block the western channel by Megara, so that no ship "
            "could slip away toward the Isthmus. The Persian crews spent the whole night at the oars. Before "
            "dawn Aristides crossed from Aegina with the news that the Greeks were surrounded: there was no "
            "longer any choice but to fight."
        ),
        "light": "night",
        "positions": {
            **{uid: dict(pl) for uid, pl in NIGHT.items()},
            "egyptians": dict(MEGARA_CHANNEL),
            "psyttaleia-troops": {"at": list(PSYTTALEIA), "facing": 300, "width": 260, "depth": 90},
        },
        "moves": night_moves,
        "notes": [{"at": [23.5395, 37.9475], "text": "Aristides: \"we are surrounded\"", "kind": "event"}],
    })

    # 4 ── dawn: the Greek line forms
    steps.append({
        "id": "greek-line",
        "title": "The Greeks form their line",
        "time": "Dawn",
        "narrative": (
            "At first light Themistocles spoke to the marines and the crews launched from the beaches of "
            "Ambelaki and Paloukia. The fleet formed in two ranks across the western end of the strait, from "
            "St George's islet to the Kynosoura peninsula: the Athenians on the left toward Eleusis, the "
            "Megarians and island crews in the centre, then the Aeginetans, and the Spartans under Eurybiades, "
            "the allied commander, on the right. The Corinthians lay beyond the Athenian wing, near the channel "
            "to the north. Across the water Xerxes took his seat on the lower slope of Mount Aigaleo, with "
            "scribes beside him to record which captains fought well."
        ),
        "camera": {"center": at(600, -500), "zoom": 12.85},
        "light": "dawn",
        "positions": {
            "egyptians": {"frame": False},
            "persian-base": {"frame": False},
            "athenians": g_pos("athenians", g_form),
            "greek-centre": g_pos("greek-centre", g_form),
            "aeginetans": g_pos("aeginetans", g_form),
            "spartans": g_pos("spartans", g_form),
            "corinthians": dict(CORINTH_LINE),
            "xerxes": {"at": list(XERXES_SEAT)},
        },
        "moves": [
            {"unit": "athenians", "type": "advance", "path": path(G_BEACH["athenians"]["at"], line(G["athenians"][0], g_form))},
            {"unit": "greek-centre", "type": "advance", "path": path(G_BEACH["greek-centre"]["at"], at(-1100, -900), line(G["greek-centre"][0], g_form))},
            {"unit": "aeginetans", "type": "advance", "path": path(G_BEACH["aeginetans"]["at"], line(G["aeginetans"][0], g_form))},
            {"unit": "spartans", "type": "advance", "path": path(G_BEACH["spartans"]["at"], line(G["spartans"][0], g_form))},
            {"unit": "corinthians", "type": "advance", "path": path(G_BEACH["corinthians"]["at"], at(-2700, 950), CORINTH_LINE["at"]), "orient": "path"},
            {"unit": "xerxes", "type": "march", "path": path(PERSIAN_BASE, [23.6400, 37.9600], [23.5800, 37.9700], XERXES_SEAT)},
        ],
        "notes": [{"at": at(-700, -350), "text": "Greek paean echoes across the strait", "kind": "event"}],
        "focus": ["athenians", "greek-centre", "aeginetans", "spartans"],
    })

    # 5 ── the Persians row in; the Corinthians sail north
    deployed = {uid: line(P[uid][0] + deploy_ds[uid], p_deploy) for uid in P}
    persian_in = {
        "phoenicians": path(NIGHT["phoenicians"]["at"], at(2300, -900), at(1000, -520), at(200, 80), deployed["phoenicians"]),
        "persian-centre": path(NIGHT["persian-centre"]["at"], at(1500, -760), deployed["persian-centre"]),
        "carians": path(NIGHT["carians"]["at"], at(1600, -1500), at(1650, -1000), deployed["carians"]),
        "ionians": path(NIGHT["ionians"]["at"], at(1450, -1500), at(1700, -1150), deployed["ionians"]),
    }
    steps.append({
        "id": "persians-enter",
        "title": "The Persians row into the strait",
        "time": "Early morning",
        "narrative": (
            "The Persian squadrons came in past the tail of Kynosoura and up along the Attic shore, the "
            "Phoenicians leading toward Eleusis to form the right of the line, Cypriots, Cilicians and other "
            "contingents in the centre, and the Carians and Ionian Greeks on the left, opposite the Spartans. "
            "In Aeschylus, who is said to have fought there, the Persians hear the Greek battle hymn ringing "
            "off the rocks before they see a single ship. As the fight was about to open, the Corinthians "
            "hoisted their sails and stood away north up the channel. The Athenians later called it flight; the "
            "other Greeks denied it, and some modern historians think they went to watch for the Egyptians "
            "coming round the island."
        ),
        "camera": {"center": at(-200, 1000), "zoom": 12.4},
        "light": "day",
        "positions": {
            uid: p_pos(uid, p_deploy, ds=deploy_ds[uid]) for uid in P
        } | {"corinthians": dict(CORINTH_NORTH)},
        "moves": [{"unit": uid, "type": "advance", "path": p, "orient": "path"} for uid, p in persian_in.items()]
        + [{"unit": "corinthians", "type": "feint", "path": path(CORINTH_LINE["at"], at(-1500, 2200), CORINTH_NORTH["at"]), "label": "Corinthians sail north", "orient": "path"}],
        "focus": list(P),
    })

    # 6 ── the Greeks back water; the Persians crowd in
    steps.append({
        "id": "backing-water",
        "title": "The Greeks back water",
        "time": "Morning",
        "narrative": (
            "Instead of charging, the Greek line backed water toward the Salamis shore and drew the Persians "
            "deeper into the narrows. Three ranks deep and still arriving from the mouth, the Persian ships "
            "bunched as the channel closed around them and their lines lost order. Plutarch says Themistocles "
            "was waiting for the morning breeze, which raised a swell in the strait that rolled the tall "
            "Persian ships but hardly troubled the low Greek hulls. Then one ship shot out of the Greek line "
            "and rammed the nearest enemy: the Athenians said it was Ameinias of Pallene, the Aeginetans "
            "claimed it for one of theirs."
        ),
        "camera": strait_cam,
        "positions": {
            **{uid: g_pos(uid, g_back) for uid in G},
            **{uid: p_pos(uid, p_press, state="wavering") for uid in P},
            "corinthians": {"frame": False},  # away up the northern channel until evening
        },
        "moves": [
            {"unit": uid, "type": "back_water", "path": path(line(G[uid][0], g_form), line(G[uid][0], g_back))} for uid in G
        ] + [
            {"unit": uid, "type": "advance", "path": path(deployed[uid], line(P[uid][0], p_press))} for uid in P
        ] + [
            {"side": "greeks", "type": "ram", "path": path(line(1500, g_back + 60), line(1500, p_press - P_DEPTH / 2)), "label": "Ameinias"},
        ],
        "notes": [{"at": line(1500, 120), "text": "Ameinias rams first", "kind": "clash"}],
    })

    # 7 ── the Greek attack
    steps.append({
        "id": "greek-attack",
        "title": "The Greek line strikes",
        "time": "Morning",
        "narrative": (
            "The whole Greek line followed and drove into the disordered Persian front. On the left the "
            "Athenians fell on the Phoenicians, and early in the fighting the Persian admiral Ariabignes, a "
            "brother of Xerxes, was killed as he tried to board an Athenian ship. Packed too close to turn, "
            "the Persian ships were rammed in the side or boarded by the Greeks' armoured hoplite marines, and "
            "crews who could not swim drowned in great numbers. On the right the Spartans and Aeginetans met "
            "the Ionians, some of whom fought hard under the eyes of their king."
        ),
        "camera": strait_cam,
        "positions": {
            **{uid: g_pos(uid, g_strike, state="engaged") for uid in G},
            **{uid: p_pos(uid, p_contact, state="engaged") for uid in P},
        },
        "moves": [
            {"unit": uid, "type": "ram", "path": path(line(G[uid][0], g_back), line(G[uid][0], g_strike))} for uid in G
        ],
        "notes": [
            {"at": line(1000, 360), "text": "Ariabignes killed", "kind": "death"},
            {"at": line(2900, 380), "text": "Spartans and Aeginetans meet the Ionians", "kind": "clash"},
        ],
        "focus": ["athenians", "phoenicians"],
    })

    # 8 ── the Persian front collapses
    steps.append({
        "id": "persian-collapse",
        "title": "The Persian front collapses",
        "time": "Late morning",
        "narrative": (
            "The Phoenicians, leaderless and pinned against the Attic shore, broke first, and many of their "
            "ships ran aground below the king's seat. Ships in the Persian front that turned to escape fouled "
            "the rear ranks still pushing forward to be seen by Xerxes, and a Greek thrust split the centre. "
            "In the turmoil Artemisia, chased by Ameinias, rammed and sank a ship of her own side from Calynda; "
            "the Athenian took her for a friend and let her go, while Xerxes, watching, thought she had sunk a "
            "Greek and remarked that his men had become women and his women men."
        ),
        "camera": strait_cam,
        "positions": {
            "athenians": {"at": athenian_push, "state": "engaged"},
            "greek-centre": {"at": centre_wedge, "shape": "wedge", "width": 380, "depth": 380, "state": "engaged"},
            "aeginetans": g_pos("aeginetans", g_strike + 120, state="engaged"),
            "spartans": g_pos("spartans", g_strike + 80, state="engaged"),
            "phoenicians": {"at": phoenicians_aground, "width": 900, "depth": 230, "state": "routed"},
            "persian-centre": {"at": centre_broken, "state": "wavering"},
            "carians": {"at": carians_flight, "facing": ALONG, "state": "routed"},
            "ionians": p_pos("ionians", p_contact + 60, state="engaged"),
            "artemisia": {"from": "carians", "at": artemisia_flight, "facing": ALONG, "conjectural": True},
            "calyndian": {"at": calyndian_at, "facing": ALONG, "conjectural": True},
        },
        "moves": [
            {"unit": "athenians", "type": "attack", "path": path(line(G["athenians"][0], g_strike), athenian_push)},
            {"unit": "greek-centre", "type": "charge", "path": path(line(G["greek-centre"][0], g_strike), centre_wedge)},
            {"unit": "phoenicians", "type": "rout", "path": path(line(P["phoenicians"][0], p_contact), phoenicians_aground)},
            {"unit": "carians", "type": "retreat", "path": path(line(P["carians"][0], p_contact), carians_flight)},
            {"unit": "persian-centre", "type": "retreat", "path": path(line(P["persian-centre"][0], p_contact), centre_broken)},
            {"unit": "artemisia", "type": "retreat", "path": path(line(P["carians"][0], p_contact), artemisia_flight), "conjectural": True},
        ],
        "beats": [
            {
                "label": "Artemisia, chased by Ameinias, rams one of her own side",
                "positions": {"artemisia": {"at": artemisia_ram}, "calyndian": {"state": "sunk"}},
                "moves": [{"unit": "artemisia", "type": "ram", "path": path(artemisia_flight, artemisia_ram), "conjectural": True}],
                "notes": [{"at": line(3480, 840), "text": "Artemisia sinks a Calyndian ship", "kind": "event"}],
            },
        ],
        "notes": [
            {"at": line(1500, 650), "text": "Phoenician ships run aground", "kind": "event"},
        ],
        "focus": ["phoenicians", "greek-centre", "carians"],
    })

    # 9 ── the rout and the Aeginetan ambush
    rout_targets = {
        "persian-centre": at(2700, -1050),
        "carians": at(3350, -1450),
        "ionians": at(1950, -1050),
        "phoenicians": at(900, 0),
    }
    aeg_ambush = at(1500, -1300)
    athenians_chase = line(1900, 220)
    centre_chase = line(2500, 260)
    spartans_chase = line(3200, 120)
    steps.append({
        "id": "aeginetan-ambush",
        "title": "The Aeginetans close the exit",
        "time": "Afternoon",
        "narrative": (
            "The beaten Persian fleet streamed back toward Phalerum, and every ship had to pass the mouth of "
            "the strait by Kynosoura. There the Aeginetans lay in wait and caught the ships coming out, while "
            "the Athenians pressed on those still fighting or trying to turn inside the strait. Herodotus has "
            "the Aeginetan captain Polycritus ramming a Sidonian ship and shouting across to Themistocles, "
            "mocking the Athenian charge that Aegina had sided with Persia. Wreckage drifted down the Attic "
            "coast as far as Cape Kolias."
        ),
        "camera": {"center": at(1300, -650), "zoom": 12.9},
        "positions": {
            "aeginetans": {"at": aeg_ambush, "facing": 45, "width": 380, "depth": 110, "state": "engaged"},
            "athenians": {"at": athenians_chase, "facing": ALONG, "width": 700, "depth": 250, "state": "engaged"},
            "greek-centre": {"at": centre_chase, "facing": ALONG, "shape": "block", "width": 450, "depth": 200, "state": "engaged"},
            "spartans": {"at": spartans_chase, "facing": 70, "state": "engaged"},
            "persian-centre": {"at": rout_targets["persian-centre"], "facing": 115, "width": 650, "depth": 220, "state": "routed"},
            "carians": {"at": rout_targets["carians"], "facing": 140, "width": 220, "depth": 160, "state": "routed"},
            "ionians": {"at": rout_targets["ionians"], "facing": 110, "width": 600, "depth": 200, "state": "routed"},
            "phoenicians": {"at": rout_targets["phoenicians"], "facing": 100, "width": 600, "depth": 230, "state": "routed"},
            "artemisia": {"into": "carians"},
        },
        "moves": [
            {"unit": "persian-centre", "type": "rout", "path": path(centre_broken, at(1500, -650), rout_targets["persian-centre"]), "orient": "path"},
            {"unit": "carians", "type": "rout", "path": path(carians_flight, at(2200, -950), rout_targets["carians"]), "orient": "path"},
            {"unit": "ionians", "type": "rout", "path": path(line(P["ionians"][0], p_contact + 60), rout_targets["ionians"])},
            {"unit": "phoenicians", "type": "rout", "path": path(phoenicians_aground, at(0, 120), rout_targets["phoenicians"]), "orient": "path"},
            {"unit": "aeginetans", "type": "flank", "path": path(line(G["aeginetans"][0], g_strike + 120), at(1100, -900), aeg_ambush)},
            {"unit": "athenians", "type": "pursuit", "path": path(athenian_push, athenians_chase)},
            {"unit": "greek-centre", "type": "pursuit", "path": path(centre_wedge, centre_chase)},
            {"unit": "spartans", "type": "pursuit", "path": path(line(G["spartans"][0], g_strike + 80), spartans_chase)},
        ],
        "notes": [{"at": at(1750, -1200), "text": "Aeginetan ambush at the mouth", "kind": "clash"}],
        "focus": ["aeginetans"],
    })

    # 10 ── Psyttaleia
    hoplites_land = dest(PSYTTALEIA, 300, 150)
    steps.append({
        "id": "psyttaleia",
        "title": "Aristides clears Psyttaleia",
        "time": "Afternoon",
        "narrative": (
            "Once the sea fight had turned, Aristides took a body of Athenian hoplites who had been posted "
            "along the shore of Salamis, ferried them across to Psyttaleia and killed the whole Persian "
            "detachment on the island. Aeschylus makes this slaughter of picked men, in full view of the king "
            "on the mainland, the bitterest moment of the day for Xerxes. The Persian ships that had escaped "
            "the strait were by now rowing for Phalerum."
        ),
        "camera": {"center": at(1500, -1550), "zoom": 13.3},
        "positions": {
            "hoplites": {"at": hoplites_land, "facing": 120, "width": 250, "depth": 40, "state": "engaged"},
            **{uid: {"state": "ready"} for uid in G},
            "psyttaleia-troops": {"state": "destroyed"},
            "calyndian": {"state": "hidden"},
            **{uid: {"at": off_piraeus[uid], "facing": 120} for uid in off_piraeus},
        },
        "moves": [
            {"unit": "hoplites", "type": "landing", "path": path(at(-900, -1330), at(0, -1700), at(1000, -1900), hoplites_land), "label": "Aristides crosses"},
        ] + [
            {"unit": uid, "type": "rout", "path": path(rout_targets[uid], *([at(2300, -950), at(3200, -1300)] if uid in ("phoenicians", "ionians") else [at(3200, -1300)]), off_piraeus[uid]), "orient": "path"}
            for uid in off_piraeus
        ],
        "notes": [{"at": dest(PSYTTALEIA, 160, 300), "text": "Persian garrison wiped out", "kind": "death"}],
        "focus": ["hoplites", "psyttaleia-troops"],
    })

    # 11 ── withdrawal to Phalerum
    steps.append({
        "id": "withdrawal",
        "title": "Back to Phalerum",
        "time": "Evening",
        "narrative": (
            "The surviving Persian ships gathered at Phalerum under the shelter of the army, while the Greeks "
            "towed what wrecks they could to Salamis and stood ready for a second attack that never came. The "
            "Corinthians returned to find the battle over. Xerxes began a causeway toward Salamis but soon "
            "gave it up; within days, fearing for his bridges over the Hellespont, he started for Asia with "
            "much of his army and left Mardonius to finish the war on land. The next summer the Greeks won at "
            "Plataea and Mycale."
        ),
        "camera": {"center": [23.6150, 37.9450], "zoom": 11.4},
        "light": "dusk",
        "positions": {
            **{uid: {**pl, "state": "routed"} for uid, pl in phalerum_return.items()},
            "athenians": {"at": line(900, 120), "state": "ready"},
            "greek-centre": {"at": line(1950, 60), "state": "ready"},
            "aeginetans": {"at": line(2600, 60), "facing": FACING, "state": "ready"},
            "spartans": {"at": line(3100, 0), "state": "ready"},
            "corinthians": {**CORINTH_LINE, "frame": True},
            "xerxes": {"with": "persian-base"},
            "hoplites": {"state": "hidden"},
        },
        "moves": [
            {"unit": uid, "type": "retreat", "path": path(off_piraeus[uid], [23.6400, 37.9150], [23.6600, 37.9200], pl["at"]), "orient": "path"}
            for uid, pl in phalerum_return.items()
        ] + [
            {"unit": "corinthians", "type": "march", "path": path(CORINTH_NORTH["at"], at(-1500, 2200), CORINTH_LINE["at"]), "label": "Corinthians return"},
            {"unit": "xerxes", "type": "march", "path": path(XERXES_SEAT, [23.6400, 37.9600], PERSIAN_BASE)},
        ],
        "notes": [{"at": [23.6000, 37.9150], "text": "Wreckage drifts toward Cape Kolias", "kind": "event"}],
    })

    return doc
