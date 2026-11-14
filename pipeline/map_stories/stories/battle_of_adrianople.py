"""Battle of Adrianople, 9 August 378 — map story builder.

Anchors: ANCHOR is the Gothic wagon circle, placed at Muratcali (village from places, ~1.4 km E of the
Wikidata P625 point); this is one of three modern theses for the site (the others lie west of the Tonzos
and near Demirhanli), so every battlefield position is conjectural. Adrianople (Edirne) lies ~14 km SSW.
Orientation: the Romans marched north-north-east from Adrianople and faced north/up the hill; the Goths
stood on a hill behind a wagon circle facing south. Gothic cavalry returned from the north-east/east and
struck the Roman left and rear. Source: Wikipedia, Battle of Adrianople (Ammianus via modern summaries).
"""
from pipeline.map_stories.geo import offset
from pipeline.map_stories.layout import Story, deploy_line, facing_off, local_frame, wing, ent

ANCHOR = (26.61632, 41.80459)
P = local_frame(ANCHOR)
ADRIANOPLE = (26.55872, 41.67593)

TUNCA = [[26.54481, 41.78509], [26.54144, 41.78655], [26.53895, 41.78593], [26.53838, 41.78407], [26.53882, 41.78206],
         [26.53537, 41.77943], [26.53677, 41.77836], [26.53961, 41.78025], [26.541, 41.77754], [26.53925, 41.77455],
         [26.53592, 41.77506], [26.53329, 41.77569], [26.53494, 41.77163], [26.53055, 41.76893], [26.52872, 41.7666]]


def hill(c, rx, ry):
    from pipeline.map_stories.geo import ellipse
    return ellipse(c, rx, ry)


