"""Battle of Waterloo, 18 June 1815 — map story builder.

Anchors are today's buildings and roads (OpenStreetMap, checked against the
1815 accounts): the farms of Hougoumont, La Haye Sainte and Papelotte, the inn
of La Belle Alliance, Plancenoit church, the Brussels–Charleroi road (N5), the
Nivelles road (N27) and the Ohain road along the Mont-Saint-Jean crest (today
Route du Lion / Rue de la Croix / Rue du Dimont). Formations are grouped by
division or corps; positions follow the mainstream reconstruction in the
Wikipedia article and its order of battle.

    scripts/capped.sh pipeline/.venv/bin/python -m pipeline.map_stories build battle_of_waterloo
"""

from __future__ import annotations

from pipeline.map_stories.geo import arc, dest, ellipse, offset, path, r6, rel

# ── anchors (lon, lat) ──────────────────────────────────────────────────────

HOUGOUMONT = (4.3946, 50.6707)  # château and farm buildings
LA_HAYE_SAINTE = (4.4117, 50.6779)
PAPELOTTE = (4.4341, 50.6801)
BELLE_ALLIANCE = (4.4135, 50.6684)  # the inn, on the Charleroi road
CROSSROADS = (4.4120, 50.6804)  # Ohain road × Brussels road (Wellington's elm)
MSJ_FARM = (4.4098, 50.6861)
MONT_SAINT_JEAN = (4.4074, 50.6895)
LION = (4.4048, 50.6784)  # Lion's Mound (built 1820s from the ridge)
ROSSOMME = (4.4122, 50.6577)  # farm on the Charleroi road (approximate)
LE_CAILLOU = (4.4207, 50.6461)
PLANCENOIT = (4.4299, 50.6599)
FRICHERMONT = (4.4446, 50.6783)  # château ruins
SMOHAIN = (4.4418, 50.6809)
CHAPELLE_ST_LAMBERT = (4.5005, 50.6927)
CHARLEROI = (4.4440, 50.4110)  # where Napoleon's flight led, off the map
OHAIN = (4.4707, 50.6977)
WAVRE = (4.6104, 50.7170)
BRAINE = (4.3693, 50.6829)
GENAPPE = (4.4511, 50.6109)
MARANSART = (4.4615, 50.6604)

# The Ohain road along the Mont-Saint-Jean crest (OSM), west → east.
OHAIN_ROAD = [
    (4.3891, 50.6834), (4.3928, 50.6835), (4.3948, 50.6820), (4.3973, 50.6818), (4.3993, 50.6814),
    (4.4010, 50.6812), (4.4033, 50.6805), (4.4054, 50.6796), (4.4073, 50.6798), (4.4097, 50.6801),
    (4.4120, 50.6804), (4.4153, 50.6807), (4.4173, 50.6811), (4.4204, 50.6814), (4.4224, 50.6812),
    (4.4266, 50.6806), (4.4285, 50.6802), (4.4309, 50.6797), (4.4324, 50.6788),
]
# Beyond Papelotte the lane runs on through Smohain toward Ohain (Zieten's road in).
OHAIN_LANE_EAST = [
    (4.4324, 50.6788), (4.4357, 50.6797), (4.4425, 50.6808), (4.4455, 50.6829), (4.4560, 50.6885), (4.4707, 50.6977),
]
# Brussels–Charleroi road (N5), Mont-Saint-Jean → Genappe (OSM, thinned).
CHARLEROI_ROAD = [
    (4.4023, 50.6986), (4.4052, 50.6922), (4.4084, 50.6881), (4.4105, 50.6835), (4.4123, 50.6793),
    (4.4128, 50.6751), (4.4132, 50.6700), (4.4136, 50.6653), (4.4131, 50.6603), (4.4129, 50.6557),
    (4.4156, 50.6513), (4.4196, 50.6468), (4.4228, 50.6406), (4.4304, 50.6330), (4.4341, 50.6262),
    (4.4407, 50.6198), (4.4505, 50.6157), (4.4589, 50.6111),
]
# Nivelles road (N27), Mont-Saint-Jean → south-west, passing west of Hougoumont.
NIVELLES_ROAD = [
    (4.4070, 50.6895), (4.4051, 50.6878), (4.4027, 50.6852), (4.4001, 50.6822), (4.3988, 50.6808),
    (4.3959, 50.6776), (4.3936, 50.6751), (4.3912, 50.6724), (4.3907, 50.6719), (4.3812, 50.6613),
]
# The ridge the French formed on, through La Belle Alliance.
FRENCH_RIDGE = [(4.3860, 50.6652), (4.4000, 50.6664), BELLE_ALLIANCE, (4.4250, 50.6712), (4.4345, 50.6742)]
# La Lasne from Plancenoit to below Chapelle-Saint-Lambert (OSM, simplified 30 m).
LASNE = [
    (4.4260, 50.6587), (4.4304, 50.6592), (4.4363, 50.6580), (4.4405, 50.6589), (4.4443, 50.6609),
    (4.4535, 50.6644), (4.4590, 50.6653), (4.4636, 50.6671), (4.4647, 50.6691), (4.4691, 50.6711),
    (4.4742, 50.6732), (4.4769, 50.6763), (4.4778, 50.6777), (4.4799, 50.6810), (4.4816, 50.6838),
    (4.4867, 50.6850), (4.4894, 50.6888), (4.4927, 50.6902), (4.4925, 50.6928), (4.4951, 50.6942),
    (4.4994, 50.6988), (4.4979, 50.7026), (4.5005, 50.7047),
]
# The Smohain brook, from below Papelotte east to the Lasne.
SMOHAIN_BROOK = [
    (4.4416, 50.6802), (4.4497, 50.6836), (4.4540, 50.6867), (4.4594, 50.6877), (4.4638, 50.6896),
    (4.4677, 50.6917), (4.4714, 50.6934), (4.4760, 50.6946), (4.4804, 50.6950), (4.4861, 50.6957),
    (4.4920, 50.6968), (4.4975, 50.6968),
]

# d'Erlon's corps stood on the ridge running east-north-east from La Belle Alliance.
DERLON_AXIS = 74.0  # bearing of the French right's line
DERLON_FACE = DERLON_AXIS - 90 + 360  # 344: facing the allied left
DERLON_0 = offset(BELLE_ALLIANCE, east=280, north=200)  # Quiot's division, beside the road


def derlon(k: float, ahead: float = 0.0) -> list[float]:
    """A point on d'Erlon's start line, `k` division-intervals (390 m) east of Quiot."""
    return rel(dest(DERLON_0, DERLON_AXIS, 390 * k), DERLON_FACE, ahead=ahead)


GRAND_BATTERY = derlon(1.0, ahead=300)  # on the spur ~300 m in front of d'Erlon's line


def pl(at, facing, width=None, depth=None, **kw) -> dict:
    out = {"at": r6(at), "facing": facing}
    if width is not None:
        out["width"] = width
    if depth is not None:
        out["depth"] = depth
    out.update(kw)
    return out


def mv(unit: str | None, kind: str, *pts, side: str | None = None, label: str | None = None, **extra) -> dict:
    out: dict = {"type": kind, "path": path(*pts)}
    if unit:
        out["unit"] = unit
    if side:
        out["side"] = side
    if label:
        out["label"] = label
    out.update(extra)
    return out


def note(at, text: str, kind: str = "event") -> dict:
    return {"at": r6(at), "text": text, "kind": kind}


# ── where things stand at each step ─────────────────────────────────────────

