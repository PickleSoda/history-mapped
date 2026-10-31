"""Battle of Carrhae, 9 June 53 BC — map story builder.
Anchors: Harran (Carrhae) from `places` / infobox P625; the Balikh river line from `places --geometry river`.
The exact field is unknown. It is placed conjecturally about 8 km south of Harran (F = field origin), between
the Balikh and the town; the stream, the hill where Publius fell and the roads are schematic.
Orientation (Plutarch via Wikipedia): the Romans marched NORTH up the Balikh caravan route from Syria, the
Parthians came on from the north/north-east facing SOUTH; the Roman square stood on the south side of a stream,
Publius was drawn off WEST to a hill, and the night retreat went NORTH to Carrhae. Cassius later led survivors
SOUTH-WEST to Syria. Numbers: infobox and Battle section of the English Wikipedia article.
"""
from pipeline.map_stories.geo import clip, ellipse, offset
from pipeline.map_stories.layout import Story, column, local_frame

ANCHOR = (39.02514, 36.87101)  # Harran (Carrhae)
_P = local_frame(ANCHOR)


def F(x, y):
    """Field frame: Harran lies at F(0, 8000); the Roman square stands near F(-2000, -3400)."""
    return _P(x, y - 8000)


BALIKH_FULL = [[38.93934, 36.67035], [38.9689, 36.64325], [38.96675, 36.63224], [38.9786, 36.62544], [38.97663, 36.61984], [38.98338, 36.6059], [38.99676, 36.60123], [38.9964, 36.59573], [39.00168, 36.59222], [38.99452, 36.58664], [38.99854, 36.57517], [39.00729, 36.5765], [39.01966, 36.55889], [39.03686, 36.55125], [39.03331, 36.52898], [39.02667, 36.52562]]
BALIKH = BALIKH_FULL[:5]

S = F(-2000, -3400)   # centre of the Roman square at the stream
S2 = F(-2700, -3700)  # after the general advance


def so(base_x, base_y, dx, dy):
    return F(base_x + dx, base_y + dy)


def sq(dx, dy):
    return F(-2000 + dx, -3400 + dy)


def sq2(dx, dy):
    return F(-2700 + dx, -3700 + dy)


