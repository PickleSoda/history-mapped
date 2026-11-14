"""Battle of Austerlitz, 2 December 1805 — map story builder.

Anchors: Pratzen peak (Q134114 P625, 16.7625 / 49.1281); villages, Žuráň, Santon and the Goldbach (Říčka) and
Bosenitz (Roketnice) streams from OSM via `places`. Santon's OSM point is doubtful and flagged conjectural.
Orientation: the French stood west of the Goldbach and Pratzen, facing east (bearing ~90); the Allies stood on and
east of the Pratzen, facing west (~270). Allied columns 1-3 attacked south-west across the Goldbach at Telnitz and
Sokolnitz; Soult's IV Corps rose from the dead ground by Puntowitz/Girzikowitz up the Pratzen's western slope;
Lannes and Murat held the north (Olmütz road), Bagration and Liechtenstein faced them from the east.
Sources: Wikipedia Battle of Austerlitz (Battlefield, dispositions, battle sections). Unit positions are reconstructed.
"""
from pipeline.map_stories.geo import ellipse, local
from pipeline.map_stories.layout import Story, local_frame

ANCHOR = (16.7625, 49.12806)
P = local_frame(ANCHOR)


def V(lon, lat):
    e, n = local((lon, lat), ANCHOR)
    return P(e, n)


GOLDBACH = [[16.72042, 49.17495], [16.7376, 49.15134], [16.73611, 49.14711], [16.73019, 49.1441], [16.72897, 49.1171],
            [16.71683, 49.10276], [16.69393, 49.08718], [16.69286, 49.07161]]
BOSENITZ = [[16.75416, 49.19636], [16.7534, 49.19569], [16.7554, 49.19368], [16.75401, 49.18749], [16.75649, 49.18108],
            [16.75374, 49.17908], [16.75308, 49.17668], [16.7563, 49.16923], [16.75583, 49.16696], [16.75301, 49.16438],
            [16.75173, 49.16025], [16.74863, 49.15855], [16.74726, 49.15636], [16.74427, 49.15508], [16.73747, 49.15234]]