# 11:00 deployment.
AL = {
    "hougoumont": pl(offset(HOUGOUMONT, east=40, north=10), 190, 260, 190),
    "maitland": pl((4.3995, 50.6826), 195, 400, 70, shape="line"),
    "alten": pl((4.4070, 50.6813), 185, 620, 140),
    "lhs": pl(LA_HAYE_SAINTE, 180, 90, 70),
    "picton": pl((4.4195, 50.6826), 180, 1150, 150),
    "saxe-weimar": pl((4.4385, 50.6793), 165, 900, 220),
    "light-cav": pl((4.4330, 50.6843), 175, 700, 90),
    "heavy-cav": pl((4.4125, 50.6850), 180, 1000, 110),
    "brunswick": pl((4.3990, 50.6873), 175, 450, 220),
    "adam": pl((4.3905, 50.6838), 160, 450, 90),
    "chasse": pl((4.3765, 50.6808), 160, 600, 220),
    "wellington": {"at": r6(offset(CROSSROADS, east=-60, north=50))},
}
FR = {
    "jerome": pl((4.3925, 50.6649), 12, 700, 150),
    "foy-bachelu": pl((4.4045, 50.6664), 8, 1050, 150),
    "kellermann": pl((4.3995, 50.6624), 8, 900, 110),
    "quiot": pl(derlon(0), DERLON_FACE, 370, 90),
    "donzelot": pl(derlon(1), DERLON_FACE, 370, 90),
    "marcognet": pl(derlon(2), DERLON_FACE, 370, 90),
    "durutte": pl(derlon(3), DERLON_FACE, 370, 90),
    "grand-battery": pl(GRAND_BATTERY, DERLON_FACE, 1100, 45),
    "milhaud": pl(derlon(1.5, ahead=-360), DERLON_FACE, 950, 110),
    "lobau": pl(offset(BELLE_ALLIANCE, east=60, north=-480), 0, 420, 260, shape="column"),
    "young-guard": pl(offset(ROSSOMME, east=330, north=230), 0, 320, 200),
    "guard-grenadiers": pl(offset(ROSSOMME, east=-260, north=260), 0, 260, 110),
    "guard-chasseurs": pl(offset(ROSSOMME, east=-260, north=50), 0, 320, 110),
    "old-guard": pl(offset(ROSSOMME, east=330, north=-60), 0, 360, 160),
    "napoleon": {"at": r6(offset(ROSSOMME, east=-60))},
}

# The Prussians, morning: Bülow's corps strung out on the road west of Wavre.
BULOW_ROAD = [(4.6400, 50.7160), WAVRE, (4.5760, 50.7090), (4.5420, 50.7010)]
BULOW_AT_CSL = (4.4935, 50.6905)
BULOW_ATTACK = (4.4420, 50.6648)  # front from Frichermont's woods down to Plancenoit
ZIETEN_AT_WAVRE = (4.5920, 50.7080)
ZIETEN_GENVAL = (4.5050, 50.7075)
ZIETEN_OHAIN = (4.4545, 50.6888)

NAP_LBA = offset(BELLE_ALLIANCE, east=-40, north=120)  # Napoleon's evening post by the inn

BATTLEFIELD = {"center": [4.4100, 50.6728], "zoom": 12.85}


