"""Battle of the Teutoburg Forest, 8-11 September 9 AD — map story builder.

Anchors: Kalkriese pass at the Wikidata P625 point (8.12583, 52.4075); Kalkrieser Berg
(8.1125, 52.3978) and the Wiehengebirge outline from `places --geometry ridge`.
Orientation: the Romans march WEST (facing 270) along an east-west sandy strip; the hill, the
Germanic turf wall and the woods lie on their LEFT (south); the Great Bog on their right (north).
The Germans stand behind the wall facing north toward the road. Wall course, bog outline, the
road line and all march positions east of the pass are reconstructions (conjectural).
Sources: Wikipedia (Battle, Lead-up, Site sections); Velleius Paterculus, Cassius Dio via those.
"""
from pipeline.map_stories.geo import ellipse, offset
from pipeline.map_stories.layout import Story, local_frame, ent

ANCHOR = (8.12583, 52.4075)
P = local_frame(ANCHOR)

WIEHEN = [[8.27806, 52.33569], [8.25512, 52.34306], [8.23677, 52.35143], [8.22381, 52.3533], [8.20622, 52.3595],
          [8.19434, 52.36866], [8.17941, 52.3723], [8.16343, 52.37147], [8.15289, 52.37451], [8.15984, 52.38399],
          [8.15526, 52.39254], [8.13999, 52.40066], [8.1284, 52.4046], [8.11214, 52.40526], [8.09803, 52.40225],
          [8.0803, 52.39673], [8.07179, 52.39185]]
ROAD = [P(6000, 0), P(3000, 0), P(1200, 0), P(0, 0), P(-1200, 0), P(-2200, 0)]
WALL = [P(1500, -60), P(1100, -40), P(700, -70), P(300, -45), P(-100, -75), P(-500, -50), P(-900, -80), P(-1200, -55)]
BOG = ellipse(P(-200, 900), 3200, 800)
FOREST = ellipse(P(1500, -1300), 3800, 900)
KALKRIESE = P(-1990, -210)


