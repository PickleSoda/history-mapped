"""Battle of Blenheim, 13 August 1704 — map story builder.

Orientation (Wikipedia, Battle section): the Franco-Bavarian line ran about 6 km from the Danube at Blindheim (south-east
end) north-west through Oberglauheim to Lutzingen and the wooded Swabian Jura hills (north-west end), with the marshy
Nebel stream in front of it. The Allies marched in from the east via Schwenningen and stood on the NORTH-EAST bank of the
Nebel, attacking south-west across it: Cutts and Marlborough toward Blindheim and the plain, Eugene (the Allied right,
north-west) toward Lutzingen. Frame: Oberglauheim (10.57725, 48.64727) from `places`; Blindheim, Lutzingen, Unterglauheim,
Schwenningen, Hoechstaedt placed from their `places` coordinates. The Nebel east of Unterglauheim is the OSM waterway
fragment; its west course, its mouth and the Danube (no OSM line in range) are schematic. Unit sizes and order from the article.
"""
from pipeline.map_stories.geo import ellipse
from pipeline.map_stories.layout import Story, facing_off, local_frame

ANCHOR = (10.57725, 48.64727)  # Oberglauheim
P = local_frame(ANCHOR)

# OSM waterway=stream "Nebel" fragment, Unterglauheim to Blindheim
NEBEL_EAST = [[10.61336, 48.641], [10.61517, 48.6379], [10.61641, 48.63733], [10.61799, 48.63604], [10.61887, 48.63577],
              [10.62013, 48.63657], [10.62191, 48.6362], [10.62275, 48.63546], [10.62438, 48.63521], [10.62444, 48.63453],
              [10.62758, 48.63395], [10.62849, 48.63271]]
NEBEL_WEST = [P(-3000, 350), P(-2300, 330), P(-1500, 330), P(-700, 300), P(0, 330), P(900, 150), P(1700, -150),
              P(2300, -450), P(2650, -710)]
NEBEL_MOUTH = [[10.62849, 48.63271], P(4000, -2300), P(4400, -3000)]
DANUBE = [P(-3600, -4300), P(-1500, -4000), P(500, -3700), P(2500, -3300), P(4400, -3000), P(5600, -2900)]