def build() -> dict:
    steps = []

    # 1 ─ morning overview: the Prussians leave Wavre ──────────────────────────
    steps.append({
        "id": "prussians-march",
        "title": "Blücher marches to join Wellington",
        "time": "06:00–11:00",
        "narrative": (
            "Rain fell all night and the clay fields were still sodden at dawn. Wellington had said he would stand at "
            "Mont-Saint-Jean only if the Prussians sent him at least one corps; early on the 18th Blücher replied that he "
            "would come with three. Bülow's IV Corps, the one corps not mauled at Ligny, led the march from Wavre, but its "
            "columns and 88 guns crawled through the town's narrow streets, around a fire that blocked several of them, and "
            "along mud tracks; its rear only got clear around 10:00. Zieten's I Corps and Pirch's II Corps were to follow. Thirteen kilometres to "
            "the west, the two armies spent the morning forming up on facing ridges about 1,300 metres apart."
        ),
        "positions": {
            **AL, **FR,
            "bulow": pl((4.5420, 50.7010), 252, 120, 2400, shape="column"),
            "zieten": pl(ZIETEN_AT_WAVRE, 250, 700, 350),
            "blucher": {"with": "bulow"},
        },
        "moves": [mv("bulow", "march", *BULOW_ROAD, continues={"toward": r6(CHAPELLE_ST_LAMBERT), "label": "to Chapelle-Saint-Lambert"})],
        "notes": [
            note(offset(WAVRE, north=600), "Fire in Wavre delays Bülow's march"),
            note((4.4040, 50.6905), "Wellington's army on the Mont-Saint-Jean ridge", "label"),
            note((4.4110, 50.6560), "Napoleon's army forms around La Belle Alliance", "label"),
        ],
        "focus": ["bulow", "zieten", "blucher"],
    })

    # 2 ─ 11:00: the two lines ─────────────────────────────────────────────────
    steps.append({
        "id": "deployment",
        "title": "Two ridges and three farms",
        "time": "c. 11:00",
        "narrative": (
            "Wellington's line ran for about four kilometres along the Mont-Saint-Jean ridge, with the sunken Ohain road "
            "following its crest. As in Spain, he kept most of his infantry lying down just behind it, so the French could "
            "see only skirmishers and guns. Three groups of farm buildings in front of the ridge served as breakwaters: the "
            "walled château of Hougoumont on the right, La Haye Sainte beside the Brussels road in the centre, and Papelotte "
            "with the hamlets of Smohain on the left, where the Prussians were expected. Napoleon, unable to see the allied "
            "army, drew up symmetrically on the La Belle Alliance ridge: Reille's II Corps west of the road, d'Erlon's I Corps "
            "east of it, Kellermann's and Milhaud's cuirassiers behind them, and Lobau's VI Corps and the Imperial Guard in "
            "reserve. He let the ground dry before committing his guns and horses."
        ),
        "camera": BATTLEFIELD,
        "positions": {
            # Still on the road from Wavre: drawn, but not part of the battlefield frame.
            "bulow": {"frame": False},
            "zieten": {"frame": False},
            "blucher": {"frame": False},
        },
        "terrain_state": {
            "hougoumont": {"held_by": "allied", "state": "held"},
            "la-haye-sainte": {"held_by": "allied", "state": "held"},
            "papelotte": {"held_by": "allied", "state": "held"},
        },
        "notes": [
            note(offset(CROSSROADS, east=-330, north=170), "Infantry lies hidden behind the crest", "label"),
            note(offset(LA_HAYE_SAINTE, east=150, north=-60), "400 KGL riflemen hold La Haye Sainte", "label"),
            note(offset(ROSSOMME, east=-60, north=-150), "Napoleon at Rossomme", "label"),
        ],
    })

    # 3 ─ 11:30: Hougoumont ─────────────────────────────────────────────────────
    jerome_wood = offset(HOUGOUMONT, east=-20, north=-230)
    steps.append({
        "id": "hougoumont",
        "title": "The attack on Hougoumont",
        "time": "c. 11:30",
        "narrative": (
            "The battle opened on the French left, where Jérôme Bonaparte's division pushed into the Hougoumont wood. "
            "Bauduin's brigade cleared the trees but was cut down by British guns on the ridge, and Bauduin was killed. "
            "Soye's brigade reached the walls, and a party led by Sous-Lieutenant Legros axed open the north gate, until "
            "Lieutenant-Colonel Macdonell and a few Guardsmen forced it shut; the Frenchmen trapped inside were killed. "
            "Napoleon hoped the attack would draw in Wellington's reserves, but it did the opposite: brigade after brigade of "
            "Reille's corps, eventually some 14,000 men, was fed into the fight for a farm that the Coldstream and 3rd Guards, "
            "steadily reinforced down the hollow lane behind it, held until nightfall."
        ),
        "camera": {"center": [4.3975, 50.6738], "zoom": 13.55},
        "positions": {
            "jerome": pl(jerome_wood, 10, 520, 240, state="engaged"),
            "hougoumont": {"state": "engaged", "label": "Hougoumont (Guards)"},
        },
        "moves": [
            mv("jerome", "attack", FR["jerome"]["at"], offset(HOUGOUMONT, east=-40, north=-430), jerome_wood),
            mv(None, "fire", (4.3990, 50.6815), offset(HOUGOUMONT, east=-30, north=-300), side="allied", target="jerome"),
            mv(None, "attack", (4.3990, 50.6670), (4.3975, 50.6697), side="france"),
        ],
        "notes": [
            note(offset(HOUGOUMONT, north=60), "North gate forced, then shut again", "clash"),
            note(offset(HOUGOUMONT, east=-60, north=-420), "Bauduin killed in the wood", "death"),
        ],
        "terrain_state": {"hougoumont": {"state": "contested"}},
        "focus": ["jerome", "hougoumont"],
    })

    # 4 ─ 12:00–13:30: Grand Battery, Prussians sighted, Lobau turns east ─────
    lobau_flank = (4.4385, 50.6655)
    napoleon_lba = offset(BELLE_ALLIANCE, east=20, north=-170)
    steps.append({
        "id": "grand-battery",
        "title": "The Grand Battery opens; Prussians sighted",
        "time": "c. 12:00–13:30",
        "narrative": (
            "Around midday some eighty French guns, massed on a spur in front of d'Erlon's corps, opened on the allied left "
            "centre. They could see little beyond the skirmishers and Bylandt's Dutch-Belgian brigade, and many balls buried "
            "themselves in the mud, but the bombardment still bled the battalions waiting behind the crest. At about 13:15 "
            "Napoleon made out dark columns near Chapelle-Saint-Lambert, six or seven kilometres to his right: Bülow's "
            "vanguard. He "
            "sent word for Grouchy to come west, turned Lobau's VI Corps and the light cavalry of Domon and Subervie to face "
            "the Bois de Paris, and moved his own post up to La Belle Alliance. Bülow halted at Chapelle-Saint-Lambert until "
            "his long column closed up before tackling the deep Lasne valley."
        ),
        "camera": {"center": [4.4540, 50.6790], "zoom": 12.15},
        "positions": {
            "grand-battery": {"state": "engaged"},
            "lobau": pl(lobau_flank, 75, 1000, 160, shape="block", label="Lobau's VI Corps & light horse"),
            "bulow": pl(BULOW_AT_CSL, 250, 1300, 600, shape="block"),
            "napoleon": {"at": r6(napoleon_lba)},
        },
        "moves": [
            mv("grand-battery", "fire", derlon(0.4, ahead=330), (4.4150, 50.6812), target="picton"),
            mv("grand-battery", "fire", derlon(1.6, ahead=330), (4.4235, 50.6818), target="picton"),
            mv("lobau", "march", FR["lobau"]["at"], offset(BELLE_ALLIANCE, east=600, north=-300), lobau_flank),
            mv("bulow", "march", (4.5420, 50.7010), (4.5180, 50.6960), BULOW_AT_CSL),
            mv("napoleon", "march", FR["napoleon"]["at"], napoleon_lba),
        ],
        "notes": [
            note((4.4840, 50.6975), "13:15: Bülow's columns sighted"),
        ],
        "focus": ["grand-battery", "lobau", "bulow"],
    })

    # 5 ─ 13:30: d'Erlon's attack ───────────────────────────────────────────────
    hedge = 50.6800  # the columns reach the hedges of the sunken lane
    d_q = (4.4140, 50.6789)
    d_d = (4.4182, hedge)
    d_m = (4.4232, hedge + 0.0003)
    d_du = (4.4300, 50.6779)
    steps.append({
        "id": "derlon-attack",
        "title": "D'Erlon's grand attack",
        "time": "c. 13:30",
        "narrative": (
            "D'Erlon then sent about 14,000 infantry up the slope east of the road. His divisions advanced in echelon as "
            "enormous columns, each a block of eight or nine battalions stacked one behind another with a front of some two "
            "hundred men, hard to manoeuvre and slow to deploy. Quiot's division on the left split to surround La Haye "
            "Sainte, whose garrison held its walls. The columns drove in the skirmishers and reached the hedges of the "
            "sunken lane, where Bylandt's brigade gave way; Kempt's and Pack's brigades rose to fire, Picton was shot dead "
            "leading them forward, and for a few minutes the French were breaking into Wellington's left centre."
        ),
        "camera": {"center": [4.4195, 50.6775], "zoom": 13.75},
        "positions": {
            "quiot": pl(d_q, 352, 300, 80, shape="column", state="engaged"),
            "donzelot": pl(d_d, 350, 190, 70, shape="column", state="engaged"),
            "marcognet": pl(d_m, 350, 190, 70, shape="column", state="engaged"),
            "durutte": pl(d_du, 340, 190, 70, shape="column", state="engaged"),
            "picton": {"state": "wavering"},
            "lhs": {"state": "engaged"},
            "grand-battery": {"state": "ready"},
        },
        "moves": [
            mv("quiot", "attack", FR["quiot"]["at"], (4.4148, 50.6745), d_q),
            mv("donzelot", "attack", FR["donzelot"]["at"], (4.4190, 50.6765), d_d),
            mv("marcognet", "attack", FR["marcognet"]["at"], (4.4240, 50.6770), d_m),
            mv("durutte", "attack", FR["durutte"]["at"], d_du),
        ],
        "notes": [
            note((4.4168, 50.6823), "Picton killed", "death"),
            note((4.4195, 50.6808), "Bylandt's brigade gives way", "clash"),
        ],
        "terrain_state": {"la-haye-sainte": {"state": "contested"}},
        "focus": ["quiot", "donzelot", "marcognet", "durutte", "picton"],
    })

    # 6 ─ 14:00: the heavy cavalry charge ──────────────────────────────────────
    hc_guns = rel(GRAND_BATTERY, DERLON_FACE, ahead=100, right=40)  # among and just beyond the guns
    steps.append({
        "id": "heavy-cavalry",
        "title": "The charge of the heavy cavalry",
        "time": "c. 14:00",
        "narrative": (
            "Uxbridge, the allied cavalry commander, sent his two British heavy brigades over the crest. Somerset's Household "
            "Brigade, charging astride the road, swept away the cuirassiers screening the French flank and rode into the "
            "leading infantry; "
            "Ponsonby's Union Brigade burst through its own infantry and caught d'Erlon's columns while they were still "
            "struggling through the hedges. Packed too deep to form square, the French divisions collapsed: the Royals and "
            "the Scots Greys each took an eagle, and about 3,000 men were lost, over two thousand as prisoners. Only Durutte's "
            "division on the right kept its order. But the troopers would not rally, and on blown horses they galloped on "
            "across the valley into the Grand Battery, sabring its gunners."
        ),
        "camera": {"center": [4.4180, 50.6775], "zoom": 13.75},
        "positions": {
            "heavy-cav": pl(hc_guns, 168, 750, 110, state="engaged"),
            "quiot": pl((4.4142, 50.6748), 180, 300, 110, state="routed"),
            "donzelot": pl((4.4178, 50.6768), 175, 260, 110, state="routed"),
            "marcognet": pl((4.4238, 50.6772), 170, 260, 110, state="routed"),
            "durutte": pl((4.4300, 50.6768), 340, 220, 80, shape="square", state="engaged"),
            "picton": {"state": "engaged"},
            "grand-battery": {"state": "engaged"},
        },
        "moves": [
            mv("heavy-cav", "charge", AL["heavy-cav"]["at"], (4.4150, 50.6805), (4.4185, 50.6775), hc_guns),
            mv("quiot", "rout", d_q, (4.4142, 50.6748)),
            mv("donzelot", "rout", d_d, (4.4178, 50.6768)),
            mv("marcognet", "rout", d_m, (4.4238, 50.6772)),
        ],
        "notes": [
            note((4.4215, 50.6795), "Eagles of the 45e and 105e taken", "capture"),
            note(rel(GRAND_BATTERY, DERLON_FACE, ahead=-170, right=420), "British horse among the guns", "clash"),
        ],
        "terrain_state": {"la-haye-sainte": {"state": "held"}},
        "focus": ["heavy-cav"],
    })

    # 7 ─ 14:15: the counterstroke ─────────────────────────────────────────────
    milhaud_strike = rel(GRAND_BATTERY, DERLON_FACE, ahead=170, right=60)
    hc_back = (4.4115, 50.6852)
    steps.append({
        "id": "counterstroke",
        "title": "Cuirassiers and lancers strike back",
        "time": "c. 14:15",
        "narrative": (
            "Napoleon answered at once. Two of Milhaud's cuirassier brigades and Jacquinot's lancers fell on the scattered "
            "British horsemen in the valley. Ponsonby was caught by lancers and killed, the Scots Greys were all but "
            "destroyed, and the two brigades suffered losses they never made good before the survivors regained their own "
            "lines, covered by Vandeleur's light dragoons and the Dutch-Belgian cavalry. The Grand Battery was soon firing again, "
            "but d'Erlon's corps needed until about 16:00 to re-form, and its attack had used up Napoleon's best chance of "
            "breaking the allied left before the Prussians arrived."
        ),
        "camera": {"center": [4.4185, 50.6785], "zoom": 13.6},
        "positions": {
            "milhaud": pl(milhaud_strike, 340, 750, 120, state="engaged"),
            "heavy-cav": pl(hc_back, 180, 650, 100, state="wavering"),
            "light-cav": pl((4.4262, 50.6800), 200, 600, 90, state="engaged"),
            "quiot": pl(FR["quiot"]["at"], DERLON_FACE, 380, 100, state="wavering"),
            "donzelot": pl(FR["donzelot"]["at"], DERLON_FACE, 380, 100, state="wavering"),
            "marcognet": pl(FR["marcognet"]["at"], DERLON_FACE, 380, 100, state="wavering"),
            "durutte": pl(FR["durutte"]["at"], DERLON_FACE, 370, 90, shape="block", state="ready"),
            "grand-battery": {"state": "ready"},
        },
        "moves": [
            mv("milhaud", "charge", FR["milhaud"]["at"], rel(GRAND_BATTERY, DERLON_FACE, ahead=-60, right=250), milhaud_strike),
            mv("heavy-cav", "retreat", hc_guns, (4.4170, 50.6795), hc_back),
            mv("light-cav", "charge", AL["light-cav"]["at"], (4.4295, 50.6820), (4.4262, 50.6800)),
        ],
        "notes": [
            note((4.4232, 50.6742), "Ponsonby killed by French lancers", "death"),
        ],
        "focus": ["milhaud", "heavy-cav", "light-cav"],
    })

    # 8 ─ 16:00–17:30: Ney's cavalry against the squares ───────────────────────
    mil_crest = (4.4045, 50.6786)
    kel_crest = (4.4002, 50.6765)
    steps.append({
        "id": "cavalry-charges",
        "title": "Ney's cavalry against the squares",
        "time": "c. 16:00–17:30",
        "narrative": (
            "Ney, commanding the front line, took the wounded streaming to the rear of Wellington's centre for the start "
            "of a retreat. With little infantry left to hand, he sent Milhaud's cuirassiers and the Guard light cavalry up the "
            "open slope between Hougoumont and La Haye Sainte, then added Kellermann's corps and the Guard heavy cavalry: "
            "around 9,000 horsemen in wave after wave. The allied infantry formed squares in a chequerboard behind the "
            "crest; the gunners fired until the last moment, sheltered inside, and returned to their pieces as each wave "
            "ebbed. No square broke. Wellington fed the Brunswickers into the line, pushed Adam's brigade forward above "
            "Hougoumont and called Chassé's division in from Braine-l'Alleud. Without infantry or guns close behind them, "
            "the charges used up the French cavalry instead."
        ),
        "camera": {"center": [4.4040, 50.6800], "zoom": 13.75},
        "positions": {
            "milhaud": pl(mil_crest, 10, 750, 160, state="engaged"),
            "kellermann": pl(kel_crest, 12, 800, 160, state="engaged"),
            "maitland": pl((4.3975, 50.6826), 195, 340, 120, shape="square", subunits=2, state="engaged", label="Maitland's Guards (squares)"),
            "brunswick": pl((4.4027, 50.6822), 190, 340, 130, shape="square", subunits=4, lines=2, state="engaged", label="Brunswickers (squares)"),
            "alten": pl((4.4088, 50.6816), 185, 480, 140, shape="square", subunits=5, lines=2, state="engaged", label="Alten's division (squares)"),
            "adam": pl((4.3958, 50.6790), 165, 420, 120, shape="square", subunits=2, lines=2),
            "chasse": pl((4.3935, 50.6868), 170, 550, 220),
            "heavy-cav": pl((4.4075, 50.6855), 185, 600, 100, state="engaged"),
            "light-cav": pl(AL["light-cav"]["at"], 175, 700, 90, state="ready"),
            "jerome": {"state": "engaged"},
            "quiot": {"state": "ready"},
            "donzelot": {"state": "ready"},
            "marcognet": {"state": "ready"},
            "wellington": {"at": r6((4.4058, 50.6838))},
        },
        "moves": [
            mv("milhaud", "charge", milhaud_strike, (4.4130, 50.6730), (4.4080, 50.6750), mil_crest),
            mv("kellermann", "charge", FR["kellermann"]["at"], (4.4005, 50.6700), kel_crest),
            mv("brunswick", "advance", AL["brunswick"]["at"], (4.4028, 50.6822)),
            mv("adam", "advance", AL["adam"]["at"], (4.3958, 50.6790)),
            mv("chasse", "march", AL["chasse"]["at"], (4.3850, 50.6850), (4.3935, 50.6868)),
        ],
        "notes": [
            note((4.4040, 50.6845), "Allied infantry in squares; no square breaks"),
            note((4.4000, 50.6738), "Some 9,000 horsemen in successive waves", "label"),
        ],
        # Shelled on Napoleon's order during the afternoon, the château burned (its garrison held on).
        "terrain_state": {"hougoumont": {"state": "burning"}},
        "focus": ["milhaud", "kellermann", "maitland", "brunswick", "alten"],
    })

    # 9 ─ 16:30–18:00: Bülow at Plancenoit ─────────────────────────────────────
    lobau_back = (4.4325, 50.6662)
    yg_plancenoit = offset(PLANCENOIT, east=-60, north=40)
    steps.append({
        "id": "plancenoit",
        "title": "Bülow strikes at Plancenoit",
        "time": "c. 16:30–18:00",
        "narrative": (
            "While the horsemen fought on the ridge, Bülow's corps finished crossing the Lasne valley and came out of the "
            "Bois de Paris around 16:30, aiming at Plancenoit and the French rear. One brigade drove Lobau's men back from "
            "Frichermont while Hiller's brigade stormed Plancenoit, a village behind Napoleon's line and close to his only "
            "road of retreat. Napoleon sent the eight battalions of the Young Guard, who won the village back after savage "
            "fighting and then lost it again; two battalions of the Old Guard finally cleared it with the bayonet. Every man "
            "held at Plancenoit was a man Napoleon could not send against Wellington. Meanwhile Zieten's I Corps had set out "
            "from Wavre toward Ohain."
        ),
        "camera": {"center": [4.4480, 50.6740], "zoom": 12.55},
        "positions": {
            "bulow": pl(BULOW_ATTACK, 262, 1800, 300, state="engaged", frame=True),
            "blucher": {"frame": True},
            "lobau": pl(lobau_back, 82, 900, 150, state="engaged"),
            "young-guard": pl(yg_plancenoit, 90, 420, 380, state="engaged"),
            "zieten": pl(ZIETEN_GENVAL, 262, 120, 2000, shape="column", state="ready"),
            "milhaud": {"state": "wavering"},
            "kellermann": {"state": "wavering"},
        },
        "moves": [
            mv("bulow", "march", BULOW_AT_CSL, (4.4840, 50.6855), (4.4660, 50.6775), (4.4540, 50.6705), BULOW_ATTACK),
            mv(None, "attack", (4.4400, 50.6595), (4.4330, 50.6598), side="prussia"),
            mv(None, "attack", (4.4410, 50.6720), (4.4355, 50.6690), side="prussia"),
            mv("lobau", "retreat", lobau_flank, lobau_back),
            mv("young-guard", "march", FR["young-guard"]["at"], (4.4230, 50.6620), yg_plancenoit),
            mv("zieten", "march", ZIETEN_AT_WAVRE, (4.5500, 50.7120), ZIETEN_GENVAL, continues={"toward": r6(OHAIN), "label": "to Ohain"}),
        ],
        "notes": [
            note(offset(PLANCENOIT, north=-280), "Plancenoit lost and retaken", "clash"),
            note((4.4600, 50.6810), "Bülow emerges from the Bois de Paris, 16:30"),
        ],
        "terrain_state": {"plancenoit": {"held_by": "france", "state": "contested"}},
        "focus": ["bulow", "lobau", "young-guard"],
    })

    # 10 ─ 18:00–18:30: La Haye Sainte falls ───────────────────────────────────
    lhs_french = offset(LA_HAYE_SAINTE, north=-20)
    bach_fwd = (4.4010, 50.6748)
    lc_centre = (4.4050, 50.6876)
    mil_back = (4.4110, 50.6672)
    gren_wait = (4.4128, 50.6704)
    chas_wait = (4.4082, 50.6690)
    steps.append({
        "id": "la-haye-sainte",
        "title": "La Haye Sainte falls",
        "time": "c. 18:00–18:30",
        "narrative": (
            "Ordered once more to take La Haye Sainte, Ney sent in rallied men of d'Erlon's corps led by the 13e Léger, with "
            "engineers and guns. The German riflemen had fired off nearly all their ammunition and the farm fell; only a few "
            "dozen got back to the ridge. Ney pushed horse artillery and skirmishers up to the farm and the knoll beside it "
            "and raked the squares at close range, and Ompteda's battalion, sent down to retake the farm, was ridden over by "
            "cuirassiers. West of it, Bachelu's and part of Foy's infantry tried a late combined attack and were shot back by "
            "Adam's brigade. Wellington's centre was perilously thin, but Zieten's van was appearing near Ohain, freeing "
            "Vivian's and Vandeleur's light cavalry to ride across behind the line to the centre."
        ),
        "camera": {"center": [4.4250, 50.6785], "zoom": 13.0},
        "positions": {
            "lhs": {"state": "destroyed", "label": "La Haye Sainte (lost)"},
            "donzelot": pl(lhs_french, 0, 260, 160, state="engaged", label="Donzelot (13e Léger)"),
            "foy-bachelu": pl(bach_fwd, 12, 700, 160, state="engaged"),
            "alten": {"state": "wavering"},
            "milhaud": pl(mil_back, 10, 650, 140, state="wavering"),
            "kellermann": pl((4.4012, 50.6690), 10, 650, 140, state="wavering"),
            "light-cav": pl(lc_centre, 185, 650, 90, state="ready"),
            "zieten": pl(ZIETEN_OHAIN, 225, 700, 400, shape="block", frame=True),
            "durutte": pl((4.4330, 50.6785), 345, 380, 110, state="engaged"),
            "saxe-weimar": pl((4.4405, 50.6808), 175, 700, 200, state="wavering"),
            "guard-grenadiers": pl(gren_wait, 330, 260, 110),
            "guard-chasseurs": pl(chas_wait, 330, 320, 110),
            "wellington": {"at": r6((4.4090, 50.6832))},
        },
        "moves": [
            mv("donzelot", "attack", FR["donzelot"]["at"], (4.4145, 50.6745), lhs_french),
            mv("foy-bachelu", "attack", FR["foy-bachelu"]["at"], bach_fwd),
            mv("milhaud", "retreat", mil_crest, mil_back),
            mv("kellermann", "retreat", kel_crest, (4.4012, 50.6690)),
            mv("light-cav", "march", AL["light-cav"]["at"], (4.4200, 50.6858), lc_centre),
            mv("zieten", "march", ZIETEN_GENVAL, OHAIN, ZIETEN_OHAIN),
            mv("guard-grenadiers", "march", FR["guard-grenadiers"]["at"], (4.4120, 50.6660), gren_wait),
            mv("guard-chasseurs", "march", FR["guard-chasseurs"]["at"], (4.4090, 50.6650), chas_wait),
            mv(None, "fire", (4.4105, 50.6790), (4.4085, 50.6812), side="france", target="alten"),
        ],
        "notes": [
            note(offset(LA_HAYE_SAINTE, east=-170, north=-30), "KGL out of ammunition: farm lost", "capture"),
            note((4.4060, 50.6800), "Ompteda's battalion destroyed", "death"),
        ],
        "terrain_state": {"la-haye-sainte": {"held_by": "france", "state": "captured"}},
        "focus": ["donzelot", "lhs", "alten", "zieten"],
    })

    # 11 ─ 19:30: the Imperial Guard attacks ───────────────────────────────────
    gren_top = (4.4060, 50.6790)
    chas_top = (4.4004, 50.6797)
    adam_flank = (4.3972, 50.6797)
    chasse_charge = (4.4055, 50.6808)
    zieten_pap = (4.4392, 50.6795)
    alten_guard = (4.4080, 50.6824)  # west of the Brussels road, clear of Picton's line
    steps.append({
        "id": "imperial-guard",
        "title": "The Imperial Guard attacks",
        "time": "c. 19:30",
        "narrative": (
            "With Plancenoit held for the moment, Napoleon committed his last reserve: five battalions of the Middle Guard in "
            "battalion squares, guns between them, with Old Guard battalions behind. Ney led them up the slope obliquely "
            "toward the allied right centre, while d'Erlon's rallied men pressed again east of the road. The grenadiers on "
            "the right drove back Colin Halkett's battered brigade until Chassé's fresh Dutch-Belgian division brought a "
            "horse battery onto their flank and charged with the bayonet. Further west the chasseurs topped the crest into "
            "point-blank volleys from Maitland's Foot Guards, who had been lying down out of the guns' sight. As the last "
            "chasseur battalion came on, Colborne swung the 52nd Light Infantry out of line onto its left flank and broke "
            "it. At Papelotte, Zieten's leading brigade, steered back to Wellington's flank by the liaison officer Müffling "
            "after a moment's hesitation, was coming into action against Durutte."
        ),
        "camera": {"center": [4.4050, 50.6782], "zoom": 13.75},
        "positions": {
            "guard-grenadiers": pl(gren_top, 335, 240, 100, state="engaged"),
            "guard-chasseurs": pl(chas_top, 330, 300, 100, state="engaged"),
            "old-guard": pl((4.4112, 50.6718), 335, 300, 120, label="Old Guard (2nd line)"),
            "maitland": pl((4.3998, 50.6816), 185, 380, 50, shape="line", subunits=1, state="engaged", label="Maitland's Foot Guards"),
            "chasse": pl(chasse_charge, 190, 360, 140, state="engaged"),
            "alten": pl(alten_guard, 185, 460, 120, shape="block", subunits=1, lines=1, state="wavering", label="Alten's division"),
            "brunswick": pl((4.4025, 50.6842), 185, 380, 110, shape="block", subunits=1, lines=1, label="Brunswickers"),
            "adam": pl(adam_flank, 100, 420, 60, shape="line", subunits=1, lines=1, state="engaged"),
            "quiot": pl((4.4160, 50.6775), 350, 300, 100, state="engaged"),
            "marcognet": pl((4.4235, 50.6782), 350, 300, 100, state="engaged"),
            "zieten": pl(zieten_pap, 230, 700, 300, state="engaged"),
            "durutte": pl((4.4330, 50.6778), 40, 380, 110, state="engaged"),
            "saxe-weimar": pl((4.4425, 50.6815), 190, 500, 160, state="ready"),
            "napoleon": {"at": r6(NAP_LBA)},
        },
        "moves": [
            mv("guard-grenadiers", "attack", gren_wait, (4.4085, 50.6745), gren_top),
            mv("guard-chasseurs", "attack", chas_wait, (4.4040, 50.6750), chas_top),
            mv("old-guard", "march", FR["old-guard"]["at"], (4.4135, 50.6650), (4.4112, 50.6718)),
            mv("chasse", "charge", (4.3935, 50.6868), (4.4030, 50.6850), chasse_charge),
            mv("adam", "flank", *arc((4.3958, 50.6790), adam_flank, -40, n=4)),
            mv("zieten", "attack", ZIETEN_OHAIN, (4.4450, 50.6830), zieten_pap),
            mv("quiot", "attack", FR["quiot"]["at"], (4.4160, 50.6775)),
            mv("marcognet", "attack", FR["marcognet"]["at"], (4.4235, 50.6782)),
        ],
        "notes": [
            note((4.3985, 50.6835), "Maitland's Guards rise and fire", "clash"),
            note((4.3935, 50.6808), "Colborne's 52nd wheels onto the flank", "clash"),
            note((4.4085, 50.6838), "Chassé's division charges the grenadiers", "clash"),
        ],
        "terrain_state": {"papelotte": {"held_by": None, "state": "contested"}},
        "focus": ["guard-grenadiers", "guard-chasseurs", "maitland", "adam", "chasse"],
    })

    # 12 ─ 20:00: the Guard recoils, general advance, Plancenoit falls ─────────
    adv = {
        "alten": (4.4085, 50.6748),
        "maitland": (4.4015, 50.6758),
        "chasse": (4.4045, 50.6775),
        "brunswick": (4.3995, 50.6788),
        "adam": (4.4065, 50.6722),
        "picton": (4.4195, 50.6772),
        "light-cav": (4.4085, 50.6705),
        "zieten": (4.4265, 50.6742),
        "bulow": (4.4350, 50.6615),
    }
    og_square = offset(LA_HAYE_SAINTE, east=-60, north=-480)
    steps.append({
        "id": "general-advance",
        "title": "The Guard falls back; the general advance",
        "time": "c. 20:00",
        "narrative": (
            "The cry that the Guard was falling back ran along the French line, and with Zieten's Prussians breaking in near "
            "Papelotte, panic spread from the right. Wellington rode to the crest, raised his hat and sent the whole allied "
            "line forward, with Vivian's and Vandeleur's fresh light cavalry ahead of it. Guard battalions rallied in squares "
            "south of La Haye Sainte to cover the retreat, but Adam's brigade and the hussars swept them back toward La Belle "
            "Alliance. At Plancenoit the Prussians attacked for the third time while Pirch's II Corps worked round through "
            "the Chantelet wood to the south; the Guard defenders gave way, and the village changed hands for the last time. "
            "Reille's, d'Erlon's and Lobau's corps dissolved into crowds streaming south down the Charleroi road."
        ),
        "camera": {"center": [4.4190, 50.6700], "zoom": 12.95},
        "light": "dusk",
        "positions": {
            **{u: pl(p, 175 if u not in ("zieten", "bulow") else (235 if u == "zieten" else 268), state="engaged")
               for u, p in adv.items()},
            "bulow": pl(adv["bulow"], 268, 1300, 300, state="engaged"),
            "guard-grenadiers": pl((4.4120, 50.6700), 180, 220, 120, state="routed"),
            "guard-chasseurs": pl((4.4060, 50.6698), 180, 260, 120, state="routed"),
            "old-guard": pl(og_square, 340, 220, 140, shape="square", state="engaged", label="Old Guard squares"),
            "jerome": pl((4.3920, 50.6625), 190, 520, 200, state="routed"),
            "foy-bachelu": pl((4.4020, 50.6655), 185, 800, 180, state="routed"),
            "kellermann": pl((4.3975, 50.6640), 190, 600, 140, state="routed"),
            "milhaud": pl((4.4055, 50.6630), 185, 600, 140, state="routed"),
            "quiot": pl((4.4165, 50.6682), 190, 300, 120, state="routed"),
            "donzelot": pl((4.4200, 50.6700), 190, 260, 140, state="routed"),
            "marcognet": pl((4.4250, 50.6705), 200, 300, 120, state="routed"),
            "durutte": pl((4.4290, 50.6700), 210, 380, 120, state="routed"),
            "grand-battery": {"state": "routed", "label": "Grand Battery (abandoned)"},
            "lobau": pl((4.4235, 50.6615), 250, 800, 160, state="routed"),
            "young-guard": pl((4.4250, 50.6560), 240, 420, 300, state="routed"),
            "hougoumont": {"state": "ready"},
            "lhs": {"state": "hidden"},
            "wellington": {"at": r6((4.4075, 50.6770))},
        },
        "moves": [
            mv("guard-grenadiers", "rout", gren_top, (4.4120, 50.6700)),
            mv("guard-chasseurs", "rout", chas_top, (4.4060, 50.6698)),
            mv("old-guard", "march", (4.4112, 50.6718), og_square),
            mv("alten", "advance", alten_guard, adv["alten"]),
            mv("maitland", "advance", (4.3998, 50.6816), adv["maitland"]),
            mv("adam", "advance", adam_flank, (4.4030, 50.6760), adv["adam"]),
            mv("light-cav", "charge", lc_centre, (4.4060, 50.6790), adv["light-cav"]),
            mv("picton", "advance", AL["picton"]["at"], adv["picton"]),
            mv("zieten", "attack", zieten_pap, adv["zieten"]),
            mv("bulow", "attack", BULOW_ATTACK, (4.4400, 50.6630), adv["bulow"]),
            mv(None, "flank", MARANSART, (4.4480, 50.6560), (4.4370, 50.6545), (4.4310, 50.6570), side="prussia",
               label="Pirch's II Corps"),
            mv("jerome", "rout", jerome_wood, (4.3920, 50.6625)),
            mv("foy-bachelu", "rout", bach_fwd, (4.4020, 50.6655)),
            mv("lobau", "rout", lobau_back, (4.4235, 50.6615)),
            mv("young-guard", "rout", yg_plancenoit, (4.4250, 50.6560)),
            mv("durutte", "rout", (4.4330, 50.6778), (4.4290, 50.6700)),
            mv("quiot", "rout", (4.4160, 50.6775), (4.4165, 50.6682)),
            mv("donzelot", "rout", lhs_french, (4.4200, 50.6700)),
            mv("milhaud", "rout", mil_back, (4.4055, 50.6630)),
        ],
        "notes": [
            note((4.4140, 50.6735), "\"La Garde recule!\": panic spreads"),
            note(offset(PLANCENOIT, north=-260), "Plancenoit falls for the last time", "capture"),
        ],
        "terrain_state": {
            "plancenoit": {"held_by": "prussia", "state": "captured"},
            "papelotte": {"held_by": "prussia", "state": "held"},
            "la-haye-sainte": {"held_by": "allied", "state": "held"},
        },
    })

    # 13 ─ 20:30–23:00: rout and pursuit ───────────────────────────────────────
    og_lba = offset(BELLE_ALLIANCE, east=-120, north=-250)
    nap_flight = (4.4268, 50.6372)
    steps.append({
        "id": "pursuit",
        "title": "Rout and pursuit",
        "time": "c. 20:30–23:00",
        "narrative": (
            "Two Old Guard battalions in square beside La Belle Alliance were the last French formations on the field. "
            "Napoleon sheltered in one until his staff persuaded him to go, and both squares drew off in fair order into the "
            "dusk while everything else broke. Around 21:00 Wellington and Blücher met near the inn. The exhausted allied "
            "army halted on the field, and the Prussian cavalry under Gneisenau took up the pursuit by moonlight, driving the "
            "fugitives through Genappe, where Napoleon's carriage was captured. The French left almost all their guns behind "
            "and lost some 25,000 killed and wounded and thousands of prisoners, against about 17,000 allied and 7,000 "
            "Prussian casualties. Napoleon abdicated four days later."
        ),
        "camera": {"center": [4.4290, 50.6425], "zoom": 11.7},
        "positions": {
            "old-guard": pl(og_lba, 0, 260, 150, shape="square", state="wavering", label="Last Old Guard squares"),
            "napoleon": {"at": r6(nap_flight)},
            "wellington": {"at": r6(offset(BELLE_ALLIANCE, east=-80, north=60))},
            "blucher": {"at": r6(offset(BELLE_ALLIANCE, east=80, north=60))},
            "bulow": pl((4.4180, 50.6505), 200, 1200, 300, state="engaged"),
            "zieten": pl(offset(BELLE_ALLIANCE, east=650, north=120), 220, 700, 300, state="ready"),
            "adam": pl(offset(ROSSOMME, east=-300, north=500), 180, 420, 80, state="ready"),
            "light-cav": pl(offset(ROSSOMME, east=-250, north=150), 180, 650, 90, state="ready"),
            "grand-battery": {"state": "destroyed", "label": "Abandoned guns"},
            "guard-grenadiers": {"state": "hidden"},
            "guard-chasseurs": {"state": "hidden"},
            "jerome": {"state": "hidden"},
            "foy-bachelu": {"state": "hidden"},
            "kellermann": {"state": "hidden"},
            "milhaud": {"state": "hidden"},
            "quiot": {"state": "hidden"},
            "donzelot": {"state": "hidden"},
            "marcognet": {"state": "hidden"},
            "durutte": {"state": "hidden"},
            "lobau": {"state": "destroyed"},
            "young-guard": {"state": "destroyed"},
        },
        "moves": [
            mv("old-guard", "retreat", og_square, og_lba),
            mv("napoleon", "retreat", NAP_LBA, og_lba, (4.4131, 50.6603), (4.4156, 50.6513), (4.4196, 50.6468), nap_flight,
               continues={"toward": r6(CHARLEROI), "label": "to Charleroi"}),
            mv("blucher", "march", adv["bulow"], (4.4230, 50.6650), offset(BELLE_ALLIANCE, east=80, north=60)),
            mv("bulow", "pursuit", adv["bulow"], (4.4250, 50.6560), (4.4180, 50.6505)),
            mv(None, "pursuit", *[offset(p, east=150) for p in CHARLEROI_ROAD[11:17]], side="prussia",
               label="Gneisenau's pursuit"),
            mv("wellington", "march", (4.4075, 50.6770), (4.4100, 50.6720), offset(BELLE_ALLIANCE, east=-80, north=60)),
            mv("adam", "advance", adv["adam"], offset(ROSSOMME, east=-300, north=500)),
            mv("light-cav", "pursuit", adv["light-cav"], offset(ROSSOMME, east=-250, north=150)),
            mv("zieten", "advance", adv["zieten"], offset(BELLE_ALLIANCE, east=650, north=120)),
        ],
        "notes": [
            note(offset(BELLE_ALLIANCE, north=180), "c. 21:00: Wellington and Blücher meet", "event"),
            note(offset(GENAPPE, north=400), "Napoleon's carriage taken at Genappe", "capture"),
        ],
    })

    return {
        "schema": 2,
        "slug": "battle-of-waterloo",
        "kind": "battle",
        "entity": {"name": "Battle of Waterloo", "wikidata": "Q48314"},
        "title": "Battle of Waterloo",
        "date_label": "18 June 1815",
        "year": 1815,
        "intro": (
            "On Sunday 18 June 1815 Napoleon's Armée du Nord met the Duke of Wellington's multinational army on the open "
            "farmland south of Waterloo, some fifteen kilometres from Brussels. Two days earlier Napoleon had beaten the "
            "Prussians at Ligny while Marshal Ney fought Wellington at Quatre Bras. On the 17th both allied armies fell back "
            "north, the Prussians to Wavre rather than east toward home, so they stayed within a day's march of each other. "
            "Wellington took up a low ridge at Mont-Saint-Jean astride the Brussels road, garrisoned three farms in front of "
            "it and kept most of his troops out of sight behind its crest, trusting Blücher's promise to march across from "
            "Wavre and join him. Napoleon, with Marshal Grouchy and a third of the army away chasing the Prussians, had to "
            "break Wellington before they came. The day became a race between the French assaults on the ridge and the slow "
            "Prussian march across the Lasne valley."
        ),
        "outcome": (
            "A decisive Coalition victory: the repulse of the Imperial Guard and the Prussian capture of Plancenoit broke "
            "the French army, and Napoleon abdicated four days later."
        ),
        "uncertainty": (
            "Witnesses' watches disagreed: the first attack on Hougoumont is timed anywhere from 10:00 to 11:30, and La Haye "
            "Sainte fell between 18:00 and 18:30; this map uses the times most modern accounts give. Strengths and losses "
            "vary by source. The Grand Battery's exact position is debated; it is drawn on a spur in front of d'Erlon's "
            "corps. Which Guard battalions attacked at 19:30, and in squares or columns, is still argued; this follows the "
            "five Middle Guard battalions in squares. Farms are placed at today's buildings; Rossomme, Smohain and the 1815 "
            "Bois de Paris are approximate, and the Lion's Mound later cut away the ridge west of the crossroads. Each block "
            "stands for many battalions, squares or batteries."
        ),
        "sources": [
            {"title": "Battle of Waterloo — Wikipedia", "url": "https://en.wikipedia.org/wiki/Battle_of_Waterloo", "kind": "web"},
            {"title": "Order of battle of the Waterloo Campaign — Wikipedia",
             "url": "https://en.wikipedia.org/wiki/Order_of_battle_of_the_Waterloo_Campaign", "kind": "web"},
            {"title": "Hougoumont — Wikipedia", "url": "https://en.wikipedia.org/wiki/Hougoumont", "kind": "web"},
            {"title": "La Haye Sainte — Wikipedia", "url": "https://en.wikipedia.org/wiki/La_Haye_Sainte", "kind": "web"},
            {"title": "Wellington's Waterloo dispatch to Earl Bathurst, 19 June 1815", "kind": "primary"},
            {"title": "OpenStreetMap (farms, roads, streams) and SRTM elevation", "url": "https://www.openstreetmap.org", "kind": "web"},
        ],
        "sides": [
            {
                "id": "allied",
                "name": "Anglo-allied army",
                "color": "#c0392b",
                "polity": {"name": "United Kingdom of Great Britain and Ireland", "wikidata": "Q174193"},
                "commanders": [
                    {"name": "Duke of Wellington", "wikidata": "Q131691", "role": "commander-in-chief"},
                    {"name": "Earl of Uxbridge", "role": "cavalry"},
                    {"name": "Prince of Orange", "role": "I Corps"},
                    {"name": "Lord Hill", "role": "II Corps"},
                ],
                "strength": "c. 68,000–73,000; 156 guns (British, KGL, Dutch-Belgian, Hanoverian, Brunswick, Nassau)",
                # Mixed formations (Alten's and Picton's divisions, the light cavalry) have no contingent.
                "contingents": [
                    {"id": "british", "name": "British", "color": "#c0392b"},
                    {"id": "kgl-hanoverian", "name": "King's German Legion and Hanoverians"},
                    {"id": "dutch-belgian", "name": "Netherlanders (Dutch-Belgian)"},
                    {"id": "brunswick", "name": "Brunswickers"},
                    {"id": "nassau", "name": "Nassauers"},
                ],
                "losses": "c. 15,000–17,000 killed, wounded and missing",
            },
            {
                "id": "prussia",
                "name": "Prussian army",
                "color": "#27272a",
                "polity": {"name": "Kingdom of Prussia", "wikidata": "Q27306"},
                "commanders": [
                    {"name": "Gebhard Leberecht von Blücher", "wikidata": "Q153522", "role": "commander-in-chief"},
                    {"name": "August von Gneisenau", "role": "chief of staff"},
                    {"name": "Friedrich Wilhelm von Bülow", "role": "IV Corps"},
                    {"name": "Hans Ernst Karl von Zieten", "role": "I Corps"},
                    {"name": "Georg von Pirch", "role": "II Corps"},
                ],
                "strength": "c. 48,000 engaged by evening",
                "losses": "c. 7,000 killed and wounded",
            },
            {
                "id": "france",
                "name": "Armée du Nord",
                "color": "#1d4ed8",
                "polity": {"name": "First French Empire", "wikidata": "Q71084"},
                "commanders": [
                    {"name": "Napoleon", "wikidata": "Q517", "role": "commander-in-chief"},
                    {"name": "Michel Ney", "wikidata": "Q40756", "role": "field commander"},
                    {"name": "Jean-de-Dieu Soult", "role": "chief of staff"},
                    {"name": "Honoré Reille", "role": "II Corps"},
                    {"name": "Jean-Baptiste Drouet, Comte d'Erlon", "role": "I Corps"},
                    {"name": "Georges Mouton, Comte de Lobau", "role": "VI Corps"},
                ],
                "strength": "c. 72,000–74,000; c. 250 guns",
                "losses": "c. 24,000–26,000 killed and wounded, 6,000–7,000 captured; c. 15,000 deserted afterwards",
            },
        ],
        "units": UNITS,
        "terrain": TERRAIN,
        "steps": steps,
    }


