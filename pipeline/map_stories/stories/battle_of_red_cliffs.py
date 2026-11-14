"""Battle of Red Cliffs, winter 208 AD - map story builder.

Anchors: Chibi (113.62682, 29.87402, places/OSM) on the south bank; Wulin (113.59841, 29.91271) on the north bank;
Yangtze line from OSM (runs SW to NE here, flowing north-east). Allies hold the south (south-east) bank facing
north-west; Cao Cao's army stands at Wulin on the north bank facing south-east. Exact battle site is disputed
(Chibi, Jiayu, Wuhan, Huangzhou): Chibi is used as the mainstream pick; all unit positions are reconstructed.
Sources: Wikipedia Battle of Red Cliffs (Battle, Location, Analysis, Aftermath sections).
"""
from pipeline.map_stories.geo import dest, along, offset
from pipeline.map_stories.layout import Story, local_frame

ANCHOR = (113.62682, 29.87402)
P = local_frame(ANCHOR)
YANGTZE = [[113.48055, 29.81045], [113.49396, 29.81741], [113.5168, 29.82753], [113.55319, 29.84555], [113.58134, 29.86133], [113.60357, 29.8744], [113.61091, 29.88099], [113.62859, 29.90242], [113.63992, 29.91462], [113.65356, 29.92861], [113.66712, 29.93976], [113.67528, 29.9456], [113.68172, 29.94783], [113.68682, 29.94813], [113.69176, 29.94728], [113.69554, 29.94568], [113.70009, 29.94259], [113.7109, 29.93061], [113.71373, 29.92838], [113.71957, 29.92561], [113.72437, 29.92416], [113.72987, 29.92308], [113.73356, 29.9228], [113.75073, 29.92221], [113.76353, 29.9223]]
WULIN = (113.59841, 29.91271)
CHIBI = (113.62682, 29.87402)
FLOW = 40  # river flows towards the north-east here


def S(t, d):
    """Point a fraction t along the river, d metres to the south bank (+) or north bank (-)."""
    return dest(along(YANGTZE, t), 130, d) if d >= 0 else dest(along(YANGTZE, t), 310, -d)


