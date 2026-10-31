"""Battle of Navarino, 20 October 1827 — map story builder.

Anchors: battle coordinates (P625) for the middle of the bay; Pylos/Neokastro (21.6964, 36.9139),
the Sphacteria outline, Sykia strait and Palaiokastro from `places` (OSM). Exact ship positions and the
mainland shore are a mainstream-diagram reconstruction (conjectural). Sources: Wikipedia (Preliminary
moves, Strategies for battle, Engagement); James, Naval History (1837).

Orientation: the bay lies north of its entrance. Sphacteria is a long islet on the WEST side running
north-south; the wide southern entrance (about 1,500 m, 1,000 m usable) lies between the islet's south
tip and Neokastro/Pylos on the EAST side; the northern Sykia channel is shallow (about 100 m wide) and
unusable by big ships. The Ottoman-Egyptian horseshoe is anchored in the bay with its centre in the
north (about y=-700 m from the anchor) and its two arms pointing SOUTH at the entrance: the "left"
(Egyptian) arm on the east leans on Neokastro fort, the "right" arm on the west on the Sphacteria
battery. The Allies sail in from the south heading NORTH: British in the middle against the Ottoman
centre, French on the east (Egyptians), Russians on the west (Ottoman right). SW wind blew up the entrance.
"""
from pipeline.map_stories.geo import ellipse, local, rel
from pipeline.map_stories.layout import Story, facing_off, local_frame

ANCHOR = (21.68778, 36.93583)
P = local_frame(ANCHOR)

# Sfaktiria (OSM place=island)
SPHACTERIA = [[21.65365, 36.94772], [21.65918, 36.94097], [21.65953, 36.93875], [21.65875, 36.9386], [21.65958, 36.93719], [21.6583, 36.93648], [21.6606, 36.93536], [21.66126, 36.93421], [21.66021, 36.93366], [21.66227, 36.93187], [21.66168, 36.93074], [21.66313, 36.9302], [21.66472, 36.92764], [21.66417, 36.92647], [21.66571, 36.92325], [21.66316, 36.92112], [21.66486, 36.91589], [21.66668, 36.91293], [21.66813, 36.91237], [21.66847, 36.9105], [21.66961, 36.91031], [21.66982, 36.90941], [21.67168, 36.90958], [21.67251, 36.91145], [21.6728, 36.91046], [21.67357, 36.91156], [21.67421, 36.9111], [21.67406, 36.91283], [21.67554, 36.91414], [21.67435, 36.91889], [21.6748, 36.92118], [21.66669, 36.93586], [21.6639, 36.9432], [21.66353, 36.94834], [21.66068, 36.95011], [21.65792, 36.94886], [21.65476, 36.94917], [21.65365, 36.94772]]

# mainland shore of the bay from Pylos north to the Divari beach: hand-drawn (conjectural)
EAST_SHORE = [P(770, -2450), P(1250, -1900), P(1600, -900), P(1650, 300), P(1350, 1400), P(600, 2150), P(0, 2300)]

# open water of the bay plus the sea outside the southern entrance (bay shore conjectural)
_EAST = [list(P(*local(tuple(pt), ANCHOR))) for pt in SPHACTERIA[20:34]]
SEA = (_EAST + [list(P(-1500, 2300)), list(P(0, 2300))] + [list(pt) for pt in reversed(EAST_SHORE[:-1])]
       + [list(P(1100, -3200)), list(P(1300, -7200)), list(P(-3600, -7200)), list(P(-3600, -3000))])

CAM_WIDE = {"center": list(P(-300, -2400)), "zoom": 12.7}
CAM_LATE = {"center": list(P(-250, -1500)), "zoom": 13.7}
CAM_BAY = {"center": list(P(-300, -1500)), "zoom": 13.1}
CAM_ENTRY = {"center": list(P(-250, -3100)), "zoom": 13.7}
CAM_FIRE = {"center": list(P(400, -2350)), "zoom": 14.3}
CAM_FRENCH = {"center": list(P(550, -1900)), "zoom": 14.2}
CAM_CENTRE = {"center": list(P(-250, -1100)), "zoom": 14.0}
CAM_RUSS = {"center": list(P(-700, -1700)), "zoom": 14.0}