def build() -> dict:
    st = Story()
    # ---- 1 march ----
    st.step("march", "Up the Balikh, refusing the Armenian road", "Spring 53 BC",
        """Crassus marches north from Syria with seven legions, about 4,000 light infantry and 4,000 cavalry. King Artavasdes of Armenia has twice offered troops and a route through the hills, away from the open plain; Crassus declines and takes the direct road through Mesopotamia. The guide Ariamnes urges haste and says the Parthians are weak. Modern study suggests the army kept to a busy caravan track beside the Balikh, where water was plentiful, not a waterless desert.""",
        camera={"center": F(-4800, -11500), "zoom": 12.6})
    st.place(column([F(-6200, -14400), F(-4300, -9700)],
                    [("rome-cav", 200), ("rome-sq", 1700), ("rome-light", 300)], spacing=60, width=260),
             state="ready", conjectural=True)
    st.put("crassus", at=F(-4500, -10600), conjectural=True)
    st.pin("crassus", "rome-sq")
    st.put("par-cat", at=F(3500, 4500), facing=200, width=320, depth=40, state="ready", frame=False, conjectural=True)
    st.put("par-ha-w", at=F(2200, 5200), facing=200, width=600, depth=30, state="ready", frame=False, conjectural=True)
    st.put("par-ha-e", at=F(4800, 5000), facing=200, width=600, depth=30, state="ready", frame=False, conjectural=True)
    st.put("par-ha-n", at=F(3000, 6200), facing=200, width=600, depth=30, state="ready", frame=False, conjectural=True)
    st.put("par-ha-s", at=F(4200, 6300), facing=200, width=600, depth=30, state="ready", frame=False, conjectural=True)
    st.put("surena", at=F(3600, 5600), frame=False, conjectural=True)
    st.note(F(-7600, -12600), "Armenian route refused", "event", conjectural=True)

    # ---- 2 contact ----
    st.step("contact", "Scouts slain: the army forms a square", "Morning, 9 June",
        """Near Carrhae the Roman reconnaissance screen finds its scouts dead and a large body of cavalry approaching. The army panics. Cassius advises the old order, legions in the centre and horse on both wings. Crassus agrees, then thinks again and closes the army into a hollow square, twelve cohorts to a side. A square cannot be turned, but it can barely manoeuvre. Light troops and cavalry are shown behind it here; Plutarch places them within.""",
        camera={"center": F(0, -2500), "zoom": 12.0})
    st.put("rome-sq", at=F(-3000, -6800), facing=0, shape="square", width=900, depth=900, move="advance", conjectural=True)
    st.put("rome-cav", at=F(-3330, -7340), facing=0, width=300, depth=40, conjectural=True, move="advance")
    st.put("rome-light", at=F(-2670, -7340), facing=0, width=400, depth=60, conjectural=True, move="advance")
    st.put("par-cat", at=F(2600, 1800), frame=True, move="advance")
    st.put("par-ha-w", at=F(1300, 2600), frame=True, move="advance")
    st.put("par-ha-e", at=F(3800, 2400), frame=True, move="advance")
    st.put("surena", at=F(2700, 2300), frame=True, move="advance")
    st.note(F(-3000, -6100), "Square formed, twelve cohorts a side", "label", conjectural=True)

    # ---- 3 stream ----
    st.step("stream", "The stream: rest, or fight at once?", "Midday",
        """The square plods on to a stream. The senior officers want to camp and fight the next morning, so the men can rest and the Parthians can be scouted. Publius, eager for battle, wins his father over. Historians have noted that no one proposed moving to ground less friendly to cavalry. Crassus gives the order to fight immediately, and the Romans halt on the stream bank with the Parthians in sight to the north.""",
        camera={"center": F(-300, -800), "zoom": 12.4})
    st.put("rome-sq", at=S, move="advance")
    st.put("rome-cav", at=sq(-330, -540), move="advance")
    st.put("rome-light", at=sq(330, -540), move="advance")
    st.put("par-cat", at=F(1500, 1500), move="advance")
    st.put("par-ha-w", at=F(-400, 1700), move="advance")
    st.put("par-ha-e", at=F(2800, 1500), move="advance")
    st.put("surena", at=F(1600, 1900), move="advance")
    st.note(sq(250, 700), "Council at the stream: Publius urges battle", "label", conjectural=True)

    # ---- 4 drums ----
    st.step("drums", "Drums and unveiled armour", "Afternoon",
        """Surena tries to frighten the Romans before a blow is struck. His men beat a great number of hollow drums, whose din unsettles the legionaries. Then the cataphracts, who had advanced with their armour hidden under cloths, throw the cloths away together and appear in blazing steel. Surena had meant to break the square with a cataphract charge, but judges it will not yet suffice and sends the horse archers to circle round it instead.""",
        camera={"center": F(-1500, -1200), "zoom": 12.8})
    st.put("par-cat", at=F(-800, -800), facing=190, move="advance")
    st.put("par-ha-w", at=F(-1900, -600), facing=190, move="advance")
    st.put("par-ha-e", at=F(300, -500), facing=190, move="advance")
    st.put("par-ha-n", at=F(-800, 300), facing=190, frame=True, move="advance")
    st.put("par-ha-s", at=F(-800, 900), facing=190, frame=True, move="advance")
    st.put("surena", at=F(-800, 200), move="advance")
    st.note(F(-800, -300), "Drums; cloths dropped", "event")

    # ---- 5 encirclement ----
    st.step("encircle", "The horse archers ring the square", "Afternoon",
        """The horse archers ride round the square and loose from every side, always beyond javelin range. Crassus sends his skirmishers out to drive them off, but arrows force these back among the legions. Shields and mail protect much of the body, yet not the whole of it, and arrows find the exposed limbs. Each time the legionaries lunge at their tormentors, the archers draw away, shooting as they go, and the square can neither catch nor outrun them.""",
        camera={"center": S, "zoom": 13.4})
    st.put("par-ha-n", at=sq(0, 680), facing=180, width=700, depth=30, state="engaged", move="flank")
    st.put("par-ha-s", at=sq(0, -680), facing=0, width=700, depth=30, state="engaged", move="flank")
    st.put("par-ha-w", at=sq(-680, 0), facing=90, width=700, depth=30, state="engaged", move="flank")
    st.put("par-ha-e", at=sq(680, 0), facing=270, width=700, depth=30, state="engaged", move="flank")
    st.put("par-cat", at=sq(0, 1100), facing=180, state="ready", move="retreat")
    st.put("surena", at=sq(900, 1000), move="retreat")
    st.put("rome-sq", state="engaged")
    st.put("rome-light", at=sq(0, 560), facing=0, width=500, depth=30, state="wavering", move="attack")
    st.fire("par-ha-n", "rome-sq")
    st.fire("par-ha-w", "rome-sq")
    st.fire("par-ha-e", "rome-sq")
    st.fire("par-ha-s", "rome-sq")
    st.note(sq(450, 1000), "Skirmishers driven back by arrows", "clash")

    # ---- 6 testudo ----
    st.step("testudo", "Shields locked, cataphracts charge", "Late afternoon",
        """The legionaries lock their shields into a testudo to blunt the arrows, but in that dense order they cannot fight hand to hand. The cataphracts exploit it, charging the line again and again and spreading panic and loss. When the Romans loosen ranks to face them, the cataphracts draw off and the archers, whose shooting has barely paused, strike the opened ranks. Crassus hopes the Parthians will run short of arrows.""",
        camera={"center": S, "zoom": 13.4})
    st.put("rome-light", at=sq(330, -540), facing=0, width=400, depth=60, state="engaged", move="retreat")
    st.put("par-cat", at=sq(0, 580), facing=180, width=320, depth=40, state="engaged", move="charge")
    st.fire("par-ha-w", "rome-sq")
    st.fire("par-ha-s", "rome-sq")
    st.note(sq(0, 900), "Cataphracts charge the locked shields", "clash")

    # ---- 7 camels ----
    st.step("camels", "Camels bring fresh arrows", "Late afternoon",
        """Crassus's hope fails. Surena has a baggage train of some thousand camels, and they carry arrows up to the horse archers, who shoot without a break. Once he sees this, Crassus knows he cannot wait for the Parthians to run dry. The square has stood under fire for hours with its wounded growing in number; he must act, and he turns to the one body of mobile troops he has.""",
        camera={"center": sq(900, 200), "zoom": 13.4})
    st.put("par-cat", at=sq(0, 1100), facing=180, state="ready", move="retreat")
    st.put("par-camels", at=sq(1050, 200), facing=270, width=200, depth=40, conjectural=True, move="advance",
           start=sq(2800, 300))
    st.fire("par-camels", "par-ha-e", mlabel="arrows")
    st.fire("par-ha-e", "rome-sq")
    st.note(sq(1700, 500), "Camel train resupplies the archers", "event")

    # ---- 8 Publius sortie ----
    st.step("sortie", "Publius sallies out; the Parthians feign flight", "Evening",
        """Crassus detaches his son Publius with 1,300 Gallic horse, 500 archers and eight cohorts of legionaries to drive off the horse archers. The archers appear to give way and Publius follows, drawn steadily westward. His men suffer heavy loss to arrow fire on the way and lose touch with the main army. The pursuit is exactly what Surena wanted.""",
        camera={"center": sq(-1700, -400), "zoom": 13.0})
    st.put("publius-cav", at=sq(-2600, -600), facing=270, width=260, depth=30, state="ready", move="attack",
           start=sq(-560, -60), conjectural=True)
    st.put("publius-inf", at=sq(-2300, -550), facing=270, width=220, depth=40, state="ready", move="attack",
           start=sq(-520, 30), conjectural=True)
    st.put("par-ha-w", at=sq(-3900, -1400), facing=270, state="ready", move="feint")
    st.note(sq(-2500, 250), "Archers feign retreat westward", "event", conjectural=True)

    # ---- 9 hill ----
    st.step("hill", "Publius is cut off on a hill", "Evening",
        """With Publius well away from the army, the cataphracts turn on his column while the horse archers close the way back. The Gauls fight bravely but are outclassed in arms and armour. The survivors fall back to a hill, where Publius and his officers fall on their swords. Only 500 of the Gauls are taken alive. The main army, a few kilometres away, still does not know what has happened.""",
        camera={"center": sq(-2400, -800), "zoom": 12.8})
    st.put("publius-cav", at=sq(-4700, -1500), state="destroyed", move="retreat")
    st.put("publius-inf", at=sq(-4400, -1300), state="destroyed", move="retreat")
    st.put("par-cat", at=sq(-3700, -1000), facing=270, width=320, depth=40, state="engaged", move="charge")
    st.put("par-ha-w", at=sq(-3300, -700), facing=270, width=400, depth=30, state="engaged", move="advance")
    st.put("rome-sq", state="engaged")
    st.note(sq(-5000, -1850), "Publius dies on the hill", "death", conjectural=True)

    # ---- 10 head, barrage ----
    st.step("head", "Publius's head; the barrage goes on", "Dusk",
        """Fearing for Publius, Crassus orders a general advance and is met by the sight of his son's head carried on a spear. The Parthians close round the whole square again. Horse archers shoot from every side, and cataphract charges tear the order of the legions. The pressure does not slacken until nightfall. Crassus, hearing that his son is dead and the day lost, is said to have collapsed into near despair.""",
        camera={"center": sq2(-300, 0), "zoom": 13.2})
    st.put("rome-sq", at=S2, move="advance")
    st.put("rome-cav", at=sq2(-330, -540), move="advance")
    st.put("rome-light", at=sq2(330, -540), move="advance")
    st.put("par-ha-n", at=sq2(0, 680), facing=180, move="advance")
    st.put("par-ha-s", at=sq2(0, -680), facing=0, move="advance")
    st.put("par-ha-w", at=sq2(-680, 0), facing=90, state="engaged", move="advance")
    st.put("par-ha-e", at=sq2(680, 0), facing=270, move="advance")
    st.put("par-cat", at=sq2(0, 580), facing=180, width=320, depth=40, move="charge")
    st.hide("publius-cav")
    st.hide("publius-inf")
    st.fire("par-ha-n", "rome-sq")
    st.fire("par-ha-e", "rome-sq")
    st.note(sq2(-1400, 150), "Publius's head shown on a spear", "capture", conjectural=True)

    # ---- 11 night retreat ----
    st.step("night", "Night: retreat to Carrhae", "Night, 9-10 June",
        """After dark the Parthians break off. Crassus orders a ragged retreat to Carrhae and leaves about 4,000 wounded, who are killed next morning. Four cohorts lose their way in the dark and are surrounded on a hill, and only 20 men survive. Plutarch makes the disorder of this withdrawal one of Crassus's worst failures, and the modern view agrees that the poorly organised retreat did most to destroy the army's chance of regrouping.""",
        light="night", camera={"center": F(-2000, 2200), "zoom": 11.4})
    st.put("rome-wounded", at=S2, facing=0, width=500, depth=60, state="wounded", conjectural=True)
    st.put("rome-lost", at=F(-5400, -2200), facing=0, width=240, depth=60, state="engaged", conjectural=True)
    st.put("rome-sq", at=F(-400, 6600), facing=0, shape="column", width=260, depth=1700, state="wavering",
           move="retreat", conjectural=True)
    st.put("rome-cav", at=F(-250, 7650), facing=0, width=240, depth=60, move="retreat")
    st.put("rome-light", at=F(-650, 7650), facing=0, width=240, depth=60, move="retreat")
    st.put("par-cat", at=F(-1500, -2500), facing=0, width=320, depth=40, state="ready", move="pursuit")
    st.put("par-ha-s", at=F(-4600, -1900), facing=270, width=400, depth=30, move="advance")
    st.note(F(-4900, -1300), "Four lost cohorts surrounded; 20 survive", "death", conjectural=True)
    st.note(sq2(500, 300), "About 4,000 wounded left behind", "event")

    # ---- 12 parley ----
    st.step("parley", "The parley and Crassus's death", "10 June",
        """Next day Surena offers the Romans a truce and safe return to Syria if Rome gives up all land east of the Euphrates. Crassus is reluctant, but his troops threaten to mutiny unless he agrees. At the meeting a Parthian tugs at Crassus's reins, a struggle breaks out, and Crassus and his officers are killed. The remaining Romans try to run and most are killed or taken. Cassius leads about 10,000 survivors out of the trap and back to Syria.""",
        camera={"center": F(-2200, 5600), "zoom": 12.3})
    st.put("rome-sq", at=F(-900, 6500), state="routed", shape="block", width=500, depth=500, move="rout")
    st.put("crassus", at=F(300, 6200), state="killed", conjectural=True)
    st.put("surena", at=F(900, 6000), move="advance", conjectural=True)
    st.put("par-cat", at=F(1500, 5200), facing=200, width=320, depth=40, state="ready", move="advance")
    st.put("par-ha-n", at=F(300, 5600), state="ready", move="advance")
    st.put("par-ha-e", at=F(-2500, 5000), state="engaged", move="pursuit")
    st.put("par-ha-w", at=F(-3800, 3200), facing=0, state="ready", move="pursuit")
    st.put("par-ha-s", at=F(1400, 5000), facing=200, state="ready", move="advance")
    st.hide("par-camels")
    st.hide("rome-wounded")
    st.hide("rome-lost")
    st.put("cassius", at=F(-1500, 6900), conjectural=True)
    st.put("cassius", at=F(-5600, 2700), move="retreat")
    st.note(F(300, 6600), "Crassus killed at the parley", "death", conjectural=True)
    st.note(F(-5600, 3200), "Cassius leads c. 10,000 back to Syria", "event")

    return st.doc(slug="battle-of-carrhae", kind="battle",
        entity={"name": "Battle of Carrhae", "wikidata": "Q205887"},
        title="Battle of Carrhae", date_label="9 June 53 BC", year=-53,
        intro="""In June 53 BC Marcus Licinius Crassus, the richest man in Rome, led seven legions into Mesopotamia against Parthia without the Senate's consent. He rejected the Armenian king's offer of a safer route through the hills and followed a caravan track north along the Balikh. Near the town of Carrhae, now Harran in Turkey, he met a force of about 10,000 under the Parthian spahbod Surena: 1,000 armoured cataphracts and 9,000 horse archers, backed by a train of camels carrying arrows. Crassus drew his infantry into a hollow square on open ground. Surena's horse archers circled it and shot into it while the cataphracts waited to charge whenever the Romans moved. Crassus's son Publius was lured away and destroyed with his detachment, and the army's night retreat ended at the parley where Crassus himself died. It is one of the heaviest defeats in Roman history.""",
        outcome="Decisive Parthian victory: Crassus was killed at the parley and Rome lost some 20,000 dead and 10,000 captured.",
        uncertainty="""The exact battlefield is not known. Everything south of Harran in this replay is a reconstruction and is marked conjectural: the field, the stream where the Romans halted, the hill where Publius died, the retreat road and the lost cohorts' hill. The Roman light troops and cavalry are drawn behind the square though Plutarch has them inside it. The Parthian approach from the north-east is implied rather than stated. Troop numbers are ancient estimates, chiefly Plutarch's, and modern historians dispute his account of the guide Ariamnes leading the army into a waterless desert.""",
        sources=[{"title": "Battle of Carrhae, Wikipedia", "url": "https://en.wikipedia.org/wiki/Battle_of_Carrhae", "kind": "web"}],
        sides=[
            {"id": "rome", "name": "Roman Republic", "color": "#b91c1c", "polity": {"name": "Roman Republic", "wikidata": "Q17167"},
             "commanders": [{"name": "Marcus Licinius Crassus", "wikidata": "Q175121", "role": "commander, killed"},
                            {"name": "Publius Licinius Crassus", "wikidata": "Q382280", "role": "cavalry commander, killed"},
                            {"name": "Gaius Cassius Longinus", "wikidata": "Q207370", "role": "quaestor, led the survivors out"}],
             "strength": "c. 42,000", "losses": "c. 20,000 killed, 10,000 captured"},
            {"id": "parthia", "name": "Parthian Empire", "color": "#1d4ed8", "polity": {"name": "Parthian Empire", "wikidata": "Q1986139"},
             "commanders": [{"name": "Surena", "wikidata": "Q470523", "role": "commander"}, {"name": "Silaces", "wikidata": "Q86755352", "role": "commander"}],
             "strength": "c. 10,000", "losses": "minimal"}],
        units=[
            {"id": "rome-sq", "side": "rome", "kind": "heavy_infantry", "label": "Legions", "strength": "c. 28,000-35,000", "strength_n": 31000},
            {"id": "rome-light", "side": "rome", "kind": "light_infantry", "label": "Light foot", "strength": "c. 4,000", "strength_n": 4000},
            {"id": "rome-cav", "side": "rome", "kind": "cavalry", "label": "Cavalry", "strength": "c. 2,700"},
            {"id": "publius-cav", "side": "rome", "kind": "cavalry", "label": "Publius: Gallic horse", "strength": "1,300", "strength_n": 1300},
            {"id": "publius-inf", "side": "rome", "kind": "heavy_infantry", "label": "Publius: 8 cohorts", "strength": "8 cohorts, 500 archers"},
            {"id": "rome-wounded", "side": "rome", "kind": "group", "label": "Wounded left behind", "strength": "c. 4,000"},
            {"id": "rome-lost", "side": "rome", "kind": "heavy_infantry", "label": "4 lost cohorts", "strength": "4 cohorts"},
            {"id": "crassus", "side": "rome", "kind": "commander", "label": "Crassus"},
            {"id": "cassius", "side": "rome", "kind": "commander", "label": "Cassius"},
            {"id": "par-cat", "side": "parthia", "kind": "heavy_cavalry", "label": "Cataphracts", "strength": "1,000", "strength_n": 1000},
            {"id": "par-ha-w", "side": "parthia", "kind": "horse_archers", "label": "Archers W", "strength": "c. 2,250"},
            {"id": "par-ha-e", "side": "parthia", "kind": "horse_archers", "label": "Archers E", "strength": "c. 2,250"},
            {"id": "par-ha-n", "side": "parthia", "kind": "horse_archers", "label": "Archers N", "strength": "c. 2,250"},
            {"id": "par-ha-s", "side": "parthia", "kind": "horse_archers", "label": "Archers S", "strength": "c. 2,250"},
            {"id": "par-camels", "side": "parthia", "kind": "baggage", "label": "Arrow camels", "strength": "c. 1,000 camels"},
            {"id": "surena", "side": "parthia", "kind": "commander", "label": "Surena"}],
        terrain=[
            {"id": "carrhae", "kind": "town", "label": "Carrhae (Harran)", "at": list(ANCHOR)},
            {"id": "balikh", "kind": "river", "label": "Balikh", "line": BALIKH},
            {"id": "caravan-road", "kind": "road", "label": "Caravan route (approx.)",
             "line": [list(F(-6400, -14800)), list(F(-5200, -11800)), list(F(-4300, -9700)), list(F(-3000, -6800)), list(F(-2000, -3400))], "conjectural": True},
            {"id": "stream", "kind": "stream", "label": "Stream (site conjectural)",
             "line": [list(F(-6500, -2800)), list(F(-4000, -2300)), list(F(-1500, -2100)), list(F(1500, -2000)), list(F(4000, -1600))], "conjectural": True},
            {"id": "hill", "kind": "hill", "label": "Hill of Publius (conj.)", "area": ellipse(sq(-4900, -1700), 400, 300), "conjectural": True},
            {"id": "lost-hill", "kind": "hill", "label": "Hill (conj.)", "area": ellipse(F(-5400, -2000), 300, 250), "conjectural": True},
            {"id": "carrhae-road", "kind": "road", "label": "Road to Carrhae (approx.)",
             "line": [list(F(-2700, -3700)), list(F(-1800, 1200)), list(F(-900, 5200)), list(ANCHOR)], "conjectural": True},
            {"id": "plain", "kind": "field", "label": "Open plain (conjectural)", "area": ellipse(F(-2500, -2800), 3800, 2400), "conjectural": True}])
