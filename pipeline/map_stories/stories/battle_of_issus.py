"""Battle of Issus, 5 November 333 BC — map story builder.

Anchors: ANCHOR sits on the Payas stream (Hammond/Devine identification of the Pinarus) from `places`
(OSM stream line); the gulf lies west, the Amanus foothills east, c. 2.6 km apart.
Orientation: Macedonians stand SOUTH of the river facing north (0); Persians stand NORTH of it facing south (180).
Macedonian right (Alexander, Companions, hypaspists) is EAST by the hills; left (Parmenion, Thessalians) is WEST by the sea.
Persian right (heavy cavalry) is by the sea facing the Macedonian left; Persian left (Cardaces) wraps into the foothills.
Positions inside the lines, the hill detachment and the later manoeuvres are reconstructions.
Sources: Wikipedia "Battle of Issus" (Location, Background, Combatants, Battle, Aftermath).
"""
from pipeline.map_stories.geo import arc, bearing, distance, ellipse, mid, offset, rel
from pipeline.map_stories.layout import Story, behind, deploy_line, facing_off, local_frame, screen, wing

ANCHOR = (36.2025, 36.7525)
P = local_frame(ANCHOR)

# Payas stream (OSM waterway), the Pinarus on the Hammond/Devine reading
PAYAS = [[36.21499, 36.75417], [36.21419, 36.75527], [36.21321, 36.75558], [36.21178, 36.75552], [36.21099, 36.75395],
         [36.20884, 36.7528], [36.20688, 36.75342], [36.20543, 36.7535], [36.20359, 36.75261], [36.20212, 36.75147],
         [36.20014, 36.75128], [36.19777, 36.75176], [36.19634, 36.75268], [36.19357, 36.75282], [36.19178, 36.75422]]


