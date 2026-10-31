"""Battle of Gaugamela, 1 October 331 BC — map story builder.

Reconstruction
--------------
Site: the northern identification on the Navkur plain beside Tell Gomel
(Gir-e Gomel), whose name preserves "Gaugamela", with the Macedonian camp on
the hills west of Mahad (Marciak et al., Iraq 83, 2021; Pirowski, Marciak &
Sobiech, Remote Sensing 13, 2021). SRTM shows the plain between the Mahad hills
and the Gomel river is almost dead flat (343-357 m); the hills rise ~80 m above
it about 5.5-6 km north-west of the line, matching Arrian's 30 stades, and the
ground starts to climb toward Zilkan and Jebel Maqlub south-west of the Persian
left, which is where Alexander's march to the right was heading.

Frame: everything is placed in metres from PC (the Persian centre) with
`P(u, v)`: `v` runs from the Persian line toward the Macedonians (bearing 310,
toward the Mahad hills), `u` runs along the lines toward bearing 220 (the
Persian left = the Macedonian right). Persians face 310, Macedonians 130.

Order of battle: Arrian 3.11-12 (Darius's captured written order and
Alexander's array). Initial alignment follows Arrian 3.13.1: Darius's own
station stood opposite Alexander's royal squadron, so the Macedonian army is
offset toward the Persian right and Bessus's wing overlaps it by ~2.5 km.

Sizes: phalanx ~1 m per file, 16 deep; cavalry ~1.2 m per horse with
intervals; the Persian line ~6 km (Livius). Unit strengths are modern
estimates or are left qualitative where nobody knows.

Coordinates of rivers were taken once from OSM (Nominatim "Gomel Su" and
"نهر الخازر"), clipped and simplified; landmarks from Nominatim and the
Remote Sensing paper's site map.
"""

from __future__ import annotations

from pipeline.map_stories.geo import bearing, ellipse, rel

SLUG = "battle-of-gaugamela"

#: Persian centre: where Darius stood, on the plain ~1 km west of Girfaqir
#: and ~2.5 km west-north-west of Tell Gomel.
PC = (43.445, 36.592)
PF = 310  # Persian facing
MF = 130  # Macedonian facing


def P(u: float, v: float) -> list[float]:
    """A point `u` m along the lines toward the Persian left (bearing 220) and
    `v` m from the Persian line toward the Macedonian side (bearing 310)."""
    return rel(PC, PF, ahead=v, right=-u)


def path(*uv: tuple[float, float]) -> list[list[float]]:
    return [P(u, v) for u, v in uv]


def toward(a: tuple[float, float], b: tuple[float, float]) -> int:
    """Compass bearing from frame point a to frame point b."""
    return round(bearing(P(*a), P(*b)))


def blk(u: float, v: float, facing: float | None = None, **kw) -> dict:
    out: dict = {"at": P(u, v)}
    if facing is not None:
        out["facing"] = round(facing) % 360
    out.update(kw)
    return out


def mv(unit: str, kind: str, *uv: tuple[float, float], label: str | None = None) -> dict:
    out = {"unit": unit, "type": kind, "path": path(*uv)}
    if label:
        out["label"] = label
    return out


def note(u: float, v: float, text: str, kind: str = "event") -> dict:
    return {"at": P(u, v), "text": text, "kind": kind}


# ── Macedonian line geometry ──────────────────────────────────────────────
# Front line relative to the Companions' centre (U, V). Right flank angled
# back 45 degrees (facing MF+45), left flank angled back (facing MF-45).


def mac_front(U: float, V: float) -> dict[str, tuple[float, float]]:
    return {
        "companions": (U, V),
        "screen": (U, V - 90),
        "hypaspists": (U - 445, V),
        "phalanx-right": (U - 812, V),
        "phalanx-left": (U - 1125, V),
        "thessalians": (U - 1600, V),
        "left-flank": (U - 2147, V + 177),
        "right-flank": (U + 557, V + 212),
        "aretes": (U + 437, V - 64),
        "ariston": (U + 621, V + 120),
        "menidas": (U + 699, V - 142),
        "rear-line": (U - 600, V + 380),
    }


MAC_SIZE = {
    "companions": {"width": 650, "depth": 50, "facing": MF},
    "screen": {"width": 600, "depth": 25, "facing": MF},
    "hypaspists": {"width": 300, "depth": 30, "facing": MF},
    "phalanx-right": {"width": 375, "depth": 30, "facing": MF},
    "phalanx-left": {"width": 190, "depth": 30, "facing": MF},
    "thessalians": {"width": 700, "depth": 50, "facing": MF},
    "left-flank": {"width": 500, "depth": 30, "facing": MF - 45},
    "right-flank": {"width": 600, "depth": 25, "facing": MF + 45},
    "aretes": {"width": 240, "depth": 30, "facing": MF + 45},
    "ariston": {"width": 240, "depth": 30, "facing": MF + 45},
    "menidas": {"width": 220, "depth": 30, "facing": MF + 45},
    "rear-line": {"width": 1100, "depth": 24, "facing": MF},
}


def mac_deploy(U: float, V: float, sized: bool) -> dict[str, dict]:
    out = {}
    for uid, (u, v) in mac_front(U, V).items():
        d = blk(u, v)
        if sized:
            d.update(MAC_SIZE[uid])
        out[uid] = d
    return out


# Positions used across steps.
U2, V2 = 100, 1700  # deployment: Companions opposite Darius
U3, V3 = 750, 1150  # after the oblique march to the right
F2 = mac_front(U2, V2)
F3 = mac_front(U3, V3)

CAMP_MAC = (-400, 5450)  # Macedonian camp on the lower slopes of the Mahad hills
BAGGAGE = (-600, 5150)
CAMP_PER = (-500, -1900)  # Persian camp by the Gomel, beside Tell Gomel

