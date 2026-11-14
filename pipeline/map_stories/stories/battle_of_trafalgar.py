"""Battle of Trafalgar, 21 October 1805 — map story builder.

Anchors: ANCHOR is the Wikidata P625 point of the battle, about 17 km NW of Cabo de Trafalgar
(places: -6.034, 36.182); Conil, Cabo Roche, Barbate and Cadiz from `places`.
Orientation (Wikipedia, Battle/Commencement): the Franco-Spanish line was a ragged curve heading
north, so its van is in the north and its rear in the south; the British came from the west in two
columns, the northern (windward) one under Nelson at the centre and van, the southern (leeward)
one under Collingwood at the rear. Order inside the line is conjectural: Trinidad, Bucentaure,
Redoutable, Santa Ana from north to south. Distances and ship spacing are conjectural throughout.
Sources: Battle of Trafalgar - Wikipedia (Nelson's plan, Fleets, Battle sections).
"""
from pipeline.map_stories.geo import offset
from pipeline.map_stories.layout import Story, local_frame

ANCHOR = (-6.2, 36.25)
P = local_frame(ANCHOR)

TERRAIN = [
    {"id": "cape-trafalgar", "kind": "label", "label": "Cabo de Trafalgar", "at": [-6.03413, 36.18163]},
    {"id": "conil", "kind": "village", "label": "Conil de la Frontera", "at": [-6.08819, 36.27705]},
    {"id": "cabo-roche", "kind": "label", "label": "Cabo Roche", "at": [-6.12905, 36.30546]},
    {"id": "barbate", "kind": "town", "label": "Barbate", "at": [-5.91928, 36.19240]},
    {"id": "vejer", "kind": "town", "label": "Vejer de la Frontera", "at": [-5.96705, 36.25194]},
]


def ship(st, uid, at, facing, **kw):
    st.put(uid, at=at, facing=facing, width=70, depth=18, shape="block", conjectural=True, **kw)


