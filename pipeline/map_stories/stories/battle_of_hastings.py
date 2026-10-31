"""Battle of Hastings, 14 October 1066 — map story builder.

Reconstruction: the traditional (English Heritage) site, with Harold's shield
wall on the ridge where Battle Abbey now stands, facing south over a wet
valley, and William's three divisions formed across the valley after marching
from Hastings over Telham Hill.

Anchors (all positions are metres east/north of ALTAR):
- ALTAR: OSM "Senlac Hill" summit beside the abbey church's high altar, where
  Harold is said to have fallen (0.48717, 50.91429).
- Ridge, valley floor and spur: SRTM 30 m profiles (crest 80–86 m just south of
  the abbey; valley floor 45–52 m 350–500 m south; a near-level saddle at
  67–70 m south-east of the crest carrying the Hastings road up from Telham).
- Telham Hill: SRTM high ground 130–143 m, 2–3 km south-east of the abbey.
- Caldbec Hill: SRTM summit c. 108 m, 0.9 km north.
- Road: OSM A2100 (London Road / High Street / Upper Lake / Lower Lake /
  Battle Hill / Hastings Road / The Ridge West), simplified at 25 m.
- Oakwood Gill (one proposed site of the Malfosse): OSM waterway.
"""

from __future__ import annotations

from pipeline.map_stories.geo import along, bearing, distance, ellipse, length, mid, offset, rel

ALTAR = (0.48717, 50.91429)
HASTINGS = (0.58503, 50.85602)  # Hastings Castle hill, site of the Norman fort


def P(e: float, n: float) -> list[float]:
    return offset(ALTAR, east=e, north=n)


def ring(e: float, n: float, rx: float, ry: float, rotate: float = 0.0, k: int = 24) -> list[list[float]]:
    return ellipse(P(e, n), rx, ry, rotate, n=k)


# OSM A2100 from Caldbec Hill (north) through Battle and over Telham Hill to
# Baldslow on the Hastings ridge (south-east), simplified at 25 m.
ROAD = [
    [0.481425, 50.920386], [0.482307, 50.918431], [0.485588, 50.915795], [0.486667, 50.915155],
    [0.490501, 50.914371], [0.491882, 50.912885], [0.492077, 50.911987], [0.493613, 50.910823],
    [0.496078, 50.909697], [0.499963, 50.91001], [0.507049, 50.907979], [0.514024, 50.902685],
    [0.51497, 50.90145], [0.520187, 50.900512], [0.522887, 50.899621], [0.528452, 50.896807],
    [0.538966, 50.892931], [0.545733, 50.891287], [0.552604, 50.891465], [0.555029, 50.890791],
    [0.556208, 50.890025],
]
JUNCTION = ROAD[8]  # foot of Battle Hill, where the road meets the saddle below the English left
TELHAM_ROAD = ROAD[11:16]  # the road along the top of Telham Hill, head (north-west) first

# OSM Oakwood Gill, extended west to the second OSM point of the stream.
OAKWOOD_GILL = [[0.485193, 50.925575], [0.484392, 50.92578], [0.483728, 50.926521], [0.481971, 50.926753], [0.48051, 50.9271]]


def front_block(a: tuple[float, float], b: tuple[float, float], depth: float) -> dict:
    """A formation whose front runs from local point a to b (left to right as
    seen from behind), facing perpendicular to that front."""
    pa, pb = P(*a), P(*b)
    facing = (bearing(pa, pb) + 90) % 360
    return {"at": rel(mid(pa, pb), facing, ahead=-depth / 2), "facing": round(facing), "width": round(distance(pa, pb)), "depth": depth}


def facing_off(target: dict, depth: float, gap: float = 4.0, width: float | None = None, slide: float = 0.0) -> dict:
    """A formation standing `gap` metres in front of `target` and facing it
    (in contact when gap is small). `slide` shifts it along the front (to the
    target's right, as the target sees it)."""
    at = rel(target["at"], target["facing"], ahead=target["depth"] / 2 + gap + depth / 2, right=slide)
    out = {"at": at, "facing": round((target["facing"] + 180) % 360), "depth": depth}
    if width:
        out["width"] = width
    return out


