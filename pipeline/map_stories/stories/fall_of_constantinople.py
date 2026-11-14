"""Fall of Constantinople, 6 April - 29 May 1453 - map story builder.

Anchors: Topkapi (St Romanus Gate, the Mesoteichion where the Lycus crossed the land walls) = ANCHOR;
Edirnekapi, Silivrikapi, Golden Gate, Blachernae and Galata/Kasimpasa from `places`; the Golden Horn
outline from OSM (Halic). The land wall line is drawn through those gates (conjectural between them).
Orientation: the land walls run roughly north-south on the west of the city. Ottomans camp west of them
and face east (90); defenders stand on the walls facing west (270). The Golden Horn lies north-east of
the land walls; Galata/Pera lies across it to the east. Sources: Wikipedia (Preparations, Siege, Final assault).
"""
from pipeline.map_stories.geo import local, offset
from pipeline.map_stories.layout import Story, facing_off, local_frame, when

ANCHOR = (28.9282, 41.0207)
P = local_frame(ANCHOR)

HALIC = [[28.93502, 41.05004], [28.93818, 41.04682], [28.93968, 41.04255], [28.9449, 41.04078], [28.94694, 41.03682], [28.94924, 41.0353], [28.94974, 41.03236], [28.95261, 41.03086], [28.95303, 41.02934], [28.95746, 41.02841], [28.96629, 41.01955], [28.96963, 41.01963], [28.97504, 41.0176], [28.97447, 41.02181], [28.9699, 41.02236], [28.96717, 41.02489], [28.96607, 41.02799], [28.96729, 41.02891], [28.96568, 41.03113], [28.96483, 41.03071], [28.96088, 41.03388], [28.95241, 41.03489], [28.95361, 41.03576], [28.95262, 41.03539], [28.95078, 41.0375], [28.9491, 41.04138], [28.94033, 41.047], [28.93936, 41.05146], [28.94771, 41.05552]]
LANDWALL = [[28.94412, 41.03859], [28.93700, 41.03600], [28.92949, 41.03340], [28.9282, 41.0207], [28.92689, 41.00541], [28.92243, 40.99322]]
CHAIN = [[28.9868, 41.0155], [28.9780, 41.0210], [28.97279, 41.02529]]
PORTAGE = [[29.00753, 41.04285], [28.9900, 41.0370], [28.9770, 41.0300], [28.96508, 41.03504]]
GATES = {"edirne": (28.92949, 41.0334), "topkapi": (28.9282, 41.0207), "silivri": (28.92689, 41.00541),
         "golden-gate": (28.92243, 40.99322), "blachernae": (28.94412, 41.03859), "galata": (28.97279, 41.02529),
         "hagia-sophia": (28.98001, 41.0085)}


def G(key):
    return P(*local(GATES[key], ANCHOR))


def L(lon, lat):
    return P(*local((lon, lat), ANCHOR))


def CAM(pt, zoom):
    return {"center": [round(pt[0], 6), round(pt[1], 6)], "zoom": zoom}