UNITS = [
    # ── Anglo-allied ──
    {"id": "wellington", "side": "allied", "kind": "commander", "label": "Wellington", "wikidata": "Q131691"},
    {"id": "hougoumont", "side": "allied", "contingent": "british", "kind": "infantry", "label": "Hougoumont garrison", "strength": "c. 1,500, later more",
     "commander": "James Macdonell, later Francis Home",
     "note": "Guards light companies, then Byng's Coldstream and 3rd Guards; Nassauers and Hanoverian jäger in wood and orchard"},
    {"id": "maitland", "side": "allied", "contingent": "british", "kind": "infantry", "label": "Maitland's Foot Guards", "strength": "c. 1,500–1,900",
     "commander": "Peregrine Maitland", "note": "2nd and 3rd battalions, 1st Foot Guards (Cooke's division)"},
    {"id": "adam", "side": "allied", "contingent": "british", "kind": "light_infantry", "label": "Adam's brigade (52nd)", "strength": "c. 2,600",
     "commander": "Frederick Adam; John Colborne (52nd)",
     "note": "52nd and 71st Light Infantry and two battalions of the 95th Rifles (Clinton's 2nd Division)"},
    {"id": "brunswick", "side": "allied", "contingent": "brunswick", "kind": "infantry", "label": "Brunswick contingent", "strength": "c. 5,900",
     "commander": "Johann Elias Olfermann", "note": "Their Duke had been killed at Quatre Bras two days earlier"},
    {"id": "alten", "side": "allied", "kind": "infantry", "label": "Alten's division", "strength": "c. 7,000",
     "commander": "Charles Alten",
     "note": "Colin Halkett's British, Ompteda's King's German Legion and Kielmansegge's Hanoverian brigades"},
    {"id": "lhs", "side": "allied", "contingent": "kgl-hanoverian", "kind": "light_infantry", "label": "La Haye Sainte (KGL)", "strength": "c. 400, later c. 800",
     "commander": "George Baring",
     "note": "2nd Light Battalion, King's German Legion, later reinforced; 95th Rifles in the sandpit opposite"},
    {"id": "picton", "side": "allied", "kind": "infantry", "label": "Picton & Bylandt", "strength": "c. 10,000",
     "commander": "Thomas Picton",
     "note": "Kempt's and Pack's British brigades, Bylandt's Dutch-Belgian brigade, Best's and Vincke's Hanoverians"},
    {"id": "heavy-cav", "side": "allied", "contingent": "british", "kind": "heavy_cavalry", "label": "Household & Union Bdes", "strength": "c. 2,000",
     "commander": "Earl of Uxbridge; Lord Edward Somerset, Sir William Ponsonby",
     "note": "Life Guards, Blues, King's Dragoon Guards; Royals, Scots Greys, Inniskillings"},
    {"id": "light-cav", "side": "allied", "kind": "light_cavalry", "label": "Vivian & Vandeleur", "strength": "c. 2,500",
     "commander": "Hussey Vivian, John Ormsby Vandeleur", "note": "British and KGL light dragoons and hussars"},
    {"id": "saxe-weimar", "side": "allied", "contingent": "nassau", "kind": "light_infantry", "label": "Saxe-Weimar's Nassauers", "strength": "c. 4,000",
     "commander": "Prince Bernhard of Saxe-Weimar", "note": "Holding Papelotte, La Haie, Smohain and Frichermont"},
    {"id": "chasse", "side": "allied", "contingent": "dutch-belgian", "kind": "infantry", "label": "Chassé's division", "strength": "c. 6,500",
     "commander": "David Hendrik Chassé", "note": "3rd Netherlands Division: Detmers' and d'Aubremé's brigades"},
    # ── French ──
    {"id": "napoleon", "side": "france", "kind": "commander", "label": "Napoleon", "wikidata": "Q517"},
    {"id": "jerome", "side": "france", "kind": "infantry", "label": "Jérôme's division", "strength": "c. 6,500",
     "commander": "Jérôme Bonaparte", "note": "Reille's II Corps: Bauduin's and Soye's brigades"},
    {"id": "foy-bachelu", "side": "france", "kind": "infantry", "label": "Foy & Bachelu", "strength": "c. 9,000",
     "commander": "Honoré Reille", "note": "The rest of II Corps; Piré's lancers watched the far left"},
    {"id": "kellermann", "side": "france", "kind": "heavy_cavalry", "label": "Kellermann's cuirassiers", "strength": "c. 5,700",
     "commander": "François Étienne de Kellermann", "note": "III Cavalry Corps, with Guyot's Guard heavy cavalry behind"},
    {"id": "quiot", "side": "france", "kind": "infantry", "label": "Quiot's division", "strength": "c. 4,000",
     "commander": "Joachim Quiot", "note": "I Corps; one brigade against La Haye Sainte, one (Bourgeois) east of the road"},
    {"id": "donzelot", "side": "france", "kind": "infantry", "label": "Donzelot's division", "strength": "c. 5,100",
     "commander": "François-Xavier Donzelot", "note": "I Corps; its 13e Léger led the capture of La Haye Sainte"},
    {"id": "marcognet", "side": "france", "kind": "infantry", "label": "Marcognet's division", "strength": "c. 3,900",
     "commander": "Pierre-Louis Binet de Marcognet", "note": "I Corps; lost the eagle of the 45e Ligne"},
    {"id": "durutte", "side": "france", "kind": "infantry", "label": "Durutte's division", "strength": "c. 3,900",
     "commander": "Pierre François Durutte", "note": "I Corps; fought for Papelotte and La Haie all afternoon"},
    {"id": "grand-battery", "side": "france", "kind": "artillery", "label": "Grand Battery (c. 80 guns)",
     "note": "Massed guns of I, II and VI Corps, many of them 12-pounders"},
    {"id": "milhaud", "side": "france", "kind": "heavy_cavalry", "label": "Milhaud's cuirassiers", "strength": "c. 5,800",
     "commander": "Édouard Jean-Baptiste Milhaud",
     "note": "IV Cavalry Corps, with Lefebvre-Desnoëttes' Guard lancers and chasseurs; Jacquinot's lancers on the far right"},
    {"id": "lobau", "side": "france", "kind": "infantry", "label": "Lobau's VI Corps", "strength": "c. 6,500 foot, 2,300 horse",
     "commander": "Georges Mouton, Comte de Lobau", "note": "With Domon's and Subervie's light cavalry divisions"},
    {"id": "young-guard", "side": "france", "kind": "infantry", "label": "Young Guard", "strength": "c. 4,500",
     "commander": "Philibert Guillaume Duhesme", "note": "Eight battalions of tirailleurs and voltigeurs; Duhesme mortally wounded"},
    {"id": "guard-grenadiers", "side": "france", "kind": "infantry", "label": "Middle Guard grenadiers", "strength": "c. 1,100",
     "commander": "Louis Friant", "note": "1st/3rd and 4th Grenadiers, in battalion squares"},
    {"id": "guard-chasseurs", "side": "france", "kind": "infantry", "label": "Middle Guard chasseurs", "strength": "c. 1,900",
     "commander": "Claude-Étienne Michel", "note": "1st/3rd, 2nd/3rd and 4th Chasseurs; Michel was killed"},
    {"id": "old-guard", "side": "france", "kind": "infantry", "label": "Old Guard", "strength": "eight battalions",
     "commander": "Antoine Drouot", "note": "1st and 2nd Grenadiers and Chasseurs; two battalions went to Plancenoit"},
    # ── Prussian ──
    {"id": "blucher", "side": "prussia", "kind": "commander", "label": "Blücher", "wikidata": "Q153522"},
    {"id": "bulow", "side": "prussia", "kind": "infantry", "label": "Bülow's IV Corps", "strength": "c. 30,000",
     "commander": "Friedrich Wilhelm von Bülow",
     "note": "Losthin's, Hiller's, Hacke's and Ryssel's brigades with reserve cavalry; Pirch's II Corps followed"},
    {"id": "zieten", "side": "prussia", "kind": "infantry", "label": "Zieten's I Corps", "strength": "c. 18,000 (its van engaged)",
     "commander": "Hans Ernst Karl von Zieten", "note": "Steinmetz's brigade and the reserve cavalry led the way in"},
]

