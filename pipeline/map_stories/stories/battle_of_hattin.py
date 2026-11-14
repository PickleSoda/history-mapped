"""Battle of Hattin, 3-4 July 1187 - map story builder.

Anchors: Horns of Hattin (OSM peak 35.45955, 32.79824) is the origin; Hittin village, Tiberias, Kafr Sabt, Lubya,
Nimrin, Zippori (La Saphorie) and the Turan area come from `places`. Franks marched west to east from Zippori along the
Acre-Tiberias road, facing east; Saladin's army lay across the road to the east and surrounded them, so Muslim blocks
face west (270). The Horns stand east of the night camp, between it and the spring of Hittin and the lake.
Camp site near Meskenah/Lubya, the road line and all block frontages are reconstructed (conjectural).
Sources: Wikipedia "Battle of Hattin" (Location, Siege of Tiberias, Battle, Surrender, Aftermath).
"""
from pipeline.map_stories.geo import local
from pipeline.map_stories.layout import Story, ent, local_frame, when

ANCHOR = (35.45955, 32.79824)
P = local_frame(ANCHOR)


def X(lon, lat):
    e, n = local((lon, lat), ANCHOR)
    return P(e, n)


ZIPPORI = X(35.27812, 32.74431)
TURAN = X(35.37403, 32.77689)
LUBYA = X(35.42020, 32.77285)
NIMRIN = X(35.42346, 32.80420)
KAFR = X(35.44079, 32.74358)
HITTIN = X(35.50134, 32.80056)
TIBERIAS = X(35.53286, 32.79385)
HORNS = P(0, 0)
ROAD = [ZIPPORI, X(35.33, 32.76), TURAN, P(-5200, -1100), P(-3300, -700), P(-1500, -300), HORNS, HITTIN, TIBERIAS]
HORNS_AREA = [P(-420, -180), P(-250, 260), P(150, 280), P(420, 60), P(300, -230), P(-100, -280)]
PLATEAU = [P(-4800, -1700), P(-4600, 600), P(-2200, 900), P(-2000, -1500)]