def build() -> dict:
    st = Story()

    st.step("muster", "Payday and a plan", "7 September",
            """On the morning of 7 September the army of Publius Quinctilius Varus mustered near its summer
            quarters west of the Weser, and the year's third pay was handed out. Word went round that
            plunder would be allowed on the coming expedition. Arminius, trusted by Varus, had urged a short
            cut through Angrivarian land to put down a revolt that he had himself invented. That evening he
            left the camp, saying he would gather his Cherusci and rejoin in a few days. He rode north to
            raise the Angrivarii and Bructeri. A few Cherusci stayed with the Romans as guides and spies.""")
    st.put("rom-leg", at=P(9500, 600), facing=270, width=60, depth=1800, shape="column", state="ready",
           strength_n=15000)
    st.put("rom-aux", at=P(11000, 600), facing=270, width=50, depth=900, shape="column", strength_n=4500)
    st.put("rom-baggage", at=P(8000, 600), facing=270, width=60, depth=1300, shape="column")
    st.put("varus", at=P(10400, 640), facing=270)
    st.put("arminius", at=P(9200, 700), facing=270)
    st.put("ger-angri", at=P(-900, -200), facing=0, width=900, depth=100, strength_n=5000, frame=False)
    st.put("ger-bructeri", at=P(1500, 3500), facing=180, width=500, depth=80, strength_n=8000, frame=False)
    st.put("ger-cherusci", at=P(3000, 3200), facing=180, width=500, depth=80, strength_n=8000, frame=False)
    st.note(P(10000, 1100), "Muster and pay parade", "label")

    st.step("arminius-leaves", "Arminius slips away", "Evening, 7 September",
            """With his Cherusci horsemen gone, the Roman column lost about a quarter of its strength and most of
            its scouting. Arminius rode north to rally the Angrivarii and Bructeri, who were already
            watching the road. Varus set off the next day into thick forest, with the paths narrow and the
            column losing its shape mile after mile. The treacherous guides kept the Germanic leaders
            informed of the order of march.""")
    st.put("arminius", at=P(8000, 3200), facing=0, move="march")
    st.put("ger-bructeri", at=P(6500, 2200), facing=180, frame=True, move="march")
    st.put("ger-cherusci", at=P(7500, 2400), facing=180, frame=True, move="march")
    st.put("rom-leg", at=P(7500, 600), move="march")
    st.put("rom-aux", at=P(9100, 600), move="march")
    st.put("rom-baggage", at=P(5400, 600), move="march")
    st.put("varus", at=P(8300, 640), move="march")

    st.step("bructeri-raid", "The column is struck along its length", "Late morning, 8 September",
            """The Roman column now ran for 15 to 20 kilometres through forest and mud. Bructeri warriors fell on
            it in many places, throwing javelins and then pulling away. This raid was meant to tire the
            men and bruise the baggage rather than destroy the army. Losses were light, but wagons and the scouting
            horse suffered most. The Roman column could not form a line in the trees.""")
    st.put("ger-bructeri", at=P(5200, 1000), facing=180, state="engaged", width=900, move="attack")
    st.put("ger-cherusci", at=P(3500, 1000), facing=180, state="engaged", width=700, move="attack")
    st.put("rom-leg", at=P(5800, 600), state="engaged", move="march")
    st.put("rom-baggage", at=P(3200, 600), state="engaged", move="march")
    st.put("rom-aux", at=P(7500, 600), move="march")
    st.put("varus", at=P(6600, 640), move="march")
    st.put("arminius", at=P(6500, 1800), facing=270, move="march")
    st.note(P(5200, 1500), "Javelins from the tree line", "clash")

    st.step("rain-camp", "Rain and a camp in the forest", "Afternoon, 8 September",
            """A cloudburst turned the forest tracks to mud, and Varus ordered a halt. His men dug a camp and
            the commanders held a council. The reports showed modest losses, and the damage to the baggage was
            plain. The Germans withdrew into the trees. The exact position of this camp is unknown and
            is shown here in a reconstructed place. The army had been drawn off the paths it knew and into the territory chosen by Arminius.""")
    st.put("camp", at=P(3300, 600), shape="circle", width=400, depth=300, conjectural=True)
    st.put("rom-leg", at=P(3800, 700), width=300, depth=300, shape="block", state="ready", conjectural=True, move="march")
    st.put("rom-aux", at=P(4800, 700), width=250, depth=150, shape="block", conjectural=True, move="march")
    st.put("rom-baggage", at=P(2800, 650), width=250, depth=200, shape="block", state="ready")
    st.put("ger-bructeri", at=P(5200, 2000), state="ready", move="retreat")
    st.put("ger-cherusci", at=P(3500, 2100), state="ready", move="retreat")

    st.step("night-march", "Night march toward the pass", "Night, 8-9 September",
            """With the camp compromised, the army moved out in the dark and headed west along the sandy
            strip under Kalkriese Hill. The Germans reached the pass ahead of it. They held a wall of turf and sand
            along the foot of the hill and the Angrivarii manned it in strength. The Romans could not see the wall until they were close and
            beyond the Great Bog on one side and the hill on the other, there was no room to turn.""")
    st.put("rom-leg", at=P(1800, 20), facing=270, width=40, depth=1400, shape="column", move="march",
           state="ready")
    st.put("rom-aux", at=P(3200, 20), width=40, depth=800, shape="column", move="march")
    st.put("rom-baggage", at=P(4500, 20), width=40, depth=1000, shape="column", move="march")
    st.put("varus", at=P(1500, 30), move="march")
    st.hide("camp")
    st.put("ger-angri", at=P(100, -110), facing=0, width=1600, depth=90, frame=True, move="march")
    st.put("ger-bructeri", at=P(1800, -250), facing=0, width=700, depth=80, frame=True, conjectural=True, move="march")
    st.put("ger-cherusci", at=P(-1000, -250), facing=0, width=700, depth=80, frame=True, conjectural=True, move="march")
    st.put("arminius", at=P(300, -300), facing=0, conjectural=True, move="march")

    st.step("pass", "The gap at Kalkriese", "Dawn, 9 September",
            """The head of the column ran into a corridor barely 100 metres wide, between the wooded hill and
            the edge of the bog. A ditch crossed the road, and a zigzag wall of turf and packed sand ran along
            the hillside, hiding warriors who could throw down on the marching men. The column was stopped and
            bunched at the front while the rest of it, many kilometres behind, was still moving up. Arminius's
            plan was to catch it unable to deploy.""")
    st.put("rom-leg", at=P(1000, 20), width=60, depth=1000, shape="column", state="engaged")
    st.put("ger-angri", at=P(100, -110), state="engaged")
    st.put("varus", at=P(500, 30), move="march")
    st.note(P(100, 160), "Gap of about 100 m", "label")

    st.step("assault", "The Roman attempt on the wall", "Morning, 9 September",
            """The legionaries tried to storm the wall, forming up as well as the narrow strip allowed. Finds in
            front of the line, and almost none behind it, show that they never broke through. Missiles
            fell on them from above. Germanic bands also struck the stalled column from the north and east,
            and the baggage train piled up behind. The fight turned into a slow butchery.""")
    st.put("rom-leg", at=P(150, 20), width=90, depth=500, shape="block", state="engaged", move="attack")
    st.put("rom-aux", at=P(900, 20), width=70, depth=500, shape="block", state="engaged", move="march")
    st.put("rom-baggage", at=P(1900, 20), width=60, depth=800, shape="column", state="engaged", move="march")
    st.put("ger-bructeri", at=P(1800, 150), facing=180, width=900, depth=80, state="engaged", move="attack")
    st.put("ger-cherusci", at=P(-1000, 150), facing=90, width=500, depth=80, state="engaged", move="attack")
    st.put("ger-cherusci", state="engaged")
    st.note(P(-100, -250), "Ditch and turf wall", "clash")

    st.step("vala", "Vala rides off", "Midday, 9 September",
            """Numonius Vala, the senior officer after Varus, took the cavalry and tried to escape, according to
            Velleius Paterculus. Germanic horsemen caught and killed him, so the flight achieved nothing, and
            the infantry were left without their mounted arm. Order began to dissolve.""")
    st.put("rom-cav", at=P(2000, 10), facing=270, width=60, depth=250, shape="column", state="ready")
    st.put("rom-cav", at=P(-2200, 200), move="flank", state="routed")
    st.put("ger-cav", start=P(-3200, 500), at=P(-2300, 300), facing=90, width=80, depth=200, conjectural=True, state="engaged",
           move="pursuit")
    st.put("rom-cav", state="destroyed")
    st.put("rom-leg", state="wavering")
    st.note(P(-2200, 350), "Vala caught and killed", "death")

    st.step("collapse", "The Romans are overrun", "Afternoon, 9 September",
            """Warriors came over the wall and across the bog edge and cut down the broken Roman formations. Varus
            took his own life, as did other officers, among them Ceionius, who had first given himself up.
            Eggius died fighting at the head of his men. Roman dead are estimated at 15,000 to 20,000.
            Some captives were sacrificed, according to Tacitus.""")
    st.put("ger-angri", at=P(150, -30), facing=0, width=900, depth=120, state="engaged", move="charge")
    st.put("ger-bructeri", at=P(900, 200), state="engaged", move="charge")
    st.put("ger-cherusci", at=P(-400, 200), state="engaged", move="charge")
    st.put("rom-leg", state="destroyed")
    st.put("rom-aux", state="destroyed")
    st.put("rom-baggage", state="captured", by="german")
    st.put("varus", state="killed")
    st.note(P(450, 120), "Varus takes his own life", "death")

    st.step("aftermath", "Three legions lost", "After 9 September",
            """Three legions, the XVII, XVIII and XIX, ceased to exist and their numbers were never reissued.
            Augustus is said to have called out for his legions to be given back. Arminius sent Varus's head to
            Maroboduus of the Marcomanni with an offer of alliance, but the king refused and sent it on to Rome
            for burial. Rome rebuilt its Rhine army under Tiberius and later struck back, though it did not
            re-establish a province east of the river.""")
    st.put("ger-angri", state="ready")
    st.put("ger-bructeri", state="ready")
    st.put("ger-cherusci", state="ready")
    st.put("arminius", at=P(100, -200), facing=0)
    st.note(P(100, 400), "Scattered remains found 1987", "event")

    units = [
        {"id": "rom-leg", "side": "roman", "kind": "heavy_infantry", "label": "XVII, XVIII, XIX legions", "strength": "c. 15,000"},
        {"id": "rom-aux", "side": "roman", "kind": "light_infantry", "label": "Roman auxiliaries", "strength": "c. 4,500"},
        {"id": "rom-baggage", "side": "roman", "kind": "baggage", "label": "Baggage train"},
        {"id": "rom-cav", "side": "roman", "kind": "cavalry", "label": "Cavalry under Vala"},
        {"id": "varus", "side": "roman", "kind": "commander", "label": "Varus"},
        {"id": "camp", "side": "roman", "kind": "camp", "label": "Roman camp"},
        {"id": "ger-angri", "side": "german", "kind": "infantry", "label": "Angrivarii at the wall", "strength": "c. 5,000"},
        {"id": "ger-bructeri", "side": "german", "kind": "infantry", "label": "Bructeri", "strength": "c. 8,000"},
        {"id": "ger-cherusci", "side": "german", "kind": "infantry", "label": "Cherusci", "strength": "c. 8,000"},
        {"id": "ger-cav", "side": "german", "kind": "cavalry", "label": "Germanic horsemen"},
        {"id": "arminius", "side": "german", "kind": "commander", "label": "Arminius"},
    ]
    return st.doc(
        slug="battle-of-the-teutoburg-forest", kind="battle",
        entity={"name": "Battle of the Teutoburg Forest", "wikidata": "Q87779"},
        title="Battle of the Teutoburg Forest", date_label="8-11 September 9 AD", year=9,
        intro="""In September of 9 AD a Roman force under the governor Publius Quinctilius Varus was ambushed and
        destroyed in the forests of north-western Germany by a coalition of Germanic tribes led by Arminius, a
        Cherusci noble who had served Rome and held citizenship. Varus was leading three legions and their
        auxiliaries from summer quarters near the Weser back toward the Rhine, by a route Arminius had
        suggested. After a running fight through forest and rain, the survivors were caught on a narrow strip
        at Kalkriese between the hill and the bog, before a wall that the Germans had built. The disaster
        ended Roman ambitions east of the Rhine.""",
        outcome="A decisive Germanic victory: three Roman legions destroyed, and Rome gave up its plan to hold Germania up to the Elbe.",
        uncertainty="""The identification of Kalkriese as the main site is widely accepted, but not universally. The
        route taken, the camp location, the timing of the night march and the order of events along the 15 to
        20 km column are reconstructions, and the road line, wall course, bog outline and positions east of the pass
        are conjectural. Strengths on both sides are estimates. The unit placements follow a mainstream reading
        of Velleius Paterculus and Cassius Dio, both written later.""",
        sources=[{"title": "Battle of the Teutoburg Forest - Wikipedia",
                  "url": "https://en.wikipedia.org/wiki/Battle_of_the_Teutoburg_Forest", "kind": "web"}],
        sides=[
            {"id": "roman", "name": "Roman Empire", "color": "#b91c1c", "polity": {"name": "Roman Empire", "wikidata": "Q2277"},
             "commanders": [{"name": "Publius Quinctilius Varus", "wikidata": "Q214765", "role": "governor of Germania"}],
             "strength": "c. 17,000-20,000", "losses": "15,000-20,000 killed"},
            {"id": "german", "name": "Germanic coalition", "color": "#15803d", "polity": {"name": "Germanic peoples", "wikidata": "Q22633"},
             "commanders": [{"name": "Arminius", "wikidata": "Q68880", "role": "Cherusci leader"}],
             "strength": "c. 18,000-30,000", "losses": "unknown"},
        ],
        units=units,
        terrain=[
            {"id": "wiehen", "kind": "ridge", "label": "Kalkriese Hill and Wiehen Hills", "line": WIEHEN},
            {"id": "bog", "kind": "marsh", "label": "Great Bog", "area": BOG, "conjectural": True},
            {"id": "forest", "kind": "woods", "label": "Forested hillside", "area": FOREST, "conjectural": True},
            {"id": "road", "kind": "road", "label": "Sandy road", "line": ROAD, "conjectural": True},
            {"id": "wall", "kind": "wall", "label": "Germanic turf wall", "line": WALL, "conjectural": True},
            {"id": "kalkriese", "kind": "village", "label": "Kalkriese", "at": KALKRIESE},
        ],
    )