def build() -> dict:
    st = Story()
    BY = 270   # defenders face west
    OT = 90    # Ottomans face east

    # ---- 1 camps
    st.step("camps", "The Sultan's army reaches the walls", "2-5 April 1453", """
        Mehmed II brings an army that Western sources put in the tens of thousands up to the Theodosian land walls, the one side of the
        city not guarded by water. The camp is pitched on Monday 2 April. His red-and-gold tent stands near the Mesoteichion, the
        middle stretch where the little river Lycus passes under the wall, and the guns and the elite Janissaries are placed around it.
        European regulars under Karaca Pasha stretch along the northern wall, Anatolian regulars under Ishak Pasha hold the southern
        stretch, and irregular bashi-bazouks wait behind. Zagan Pasha takes troops north of the Golden Horn. In the sea, Baltoghlu's
        fleet gathers.""", date=when(1453, 4, 2, end=(1453, 4, 5)), light="day", camera=CAM(P(0, 350), 13.9))
    st.put("o-janissaries", at=P(-420, 0), facing=OT, width=500, depth=40, strength_n=5000)
    st.put("o-guns", at=P(-230, 0), facing=OT, width=300, depth=30)
    st.put("o-europeans", at=P(-380, 1100), facing=OT, width=800, depth=60)
    st.put("o-anatolians", at=P(-380, -1100), facing=OT, width=1100, depth=60)
    st.put("o-irregulars", at=P(-800, 0), facing=OT, width=1500, depth=120)
    st.put("o-mehmed", at=P(-650, 0), facing=OT, width=30, depth=30)
    st.put("o-zagan", at=L(28.9765, 41.0390), facing=200, width=500, depth=60, frame=False)
    st.put("o-fleet", at=L(29.0075, 41.0405), facing=180, width=300, depth=100)

    # ---- 2 defenders
    st.step("defenders", "The defenders take their posts", "5 April 1453", """
        With about eight thousand fighting men for roughly twenty kilometres of walls, the defenders can only man the outer land wall.
        Emperor Constantine XI and his Greeks hold the Mesoteichion, the section feared most. Giovanni Giustiniani and his Genoese
        stand north of him at the Charisian Gate and later join the emperor at the centre. The Venetians under Minotto hold the
        Blachernae palace corner, while Theophilos Palaiologos, Filippo Contarini and Demetrios Kantakouzenos watch the southern
        gates. Reserves are kept back in the Petra quarter, and Alviso Diedo commands the ships inside the Golden Horn behind the chain.""",
            date=when(1453, 4, 5), light="day", camera=CAM(P(0, 350), 13.9))
    st.put("b-constantine", at=P(40, 0), facing=BY, width=450, depth=30, strength_n=1500)
    st.put("b-giustiniani", at=P(100, 600), facing=BY, width=500, depth=30, strength_n=700)
    st.put("b-venetians", at=P(1250, 1950), facing=330, width=400, depth=30)
    st.put("b-south", at=P(-60, -1600), facing=BY, width=1700, depth=20)
    st.put("b-reserve", at=P(1500, 300), facing=BY, width=300, depth=40, conjectural=True)
    st.put("b-fleet", at=L(28.9665, 41.0285), facing=60, width=300, depth=80)
    st.put("b-chain", at=L(28.9790, 41.0215), facing=60, width=30, depth=30)

    # ---- 3 bombardment
    st.step("bombardment", "The great guns open fire", "6 April - mid April", """
        The bombardment begins. Orban's giant gun, hauled from Edirne by a team of oxen and hundreds of men, and other bombards
        batter the wall around the Mesoteichion. They fire slowly and imprecisely, and each night the defenders mend the damage with
        timber, earth and barrels. Mehmed also sends detachments to take outlying strongholds such as Therapia and Studius. Janissary
        rushes against the wall cost many lives, as the Venetian surgeon Barbaro recorded, because the Turks would not leave their dead
        behind.""", date=when(1453, 4, 6, end=(1453, 4, 18)), camera=CAM(P(0, 350), 13.9))
    st.fire("o-guns", st.at("b-constantine"), "bombardment")
    st.put("o-janissaries", at=P(-130, 0), facing=OT, width=500, depth=40, move="attack", state="engaged")
    st.put("b-constantine", state="engaged")
    st.note(P(-60, 120), "Wall battered, repaired each night", "event")

    # ---- 4 20 April
    st.step("four-ships", "Four ships break the blockade", "20 April 1453", """
        Baltoghlu's fleet cannot force the chain across the mouth of the Golden Horn. On 20 April a small flotilla of Christian
        ships, running before a wind, fights its way through the Ottoman galleys and reaches the harbour. The success cheers the
        defenders and humiliates the Sultan; Baltoghlu, probably wounded in the eye, is stripped of his property and whipped. The relief
        also shows that Western help had not arrived in force.""", date=when(1453, 4, 20), light="day", camera=CAM(L(28.985, 41.030), 14.0))
    st.put("o-janissaries", state="ready")
    st.put("b-constantine", state="ready")
    st.put("o-fleet", at=L(28.9990, 41.0200), facing=300, width=300, depth=100, move="advance", state="engaged")
    st.put("b-relief", at=L(28.9700, 41.0080), facing=0, width=120, depth=60, frame=False)
    st.put("b-relief", at=L(28.9740, 41.0195), facing=40, move="advance", state="engaged",
           via=[L(28.9790, 41.0110), L(28.9810, 41.0165)])
    st.note(L(28.9770, 41.0205), "Four ships reach the boom", "event")

    # ---- 5 portage
    st.step("portage", "The fleet crosses the hill of Galata", "22 April 1453", """
        Mehmed answers by building a track of greased logs over the hill behind Galata and hauling a part of his fleet overland from
        the Bosphorus shore to the upper Golden Horn, bypassing the chain. The sight of Ottoman ships floating inside the harbour
        demoralises the defenders and forces them to thin their land defences to guard the sea walls along the Horn. The exact
        route over the hill is not certain.""", date=when(1453, 4, 22), light="day", camera=CAM(L(28.985, 41.030), 14.0))
    st.put("o-fleet", at=L(28.9990, 41.0200), state="ready")
    st.put("o-portage", at=L(29.0075, 41.0428), facing=250, width=200, depth=60, conjectural=True)
    st.put("o-portage", at=L(28.9651, 41.0350), move="march", state="ready", conjectural=True,
           via=[L(28.9900, 41.0370), L(28.9770, 41.0300)])
    st.note(L(28.9900, 41.0385), "Greased-log track over Galata (conj.)", "event", conjectural=True)
    st.put("b-fleet", state="ready")
    st.note(L(28.9790, 41.0215), "Chain across the Horn", "label")

    # ---- 6 fire ships
    st.step("fireships", "The fireship attack fails", "28 April 1453", """
        On the night of 28 April the defenders try to burn the Ottoman ships now in the Golden Horn. The attempt fails, and many of
        the Italian crews are lost. Forty swimmers who reach the northern shore are impaled in view of the city; in reprisal the
        defenders execute 260 Ottoman prisoners on the walls. The failure leaves the defenders stretched, with part of their small force
        committed to the sea walls.""", date=when(1453, 4, 28), light="night", camera=CAM(L(28.985, 41.030), 14.0))
    st.put("o-portage", at=L(28.9600, 41.0335), facing=250, state="engaged", move="advance", conjectural=True)
    st.put("b-fleet", at=L(28.9615, 41.0328), facing=300, move="attack", state="burning")
    st.note(L(28.9565, 41.0345), "Night attack beaten off", "clash")

    # ---- 7 mines
    st.step("mines", "Mines and countermines", "16-25 May 1453", """
        Mehmed turns to the earth. Serbian miners from Novo Brdo, under Zagan Pasha, dig tunnels toward the walls. The German
        engineer Johannes Grant, serving with the Genoese, runs countermines, and the defenders break into the Ottoman galleries,
        kill the miners and use Greek fire. Tunnels are cut off on 16, 21, 23 and 25 May. Two captured Turkish officers on 23 May
        reveal where the rest run, and those are destroyed.""", date=when(1453, 5, 16, end=(1453, 5, 25)), light="day", camera=CAM(P(0, 350), 13.9))
    st.put("o-portage", at=L(28.9600, 41.0335), state="ready", conjectural=True)
    st.put("o-miners", at=P(-200, 450), facing=OT, width=200, depth=40, conjectural=True)
    st.put("o-miners", at=P(30, 450), move="advance", state="engaged", conjectural=True)
    st.put("b-giustiniani", state="engaged")
    st.note(P(30, 560), "Countermine; tunnels cut 16-25 May", "clash")

    # ---- 8 council
    st.step("council", "An offer refused, a council held", "21-27 May 1453", """
        On 21 May Mehmed offers to lift the siege if the city is handed over: the emperor would keep life and goods and rule the
        Peloponnese. Constantine will pay more tribute but will not give up the city. Halil Pasha urges the Sultan to withdraw, while
        Zagan Pasha demands an all-out assault, and Mehmed chooses the assault. On 27 May a Venetian scouting squadron reaches the
        city and reports that no relief fleet is coming. By then the guns have fired about 5,000 shots.""",
            date=when(1453, 5, 21, end=(1453, 5, 27)), camera=CAM(P(0, 350), 13.9))
    st.hide("o-miners")
    st.put("o-turkmen", at=P(300, 2650), facing=150, width=400, depth=40, frame=False, conjectural=True)
    st.put("b-constantine", state="ready")
    st.note(P(-640, 150), "Council: Halil against, Zagan for", "event")

    # ---- 9 first waves
    st.step("first-waves", "Midnight: the irregular waves", "00:00-c. 04:00, 29 May 1453", """
        After a day of prayer and rest, the attack begins shortly after midnight on Tuesday 29 May with torches, horns and drums.
        First come the Christian troops of the Ottoman realm, then the poorly equipped azaps, then Anatolian Turkmen, who press on the
        older Blachernae stretch in the north-west. Turkmen warriors briefly get into the city there but are driven out. The
        defenders, thin on the ground, hold every point.""", date=when(1453, 5, 29), light="night", camera=CAM(P(500, 1000), 14.3))
    st.put("b-giustiniani", state="engaged")
    st.put("b-constantine", state="engaged")
    st.put("b-venetians", state="engaged")
    st.put("o-irregulars", facing_off(st.pl("b-giustiniani"), depth=50, gap=8, width=600), move="attack", state="engaged")
    st.put("o-europeans", at=P(-60, 1250), facing=OT, width=600, depth=50, move="attack", state="engaged")
    st.put("o-turkmen", facing_off(st.pl("b-venetians"), depth=40, gap=8), move="attack", state="engaged")
    st.put("o-anatolians", at=P(-60, -1100), move="advance", state="engaged")
    st.put("o-janissaries", at=P(-300, 0), move="advance", state="ready")
    st.note(P(1250, 2150), "Turkmen briefly enter at Blachernae", "clash")

    # ---- 10 janissaries
    st.step("janissaries", "The Janissaries and Giustiniani's wound", "c. 04:00-05:00, 29 May", """
        The last wave is the Janissaries, fresh and disciplined, who storm the Mesoteichion and fight the Greeks and Genoese on the
        broken wall. Giustiniani, the commander of the Genoese on land, is badly wounded and carried from the ramparts. His men
        fall back toward the harbour, and panic spreads. Constantine and his Greeks keep fighting, but the line is now opening.""",
            date=when(1453, 5, 29), light="dawn", camera=CAM(P(500, 1000), 14.3))
    st.put("o-irregulars", at=P(-450, 650), move="retreat", state="ready")
    st.put("o-europeans", at=P(-450, 1250), move="retreat", state="ready")
    st.put("o-turkmen", at=P(500, 2500), move="retreat", state="ready")
    st.put("o-janissaries", facing_off(st.pl("b-constantine"), depth=50, gap=8), move="charge", state="engaged")
    st.put("b-giustiniani", at=P(900, 1050), move="retreat", state="wavering")
    st.note(P(250, 520), "Giustiniani wounded, carried off", "death")

    # ---- 11 breach
    st.step("breach", "The wall is lost", "c. 05:00-08:00, 29 May", """
        Janissaries led by Ulubatli Hasan pour over the wall and through the gaps, and the defence collapses at several points.
        Many Greeks run home to protect their families, the Venetians seek their ships, and a few Genoese flee to Galata. Constantine
        is last seen leading a final charge; sources differ and his fate is unknown. The Catalans on their stretch of wall are the
        last to fall. An Ottoman force reaches the Golden Horn walls from behind, and the Venetians break open a harbour gate to escape.""",
            date=when(1453, 5, 29), light="day", camera=CAM(P(500, 1000), 14.3))
    st.put("o-janissaries", at=P(300, 100), facing=OT, move="charge", state="engaged")
    st.put("o-irregulars", at=P(200, 650), facing=OT, move="advance", state="engaged")
    st.put("o-europeans", at=P(200, 1250), facing=OT, move="advance", state="engaged")
    st.put("o-turkmen", at=L(28.9500, 41.0338), facing=60, move="attack", state="engaged", conjectural=True)
    st.put("b-constantine", state="destroyed")
    st.put("b-giustiniani", at=L(28.9540, 41.0310), state="routed", move="retreat", conjectural=True)
    st.put("b-south", state="routed")
    st.put("b-venetians", at=L(28.9565, 41.0335), facing=60, state="routed", move="retreat")
    st.put("b-fleet", at=L(28.9600, 41.0310), facing=45, move="sail", state="ready")
    st.note(P(60, 60), "Constantine XI last seen here (disputed)", "death", conjectural=True)

    # ---- 12 city falls
    st.step("sack", "The city is taken", "29 May 1453 (midday onward)", """
        The Ottoman army spreads along the Mese, the main avenue, past the great forums toward the Church of the Holy Apostles,
        while the navy takes control of the Golden Horn by midday. A few Venetian and Genoese ships escape with refugees. The crowds
        sheltering in Hagia Sophia are taken when the doors are broken, and the captives are sorted by value for the slave markets.
        Thousands die; sources count about 4,000 Greek civilians killed and some 30,000 enslaved. The Byzantine Empire is over.""",
            date=when(1453, 5, 29), light="day")
    st.put("o-janissaries", at=G("hagia-sophia"), facing=OT, move="advance", state="engaged", conjectural=True)
    st.put("o-irregulars", at=P(700, 300), facing=OT, move="advance", state="engaged", conjectural=True)
    st.put("o-mehmed", at=G("hagia-sophia"), move="march", conjectural=True)
    st.put("o-fleet", at=L(28.9560, 41.0330), facing=90, move="advance", state="ready")
    st.put("b-fleet", at=L(28.9250, 41.0600), facing=0, move="sail", state="ready", frame=False)
    st.put("b-reserve", state="routed")
    st.note(G("hagia-sophia"), "Hagia Sophia: the congregation seized", "capture")

    units = [
        {"id": "o-janissaries", "side": "ottoman", "kind": "heavy_infantry", "label": "Janissaries", "strength": "c. 5,000"},
        {"id": "o-guns", "side": "ottoman", "kind": "artillery", "label": "Guns", "strength": "12-62 guns"},
        {"id": "o-europeans", "side": "ottoman", "kind": "infantry", "label": "Rumelians"},
        {"id": "o-anatolians", "side": "ottoman", "kind": "infantry", "label": "Anatolians"},
        {"id": "o-irregulars", "side": "ottoman", "kind": "light_infantry", "label": "Azaps", "strength": "c. 20,000"},
        {"id": "o-mehmed", "side": "ottoman", "kind": "commander", "label": "Mehmed II"},
        {"id": "o-zagan", "side": "ottoman", "kind": "infantry", "label": "Zagan Pasha"},
        {"id": "o-turkmen", "side": "ottoman", "kind": "light_infantry", "label": "Anatolian Turkmen"},
        {"id": "o-miners", "side": "ottoman", "kind": "light_infantry", "label": "Serbian sappers"},
        {"id": "o-fleet", "side": "ottoman", "kind": "fleet", "label": "Ottoman fleet", "strength": "c. 110 ships (modern est.)"},
        {"id": "o-portage", "side": "ottoman", "kind": "fleet", "label": "Ships hauled overland"},
        {"id": "b-constantine", "side": "byzantine", "kind": "infantry", "label": "Constantine XI"},
        {"id": "b-giustiniani", "side": "byzantine", "kind": "heavy_infantry", "label": "Giustiniani"},
        {"id": "b-venetians", "side": "byzantine", "kind": "infantry", "label": "Venetians"},
        {"id": "b-south", "side": "byzantine", "kind": "infantry", "label": "South wall"},
        {"id": "b-reserve", "side": "byzantine", "kind": "infantry", "label": "Reserve"},
        {"id": "b-fleet", "side": "byzantine", "kind": "fleet", "label": "Christian ships", "strength": "26 ships"},
        {"id": "b-chain", "side": "byzantine", "kind": "standard", "label": "Chain (boom)"},
        {"id": "b-relief", "side": "byzantine", "kind": "fleet", "label": "Relief flotilla"},
    ]
    terrain = [
        {"id": "land-walls", "kind": "wall", "label": "Theodosian land walls", "line": LANDWALL, "conjectural": True},
        {"id": "chain", "kind": "wall", "label": "Chain across the Golden Horn", "line": CHAIN, "conjectural": True},
        {"id": "portage", "kind": "road", "label": "Overland track (conj.)", "line": PORTAGE, "conjectural": True},
        {"id": "golden-horn", "kind": "label", "label": "Golden Horn", "at": L(28.9540, 41.0420)},
        {"id": "mesoteichion", "kind": "label", "label": "Mesoteichion (St Romanus Gate)", "at": P(250, -150)},
        {"id": "blachernae", "kind": "town", "label": "Blachernae", "at": G("blachernae")},
        {"id": "galata", "kind": "town", "label": "Galata (Pera)", "at": G("galata")},
        {"id": "hagia-sophia", "kind": "building", "label": "Hagia Sophia", "at": G("hagia-sophia")},
        {"id": "golden-gate", "kind": "pass", "label": "Golden Gate", "at": G("golden-gate")},
        {"id": "edirne", "kind": "pass", "label": "Charisian Gate", "at": G("edirne")},
    ]
    return st.doc(
        slug="fall-of-constantinople", kind="siege", schema=3,
        entity={"name": "Fall of Constantinople", "wikidata": "Q160077"},
        title="Fall of Constantinople", date_label="6 April - 29 May 1453", year=1453,
        intro=("In the spring of 1453 the twenty-one-year-old Sultan Mehmed II besieged Constantinople, the last real stronghold of "
               "the Byzantine Empire and a city that had stood behind its walls for a thousand years. The defenders, about eight "
               "thousand strong including Genoese, Venetian, Catalan and other volunteers under Emperor Constantine XI, faced an army "
               "that Western accounts number at around a hundred thousand, together with a large fleet and an unusual train of heavy "
               "guns. The land walls on the west held for seven weeks against bombardment, assaults and mining, and the Golden Horn "
               "was sealed by a chain until the Ottomans dragged ships over the hill of Galata. Before dawn on 29 May the last attack "
               "broke through, helped by the wounding of the Genoese captain Giustiniani, and the city fell."),
        outcome="Ottoman victory: Constantinople taken, Constantine XI killed, the Byzantine Empire ended.",
        uncertainty=("Troop figures are contemporary estimates and vary widely, as do fleet sizes and gun counts. The land wall line is "
                     "drawn through the gate positions from map data and is approximate in between. The chain's line, the overland track "
                     "of the ships, the reserve positions and the miners' sectors are reconstructions. Constantine's death and the "
                     "performance of the Orban gun are disputed in the sources."),
        sources=[{"title": "Fall of Constantinople - Wikipedia", "url": "https://en.wikipedia.org/wiki/Fall_of_Constantinople", "kind": "web"}],
        sides=[
            {"id": "ottoman", "name": "Ottoman Empire", "color": "#b91c1c", "polity": {"name": "Ottoman Empire", "wikidata": "Q12560"},
             "commanders": [{"name": "Mehmed II", "wikidata": "Q34503", "role": "Sultan"},
                            {"name": "Zagan Pasha", "wikidata": "Q2353735", "role": "Commander"},
                            {"name": "Suleiman Baltoghlu", "wikidata": "Q376445", "role": "Admiral"},
                            {"name": "Ulubatli Hasan", "wikidata": "Q3622985", "role": "Janissary"}],
             "strength": "c. 100,000 (reported); 5,000 Janissaries", "losses": "Heavy; unknown"},
            {"id": "byzantine", "name": "Byzantine Empire and allies", "color": "#1d4ed8",
             "polity": {"name": "Byzantine Empire", "wikidata": "Q12544"},
             "commanders": [{"name": "Constantine XI", "wikidata": "Q37142", "role": "Emperor"},
                            {"name": "Giovanni Giustiniani", "wikidata": "Q59879", "role": "Genoese captain"}],
             "strength": "c. 8,000 men, 26 ships", "losses": "Heavy; c. 4,000 civilians killed, c. 30,000 enslaved"},
        ],
        units=units, terrain=terrain)