def build() -> dict:
    st = Story()
    # 1
    st.step("muster", "The Franks gather at La Saphorie", "Late June - 2 July 1187", """
        Saladin crossed the Jordan on 30 June with the largest army he had ever led, about 40,000 men of whom some
        12,000 were regular cavalry, and camped at Kafr Sabt. The Frankish host, 18,000 to 20,000 strong with some
        1,200 knights, waited at the well-watered castle of La Saphorie, a strong position with water close at hand.
        On 2 July Saladin stormed Tiberias, the town of Count Raymond, in the hope that its fall would draw the
        Franks out of their camp. Raymond's wife held on in the citadel.""", date=when(1187, 7, 2))
    st.put("f-host", at=ZIPPORI, facing=90, width=900, depth=500, state="ready", frame=False)
    st.put("m-main", at=KAFR, facing=270, width=1800, depth=500)
    st.put("m-siege", at=offset_(TIBERIAS, -300, 0), facing=90, width=500, depth=250, state="engaged")
    st.put("f-garrison", at=offset_(TIBERIAS, 250, 150), facing=270, width=150, depth=100, state="engaged")
    st.note(TIBERIAS, "Tiberias stormed, citadel holds", "event")
    # 2
    st.step("council", "The night council", "Night of 2 July", """
        That night Raymond of Tripoli argued that a march across the dry hills to Tiberias was exactly what Saladin
        wanted, and that the camp at La Saphorie should be held while Tiberias, his own town, was given up if need
        be. Gerard de Ridefort and Raynald of Chatillon answered by calling him a coward. King Guy sided with them
        and ordered the army out at once against Saladin.""", date=when(1187, 7, 2))
    st.put("f-host", state="ready")
    st.note(offset_(TIBERIAS, -2500, 900), "Council at La Saphorie, far west", "label", conjectural=True)
    # 3
    st.step("march", "The march into the heat", "Morning, 3 July", """
        The Frankish army left La Saphorie and struggled east in the July heat, with Raymond's division in front and
        Balian's and Joscelin's men in the rear. Muslim mounted archers harassed it from the first mile. The Springs
        of Turan gave far too little water for such a host. Saladin, learning the Franks had left their water, broke
        off from Tiberias and brought his army out to meet them.""", date=when(1187, 7, 3))
    st.put("f-host", state="ready")
    st.hide("f-host")
    st.put("f-van", at=TURAN, facing=90, width=500, depth=400, state="ready")
    st.put("f-centre", at=offset_(TURAN, -900, -200), facing=90, width=500, depth=500, state="ready")
    st.put("f-rear", at=offset_(TURAN, -1900, -400), facing=90, width=500, depth=450, state="ready")
    st.put("f-foot", at=offset_(TURAN, -1100, -600), facing=90, width=450, depth=700, state="ready")
    st.put("m-main", at=P(1500, -800), facing=270, width=1800, depth=500, move="advance")
    st.put("m-archers", at=P(-2000, 1100), facing=225, width=900, depth=180, state="ready")
    st.hide("m-siege")
    st.note(TURAN, "Springs of Turan: too little water", "label")
    # 4
    st.step("turn", "Veering for Hattin", "Midday, 3 July", """
        At midday Raymond judged that the army could not reach Tiberias by nightfall, and he and Guy turned it left
        toward the springs at Kafr Hattin, about nine kilometres off, to drink there and go down to the lake next
        day. Saladin's men slid between the Franks and the water, and the column, hemmed in and tormented by thirst,
        had to halt on the dry plateau near Meskenah. Reaching the wells that day had become impossible.""",
        date=when(1187, 7, 3))
    st.put("f-van", at=P(-3300, -900), facing=75, width=500, depth=400, move="march")
    st.put("f-centre", at=P(-3900, -1000), facing=75, width=500, depth=500, move="march")
    st.put("f-rear", at=P(-4700, -1200), facing=75, width=500, depth=450, move="march", state="engaged")
    st.put("f-foot", at=P(-4100, -1500), facing=75, width=450, depth=700, move="march")
    st.put("m-archers", at=P(-4100, 700), facing=200, width=1200, depth=180, state="engaged", move="flank")
    st.put("m-right", at=P(-1900, 1400), facing=250, width=1000, depth=400, state="ready", conjectural=True)
    st.put("m-main", at=P(-1000, -400), facing=270, width=1400, depth=450, move="advance")
    st.put("m-left", at=P(-2200, -2400), facing=300, width=1000, depth=400, state="ready", conjectural=True)
    st.note(P(-2200, -300), "Muslims close the road to the water", "event")
    # 5
    st.step("night", "A night without water", "Night of 3-4 July", """
        The Franks pitched camp on the arid plateau, so closely ringed that, in one chronicler's phrase, a cat could
        not have slipped out. The Muslims prayed, sang and beat drums through the dark, and set fire to the dry
        grass so that smoke and heat added to the thirst. Their own camels brought skins of water up from the lake.
        Fresh arrows, 400 camel loads of them, reached Gokbori's archers.""", date=when(1187, 7, 3), light="night")
    st.put("f-van", at=P(-3000, -700), facing=90, width=500, depth=350, state="ready", move=None)
    st.put("f-centre", at=P(-3500, -800), facing=90, width=500, depth=400, state="ready")
    st.put("f-rear", at=P(-4100, -900), facing=90, width=500, depth=400, state="ready")
    st.put("f-foot", at=P(-3600, -1300), facing=90, width=450, depth=500, state="ready")
    st.put("m-main", at=P(-1900, -500), facing=270, width=1300, depth=350, state="ready", move="march")
    st.put("m-right", at=P(-3300, 700), facing=225, width=1100, depth=350, move="march")
    st.put("m-left", at=P(-3000, -1800), facing=315, width=1100, depth=350, move="march")
    st.put("m-archers", at=P(-4300, 100), facing=90, width=700, depth=250, state="ready", move="flank")
    st.put("m-camels", at=P(2500, -400), facing=270, width=250, depth=200, state="ready")
    st.note(P(-2600, 400), "Grass fired: smoke and heat", "event")
    st.note(P(-2800, -1100), "Camp on the dry plateau", "label", conjectural=True)
    # 6
    st.step("dawn", "Smoke and arrows", "Dawn, 4 July", """
        Morning showed the Franks blinded by smoke from the grass fires and under steady fire from Gokbori's horse
        archers on the left of Saladin's line. Gerard and Raynald urged Guy to form for battle and fight through.
        Raymond took the first division with Raymond of Antioch, Guy the centre with the True Cross, while Balian
        and Joscelin of Edessa brought up the rear.""", date=when(1187, 7, 4), light="dawn")
    st.put("f-van", at=P(-2600, -500), facing=90, width=600, depth=300, state="ready")
    st.put("f-centre", at=P(-3100, -600), facing=90, width=600, depth=350, state="ready")
    st.put("f-rear", at=P(-3700, -700), facing=90, width=600, depth=300, state="engaged")
    st.put("f-foot", at=P(-3100, -1100), facing=90, width=450, depth=500, state="ready")
    st.put("m-left", at=P(-2900, -1500), facing=315, width=1100, depth=300, state="engaged", move="attack")
    st.put("m-right", at=P(-3000, 650), facing=225, width=1000, depth=300, state="engaged")
    st.fire("m-left", st.pl("f-centre")["at"], "arrows")
    st.note(P(-3000, 100), "Smoke blows into Frankish faces", "event", conjectural=True)
    # 7
    st.step("advance", "Raymond's charge", "Morning, 4 July", """
        Thirsty and sapped, the Franks broke camp and headed again for the springs of Hattin, but Saladin's army
        blocked the road ahead and fell on the ragged column from behind as well. Count Raymond led two charges to
        break through to the lake and its water. The Muslim ranks parted before the second charge and let him
        through, and he reached the shore and rode on to Tyre.""", date=when(1187, 7, 4))
    st.put("f-van", at=P(-1500, -300), facing=90, width=550, depth=300, state="engaged", move="advance")
    st.put("f-centre", at=P(-2300, -450), facing=90, width=550, depth=350, state="engaged", move="advance")
    st.put("f-rear", at=P(-3000, -600), facing=90, width=600, depth=300, state="engaged", move="advance")
    st.put("f-foot", at=P(-2300, -1000), facing=90, width=450, depth=500, state="engaged", move="advance")
    st.put("m-main", at=P(-700, -250), facing=270, width=1200, depth=350, state="engaged", move="advance")
    st.put("m-right", at=P(-2200, 700), facing=250, width=900, depth=300, state="engaged", move="attack")
    st.put("m-left", at=P(-2200, -1600), facing=290, width=900, depth=300, state="engaged", move="attack")
    st.put("m-archers", at=P(-3300, -300), facing=90, width=600, depth=200, state="engaged", move="attack")
    st.pin("guy", "f-centre")
    st.pin("saladin", "m-main")
    st.note(P(-900, -200), "First clash on the road", "clash")
    # 8
    st.step("breakout", "Raymond escapes; the foot flee to the Horns", "Midday, 4 July", """
        After Raymond rode clear, Guy's position was hopeless. Most of the infantry had already broken and run up
        onto the Horns of Hattin, where they took no further part. Many men too weak with thirst to fight were
        killed on the spot or taken. Guy tried to pitch tents to block the Muslim horsemen, and the knights and
        mounted sergeants, though disordered, kept fighting around him.""", date=when(1187, 7, 4))
    st.put("f-van", at=P(4600, -1400), facing=90, width=300, depth=200, state="ready", move="charge", frame=False,
           conjectural=True)
    st.put("f-foot", at=P(-80, 20), facing=90, width=380, depth=250, state="wavering", move="rout")
    st.put("f-centre", at=P(-650, -150), facing=90, width=450, depth=300, state="engaged", move="advance")
    st.put("f-rear", at=P(-1500, -400), facing=90, width=500, depth=300, state="engaged", move="advance")
    st.put("m-main", at=P(-100, -150), facing=270, width=1000, depth=300, state="engaged", move="advance")
    st.put("m-right", at=P(-900, 500), facing=250, width=800, depth=250, state="engaged", move="advance")
    st.put("m-left", at=P(-900, -900), facing=290, width=800, depth=250, state="engaged", move="advance")
    st.put("m-archers", at=P(-2300, -400), facing=90, width=500, depth=200, state="engaged", move="pursuit")
    st.note(P(4100, -900), "Raymond reaches the lake, flees to Tyre", "event", conjectural=True)
    # 9
    st.step("horns", "Last stand on the Horns", "Afternoon, 4 July", """
        Encircled on the slope of the Horns, Guy's knights charged three times at the Muslims about Saladin. Saladin's
        young son al-Afdal later recalled how each charge drove the Muslims back on his father, whose face went pale
        and who cried out to rally them, and how each time the Muslims turned and pushed the Franks up the hill again.
        Saladin said the Franks were not beaten until Guy's tent fell. Then it fell.""", date=when(1187, 7, 4))
    st.put("f-centre", at=P(-80, -60), facing=90, width=350, depth=250, state="engaged", move="advance")
    st.put("f-rear", at=P(-250, 150), facing=90, width=350, depth=250, state="engaged", move="retreat")
    st.put("f-foot", at=P(120, 130), facing=90, width=300, depth=200, state="routed")
    st.put("m-main", at=P(-600, -80), facing=270, width=700, depth=250, state="engaged", move="attack")
    st.put("m-right", at=P(-300, 560), facing=225, width=600, depth=200, state="engaged", move="advance")
    st.put("m-left", at=P(-250, -620), facing=315, width=600, depth=200, state="engaged", move="advance")
    st.put("m-archers", at=P(450, 90), facing=270, width=400, depth=150, state="engaged", move="advance")
    st.note(P(-60, -30), "Guy's tent falls; Saladin gives thanks", "death")
    # 10
    st.step("surrender", "Guy and Raynald before Saladin", "Evening, 4 July", """
        Guy, his brother Amalric, Raynald of Chatillon, Gerard de Ridefort and many other barons were taken. Guy and
        Raynald were brought to Saladin's tent. Saladin offered Guy a cup of water, which among Muslims meant mercy,
        and Guy passed it on to Raynald; Saladin knocked it away, saying he had not offered it to that evil man, and
        accused Raynald of breaking the truce. Raynald was killed, by Saladin's own sword in some reports. Guy was
        told that kings do not kill kings.""", date=when(1187, 7, 4), light="dusk")
    st.put("f-centre", state="captured", by="b")
    st.put("f-rear", state="captured", by="b")
    st.put("f-foot", state="captured", by="b")
    st.put("m-main", at=P(-200, -90), state="ready", facing=90)
    st.put("m-right", state="ready")
    st.put("m-left", state="ready")
    st.put("m-archers", state="ready")
    st.put("saladin-tent", at=P(900, 250), facing=90, width=150, depth=100, state="ready", conjectural=True)
    st.note(P(900, 330), "Raynald executed by Saladin's order", "death")
    # 11
    st.step("aftermath", "After the field", "5 July and later", """
        Saladin spared the captured barons but had all about 200 captured Templar and Hospitaller knights beheaded, sparing
        only the Templar Grand Master, and the captured turcopoles were executed as apostates. The other prisoners
        were sold as slaves. The True Cross was sent to Damascus and Guy was held there until 1188. With the field
        army destroyed, the cities of the Kingdom of Jerusalem lay open to Saladin.""", date=when(1187, 7, 5))
    st.put("f-centre", state="destroyed")
    st.put("f-rear", state="destroyed")
    st.put("f-foot", state="captured", by="b")
    st.put("m-main", at=P(300, -100))
    st.put("m-archers", at=P(700, 250), move="march")
    st.note(P(200, 300), "About 200 knights beheaded", "death")
    st.note(HITTIN, "Springs of Hattin, now in Muslim hands", "label")

    return st.doc(slug="battle-of-hattin", kind="battle", entity={"name": "Battle of Hattin", "wikidata": "Q233568"},
        title="Battle of Hattin", date_label="3-4 July 1187", year=1187,
        intro="""In July 1187 Saladin, ruler of Egypt and Syria, led the largest army he had ever commanded across the
            Jordan into the Kingdom of Jerusalem. The Frankish host, gathered at the springs of La Saphorie, was
            drawn out by his assault on Tiberias and marched east across a waterless plateau in midsummer heat. On the
            night of 3 July Saladin's cavalry closed round it near the village of Meskenah, and the next morning,
            thirsty and surrounded, the Franks were broken at the double hill known as the Horns of Hattin, west of
            Tiberias. King Guy was taken with most of his barons, and the way lay open to Jerusalem.""",
        outcome="Ayyubid victory: the Frankish field army was destroyed; Guy of Lusignan was captured and Raynald of Chatillon executed.",
        uncertainty="""The sources do not fix the camp, the road line or the exact positions of each division. Placements
            of the night camp near Meskenah/Lubya, the Muslim wings, the Frankish divisions, Raymond's escape route and
            Saladin's tent are reconstructed and marked conjectural. Strengths are rough: figures for Saladin's army
            run from 20,000 to 40,000, and the Frankish infantry numbers are uncertain. Arrangements of the divisions
            in the march differ between the Latin and Arabic chroniclers.""",
        sources=[{"title": "Battle of Hattin - Wikipedia", "url": "https://en.wikipedia.org/wiki/Battle_of_Hattin",
                  "kind": "web"}],
        sides=[
            {"id": "a", "name": "Crusader states", "color": "#1d4ed8",
             "polity": {"name": "Kingdom of Jerusalem", "wikidata": "Q55502"},
             "commanders": [{"name": "Guy of Lusignan", "wikidata": "Q294192", "role": "King of Jerusalem"},
                            {"name": "Raymond III of Tripoli", "wikidata": "Q354389", "role": "van commander"},
                            {"name": "Raynald of Chatillon", "wikidata": "Q316831", "role": "lord of Oultrejourdain"},
                            {"name": "Balian of Ibelin", "wikidata": "Q374385", "role": "rearguard"}],
             "strength": "18,000-20,000 incl. c. 1,200 knights",
             "losses": "Most of the army killed or captured"},
            {"id": "b", "name": "Ayyubids", "color": "#15803d",
             "polity": {"name": "Ayyubid dynasty", "wikidata": "Q180114"},
             "commanders": [{"name": "Saladin", "wikidata": "Q8581", "role": "Sultan"},
                            {"name": "Gokbori", "wikidata": "Q18639250", "role": "left wing"},
                            {"name": "Al-Muzaffar Umar", "wikidata": "Q4703002", "role": "right wing"}],
             "strength": "20,000-40,000 incl. 12,000 regular cavalry", "losses": "Light"},
        ],
        units=[
            {"id": "f-host", "side": "a", "kind": "army", "label": "Frankish host", "strength": "18,000-20,000"},
            {"id": "f-garrison", "side": "a", "kind": "infantry", "label": "Tiberias citadel"},
            {"id": "f-van", "side": "a", "kind": "heavy_cavalry", "label": "Van: Raymond"},
            {"id": "f-centre", "side": "a", "kind": "heavy_cavalry", "label": "Centre: Guy, True Cross"},
            {"id": "f-rear", "side": "a", "kind": "heavy_cavalry", "label": "Rear: Balian, Joscelin"},
            {"id": "f-foot", "side": "a", "kind": "infantry", "label": "Frankish infantry"},
            {"id": "guy", "side": "a", "kind": "commander", "label": "Guy of Lusignan"},
            {"id": "m-main", "side": "b", "kind": "heavy_cavalry", "label": "Saladin's centre"},
            {"id": "m-siege", "side": "b", "kind": "siege_engine", "label": "Tiberias assault"},
            {"id": "m-archers", "side": "b", "kind": "horse_archers", "label": "Horse archers"},
            {"id": "m-right", "side": "b", "kind": "light_cavalry", "label": "Right: Taki ad-Din"},
            {"id": "m-left", "side": "b", "kind": "horse_archers", "label": "Left: Gokbori"},
            {"id": "m-camels", "side": "b", "kind": "camels", "label": "Water camels"},
            {"id": "saladin", "side": "b", "kind": "commander", "label": "Saladin"},
            {"id": "saladin-tent", "side": "b", "kind": "camp", "label": "Saladin's tent"},
        ],
        terrain=[
            {"id": "road", "kind": "road", "label": "Acre-Tiberias road", "line": ROAD, "conjectural": True},
            {"id": "horns", "kind": "hill", "label": "Horns of Hattin", "area": HORNS_AREA},
            {"id": "plateau", "kind": "field", "label": "Dry plateau, Meskenah", "area": PLATEAU, "conjectural": True},
            {"id": "hittin", "kind": "village", "label": "Hittin", "at": list(HITTIN)},
            {"id": "tiberias", "kind": "town", "label": "Tiberias", "at": list(TIBERIAS)},
            {"id": "kafr-sabt", "kind": "village", "label": "Kafr Sabt", "at": list(KAFR)},
            {"id": "lubya", "kind": "village", "label": "Lubya", "at": list(LUBYA)},
            {"id": "turan", "kind": "site", "label": "Springs of Turan", "at": list(TURAN)},
            {"id": "zippori", "kind": "village", "label": "La Saphorie", "at": list(ZIPPORI)},
        ])


def offset_(p, e, n):
    from pipeline.map_stories.geo import offset
    return offset(p, e, n)