def build() -> dict:
    st = Story()
    adr = P(-5200, -14700)
    st.step("camps", "Two camps north of Adrianople", "6-8 August 378", """
        Valens has gathered his field army at Adrianople and fortified a camp with ditch and rampart, leaving the
        treasury and officials inside. Scouts report a Gothic force of about ten thousand twenty-five kilometres to
        the north. Richomeres arrives with a letter from Gratian asking him to wait for the western reinforcements,
        and the officers agree, but Valens wants a victory of his own. On 8 August Fritigern offers peace in
        exchange for land, and Valens refuses.""", entities=[ent("Valens", "Q172471", role="Eastern emperor"), ent("Fritigern", "Q159712", role="Thervingi leader")])
    st.put("r-camp", at=adr, label="Roman camp, Adrianople", state="ready")
    st.put("g-wagons", at=P(0, 0), shape="circle", width=420, depth=420, facing=180, label="Gothic wagon circle", conjectural=True)
    st.put("g-foot", at=P(0, -260), facing=180, width=900, depth=60, label="Gothic infantry", strength_n=9000, conjectural=True)

    st.step("march", "The march in the heat", "Morning to noon, 9 August", """
        Valens leaves Adrianople at dawn and marches about eight Roman miles over rough ground, arriving around
        noon. His men are tired and thirsty after the August heat. The Gothic camp sits on rising ground, with the
        wagon circle protecting families and goods. Fritigern's aim is to stall, because Alatheus, Saphrax and the
        Gothic horse are away foraging.""", frame=True)
    st.put("r-camp", frame=False)
    st.put("r-column", at=P(-1400, -2900), start=adr, move="march", via=[P(-3300, -9000)], label="Roman field army on the march", strength_n=15000, facing=20, conjectural=True)

    st.step("stall", "Smoke and negotiation", "Early afternoon", """
        The Goths set fire to the fields so that smoke and heat harass the approaching Romans. Envoys cross
        between the lines to arrange an exchange of hostages. Each hour of talk costs the Romans water and
        patience, while it buys Fritigern time for his cavalry. Valens forms his army into line facing the hill,
        with infantry in the centre and horse on the flanks. The exact order is not given in the sources.""")
    st.hide("r-column")
    st.put("r-left", at=P(-700, -1300), facing=0, width=500, depth=40, label="Roman left wing", strength_n=3000, conjectural=True)
    pl = deploy_line(P(-450, -1300), P(450, -1300), [("r-centre", 3), ("r-right", 2)], depth=40)
    st.place(pl, facing=0, conjectural=True)
    st.put("r-cav-left", at=P(-1200, -1250), facing=0, width=300, depth=40, label="Roman cavalry", conjectural=True)
    st.put("r-cav-right", at=P(1100, -1250), facing=0, width=300, depth=40, label="Roman cavalry", conjectural=True)
    st.put("r-valens", at=P(0, -1700), label="Valens", conjectural=True)

    st.step("scholae", "The scholae charge without orders", "Mid-afternoon", """
        Before talks conclude, some Roman units open the fight on their own. The imperial scholae, shield bearers
        and archers under the Iberian prince Bacurius, rush ahead, hoping for an easy win and revenge for two years
        of raiding. With no support behind them, they are pushed back by the Gothic defenders. The assault shows the
        discipline breaking and drags the whole line into battle before it is ready.""")
    st.put("r-scholae", at=P(-100, -1450), facing=0, width=200, depth=30, label="Scholae (Bacurius)", conjectural=True)
    st.put("r-scholae", facing_off(st.pl("g-foot"), depth=30), move="charge", state="engaged")
    st.put("g-foot", state="engaged")

    st.step("left", "The Roman left reaches the wagons", "Mid-afternoon", """
        The Roman left wing presses forward until it reaches the circle of wagons. It arrives too late and in poor
        order, with the rest of the army strung out behind it. The attack stalls in the confined space around the
        carts, and the Romans are fought to a halt by men fighting for their families.""")
    st.put("r-left", facing_off(st.pl("g-wagons"), depth=40, gap=-60), move="attack", state="engaged", width=300)
    st.put("g-wagons", state="engaged")
    st.put("r-centre", at=P(-150, -750), move="advance")
    st.put("r-right", at=P(350, -950), move="advance")

    st.step("cavalry", "The Gothic horse returns", "Late afternoon", """
        Alatheus and Saphrax come back with their cavalry, joined by Alans, and fall on the Romans like a
        thunderbolt, in Ammianus's image. The Roman left, already disordered after the failed assault, is
        surrounded. Modern writers differ on how many horsemen there were: older accounts made them the decisive
        force, while recent work gives the Gothic infantry the larger part.""")
    st.put("g-cav", at=P(2600, 1000), facing=225, width=500, depth=60, label="Gothic cavalry (Alatheus, Saphrax)", conjectural=True, frame=True)
    st.put("g-cav", at=P(-300, -1000), facing=230, move="charge", state="engaged")
    st.put("r-left", state="wavering")

    st.step("crush", "Pressed against the hill", "Late afternoon", """
        The Romans fall back toward the foot of the hill, where they cannot manoeuvre. Their heavy armour and long
        shields hamper them, units are packed too close to fight, and the pressure on all sides turns retreat into
        rout. The cavalry on the Roman right flees rather than hold, leaving the foot isolated.""")
    st.put("r-cav-right", move="retreat", at=P(2200, -2800), state="routed")
    st.put("r-cav-left", move="retreat", at=P(-2500, -2500), state="routed")
    st.put("r-centre", state="wavering", at=P(-100, -950), move="retreat")
    st.put("r-right", state="wavering", at=P(450, -1200), move="retreat")
    st.put("r-scholae", state="routed")

    st.step("rout", "Slaughter until nightfall", "Evening", """
        The Roman army dissolves. Ammianus says the killing went on until dark, and modern estimates put Roman
        dead at between ten and twenty thousand, roughly two thirds of the force. Sebastianus and many senior
        officers fall. A third of the army escapes, some of it toward the walls of Adrianople.""")
    st.put("g-cav", at=P(-600, -1900), move="pursuit")
    st.put("r-centre", state="destroyed")
    st.put("r-right", state="destroyed")
    st.put("r-left", state="destroyed")

    st.step("valens", "The emperor disappears", "Night", """
        Abandoned by his guards, Valens is never seen again and his body is not found. One tale says he reached
        a peasant's cottage with a few companions; the Goths, unaware who was inside, set it alight and he burned
        to death. Others think he died unnoticed in the fighting. Either way, it is the end of the senior
        emperor of the East.""")
    st.put("r-valens", at=P(-600, -2400), move="retreat", state="killed", label="Valens (fate uncertain)")
    st.note(P(-600, -2400), "Valens lost; fate unknown", "death", conjectural=True)

    st.step("after", "The Goths before Adrianople", "10 August and after", """
        The victorious Goths march on Adrianople and try to storm it, but the garrison, helped by soldiers shut
        out the night before, repels them. The defeat destroys the core of the eastern field army and many
        arsenals in the Danubian provinces. Theodosius, Valens's successor, eventually settles the Goths as allied
        peoples inside the empire. Their lasting presence changes the frontier for good.""")
    st.put("g-foot", at=P(-3500, -10000), move="march", state="ready", facing=200)
    st.put("g-cav", state="ready", at=P(-3000, -9500), facing=200, move="march")
    st.put("g-wagons", state="ready", at=P(-3300, -10500), move="march")

    return st.doc(
        slug="battle-of-adrianople", kind="battle", entity={"name": "Battle of Adrianople", "wikidata": "Q192473"},
        title="Battle of Adrianople", date_label="9 August 378", year=378,
        intro="""In August 378 the eastern emperor Valens led his field army out of Adrianople to destroy a Gothic host that had been in revolt in Thrace for two years. The Goths had crossed the Danube in 376 as refugees from the Huns and had been mistreated by Roman officials. Valens ignored warnings to wait for his western colleague Gratian and rejected Fritigern's last offer of peace. After a hot eight-mile march his tired army reached the Gothic wagon circle on a hill, was drawn into the fight by a premature attack and was enveloped when the Gothic cavalry returned from foraging. Valens died, and about two thirds of his army went with him.""",
        outcome="Decisive Gothic and Alan victory; Valens killed and the eastern field army destroyed.",
        uncertainty="The battlefield is unplaced: three modern theses exist, so all positions are conjectural and use the Muratcali site only as an anchor. Strengths are estimates (12,000-15,000 each) and the Roman line and cavalry placements, the route of the Gothic cavalry and Valens's death are reconstructed or disputed.",
        sources=[{"title": "Battle of Adrianople - Wikipedia", "url": "https://en.wikipedia.org/wiki/Battle_of_Adrianople", "kind": "web"}],
        sides=[
            {"id": "r", "name": "Eastern Roman Empire", "color": "#b91c1c", "polity": {"name": "Eastern Roman Empire", "wikidata": "Q12544"},
             "commanders": [{"name": "Valens", "wikidata": "Q172471", "role": "emperor, killed"}], "strength": "c. 15,000 (Heather)", "losses": "10,000-20,000"},
            {"id": "g", "name": "Goths and Alans", "color": "#1d4ed8", "polity": {"name": "Goths", "wikidata": "Q42193"},
             "commanders": [{"name": "Fritigern", "wikidata": "Q159712", "role": "Thervingi leader"}], "strength": "12,000-15,000", "losses": "Unknown"},
        ],
        units=[
            {"id": "r-camp", "side": "r", "kind": "camp", "label": "Roman camp, Adrianople"},
            {"id": "r-column", "side": "r", "kind": "army", "label": "Roman army on the march", "strength": "c. 15,000"},
            {"id": "r-left", "side": "r", "kind": "heavy_infantry", "label": "Roman left wing"},
            {"id": "r-centre", "side": "r", "kind": "heavy_infantry", "label": "Roman centre"},
            {"id": "r-right", "side": "r", "kind": "heavy_infantry", "label": "Roman right wing"},
            {"id": "r-cav-left", "side": "r", "kind": "cavalry", "label": "Roman cavalry, left"},
            {"id": "r-cav-right", "side": "r", "kind": "cavalry", "label": "Roman cavalry, right"},
            {"id": "r-scholae", "side": "r", "kind": "light_infantry", "label": "Scholae (Bacurius)"},
            {"id": "r-valens", "side": "r", "kind": "commander", "label": "Valens"},
            {"id": "g-wagons", "side": "g", "kind": "camp", "label": "Gothic wagon circle"},
            {"id": "g-foot", "side": "g", "kind": "infantry", "label": "Gothic infantry"},
            {"id": "g-cav", "side": "g", "kind": "cavalry", "label": "Gothic cavalry and Alans"},
        ],
        terrain=[
            {"id": "tunca", "kind": "river", "label": "Tunca", "line": TUNCA},
            {"id": "hill", "kind": "hill", "label": "Gothic hill", "area": hill(P(0, 150), 900, 500), "conjectural": True},
            {"id": "muratcali", "kind": "village", "label": "Muratcali", "at": list(ANCHOR)},
            {"id": "adrianople", "kind": "town", "label": "Adrianople", "at": list(ADRIANOPLE)},
            {"id": "road", "kind": "road", "label": "Road from Adrianople", "line": [list(ADRIANOPLE), list(P(-3300, -9000)), list(P(-1500, -3400)), list(P(-300, -1400))], "conjectural": True},
            {"id": "fields", "kind": "field", "label": "Burnt fields", "area": hill(P(-200, -900), 900, 350), "conjectural": True},
        ],
    )