GOMEL = [[43.48095, 36.66747], [43.4842, 36.66555], [43.48282, 36.66223], [43.47716, 36.66269], [43.47653, 36.6589], [43.47892, 36.65719], [43.4805, 36.65272], [43.47575, 36.65062], [43.47872, 36.64835], [43.47409, 36.64362], [43.47309, 36.64062], [43.47474, 36.62929], [43.47739, 36.62666], [43.47451, 36.62267], [43.47857, 36.61866], [43.47343, 36.6116], [43.47469, 36.60376], [43.47719, 36.6009], [43.47506, 36.59602], [43.47953, 36.59375], [43.47989, 36.58909], [43.47731, 36.58378], [43.48539, 36.58174], [43.48198, 36.57585], [43.48771, 36.57339], [43.48691, 36.56815], [43.48976, 36.56172], [43.49716, 36.55803], [43.5033, 36.55347]]
KHAZIR = [[43.5753, 36.64366], [43.56282, 36.63958], [43.55771, 36.62965], [43.55299, 36.62657], [43.54985, 36.61465], [43.54362, 36.60982], [43.5419, 36.59962], [43.5425, 36.59005], [43.54395, 36.58393], [43.54054, 36.58238], [43.53804, 36.56956], [43.5334, 36.56301], [43.53701, 36.55476], [43.54034, 36.54403], [43.53477, 36.54237], [43.53467, 36.5303], [43.53182, 36.5225], [43.52457, 36.51847], [43.51664, 36.51646], [43.51219, 36.50894], [43.51148, 36.50253], [43.50456, 36.49323]]