def build() -> dict:
    st = Story()
    C = True
    east = ["al-cutts", "al-lumley", "al-orkney", "al-churchill", "al-cavalry", "fb-tallard-cav", "fb-tallard-inf",
            "fb-blenheim", "fb-blen-res", "al-marlborough"]
    west = ["al-eugene-inf", "al-eugene-cav", "fb-lutz-rozel", "fb-lutz-inf", "fb-bav-cav"]

    def fr(ids, v):
        for u in ids:
            st.put(u, frame=v)

    # ---- 1: Allied approach
    st.step("approach", "The Allies march in from the east", "02:00 to 06:00", """
        Forty squadrons of Allied cavalry leave camp at 02:00, and at 03:00 the main army follows in eight columns
        across the Kessel. By about 06:00 the head of the march reaches Schwenningen, three kilometres from Blindheim,
        where troops who held the village overnight form a ninth column. Marlborough and Eugene agree the plan:
        Marlborough, with 36,000 men, will take on Tallard, while Eugene's 16,000 will hold Marsin and the Elector.
        Tallard, fooled by prisoners' tales, believes the Allies are about to withdraw.""")
    for uid, x, y, f, w, d in [("al-cutts", 5000, 200, 225, 500, 120), ("al-lumley", 5300, 900, 225, 450, 60),
                               ("al-orkney", 4500, 700, 225, 700, 60), ("al-churchill", 4700, 1300, 225, 800, 80),
                               ("al-cavalry", 5600, 1700, 225, 1100, 80), ("al-horn", 3300, 2000, 250, 500, 80),
                               ("al-danes", 2400, 2500, 250, 500, 60), ("al-eugene-inf", 1200, 2800, 270, 800, 100),
                               ("al-eugene-cav", 2400, 3050, 270, 1000, 70)]:
        st.put(uid, at=P(x, y), facing=f, width=w, depth=d, conjectural=C)
    st.put("al-marlborough", at=P(4700, 1500), facing=225, conjectural=C)
    st.pin("al-marlborough", "al-churchill")
    for uid in ["fb-lutz-rozel", "fb-lutz-inf", "fb-bav-cav", "fb-marsin", "fb-oberglau", "fb-tallard-cav",
                "fb-tallard-inf", "fb-blenheim", "fb-blen-res"]:
        st.put(uid, at=P(0, -900), facing=0, width=100, depth=40, state="hidden", conjectural=C)
    st.side_move("a", "march", [P(7000, 1600), P(5300, 800)], label="Allied columns")
    st.note(P(5254, 780), "Schwenningen, c. 06:00", "label")

    # ---- 2: Franco-Bavarian deployment, Allies form up
    st.step("deploy", "Both armies take position", "08:00 to 11:00", """
        Signal guns recall the French foragers and the army forms behind the Nebel. Maffei holds Lutzingen with five
        Bavarian battalions and sixteen guns, Rozel's seven French battalions stand in the woods beside it, and cavalry
        fill the gap to Oberglauheim, packed with fourteen battalions under Blainville. Tallard draws his horse up
        between that village and Blindheim, where Clérambault holds nine battalions. The Allies form beyond the stream,
        taking cannon fire for hours; many of their generals doubt the attack can succeed.""")
    for uid, x, y, f, w, d in [
            ("fb-lutz-rozel", -3200, -100, 0, 400, 150), ("fb-lutz-inf", -2650, -100, 0, 300, 120),
            ("fb-bav-cav", -1700, 110, 0, 1200, 60), ("fb-marsin", -650, 60, 0, 600, 60),
            ("fb-oberglau", 0, -30, 0, 400, 200), ("fb-tallard-cav", 1700, -650, 30, 1700, 60),
            ("fb-tallard-inf", 1500, -1000, 30, 600, 100), ("fb-blenheim", 3060, -1700, 30, 450, 350),
            ("fb-blen-res", 3500, -2500, 30, 400, 100)]:
        st.put(uid, at=P(x, y), facing=f, width=w, depth=d, state="ready", conjectural=C)
    for uid, x, y, f, w, d in [
            ("al-eugene-inf", -2700, 1300, 180, 800, 100), ("al-eugene-cav", -1600, 1300, 180, 1000, 70),
            ("al-danes", -700, 950, 180, 500, 60), ("al-horn", -200, 750, 190, 500, 80),
            ("al-orkney", 900, 450, 210, 700, 60), ("al-churchill", 1500, 800, 210, 1000, 80),
            ("al-cavalry", 1700, 1300, 210, 1100, 80), ("al-lumley", 2750, 250, 210, 450, 60),
            ("al-cutts", 3750, -850, 225, 500, 120)]:
        st.put(uid, at=P(x, y), facing=f, width=w, depth=d, move="march", conjectural=C)
    st.put("al-fugger", at=P(-1050, 1550), facing=180, width=400, depth=60, frame=False, conjectural=C)
    st.note(P(700, 600), "Allied lines form beyond the Nebel", "label")

    # ---- 3: Cutts' first assault
    st.step("cutts1", "Cutts's first assault on Blindheim", "13:00", """
        By 10:00 Cutts has cleared two mills on the stream and sits in front of Blindheim under a six-gun battery.
        At 13:00 Rowe's brigade advances silently across about 150 metres. The French hold their fire until thirty
        metres and then deliver a deadly volley; Rowe falls mortally wounded. Small parties break in but are thrown
        out, and the Gens d'Armes ride down on the exposed flank until Wilkes's Hessians stand firm and drive them off.""")
    st.put("al-cutts", facing_off(st.pl("fb-blenheim"), depth=120, gap=30, width=500), move="attack", state="engaged",
           conjectural=C)
    st.put("fb-blenheim", state="engaged")
    st.note(P(3500, -1400), "Rowe falls at the palisades", "death")

    # ---- 4: second assault and crowding
    st.step("cutts2", "The village is crammed with men", "Early afternoon", """
        The Allies rally and storm again, and again fail. The repeated blows panic Clérambault, who without asking
        Tallard orders his reserve battalions into Blindheim. The village fills so tightly that, in one French
        officer's words, the men could not even fire, and the garrison loses the power to move. Marlborough sees the
        mistake and cancels a third assault: Cutts is merely to contain the village, and no more than 5,000 Allies
        hold twice that number of French in place.""")
    st.put("fb-blen-res", at=P(3060, -1975), width=450, depth=100, move="advance", state="engaged", conjectural=C)
    st.put("al-cutts", facing_off(st.pl("fb-blenheim"), depth=120, gap=6, width=500), move="attack", conjectural=C)
    st.note(P(3380, -2080), "Reserve battalions pour into the village", "event")

    # ---- 5: Eugene's first attack
    st.step("lutz1", "Eugene's first attack at Lutzingen", "c. 13:00 to 14:00", """
        On the Allied right Anhalt-Dessau leads four Prussian and Danish brigades across the Nebel toward Lutzingen.
        Maffei's infantry and the sixteen-gun battery, with guns enfilading from the wood, tear into them as they
        cross. Eugene's cavalry follows and enjoys a first success, but Marsin's second line drives it back over the
        stream in confusion. Left without horse, the foot are forced to retire as well, losing ten colours.""",
        camera={"center": P(-1700, 500), "zoom": 14})
    st.put("al-eugene-inf", facing_off(st.pl("fb-lutz-inf"), depth=100, gap=40, width=800), move="attack",
           state="engaged", conjectural=C)
    st.put("al-eugene-cav", facing_off(st.pl("fb-bav-cav"), depth=70, gap=40, width=1000), move="attack",
           state="engaged", conjectural=C)
    st.put("fb-lutz-inf", state="engaged")
    st.put("fb-bav-cav", state="engaged")
    st.note(P(-2650, 350), "Prussians meet the great battery", "clash")
    fr(east, False)

    # ---- 6: second and third attack
    st.step("lutz2", "Eugene is repulsed again and again", "c. 14:00 to 16:00", """
        Eugene rallies his men near Schwennenbach, well behind their start line, and tries a second time, led by
        the Duke of Württemberg-Teck's second-line squadrons and Anhalt-Dessau's foot. Caught again in the crossfire
        from the guns at Lutzingen and Oberglauheim, they fall back across the stream. A third effort fares no
        better, and by mid-afternoon his wing has been driven back to the woods and mauled, though it still pins
        the Elector's and Marsin's troops.""", camera={"center": P(-1700, 600), "zoom": 14})
    st.put("al-eugene-inf", at=P(-2650, 1050), state="wavering", move="retreat", conjectural=C)
    st.put("al-eugene-cav", at=P(-1650, 1000), state="wavering", move="retreat", conjectural=C)
    st.put("fb-lutz-inf", state="ready")
    st.put("fb-bav-cav", state="ready")
    st.note(P(-2300, 750), "Third attack thrown back", "clash")

    # ---- 7: Marlborough crosses the Nebel
    st.step("crossing", "Marlborough crosses the Nebel", "c. 13:00 to 15:00", """
        With Cutts and Eugene engaged, Marlborough sends Hulsen's and Orkney's brigades over the stream on bridges
        built across the marsh, covered by dismounted dragoons and ten squadrons. Churchill's foot and further horse
        form up beyond it, the battalions spaced to let cavalry pass between them. Zurlauben's Gens d'Armes charge
        Lumley's horse but five squadrons under Palmes throw them back. Marsin refuses Tallard's plea for help.""")
    st.put("al-orkney", at=P(1300, -150), facing=210, move="advance", conjectural=C)
    st.put("al-churchill", at=P(2100, -250), facing=210, width=800, move="advance", conjectural=C)
    st.put("al-cavalry", at=P(1700, 300), move="advance", conjectural=C)
    st.put("al-lumley", at=P(2800, -450), move="advance", conjectural=C)
    st.put("fb-tallard-cav", state="wavering")
    fr(east, True)
    st.note(P(2600, -700), "Gens d'Armes driven back by Palmes", "clash")

    # ---- 8: Oberglauheim
    st.step("oberglau", "Disaster at Oberglauheim", "Mid-afternoon", """
        Before the centre can strike, Oberglauheim must be secured. Count Horn sends Holstein-Beck to take it, but his
        two Dutch brigades are cut down by French and Irish troops and he is captured, badly wounded. The Danes are
        driven back over the stream. Seeing the Allied army about to be split, Marsin turns his cavalry from Eugene
        toward the open flank of Churchill's infantry drawn up before Unterglauheim. The battle hangs in the balance.""",
        camera={"center": P(-300, 300), "zoom": 14})
    st.put("al-horn", facing_off(st.pl("fb-oberglau"), depth=80, gap=40, width=500), move="attack", state="wavering",
           conjectural=C)
    st.put("fb-oberglau", state="engaged")
    st.put("al-danes", at=P(-700, 1150), move="retreat", state="wavering", conjectural=C)
    st.put("fb-marsin", at=P(-560, -20), facing=100, move="flank", conjectural=C)
    st.note(P(-150, 330), "Holstein-Beck's Dutch broken", "clash")
    fr(east + west, False)
    fr(["fb-marsin", "fb-oberglau", "al-horn", "al-danes"], True)

    # ---- 9: Marlborough's reply
    st.step("reply", "Marlborough answers the threat", "c. 16:00", """
        Marlborough crosses on a makeshift bridge to take charge. He orders Hulsen's Hanoverians up to support the
        Dutch, brings forward a nine-gun battery and asks Eugene for Fugger's Imperial cuirassiers. Eugene sends them
        despite his own troubles. Marsin must change front, and Fugger charges at a favourable angle and throws his
        squadrons back in disorder. The Allied foot then push the French and Irish into Oberglauheim, penned there for
        the rest of the day, while Marlborough completes his line.""", camera={"center": P(-200, 300), "zoom": 14})
    st.put("fb-marsin", at=P(-620, -20), facing=0, state="wavering", move="back_water", conjectural=C)
    st.put("al-fugger", facing_off(st.pl("fb-marsin"), depth=60, gap=6, width=400), move="charge", state="engaged",
           conjectural=C)
    st.put("al-horn", at=P(0, 150), facing=190, move="advance", state="engaged", conjectural=C)
    st.put("al-cavalry", at=P(1700, 200), state="ready", conjectural=C)
    st.note(P(-620, 120), "Fugger's cuirassiers charge", "clash")
    fr(["al-fugger"], True)

    # ---- 10: the charge
    st.step("charge", "The charge in the centre", "Just after 17:00", """
        By now much of the Franco-Bavarian army is bottled up in Blindheim and Oberglauheim. In the centre
        Marlborough has about 81 squadrons and 18 battalions against Tallard's 64 squadrons and nine raw battalions.
        He puts his horse in front of the foot and sends them forward. Tallard's tired, unsupported cavalry first push
        the first line back, but the second line, brought up by Bülow and Bothmer, drives through the middle.""")
    st.put("al-cavalry", facing_off(st.pl("fb-tallard-cav"), depth=80, gap=6, width=1100), move="charge",
           state="engaged", conjectural=C)
    st.put("fb-tallard-cav", state="engaged")
    fr(east + west, True)
    st.note(P(1700, -300), "Marlborough's horse breaks the centre", "clash")

    # ---- 11: rout
    st.step("rout", "Tallard's army breaks", "Evening", """
        Tallard's cavalry flees toward Höchstädt and the Danube, where more than 3,000 horse are said to drown. The nine
        French battalions left on the open plain are overwhelmed by close-range gunfire and platoon volleys, and
        Tallard himself is taken prisoner. At Lutzingen Eugene's Prussians at last storm the Bavarian battery. With the
        centre gone, Marsin and the Elector give up their wings and fall back.""")
    st.put("fb-tallard-cav", at=P(1300, -3150), facing=180, state="routed", move="rout", conjectural=C)
    st.put("fb-tallard-inf", state="destroyed")
    st.put("al-cavalry", at=P(1550, -1000), move="pursuit", state="ready", conjectural=C)
    st.put("fb-marsin", at=P(-1800, -700), facing=270, state="routed", move="retreat", conjectural=C)
    st.put("fb-bav-cav", at=P(-2900, -300), state="routed", move="retreat", conjectural=C)
    st.put("al-eugene-inf", facing_off(st.pl("fb-lutz-inf"), depth=100, gap=6, width=800), move="attack",
           state="engaged", conjectural=C)
    st.put("fb-lutz-inf", state="wavering")
    st.note(P(1300, -3400), "Over 3,000 French horse drown", "death")

    # ---- 12: Blindheim surrenders
    st.step("surrender", "Blindheim surrenders", "Evening to night, 13 August", """
        The troops crowded into Blindheim are cut off and surrounded. After failing to break out, they lay down their
        arms in the night. The day leaves the Franco-Bavarian army shattered, with its commander captured and Bavaria
        soon to be lost to the Elector.""")
    st.put("fb-blenheim", state="captured", by="a")
    st.put("fb-blen-res", state="captured", by="a")
    st.put("al-cutts", state="engaged")
    st.put("al-churchill", at=P(2500, -900), move="advance", state="ready", conjectural=C)
    st.put("fb-oberglau", state="wavering")
    st.note(P(3060, -2150), "Blindheim garrison surrenders", "capture")

    return st.doc(
        slug="battle-of-blenheim", kind="battle", schema=2,
        entity={"name": "Battle of Blenheim", "wikidata": "Q154635"},
        title="Battle of Blenheim", date_label="13 August 1704", year=1704,
        intro="""On 13 August 1704 the Duke of Marlborough and Prince Eugene of Savoy attacked a Franco-Bavarian army
        on the north bank of the Danube, near the village of Blindheim in Bavaria. Tallard, Marsin and the Elector
        Maximilian II Emanuel held a strong six-kilometre front behind the marshy Nebel stream, from the Danube to the
        wooded hills beyond Lutzingen, with the Allies slightly fewer in men and facing more guns. The Allies marched
        in from the east that morning; Cutts pinned Tallard's garrison in Blindheim, Eugene held the Elector and Marsin
        at Lutzingen, and Marlborough crossed the stream and broke the weakened centre with a late cavalry charge.
        The victory saved Vienna and knocked Bavaria out of the War of the Spanish Succession.""",
        outcome="Decisive Grand Alliance victory: Tallard captured, Blindheim garrison surrendered, Bavaria knocked out of the war.",
        uncertainty="""The Nebel east of Unterglauheim follows an OpenStreetMap stream; its west course is schematic. The
        exact frontages of brigades and squadrons are reconstructed from the Wikipedia order
        of battle rather than surveyed, so the unit placements and sizes are conjectural. Timings of the attacks at
        Lutzingen and Oberglauheim are given only loosely in the sources, so those steps use approximate times, and
        the order of the second and third attacks at Lutzingen is simplified.""",
        sources=[{"title": "Battle of Blenheim — Wikipedia", "url": "https://en.wikipedia.org/wiki/Battle_of_Blenheim", "kind": "web"}],
        sides=[
            {"id": "a", "name": "Grand Alliance", "color": "#b91c1c",
             "polity": {"name": "Holy Roman Empire", "wikidata": "Q12548"},
             "commanders": [{"name": "Duke of Marlborough", "wikidata": "Q153803", "role": "commander"},
                            {"name": "Prince Eugene of Savoy", "wikidata": "Q152428", "role": "commander"}],
             "strength": "52,000; 66 guns", "losses": "4,542 killed, 7,942 wounded, 500 captured"},
            {"id": "f", "name": "Franco-Bavarian army", "color": "#1d4ed8",
             "polity": {"name": "Kingdom of France", "wikidata": "Q70972"},
             "commanders": [{"name": "Duc de Tallard", "wikidata": "Q112932", "role": "commander"},
                            {"name": "Ferdinand de Marsin", "wikidata": "Q614104", "role": "commander"},
                            {"name": "Maximilian II Emanuel", "wikidata": "Q57628", "role": "Elector of Bavaria"}],
             "strength": "56,000; 90 guns",
             "losses": "6,000 killed or drowned, 7,000 wounded, 14,190 captured"},
        ],
        units=[
            {"id": "fb-lutz-rozel", "side": "f", "kind": "infantry", "label": "Rozel, 7 battalions", "strength": "7 battalions"},
            {"id": "fb-lutz-inf", "side": "f", "kind": "infantry", "label": "Maffei at Lutzingen", "strength": "5 battalions, 16 guns"},
            {"id": "fb-bav-cav", "side": "f", "kind": "cavalry", "label": "Bavarian cavalry", "strength": "c. 54 squadrons"},
            {"id": "fb-marsin", "side": "f", "kind": "cavalry", "label": "Marsin's cavalry", "strength": "40 squadrons, 12 battalions"},
            {"id": "fb-oberglau", "side": "f", "kind": "infantry", "label": "Blainville, 14 bn", "strength": "14 battalions"},
            {"id": "fb-tallard-cav", "side": "f", "kind": "heavy_cavalry", "label": "Tallard's cavalry", "strength": "64 squadrons"},
            {"id": "fb-tallard-inf", "side": "f", "kind": "infantry", "label": "Nine raw battalions", "strength": "9 battalions"},
            {"id": "fb-blenheim", "side": "f", "kind": "infantry", "label": "Blindheim garrison", "strength": "9 battalions at first"},
            {"id": "fb-blen-res", "side": "f", "kind": "infantry", "label": "Clérambault's reserve", "strength": "reserve battalions"},
            {"id": "al-eugene-inf", "side": "a", "kind": "infantry", "label": "Prussians and Danes"},
            {"id": "al-eugene-cav", "side": "a", "kind": "cavalry", "label": "Imperial cavalry"},
            {"id": "al-danes", "side": "a", "kind": "cavalry", "label": "Danish cavalry"},
            {"id": "al-fugger", "side": "a", "kind": "heavy_cavalry", "label": "Fugger's cuirassiers"},
            {"id": "al-horn", "side": "a", "kind": "infantry", "label": "Horn's Dutch"},
            {"id": "al-orkney", "side": "a", "kind": "infantry", "label": "Orkney and Hulsen"},
            {"id": "al-churchill", "side": "a", "kind": "infantry", "label": "Churchill's infantry"},
            {"id": "al-cavalry", "side": "a", "kind": "heavy_cavalry", "label": "Marlborough's horse"},
            {"id": "al-lumley", "side": "a", "kind": "cavalry", "label": "Lumley's horse"},
            {"id": "al-cutts", "side": "a", "kind": "infantry", "label": "Cutts's column"},
            {"id": "al-marlborough", "side": "a", "kind": "commander", "label": "Marlborough"},
        ],
        terrain=[
            {"id": "nebel-east", "kind": "stream", "label": "Nebel", "line": NEBEL_EAST},
            {"id": "nebel-west", "kind": "stream", "label": "Nebel", "line": NEBEL_WEST, "conjectural": True},
            {"id": "marsh-centre", "kind": "marsh", "label": "Nebel marshes", "area": ellipse(P(1500, -100), 1300, 230, 25),
             "conjectural": True},
            {"id": "marsh-west", "kind": "marsh", "label": "Marshy meadows", "area": ellipse(P(-1300, 320), 1000, 180),
             "conjectural": True},
            {"id": "blindheim", "kind": "village", "label": "Blindheim", "at": P(3043, -1724)},
            {"id": "oberglau", "kind": "village", "label": "Oberglauheim", "at": P(0, 0)},
            {"id": "lutzingen", "kind": "village", "label": "Lutzingen", "at": P(-2622, -120)},
            {"id": "unterglau", "kind": "village", "label": "Unterglauheim", "at": P(2237, 169)},
            {"id": "schwenningen", "kind": "village", "label": "Schwenningen", "at": P(5254, 734)},
            {"id": "hoechstaedt", "kind": "town", "label": "Höchstädt", "at": P(-76, -3980)},
            {"id": "woods", "kind": "woods", "label": "Wooded hills", "area": ellipse(P(-3500, -100), 450, 900),
             "conjectural": True},
        ],
    )