def build() -> dict:
    st = Story()

    st.step("approach", "Two columns against one line", "Dawn to c. 11:00",
        """The Franco-Spanish fleet had left Cadiz and was strung out in a ragged curve heading north, with its van far ahead of its rear.
        Nelson's twenty-seven ships came up from the west already arranged in two columns, as he had briefed his captains over dinner. He led the northern, windward column in Victory. Collingwood led the southern, leeward one in Royal Sovereign. Nelson intended to hit the line at right angles, split it, and force a close melee in which his better-drilled gunners would tell. Villeneuve guessed something like this was coming, but kept a single line because he doubted his officers could manage more.""")
    st.put("allied-van", at=P(300, 3800), facing=270, width=2500, depth=120, shape="line", conjectural=True)
    ship(st, "trinidad", P(0, 900), 270)
    ship(st, "bucentaure", P(0, 350), 270)
    ship(st, "redoutable", P(0, -150), 270)
    ship(st, "santa-ana", P(0, -1800), 270)
    st.put("allied-rear", at=P(-300, -4000), facing=270, width=2800, depth=120, shape="line", conjectural=True)
    st.put("weather-column", at=P(-10800, 1700), facing=90, width=120, depth=2600, shape="column", conjectural=True)
    ship(st, "victory", P(-9100, 1700), 90)
    st.put("lee-column", at=P(-10800, -3000), facing=90, width=120, depth=2600, shape="column", conjectural=True)
    ship(st, "royal-sovereign", P(-9100, -3000), 90)
    ship(st, "temeraire", P(-9900, 1700), 90)
    ship(st, "belleisle", P(-9900, -3000), 90)

    st.step("feint", "England expects", "c. 11:45",
        """Light winds meant the British crawled in. Nelson ran up his signal that England expected every man to do his duty, then followed it with the order for close action. His column made a feint toward the allied van before swinging at the real target, the centre near Bucentaure. Collingwood nudged his heading so that the two columns would converge on the line together. For the leading ships the price of this plan was already being paid, because they would have to absorb the allied broadsides for a long stretch before their own guns could answer.""")
    st.put("victory", at=P(-5200, 2500), move="feint")
    st.put("temeraire", at=P(-6000, 2500), move="advance")
    st.put("weather-column", at=P(-8000, 2500), move="advance")
    st.put("royal-sovereign", at=P(-5200, -2500), move="advance")
    st.put("belleisle", at=P(-6000, -2600), move="advance")
    st.put("lee-column", at=P(-8000, -2600), move="advance")
    st.note(P(-7200, 3200), "11:45 signal: England expects", "label")

    st.step("first-shots", "Royal Sovereign outruns the fleet", "c. 12:00",
        """At noon Villeneuve signalled the allied ships to engage and Fougueux fired the first ranging shot at Royal Sovereign. Collingwood's flagship, with a freshly cleaned bottom, had pulled well ahead of the rest of her column. She now came under fire from four allied ships at once. Victory, meanwhile, was swinging back from the feint toward the line, and for some forty minutes she was battered by Heros, Santisima Trinidad, Redoutable and Neptune before she could fire a shot. Her wheel was shot away, so she had to be steered by tiller from below decks.""")
    st.put("royal-sovereign", at=P(-1600, -1850), facing=90, move="attack")
    st.put("victory", at=P(-3000, 1100), facing=90, move="advance")
    st.put("temeraire", at=P(-3800, 1100), move="advance")
    st.put("weather-column", at=P(-6400, 1300), move="advance")
    st.put("belleisle", at=P(-3700, -2500), move="advance")
    st.put("lee-column", at=P(-5600, -2400), move="advance")
    st.note(P(-1600, -1300), "Fougueux fires first shot", "event")

    st.step("collingwood-breaks", "The leeward column cuts the rear", "Shortly after noon",
        """Royal Sovereign broke the allied line just astern of the Spanish flagship Santa Ana, firing a double-shotted raking broadside into her stern as she passed. Seeing it, Nelson remarked how nobly Collingwood was taking his ship in. Behind her, Belleisle was jumped by Aigle, Achille, Neptune and Fougueux. She was dismasted and could barely fight, her fallen sails blinding her own batteries, yet she kept her flag flying for three quarters of an hour until the following ships reached her. The fight in the rear was now a crowd of single-ship duels, exactly what the British wanted.""")
    st.put("royal-sovereign", at=P(-80, -1950), state="engaged", move="attack")
    st.put("santa-ana", state="engaged")
    st.put("belleisle", at=P(-900, -2700), state="wavering", move="advance")
    st.put("allied-rear", state="engaged")
    st.put("lee-column", at=P(-3400, -2700), move="advance")
    st.note(P(-900, -3300), "Belleisle dismasted, fights on", "event")

    st.step("victory-breaks", "Victory cuts the centre", "12:45",
        """At a quarter to one Victory came through the line between Bucentaure and Redoutable. Her guns were loaded with multiple shot and her big carronade with hundreds of musket balls, and she fired a raking broadside through the French flagship's stern. Several hundred of Bucentaure's men were killed or wounded, and she lost her masts. Villeneuve expected to be boarded and held up the ship's eagle, ready to hurl it across. Victory instead turned on Redoutable, and the stricken flagship was left for Temeraire, Neptune, Conqueror and Leviathan to deal with. Allied ships ahead of the break could no longer read their leader's signals.""")
    st.put("victory", at=P(-60, 100), state="engaged", move="attack")
    st.put("bucentaure", state="wavering")
    st.put("redoutable", state="engaged")
    st.put("temeraire", at=P(-1500, 500), move="advance")
    st.put("weather-column", at=P(-4200, 900), move="advance")
    st.note(P(-700, 700), "Raking broadside into Bucentaure", "clash")

    st.step("nelson-falls", "Locked with Redoutable", "c. 13:15",
        """Victory's masts locked with those of Redoutable, whose crew included a strong body of soldiers who gathered to board. A musket ball fired from Redoutable's mizzen top struck Nelson in the shoulder and travelled through his spine. He was carried below and said that they had succeeded and he was dead. Victory's gunners were called up to fight boarders and the ship stopped firing, until French grenades drove them down again. As Redoutable's men prepared to board, Temeraire came up on her starboard bow and swept the exposed French crowd with a carronade.""")
    st.put("victory", at=P(-45, -90), state="engaged")
    st.put("redoutable", state="engaged")
    st.put("temeraire", at=P(-120, -380), facing=30, state="engaged", move="attack")
    st.put("weather-column", at=P(-3000, 400), move="advance")
    st.note(P(-300, -30), "Nelson shot from Redoutable's top", "death")

    st.step("redoutable-yields", "The centre is overwhelmed", "13:55 onward",
        """At five to two Redoutable's captain, Lucas, himself badly wounded, surrendered with only 99 fit men left of 643. Bucentaure was cut off by Victory and Temeraire and then worked over by Neptune, Leviathan and Conqueror. Santisima Trinidad, the largest ship afloat, was isolated and beaten down, and gave up after about three hours. Further south the same thing was happening around Santa Ana. As more British ships arrived, the allied centre and rear were ground down one ship at a time, while the allied van stood by with little effect.""")
    st.put("redoutable", state="captured", by="gb")
    st.put("bucentaure", state="captured", by="gb")
    st.put("trinidad", state="captured", by="gb")
    st.put("santa-ana", state="captured", by="gb")
    st.put("allied-rear", state="wavering")
    st.put("victory", state="ready")
    st.put("temeraire", state="ready")
    st.put("royal-sovereign", state="ready")

    st.step("van-leaves", "Dumanoir sails away", "Late afternoon, 21 October",
        """Rear-Admiral Dumanoir, whose van had hardly been engaged, tried to come back to help the collapsing centre. He could not fight his way through and broke off with four ships, Formidable, Scipion, Duguay-Trouin and Mont Blanc. He first steered for the Straits of Gibraltar, later changed course, and was caught and captured on 4 November at Cape Ortegal. Gravina was wounded and handed on the survivors, and only eleven allied ships reached Cadiz. Nelson died at half past four, three hours after being hit, having first ordered the fleet to anchor because a storm was expected. The British took twenty ships and lost none.""")
    st.put("allied-van", at=P(5200, 2400), facing=90, width=900, depth=120, move="retreat", label="Dumanoir's four ships")
    st.put("allied-rear", state="routed")
    st.note(P(500, 600), "Nelson dies, c. 16:30", "death")
    st.note(P(5200, 3400), "Van bound for the Straits", "label")

    st.step("storm", "The storm", "22 October",
        """The gale Nelson had foreseen arrived as the fleets, scattered and crippled, were still near the coast. Many damaged ships sank, ran aground on the shoals or were wrecked. Achille had already exploded, Redoutable sank, and the British scuttled Santisima Trinidad and Argonauta. Intrepide and San Agustin burned, while Aigle, Berwick, Fougueux and Monarca were wrecked in the gale. Some prizes were retaken, either by their own prisoners rising against the small British prize crews or by ships coming out from Cadiz. Collingwood's captains fought to keep their own battered ships and their prizes off the lee shore.""")
    st.put("bucentaure", state="sunk")
    st.put("redoutable", state="sunk")
    st.put("trinidad", state="sunk")
    st.put("lee-column", at=P(-4000, -3800), state="wavering")
    st.put("weather-column", at=P(-3500, 800), state="wavering")

    st.step("sortie", "The sortie from Cadiz", "23 October",
        """With Gravina badly wounded, Commodore Cosmao took charge in Cadiz. From the harbour the allied officers could see the prizes scattered to leeward, and a rescue seemed possible. Pluton, Neptune, Indomptable, the Spanish Rayo and San Francisco de Asis, five frigates and two brigs sailed out. The wind veered west-southwest and raised a heavy sea, and many prizes broke their tow lines. Collingwood told his best ships to cast off their prizes and formed a line of ten by three o'clock. The allied squadron would not close, but in the confusion French frigates retook Santa Ana and Neptuno, whose Spanish crews rose against their prize crews.""")
    st.put("sortie", at=P(-6500, 9500), facing=190, width=1800, depth=120, shape="line", conjectural=True, label="Cosmao's sortie from Cadiz")
    st.put("british-line", at=P(-5000, 4000), facing=0, width=3000, depth=120, shape="line", conjectural=True, label="Collingwood's line of ten")
    st.put("santa-ana", at=P(-4000, -3500), state="ready", facing=0, move="retreat")
    st.note(P(-4000, -2900), "Santa Ana retaken by French frigates", "event")

    return st.doc(
        slug="battle-of-trafalgar", kind="naval_battle", schema=3,
        entity={"name": "Battle of Trafalgar", "wikidata": "Q171416"},
        title="Battle of Trafalgar", date_label="21 October 1805", year=1805,
        intro="""On 21 October 1805, off the Atlantic coast of Spain west of Cadiz and near Cape Trafalgar, a British fleet of twenty-seven ships of the line under Lord Nelson met thirty-three French and Spanish ships under Admiral Villeneuve. The allies had sailed out of Cadiz and were strung out in one long, ragged line. Nelson broke with the usual practice of sailing parallel and exchanging broadsides. He sent two columns straight at the line at right angles, accepting heavy fire on the approach in exchange for a close melee in which his crews' gunnery and seamanship would count. The plan worked. Nelson was shot in the middle of the fight and died that afternoon, but the British took twenty ships and lost none. The result ended any serious French hope of challenging British command of the sea.""",
        outcome="British victory: Nelson's two columns split the Franco-Spanish line, and the British took twenty ships and lost none, though Nelson was killed.",
        uncertainty="""Exact ship positions, spacing and the order of ships in the allied line are reconstructed (all marked conjectural), as the light wind and smoke make any minute-by-minute plot approximate. Times are those given by the main account, which cites about 12:00, 12:45, 13:55 and 16:30, and the others here are rounded. Fleet blocks stand for groups whose full composition is not shown. The Cadiz sortie and the British line of ten are placed approximately. The wreck and sinking events of the storm are drawn as a general outcome, not ship by ship.""",
        sources=[{"title": "Battle of Trafalgar - Wikipedia", "url": "https://en.wikipedia.org/wiki/Battle_of_Trafalgar", "kind": "web"}],
        sides=[
            {"id": "gb", "name": "Britain", "color": "#b91c1c", "polity": {"name": "United Kingdom of Great Britain and Ireland", "wikidata": "Q174193"},
             "commanders": [{"name": "Horatio Nelson", "wikidata": "Q83235", "role": "commander-in-chief, killed"},
                            {"name": "Cuthbert Collingwood", "wikidata": "Q335267", "role": "second in command, leeward column"}],
             "strength": "27 ships of the line, 4 frigates, 1 schooner, 1 cutter", "losses": "458 killed, 1,208 wounded"},
            {"id": "fs", "name": "France and Spain", "color": "#1e40af", "polity": {"name": "First French Empire", "wikidata": "Q71084"},
             "contingents": [{"id": "spain", "name": "Spain", "polity": {"name": "Kingdom of Spain", "wikidata": "Q3399982"}}],
             "commanders": [{"name": "Pierre-Charles Villeneuve", "wikidata": "Q315255", "role": "combined fleet commander"},
                            {"name": "Federico Gravina", "wikidata": "Q602054", "role": "Spanish admiral, mortally wounded"}],
             "strength": "33 ships of the line, 5 frigates, 2 brigs", "losses": "4,395 killed, 2,541 wounded, 7,000-8,000 captured; 17 ships of the line captured, 1 destroyed"},
        ],
        units=[
            {"id": "weather-column", "side": "gb", "kind": "fleet", "label": "Nelson column"},
            {"id": "lee-column", "side": "gb", "kind": "fleet", "label": "Collingwood column"},
            {"id": "victory", "side": "gb", "kind": "warship", "label": "Victory"},
            {"id": "royal-sovereign", "side": "gb", "kind": "warship", "label": "Royal Sovereign"},
            {"id": "temeraire", "side": "gb", "kind": "warship", "label": "Temeraire"},
            {"id": "belleisle", "side": "gb", "kind": "warship", "label": "Belleisle"},
            {"id": "british-line", "side": "gb", "kind": "fleet", "label": "Collingwood's line of ten"},
            {"id": "allied-van", "side": "fs", "kind": "fleet", "label": "Allied van (Dumanoir)"},
            {"id": "trinidad", "side": "fs", "kind": "warship", "label": "Trinidad", "strength": "130 guns"},
            {"id": "bucentaure", "side": "fs", "kind": "warship", "label": "Bucentaure"},
            {"id": "redoutable", "side": "fs", "kind": "warship", "label": "Redoutable", "strength": "74 guns"},
            {"id": "santa-ana", "side": "fs", "kind": "warship", "label": "Santa Ana", "strength": "112 guns"},
            {"id": "allied-rear", "side": "fs", "kind": "fleet", "label": "Allied rear"},
            {"id": "sortie", "side": "fs", "kind": "fleet", "label": "Cadiz sortie squadron"},
        ],
        terrain=TERRAIN,
    )
