"""Battle of Tours (Poitiers), October 732 - map story builder.

Anchors: Moussais-la-Bataille (0.488, 46.737), the traditional site, via `places`; Naintre, Cenon-sur-Vienne and
Vouneuil-sur-Vienne from `places`. The exact field is unknown (Wikidata P625 sits near Tours); all positions are
a conjectural reconstruction. The Clain and Vienne were not returned by `places --geometry`, so they are hand-drawn
and marked conjectural. Orientation: the Franks stood on high, wooded ground in a dense block and faced south;
the Umayyads came up from the south (Poitiers direction) heading north to Tours and charged uphill, facing north.
Sources: Wikipedia, Battle of Tours (Preparations and maneuver, Engagement, Strategic analysis).
"""
from pipeline.map_stories.geo import ellipse, offset
from pipeline.map_stories.layout import Story, deploy_line, facing_off, local_frame, wing, when

ANCHOR = (0.48793, 46.73671)
P = local_frame(ANCHOR)

CLAIN = [P(-2600, -3500), P(-1800, -1800), P(-900, -600), P(300, 1500), P(2400, 3300), P(4600, 4300)]
VIENNE = [P(5200, -2800), P(5000, 0), P(5100, 2000), P(4900, 4000), P(5200, 6200)]
HILL = ellipse(P(0, 650), 1300, 700)
WOODS = ellipse(P(-100, 40), 1200, 280)