def build() -> dict:
    st = Story()
    st.step("approach", "Cao Cao reaches the Yangtze", "Autumn-winter 208",
            """After taking Jingzhou without a fight, Cao Cao's northern army came down the river towards Jiangling and on to the Yangtze, sick and tired from forced marches. Sun Quan and Liu Bei had agreed to stand together. Their fleet and Zhou Yu's troops waited downstream on the south bank, while Cao Cao gathered his fleet of captured Jingzhou ships and his foot and horse near Wulin. The exact stretch of river is argued over, so every position here is a reconstruction.""",
            )
    st.put("b-army", at=P(-3100, 4500), facing=130, width=1500, depth=300, conjectural=True)
    st.put("b-cao", at=P(-3500, 4900), conjectural=True)
    st.put("b-fleet", at=S(0.42, -300), facing=FLOW + 90, width=1400, depth=160, conjectural=True)
    st.put("a-fleet", at=S(0.30, 350), facing=FLOW, width=900, depth=150, conjectural=True)
    st.put("a-army", at=S(0.28, 3000), facing=310, width=900, depth=200, conjectural=True)
    st.put("a-liu", at=S(0.24, 4000), facing=310, width=500, depth=150, conjectural=True)
    st.pin("a-zhou", "a-fleet")

    st.step("skirmish", "The first clash at Red Cliffs", "Early winter 208",
            """The allied fleet sailed upstream from Xiakou or Fankou and met Cao Cao's vanguard at Red Cliffs. The northern troops, sick and demoralised, could not win the small fight. Cao Cao fell back to Wulin on the north bank, and the allies drew back to the south, leaving the river between the two armies.""")
    st.put("b-van", at=S(0.40, 600), facing=130, width=500, depth=120, conjectural=True, state="engaged")
    st.put("a-fleet", at=S(0.38, 300), facing=FLOW + 90, move="attack", state="engaged", conjectural=True)
    st.note(S(0.40, 300), "Vanguard skirmish", "clash")

    st.step("retreat", "Both sides pull back", "Early winter 208",
            """Cao Cao's vanguard withdrew across the river to join the main army at Wulin. The allies returned to their south-bank anchorage. Cao Cao's northerners, mostly horsemen and foot, practised on the water for only a few days. To steady his seasick men he had his ships chained stem to stern, possibly for that reason.""")
    st.put("b-van", at=S(0.40, -1200), move="retreat", state="ready", conjectural=True)
    st.put("a-fleet", at=S(0.30, 350), move="retreat", state="ready", conjectural=True)
    st.put("b-fleet", at=S(0.42, -300), state="ready", conjectural=True)

    st.step("ruse", "Huang Gai's letter", "A night in winter 208",
            """The allied commander Huang Gai wrote to Cao Cao pretending to defect. He loaded several large warships with bundles of kindling, dry reeds and fatty oil. Cao Cao's chained fleet lay at the north bank, a tempting mass of timber. The allied squadron set out as if to surrender, with the south-east wind behind it.""")
    st.put("a-fire", at=S(0.37, 350), facing=310, width=300, depth=60, conjectural=True)
    st.put("a-fire", move="advance", at=S(0.40, 100), facing=310, conjectural=True)

    st.step("fire", "The fire ships strike", "Night, winter 208",
            """At mid-river the crews lit their ships and escaped in small boats. Driven by the south-east wind, the burning hulls ran into Cao Cao's chained fleet and set it alight. The fire spread to the camps on the bank, and many men and horses burned or drowned.""")
    st.put("a-fire", at=S(0.42, -300), facing=310, move="ram", state="engaged", conjectural=True)
    st.put("b-fleet", state="engaged", conjectural=True)
    st.note(S(0.42, -200), "Fleet ablaze", "event")

    st.step("assault", "The allied assault", "Dawn",
            """Zhou Yu led a lightly armed force across behind the fire. Cao Cao's army, thrown into confusion by the blaze, was beaten on the north bank. Seeing the situation was hopeless, Cao Cao ordered a general retreat and had some remaining ships destroyed before he left.""")
    st.put("a-army", at=S(0.40, -900), facing=310, move="attack", state="engaged", conjectural=True)
    st.put("b-army", at=P(-3100, 4300), state="wavering", conjectural=True)
    st.put("b-fleet", state="destroyed", conjectural=True)
    st.put("a-fleet", at=S(0.38, 300), facing=310, move="advance", conjectural=True)

    st.step("rout", "Cao Cao's retreat begins", "Days after the fire",
            """Cao Cao's army withdrew along the Huarong road towards Jiangling. Heavy rain turned the marshes north of Dongting Lake into mud. Sick soldiers carried bundles of grass to fill the track so the horsemen could pass, and many drowned or were trampled. The allies, led by Zhou Yu and Liu Bei, chased by land and water.""")
    st.put("b-army", at=P(-6500, 2000), facing=250, move="rout", state="routed", conjectural=True)
    st.put("b-cao", at=P(-7000, 2000), move="retreat", conjectural=True)
    st.put("a-army", at=P(-4500, 3200), facing=250, move="pursuit", conjectural=True)
    st.put("a-liu", at=P(-4000, 1800), facing=250, move="pursuit", conjectural=True)
    st.note(P(-6800, 1500), "Muddy Huarong road", "event")

    st.step("escape", "Cao Cao escapes", "Winter 208-209",
            """Hunger and disease finished much of what the chase left. Cao Cao got through Huarong Pass and then retreated north to Ye. He left Cao Ren and Xu Huang at Jiangling, Yue Jin at Xiangyang and Man Chong at Dangyang. Cao Cao later blamed sickness rather than Zhou Yu for the loss.""")
    st.put("b-cao", at=P(-9500, 3000), move="retreat", conjectural=True)
    st.put("b-army", at=P(-9000, 2500), move="retreat", state="wavering", conjectural=True)
    st.put("a-army", at=P(-5500, 2800), move="march", state="ready", conjectural=True)

    st.step("aftermath", "A divided Jingzhou", "209-210",
            """Zhou Yu took Jiangling by the end of 209, and Cao Cao's border shrank by some 160 km towards Xiangyang. Liu Qi died within months, and Liu Bei claimed Jingzhou, taking four commanderies south of the Yangtze. Zhou Yu died in 210. The victory fixed the split between north and south and made possible the later Three Kingdoms.""")
    st.put("a-liu", at=P(-4200, 1000), state="ready", conjectural=True)

    return st.doc(slug="battle-of-red-cliffs", kind="battle", entity={"name": "Battle of Red Cliffs", "wikidata": "Q830059"},
        title="Battle of Red Cliffs", date_label="Winter 208 AD", year=208,
        intro="""In the winter of 208 AD, the warlord Cao Cao, master of northern China and the last Han court, marched south down the Yangtze to crush the remaining rivals. He faced an alliance of Sun Quan's forces from the lower Yangtze, Liu Bei, and Liu Qi. After a small clash at Red Cliffs, the two armies faced each other across the river. Cao Cao's fleet of captured ships, chained together to calm seasick northern soldiers, was set on fire by a feigned surrender led by Huang Gai. The fire and a quick assault broke the northern army, which fled through mud and disease. The exact place of the battle is still debated.""",
        outcome="Allied victory. Cao Cao failed to cross the Yangtze, and Liu Bei gained much of Jingzhou.",
        uncertainty="The battle site is disputed among Chibi, Jiayu, Wuhan and Huangzhou; Chibi is used here by convention. All unit positions, river-side placements and routes are reconstructed. Strength figures are claims: 800,000 by Cao Cao, 220,000-240,000 by Zhou Yu's estimate. Casualties are unknown for the allies.",
        sources=[{"title": "Battle of Red Cliffs - Wikipedia", "url": "https://en.wikipedia.org/wiki/Battle_of_Red_Cliffs", "kind": "web"}],
        sides=[
            {"id": "a", "name": "Sun-Liu alliance", "color": "#b91c1c",
             "polity": {"name": "Sun Quan"},
             "commanders": [{"name": "Zhou Yu", "wikidata": "Q198048", "role": "Commander"},
                            {"name": "Liu Bei", "wikidata": "Q245315", "role": "Allied warlord"},
                            {"name": "Zhuge Liang", "wikidata": "Q198211", "role": "Envoy and strategist"},
                            {"name": "Cheng Pu", "wikidata": "Q740441", "role": "General"}],
             "strength": "c. 50,000", "losses": "Unknown"},
            {"id": "b", "name": "Cao Cao's army", "color": "#1d4ed8",
             "polity": {"name": "Cao Cao"},
             "commanders": [{"name": "Cao Cao", "wikidata": "Q204077", "role": "Warlord"}],
             "strength": "220,000-240,000 (Zhou Yu's estimate)", "losses": "Heavy"}],
        units=[
            {"id": "a-fleet", "side": "a", "kind": "warship", "label": "Allied fleet"},
            {"id": "a-fire", "side": "a", "kind": "warship", "label": "Huang Gai's fire ships"},
            {"id": "a-army", "side": "a", "kind": "light_infantry", "label": "Zhou Yu's land force"},
            {"id": "a-liu", "side": "a", "kind": "infantry", "label": "Liu Bei's troops"},
            {"id": "a-zhou", "side": "a", "kind": "commander", "label": "Zhou Yu"},
            {"id": "b-army", "side": "b", "kind": "infantry", "label": "Cao Cao's northern army", "strength": "disputed"},
            {"id": "b-cao", "side": "b", "kind": "commander", "label": "Cao Cao"},
            {"id": "b-fleet", "side": "b", "kind": "warship", "label": "Chained fleet"},
            {"id": "b-van", "side": "b", "kind": "infantry", "label": "Vanguard"}],
        terrain=[
            {"id": "yangtze", "kind": "river", "label": "Yangtze", "line": YANGTZE},
            {"id": "wulin", "kind": "town", "label": "Wulin", "at": list(WULIN)},
            {"id": "chibi", "kind": "town", "label": "Chibi (Red Cliffs)", "at": list(CHIBI)},
            {"id": "huarong", "kind": "road", "label": "Huarong road", "conjectural": True,
             "line": [P(-4500, 2500), P(-6500, 2000), P(-9500, 3000)]},
            {"id": "marsh", "kind": "marsh", "label": "Marsh", "conjectural": True,
             "area": [P(-8000, 1000), P(-5500, 800), P(-5500, 3000), P(-8000, 3200)]},
            {"id": "south-hills", "kind": "hill", "label": "South bank hills", "conjectural": True,
             "area": [P(-1200, -800), P(1200, -800), P(1200, 600), P(-1200, 600)]}])
