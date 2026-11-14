"""Battle of Megiddo, 21st day of month 1 of Shemu, year 23 of Thutmose III (traditionally 16 April 1457 BC).

Anchors: Tel Megiddo (OSM archaeological site, 35.18419,32.58543); Nahal Iron stream (the Wadi Ara / Aruna
route, OSM); Nahal Kishon (OSM); Taanach and Yokneam villages (OSM). Sources: Wikipedia, drawing on Tjaneni's
Karnak Annals.
Orientation: the Egyptians came out of the Aruna ravine from the south-west and formed up facing north-east,
the left (southern) wing towards Taanach, the right (northern) wing north-west of the city; the Canaanite
coalition stood between them and the walls of Megiddo, facing south-west. Exact line positions are
reconstructed (conjectural); the Annals place only the wings relative to Taanach and the Qina brook.
"""
from pipeline.map_stories.geo import arc, ellipse, offset
from pipeline.map_stories.layout import Story, local_frame, ent

ANCHOR = (35.18419, 32.58543)
P = local_frame(ANCHOR)

NAHAL_IRON = [[35.14774, 32.53283], [35.13901, 32.52531], [35.13353, 32.52305], [35.12927, 32.52189], [35.1277, 32.51918],
              [35.12282, 32.51732], [35.1216, 32.5145], [35.11744, 32.51148], [35.11358, 32.50967], [35.10676, 32.50688],
              [35.10286, 32.5051], [35.09573, 32.50521], [35.08945, 32.50451], [35.0842, 32.50185]]
NAHAL_KISHON = [[35.28972, 32.48366], [35.28068, 32.49986], [35.27883, 32.52696], [35.26178, 32.5359], [35.25512, 32.54803],
                [35.25876, 32.55978], [35.26101, 32.57493], [35.25796, 32.58711], [35.24281, 32.60159], [35.23543, 32.61089],
                [35.2265, 32.62663], [35.21227, 32.63486], [35.19425, 32.63805], [35.17596, 32.64118], [35.1631, 32.6467],
                [35.14571, 32.66262], [35.11879, 32.68291], [35.10413, 32.70197]]
ARUNA_EXIT = P(-3400, -5800)
TAANACH = P(11400, -3000)
YOKNEAM = P(-8000, 7000)
WALL = P(0, 0)


