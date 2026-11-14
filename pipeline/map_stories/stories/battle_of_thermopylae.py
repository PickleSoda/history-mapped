"""Battle of Thermopylae, August or September 480 BC — map story builder.

Anchors: Kolonos Hill (OSM peak, 22.53715 38.79577), where the last stand is placed after Marinatos' 1939 finds.
Phocian wall at the middle gate ~500 m west of Kolonos (conjectural). Asopos river from OSM; mountain path conjectural.
Orientation: the Greeks held the pass facing WEST toward Trachis and the Persian camp; the Persians attacked eastward.
Sea (ancient shore at the gates) lay to the north, the cliffs of Mt Kallidromos to the south. The Persian flank
column came over the ridge from the west and dropped down behind the Greeks to the east. Sources: Herodotus and
Diodorus as summarised in Wikipedia's article on the battle (infobox, Topography, Greek army, Battle sections).
"""
from pipeline.map_stories.geo import ellipse, offset
from pipeline.map_stories.layout import Story, local_frame

ANCHOR = (22.53715, 38.79577)
P = local_frame(ANCHOR)

ASOPOS = [[22.495, 38.81241], [22.49008, 38.81381], [22.47315, 38.80642], [22.43459, 38.78498], [22.43591, 38.77535],
          [22.4259, 38.77007], [22.42078, 38.77013]]

WALL_X = -500
ROAD = [P(-2200, 0), P(-1000, 5), P(-500, 0), P(0, -5), P(1500, 0), P(2600, -40)]
PATH = [P(-8000, -1600), P(-5200, -2600), P(-2500, -2500), P(500, -1900), P(1800, -900), P(2400, -200)]