def build() -> dict:
    st = Story()

    st.step("raid", "The raiders push toward the Loire", "Summer-autumn 732", """
        After beating Duke Odo on the Garonne, the Umayyad army of al-Andalus moved north through Aquitaine. Its
        fast cavalry had outrun the supply wagons and much of the host, and it split into raiding parties while the
        main body followed more slowly. The prize may have been the rich abbey of Saint Martin at Tours, the holiest
        shrine of the West. Abd al-Rahman waited for the harvest before moving, so that the army could eat off the land.""")
    st.put("umayyad-main", at=P(-1800, -4200), facing=20, width=700, depth=120)
    st.put("umayyad-raiders", at=P(-3800, -3000), facing=15, width=600, depth=90, frame=False)
    st.put("abd-al-rahman", at=P(-1800, -4300), frame=False)
    st.pin("abd-al-rahman", "umayyad-main")

    st.step("frankish-march", "Charles marches by stealth", "Autumn 732", """
        Odo, beaten and short of men, appealed to the Franks, and Charles Martel agreed only after Odo accepted
        Frankish overlordship. Charles gathered Austrasian Franks and auxiliaries from beyond the Rhine, including
        Thuringians, Alemanni and Bavarians, and marched south while avoiding the old Roman roads. His aim was to
        arrive unseen, so that he and not the enemy would choose the ground.""")
    st.put("franks-main", at=P(300, 5200), facing=180, width=500, depth=80)
    st.put("franks-allies", at=P(-500, 5400), facing=180, width=300, depth=60, frame=False)
    st.put("martel", at=P(300, 5100), frame=False)
    st.pin("martel", "franks-main")
    st.side_move("franks", "march", [P(300, 9000), P(300, 5200)], label="Charles avoids the roads")

    st.step("surprise", "The Umayyads find a wall in front of them", "Early October 732", """
        The invaders were caught off guard to find a large army sitting squarely across their road to Tours. Charles
        chose not to attack. He drew his men up on high ground with trees before them, in a deep, close formation that
        Arab sources describe as a great square, so that any cavalry charge would have to climb and thread through
        timber. The forest also hid how many Franks there really were.""")
    st.put("franks-allies", at=P(-560, 600), facing=180, width=560, depth=170, frame=True, move="advance", conjectural=True)
    st.put("franks-main", at=P(100, 600), facing=180, width=760, depth=170, frame=True, move="advance", conjectural=True)
    st.put("franks-levies", at=P(650, 600), facing=180, width=300, depth=120, frame=True, conjectural=True)
    st.pin("martel", "franks-main")
    st.put("umayyad-main", at=P(0, -1500), facing=0, width=1200, depth=150, frame=True, move="advance", conjectural=True)
    st.put("umayyad-raiders", at=P(-1200, -1700), facing=0, width=500, depth=100, frame=True, move="advance", conjectural=True)
    st.pin("abd-al-rahman", "umayyad-main")

    st.step("waiting", "A week of skirmishing", "c. 3-9 October 732", """
        For about a week neither side wished to attack. The Umayyads waited for the rest of their strength to come
        up and hoped to draw the Franks down into open ground; they could not judge Frankish numbers. Charles, whose
        men were dressed for the northern cold and whose levies were foraging and harassing the enemy, was content to
        wait while winter drew nearer and the invaders' food ran short.""")
    st.put("umayyad-raiders", at=P(-900, -1400), facing=0, move="march", conjectural=True)
    st.put("franks-levies", at=P(900, 450), facing=160, width=260, depth=60, state="ready", move="feint", conjectural=True)
    st.note(P(900, -200), "Skirmishes between the lines", "label", conjectural=True)

    st.step("first-charge", "Abd al-Rahman orders the charge", "Seventh day, 10 October 732", """
        Abd al-Rahman would not wait longer, with winter coming and Tours still unreached. On the seventh day he put his
        faith in his cavalry and sent it against the hill. The horsemen had to ride uphill and through the trees,
        which blunted the shock they were used to delivering. The Frankish infantry held its ground in a tight mass.""")
    st.put("umayyad-cav-1", start=P(-250, -950), at=P(-250, -400), facing=0, width=700, depth=100, state="engaged", move="charge", conjectural=True)
    st.put("franks-main", state="engaged")
    st.put("franks-allies", state="engaged")
    st.put("umayyad-main", at=P(0, -1100), facing=0, width=1000, depth=150, move="advance", conjectural=True)
    st.note(P(-100, 300), "Uphill through the trees", "clash", conjectural=True)

    st.step("repeated-charges", "Charge after charge", "Through the day", """
        The charges came again and again all day. Arab accounts say the horsemen broke into the Frankish square more
        than once, and western accounts agree the fight was hard. Yet the formation re-closed each time. Charles's
        veterans, many of them campaigning with him for years, did what contemporaries thought impossible: they stood
        against heavy cavalry on foot and did not break.""")
    st.put("umayyad-cav-1", at=P(-300, -80), facing=0, state="engaged", move="charge", conjectural=True)
    st.put("umayyad-cav-2", start=P(350, -1000), at=P(350, -420), facing=0, width=700, depth=100, state="engaged", move="charge", conjectural=True)
    st.put("umayyad-cav-3", start=P(-700, -1000), at=P(-700, -500), facing=0, width=500, depth=90, state="engaged", move="charge", conjectural=True)
    st.put("franks-levies", state="engaged")
    st.note(P(0, 250), "Horsemen break in, Franks re-close", "clash", conjectural=True)

    st.step("al-ghafiqi-falls", "The Umayyad commander is killed", "10 October 732", """
        Abd al-Rahman al-Ghafiqi was killed in the fighting. Loss of the governor and commander unsettled an army that
        had already suffered losses and carried a great deal of plunder. The line of Umayyad cavalry stalled against the
        Frankish block. Where exactly and how he fell is not agreed; the mainstream account places it in the day's
        assaults on the hill.""")
    st.put("abd-al-rahman", at=P(-150, -250), state="killed", conjectural=True)
    st.put("umayyad-cav-1", state="wavering")
    st.put("umayyad-cav-2", state="wavering")
    st.put("umayyad-cav-3", state="wavering")
    st.note(P(-150, -250), "Abd al-Rahman killed", "death", conjectural=True)

    st.step("withdrawal", "The invaders withdraw", "After the battle", """
        With the commander dead and the Franks still standing on their hill, the Umayyad army gave up the attempt on
        Tours and retreated south, back over the Pyrenees. Charles did not follow far, and the Frankish army, which had
        no standing force to keep it in the field, returned north. The raid on the heartland of Francia had failed.""")
    st.put("umayyad-main", at=P(0, -3500), facing=180, state="ready", move="retreat", frame=False)
    st.put("umayyad-raiders", at=P(-900, -3400), facing=180, move="retreat", frame=False)
    st.put("umayyad-cav-1", at=P(-300, -2400), facing=180, state="routed", move="retreat", conjectural=True)
    st.put("umayyad-cav-2", at=P(350, -2300), facing=180, state="routed", move="retreat", conjectural=True)
    st.put("umayyad-cav-3", at=P(-700, -2500), facing=180, state="routed", move="retreat", conjectural=True)
    st.put("franks-main", state="ready")
    st.put("franks-allies", state="ready")
    st.put("franks-levies", state="ready")

    st.step("aftermath", "After Tours", "735-739", """
        Charles kept pressing south. Odo died around 735 and his son Hunald took the duchy, bowing to Charles when a
        fresh Umayyad force entered Provence. In 735 a new governor, Uqba ibn al-Hajjaj, took Arles and Avignon and held
        part of Provence and Septimania for four years; Charles campaigned there in 736 and 739. Raids went on, but no
        large Umayyad army crossed the Pyrenees again, and Charles's prestige paved the way for the Carolingian dynasty.""")
    st.put("franks-main", at=P(300, 1800), facing=180, move="march")
    st.put("franks-allies", at=P(-400, 1800), facing=180, move="march", frame=False)
    st.put("franks-levies", at=P(800, 1700), facing=180, move="march", frame=False)

    units = [
        {"id": "franks-allies", "side": "franks", "kind": "infantry", "label": "Rhenish allies"},
        {"id": "franks-main", "side": "franks", "kind": "heavy_infantry", "label": "Austrasian infantry", "strength": "veteran core"},
        {"id": "franks-levies", "side": "franks", "kind": "light_infantry", "label": "Frankish levies"},
        {"id": "martel", "side": "franks", "kind": "commander", "label": "Charles Martel"},
        {"id": "umayyad-main", "side": "umayyad", "kind": "army", "label": "Umayyad main body"},
        {"id": "umayyad-raiders", "side": "umayyad", "kind": "light_cavalry", "label": "Raiding parties"},
        {"id": "umayyad-cav-1", "side": "umayyad", "kind": "heavy_cavalry", "label": "Cavalry, first charge"},
        {"id": "umayyad-cav-2", "side": "umayyad", "kind": "cavalry", "label": "Cavalry, right"},
        {"id": "umayyad-cav-3", "side": "umayyad", "kind": "light_cavalry", "label": "Cavalry, left"},
        {"id": "abd-al-rahman", "side": "umayyad", "kind": "commander", "label": "Abd al-Rahman"},
    ]
    terrain = [
        {"id": "hill", "kind": "hill", "label": "Wooded high ground", "area": HILL, "conjectural": True},
        {"id": "woods", "kind": "woods", "label": "Trees before the Franks", "area": WOODS, "conjectural": True},
        {"id": "clain", "kind": "river", "label": "Clain", "line": CLAIN, "conjectural": True},
        {"id": "vienne", "kind": "river", "label": "Vienne", "line": VIENNE, "conjectural": True},
        {"id": "moussais", "kind": "village", "label": "Moussais-la-Bataille", "at": list(ANCHOR)},
        {"id": "naintre", "kind": "village", "label": "Naintre", "at": [0.48237, 46.76389]},
        {"id": "cenon", "kind": "village", "label": "Cenon-sur-Vienne", "at": [0.53575, 46.77430]},
    ]
    return st.doc(
        slug="battle-of-tours", kind="battle", entity={"name": "Battle of Tours", "wikidata": "Q173077"},
        title="Battle of Tours", date_label="10 October 732", year=732,
        intro="""In October 732 a Frankish army under Charles Martel met an Umayyad army from al-Andalus somewhere between
            Tours and Poitiers, in the heart of Gaul. The Umayyads, led by the governor Abd al-Rahman al-Ghafiqi, had crushed
            Duke Odo of Aquitaine and then pushed north, perhaps drawn by the wealth of the abbey of Saint Martin at Tours.
            Charles, called in by Odo, marched by stealth, took high ground among trees and made his veteran infantry stand
            in a dense block. After a week of skirmishing the Umayyads charged uphill. The Franks held, Abd al-Rahman was
            killed, and the invaders withdrew south. The exact site, the numbers and the true weight of the victory are all
            debated.""",
        outcome="Frankish victory: Abd al-Rahman was killed and the Umayyad army withdrew south over the Pyrenees.",
        uncertainty="""The site is unknown; Moussais-la-Bataille is only the traditional guess and Wikidata places it near
            Tours. All unit positions, the hill, the woods and the Clain and Vienne lines are conjectural reconstructions.
            Army sizes (about 15,000-30,000 Franks, 20,000-30,000 Umayyads) are contested, and older claims of heavy Frankish
            inferiority are disputed. The timing of Abd al-Rahman's death and the exact retreat are not recorded in detail.""",
        sources=[{"title": "Battle of Tours - Wikipedia", "url": "https://en.wikipedia.org/wiki/Battle_of_Tours", "kind": "web"}],
        sides=[
            {"id": "franks", "name": "Franks and Aquitaine", "color": "#1d4ed8",
             "polity": {"name": "Francia", "wikidata": "Q146246"},
             "commanders": [{"name": "Charles Martel", "wikidata": "Q3301", "role": "Mayor of the Palace"},
                            {"name": "Odo the Great", "wikidata": "Q269536", "role": "Duke of Aquitaine"}],
             "strength": "c. 15,000-30,000", "losses": "Unknown"},
            {"id": "umayyad", "name": "Umayyad army", "color": "#15803d",
             "polity": {"name": "Umayyad Caliphate", "wikidata": "Q8575586"},
             "commanders": [{"name": "Abd al-Rahman al-Ghafiqi", "wikidata": "Q220228", "role": "Governor of al-Andalus"}],
             "strength": "c. 20,000-30,000", "losses": "Abd al-Rahman killed"},
        ],
        units=units, terrain=terrain)
