"""Battle of Zama, 19 October 202 BC (date per Wikidata) — map story builder.

Anchors: field centre = Wikidata P625 (9.44917, 36.29889), near the Draa el Metnan plain south of Sicca (El Kef).
Places finds no local anchors, so all terrain and the north-south axis are conjectural (mainstream reconstruction).
Orientation: Romans in the north facing south; Carthaginians in the south facing north. Roman right (Masinissa,
Numidians) = west; Roman left (Laelius) = east; Hannibal's Numidian cavalry on his left = west, facing Masinissa;
African cavalry on his right = east, facing Laelius. Carthaginian third line stood about 200 m behind the second.
Sources: Wikipedia, Battle of Zama (Polybius and Livy via the article).
"""
from pipeline.map_stories.geo import arc, ellipse, offset
from pipeline.map_stories.layout import Story, local_frame, screen, facing_off

ANCHOR = (9.44917, 36.29889)
P = local_frame(ANCHOR)

WADI = [P(-2600, 200), P(-1500, 120), P(-300, 260), P(900, 150), P(2600, 300)]
ROAD = [P(-2600, 1700), P(-1000, 1500), P(1000, 1450), P(2600, 1650)]
PLAIN = ellipse(P(0, 0), 2900, 1400)
CAMP_R = ellipse(P(-200, 1700), 500, 250)
CAMP_C = ellipse(P(200, -1550), 500, 250)