class Story:
    def __init__(self) -> None:
        self.cur: dict[str, dict] = {}
        self.steps: list[dict] = []

    def step(self, sid: str, title: str, time: str, narrative: str, **extra) -> None:
        self.steps.append({"id": sid, "title": title, "time": time, "narrative": " ".join(narrative.split()), "positions": {}, "moves": [], "notes": [], **extra})

    @property
    def s(self) -> dict:
        return self.steps[-1]

    def at(self, uid: str) -> list[float]:
        return self.cur[uid]["at"]

    def put(self, uid: str, move: str | None = None, via: tuple | list = (), mlabel: str | None = None, start: list[float] | None = None, **pl) -> None:
        """Place a unit (only the keys that change) and, with `move`, draw its
        arrow from where it stood (or `start`, for a unit entering the field)
        through `via` to its new point."""
        prev = start or self.cur.get(uid, {}).get("at")
        self.s["positions"][uid] = dict(pl)
        if "at" in pl:
            self.cur.setdefault(uid, {}).pop("with", None)
        self.cur.setdefault(uid, {}).update(pl)
        if move:
            mv = {"unit": uid, "type": move, "path": [prev, *[list(v) for v in via], pl["at"]]}
            if mlabel:
                mv["label"] = mlabel
            self.s["moves"].append(mv)

    def pin(self, uid: str, host: str) -> None:
        """Pin a marker to a unit (drawn just behind it, moving with it)."""
        self.s["positions"][uid] = {"with": host}
        self.cur[uid] = {"with": host, "at": self.cur[host]["at"]}

    def markers(self) -> None:
        """End of step: pinned markers follow their hosts. Where a host made a
        long move, give the marker the same arrow (it is drawn over the host's)."""
        for uid, pl in self.cur.items():
            host = pl.get("with")
            if not host:
                continue
            prev, now = pl["at"], self.cur[host]["at"]
            host_move = next((m for m in self.s["moves"] if m.get("unit") == host), None)
            if host_move and distance(prev, now) > 800:
                self.s["moves"].append({"unit": uid, "type": host_move["type"], "path": [prev, *host_move["path"][1:]]})
            pl["at"] = now

    def fire(self, uid: str, target: list[float], mlabel: str | None = None) -> None:
        mv = {"unit": uid, "type": "fire", "path": [self.at(uid), target]}
        if mlabel:
            mv["label"] = mlabel
        self.s["moves"].append(mv)

    def note(self, at: list[float], text: str, kind: str = "event") -> None:
        self.s["notes"].append({"at": at, "text": text, "kind": kind})


MARKERS_WITH = {"harold": "housecarls", "william": "norman-knights", "alan": "breton-horse", "eustace": "french-horse"}