def build() -> dict:
    st = Story()

    # ---- Step 1: blockade
    st.step("blockade", "Blockade off the bay", "12 September to 12 October",
            """Navarino Bay, about five kilometres long and sheltered by the islet of Sphacteria, was the Ottoman
            navy's main base in the Peloponnese. Ibrahim Pasha's fleet, which left Alexandria on 5 August and
            joined other Ottoman ships there on 8 September, lay at anchor inside. Codrington arrived off the
            entrance on 12 September, talked with Ibrahim on 25 September and then withdrew to Zante, leaving a
            frigate to watch. Twice in early October he turned Ibrahim's sorties toward Patras back to port.""",
            camera=CAM_WIDE)
    st.put("ot-centre", at=P(-100, -700), facing=180, width=700, depth=60, conjectural=True)
    st.put("ot-left", at=P(900, -1250), facing=235, width=700, depth=60, conjectural=True)
    st.put("ot-right", at=P(-850, -1250), facing=135, width=700, depth=60, conjectural=True)
    st.put("ot-second", at=P(-100, -300), facing=180, width=1500, depth=60, conjectural=True)
    st.put("ot-third", at=P(-100, 80), facing=180, width=1700, depth=60, conjectural=True)
    st.put("ot-fire", at=P(550, -2050), facing=200, width=350, depth=50, conjectural=True)
    st.put("ot-fort", at=P(930, -2430), facing=225, width=140, depth=90)
    st.put("ot-batt", at=P(-1650, -2600), facing=135, width=140, depth=90, conjectural=True)
    st.put("br-line", at=P(-300, -5200), facing=0, width=90, depth=260)
    st.put("br-frig", at=P(-420, -5000), facing=0, width=70, depth=200)
    st.put("br-small", at=P(-150, -5000), facing=0, width=70, depth=200)
    st.pin("codrington", "br-line")

    # ---- Step 2: the Allied squadrons gather
    st.step("gathering", "The three squadrons meet", "13 to 18 October",
            """On 13 October the French squadron under Rigny and the Russian squadron under Van Heiden joined
            Codrington off Navarino. Behind the bay Ibrahim's troops were burning villages and fields, and a British
            landing party found Messinia close to famine. After futile attempts to reach Ibrahim, the three admirals
            met on 18 October and decided that a winter blockade was impracticable and that the population had to
            be protected. They resolved to anchor their ships face to face with the Ottoman fleet.""",
            camera=CAM_WIDE)
    st.put("fr-sirene", at=P(120, -5350), facing=0, width=60, depth=100)
    st.put("fr-line", at=P(150, -5000), facing=0, width=80, depth=200)
    st.put("fr-breslaw", at=P(180, -4800), facing=0, width=60, depth=100)
    st.put("fr-small", at=P(300, -5000), facing=0, width=60, depth=160)
    st.put("ru-line", at=P(-800, -5400), facing=0, width=100, depth=300)
    st.put("ru-frig", at=P(-950, -5100), facing=0, width=80, depth=200)
    st.pin("rigny", "fr-sirene")
    st.pin("heiden", "ru-line")
    st.note(P(-300, -4500), "Council of 18 Oct decides to enter", "event")

    # ---- Step 3: off the entrance
    st.step("prepare", "Off the entrance", "1:30 p.m., 20 October",
            """Inside, the Ottoman-Egyptian fleet stood in a horseshoe plan devised by the French officer
            Letellier: three lines from Navarino fort round to the Sphacteria battery, ships of the line and large
            frigates in front, corvettes and brigs behind to fire through the gaps, fireships on the ends. Outside,
            Codrington signalled to prepare for action. Gun ports stayed half open and captains were ordered to fire
            only if attacked. The wind blew from the south-west, straight up the entrance.""",
            camera=CAM_WIDE)
    st.put("br-line", at=P(-300, -4300), move="sail")
    st.put("br-frig", at=P(-430, -4150), move="sail")
    st.put("br-small", at=P(-150, -4100), move="sail")
    st.put("fr-sirene", at=P(130, -4450), move="sail")
    st.put("fr-line", at=P(170, -4250), move="sail")
    st.put("fr-breslaw", at=P(190, -4100), move="sail")
    st.put("fr-small", at=P(330, -4200), move="sail")
    st.put("ru-line", at=P(-800, -4500), move="sail")
    st.put("ru-frig", at=P(-950, -4300), move="sail")
    st.note(P(-300, -3800), "Signal: prepare for action", "event")

    # ---- Step 4: entry
    st.step("entry", "The Allies sail in", "About 2 p.m.",
            """Codrington leads in Asia, the British ships followed by the French along the south-east side, closest
            to Navarino, and the Russians to port, abreast of the French but slightly behind. The shore batteries
            and the Ottoman corvettes at the mouth make no attempt to stop them through the southern channel, which
            was 1,500 m wide but only about 1,000 m usable because of rocks. A launch brings Ibrahim's protest. Codrington
            replies that he has come to give orders, not to receive them.""",
            camera=CAM_ENTRY)
    st.put("br-line", at=P(-300, -3300), move="sail")
    st.put("br-frig", at=P(-430, -3100), move="sail")
    st.put("br-small", at=P(-150, -3450), move="sail")
    st.put("fr-sirene", at=P(60, -3550), move="sail")
    st.put("fr-line", at=P(150, -3250), move="sail")
    st.put("fr-breslaw", at=P(180, -3450), move="sail")
    st.put("fr-small", at=P(380, -3350), move="sail")
    st.put("ru-line", at=P(-850, -3600), move="sail")
    st.put("ru-frig", at=P(-1000, -3750), move="sail")
    st.note(P(-300, -2950), "Entrance passed unopposed", "event")

    # ---- Step 5: anchoring
    st.step("anchoring", "Anchoring in the crescent", "About 2:15 p.m.",
            """By a quarter past two the three British ships of the line had dropped anchor in their allotted places
            in the middle of the Ottoman line, and a band played on Asia's deck to show peaceful intent. As they
            did so, trumpets sounded action stations along the Ottoman lines. Behind the leaders the French were
            still sailing toward the Egyptian end of the horseshoe and the Russians, who were to anchor last, were
            still some way short of their berths on the western wing.""",
            camera=CAM_WIDE)
    ot_c = st.pl("ot-centre")
    st.put("br-line", facing_off(ot_c, depth=50, gap=120, width=420, facing=0), move="advance")
    st.put("br-frig", at=P(-640, -1500), facing=0, width=170, depth=60, move="advance")
    st.put("fr-sirene", at=P(420, -2750), move="sail")
    st.put("fr-line", at=P(480, -2450), move="sail")
    st.put("fr-breslaw", at=P(-80, -2800), move="sail")
    st.put("fr-small", at=P(650, -2900), move="sail")
    st.put("ru-line", at=P(-850, -2700), move="sail")
    st.put("ru-frig", at=P(-700, -3050), move="sail")
    st.put("br-small", at=P(250, -2900), move="sail")

    # ---- Step 6: fireship, first shots
    st.step("fireship", "The fireship and the first shots", "About 2:20 p.m.",
            """At the mouth Captain Fellowes of Dartmouth, with two brigs and four schooners, was watching the
            corvettes and fireships on the Ottoman left. He saw a fireship being readied and sent a boat to make the
            crew desist. The Ottomans fired on the boat and lit the fireship. A cutter sent to tow it away was also
            fired on, and Fellowes had his men cover it with muskets. Sirene, entering at the tail of the line,
            joined in and an Ottoman corvette hit her with its guns.""",
            camera=CAM_FIRE)
    st.put("br-small", at=P(250, -2450), facing=0, width=180, depth=50, move="advance", state="engaged")
    st.put("ot-fire", state="engaged")
    st.put("fr-sirene", at=P(380, -2600), move="advance", state="engaged")
    st.put("ot-fort", state="engaged")
    st.note(P(500, -2250), "Fireship lit; first shots", "clash")
    st.note(P(150, -2650), "Fellowes' boat fired on", "event", conjectural=True)

    # ---- Step 7: French sector
    ot_l = st.pl("ot-left")
    st.step("french", "The French on the Egyptian wing", "About 2:30 p.m.",
            """The chain reaction ran along the line within minutes. Scipion, behind Rigny's Sirene, was hit by
            Egyptian frigates on both sides, by the fort and by a fireship that jammed under her bowsprit and set
            her fore sails alight. Her crew went on firing while Trident took the fireship in tow with help from
            Dartmouth. Sirene fought a long duel with the 64-gun Ihsania until the Ottoman frigate blew up, then
            with Trident and Scipion silenced the fort.""",
            camera=CAM_FRENCH)
    st.put("fr-sirene", at=rel(ot_l["at"], 235, ahead=150, right=-170), facing=55, width=110, depth=60, move="advance", state="engaged")
    st.put("fr-line", at=rel(ot_l["at"], 235, ahead=150, right=130), facing=55, width=230, depth=60, move="advance", state="engaged")
    st.put("fr-small", at=P(650, -2350), facing=0, width=170, depth=60, move="advance")
    st.put("ot-left", state="engaged")
    st.put("ot-fire", state="burning")
    st.note(rel(ot_l["at"], 235, ahead=80), "Ihsania blows up", "death", conjectural=True)
    st.note(P(780, -2150), "Scipion nearly lost to fireship", "event")

    # ---- Step 8: centre
    st.step("centre", "Asia in the centre", "About 3 p.m.",
            """Codrington's Asia lay between the Capitan Bey's flagship Fahti Bahri and Moharram Bey's frigate
            Guerriere. Moharram sent word that he would not attack, so Asia pounded the poorly manned Fahti Bahri.
            When Codrington's Greek interpreter was shot dead boarding Guerriere, she opened fire and was soon a
            burning wreck under the broadsides of Asia and Azov. Albion was pressed by all three Ottoman ships of
            the line until Breslaw left the French and came to her help.""",
            camera=CAM_CENTRE)
    st.put("fr-breslaw", at=P(-380, -1050), facing=0, width=110, depth=60, move="advance", state="engaged", conjectural=True)
    st.put("br-line", state="engaged")
    st.put("ot-centre", state="engaged")
    st.put("ot-second", state="engaged")
    st.note(P(-100, -1000), "Guerriere set ablaze", "death", conjectural=True)

    # ---- Step 9: Russians
    st.step("russians", "The Russians on the exposed wing", "About 3:30 p.m.",
            """The Russians under Van Heiden anchored last, on the right end of the Ottoman crescent, the most
            exposed position. Azov sank or disabled three large frigates and a corvette but took 153 hits, several
            below the waterline. The British frigates Armide and Talbot at first faced the Ottoman right-wing
            frigates and the Sphacteria battery alone, since their other two frigates were away, until the Russian
            frigates came up and saved them.""",
            camera=CAM_RUSS)
    ot_r = st.pl("ot-right")
    st.put("ru-line", facing_off(ot_r, depth=60, gap=120, width=330, facing=315), move="advance", state="engaged")
    st.put("ru-frig", at=rel(ot_r["at"], 135, ahead=150, right=-200), facing=315, width=170, depth=60, move="advance", state="engaged")
    st.put("br-frig", state="engaged")
    st.put("ot-right", state="engaged")
    st.put("ot-batt", state="engaged")
    st.put("ot-third", state="engaged")

    # ---- Step 10: first line broken
    st.step("first-line", "The first line is broken", "About 4 p.m.",
            """By around four o'clock all three Ottoman ships of the line and most of the large frigates of the
            front line were finished, and the fort and the Sphacteria battery were silent. The small British and
            French vessels under Dartmouth had kept the fireships away: apart from the attack on Scipion not one
            struck a target. The smaller craft of the second and third lines now lay open to Allied ships of the
            line, all of which were still fighting.""",
            camera=CAM_LATE)
    st.put("ot-centre", state="destroyed")
    st.put("ot-left", state="burning")
    st.put("ot-right", state="burning")
    st.put("ot-fort", state="destroyed")
    st.put("ot-batt", state="destroyed")
    st.put("ot-fire", state="destroyed")
    st.put("br-small", state="ready")
    st.put("fr-small", state="ready")
    st.note(P(-100, -700), "Tahir's Ghiuh Rewan destroyed", "death")

    # ---- Step 11: destruction
    st.step("destruction", "Destruction of the rear lines", "4 to 6 p.m.",
            """Codrington twice tried to order a ceasefire, but his signals vanished in the smoke or were ignored.
            Within two hours virtually the whole Ottoman fleet was destroyed, despite the bravery of its crews,
            which Codrington himself praised. Many dismasted hulks that could have been repaired were fired or
            blown up by their own crews to keep them from Allied hands, and men were trapped in the burning ships.
            Some had been shackled to their posts. Three quarters of the fleet was sunk.""",
            camera=CAM_LATE)
    st.put("ot-second", state="burning")
    st.hide("br-small")
    st.hide("fr-small")
    st.hide("codrington")
    st.hide("rigny")
    st.hide("heiden")
    st.put("ot-third", state="sunk")
    st.put("ot-centre", state="sunk")
    st.put("ot-left", state="sunk")
    st.put("ot-right", state="sunk")
    st.note(P(-100, -100), "Ceasefire signals lost in smoke", "event")

    # ---- Step 12: aftermath
    st.step("aftermath", "A shattered fleet", "Dusk, 20 October",
            """When the guns fell silent at dusk only eight of the 78 Ottoman and Egyptian vessels were seaworthy.
            Codrington reported 181 Allied dead and 480 wounded; Letellier gave about 3,000 Ottoman dead and 1,109
            wounded, though Codrington thought the proportion might be reversed. Azov, Gangut and Iezekiil were
            disabled, the three British ships of the line had to go home for repair, and no Allied ship was sunk.""",
            camera=CAM_LATE)
    st.put("ot-second", state="destroyed")
    st.put("ot-third", state="destroyed")
    st.put("br-line", state="ready")
    st.put("fr-sirene", state="ready")
    st.put("fr-line", state="ready")
    st.put("fr-breslaw", state="ready")
    st.put("br-frig", state="ready")
    st.put("ru-line", state="ready")
    st.put("ru-frig", state="ready")

    return st.doc(
        slug="battle-of-navarino", kind="naval_battle", schema=3,
        entity={"name": "Battle of Navarino", "wikidata": "Q238440"},
        title="Battle of Navarino", date_label="20 October 1827", year=1827,
        intro="""On 20 October 1827 a combined British, French and Russian fleet sailed into Navarino Bay on the
        south-west coast of the Peloponnese, where an Ottoman-Egyptian fleet lay at anchor. The Allies meant to
        press an armistice on the Ottomans during the Greek War of Independence and had decided, after weeks of
        blockade, that the only practical way was a show of force inside the harbour. Shots exchanged at the
        harbour mouth grew into a general engagement fought mostly at point-blank range between anchored ships.
        In about four hours the Ottoman fleet was wrecked, at small cost to the Allies.""",
        outcome="Decisive Allied victory: most of the Ottoman-Egyptian fleet was destroyed; Allied losses were 181 killed and 480 wounded.",
        uncertainty="""Positions of individual ships, the exact curve of the Ottoman horseshoe and the Allied
        approach lanes are reconstructed from the general description (conjectural). The sea and mainland coast are
        left to the base map; only Sphacteria is outlined. Who fired first is disputed,
        and the Allies blame the Ottomans. Ottoman casualty figures, about 3,000 killed and 1,109 wounded, come from
        Letellier through Codrington, who thought the proportion might be reversed.""",
        sources=[{"title": "Battle of Navarino — Wikipedia", "url": "https://en.wikipedia.org/wiki/Battle_of_Navarino", "kind": "web"}],
        sides=[
            {"id": "allied", "name": "Allied squadrons", "color": "#1d4ed8",
             "polity": {"name": "British Empire", "wikidata": "Q8680"},
             "contingents": [
                 {"id": "british", "name": "British Empire", "wikidata": "Q8680", "color": "#1d4ed8"},
                 {"id": "french", "name": "Bourbon Restoration in France", "wikidata": "Q207162", "color": "#38bdf8"},
                 {"id": "russian", "name": "Russian Empire", "wikidata": "Q34266", "color": "#0f766e"}],
             "commanders": [{"name": "Edward Codrington", "wikidata": "Q958853", "role": "British commander, Asia"},
                            {"name": "Henri de Rigny", "wikidata": "Q2634483", "role": "French commander, Sirene"},
                            {"name": "Lodewijk van Heiden", "wikidata": "Q928539", "role": "Russian commander"}],
             "strength": "10 ships of the line, 10 frigates and smaller craft; 1,252 guns, about 8,000 men",
             "losses": "181 killed, 480 wounded"},
            {"id": "ottoman", "name": "Ottoman-Egyptian fleet", "color": "#b91c1c",
             "polity": {"name": "Ottoman Empire", "wikidata": "Q12560"},
             "commanders": [{"name": "Tahir Pasha", "role": "Ottoman admiral"},
                            {"name": "Moharram Bey", "role": "Egyptian squadron"}],
             "strength": "3 ships of the line, 17 frigates and many smaller vessels; 2,158 guns, about 20,000 men",
             "losses": "About 4,000 killed or wounded, 55 ships lost"},
        ],
        units=[
            {"id": "br-line", "side": "allied", "contingent": "british", "kind": "warship", "label": "British line ships", "strength": "3 ships"},
            {"id": "br-frig", "side": "allied", "contingent": "british", "kind": "warship", "label": "Armide, Talbot", "strength": "2 frigates"},
            {"id": "br-small", "side": "allied", "contingent": "british", "kind": "warship", "label": "Dartmouth, brigs", "strength": "frigate, 2 brigs, 4 schooners"},
            {"id": "fr-sirene", "side": "allied", "contingent": "french", "kind": "warship", "label": "Sirene (Rigny)", "strength": "frigate"},
            {"id": "fr-line", "side": "allied", "contingent": "french", "kind": "warship", "label": "Scipion, Trident", "strength": "2 ships"},
            {"id": "fr-breslaw", "side": "allied", "contingent": "french", "kind": "warship", "label": "Breslaw", "strength": "84 guns"},
            {"id": "fr-small", "side": "allied", "contingent": "french", "kind": "warship", "label": "French schooners", "strength": "Alcyone, Daphne"},
            {"id": "ru-line", "side": "allied", "contingent": "russian", "kind": "warship", "label": "Russian line ships", "strength": "Azov, Gangut, Iezekiil"},
            {"id": "ru-frig", "side": "allied", "contingent": "russian", "kind": "warship", "label": "Russian frigates"},
            {"id": "codrington", "side": "allied", "contingent": "british", "kind": "commander", "label": "Codrington"},
            {"id": "rigny", "side": "allied", "contingent": "french", "kind": "commander", "label": "Rigny"},
            {"id": "heiden", "side": "allied", "contingent": "russian", "kind": "commander", "label": "Van Heiden"},
            {"id": "ot-centre", "side": "ottoman", "kind": "warship", "label": "Ottoman front line", "strength": "3 ships of the line"},
            {"id": "ot-left", "side": "ottoman", "kind": "warship", "label": "Egyptian wing"},
            {"id": "ot-right", "side": "ottoman", "kind": "warship", "label": "Ottoman right wing"},
            {"id": "ot-second", "side": "ottoman", "kind": "warship", "label": "Second line"},
            {"id": "ot-third", "side": "ottoman", "kind": "warship", "label": "Third line"},
            {"id": "ot-fire", "side": "ottoman", "kind": "warship", "label": "Fireships", "strength": "5-6 fireships"},
            {"id": "ot-fort", "side": "ottoman", "kind": "artillery", "label": "Navarino fort"},
            {"id": "ot-batt", "side": "ottoman", "kind": "artillery", "label": "Sphacteria battery"},
        ],
        terrain=[
            {"id": "sphacteria", "kind": "island", "label": "Sphacteria", "area": SPHACTERIA},
            {"id": "pylos", "kind": "town", "label": "Pylos", "at": P(770, -2250)},
            {"id": "neokastro", "kind": "fortification", "label": "Neokastro", "area": ellipse(P(766, -2437), 170, 130)},
            {"id": "south-entrance", "kind": "label", "label": "Southern entrance", "at": P(-420, -3050)},
            {"id": "sykia", "kind": "label", "label": "Sykia channel (shallow)", "at": P(-2556, 1591)},
            {"id": "paliokastro", "kind": "building", "label": "Old Navarino castle", "at": P(-2729, 2556)},
            {"id": "bay", "kind": "label", "label": "Navarino Bay", "at": P(400, 800)},
        ],
    )