def build() -> dict:
    st = Story()

    # Step 1
    st.step("roman-lines", "Scipio draws up his legions", "Morning",
        """Scipio brings his army out of its camp onto the open plain. The legionary heavy infantry stands in the
        centre in three ranks: hastati in front, principes behind them and triarii last. Unlike the usual
        chessboard pattern, each maniple of principes sits directly behind a maniple of hastati, which leaves
        straight lanes through the line. The velites skirmish in those lanes. Masinissa's Numidian horse takes the
        right, Laelius's Roman and allied horse the left.""")
    st.put("r-hastati", at=P(0, 520), facing=180, width=1800, depth=50, state="ready")
    st.put("r-principes", at=P(0, 630), facing=180, width=1800, depth=50)
    st.put("r-triarii", at=P(0, 740), facing=180, width=1800, depth=50)
    st.put("r-velites", screen(st.pl("r-hastati"), gap=40, depth=10))
    st.put("r-masinissa", at=P(-1400, 520), facing=180, width=800, depth=70)
    st.put("r-laelius", at=P(1300, 520), facing=180, width=500, depth=60)
    st.put("r-numid-inf", at=P(-1400, 650), facing=180, width=700, depth=60, conjectural=True)
    st.put("r-scipio", at=P(0, 800), facing=180)
    st.pin("r-scipio", "r-triarii")

    # Step 2
    st.step("carthage-lines", "Hannibal's three lines", "Morning",
        """Hannibal, who has had no time to weld his three armies together, keeps them apart. Eighty elephants
        screened by slingers, archers and javelin-men stand in front. Behind them come the veterans of Mago's
        army, then Carthaginian and African levies, and about 200 metres further back the men brought home from
        Italy. His Numidian cavalry faces Masinissa on the left and African horse faces Laelius on the right.""")
    st.put("c-skirm", at=P(0, -330), facing=0, width=1800, depth=12, state="ready")
    st.put("c-elephants", at=P(0, -390), facing=0, width=1800, depth=20)
    st.put("c-line1", at=P(0, -480), facing=0, width=1800, depth=50)
    st.put("c-line2", at=P(0, -590), facing=0, width=1800, depth=50)
    st.put("c-line3", at=P(0, -820), facing=0, width=1700, depth=60)
    st.put("c-cav-num", at=P(-1400, -480), facing=0, width=800, depth=70)
    st.put("c-cav-afr", at=P(1300, -480), facing=0, width=700, depth=60)
    st.put("c-hannibal", at=P(0, -900), facing=0)
    st.pin("c-hannibal", "c-line3")

    # Step 3
    st.step("skirmish", "Javelins on the Numidian flank", "Late morning",
        """The armies advance. On the western wing the two bodies of Numidian horse trade javelins, charging in
        small groups and then wheeling away; the fighting is half-hearted. Hannibal then gives the order that
        sets the battle moving. The elephants lurch forward, and his first two lines follow them.""")
    st.put("c-cav-num", facing=0, at=P(-1400, -380), move="advance", state="engaged")
    st.put("r-masinissa", facing_off(st.pl("c-cav-num"), depth=70, gap=10, facing=180), state="engaged")
    st.put("c-elephants", at=P(0, -210), move="advance")
    st.put("c-skirm", at=P(0, -150), move="advance")
    st.put("c-line1", at=P(0, -300), move="advance")
    st.put("c-line2", at=P(0, -410), move="advance")

    # Step 4
    st.step("elephants", "The elephants are met", "Midday",
        """The velites run forward into the gap, throw javelins at the animals and fall back into the lanes. The
        Roman horns blare, and perhaps weapons beat on shields. Many elephants shy at the noise. Most of them
        plunge into the empty lanes, where javelins strike their flanks and those that emerge behind the army are
        hunted down. A few slam into the hastati and do real harm before they are driven off.""")
    st.put("r-velites", at=P(0, 330), move="advance", state="engaged")
    st.put("c-elephants", at=P(0, 330), move="charge", state="engaged", width=1700)
    st.put("r-hastati", state="engaged")
    st.note(P(0, 690), "Elephants lost in the lanes", "event")

    # Step 5
    st.step("cavalry-flight", "Both wings of cavalry drive off the enemy", "Midday",
        """Terrified elephants on the Carthaginian left stampede through their own Numidian horse. Masinissa
        seizes the moment and charges, and the broken squadrons flee with his men on their heels. On the other
        wing elephants that balked at the infantry turn on Laelius's horse and are wounded by javelins, then
        they crash into the Carthaginian cavalry. Laelius charges as well. Both Roman horse wings gallop away in
        pursuit, leaving the infantry to settle the day.""")
    st.put("c-elephants", state="destroyed")
    st.put("c-cav-num", at=P(-2300, -900), move="rout", state="routed", frame=False)
    st.put("r-masinissa", at=P(-2250, -780), move="pursuit", facing=225, state="engaged", frame=False)
    st.put("c-cav-afr", at=P(2200, -1000), move="rout", state="routed", frame=False)
    st.put("r-laelius", at=P(2150, -880), move="pursuit", facing=135, state="engaged", frame=False)
    st.put("r-numid-inf", at=P(-1400, 650), state="ready")

    # Step 6
    st.step("first-clash", "Hastati against the first line", "Afternoon",
        """With the wings empty, the Roman heavy infantry and the first two Carthaginian lines advance and crash
        together. It is a hard push of shield against shield. The Roman training and swords tell, and the
        Carthaginian first line breaks. The second line will not let the fugitives through, and they have to
        slip round its flanks. Many rally there and lengthen the second line's ends.""")
    st.hide("c-elephants")
    st.hide("r-velites")
    st.put("c-skirm", at=P(0, 250), state="routed", frame=True)
    st.put("c-line1", at=P(0, 100), move="advance", state="engaged", facing=0)
    st.put("r-hastati", facing_off(st.pl("c-line1"), depth=50, gap=4, facing=180), state="engaged", move="attack")
    st.put("c-line2", at=P(0, -80), move="advance", state="ready")
    st.put("r-principes", at=P(0, 380), move="advance")
    st.put("r-triarii", at=P(0, 500), move="advance")
    st.put("c-line3", at=P(0, -820))

    # Step 7
    st.step("second-line", "The second line pushes the Romans back", "Afternoon",
        """The hastati, already bloodied, now meet the Carthaginian and African spearmen of the second line, who
        fight fiercely and drive them back in disorder. Scipio has to feed the principes into the fight. They
        steady the line and at last break the second line, whose men retreat while the hastati chase them. Hannibal
        does not send his third line forward, and the ground between is slippery with corpses.""")
    st.put("c-line1", state="destroyed")
    st.hide("c-skirm")
    st.put("c-line2", at=P(0, -20), state="engaged", move="advance")
    st.put("r-hastati", at=P(0, 130), state="wavering")
    st.put("r-principes", facing_off(st.pl("c-line2"), depth=50, gap=4, facing=180), state="engaged", move="attack")
    st.note(P(0, 40), "Ground choked with the dead", "label")

    # Step 8
    st.step("recall", "Scipio recalls his men", "Afternoon",
        """The second line gives way, and the hastati pursue it. Scipio sees the risk and sounds the recall.
        The Romans pull back and re-form. The hastati stay in the centre while the principes and triarii move out to
        both sides to build one long line against Hannibal's rested veterans, who overlap it at each end. There is a
        long pause. Carthaginian survivors gather on the flanks and extend their line.""")
    st.put("c-line2", state="routed", at=P(0, -250), move="retreat")
    st.put("r-hastati", at=P(0, 280), facing=180, width=700, state="ready", move="back_water")
    st.put("r-principes", at=P(-750, 280), facing=180, width=800, state="ready", move="flank")
    st.put("r-triarii", at=P(750, 280), facing=180, width=800, state="ready", move="flank")
    st.put("c-line3", at=P(0, -80), width=1900, state="ready", move="advance")

    # Step 9
    st.step("last-clash", "The last fresh Carthaginian line", "Late afternoon",
        """The two heavy lines, now nearly equal in men, charge with great fury. Hannibal's soldiers are fresh and
        veterans of long campaigns. The Romans are tired but flushed with two victories that day. Their line is
        thinner, so they can no longer swap tired men for fresh ones. The fighting is a grim, even struggle and for
        some time neither side gives way.""")
    st.put("c-line3", at=P(0, 20), facing=0, state="engaged", move="attack")
    st.put("r-hastati", facing_off(st.pl("c-line3"), depth=40, gap=4, facing=180, width=700), state="engaged")
    st.put("r-principes", at=P(-750, 70), facing=180, state="engaged")
    st.put("r-triarii", at=P(750, 70), facing=180, state="engaged")
    st.note(P(0, 120), "Even, grinding fight", "clash")

    # Step 10
    st.step("cavalry-return", "The cavalry come back", "Late afternoon",
        """Masinissa and Laelius ride back from their long pursuit, at about the same moment. With the Carthaginian
        infantry pinned in the front, nothing can prevent the horse from falling on their rear. Both
        wings crash into the rear of the line. Polybius says the cavalry came back at just the right time.""")
    st.put("r-masinissa", at=P(-900, -520), facing=0, state="engaged", move="charge", frame=True)
    st.put("r-laelius", at=P(900, -520), facing=0, state="engaged", move="charge", frame=True)
    st.put("c-cav-num", state="destroyed")
    st.put("c-cav-afr", state="destroyed")

    # Step 11
    st.step("rout", "The Carthaginian line collapses", "Dusk",
        """Attacked from front and rear, the line gives way. Most of Hannibal's last line is cut down where it
        stands, and the survivors are caught by the cavalry. Hannibal gets away with a few others, but the army he
        led to Zama is destroyed.""")
    st.put("c-line3", state="destroyed", at=P(0, 20))
    st.put("c-hannibal", at=P(-900, -1500), move="retreat", facing=180, state="ready")
    st.put("r-masinissa", at=P(-800, -450), facing=0, state="engaged")
    st.put("r-laelius", at=P(800, -450), facing=0, state="engaged")
    st.put("r-hastati", state="ready")
    st.put("r-principes", state="ready")
    st.put("r-triarii", state="ready")
    st.note(P(0, -120), "A great slaughter and thousands captured", "death")

    return st.doc(
        slug="battle-of-zama", kind="battle",
        entity={"name": "Battle of Zama", "wikidata": "Q200056"},
        title="Battle of Zama", date_label="19 October 202 BC", year=-202,
        intro="""In 202 BC, on open ground inland from Carthage, the Second Punic War came to its end. Scipio had
        carried the war to Africa and defeated two armies. Carthage recalled Hannibal from Italy to meet him. Hannibal
        lacked both time and cavalry that could match the Numidians who had come over to Scipio under Masinissa. His
        army was a patchwork of the survivors of three different forces. He marched inland for five days and camped
        about three kilometres from the Roman camp, and battle was now certain. The battle took place on a plain generally placed south of
        Sicca, modern El Kef. The two sides were close to equal in infantry but the Romans had the stronger cavalry. The
        outcome turned on the elephants, the cavalry flanks and Scipio's discipline.""",
        outcome="Decisive Roman victory; Carthage soon accepted a harsh peace, ending the Second Punic War.",
        uncertainty="""The exact site is disputed; the story centres on Wikidata's coordinates, and every terrain item
        is conjectural. The north-south axis, camp positions and distances are reconstructions. Armies' sizes
        vary: the Carthaginian third line is estimated at 12,000 to 20,000, and the second line's strength is
        unknown. Where the 6,000 Numidian infantry stood is unknown (placed conjecturally behind Masinissa).
        Depths, gaps and the length of the cavalry pursuit are schematic. Scholars debate whether Hannibal meant
        the retreat of his second line to bait the Romans.""",
        sources=[{"title": "Battle of Zama — Wikipedia", "url": "https://en.wikipedia.org/wiki/Battle_of_Zama", "kind": "web"}],
        sides=[
            {"id": "r", "name": "Rome", "color": "#b91c1c",
             "polity": {"name": "Roman Republic", "wikidata": "Q17167"},
             "commanders": [{"name": "Scipio Africanus", "wikidata": "Q2253", "role": "Roman commander"}],
             "strength": "c. 29,000-30,000 (6,100 cavalry)", "losses": "At least 1,500 killed"},
            {"id": "c", "name": "Carthage", "color": "#1d4ed8",
             "polity": {"name": "Ancient Carthage", "wikidata": "Q2429397"},
             "commanders": [{"name": "Hannibal", "wikidata": "Q36456", "role": "Carthaginian commander"}],
             "strength": "c. 40,000-50,000 (4,000 cavalry, 80 elephants)",
             "losses": "c. 20,000 killed, 20,000 captured"},
        ],
        units=[
            {"id": "r-hastati", "side": "r", "kind": "heavy_infantry", "label": "Hastati"},
            {"id": "r-principes", "side": "r", "kind": "heavy_infantry", "label": "Principes"},
            {"id": "r-triarii", "side": "r", "kind": "heavy_infantry", "label": "Triarii"},
            {"id": "r-velites", "side": "r", "kind": "light_infantry", "label": "Velites"},
            {"id": "r-masinissa", "side": "r", "kind": "light_cavalry", "label": "Masinissa's Numidians", "strength": "c. 4,000"},
            {"id": "r-laelius", "side": "r", "kind": "cavalry", "label": "Laelius's cavalry", "strength": "c. 1,500"},
            {"id": "r-numid-inf", "side": "r", "kind": "light_infantry", "label": "Numidian foot", "strength": "c. 6,000"},
            {"id": "r-scipio", "side": "r", "kind": "commander", "label": "Scipio"},
            {"id": "c-skirm", "side": "c", "kind": "light_infantry", "label": "Slingers, archers, javelins"},
            {"id": "c-elephants", "side": "c", "kind": "elephants", "label": "War elephants", "strength": "80"},
            {"id": "c-line1", "side": "c", "kind": "heavy_infantry", "label": "First line (Mago's army)"},
            {"id": "c-line2", "side": "c", "kind": "heavy_infantry", "label": "Second line (levies)"},
            {"id": "c-line3", "side": "c", "kind": "heavy_infantry", "label": "Third line (Italy veterans)"},
            {"id": "c-cav-num", "side": "c", "kind": "light_cavalry", "label": "Numidian cavalry"},
            {"id": "c-cav-afr", "side": "c", "kind": "cavalry", "label": "African cavalry"},
            {"id": "c-hannibal", "side": "c", "kind": "commander", "label": "Hannibal"},
        ],
        terrain=[
            {"id": "plain", "kind": "field", "label": "Plain (Draa el Metnan?)", "area": PLAIN, "conjectural": True},
            {"id": "wadi", "kind": "stream", "label": "Dry watercourse", "line": WADI, "conjectural": True},
            {"id": "road", "kind": "road", "label": "Track to Sicca", "line": ROAD, "conjectural": True},
            {"id": "camp-r", "kind": "camp", "label": "Roman camp", "area": CAMP_R, "conjectural": True},
            {"id": "camp-c", "kind": "camp", "label": "Carthaginian camp", "area": CAMP_C, "conjectural": True},
            {"id": "sicca", "kind": "town", "label": "Sicca (El Kef)", "at": P(-2500, 1900), "conjectural": True},
        ],
    )