TERRAIN = [
    {"id": "msj-ridge", "kind": "ridge", "label": "Mont-Saint-Jean ridge (Ohain road)", "line": path(*OHAIN_ROAD)},
    {"id": "ohain-lane", "kind": "road", "label": "Road to Ohain", "line": path(*OHAIN_LANE_EAST)},
    {"id": "french-ridge", "kind": "ridge", "label": "La Belle Alliance ridge", "line": path(*FRENCH_RIDGE)},
    {"id": "charleroi-road", "kind": "road", "label": "Brussels–Charleroi road", "line": path(*CHARLEROI_ROAD)},
    {"id": "nivelles-road", "kind": "road", "label": "Nivelles road", "line": path(*NIVELLES_ROAD)},
    {"id": "lasne", "kind": "stream", "label": "Lasne", "line": path(*LASNE)},
    {"id": "smohain-brook", "kind": "stream", "line": path(*SMOHAIN_BROOK)},
    {"id": "hougoumont-wood", "kind": "woods", "label": "Hougoumont wood",
     "area": ellipse(offset(HOUGOUMONT, east=-10, north=-250), 210, 170)},
    {"id": "bois-de-paris", "kind": "woods", "label": "Bois de Paris", "area": ellipse((4.4600, 50.6772), 720, 620, rotate=-15)},
    {"id": "hougoumont", "kind": "farm", "label": "Hougoumont", "at": r6(HOUGOUMONT)},
    {"id": "la-haye-sainte", "kind": "farm", "label": "La Haye Sainte", "at": r6(LA_HAYE_SAINTE)},
    {"id": "papelotte", "kind": "farm", "label": "Papelotte", "at": r6(PAPELOTTE)},
    {"id": "belle-alliance", "kind": "building", "label": "La Belle Alliance", "at": r6(BELLE_ALLIANCE)},
    {"id": "msj-farm", "kind": "farm", "label": "Mont-Saint-Jean farm", "at": r6(MSJ_FARM)},
    {"id": "mont-saint-jean", "kind": "village", "label": "Mont-Saint-Jean", "at": r6(MONT_SAINT_JEAN)},
    {"id": "rossomme", "kind": "farm", "label": "Rossomme", "at": r6(ROSSOMME)},
    {"id": "le-caillou", "kind": "building", "label": "Le Caillou", "at": r6(LE_CAILLOU)},
    {"id": "frichermont", "kind": "building", "label": "Frichermont", "at": r6(FRICHERMONT)},
    {"id": "smohain", "kind": "village", "label": "Smohain", "at": r6(SMOHAIN)},
    {"id": "plancenoit", "kind": "village", "label": "Plancenoit", "at": r6(PLANCENOIT)},
    {"id": "chapelle-saint-lambert", "kind": "village", "label": "Chapelle-Saint-Lambert", "at": r6(CHAPELLE_ST_LAMBERT)},
    {"id": "ohain", "kind": "village", "label": "Ohain", "at": r6(OHAIN)},
    {"id": "wavre", "kind": "town", "label": "Wavre", "at": r6(WAVRE)},
    {"id": "braine-lalleud", "kind": "town", "label": "Braine-l'Alleud", "at": r6(BRAINE)},
    {"id": "genappe", "kind": "town", "label": "Genappe", "at": r6(GENAPPE)},
    {"id": "lions-mound", "kind": "label", "label": "Lion's Mound (built 1820s)", "at": r6(LION)},
]