def build() -> dict:
    sides = [
        {
            "id": "macedon",
            "name": "Macedonian and allied Greek army",
            "color": "#b91c1c",
            "polity": {"name": "Macedon", "wikidata": "Q83958"},
            "commanders": [
                {"name": "Alexander the Great", "wikidata": "Q8409", "role": "king, commander-in-chief and the right wing"},
                {"name": "Parmenion", "wikidata": "Q1230252", "role": "left wing"},
                {"name": "Philotas", "wikidata": "Q5973506", "role": "Companion cavalry"},
                {"name": "Craterus", "wikidata": "Q16190036", "role": "infantry of the left"},
                {"name": "Coenus", "wikidata": "Q21866993", "role": "phalanx battalion (wounded)"},
                {"name": "Polyperchon", "wikidata": "Q312008", "role": "phalanx battalion"},
            ],
            "strength": "c. 47,000 (c. 7,000 horse, c. 40,000 foot)",
            # Arrian 3.12: the allies beside the Macedonian core (drawn in the side colour).
            "contingents": [
                {"id": "greek-allies", "name": "Thessalian and Greek allies"},
                {"id": "balkan-allies", "name": "Thracians, Agrianians and Paeonians"},
                {"id": "mercenaries", "name": "Greek mercenaries"},
            ],
            "losses": "probably a few hundred to c. 1,500 killed; Arrian: c. 100 men and over 1,000 horses",
        },
        {
            "id": "persia",
            "name": "Achaemenid Persian army",
            "color": "#6d28d9",
            "polity": {"name": "Achaemenid Empire", "wikidata": "Q389688"},
            "commanders": [
                {"name": "Darius III", "wikidata": "Q102865", "role": "Great King, centre"},
                {"name": "Bessus", "wikidata": "Q296434", "role": "satrap of Bactria, left wing"},
                {"name": "Mazaeus", "wikidata": "Q561959", "role": "right wing"},
            ],
            "strength": "c. 50,000-120,000 (modern estimates), much of it cavalry; 200 scythed chariots, 15 elephants",
            # Arrian 3.11: the peoples of each wing (the king's own centre is drawn in the side colour).
            "contingents": [
                {"id": "eastern", "name": "Bessus's wing: Bactrians and the eastern peoples"},
                {"id": "western", "name": "Mazaeus's wing: Syrians, Medes and the northern peoples"},
                {"id": "greek-mercenaries", "name": "Greek mercenaries"},
            ],
            "losses": "unknown but very heavy; ancient claims run from 40,000 to 300,000",
        },
    ]

    units = [
        # Macedonians
        {"id": "alexander", "side": "macedon", "kind": "commander", "label": "Alexander", "wikidata": "Q8409"},
        {"id": "parmenion", "side": "macedon", "kind": "commander", "label": "Parmenion", "wikidata": "Q1230252"},
        {"id": "baggage", "side": "macedon", "kind": "baggage", "label": "Baggage & captives", "note": "Guarded by Thracian infantry; Darius's mother and family were held here"},
        {"id": "companions", "side": "macedon", "kind": "heavy_cavalry", "label": "Companion cavalry", "strength": "c. 1,800-2,000", "commander": "Philotas, under Alexander", "note": "Eight squadrons, the royal squadron under Cleitus nearest the flank"},
        {"id": "screen", "side": "macedon", "kind": "light_infantry", "label": "Javelinmen & archers", "strength": "c. 1,500", "commander": "Balacrus", "note": "Half the Agrianians and archers with Balacrus's javelinmen, posted to meet the chariots"},
        {"id": "hypaspists", "side": "macedon", "kind": "heavy_infantry", "label": "Hypaspists", "strength": "c. 3,000", "commander": "Nicanor, son of Parmenion"},
        {"id": "phalanx-right", "side": "macedon", "kind": "pikemen", "label": "Phalanx, four battalions", "strength": "c. 6,000", "commander": "Coenus, Perdiccas, Meleager, Polyperchon", "note": "Sarissa phalanx, about 16 deep"},
        {"id": "phalanx-left", "side": "macedon", "kind": "pikemen", "label": "Simmias & Craterus", "strength": "c. 3,000", "commander": "Simmias (for Amyntas) and Craterus", "note": "The two left battalions of the phalanx"},
        {"id": "thessalians", "side": "macedon", "kind": "heavy_cavalry", "label": "Thessalian & allied horse", "strength": "c. 2,500", "commander": "Philip son of Menelaus; Erigyius; under Parmenion", "note": "Thessalian squadrons, the Pharsalians round Parmenion, with the allied Greek horse", "contingent": "greek-allies"},
        {"id": "left-flank", "side": "macedon", "kind": "cavalry", "label": "Thracian & allied flank", "strength": "c. 3,000-4,000", "commander": "Sitalces, Coeranus, Agathon, Andromachus", "note": "Angled-back left flank: Thracian javelinmen, allied and Odrysian horse, mercenary horse in front", "contingent": "balkan-allies"},
        {"id": "right-flank", "side": "macedon", "kind": "light_infantry", "label": "Agrianians & mercenary foot", "strength": "c. 3,000", "commander": "Attalus, Brison, Cleander", "note": "Angled-back right flank: Agrianians, Macedonian archers and Cleander's veteran mercenaries", "contingent": "balkan-allies"},
        {"id": "aretes", "side": "macedon", "kind": "light_cavalry", "label": "Aretes' lancers", "strength": "c. 600-800", "commander": "Aretes", "note": "Prodromoi (scouts, armed with long lances)"},
        {"id": "ariston", "side": "macedon", "kind": "light_cavalry", "label": "Ariston's Paeonians", "strength": "a few hundred", "commander": "Ariston", "contingent": "balkan-allies"},
        {"id": "menidas", "side": "macedon", "kind": "cavalry", "label": "Menidas' mercenary horse", "strength": "c. 400-500", "commander": "Menidas", "note": "Ordered to take any flanking force in the flank", "contingent": "mercenaries"},
        {"id": "rear-line", "side": "macedon", "kind": "heavy_infantry", "label": "Reserve line (Greek foot)", "strength": "c. 10,000+", "note": "Greek allied and mercenary infantry, ordered to face about if the army was surrounded", "contingent": "greek-allies"},
        # Persians
        {"id": "darius", "side": "persia", "kind": "commander", "label": "Darius III", "wikidata": "Q102865"},
        {"id": "bessus", "side": "persia", "kind": "commander", "label": "Bessus", "wikidata": "Q296434"},
        {"id": "mazaeus", "side": "persia", "kind": "commander", "label": "Mazaeus"},
        {"id": "guard", "side": "persia", "kind": "heavy_infantry", "label": "Royal guard (apple-bearers)", "strength": "up to c. 10,000", "note": "Persian guard foot (the 'Immortals' of Greek writers) with the Kinsmen horse, Carians and Mardian archers"},
        {"id": "greeks-l", "side": "persia", "kind": "heavy_infantry", "label": "Greek mercenaries", "strength": "a few thousand in all", "note": "One of two divisions posted either side of Darius, facing the phalanx", "contingent": "greek-mercenaries"},
        {"id": "greeks-r", "side": "persia", "kind": "heavy_infantry", "label": "Greek mercenaries", "note": "The second division, on Darius's right", "contingent": "greek-mercenaries"},
        {"id": "chariots-left", "side": "persia", "kind": "chariots", "label": "Scythed chariots (100)", "strength": "100", "note": "Arrian: 100 before the left, 50 before Darius, 50 before the right wing (not drawn)"},
        {"id": "chariots-centre", "side": "persia", "kind": "chariots", "label": "Scythed chariots (50)", "strength": "50"},
        {"id": "elephants", "side": "persia", "kind": "elephants", "label": "Indian elephants (15)", "strength": "15", "note": "Listed in Darius's order but never mentioned in the fighting; captured in the camp"},
        {"id": "left-horse", "side": "persia", "kind": "cavalry", "label": "Persian & Cadusian horse", "note": "Horsemen of the left-centre (Persians, Susians, Cadusians)", "contingent": "eastern"},
        {"id": "left-foot", "side": "persia", "kind": "infantry", "label": "Persian & Susian foot", "note": "Arrian: Persians, horse and foot mixed, then Susians and Cadusians", "contingent": "eastern"},
        {"id": "bessus-horse", "side": "persia", "kind": "cavalry", "label": "Bactrian & Arachosian horse", "strength": "c. 8,000+", "commander": "Bessus", "note": "Bactrians with Dahae and Arachosians; Curtius gives Bessus 8,000 Bactrian horse", "contingent": "eastern"},
        {"id": "scythians", "side": "persia", "kind": "heavy_cavalry", "label": "Scythian & Bactrian horse", "strength": "c. 2,000+", "note": "Armoured Saca horsemen (horse and rider) and about 1,000 Bactrians, out in front of the left", "contingent": "eastern"},
        {"id": "indian-horse", "side": "persia", "kind": "cavalry", "label": "Indian & Persian horse", "strength": "a few thousand"},
        {"id": "levies", "side": "persia", "kind": "infantry", "label": "Babylonians & levies", "note": "Uxians, Babylonians, Red Sea peoples and Sitacenians, drawn up deep behind the centre"},
        {"id": "syrian-median", "side": "persia", "kind": "cavalry", "label": "Syrian & Median horse", "commander": "Mazaeus", "note": "Coele-Syrians, Mesopotamians and Medes", "contingent": "western"},
        {"id": "parthian-horse", "side": "persia", "kind": "cavalry", "label": "Parthian & Hyrcanian horse", "note": "Parthians, Sacae, Tapurians, Hyrcanians, Albanians and Sacesinians at the end of the line", "contingent": "western"},
        {"id": "arm-capp", "side": "persia", "kind": "cavalry", "label": "Armenian & Cappadocian horse", "note": "Posted in front of the right wing", "contingent": "western"},
    ]

    field_ring = path((-3200, -150), (-200, -150), (2600, -150), (2600, 1000), (2600, 2100), (-200, 2100), (-3200, 2100), (-3200, 1000))
    terrain = [
        {"id": "levelled-ground", "kind": "field", "label": "Ground levelled for the chariots", "area": field_ring},
        {"id": "gomel", "kind": "river", "label": "Gomel (Bumodus?)", "line": GOMEL},
        {"id": "khazir", "kind": "river", "label": "Khazir", "line": KHAZIR},
        {"id": "mahad-hills", "kind": "hill", "label": "Hills west of Mahad", "area": ellipse((43.386, 36.632), 1300, 2700, rotate=-10)},
        {"id": "jebel-maqlub", "kind": "hill", "label": "Jebel Maqlub", "area": ellipse((43.413, 36.526), 3600, 1300, rotate=15)},
        {"id": "mac-camp", "kind": "camp", "label": "Macedonian camp", "area": ellipse(P(*CAMP_MAC), 650, 420, rotate=-50)},
        {"id": "persian-camp", "kind": "camp", "label": "Persian camp", "area": ellipse(P(*CAMP_PER), 800, 450, rotate=-50)},
        {"id": "tell-gomel", "kind": "village", "label": "Tell Gomel (Gaugamela?)", "at": [43.472, 36.585]},
        {"id": "rough-ground", "kind": "label", "label": "Unlevelled ground", "at": P(3500, 1100)},
    ]

    # ── Step 1: the eve ────────────────────────────────────────────────
    persian_line = {
        "guard": blk(0, 0, PF, width=400, depth=40),
        "darius": {"with": "guard"},
        "greeks-l": blk(400, 0, PF, width=350, depth=24),
        "greeks-r": blk(-400, 0, PF, width=350, depth=24),
        "elephants": blk(-250, 230, PF, width=200, depth=15),
        "chariots-centre": blk(200, 250, PF, width=500, depth=12),
        "left-horse": blk(912, 0, PF, width=650, depth=50),
        "left-foot": blk(1580, 0, PF, width=600, depth=40),
        "bessus-horse": blk(2450, 0, PF, width=1100, depth=60),
        "bessus": {"with": "bessus-horse"},
        "scythians": blk(2250, 320, PF, width=700, depth=40),
        "chariots-left": blk(1350, 380, PF, width=1100, depth=12),
        "indian-horse": blk(-800, 0, PF, width=400, depth=50),
        "levies": blk(0, -320, PF, width=1000, depth=220),
        "syrian-median": blk(-1600, 0, PF, width=1200, depth=60),
        "mazaeus": {"with": "syrian-median"},
        "parthian-horse": blk(-2600, 0, PF, width=800, depth=60),
        "arm-capp": blk(-2200, 300, PF, width=800, depth=40),
    }
    step1 = {
        "id": "eve",
        "title": "Darius waits on his levelled plain",
        "time": "30 September, evening and night",
        "narrative": (
            "Darius drew his army up on the open plain in front of Gaugamela and, afraid of a surprise attack, kept it "
            "standing in battle order all night. Cavalry held both wings: Bessus with the Bactrians and the eastern "
            "peoples on the left, Mazaeus with the Syrian, Median and Parthian horse on the right. The king stood in the "
            "centre among his guard and Greek mercenaries, with scythed chariots and a few Indian elephants out in front. "
            "About 30 stades away, on the hills to the north-west, Alexander camped his army in fighting order, rode round "
            "the ground with his Companions and light troops to look for traps, and turned down Parmenion's advice to "
            "attack in the dark."
        ),
        "positions": {
            **persian_line,
            "alexander": blk(-150, 5300),
            "baggage": blk(*BAGGAGE),
        },
        "moves": [
            mv("alexander", "march", (-150, 5300), (1200, 3900), (2900, 2500), (1500, 2100), (-1200, 2200), (-2900, 2800), (-1600, 4300), (-150, 5300), label="Reconnaissance"),
        ],
        "notes": [
            note(-150, 5750, "Parmenion urges a night attack; Alexander refuses"),
            note(0, -600, "The Persians stand under arms all night"),
            note(-1400, 3300, "About 30 stades (5.5 km) between the armies", "label"),
        ],
    }

    # ── Step 2: Alexander's array ──────────────────────────────────────
    step2 = {
        "id": "deployment",
        "title": "Alexander's two-line array",
        "time": "1 October, morning",
        "narrative": (
            "Alexander brought his army down onto the plain and formed it against a line far longer than his own. The "
            "hypaspists and the phalanx held the centre, the Companion cavalry the right under his own command, the "
            "Thessalian and allied Greek horse the left under Parmenion. Both ends were bent back at an angle with light "
            "infantry and horse, so that Persians riding round a wing would meet a front instead of a bare flank, and a "
            "second line of Greek allied and mercenary foot stood behind, ready to face about. Arrian notes that Darius's "
            "own station lay opposite Alexander's squadron: the Persian left reached far beyond the Macedonian right."
        ),
        "positions": {
            **mac_deploy(U2, V2, sized=True),
            "alexander": {"with": "companions"},
            "parmenion": {"with": "thessalians"},
            "baggage": {"state": "hidden"},
        },
        "moves": [
            mv("alexander", "march", (-150, 5300), (0, 3600), F2["companions"], label="Down from the hills"),
            {"side": "macedon", "type": "march", "path": path((-600, 4900), (-900, 3300), (-1300, 2150))},
        ],
        "notes": [
            note(F2["rear-line"][0], F2["rear-line"][1] + 120, "Second line, ready to face about", "label"),
            note(F2["right-flank"][0] + 250, F2["right-flank"][1] + 250, "Flank refused at an angle", "label"),
        ],
    }

    # ── Step 3: the march to the right ─────────────────────────────────
    step3 = {
        "id": "march-right",
        "title": "The march to the right",
        "time": "Morning",
        "narrative": (
            "Rather than advance straight at the Persians, Alexander led the whole army obliquely to the right as it "
            "closed. Darius kept pace, shifting and stretching his left wing so that it still overlapped the Macedonian "
            "right, while the Scythian horse out in front rode along the line and skirmished with Alexander's leading "
            "troops. The Macedonian right was now nearing the end of the cleared ground, and beyond it the chariots "
            "would be of no use."
        ),
        "positions": {
            **mac_deploy(U3, V3, sized=False),
            "bessus-horse": blk(2850, 0),
            "left-foot": blk(1780, 0),
            "left-horse": blk(1000, 0, width=800),
            "scythians": blk(1950, 820, toward((1950, 820), (1600, 1300))),
            "chariots-left": blk(1450, 400),
        },
        "moves": [
            mv("companions", "advance", F2["companions"], F3["companions"]),
            mv("phalanx-right", "advance", F2["phalanx-right"], F3["phalanx-right"]),
            mv("thessalians", "advance", F2["thessalians"], F3["thessalians"]),
            mv("right-flank", "advance", F2["right-flank"], F3["right-flank"]),
            mv("bessus-horse", "march", (2450, 0), (2850, 0)),
            mv("scythians", "advance", (2250, 320), (2150, 600), (1950, 820)),
        ],
        "notes": [
            note(2600, 1950, "End of the levelled ground", "label"),
        ],
        "focus": ["companions", "scythians"],
    }

    # ── Step 4: Bessus's horse rides round the flank ───────────────────
    scy4 = (2130, 1600)
    men4 = (2000, 1510)
    step4 = {
        "id": "outflanking",
        "title": "Bessus's horse rides round the flank",
        "camera": {"center": P(1750, 1250), "zoom": 13.7},
        "narrative": (
            "To stop Alexander slipping off the prepared ground, Darius ordered the leading horsemen of his left, the "
            "armoured Scythians and about a thousand Bactrians, to ride round the Macedonian right. This was the threat "
            "the angled flank had been built to meet. Alexander sent Menidas with the mercenary cavalry posted in front "
            "of it to charge them, as his orders anticipated, but Menidas had only a few hundred riders against many "
            "times that number."
        ),
        "positions": {
            "scythians": blk(*scy4, toward(scy4, men4), width=450, depth=100, state="engaged"),
            "menidas": blk(*men4, toward(men4, scy4), state="engaged"),
        },
        "moves": [
            mv("scythians", "flank", (1950, 820), (2450, 1050), (2400, 1450), scy4),
            mv("menidas", "charge", F3["menidas"], (1750, 1250), men4),
        ],
        "focus": ["scythians", "menidas"],
    }

    # ── Step 5: the cavalry fight on the right ─────────────────────────
    ari5 = (1990, 1560)
    scy5 = (2140, 1660)
    bes5 = (2230, 1390)
    men5 = (1650, 1420)
    step5 = {
        "id": "flank-fight",
        "title": "The cavalry fight on the right",
        "camera": {"center": P(1800, 1250), "zoom": 13.7},
        "narrative": (
            "Menidas's horsemen were driven back. Alexander answered with Ariston's Paeonians and the mercenaries, who "
            "made the Scythians give way, but the main body of Bessus's Bactrian cavalry then came up, rallied them and "
            "turned the clash into a general cavalry battle. Better armoured and far more numerous, the Persian riders "
            "inflicted heavy losses, yet the Macedonian squadrons held and charged again and again, keeping the "
            "flanking force busy well away from the main line."
        ),
        "positions": {
            "menidas": blk(*men5, MF + 45, state="routed"),
            "ariston": blk(*ari5, toward(ari5, scy5), state="engaged"),
            "scythians": blk(*scy5, toward(scy5, ari5), state="engaged"),
            "bessus-horse": blk(*bes5, toward(bes5, ari5), width=700, depth=140, state="engaged"),
            "right-flank": blk(1430, 1450),
        },
        "moves": [
            mv("menidas", "retreat", men4, (1800, 1490), men5),
            mv("ariston", "charge", F3["ariston"], (1700, 1400), ari5),
            mv("bessus-horse", "advance", (2850, 0), (2800, 700), bes5),
        ],
        "notes": [
            note(2450, 1950, "Armoured Scythian horse take a heavy toll", "clash"),
        ],
        "focus": ["ariston", "bessus-horse", "scythians"],
    }

    # ── Step 6: the scythed chariots ───────────────────────────────────
    ch_l6 = (850, 1000)
    ch_c6 = (330, 1060)
    step6 = {
        "id": "chariots",
        "title": "The scythed chariots fail",
        "narrative": (
            "Darius now loosed his scythed chariots at Alexander's part of the line, hoping to break up the phalanx "
            "before the infantry met. The Agrianians, archers and Balacrus's javelinmen in front of the Companions shot "
            "down drivers and teams, and some ran in to seize the reins. Where chariots got through, the files stepped "
            "apart as they had been drilled to and let them run on down the lanes, to be finished off by the grooms and "
            "hypaspists behind. The elephants seem to have been kept back; they were found in the Persian camp after the "
            "battle."
        ),
        "positions": {
            "chariots-left": blk(*ch_l6, MF + 180, state="destroyed"),
            "chariots-centre": blk(*ch_c6, MF + 180, state="destroyed"),
            "elephants": blk(-350, -1700, state="ready"),
            "screen": {"state": "engaged"},
            "hypaspists": {"lanes": 3},
            "phalanx-right": {"lanes": 4},
        },
        "moves": [
            mv("chariots-left", "charge", (1450, 400), (1150, 700), ch_l6),
            mv("chariots-centre", "charge", (200, 250), (260, 650), ch_c6),
            mv("elephants", "march", (-250, 230), (-300, -900), (-350, -1700)),
        ],
        "notes": [
            note(750, 870, "Javelinmen shoot the drivers and seize reins", "clash"),
            note(250, 1300, "Files open lanes; chariots are taken behind", "event"),
        ],
        "focus": ["chariots-left", "chariots-centre", "screen"],
    }

    # ── Step 7: the gap ────────────────────────────────────────────────
    lh7 = (2450, 1000)
    are7 = (2050, 1290)
    arm7 = (-1500, 1220)
    step7 = {
        "id": "gap",
        "title": "A gap opens in the Persian line",
        "narrative": (
            "Darius set his whole line moving forward. On his left still more horsemen rode out to join the fight on the "
            "Macedonian flank, and as the Persian and Cadusian cavalry beside the centre left their place, a gap opened "
            "between the king's Greek mercenaries and the foot further out. Alexander sent Aretes and his lancers against "
            "the riders working round his wing. On the far side of the field the Armenian and Cappadocian cavalry charged "
            "Parmenion's angled left."
        ),
        "positions": {
            "guard": blk(0, 350),
            "greeks-l": blk(400, 350),
            "greeks-r": blk(-400, 350),
            "indian-horse": blk(-800, 350),
            "levies": blk(0, 30),
            "syrian-median": blk(-1600, 400),
            "parthian-horse": blk(-2600, 400),
            "left-foot": blk(1780, 250),
            "left-horse": blk(*lh7, toward(lh7, bes5), width=500, depth=80, state="ready"),
            "aretes": blk(*are7, toward(are7, bes5), state="engaged"),
            "arm-capp": blk(*arm7, toward(arm7, F3["left-flank"]), state="engaged"),
            "left-flank": {"state": "engaged"},
            "screen": {"state": "ready"},
            "hypaspists": {"lanes": 0},
            "phalanx-right": {"lanes": 0},
        },
        "moves": [
            mv("left-horse", "advance", (1000, 0), (1800, 450), lh7),
            mv("aretes", "charge", F3["aretes"], (1650, 1050), are7),
            mv("arm-capp", "charge", (-2200, 300), (-1950, 900), arm7),
            {"side": "persia", "type": "advance", "path": path((-1600, -150), (-1600, 330))},
            {"side": "persia", "type": "advance", "path": path((0, -500), (0, 280))},
        ],
        "notes": [
            note(1100, 200, "Gap opens in the Persian line", "event"),
        ],
        "focus": ["left-horse", "aretes", "companions"],
    }

    # ── Step 8: the wedge ──────────────────────────────────────────────
    com8 = (760, 470)
    hyp8 = (420, 390)
    phr8 = (-20, 395)
    step8 = {
        "id": "wedge",
        "title": "The wedge drives at Darius",
        "camera": {"center": P(450, 650), "zoom": 13.7},
        "narrative": (
            "This was the opening Alexander had been waiting for. He swung the Companions, until then moving to the right "
            "in column, into the gap in a wedge, with the hypaspists and the nearest phalanx battalions charging beside "
            "them, and drove straight for Darius. The horsemen pressed in close, thrusting at faces; the sarissas of the "
            "phalanx came in alongside; and the Greek mercenaries and the royal guard took the full weight of the blow."
        ),
        "positions": {
            "companions": blk(*com8, toward(com8, (0, 330)), shape="wedge", width=450, depth=260, state="engaged"),
            "hypaspists": blk(*hyp8, MF, state="engaged"),
            "phalanx-right": blk(*phr8, MF, state="engaged"),
            "greeks-l": {"state": "engaged"},
            "guard": {"state": "engaged"},
        },
        "moves": [
            mv("companions", "charge", F3["companions"], (880, 800), com8, label="The wedge"),
            mv("hypaspists", "attack", F3["hypaspists"], hyp8),
            mv("phalanx-right", "attack", F3["phalanx-right"], phr8),
        ],
        "notes": [
            note(250, 150, "Alexander strikes for the king", "clash"),
        ],
        "focus": ["companions", "hypaspists", "phalanx-right", "guard"],
    }

    # ── Step 9: Darius flees ───────────────────────────────────────────
    dar9 = (-100, -2800)
    com9 = (300, -1700)
    bes9 = (1500, -2600)
    are9 = (2500, 500)
    step9 = {
        "id": "flight",
        "title": "Darius flees",
        "narrative": (
            "Under this pressure Darius turned his chariot and fled, by Arrian's account the first in his centre to break; "
            "Diodorus has a javelin aimed at the king strike his charioteer instead, so that those nearby thought Darius "
            "had fallen. The centre gave way behind him, and the horsemen working round the Macedonian right broke as "
            "Aretes charged them and streamed away to the rear. Alexander set off after the king with the Companions."
        ),
        "positions": {
            "darius": blk(*dar9),
            "guard": blk(100, -650, state="routed"),
            "greeks-l": blk(500, -350, state="routed"),
            "greeks-r": blk(-400, -150, state="routed"),
            "levies": blk(0, -500, state="routed"),
            "left-horse": blk(2750, 300, PF + 180, state="routed"),
            "scythians": blk(2750, 1300, PF + 180, state="routed"),
            "bessus-horse": blk(*bes9, PF + 180, state="routed"),
            "companions": blk(*com9, MF, shape="block", width=500, depth=80, state="ready"),
            "aretes": blk(*are9, toward(are9, bes9), state="ready"),
            "hypaspists": blk(420, 100),
            "phalanx-right": blk(-20, 120),
            "ariston": {"state": "ready"},
            "left-foot": {"state": "routed"},
        },
        "moves": [
            mv("darius", "retreat", (0, 300), (-100, -1200), dar9, label="Darius flees"),
            mv("guard", "rout", (0, 350), (100, -650)),
            mv("companions", "pursuit", com8, (500, -500), com9),
            mv("bessus-horse", "retreat", bes5, (2700, 0), bes9),
            mv("aretes", "pursuit", are7, are9),
        ],
        "notes": [
            note(-350, 600, "The Persian centre collapses", "event"),
        ],
        "focus": ["darius", "companions", "guard"],
    }

    # ── Step 10: the phalanx tears, Parmenion pressed ──────────────────
    ind10 = (-500, 4850)
    par10 = (-2000, 1950)
    syr10 = (-950, 1060)
    com10 = (500, -3200)
    step10 = {
        "id": "left-pressed",
        "title": "The phalanx tears; Parmenion hard pressed",
        "narrative": (
            "Not every battalion could follow. Simmias held his battalion back because the left was reported to be in "
            "trouble, and with Craterus's beside it stayed to fight while the rest went forward, so a gap opened in the "
            "phalanx. Indian and Persian horsemen poured through it, rode past the second "
            "line and fell on the baggage, where the Persian prisoners rose to help them. Meanwhile Mazaeus's wing, unaware "
            "that Darius had gone, pressed the Thessalians from the front while Parthian and other horse rode round the "
            "angled flank and struck Parmenion's wing in the side. Parmenion sent riders after Alexander for help."
        ),
        "positions": {
            "darius": {"state": "hidden"},
            "phalanx-left": {"state": "engaged"},
            "phalanx-right": blk(-20, -350),
            "hypaspists": blk(420, -400),
            "indian-horse": blk(*ind10, toward((-300, 3000), ind10), state="engaged"),
            "parthian-horse": blk(*par10, toward(par10, F3["left-flank"]), state="engaged"),
            "syrian-median": blk(*syr10, PF, width=1000, state="engaged"),
            "thessalians": {"state": "engaged"},
            "left-flank": {"state": "wavering"},
            "companions": blk(*com10),
            "baggage": {"state": "captured", "by": "persia"},
        },
        "moves": [
            mv("indian-horse", "charge", (-800, 350), (-200, 950), (-600, 1750), (-700, 3200), ind10, label="Through the gap"),
            mv("parthian-horse", "flank", (-2600, 400), (-3000, 1300), par10),
            mv("syrian-median", "attack", (-1600, 400), syr10),
            mv("companions", "pursuit", com9, com10),
            mv("phalanx-right", "advance", (-20, 120), (-20, -350)),
        ],
        "notes": [
            note(-170, 1250, "Simmias halts: the phalanx line breaks", "event"),
            note(-1100, 1450, "Parmenion sends riders to recall Alexander", "event"),
        ],
        "focus": ["indian-horse", "parthian-horse", "phalanx-left", "thessalians"],
    }

    # ── Step 11: Alexander turns back ──────────────────────────────────
    com11 = (-1780, 160)
    par11 = (-1950, 310)
    rear11 = (-450, 4500)
    ind11 = (-2700, 3600)
    the11 = (-950, 880)
    syr11 = (-1700, -400)
    step11 = {
        "id": "return",
        "title": "Alexander turns back",
        "narrative": (
            "The officers of the second line faced about and caught the raiders at the baggage from behind, killing many "
            "and scattering the rest; Darius's mother Sisygambis is said to have refused to leave with them. Alexander "
            "broke off the chase and rode back toward the Persian right, running into Parthian, Indian and Persian horse "
            "retreating in deep formation. In the hardest cavalry fight of the day about sixty Companions fell and "
            "Hephaestion, Coenus and Menidas were wounded. By the time Alexander broke through, the Thessalians had charged "
            "and Mazaeus's wing was already giving way."
        ),
        "positions": {
            "companions": blk(*com11, toward(com11, par11), state="engaged"),
            "parthian-horse": blk(*par11, toward(par11, com11), state="engaged"),
            "rear-line": blk(*rear11, PF, state="engaged"),
            "indian-horse": blk(*ind11, state="routed"),
            "baggage": {"state": "ready"},
            "thessalians": blk(*the11, state="engaged"),
            "syrian-median": blk(*syr11, PF + 180, state="routed"),
            "arm-capp": blk(-2050, 700, PF + 180, state="routed"),
            "left-flank": {"state": "ready"},
            "phalanx-left": {"state": "ready"},
        },
        "moves": [
            mv("companions", "charge", com10, (-900, -2300), (-1500, -700), com11, label="Alexander rides back"),
            mv("parthian-horse", "retreat", par10, (-2200, 1200), par11),
            mv("rear-line", "attack", F3["rear-line"], (-500, 3000), rear11, label="Reserve faces about"),
            mv("indian-horse", "rout", ind10, (-1600, 4500), ind11),
            mv("thessalians", "charge", F3["thessalians"], the11),
            mv("syrian-median", "rout", syr10, (-1300, 300), syr11),
        ],
        "notes": [
            note(-1950, -100, "Hardest fight of the day: about 60 Companions fall", "clash"),
            note(-600, 5450, "Sisygambis refuses to go with the raiders", "event"),
        ],
        "focus": ["companions", "parthian-horse", "thessalians", "rear-line"],
    }

    # ── Step 12: pursuit ───────────────────────────────────────────────
    com12 = (-700, -11500)
    the12 = (-1900, -2600)
    gone = {uid: {"state": "hidden"} for uid in ("guard", "greeks-l", "greeks-r", "levies", "left-horse", "left-foot", "bessus-horse", "scythians", "indian-horse", "syrian-median", "parthian-horse", "arm-capp", "bessus", "mazaeus")}
    step12 = {
        "id": "pursuit",
        "title": "Pursuit toward Arbela",
        "time": "Until nightfall; Arbela the next day",
        "narrative": (
            "With both Persian wings beaten, Alexander took up the chase again for as long as the light lasted, crossed "
            "the Lycus (Great Zab), rested his horses until midnight and rode on to Arbela, which he reached the next day. "
            "Darius had already gone, but his treasure, chariot and weapons were taken there. Parmenion, following the "
            "enemy on his own front, seized the Persian camp with its baggage, elephants and camels. Darius escaped into "
            "Media and never again led an army against Alexander."
        ),
        "positions": {
            **gone,
            "companions": blk(*com12, MF, state="ready"),
            "thessalians": blk(*the12, MF, state="ready"),
            "parmenion": blk(*CAMP_PER),
            "elephants": {"state": "captured", "by": "macedon"},
            "rear-line": {"state": "ready"},
            "phalanx-right": {"state": "ready"},
            "hypaspists": {"state": "ready"},
        },
        "moves": [
            mv("companions", "pursuit", com11, (-1100, -3500), com12, label="To the Lycus and Arbela"),
            mv("thessalians", "pursuit", the11, (-1600, -1000), the12),
            mv("parmenion", "march", the11, (-900, -600), CAMP_PER),
        ],
        "notes": [
            note(-500, -1450, "Parmenion takes the Persian camp, elephants and camels", "capture"),
            note(-600, -11900, "On to the Lycus and Arbela, c. 70 km", "label"),
        ],
        "terrain_state": {"persian-camp": {"held_by": "macedon", "state": "captured"}},
        "focus": ["companions", "parmenion"],
    }

    return {
        "schema": 2,
        "slug": SLUG,
        "kind": "battle",
        "entity": {"name": "Battle of Gaugamela", "wikidata": "Q179670"},
        "title": "Battle of Gaugamela",
        "date_label": "1 October 331 BC",
        "year": -331,
        "intro": (
            "In the late summer of 331 BC Alexander of Macedon crossed the Euphrates and the Tigris in search of the "
            "battle that would decide the war with Persia. Darius III, beaten at Issus two years before, had spent the "
            "interval raising a far larger army from the eastern satrapies, strong above all in cavalry, and he chose his "
            "ground with care: an open plain beside the village of Gaugamela, east of the Tigris, where rough patches "
            "were cleared and levelled so that scythed chariots and horsemen could charge freely. Alexander came down "
            "the Tigris from the north-west, rested his army for four days once his scouts had found the enemy, and on "
            "30 September halted on low hills about 30 stades from the Persian line. The next day some 47,000 "
            "Macedonians and Greeks faced an army that probably outnumbered them two to one and whose line overlapped "
            "theirs at both ends."
        ),
        "outcome": (
            "A decisive Macedonian victory: Darius fled, the royal army broke up, and Babylon, Susa and Persepolis "
            "lay open to Alexander."
        ),
        "uncertainty": (
            "The site is disputed. This map follows the northern identification on the Navkur plain by Tell Gomel, whose "
            "name echoes Gaugamela, with the Macedonian camp on the hills west of Mahad; the older southern candidate, "
            "Karamlesh, lies about 30 km to the south. The orientation, frontages and block sizes are reconstructed from "
            "Arrian's order of battle and the ground, not from surveyed evidence; his remark that Darius stood opposite "
            "Alexander's own squadron fixes the opening alignment. Arrian credits Darius with 40,000 horse "
            "and a million foot, Diodorus with a million men, Curtius with about 245,000; modern estimates range from "
            "roughly 50,000 to 120,000. In Arrian the baggage was raided by Indian and Persian horse riding through a gap "
            "in the phalanx; Diodorus and Curtius instead have Mazaeus send a detachment round the flank to the camp."
        ),
        "sources": [
            {"title": "Arrian, Anabasis of Alexander 3.7-3.16", "kind": "primary"},
            {"title": "Diodorus Siculus, Library of History 17.53-61", "kind": "primary"},
            {"title": "Quintus Curtius Rufus, Histories of Alexander 4.9-4.16", "kind": "primary"},
            {"title": "Battle of Gaugamela - Wikipedia", "url": "https://en.wikipedia.org/wiki/Battle_of_Gaugamela", "kind": "web"},
            {"title": "Gaugamela (331 BCE) - Livius.org", "url": "https://www.livius.org/articles/battle/gaugamela-331-bce/", "kind": "web"},
            {"title": "Marciak, Szypula, Sobiech & Pirowski, The Battle of Gaugamela and the Question of Visibility on the Battlefield, Iraq 83 (2021)", "url": "https://doi.org/10.1017/irq.2021.11", "kind": "secondary"},
            {"title": "Pirowski, Marciak & Sobiech, Alexander the Great's Military Camp at Gaugamela on the Navkur Plain, Remote Sensing 13 (2021) 904", "url": "https://doi.org/10.3390/rs13050904", "kind": "secondary"},
            {"title": "Marciak et al., Gaugamela in the Plains of Nineveh? The Southern Location Reconsidered, Anabasis 11 (2020)", "url": "https://journals.ur.edu.pl/anabasis/article/view/10401", "kind": "secondary"},
        ],
        "sides": sides,
        "units": units,
        "terrain": terrain,
        "steps": [step1, step2, step3, step4, step5, step6, step7, step8, step9, step10, step11, step12],
    }