def build() -> dict:
    st = Story()

    # ---- step 1
    st.step("trap", "The bait on the Pratzen", "1 December, evening",
        """Napoleon has pulled his troops off the Pratzen Heights and let the Allies see a thin, nervous right wing near the Goldbach villages. Most of his army hides in the dead ground west of the Bosenitz, between Puntowitz and Girzikowitz, while Davout's corps hurries up from Vienna. The Allies, pressed by the Tsar's circle and following Weyrother's plan, camp on and east of the Pratzen, ready to swing south and roll up the French right.""")
    st.put("fr-legrand", at=V(16.7185, 49.1085), facing=90, width=1300, depth=30, state="ready", conjectural=True)
    st.put("fr-st-hilaire", at=V(16.742, 49.1585), facing=90, width=700, depth=60, conjectural=True)
    st.put("fr-vandamme", at=V(16.753, 49.1700), facing=90, width=700, depth=60, conjectural=True)
    st.put("fr-bernadotte", at=V(16.730, 49.1620), facing=90, width=600, depth=70, conjectural=True)
    st.put("fr-murat", at=V(16.744, 49.1790), facing=90, width=900, depth=60, conjectural=True)
    st.put("fr-lannes", at=V(16.757, 49.1850), facing=90, width=800, depth=50, conjectural=True)
    st.put("fr-santon-guns", at=V(16.76388, 49.18854), facing=90, width=120, depth=30, conjectural=True)
    st.put("fr-guard", at=V(16.728, 49.1740), facing=90, width=500, depth=60, conjectural=True)
    st.put("fr-davout", at=V(16.690, 49.060), facing=45, width=120, depth=800, shape="column", frame=False, conjectural=True)
    st.put("fr-napoleon", at=V(16.738, 49.1797), facing=90)
    st.put("al-col1", at=V(16.780, 49.1060), facing=270, width=150, depth=700, shape="column", conjectural=True)
    st.put("al-col2", at=V(16.775, 49.1180), facing=270, width=150, depth=700, shape="column", conjectural=True)
    st.put("al-col3", at=V(16.775, 49.1290), facing=270, width=150, depth=700, shape="column", conjectural=True)
    st.put("al-kienmayer", at=V(16.752, 49.1000), facing=270, width=400, depth=60, conjectural=True)
    st.put("al-col4", at=V(16.766, 49.1340), facing=270, width=900, depth=80, conjectural=True)
    st.put("al-guard", at=V(16.815, 49.1400), facing=270, width=600, depth=70, conjectural=True)
    st.put("al-liechtenstein", at=V(16.805, 49.1650), facing=270, width=800, depth=50, conjectural=True)
    st.put("al-bagration", at=V(16.800, 49.1800), facing=270, width=900, depth=50, conjectural=True)
    st.put("al-kutuzov", at=V(16.764, 49.1330), facing=270)
    st.pin("al-kutuzov", "al-col4")

    # ---- step 2
    st.step("telnitz", "Allied columns strike Telnitz", "c. 08:00",
        """The Allied left wing marches down the Pratzen's southern slopes and hits Telnitz, held by the 3rd Line. Austrian and Russian assaults throw the French out, but the first of Davout's men arrive from the south, retake the village, and are in turn driven off by hussar charges. French guns across the Goldbach hold the Allies in check. The attack comes slower and more tangled than Weyrother intended, since Liechtenstein's cavalry crossing the line delays a column.""")
    st.put("al-col1", at=V(16.7255, 49.1020), facing=270, width=500, depth=70, shape="block", state="engaged", move="attack", conjectural=True)
    st.put("al-kienmayer", at=V(16.7300, 49.0990), facing=270, move="attack", state="engaged", conjectural=True)
    st.put("fr-legrand", at=V(16.7140, 49.1060), facing=90, width=1200, state="engaged", conjectural=True)
    st.put("fr-davout", at=V(16.7080, 49.0930), facing=90, width=500, depth=60, shape="block", move="advance", frame=True, conjectural=True)
    st.put("al-col2", at=V(16.742, 49.1150), facing=270, move="advance", conjectural=True)
    st.put("al-col3", at=V(16.745, 49.1240), facing=270, move="advance", conjectural=True)
    st.note(V(16.7178, 49.1019), "Telnitz changes hands", "clash")

    # ---- step 3
    st.step("sokolnitz", "Sokolnitz, the most contested village", "c. 08:30-10:00",
        """Langeron's column attacks Sokolnitz, defended by the 26th Light and Tirailleurs. Repeated assaults fail until Russian guns bombard the village and drive the garrison out. Przybyszewski's column goes for the castle, the French counterattack and take the place back, and it is lost again before Friant's division of Davout's corps retakes the village. Sokolnitz changes hands several times and soaks up the Allied left wing.""")
    st.put("al-col2", at=V(16.7260, 49.1135), facing=270, width=500, depth=70, shape="block", state="engaged", move="attack", conjectural=True)
    st.put("al-col3", at=V(16.7280, 49.1200), facing=270, width=450, depth=70, shape="block", state="engaged", move="attack", conjectural=True)
    st.put("fr-legrand", at=V(16.7150, 49.1130), facing=90, width=900, state="engaged", conjectural=True)
    st.put("fr-davout", at=V(16.7140, 49.1060), facing=90, state="engaged", move="advance", conjectural=True)
    st.note(V(16.7211, 49.11365), "Sokolnitz: village and castle", "clash")

    # ---- step 4
    st.step("heights-emptied", "The Tsar empties the heights", "c. 08:45",
        """Kutuzov's fourth column stands still on the Pratzen, since he sees that whoever holds the ridge holds the field. Alexander I orders it to leave and follow the other columns south. As the mist thins, Napoleon sees the gap, asks Soult how long his men need to climb, hears 'less than twenty minutes', and about a quarter of an hour later gives the order. He says that one sharp blow will end the war.""")
    st.put("al-col4", at=V(16.7600, 49.1290), facing=225, move="march", conjectural=True)
    st.put("fr-st-hilaire", state="ready")
    st.note(V(16.7625, 49.12806), "Pratzen Heights half abandoned", "event")

    # ---- step 5
    st.step("soult-attack", "Soult goes up the Pratzen", "c. 09:00",
        """St Hilaire's division rises out of the fog on the western slope while the winter sun tears the mist apart. Russian and Austrian troops on top, who had thought the heights safe, are stunned at the sight of French columns. Fighting breaks out as the delayed head of Kutuzov's column is turned back into the line. To the north Vandamme's division strikes the Old Vineyards and breaks several battalions with skirmish fire and volleys.""")
    st.put("fr-st-hilaire", at=V(16.7520, 49.1330), facing=100, move="attack", state="engaged", conjectural=True)
    st.put("fr-vandamme", at=V(16.7610, 49.1480), facing=100, move="attack", state="engaged", conjectural=True)
    st.put("al-col4", at=V(16.7640, 49.1320), facing=270, width=700, state="engaged", move="retreat", conjectural=True)
    st.put("fr-bernadotte", at=V(16.742, 49.1560), facing=90, move="advance", conjectural=True)
    st.note(V(16.7620, 49.1480), "Staré Vinohrady (Old Vineyards)", "clash")

    # ---- step 6
    st.step("heights-fight", "The struggle for the summit", "c. 09:30-11:00",
        """Over an hour of fighting wrecks much of the Allied fourth column under Kutuzov's eye. Inexperienced Austrians from the second column join in and force St Hilaire's veterans down the slope. Desperate, they come on again and clear the heights with the bayonet. Napoleon moves his command post from Žuráň to St Anthony's Chapel on the Pratzen. Bernadotte's corps goes in on Vandamme's left.""")
    st.put("fr-st-hilaire", at=V(16.7600, 49.1300), facing=90, move="attack", state="engaged", conjectural=True)
    st.put("al-col4", at=V(16.7700, 49.1330), facing=270, width=600, state="wavering", move="retreat", conjectural=True)
    st.put("fr-vandamme", at=V(16.7640, 49.1440), facing=90, move="advance", state="engaged", conjectural=True)
    st.put("fr-napoleon", at=V(16.7625, 49.1285), move="march", conjectural=True)
    st.note(V(16.7625, 49.1281), "Napoleon's post: St Anthony's Chapel", "event")

    # ---- step 7
    st.step("guard-clash", "The Russian Guard counterattacks", "c. 11:00-13:00",
        """With the centre in danger the Russian Imperial Guard under Grand Duke Constantine counterattacks near Vandamme's sector and defeats a battalion of the 4th Line, which loses the French army's only standard of the day. Napoleon sends in his own Guard cavalry, which crushes its Russian counterpart. Both sides feed in more horsemen until Drouet's division of Bernadotte's corps deploys on the flank and the Guard horse artillery tears into the Russians, who break and are chased.""")
    st.put("al-guard", at=V(16.7760, 49.1440), facing=270, move="attack", state="engaged", conjectural=True)
    st.put("fr-vandamme", at=V(16.7690, 49.1450), facing=90, state="engaged", conjectural=True)
    st.put("fr-guard", at=V(16.7680, 49.1380), facing=90, move="charge", state="engaged", conjectural=True)
    st.put("fr-bernadotte", at=V(16.7700, 49.1530), facing=90, move="advance", state="engaged", conjectural=True)
    st.put("al-kutuzov", state="wounded")
    st.note(V(16.7720, 49.1450), "4th Line loses a standard", "clash")

    # ---- step 8
    st.step("north", "Cavalry and Lannes in the north", "c. 11:00-14:00",
        """North of the Pratzen, Liechtenstein's Austrian cavalry finally arrives and presses Kellermann's light horse, which shelters behind Caffarelli's infantry. Murat then sends in the cuirassier divisions of d'Hautpoul and Nansouty, and a long melee ends in French favour. Lannes's corps goes against Bagration and drives him off the field. Murat, in charge of the sector, rejects a deep pursuit and Napoleon calls it off.""")
    st.put("al-liechtenstein", at=V(16.7640, 49.1700), facing=270, move="attack", state="engaged", conjectural=True)
    st.put("fr-murat", at=V(16.7580, 49.1720), facing=90, move="charge", state="engaged", conjectural=True)
    st.put("fr-lannes", at=V(16.7720, 49.1850), facing=90, move="attack", state="engaged", conjectural=True)
    st.put("al-bagration", at=V(16.8100, 49.1800), facing=270, move="retreat", state="wavering", conjectural=True)

    # ---- step 9
    st.step("south-collapse", "The Allied left is taken from behind", "c. 14:00-16:00",
        """Napoleon turns south. St Hilaire's division, joined by part of Davout's corps, strikes Sokolnitz from two directions, and the cut-off commanders Kienmayer and Langeron pull out. The sources say Buxhoeveden fled drunk, though this charge comes from hostile accounts. Kienmayer covers the withdrawal with O'Reilly's light cavalry, which beats five of six French regiments before falling back. General panic spreads and the Allied army leaves the field in every direction.""")
    st.put("fr-st-hilaire", at=V(16.7300, 49.1180), facing=225, move="attack", state="engaged", conjectural=True)
    st.put("fr-legrand", at=V(16.7170, 49.1100), facing=90, state="engaged", conjectural=True)
    st.put("al-col2", at=V(16.7330, 49.1120), facing=270, state="routed", move="rout", conjectural=True)
    st.put("al-col3", at=V(16.7380, 49.1160), facing=270, state="routed", move="rout", conjectural=True)
    st.put("al-col1", at=V(16.7390, 49.0960), facing=270, state="wavering", move="retreat", conjectural=True)
    st.put("al-kienmayer", at=V(16.7420, 49.0960), facing=90, state="engaged", move="charge", conjectural=True)
    st.put("al-col4", state="routed", at=V(16.8000, 49.1330), move="rout", conjectural=True)

    # ---- step 10
    st.step("satschan", "Retreat to the Satschan ponds", "late afternoon",
        """Part of the beaten Allied left retreats south over the frozen Satschan ponds. Napoleon's account says artillery on the Augezd heights smashed the ice and drowned thousands of men and dozens of guns. Local evidence later suggested that when the ponds were drained days afterwards, only a few corpses and about 150 horses were found, so the scale is disputed. Dokhturov keeps his men together and they rally near Neudorf by nightfall, after heavy losses.""")
    st.put("al-col1", at=V(16.7220, 49.0800), facing=180, state="routed", move="retreat", conjectural=True)
    st.put("fr-davout", at=V(16.7300, 49.1040), facing=135, state="ready", move="pursuit", conjectural=True)
    st.note(V(16.7270, 49.0920), "Ice and the ponds: scale of losses disputed", "event", conjectural=True)

    # ---- step 11
    st.step("aftermath", "Three emperors, one winner", "2-26 December",
        """The Allies lose around 36,000 of 89,000 men and 186 guns, the French around 9,000 of 66,000. France and Austria agree a truce on 4 December and sign the Treaty of Pressburg 22 days later. Austria pays 40 million francs and gives up land. Russian forces withdraw home. The Holy Roman Empire is wound up the following year, Napoleon builds the Confederation of the Rhine, and Prussia, feeling slighted, goes to war with him in 1806.""")
    st.put("fr-napoleon", at=V(16.7625, 49.1285))

    sides = [
        {"id": "fr", "name": "French Empire", "color": "#1d4ed8",
         "polity": {"name": "First French Empire"},
         "commanders": [{"name": "Napoleon", "wikidata": "Q517", "role": "Emperor and commander"},
                        {"name": "Jean-de-Dieu Soult", "wikidata": "Q296023", "role": "IV Corps"},
                        {"name": "Louis-Nicolas Davout", "wikidata": "Q158778", "role": "III Corps"},
                        {"name": "Jean Lannes", "wikidata": "Q273032", "role": "V Corps"},
                        {"name": "Joachim Murat", "wikidata": "Q151173", "role": "Cavalry Reserve"}],
         "strength": "65,000-75,000", "losses": "8,569-9,288 (about 1,300-1,500 dead)"},
        {"id": "al", "name": "Russo-Austrian Allies", "color": "#b91c1c",
         "polity": {"name": "Russian Empire", "wikidata": "Q34266"},
         "commanders": [{"name": "Alexander I of Russia", "wikidata": "Q15193", "role": "Tsar"},
                        {"name": "Mikhail Kutuzov", "wikidata": "Q185801", "role": "Allied commander-in-chief (nominal)"},
                        {"name": "Franz von Weyrother", "wikidata": "Q689584", "role": "Chief of staff, author of the plan"},
                        {"name": "Pyotr Bagration", "wikidata": "Q239260", "role": "Allied right"},
                        {"name": "Friedrich Wilhelm von Buxhoeveden", "wikidata": "Q700437", "role": "Allied left"}],
         "strength": "73,000-89,000", "losses": "27,000-36,000, 186 guns, 45 standards"},
    ]
    units = [
        {"id": "fr-legrand", "side": "fr", "kind": "infantry", "label": "Legrand's division", "strength": "c. 5,000 at dawn"},
        {"id": "fr-davout", "side": "fr", "kind": "infantry", "label": "Davout's III Corps (arriving)", "strength": "c. 7,500 more"},
        {"id": "fr-st-hilaire", "side": "fr", "kind": "infantry", "label": "St Hilaire (IV Corps)"},
        {"id": "fr-vandamme", "side": "fr", "kind": "infantry", "label": "Vandamme (IV Corps)"},
        {"id": "fr-bernadotte", "side": "fr", "kind": "infantry", "label": "Bernadotte's I Corps"},
        {"id": "fr-murat", "side": "fr", "kind": "heavy_cavalry", "label": "Murat's cavalry"},
        {"id": "fr-lannes", "side": "fr", "kind": "infantry", "label": "Lannes's V Corps"},
        {"id": "fr-santon-guns", "side": "fr", "kind": "artillery", "label": "Santon battery", "strength": "18 guns"},
        {"id": "fr-guard", "side": "fr", "kind": "heavy_cavalry", "label": "Imperial Guard"},
        {"id": "fr-napoleon", "side": "fr", "kind": "commander", "label": "Napoleon"},
        {"id": "al-col1", "side": "al", "kind": "infantry", "label": "1st column (Dokhturov)"},
        {"id": "al-col2", "side": "al", "kind": "infantry", "label": "2nd column (Langeron)"},
        {"id": "al-col3", "side": "al", "kind": "infantry", "label": "3rd column (Przybyszewski)"},
        {"id": "al-kienmayer", "side": "al", "kind": "light_cavalry", "label": "Kienmayer's advance guard"},
        {"id": "al-col4", "side": "al", "kind": "infantry", "label": "4th column (Kolowrat)"},
        {"id": "al-guard", "side": "al", "kind": "heavy_cavalry", "label": "Russian Imperial Guard"},
        {"id": "al-liechtenstein", "side": "al", "kind": "heavy_cavalry", "label": "Liechtenstein's cavalry"},
        {"id": "al-bagration", "side": "al", "kind": "infantry", "label": "Bagration's right"},
        {"id": "al-kutuzov", "side": "al", "kind": "commander", "label": "Kutuzov"},
    ]
    terrain = [
        {"id": "goldbach", "kind": "stream", "label": "Goldbach (Říčka)", "line": GOLDBACH},
        {"id": "bosenitz", "kind": "stream", "label": "Bosenitz (Roketnice)", "line": BOSENITZ},
        {"id": "pratzen", "kind": "hill", "label": "Pratzen Heights", "area": ellipse(P(-200, 900), 1600, 1700, 0)},
        {"id": "zuran", "kind": "hill", "label": "Žuráň", "area": ellipse(V(16.73842, 49.17976), 500, 350)},
        {"id": "santon", "kind": "hill", "label": "Santon", "area": ellipse(V(16.76388, 49.18854), 350, 300), "conjectural": True},
        {"id": "telnitz", "kind": "village", "label": "Telnitz", "at": V(16.71779, 49.10192)},
        {"id": "sokolnitz", "kind": "village", "label": "Sokolnitz", "at": V(16.7211, 49.11365)},
        {"id": "kobelnitz", "kind": "village", "label": "Kobelnitz", "at": V(16.73182, 49.13803)},
        {"id": "puntowitz", "kind": "village", "label": "Puntowitz", "at": V(16.74229, 49.15216)},
        {"id": "girzikowitz", "kind": "village", "label": "Girzikowitz", "at": V(16.7585, 49.16713)},
        {"id": "aujezd", "kind": "village", "label": "Augezd", "at": V(16.75737, 49.10435)},
        {"id": "krenowitz", "kind": "village", "label": "Krenowitz", "at": V(16.82932, 49.14216)},
        {"id": "olmutz-road", "kind": "road", "label": "Olmütz-Brünn road", "conjectural": True,
         "line": [[16.8175, 49.1734], [16.77, 49.1760], [16.74, 49.1790], [16.7131, 49.1790]]},
    ]
    return st.doc(slug="battle-of-austerlitz", kind="battle", entity={"name": "Battle of Austerlitz", "wikidata": "Q134114"},
        title="Battle of Austerlitz", date_label="2 December 1805", year=1805,
        intro="""On 2 December 1805 Napoleon's army met the combined Russian and Austrian forces on a low plateau and its streams about ten kilometres south-east of Brno, in present-day Czechia. The French emperor had deliberately given up the commanding Pratzen Heights and weakened his right wing to tempt the Allies into a flank march. When the Allies sent most of their strength south toward the Goldbach villages, Soult's corps rose out of the fog, took the abandoned heights, and split the Allied army in two. Davout's marching corps held the south long enough, and Murat and Lannes held the north. By dusk the Allies had lost around a third of their men, and Austria soon left the Third Coalition.""",
        outcome="French victory; Austria leaves the war at the Treaty of Pressburg and the Holy Roman Empire is dissolved in 1806.",
        uncertainty="""Unit positions, march routes and timings are reconstructed from the general narrative of the battle, not from surveyed orders of battle, so they are marked conjectural. The OSM point for Santon is doubtful. Strengths and losses vary between sources. The mass drowning in the Satschan ponds is disputed, since drained ponds showed far fewer bodies than Napoleon claimed. The charge that Buxhoeveden was drunk comes from hostile accounts and is not verified.""",
        sources=[{"title": "Battle of Austerlitz - Wikipedia", "url": "https://en.wikipedia.org/wiki/Battle_of_Austerlitz", "kind": "web"}],
        sides=sides, units=units, terrain=terrain)