def build() -> dict:
    st = Story()

    # ── 1. The approach ─────────────────────────────────────────────────────
    st.step(
        "approach",
        "Two armies close in",
        "Night of 13 October to c. 8:00",
        """Harold's army, rushed south from London barely two weeks after destroying a
        Norwegian invasion at Stamford Bridge, spent the night assembling at a landmark the
        English chronicle calls the hoary apple tree, probably on Caldbec Hill. Before dawn
        William led his men out of their fortified camp at Hastings and north along the
        ridgeway. On Telham Hill, about two and a half kilometres short of the English, the
        column halted so that the knights could put on their mail and the divisions could
        sort themselves into order. The road they had come up was the only way out of the
        Norman beachhead, and Harold was already sitting across it.""",
        camera={"center": P(3300, -2700), "zoom": 11.6},
    )
    st.put("fyrd-west", at=P(-300, 905), facing=175, width=200, depth=45)
    st.put("housecarls", at=P(-110, 880), facing=175, width=160, depth=40)
    st.put("fyrd-east", at=P(70, 850), facing=175, width=200, depth=45)
    st.pin("harold", "housecarls")
    column = ["french-archers", "french-foot", "french-horse", "norman-archers", "norman-foot", "norman-knights", "breton-archers", "breton-foot", "breton-horse"]
    column_t: dict[str, float] = {}
    for i, uid in enumerate(column):
        t = (i + 0.5) / len(column)
        column_t[uid] = t
        here, ahead = along(TELHAM_ROAD, t), along(TELHAM_ROAD, max(0.0, t - 0.03))
        st.put(uid, at=here, facing=round(bearing(here, ahead)), width=22, depth=105, shape="column")
    for uid in ("william", "alan", "eustace"):
        st.pin(uid, MARKERS_WITH[uid])
    st.put("baggage", at=along(ROAD[15:18], 0.35))
    st.s["moves"].append(
        {
            "side": "normans",
            "type": "march",
            "label": "From the camp at Hastings",
            "path": [list(HASTINGS), [0.5785, 50.8655], [0.5668, 50.8785], [0.5562, 50.8900], *ROAD[19:10:-1]],
        }
    )
    st.note(P(-110, 1010), "English muster at the hoary apple tree")
    st.note(along(TELHAM_ROAD, 0.5), "Normans halt on Telham Hill to arm")
    st.markers()

    # ── 2. Deployment ───────────────────────────────────────────────────────
    st.step(
        "deployment",
        "The shield wall and the three divisions",
        "c. 8:00–9:00",
        """The English came south along the ridge and locked shields on its crest, where
        Battle Abbey now stands, in a dense line about 750 metres long. The housecarls of the
        king and his brothers, armoured professionals with long Danish axes, held the centre
        around Harold's two standards, the Dragon of Wessex and his own Fighting Man; the shire
        levies of the fyrd filled out the wings. William's army filed down off Telham and spread
        across the valley in three divisions: Bretons, with men of Anjou, Poitou and Maine, on
        the left under Alan the Red; Normans in the centre under the duke; and French and
        Flemish contingents on the right under William fitzOsbern and Eustace of Boulogne. Each
        division put its bowmen and crossbowmen in front, armoured foot behind them and the
        mounted knights at the back.""",
        camera={"center": P(200, -400), "zoom": 14.4},
    )
    W, A, B, E = (-480, -75), (-200, -58), (60, -48), (330, -15)
    for uid, (a, b), via in (
        ("fyrd-west", (W, A), [P(-330, 420)]),
        ("housecarls", (A, B), [P(-90, 420)]),
        ("fyrd-east", (B, E), [P(120, 420)]),
    ):
        st.put(uid, move="march", via=via, **front_block(a, b, 16))

    telham_cum = [length(TELHAM_ROAD[: j + 1]) for j in range(len(TELHAM_ROAD))]

    def deploy(uid: str, at: list[float], facing: float, width: float, depth: float, via: list) -> None:
        """March a unit from its place in the column down the road to the
        junction below Battle Hill, then out to its place in the line."""
        d = column_t[uid] * length(TELHAM_ROAD)
        ahead = [TELHAM_ROAD[j] for j in range(len(TELHAM_ROAD) - 1, -1, -1) if telham_cum[j] < d - 30]
        st.put(uid, move="march", via=[*ahead, ROAD[10], ROAD[9], JUNCTION, *via], at=at, facing=facing, width=width, depth=depth, shape="block")

    b_arch = P(-380, -545)
    n_arch = P(10, -480)
    f_arch = P(410, -330)
    deploy("breton-archers", b_arch, 5, 240, 8, [P(150, -700), P(-250, -690)])
    deploy("breton-foot", rel(b_arch, 5, ahead=-42), 5, 230, 14, [P(150, -720), P(-250, -720)])
    deploy("breton-horse", rel(b_arch, 5, ahead=-110), 5, 200, 22, [P(150, -760), P(-250, -770)])
    deploy("norman-archers", n_arch, 0, 320, 8, [P(260, -560)])
    deploy("norman-foot", rel(n_arch, 0, ahead=-42), 0, 320, 16, [P(260, -590)])
    deploy("norman-knights", rel(n_arch, 0, ahead=-112), 0, 300, 24, [P(260, -630)])
    deploy("french-archers", f_arch, 335, 240, 8, [])
    deploy("french-foot", rel(f_arch, 335, ahead=-42), 335, 230, 14, [])
    deploy("french-horse", rel(f_arch, 335, ahead=-110), 335, 200, 22, [])
    st.put("baggage", move="march", via=ROAD[15:10:-1], at=P(820, -760))
    st.markers()

    # ── 3. Archery ──────────────────────────────────────────────────────────
    st.step(
        "archery",
        "Arrows against the shields",
        "c. 9:00",
        """Trumpets opened the fighting at about nine o'clock. The Norman archers walked up
        the slope to within easy range and shot into the English line, but shooting uphill at
        men crouched behind overlapping shields did little damage: arrows stuck in the boards
        or sailed over the crest. Harold's army had very few archers, so almost nothing came
        back down that the Normans could gather up and shoot again, and their quivers soon
        began to run low.""",
        focus=["breton-archers", "norman-archers", "french-archers"],
    )
    st.put("baggage", state="hidden")  # stays at the foot of Telham Hill, off the fighting field
    st.put("breton-archers", move="advance", at=P(-350, -205), facing=2)
    st.put("norman-archers", move="advance", at=P(-50, -175), facing=0)
    st.put("french-archers", move="advance", at=P(285, -140), facing=340)
    st.fire("breton-archers", P(-335, -82))
    st.fire("norman-archers", P(-60, -66))
    st.fire("french-archers", P(220, -48))
    st.note(P(-190, -125), "Arrows lodge in shields or fly over the crest")

    # ── 4. The foot assault ─────────────────────────────────────────────────
    st.step(
        "foot-assault",
        "The foot climb the hill",
        "c. 9:30–10:30",
        """The archers fell back and the armoured spearmen of all three divisions laboured up
        the hill to close with the shield wall. The English met them with thrusting spears,
        axes, javelins and stones hurled from the rear ranks, and a two-handed Danish axe could
        split a shield and the man behind it. The Bretons on the left had the steepest climb
        and the wettest ground to cross at the foot of the slope, and made the least headway.""",
        focus=["breton-foot", "norman-foot", "french-foot"],
    )
    st.put("breton-archers", at=b_arch)
    st.put("norman-archers", at=n_arch)
    st.put("french-archers", at=f_arch)
    fw, hc, fe = (st.cur[u] for u in ("fyrd-west", "housecarls", "fyrd-east"))
    st.put("breton-foot", move="attack", state="engaged", **facing_off(fw, 14, width=230))
    st.put("norman-foot", move="attack", state="engaged", **facing_off(hc, 16, width=300))
    st.put("french-foot", move="attack", state="engaged", **facing_off(fe, 14, width=230))
    for uid in ("fyrd-west", "housecarls", "fyrd-east"):
        st.put(uid, state="engaged")
    st.note(rel(hc["at"], hc["facing"], ahead=70), "Spears, axes and stones meet the attack", "clash")

    # ── 5. The knights ride up ──────────────────────────────────────────────
    st.step(
        "cavalry",
        "The knights ride up in support",
        "c. 10:30–11:00",
        """With the foot making no impression, William sent his mounted knights up the slope
        behind them. Riding uphill in small troops they could not build up speed, and no horse
        would hurl itself onto a solid hedge of shields and blades, so the riders jabbed and
        threw their lances, wheeled away and came back again. In places the English line bent,
        but nowhere did it break.""",
        focus=["breton-horse", "norman-knights", "french-horse"],
    )
    for foot, horse, target, depth in (
        ("breton-foot", "breton-horse", fw, 22),
        ("norman-foot", "norman-knights", hc, 24),
        ("french-foot", "french-horse", fe, 22),
    ):
        st.put(horse, move="charge", state="engaged", **facing_off(target, depth))
        st.put(foot, state="ready", **facing_off(target, st.cur[foot]["depth"], gap=70))
    st.markers()
    st.note(rel(hc["at"], hc["facing"], ahead=95, right=-60), "Horses balk at the wall of shields")

    # ── 6. The Breton rout ──────────────────────────────────────────────────
    st.step(
        "breton-rout",
        "The Breton wing gives way",
        "Late morning",
        """The left broke first. Horse and foot of the Breton division turned and fled back
        down the slope, and part of the English right came off the ridge after them to cut
        down the fugitives in the valley. Alarm ran along the whole Norman line as men began
        to give ground, and a rumour spread that the duke himself had been killed. Whether
        Harold ordered the pursuit or his men simply broke ranks is not known; only one late
        writer says he told them to stand fast.""",
        focus=["breton-horse", "breton-foot", "west-pursuers"],
    )
    st.put("breton-horse", move="rout", via=[P(-420, -380)], at=P(-480, -660), facing=195, state="routed")
    st.put("breton-foot", move="rout", via=[P(-300, -380)], at=P(-330, -700), facing=185, state="routed")
    st.put("breton-archers", move="rout", at=P(-420, -790), facing=190, state="routed")
    st.put("west-pursuers", move="pursuit", start=P(-360, -90), via=[P(-390, -300)], at=P(-420, -455), facing=190, width=180, depth=30)
    st.put("fyrd-west", at=rel(fw["at"], fw["facing"], right=-30), width=220, state="ready")
    st.put("norman-knights", move="retreat", at=P(-40, -330), facing=0, state="wavering")
    st.put("norman-foot", move="retreat", at=P(-50, -390), state="wavering")
    st.put("french-horse", move="retreat", at=P(400, -255), facing=335, state="wavering")
    st.put("french-foot", move="retreat", at=P(430, -320), facing=335, state="wavering")
    st.put("housecarls", state="ready")
    st.put("fyrd-east", state="ready")
    st.markers()
    st.note(P(-30, -420), "Rumour sweeps the line: the duke is dead")

    # ── 7. William shows his face; the hillock ──────────────────────────────
    hillock = P(-640, -300)
    st.step(
        "hillock",
        "William lifts his helmet",
        "Late morning",
        """William rode across the front of his wavering men, pushed his helmet back so they
        could see his face and shouted that he was alive; the Bayeux Tapestry shows Bishop Odo
        rallying the young horsemen at the same moment. Knights from the centre wheeled left
        into the flank of the English who had come down the hill. Cut off from their line, the
        pursuers gathered on a small hillock and were surrounded and killed there. The Tapestry
        puts the deaths of Harold's brothers Gyrth and Leofwine just before this scene, although
        William of Poitiers says their bodies lay close to the king's.""",
        focus=["norman-knights", "west-pursuers", "william"],
    )
    st.put("norman-knights", move="charge", via=[P(-300, -400)], at=rel(hillock, 100, ahead=125), facing=280, width=200, state="engaged")
    st.put("breton-horse", move="charge", via=[P(-640, -560)], at=rel(hillock, 190, ahead=115), facing=10, width=180, state="engaged")
    st.put("west-pursuers", move="retreat", at=hillock, facing=150, width=120, depth=95, shape="circle", state="destroyed")
    st.put("breton-foot", at=P(-360, -610), facing=5, state="ready")
    st.put("breton-archers", at=P(-380, -680), facing=5, state="ready")
    st.put("norman-foot", state="ready")
    st.put("french-horse", state="ready")
    st.put("french-foot", state="ready")
    st.markers()
    st.note(P(-330, -455), "William bares his face to show he lives")
    st.note(rel(hillock, 0, ahead=55), "English cut down on a hillock", "clash")

    # ── 8. The feigned flight ───────────────────────────────────────────────
    st.step(
        "feigned-flight",
        "The feigned flight",
        "Early afternoon",
        """After a lull in which both armies re-formed, the Normans turned the morning's near
        disaster into a ruse. A body of horsemen rode up against the English line, then
        pretended to break and galloped back down the slope. Remembering how the Bretons had
        run, a group of Englishmen left the wall to chase them. Where on the field this happened
        is not recorded; the map shows it on the right, where the gentler saddle suited
        horses.""",
        focus=["french-horse", "feint-followers"],
        camera={"center": P(320, -300), "zoom": 15.2},
    )
    st.put("west-pursuers", state="hidden")  # the dead on the hillock: shown in the previous step
    st.put("norman-knights", at=P(-30, -300), facing=0, width=300, state="ready")
    st.put("breton-horse", at=P(-380, -520), facing=5, width=200, state="ready")
    st.put("breton-foot", at=P(-370, -450), facing=5)
    st.put("norman-foot", at=P(-40, -380))
    fe_now = st.cur["fyrd-east"]
    st.put("french-foot", at=P(570, -565), facing=335)  # the right's foot and archers re-form up the spur
    st.put("french-archers", at=P(665, -470), facing=335)
    st.put("french-horse", move="feint", via=[P(300, -105), P(385, -115)], at=P(530, -470), facing=150, mlabel="Feigned flight")
    st.put("feint-followers", move="pursuit", start=P(250, -50), via=[P(300, -200)], at=P(420, -365), facing=150, width=150, depth=30)
    st.put("fyrd-east", at=rel(fe_now["at"], fe_now["facing"], right=-25), width=230)
    st.markers()
    st.note(P(560, -330), "Horsemen feign flight to draw the English out")

    # ── 9. The trap closes ──────────────────────────────────────────────────
    st.step(
        "trap",
        "The trap closes",
        "Early afternoon",
        """Once their pursuers were well clear of the ridge, the fleeing riders wheeled about
        while other knights rode in from the flank, and the English were caught in the open and
        killed. William of Poitiers says the ruse was played twice, and most historians accept
        that feigned flights, a manoeuvre known to Norman and Breton horsemen, were used that
        day. Each time the shield wall closed up behind its losses, levies of the fyrd taking
        the places of fallen housecarls, but the line was growing shorter and thinner.""",
        focus=["french-horse", "norman-knights", "feint-followers"],
        camera={"center": P(320, -300), "zoom": 15.2},
    )
    ff = st.cur["feint-followers"]["at"]
    st.put("feint-followers", at=ff, width=90, depth=60, shape="circle", state="destroyed")
    st.put("french-horse", move="charge", via=[P(560, -420)], at=rel(ff, 135, ahead=70), facing=315, state="engaged")
    st.put("norman-knights", move="charge", via=[P(160, -360)], at=rel(ff, 260, ahead=110), facing=80, width=220, state="engaged")
    st.markers()
    st.note(rel(ff, 0, ahead=60), "Riders wheel and cut down the pursuers", "clash")

    # ── 10. The long afternoon ──────────────────────────────────────────────
    st.step(
        "attrition",
        "The long afternoon",
        "c. 14:00–16:00",
        """Through the afternoon William alternated his arms: archers to wear the line down,
        then foot and horse together to test it. Twelfth-century writers say he had the bowmen
        shoot high so that their arrows dropped onto the ranks behind the shields, though the
        accounts written soon after the battle do not mention it. The duke fought in the thick
        of it and had two or, by another account, three horses killed under him. The English,
        exhausted and bleeding, held a front that had shrunk inwards along the crest.""",
    )
    W2, A2, B2, E2 = (-420, -68), (-180, -56), (50, -48), (280, -24)
    for uid, (a, b) in (("fyrd-west", (W2, A2)), ("housecarls", (A2, B2)), ("fyrd-east", (B2, E2))):
        st.put(uid, state="engaged", **front_block(a, b, 14))
    fw, hc, fe = (st.cur[u] for u in ("fyrd-west", "housecarls", "fyrd-east"))
    st.put("feint-followers", state="hidden")
    st.put("breton-foot", move="attack", state="engaged", **facing_off(fw, 14, width=220))
    st.put("norman-foot", move="attack", state="engaged", **facing_off(hc, 16, width=240))
    st.put("french-foot", move="attack", state="engaged", **facing_off(fe, 14, width=210))
    st.put("breton-archers", at=P(-470, -170), facing=10)
    st.put("norman-archers", at=P(-210, -175), facing=0)
    st.put("french-archers", at=P(320, -175), facing=330)
    st.fire("breton-archers", P(-330, -20), mlabel="Shot high")
    st.fire("norman-archers", P(-110, 0))
    st.fire("french-archers", P(170, 10))
    st.put("breton-horse", at=P(-330, -265), facing=0, state="ready")
    st.put("norman-knights", at=P(-30, -250), facing=0, width=260, state="ready")
    st.put("french-horse", at=P(300, -260), facing=335, state="ready")
    st.markers()
    st.note(P(80, -320), "William loses horses killed under him")

    # ── 11. Harold falls ────────────────────────────────────────────────────
    st.step(
        "harold-falls",
        "Harold falls",
        "Late afternoon",
        """Late in the day Harold was killed beside his standards on the crest. The Bayeux
        Tapestry shows one warrior with an arrow at his eye and another cut down by a horseman
        beneath the words announcing the king's death; whether Harold is one figure, the other
        or both is still argued over. With the king dead the English wings broke and began to
        flee north, while the royal household fought on around his body until it was
        overwhelmed. The high altar of Battle Abbey was later raised over the spot.""",
        focus=["housecarls", "harold", "norman-knights"],
    )
    st.put("housecarls", at=P(-15, 0), facing=175, width=130, depth=110, shape="circle")
    st.put("harold", at=P(-5, 5), state="destroyed")
    st.put("norman-knights", move="charge", via=[P(-40, -140)], at=P(-30, -85), facing=0, width=200, state="engaged")
    st.put("breton-horse", move="charge", via=[P(-330, -120)], at=P(-250, -10), facing=60, width=160, state="engaged")
    st.put("french-horse", move="charge", via=[P(260, -110)], at=P(170, 20), facing=290, width=160, state="engaged")
    st.put("fyrd-west", move="rout", via=[P(-330, 40)], at=P(-360, 230), facing=330, state="routed")
    st.put("fyrd-east", move="rout", via=[P(200, 60)], at=P(170, 260), facing=350, state="routed")
    st.put("breton-foot", at=P(-330, -95), state="ready")
    st.put("norman-foot", at=P(-60, -150), state="ready")
    st.put("french-foot", at=P(250, -90), state="ready")
    st.markers()
    st.note(P(60, -25), "Harold is killed beside his standards", "death")

    # ── 12. Rout and the Malfosse ───────────────────────────────────────────
    gill = P(-250, 1365)
    st.step(
        "malfosse",
        "Rout and the Malfosse",
        "Dusk, c. 17:00",
        """As the light failed the English streamed back over Caldbec Hill towards the
        woods of the Weald, the way they had come, with Norman horsemen at their heels. At a
        place later remembered as the Malfosse, the evil ditch, a band of them turned at a
        steep ravine or old earthwork; pursuing riders tumbled into it in the dusk and Eustace
        of Boulogne was badly wounded before the English were overcome. William spent the
        night on the battlefield among the dead, and Harold's Fighting Man banner was later
        sent to the pope.""",
        camera={"center": P(-150, 720), "zoom": 13.9},
    )
    st.put("housecarls", state="destroyed")
    st.put("fyrd-west", move="rout", via=[P(-480, 650)], at=P(-640, 1150), facing=330, width=200)
    st.put("fyrd-east", move="rout", via=[P(-80, 650), P(-140, 1000)], at=rel(gill, 0, ahead=40), facing=180, width=170, depth=30, state="engaged", label="Rearguard at the Malfosse")
    st.put("norman-knights", move="pursuit", via=[P(-90, 400), P(-150, 900)], at=rel(gill, 180, ahead=90), facing=0, width=180, state="engaged")
    st.put("french-horse", move="pursuit", via=[P(100, 500), P(0, 1000)], at=P(-30, 1215), facing=320, width=150, state="engaged")
    st.put("breton-horse", move="pursuit", via=[P(-420, 500)], at=P(-560, 960), facing=330, width=150, state="ready")
    st.put("william", at=P(40, -40))
    st.markers()
    st.note(rel(gill, 270, ahead=120), "Malfosse: riders plunge into a hidden ditch", "clash")
    st.note(P(80, 1170), "Eustace of Boulogne badly wounded")
    st.note(P(60, -10), "Harold's standard taken", "capture")

    return {
        "schema": 1,
        "slug": "battle-of-hastings",
        "kind": "battle",
        "entity": {"name": "Battle of Hastings", "wikidata": "Q83224"},
        "title": "Battle of Hastings",
        "date_label": "14 October 1066",
        "year": 1066,
        "intro": (
            "On 14 October 1066 King Harold II of England, crowned only that January, met William, Duke of "
            "Normandy, on a ridge about 11 kilometres north-west of Hastings. William had crossed the Channel and "
            "landed at Pevensey on 28 September with Normans, Bretons, Frenchmen and Flemings to enforce his claim "
            "to the English throne, then moved east to Hastings and fortified a base there. Harold, who had wiped "
            "out a Norwegian invasion at Stamford Bridge near York on 25 September, marched south at speed and "
            "planted his army across the only road out of the Norman beachhead. The result was an unusually long "
            "medieval battle: a whole day in which an English army fighting entirely on foot behind a shield wall "
            "held a hilltop against a Norman army that combined archers, armoured infantry and mounted knights."
        ),
        "outcome": (
            "Decisive Norman victory: Harold and his brothers Gyrth and Leofwine were killed, the English army was "
            "destroyed, and William was crowned king of England on Christmas Day 1066."
        ),
        "uncertainty": (
            "This map follows the traditional site, with the English on the ridge now occupied by Battle Abbey. "
            "Some writers put the fight on Caldbec Hill, 1.5 km north, or near Crowhurst, 5 km south, and a 2013 "
            "landscape study argued that the main Norman thrust came up the Hastings road from the south-east. "
            "Army sizes (each perhaps 7,000–8,000), frontages, the split into units and the clock times are "
            "reconstructions. The hillock, the feigned flights and the Malfosse are not located by the sources: "
            "here the hillock sits on the spur below the English right and the Malfosse at Oakwood Gill, one of "
            "several proposed sites. Gyrth and Leofwine may have died in the morning or at the end. High-angle "
            "archery is reported only by 12th-century writers. The ponds in the valley are later abbey works."
        ),
        "sources": [
            {"title": "William of Poitiers, Gesta Guillelmi (c. 1071–1077)", "kind": "primary"},
            {"title": "Carmen de Hastingae Proelio (attributed to Guy of Amiens)", "kind": "primary"},
            {"title": "The Bayeux Tapestry", "kind": "primary"},
            {"title": "Anglo-Saxon Chronicle, annal for 1066", "kind": "primary"},
            {"title": "Orderic Vitalis, Ecclesiastical History (the Malfosse)", "kind": "primary"},
            {"title": "Battle of Hastings — Wikipedia", "url": "https://en.wikipedia.org/wiki/Battle_of_Hastings", "kind": "web"},
            {
                "title": "Where Did the Battle of Hastings Happen? — English Heritage",
                "url": "https://www.english-heritage.org.uk/visit/places/1066-battle-of-hastings-abbey-and-battlefield/history-and-stories/battle-of-hastings-location",
                "kind": "web",
            },
            {
                "title": "History of Battle Abbey and Battlefield — English Heritage",
                "url": "https://www.english-heritage.org.uk/visit/places/1066-battle-of-hastings-abbey-and-battlefield/history-and-stories/history/",
                "kind": "web",
            },
            {"title": "Hastings 1066 — Battlefields Trust resource centre", "url": "https://www.battlefieldstrust.com/resource-centre/battlepageview.asp?PageId=536", "kind": "web"},
            {"title": "Terrain: OpenStreetMap (roads, streams) and SRTM 30 m elevation", "url": "https://www.openstreetmap.org/#map=15/50.912/0.490", "kind": "web"},
        ],
        "sides": [
            {
                "id": "english",
                "name": "English army",
                "color": "#b91c1c",
                "polity": {"name": "Kingdom of England", "wikidata": "Q179876"},
                "commanders": [
                    {"name": "Harold Godwinson", "wikidata": "Q159597", "role": "King of England (killed)"},
                    {"name": "Gyrth Godwinson", "role": "Earl of East Anglia, Harold's brother (killed)"},
                    {"name": "Leofwine Godwinson", "role": "Earl, Harold's brother (killed)"},
                ],
                "strength": "c. 7,000–8,000 (estimates range 5,000–13,000)",
                "losses": "Perhaps 4,000 killed, including the king and his brothers",
            },
            {
                "id": "normans",
                "name": "Norman army",
                "color": "#1d4ed8",
                "polity": {"name": "Duchy of Normandy", "wikidata": "Q2219635"},
                "commanders": [
                    {"name": "William the Conqueror", "wikidata": "Q37594", "role": "Duke of Normandy, commander-in-chief"},
                    {"name": "Odo of Bayeux", "role": "Bishop of Bayeux, William's half-brother"},
                    {"name": "Alan the Red", "role": "Breton division (left)"},
                    {"name": "William fitzOsbern", "role": "Franco-Flemish division (right)"},
                    {"name": "Eustace II of Boulogne", "role": "Franco-Flemish division (right)"},
                ],
                "strength": "c. 8,000, about a quarter mounted (estimates 7,000–12,000)",
                "losses": "Perhaps 2,000 killed",
            },
        ],
        "units": [
            {"id": "fyrd-west", "side": "english", "kind": "infantry", "label": "Fyrd (west wing)", "strength": "c. 2,700",
             "note": "Shire levies stiffened by thegns; lighter armour than the housecarls"},
            {"id": "housecarls", "side": "english", "kind": "heavy_infantry", "label": "Housecarls", "strength": "c. 2,000",
             "note": "Household troops of Harold and his brothers: mail, big shields, two-handed Danish axes"},
            {"id": "fyrd-east", "side": "english", "kind": "infantry", "label": "Fyrd (east wing)", "strength": "c. 2,700",
             "note": "Shire levies stiffened by thegns; javelin men and a few archers stood behind the wall"},
            {"id": "west-pursuers", "side": "english", "kind": "infantry", "label": "English pursuers", "strength": "Several hundred?",
             "note": "Men of the right wing who chased the routed Bretons down the hill"},
            {"id": "feint-followers", "side": "english", "kind": "infantry", "label": "English pursuers", "strength": "Several hundred?",
             "note": "Drawn off the ridge by a feigned flight"},
            {"id": "harold", "side": "english", "kind": "commander", "label": "Harold", "wikidata": "Q159597",
             "note": "Fought on foot beside his standards at the crest"},
            {"id": "breton-archers", "side": "normans", "kind": "archers", "label": "Breton archers", "strength": "c. 500"},
            {"id": "breton-foot", "side": "normans", "kind": "infantry", "label": "Breton foot", "strength": "c. 1,000",
             "note": "Bretons with men of Anjou, Poitou and Maine"},
            {"id": "breton-horse", "side": "normans", "kind": "heavy_cavalry", "label": "Breton horse", "strength": "c. 500"},
            {"id": "norman-archers", "side": "normans", "kind": "archers", "label": "Norman archers & crossbows", "strength": "c. 1,000",
             "note": "Self bows, some crossbows and perhaps a few slingers"},
            {"id": "norman-foot", "side": "normans", "kind": "infantry", "label": "Norman foot", "strength": "c. 2,000",
             "note": "Spearmen in mail or quilted coats with round or kite shields"},
            {"id": "norman-knights", "side": "normans", "kind": "heavy_cavalry", "label": "Norman knights", "strength": "c. 1,000",
             "note": "Mail hauberks, kite shields and lances; fought in small troops"},
            {"id": "french-archers", "side": "normans", "kind": "archers", "label": "Franco-Flemish archers", "strength": "c. 500"},
            {"id": "french-foot", "side": "normans", "kind": "infantry", "label": "Franco-Flemish foot", "strength": "c. 1,000",
             "note": "Frenchmen with men of Picardy, Boulogne and Flanders"},
            {"id": "french-horse", "side": "normans", "kind": "heavy_cavalry", "label": "Franco-Flemish horse", "strength": "c. 500"},
            {"id": "william", "side": "normans", "kind": "commander", "label": "William", "wikidata": "Q37594"},
            {"id": "alan", "side": "normans", "kind": "commander", "label": "Alan the Red"},
            {"id": "eustace", "side": "normans", "kind": "commander", "label": "Eustace of Boulogne"},
            {"id": "baggage", "side": "normans", "kind": "baggage", "label": "Clergy & servants",
             "note": "Waited at the foot of Telham Hill"},
        ],
        "terrain": [
            {"id": "telham-hill", "kind": "hill", "label": "Telham Hill (Blackhorse Hill)", "area": ring(2300, -1750, 820, 420, 15)},
            {"id": "caldbec-hill", "kind": "hill", "label": "Caldbec Hill", "area": ring(-120, 900, 300, 220)},
            {"id": "senlac-ridge", "kind": "ridge", "label": "Senlac ridge",
             "line": [P(-600, -25), P(-420, -10), P(-200, 8), P(0, 18), P(200, 22), P(380, 5)]},
            {"id": "valley-marsh", "kind": "marsh", "label": "Wet ground",
             "area": [P(-30, -395), P(-160, -400), P(-330, -415), P(-500, -430), P(-600, -470), P(-560, -505),
                      P(-430, -500), P(-280, -480), P(-140, -458), P(-30, -440)]},
            {"id": "valley-stream", "kind": "stream",
             "line": [P(40, -405), P(-120, -428), P(-250, -445), P(-420, -472), P(-560, -540), P(-660, -680), P(-750, -850)]},
            {"id": "hillock", "kind": "hill", "label": "Hillock (approx.)", "area": ring(-640, -300, 55, 42, 30, k=16)},
            {"id": "woods-west", "kind": "woods", "label": "Woods", "area": ring(-820, 130, 190, 260, 20, k=16)},
            {"id": "woods-east", "kind": "woods", "label": "Woods", "area": ring(640, 260, 200, 180, -20, k=16)},
            {"id": "road", "kind": "road", "label": "Road to Hastings", "line": ROAD},
            {"id": "oakwood-gill", "kind": "stream", "label": "Oakwood Gill (Malfosse?)", "line": OAKWOOD_GILL},
            {"id": "standards", "kind": "label", "label": "Standards: Dragon & Fighting Man", "at": P(-15, 30)},
            {"id": "hastings", "kind": "town", "label": "Hastings (Norman camp)", "at": list(HASTINGS)},
        ],
        "steps": st.steps,
    }