def build() -> dict:
    st = Story()
    # 1. Council at Yehem
    st.step("yehem", "Three roads from Yehem", "Spring, year 23",
            """The army has marched north from Gaza and halted at Yehem below the Carmel hills. Scouts report three ways to Megiddo: a northern road by Yokneam, a southern road by Taanach, and the short road through the Aruna ravine, where men must go in single file. The generals urge a safe road. Thutmose reportedly reasons that the enemy expects exactly that, and chooses Aruna. The rebel coalition, gathered in and around Megiddo, has posted detachments on the two longer roads.""")
    st.put("egypt-army", at=P(-12500, -11500), facing=45, width=300, depth=300, frame=False)
    st.put("pharaoh", at=P(-12400, -11400), facing=45, frame=False)
    st.put("canaan-main", at=P(-900, -500), facing=225, width=1400, depth=120, conjectural=True)
    st.put("det-yokneam", at=YOKNEAM, facing=180, width=300, depth=100, conjectural=True)
    st.put("det-taanach", at=TAANACH, facing=270, width=300, depth=100, conjectural=True)
    st.put("kadesh-king", at=P(-400, -200), conjectural=True)
    # 2. Aruna
    st.step("aruna", "Through the Aruna ravine", "Days before the battle",
            """Thutmose leads in person, with light infantry and mounted archers first to clear any pickets and the chariots and baggage strung out behind. The column is stretched thin along the narrow ravine for hours, and a determined enemy at its mouth could have destroyed it piecemeal. No one is there. The rebel main force is far off, watching the other two roads, and cannot reach the exit in time.""")
    st.put("egypt-army", at=P(-7000, -8000), facing=45, width=120, depth=3500, shape="column", move="march",
           via=[P(-9500, -9700)], frame=True)
    st.put("pharaoh", at=P(-8500, -9000), facing=45, move="march", frame=True)
    st.put("det-yokneam", frame=False)
    st.put("det-taanach", frame=False)
    st.note(P(-5500, -6700), "Aruna ravine: single file", "label", conjectural=True)
    # 3. Emerging
    st.step("emerge", "Egypt reaches the plain", "Evening before battle",
            """The Egyptian vanguard breaks out of the ravine onto the southern edge of the plain of Megiddo and the army gathers in the open without a fight. The rebel detachments on the Taanach and Yokneam roads are now out of position, since Thutmose has come between them and the city. The Annals say the army camped that night, and that the king warned the troops to be ready at dawn.""")
    st.put("egypt-army", at=P(-3000, -4300), facing=40, width=1500, depth=400, shape="block", move="march", state="ready")
    st.put("pharaoh", at=P(-2800, -4100), move="march")
    st.put("canaan-main", at=P(-600, -300), facing=215)
    st.put("det-yokneam", state="ready")
    # 4. Deployment
    st.step("deploy", "The crescent forms at night", "Night to dawn",
            """During the night Thutmose draws his troops up in a wide arc facing the city: the left wing resting towards Taanach to the south-east, the right wing reaching the north-west of Megiddo, and the king with the centre. The lines are on the low ground in front of the tell, while the rebels stand nearer the walls, on higher ground. The exact placing of each body is not recorded, so the drawing here is a reconstruction.""")
    st.put("egypt-army", state="hidden")
    st.put("egypt-left", at=P(1900, -1400), facing=320, width=1000, depth=60, conjectural=True)
    st.put("egypt-centre", at=P(-300, -1700), facing=15, width=1100, depth=60, conjectural=True)
    st.put("egypt-right", at=P(-2300, -800), facing=60, width=1000, depth=60, conjectural=True)
    st.put("egypt-chariots-l", at=P(2500, -900), facing=315, width=500, depth=40, conjectural=True)
    st.put("egypt-chariots-c", at=P(-300, -2000), facing=15, width=500, depth=40, conjectural=True)
    st.put("pharaoh", at=P(-300, -1850), facing=15, conjectural=True, move="march")
    st.put("canaan-left", at=P(1400, -150), facing=215, width=900, depth=50, conjectural=True)
    st.put("canaan-centre", at=P(-150, -300), facing=200, width=700, depth=50, conjectural=True)
    st.put("canaan-right", at=P(-1300, -300), facing=215, width=700, depth=50, conjectural=True)
    st.put("canaan-chariots", at=P(-100, 250), facing=200, width=600, depth=40, conjectural=True)
    st.put("canaan-main", state="hidden")
    st.put("kadesh-king", at=P(-100, 100), conjectural=True)
    # 5. Charge
    st.step("charge", "The pharaoh attacks at dawn", "Dawn",
            """At first light Thutmose sets his chariot out ahead of the centre and the whole line advances. The curved front threatens both rebel flanks at once, and the Annals stress the speed and boldness of the attack, with the left wing seen as the most mobile. The rebel line is unprepared for such a blow, and an early shock decides the matter before the coalition can use its numbers.""")
    st.put("egypt-chariots-c", at=P(-250, -950), move="charge", state="engaged", facing=10)
    st.put("egypt-centre", at=P(-250, -700), move="advance", state="engaged")
    st.put("egypt-left", at=P(1700, -700), move="advance", state="engaged")
    st.put("egypt-chariots-l", at=P(2200, -400), move="flank", state="engaged")
    st.put("egypt-right", at=P(-2000, -400), move="advance", state="engaged")
    st.put("pharaoh", at=P(-250, -1000), move="advance")
    st.put("canaan-centre", state="engaged")
    st.put("canaan-left", state="engaged")
    st.put("canaan-right", state="engaged")
    st.put("canaan-chariots", state="engaged")
    st.note(P(-250, -550), "Contact: first recorded body count", "clash", conjectural=True)
    # 6. Rout
    st.step("rout", "The coalition breaks", "Morning",
            """The rebel line collapses almost at once. Chariots and men abandon their equipment and run for the city. The garrison, afraid to let Egyptians in with the fugitives, shuts the gates and lowers clothing tied together as ropes. The Annals record the dead and prisoners, and modern writers treat this as the first battle in which casualties were counted.""")
    st.put("canaan-left", at=P(900, 700), facing=0, move="rout", state="routed")
    st.put("canaan-centre", at=P(-100, 450), facing=0, move="rout", state="routed")
    st.put("canaan-right", at=P(-900, 500), facing=0, move="rout", state="routed")
    st.put("canaan-chariots", at=P(-50, 300), move="rout", state="routed")
    st.put("kadesh-king", at=P(0, 80), move="retreat")
    st.put("egypt-centre", at=P(-200, -200), move="pursuit")
    st.put("egypt-chariots-c", at=P(-200, -450), move="pursuit")
    st.put("egypt-left", at=P(1400, -150), move="pursuit")
    st.put("egypt-right", at=P(-1600, -150), move="pursuit")
    st.put("egypt-chariots-l", state="ready")
    st.put("pharaoh", at=P(-200, -500), move="advance")
    st.note(P(100, 50), "Gates shut; fugitives hauled up the wall", "event")
    # 7. Plunder
    st.step("plunder", "The camp is plundered", "Midday",
            """The Egyptian soldiers halt to strip the abandoned rebel camp. They take 924 chariots and 200 suits of armour. While they are busy, many of the fleeing men, among them the kings of Kadesh and Megiddo, are pulled up the walls into Megiddo. Later writers blame the pause for the lost chance of seizing the city that day.""")
    st.put("canaan-camp", at=P(-1300, -1400), facing=0, width=500, depth=200, conjectural=True)
    st.put("egypt-centre", at=P(-1000, -1100), move="march", state="ready")
    st.put("egypt-left", at=P(900, -300), state="ready")
    st.put("egypt-right", at=P(-1800, -700), move="march", state="ready")
    st.put("canaan-left", at=P(300, 200), move="retreat", state="wavering")
    st.put("canaan-centre", at=P(-50, 120), move="retreat", state="wavering")
    st.put("canaan-right", at=P(-700, 150), move="retreat", state="wavering")
    st.put("canaan-chariots", state="destroyed")
    st.put("det-yokneam", state="ready")
    st.note(P(-1300, -1400), "924 chariots, 200 armours taken", "capture")
    # 8. Siege
    st.step("siege", "The siege of Megiddo", "Following months",
            """Thutmose orders a ditch and a wooden palisade built around the city so that nobody can leave. The siege lasts about seven months. The king of Kadesh slips out, but Megiddo's ruler and his people are eventually forced to surrender. The Annals say the city and its citizens were spared.""")
    st.put("egypt-ring", at=P(0, -100), facing=0, width=1500, depth=60, shape="circle", conjectural=True)
    for u in ("egypt-left", "egypt-right", "egypt-centre", "egypt-chariots-l", "egypt-chariots-c"):
        st.put(u, state="hidden")
    st.put("pharaoh", at=P(-600, -800))
    st.put("canaan-camp", state="hidden")
    st.put("canaan-left", state="hidden")
    st.put("canaan-centre", state="hidden")
    st.put("canaan-right", state="hidden")
    st.put("kadesh-king", state="hidden")
    st.note(P(500, 400), "Kadesh's king escapes", "event", conjectural=True)
    st.note(P(-700, -450), "Ditch and palisade", "label", conjectural=True)
    # 9. Aftermath
    st.step("aftermath", "Spoils and settlement", "After the surrender",
            """The Annals list what was carried off: 340 prisoners, 2,041 mares, 191 foals, 6 stallions, 924 chariots, 502 bows, 1,929 cattle and 22,500 sheep, plus the royal chariot and tent poles of the king of Megiddo. Local kings had to send sons to be educated in Egypt. The victory opened the way for years of annual campaigns that built Egypt's empire in the Levant.""")
    st.put("egypt-ring", state="hidden")
    st.put("egypt-army", at=P(-1500, -1500), facing=225, width=800, depth=300, state="ready", frame=True)
    st.put("pharaoh", at=P(-1400, -1400), move="march")
    st.note(P(0, 0), "Megiddo spared; Egyptian rule restored", "event")

    sources = [{"title": "Battle of Megiddo (15th century BC), Wikipedia",
                "url": "https://en.wikipedia.org/wiki/Battle_of_Megiddo_(15th_century_BC)", "kind": "web"}]
    return st.doc(
        slug="battle-of-megiddo", kind="battle", schema=3,
        entity={"name": "Battle of Megiddo", "wikidata": "Q733364"},
        title="Battle of Megiddo", date_label="16 April 1457 BC (traditional date)", year=-1457,
        intro="""Megiddo is the earliest battle for which a reasonably detailed account survives. Pharaoh Thutmose III, newly in sole rule of Egypt, marched to put down a coalition of Canaanite and Syrian rulers led by the king of Kadesh, who had gathered at Megiddo on the edge of the Jezreel Valley, a key point on the road between Egypt and Mesopotamia. Against his generals' advice he chose the narrow Aruna ravine, came out unopposed on the plain and attacked the coalition at dawn in a curved formation. The rebels broke and fled into the city, where a seven month siege followed and Egyptian authority in the Levant was restored. All details come from Egyptian records, chiefly the Karnak Annals.""",
        outcome="Egyptian victory; Megiddo fell after a seven month siege and Egypt regained control of Canaan.",
        uncertainty="""Everything comes from Egyptian court records, which favour the king. The date is debated, since some scholars place the battle in 1482 or 1479 BC. Strengths are modern estimates. The positions of the lines and of the camp are reconstructed, as the Annals give only the wings relative to Taanach and the Qina brook, and the Aruna route is generally identified with the Wadi Ara. The routes of the two rebel detachments are conjectural.""",
        sources=sources,
        sides=[
            {"id": "a", "name": "Egypt", "color": "#b45309", "polity": {"name": "Egyptian Empire", "wikidata": "Q180568"},
             "commanders": [{"name": "Thutmose III", "wikidata": "Q157899", "role": "Pharaoh"}],
             "strength": "c. 10,800 (modern estimate)", "losses": "4,000 killed, 1,000 wounded"},
            {"id": "b", "name": "Canaanite coalition", "color": "#1d4ed8", "polity": {"name": "Canaan", "wikidata": "Q163329"},
             "commanders": [{"name": "King of Kadesh", "role": "Coalition leader"}, {"name": "Prince of Megiddo", "role": "Local ruler"}],
             "strength": "c. 10,700 (modern estimate)", "losses": "8,300 killed, 3,400 captured"},
        ],
        units=[
            {"id": "egypt-army", "side": "a", "kind": "army", "label": "Egyptian army"},
            {"id": "pharaoh", "side": "a", "kind": "commander", "label": "Thutmose III"},
            {"id": "egypt-left", "side": "a", "kind": "infantry", "label": "Egyptian left wing", "strength": "c. 3,000"},
            {"id": "egypt-centre", "side": "a", "kind": "infantry", "label": "Egyptian centre", "strength": "c. 4,000"},
            {"id": "egypt-right", "side": "a", "kind": "infantry", "label": "Egyptian right wing", "strength": "c. 3,000"},
            {"id": "egypt-chariots-l", "side": "a", "kind": "chariots", "label": "Left chariots"},
            {"id": "egypt-chariots-c", "side": "a", "kind": "chariots", "label": "Royal chariots"},
            {"id": "egypt-ring", "side": "a", "kind": "army", "label": "Siege lines"},
            {"id": "canaan-main", "side": "b", "kind": "army", "label": "Coalition army"},
            {"id": "canaan-left", "side": "b", "kind": "infantry", "label": "Coalition left"},
            {"id": "canaan-centre", "side": "b", "kind": "infantry", "label": "Coalition centre"},
            {"id": "canaan-right", "side": "b", "kind": "infantry", "label": "Coalition right"},
            {"id": "canaan-chariots", "side": "b", "kind": "chariots", "label": "Coalition chariots"},
            {"id": "canaan-camp", "side": "b", "kind": "camp", "label": "Coalition camp"},
            {"id": "kadesh-king", "side": "b", "kind": "commander", "label": "King of Kadesh"},
            {"id": "det-yokneam", "side": "b", "kind": "infantry", "label": "Northern road guard"},
            {"id": "det-taanach", "side": "b", "kind": "infantry", "label": "Taanach road guard"},
        ],
        terrain=[
            {"id": "megiddo", "kind": "city", "label": "Megiddo", "at": WALL},
            {"id": "tell", "kind": "hill", "label": "Tell of Megiddo", "area": ellipse(WALL, 350, 250)},
            {"id": "nahal-iron", "kind": "stream", "label": "Wadi Ara (Aruna route)", "line": NAHAL_IRON},
            {"id": "kishon", "kind": "river", "label": "Kishon", "line": NAHAL_KISHON},
            {"id": "taanach", "kind": "village", "label": "Taanach", "at": TAANACH},
            {"id": "yokneam", "kind": "village", "label": "Yokneam", "at": YOKNEAM},
            {"id": "aruna-exit", "kind": "pass", "label": "Aruna exit", "at": ARUNA_EXIT},
            {"id": "jezreel", "kind": "label", "label": "Jezreel Valley", "at": P(3000, 4500)},
        ],
    )