def build() -> dict:
    st = Story()

    # ---- 1 deployment
    st.step("deployment", "The Greeks close the Hot Gates", "Day 0 to 4", """
        Xerxes brought his host down from Thessaly and halted before the narrow coastal pass of Thermopylae.
        King Leonidas of Sparta had marched north with his 300 Spartans and a mixed force of allied Greeks,
        perhaps 7,000 men in all by the modern standard count. He posted them at the middle gate, where the
        Phocians had once built a wall, and where the cliffs of Mt Kallidromos on one side and the Malian Gulf
        on the other left a passage of roughly 100 metres. The Persians camped in the plain to the west and for
        four days did nothing, waiting for the Greeks to give way.""")
    st.put("g-line", at=P(WALL_X + 100, -5), facing=270, width=100, depth=30, strength_n=3000, label="Greek allies")
    st.put("g-spartans", at=P(WALL_X + 40, -28), facing=270, width=36, depth=14, strength_n=300, label="300 Spartans")
    st.put("g-thespians", at=P(WALL_X + 40, 0), facing=270, width=28, depth=18, strength_n=700, label="Thespians", conjectural=True)
    st.put("g-thebans", at=P(WALL_X + 40, 22), facing=270, width=20, depth=14, strength_n=400, label="Thebans", conjectural=True)
    st.put("g-phocians", at=P(-3500, -2600), facing=270, width=200, depth=30, strength_n=1000, label="Phocians on the path", conjectural=True, frame=False)
    st.put("g-leonidas", at=P(WALL_X + 40, -28), facing=270, label="Leonidas")
    st.pin("g-leonidas", "g-spartans")
    st.put("p-camp", at=P(-3800, 100), facing=90, label="Persian camp", frame=False)
    st.put("p-xerxes", at=P(-3000, 60), facing=90, label="Xerxes", frame=False)
    st.put("p-archers", at=P(-2600, -10), facing=90, width=100, depth=40, strength_n=5000, label="5,000 archers", frame=False)

    # ---- 2 archers
    st.step("archers", "Day one: the arrow barrage", "Day 5, morning", """
        On the fifth day Xerxes finally ordered an attack. He opened with 5,000 archers, who shot from beyond
        the reach of the Greek spears. The volleys did little harm: bronze helmets and big wooden shields caught
        most of the arrows, and the defenders stood behind their wall where the pass was narrowest, so few
        of them were exposed at any time. The Persians had to send in men on foot.""")
    st.put("p-archers", at=P(-950, -5), facing=90, move="advance", state="engaged")
    st.fire("p-archers", st.at("g-line"), mlabel="arrows")
    st.note(P(-700, 70), "Arrows glance off shields", "event")

    # ---- 3 Medes
    st.step("medes", "Day one: Medes and Cissians", "Day 5, midday", """
        Xerxes sent 10,000 Medes and Cissians to take the defenders alive. They attacked in waves against the
        Greek front. Their shields were lighter and their spears and swords shorter than those of the hoplites,
        and in the narrow ground they could not use their numbers. Herodotus says the Greeks fought by city
        contingents and rotated men to rest, and that Xerxes leapt up three times from his throne as his
        troops were cut down. Ctesias claims the first wave was slaughtered for the loss of two or three Spartans.""")
    st.put("p-archers", at=P(-1700, -5), move="retreat", state="ready")
    st.put("p-medes", at=P(-640, -5), facing=90, width=100, depth=60, strength_n=10000, label="10,000 Medes, Cissians", state="engaged")
    st.put("g-line", state="engaged")
    st.put("g-spartans", state="engaged")
    st.note(P(-560, 60), "Waves break on the wall", "clash")

    # ---- 4 Immortals
    st.step("immortals", "Day one: the Immortals", "Day 5, afternoon", """
        The same day the king committed his best troops, the 10,000 Immortals. They fared no better than the
        Medes. The Greeks are said to have used a trick, turning as if in flight and then wheeling on the
        pursuers once they had broken their own order. Whatever the details, the Persians could not make the
        weight of their numbers count in a space only one hundred metres wide, and withdrew at dusk.""")
    st.put("p-medes", at=P(-1900, -5), move="retreat", state="routed")
    st.put("p-immortals", at=P(-600, -5), facing=90, width=100, depth=60, strength_n=10000, label="Immortals", state="engaged")
    st.put("g-spartans", at=P(WALL_X + 15, -28), move="feint", conjectural=True)
    st.note(P(-520, 60), "Feigned Spartan retreat", "event")

    # ---- 5 day 2
    st.step("day2", "Day two: assaults again fail", "Day 6", """
        On the second day Xerxes sent the infantry in again, believing the few Greeks must be worn down by
        their wounds. They held as before. Late in the day the king called off the attack and went back to his
        camp in perplexity. The pass was blocked and a frontal fight was costing him heavily, while his fleet
        was far away. Nothing in the sources suggests the Greeks yielded any ground.""")
    st.put("p-immortals", at=P(-1500, -5), move="retreat", state="ready")
    st.put("p-medes", at=P(-700, -5), state="engaged", move="attack", start=P(-1900, -5))
    st.put("g-spartans", at=P(WALL_X + 40, -28))
    st.note(P(-800, 60), "Same result as day one", "label")

    # ---- 6 Ephialtes
    st.step("ephialtes", "Ephialtes shows the mountain path", "Evening of day 6", """
        A local man from Trachis, Ephialtes, came to Xerxes and offered for a reward to guide troops over the
        mountain track that bypassed the pass. It climbed from the Asopos gorge, ran along the ridge of Mt
        Anopaea and came down toward Alpenus in Locris, behind the Greek position. Herodotus sends Hydarnes
        with the Immortals at nightfall, while Diodorus gives him 20,000 men. The route drawn here is
        reconstructed from the account, not surveyed.""")
    st.put("p-medes", at=P(-1900, -5), state="ready", move="retreat")
    st.put("p-immortals", at=P(-1500, -5), state="ready")
    st.put("p-hydarnes", at=P(-8000, -1600), facing=90, width=300, depth=40, strength_n=20000, label="Hydarnes' flanking column", conjectural=True, frame=False)
    st.put("g-line", state="ready")
    st.put("g-spartans", state="ready")
    st.put("p-hydarnes", at=P(-5200, -2600), move="march", conjectural=True, frame=False)
    st.put("p-ephialtes", at=P(-5200, -2500), facing=90, label="Ephialtes (guide)", conjectural=True, frame=False)

    # ---- 7 Phocians
    st.step("phocians", "Dawn: the Phocians are bypassed", "Dawn, day 7", """
        As day broke the Phocians who guarded the track heard the oak leaves rustle and saw armed men coming
        through the trees. They scrambled to their weapons and withdrew to a nearby height, thinking they were
        the target. Hydarnes, who had feared they were Spartans, merely loosed a volley and carried on
        downhill. A runner took word of it to Leonidas, who called a council of war at first light.""")
    st.put("p-hydarnes", at=P(-3500, -2500), move="march", conjectural=True, frame=False)
    st.put("p-ephialtes", at=P(-3500, -2400), move="march", start=P(-5200, -2500), conjectural=True)
    st.put("g-phocians", at=P(-3200, -3000), move="retreat", state="wavering", conjectural=True, frame=False)
    st.fire("p-hydarnes", st.at("g-phocians"), mlabel="volley")
    st.note(P(-3400, -2900), "Phocians fall back", "event", conjectural=True)

    # ---- 8 council
    st.step("council", "Leonidas dismisses most of the army", "Dawn, day 7", """
        Warned that he was surrounded, Leonidas held a council. Some wished to retreat; he himself would not
        leave, and told the allies that they were free to go. Most did, or were ordered away. Retreating over
        the open ground beyond the pass would have exposed them to cavalry, so the rearguard gave the rest a
        chance to get clear. Herodotus is unsure whether they left on orders or of their own accord. The 300
        Spartans stayed, with 700 Thespians under Demophilus and about 400 Thebans.""")
    st.hide("p-ephialtes")
    st.hide("g-phocians")
    st.put("g-line", at=P(WALL_X + 800, -5), move="retreat", facing=90, width=80, depth=30, state="ready", label="Allies leave (c. 3,000)")
    st.put("g-spartans", at=P(WALL_X + 40, -28), state="ready")
    st.note(P(WALL_X + 70, 70), "300 Spartans, Thespians, Thebans stay", "label")

    # ---- 9 sally
    st.step("sally", "The Greeks sally out", "Morning, day 7", """
        Xerxes poured libations at sunrise and waited until the Immortals could be expected to have come
        down the mountain, then ordered his front to advance. Knowing that they were about to be caught from
        behind, the Greeks left their wall and went out into the wider part of the pass to kill as many of the
        enemy as they could. They fought with spears until the shafts broke and then with their short swords.
        Two brothers of Xerxes, Abrocomes and Hyperanthes, fell. Leonidas was killed by arrows, and the Greeks
        won the fight over his body.""")
    st.put("p-light", at=P(-1100, -5), facing=90, width=110, depth=60, strength_n=10000, label="10,000 light inf. and horse", frame=False)
    st.put("p-light", at=P(-700, -5), move="attack", state="engaged", frame=True)
    st.put("g-spartans", at=P(-620, -28), move="attack", state="engaged")
    st.put("g-thespians", at=P(-620, 0), move="attack", state="engaged", conjectural=True)
    st.put("g-thebans", at=P(-620, 22), move="attack", state="engaged", conjectural=True)
    st.put("p-immortals", at=P(-1500, -5), state="ready")
    st.put("p-hydarnes", at=P(1800, -900), facing=270, move="march", state="ready", conjectural=True, frame=False)
    st.note(P(-640, 60), "Leonidas killed; body held", "death")

    # ---- 10 hill
    st.step("hill", "Withdrawal to Kolonos Hill", "Midday, day 7", """
        Hydarnes' column came out of the hills onto the road behind the defenders and the Immortals pressed
        in from the front. The Greeks drew back through the wall onto a mound. The Thebans broke away, held up
        their hands and surrendered, though some were killed first, and Xerxes later had the survivors branded.
        Marinatos' 1939 excavation found masses of Persian arrowheads on Kolonos Hill, which is why the final
        stand is now placed there and not on a lower rise by the wall.""")
    st.put("p-hydarnes", at=P(450, -10), facing=270, width=100, depth=150, state="engaged", move="attack", conjectural=True, frame=True)
    st.put("p-immortals", at=P(-450, -5), move="attack", state="engaged")
    st.put("p-light", at=P(-650, -5), state="engaged")
    st.put("g-spartans", at=P(-60, -20), facing=270, width=30, depth=20, move="retreat", state="engaged")
    st.put("g-thespians", at=P(30, 15), facing=90, width=30, depth=15, move="retreat", state="engaged", conjectural=True)
    st.put("g-thebans", at=P(-220, 30), move="retreat", state="captured", by="b", facing=90, width=30, depth=10, conjectural=True)
    st.note(P(-220, 60), "Thebans surrender", "capture")

    # ---- 11 last stand
    st.step("last-stand", "The last stand", "Afternoon, day 7", """
        Surrounded on the hill, the survivors fought with what they had left. In Herodotus' words, those with
        swords used them and the rest struggled with hands and teeth. Xerxes ordered part of the wall pulled
        down and had the hill encircled, and his archers shot until no Greek was left standing. The Persian
        losses are given by Herodotus as up to 20,000; modern scholars regard that and the Greek figure of
        4,000 dead as too high.""")
    st.put("g-spartans", at=P(-10, -20), state="destroyed", conjectural=True)
    st.put("g-thespians", at=P(15, 15), state="destroyed", conjectural=True)
    st.put("p-immortals", at=P(-200, -5), move="attack", state="engaged")
    st.put("p-hydarnes", at=P(220, -5), move="attack", state="engaged", conjectural=True)
    st.fire("p-immortals", st.at("g-spartans"), mlabel="arrows")
    st.note(P(0, 80), "Kolonos Hill: arrowheads found 1939", "event")

    # ---- 12 aftermath
    st.step("aftermath", "The pass is open", "Evening, day 7", """
        The way to Phocis, Boeotia and Attica now lay open to the Persian army. The defenders had delayed it
        for several days, and the Greek fleet at Artemisium withdrew after hearing the news. The 300 Spartans
        and the Thespians were wiped out, while some 3,000 men of the other contingents had got away to fight
        again. Xerxes advanced south; the Greeks would answer at Salamis and Plataea.""")
    st.put("p-immortals", at=P(500, -5), move="march", state="ready", facing=90)
    st.put("p-hydarnes", at=P(900, -5), move="march", state="ready", facing=90, conjectural=True)
    st.put("p-light", at=P(300, -5), move="march", state="ready", facing=90)
    st.hide("g-line")
    st.side_move("b", "march", [P(500, 0), P(2600, -40)], label="Road to Phocis and Boeotia")

    return st.doc(
        slug="battle-of-thermopylae", kind="battle",
        entity={"name": "Battle of Thermopylae", "wikidata": "Q131969"},
        title="Battle of Thermopylae", date_label="August or September 480 BC", year=-480,
        intro=("In the summer of 480 BC Xerxes I of Persia led a vast army into Greece to punish Athens and "
               "Sparta and to add the mainland to his empire. The one land route south from Thessaly ran through "
               "Thermopylae, the Hot Gates, a coastal strip where the cliffs of Mt Kallidromos came close to the "
               "Malian Gulf. A small Greek force under the Spartan king Leonidas I blocked it for three days "
               "against Persian armies many times its size. The first two days were frontal fights that the "
               "defenders won. On the third a local man led a Persian column over the mountains, forcing "
               "Leonidas to send most of his army away and make a last stand with the Spartans, Thespians and "
               "Thebans. This map replays the fight step by step."),
        outcome="Persian victory: the pass was forced and the way into central Greece opened.",
        uncertainty=("Ancient sources give wildly inflated numbers, and modern estimates of Xerxes' army run "
                     "from 40,000 to 300,000. Exact dates vary: 21-23 July, 20 August or 8-10 September. The "
                     "unit sizes follow the standard modern count of about 7,000 Greeks. The position of the "
                     "Phocian wall, the unit placements, the Persian camp, Hydarnes' route over the mountain and "
                     "the order of the final retreat are reconstructed and marked conjectural. The shoreline "
                     "has moved several kilometres; the base map shows the modern coast."),
        sources=[{"title": "Battle of Thermopylae - Wikipedia", "url": "https://en.wikipedia.org/wiki/Battle_of_Thermopylae", "kind": "web"}],
        sides=[
            {"id": "a", "name": "Allied Greek city-states", "color": "#1d4ed8",
             "polity": {"name": "Sparta", "wikidata": "Q5690"},
             "commanders": [{"name": "Leonidas I", "wikidata": "Q44228", "role": "King of Sparta"},
                            {"name": "Demophilus of Thespiae", "wikidata": "Q928788", "role": "Thespian general"}],
             "strength": "c. 7,000", "losses": "up to c. 2,000 (Herodotus says 4,000)"},
            {"id": "b", "name": "Achaemenid Empire", "color": "#b91c1c",
             "polity": {"name": "Achaemenid Empire", "wikidata": "Q389688"},
             "commanders": [{"name": "Xerxes I", "wikidata": "Q129165", "role": "Great King"},
                            {"name": "Hydarnes", "wikidata": "Q19568922", "role": "commander of the flank column"}],
             "strength": "40,000 to 300,000 (modern estimates)", "losses": "c. 20,000 (Herodotus)"},
        ],
        units=[
            {"id": "g-line", "side": "a", "kind": "heavy_infantry", "label": "Greek allies", "strength": "c. 3,000"},
            {"id": "g-spartans", "side": "a", "kind": "heavy_infantry", "label": "300 Spartans", "strength": "300"},
            {"id": "g-thespians", "side": "a", "kind": "heavy_infantry", "label": "Thespians", "strength": "700"},
            {"id": "g-thebans", "side": "a", "kind": "heavy_infantry", "label": "Thebans", "strength": "400"},
            {"id": "g-phocians", "side": "a", "kind": "light_infantry", "label": "Phocians on the path", "strength": "1,000"},
            {"id": "g-leonidas", "side": "a", "kind": "commander", "label": "Leonidas"},
            {"id": "p-camp", "side": "b", "kind": "camp", "label": "Persian camp"},
            {"id": "p-xerxes", "side": "b", "kind": "commander", "label": "Xerxes"},
            {"id": "p-archers", "side": "b", "kind": "archers", "label": "5,000 archers", "strength": "5,000"},
            {"id": "p-medes", "side": "b", "kind": "infantry", "label": "Medes and Cissians", "strength": "10,000"},
            {"id": "p-immortals", "side": "b", "kind": "infantry", "label": "Immortals", "strength": "10,000"},
            {"id": "p-hydarnes", "side": "b", "kind": "infantry", "label": "Hydarnes' column", "strength": "up to 20,000"},
            {"id": "p-ephialtes", "side": "b", "kind": "commander", "label": "Ephialtes"},
            {"id": "p-light", "side": "b", "kind": "light_infantry", "label": "Light infantry and horse", "strength": "10,000"},
        ],
        terrain=[
            {"id": "road", "kind": "road", "label": "Coastal road through the pass", "line": ROAD, "conjectural": True},
            {"id": "wall", "kind": "wall", "label": "Phocian wall", "line": [P(WALL_X, -70), P(WALL_X, 45)], "conjectural": True},
            {"id": "cliffs", "kind": "ridge", "label": "Mt Kallidromos cliffs", "line": [P(-2200, -90), P(-1000, -75), P(0, -85), P(1500, -80), P(2600, -110)], "conjectural": True},
            {"id": "marsh", "kind": "marsh", "label": "Hot spring marsh", "area": ellipse(P(WALL_X - 120, 20), 180, 35), "conjectural": True},
            {"id": "kolonos", "kind": "hill", "label": "Kolonos Hill", "area": ellipse(P(0, 0), 140, 55), "conjectural": True},
            {"id": "path", "kind": "road", "label": "Anopaea mountain path", "line": PATH, "conjectural": True},
            {"id": "asopos", "kind": "river", "label": "Asopos gorge", "line": ASOPOS},
        ],
    )