def build() -> dict:
    st = Story()

    st.step("approach", "Darius cuts the road, Alexander turns back", "Early November, 333 BC", """
        Darius brought his army north around the Amanus range and took Issus, which put it astride Alexander's
        supply line while the Macedonians were still south of the Pass of Jonah. On learning this, Alexander
        marched back up the coast in column. Darius, advancing south, got no further than the Pinarus before his
        scouts saw the Macedonians coming, and he drew up on the north bank of the narrow coastal plain, where his
        numbers counted for little.""")
    st.put("p-cav", at=P(-640, 330), facing=180, width=700, depth=90, shape="block")
    st.put("p-greeks", at=P(-60, 330), facing=180, width=620, depth=45, strength_n=10000)
    st.put("p-guard", at=P(-60, 520), facing=180, width=520, depth=45, conjectural=True)
    st.put("p-cardaces", at=P(740, 330), facing=180, width=800, depth=50, conjectural=True)
    st.put("p-darius", at=P(-60, 700), facing=180)
    st.pin("p-darius", "p-guard")
    st.put("a-column", at=P(-250, -1650), facing=0, width=150, depth=1100, shape="column", conjectural=True)
    st.note(P(-300, 250), "Persians hold the north bank", "label")

    st.step("deploy", "Alexander forms line", "Midday", """
        As the plain narrowed, Alexander fed his column into line one body after another. The Macedonian phalanx
        and the hypaspists took the centre and right, the Companion cavalry stood with him on the right wing near
        the foothills, and Parmenion took the left by the sea with the Thessalian and allied horse and orders to
        hold the shore. Craterus commanded the infantry of the left wing. Seeing Persian infantry reaching into
        the hills, Alexander angled his Agrianians and archers to guard his right.""")
    st.hide("a-column")
    st.put("a-thess", at=P(-860, -80), facing=0, width=360, depth=50, strength_n=2400)
    st.put("a-phalanx", at=P(-340, -70), facing=0, width=760, depth=36, strength_n=9000)
    st.put("a-hypaspists", at=P(300, -70), facing=0, width=420, depth=30, strength_n=3000)
    st.put("a-companions", at=P(700, -90), facing=0, width=320, depth=60, strength_n=1800)
    st.put("a-agrianians", at=P(1130, 20), facing=30, width=300, depth=30, strength_n=1000, conjectural=True)
    st.put("a-alexander", at=P(700, -180), facing=0)
    st.pin("a-alexander", "a-companions")
    st.put("a-parmenion", at=P(-860, -170), facing=0)
    st.pin("a-parmenion", "a-thess")
    st.put("p-hill", at=P(1330, 380), facing=225, width=200, depth=40, conjectural=True)

    st.step("persian-cav", "Persian horse crosses against the left", "Early afternoon", """
        Darius's heavy cavalry on the sea flank splashed over the stream and charged Parmenion's wing. The
        Thessalians were heavily outnumbered, and they met the weight of Persian horse by charging and falling
        back, again and again, to buy time rather than to win. Parmenion's task was only to survive until the
        right wing had done its work, the same plan Alexander would use two years later at Gaugamela.""")
    st.put("p-cav", at=P(-740, -20), facing=180, width=700, depth=90, move="charge", state="engaged")
    st.put("a-thess", at=P(-800, -150), facing=0, state="engaged", move="retreat")
    st.note(P(-800, -60), "Thessalians fight a delaying action", "clash")

    st.step("advance", "The Macedonian right goes forward", "Afternoon", """
        On the right Alexander advanced at a walk until the Persian missiles reached his ranks, then ordered his
        men to run the last stretch to the water. Hypaspists and Companions went into the stream together, with
        the Agrianians pressing the skirmishers in the foothills. The centre phalanx, held back by uneven ground
        and a steep bank, was meanwhile advancing more slowly and opening gaps in the line.""")
    st.put("a-companions", at=P(700, -10), move="advance")
    st.put("a-hypaspists", at=P(300, -10), move="advance")
    st.put("a-agrianians", at=P(1130, 150), move="advance", state="engaged")
    st.put("p-hill", state="engaged")
    st.put("a-phalanx", at=P(-380, -50), move="advance")

    st.step("cardaces", "The hypaspists break the Persian left", "Late afternoon", """
        Hypaspists and Companions struck the Persian infantry of the left, which stood on a fortified bank and
        was partly bent back toward the hills. The attack drove a hole through the Cardaces, and the Agrianians
        beat the skirmishers off the right flank so the cavalry could not be taken from the side. At about this
        moment Alexander was able to leave the infantry fight and turn his own men toward the Persian centre.""")
    st.put("a-hypaspists", at=P(300, 140), state="engaged", move="attack")
    st.put("p-cardaces", at=P(780, 240), state="wavering", move="back_water")
    st.put("a-companions", at=P(700, 130), state="engaged", move="attack")
    st.note(P(500, 200), "A gap opens in the Persian left", "clash")

    st.step("centre", "The phalanx is thrown back", "Afternoon", """
        While Alexander was winning on the right, the centre ran into trouble. The phalanx, with its right side
        pulled ahead, had to climb out of the stream against the Greek mercenaries in Darius's pay, who
        counter-charged into its gaps. Arrian says that 120 Macedonians of rank fell here. The phalanx was driven
        back across the river, and for a while the whole centre of the Macedonian army was in danger of coming
        apart, with the Persian cavalry still pressing on its left.""")
    st.put("a-phalanx", at=P(-380, -40), state="wavering", move="retreat")
    st.put("p-greeks", at=P(-200, 40), facing=180, state="engaged", move="attack")
    st.note(P(-300, 0), "120 Macedonian officers fall", "death")

    st.step("charge", "Alexander charges at Darius", "Late afternoon", """
        Seeing Darius's royal cavalry guard and chariot only a short way beyond, Alexander mounted and led the
        Companions at the Persian centre. The Great King's guard stood and fought briefly, and in the melee the
        royal party began to give way. The accounts disagree on how hard Alexander himself was pressed, but all
        make the strike at the centre of the Persian line the turning point of the day.""")
    st.put("a-companions", at=P(440, 420), facing=0, move="charge", state="engaged", conjectural=True)
    st.put("p-guard", at=P(-60, 520), state="engaged")
    st.put("p-cardaces", at=P(1000, 300), state="routed", move="rout")
    st.note(P(150, 480), "Alexander drives at the royal guard", "clash", conjectural=True)

    st.step("flight", "Darius flees", "Late afternoon", """
        Darius, the royal chariot and his household troops turned and fled when the Macedonian horse reached them.
        Alexander now saw that his own centre was struggling, so he did not follow the king at once. He turned
        some of his force left and struck the Greek mercenaries on their exposed flank and rear, while the
        phalanx, steadied by this relief, came forward again.""")
    st.put("p-guard", state="routed", move="rout", at=P(-60, 1150))
    st.put("p-darius", at=P(-60, 1300))
    st.put("a-companions", at=P(100, 340), facing=270, move="flank", state="engaged")
    st.put("a-phalanx", at=P(-380, 0), state="engaged", move="advance")

    st.step("mercenaries", "The Greek mercenaries are cut off", "Dusk", """
        Hit from front and flank at once, the mercenary phalanx broke and gave ground. Without their paymaster
        and with their allies gone, they began to leave the field. Many fell back through the foothills in good
        order, and survivors later escaped to the south or east to serve elsewhere. The Persian cavalry on the
        coast, seeing the centre gone, turned for the north, though some had pressed Parmenion hard until the
        end.""")
    st.put("p-greeks", state="routed", move="rout", at=P(-300, 480))
    st.put("p-cav", state="routed", move="rout", at=P(-900, 700))
    st.put("a-thess", state="ready")
    st.put("p-hill", state="routed")

    st.step("pursuit", "Rout and pursuit", "Nightfall", """
        The whole Persian army broke. Fleeing men crowded the narrow roads, and the Greek horse rode them down
        until the light failed. Ptolemy was reported to say that Alexander and his companions, chasing Darius,
        crossed a ravine on the heaped bodies of the dead. The pursuit did not catch the king, who got away on a
        horse after abandoning his chariot, mantle and bow.""")
    st.put("a-companions", at=P(-100, 1300), facing=0, move="pursuit", state="ready")
    st.put("a-thess", at=P(-700, 700), facing=0, move="pursuit")
    st.put("p-cardaces", at=P(1100, 1100), move="rout")
    st.put("p-greeks", at=P(-300, 900))
    st.put("p-cav", at=P(-900, 1200))

    st.step("aftermath", "Persian camp captured", "Night", """
        Alexander took the royal camp that night. Darius's mother Sisygambis, his wife Stateira and his
        daughters were captured and treated with respect, though the Persian treasure and tent went to the
        victors. It was the first time a Persian army had been defeated with the king present. Alexander turned
        south toward Phoenicia and Egypt to deny the Persian fleet its bases, and Darius took the long road home
        to raise a new army.""")
    st.put("p-darius", at=P(-60, 1900), move="rout")
    st.put("a-companions", at=P(-100, 800), facing=180)
    st.note(P(0, 900), "Royal camp and family captured", "capture")

    return st.doc(slug="battle-of-issus", kind="battle", entity={"name": "Battle of Issus", "wikidata": "Q201526"},
        title="Battle of Issus", date_label="5 November 333 BC", year=-333,
        intro="""
        In November 333 BC Alexander of Macedon and the Persian Great King Darius III met on a coastal strip beside
        the Gulf of Issus, in what is now southern Turkey. Darius had marched round the Amanus mountains by a
        northern route and cut Alexander's lines of supply, and Alexander turned his army back to fight. The
        plain between the sea and the hills was barely 2.6 km wide, so the larger Persian army could not use its
        weight of numbers. Alexander led the right wing in a strike at the Persian centre while Parmenion held the
        left. Darius fled, his army collapsed, and his family fell into Macedonian hands. It was the first
        Persian defeat in a battle where the king himself was present.""",
        outcome="Macedonian victory: Darius fled, the Persian camp and royal family were taken, and southern Asia Minor and the road to Phoenicia lay open.",
        uncertainty="""The site of the Pinarus is disputed: older scholars chose the Deli Cay, but Hammond and Devine argue for the Payas. We follow the Payas. Persian numbers are very uncertain, from about 25,000 (Delbruck) to 600,000 (Arrian). The line-up inside each wing, the hill detachment, the exact timing and direction of Alexander's turn on the mercenaries, and all later positions are reconstructed from Arrian and Curtius and are marked conjectural.""",
        sources=[{"title": "Battle of Issus - Wikipedia", "url": "https://en.wikipedia.org/wiki/Battle_of_Issus", "kind": "web"}],
        sides=[
            {"id": "a", "name": "Macedon and the League of Corinth", "color": "#1d4ed8",
             "polity": {"name": "Macedon", "wikidata": "Q83958"},
             "commanders": [{"name": "Alexander the Great", "wikidata": "Q8409", "role": "king, right wing"},
                            {"name": "Parmenion", "wikidata": "Q296233", "role": "left wing"},
                            {"name": "Craterus", "wikidata": "Q297390", "role": "left infantry"}],
             "strength": "c. 37,000", "losses": "c. 150 killed, 4,500 wounded"},
            {"id": "p", "name": "Achaemenid Empire", "color": "#b91c1c",
             "polity": {"name": "Achaemenid Empire", "wikidata": "Q389688"},
             "commanders": [{"name": "Darius III", "wikidata": "Q102865", "role": "Great King"}],
             "strength": "modern estimates 108,000-158,000", "losses": "c. 20,000-40,000"},
        ],
        units=[
            {"id": "a-thess", "side": "a", "kind": "cavalry", "label": "Thessalian and Greek horse", "strength": "c. 2,400"},
            {"id": "a-phalanx", "side": "a", "kind": "pikemen", "label": "Phalanx (Craterus)", "strength": "c. 9,000"},
            {"id": "a-hypaspists", "side": "a", "kind": "heavy_infantry", "label": "Hypaspists", "strength": "c. 3,000"},
            {"id": "a-companions", "side": "a", "kind": "heavy_cavalry", "label": "Companion cavalry", "strength": "c. 1,800"},
            {"id": "a-agrianians", "side": "a", "kind": "light_infantry", "label": "Agrianians and archers", "strength": "c. 1,000"},
            {"id": "a-column", "side": "a", "kind": "army", "label": "Macedonian army marching"},
            {"id": "a-alexander", "side": "a", "kind": "commander", "label": "Alexander"},
            {"id": "a-parmenion", "side": "a", "kind": "commander", "label": "Parmenion"},
            {"id": "p-cav", "side": "p", "kind": "heavy_cavalry", "label": "Persian heavy cavalry"},
            {"id": "p-greeks", "side": "p", "kind": "heavy_infantry", "label": "Greek mercenaries", "strength": "c. 10,000"},
            {"id": "p-guard", "side": "p", "kind": "heavy_infantry", "label": "Royal guard"},
            {"id": "p-cardaces", "side": "p", "kind": "infantry", "label": "Cardaces and levies"},
            {"id": "p-hill", "side": "p", "kind": "light_infantry", "label": "Hill detachment"},
            {"id": "p-darius", "side": "p", "kind": "commander", "label": "Darius III"},
        ],
        terrain=[
            {"id": "payas", "kind": "river", "label": "Pinarus (Payas)", "line": PAYAS},
            {"id": "bank", "kind": "wall", "label": "Fortified north bank", "conjectural": True,
             "line": [P(-1100, 90), P(-300, 90), P(500, 90), P(1100, 130)]},
            {"id": "foothills", "kind": "hill", "label": "Amanus foothills", "conjectural": True,
             "area": ellipse(P(1550, 200), 450, 700, rotate=0)},
            {"id": "ridge", "kind": "ridge", "label": "Mountain edge", "conjectural": True,
             "line": [P(1250, -900), P(1450, -300), P(1500, 400), P(1400, 1000)]},
            {"id": "road", "kind": "road", "label": "Coast road north to Issus", "conjectural": True,
             "line": [P(-650, -1500), P(-650, -500), P(-600, 500), P(-500, 1500)]},
        ])
