"""Battle of Manzikert, 26 August 1071 - map story builder.

Anchors: Malazgirt town (OSM, 42.54095 39.14614) as Manzikert; Ahlat (OSM) for Khliat; Murat Nehri line from places.
Orientation (conjectural, sources give no compass): Byzantines advanced from Manzikert eastwards, facing 90; the
Seljuk crescent stood about 4 km east among the hills facing 270; Alp Arslan's camp further east. Byzantine left
(Bryennios) is north, right (Alyates) south, Doukas' reserve behind (west). Sources: Wikipedia, Battle of Manzikert.
"""
from pipeline.map_stories.geo import ellipse
from pipeline.map_stories.layout import Story, ent, local_frame

ANCHOR = (42.54095, 39.14614)
P = local_frame(ANCHOR)
MURAT = [[42.5232, 39.22864], [42.527, 39.22248], [42.52404, 39.21836], [42.52877, 39.21716], [42.53036, 39.21503], [42.53002, 39.20629], [42.52623, 39.20325], [42.52016, 39.20164], [42.51773, 39.19257], [42.52479, 39.17938], [42.52409, 39.17606], [42.51849, 39.17423], [42.5181, 39.1712], [42.52413, 39.1613], [42.51498, 39.15615], [42.5083, 39.15498], [42.50118, 39.15733], [42.49229, 39.16758], [42.47722, 39.1663], [42.46911, 39.16284]]


def build() -> dict:
    st = Story()
    # 1 approach
    st.step("march", "The army splits on the march", "June to 22 August 1071", """
        Romanos marched his composite army across Anatolia, resting at Sebasteia and reaching Theodosiopolis in June.
        Believing Alp Arslan was far off, he turned towards Lake Van to retake Manzikert and the fortress of Khliat.
        Near the end he divided his force: Joseph Tarchaniotes took part of the regulars, the Varangians and the
        Pecheneg and Frankish mercenaries towards Khliat, while the emperor went on to Manzikert. What became of
        Tarchaniotes is unclear, but he never rejoined the field army, which was left far smaller than planned.""")
    st.put("byz-army", at=P(-9000, 0), facing=90, width=900, depth=500, shape="block", label="Byzantine main army")
    st.put("tarchaniotes", at=P(-3500, -6000), facing=135, width=500, depth=250, label="Tarchaniotes' detachment", frame=False, conjectural=True)
    st.put("seljuk-host", at=P(5500, 1500), facing=270, width=1200, depth=500, label="Seljuk host (hidden)", conjectural=True)
    st.step("manzikert", "Manzikert taken, 23 August", "23 August", """
        Romanos reached Manzikert and took it with little trouble. Alp Arslan, who had been in the area all along with
        allied horse and Kurdish contingents from the Marwanid emir, knew exactly where the Byzantines were, while
        the emperor had no idea where the Sultan was. Seljuk horse archers began harassing the camp at once, a first
        sign of how the fighting would go.""")
    st.put("byz-army", at=P(-400, 0), move="advance", width=1500, depth=600)
    st.put("tarchaniotes", at=P(210, -6945), move="march", conjectural=True)
    st.put("seljuk-host", at=P(4200, 1000), move="advance")
    st.step("foragers", "Foragers meet the Seljuk army", "24 August", """
        Foraging parties under Nikephoros Bryennios ran into the main Seljuk force and fell back on Manzikert.
        Romanos doubted it was the Sultan's whole army and sent the Armenian general Basilakes with cavalry; they
        were routed and Basilakes was captured. The emperor then drew up his men and sent Bryennios' left wing out,
        and it was nearly surrounded by the fast Turkish horsemen before it withdrew. At night the Seljuks vanished
        into the hills, leaving no target for a counter-attack.""")
    st.put("byz-cav", at=P(300, 600), facing=90, width=500, depth=60, label="Basilakes' cavalry", conjectural=True)
    st.put("seljuk-skirm", at=P(2400, 900), facing=270, width=1200, depth=60, label="Seljuk horse archers", conjectural=True)
    st.put("byz-cav", at=P(2000, 900), move="attack", state="engaged")
    st.put("seljuk-skirm", state="engaged")
    st.note(P(2200, 900), "Basilakes captured", "capture", conjectural=True)
    st.step("desertion", "Desertions and a refused peace", "25 August", """
        Some of the Turkic mercenaries met their Seljuk kinsmen and went over to them. An envoy came with peace
        terms, but Romanos refused: he wanted a decisive victory over the Turks to settle the eastern frontier,
        and he knew a second army would be hard and costly to raise. He tried to recall Tarchaniotes, who was by
        then out of reach. No fighting took place that day.""")
    st.hide("byz-cav")
    st.hide("seljuk-skirm")
    st.put("byz-army", at=P(-400, 0))
    st.step("deploy", "The two lines form up", "26 August, morning", """
        On 26 August the Byzantines formed a full line of battle. Bryennios held the left wing, Theodore Alyates
        the right and the emperor the centre. Andronikos Doukas commanded the reserve in the rear, a placing that
        later looked reckless given the Doukas family's rivalry with Romanos. About four kilometres off, the
        Seljuks waited in a crescent. All placements here are reconstructed, since the sources give no compass
        bearings.""")
    st.hide("byz-army")
    st.hide("seljuk-host")
    st.put("byz-left", at=P(300, 1150), facing=90, width=1100, depth=120, label="Left wing (Bryennios)", strength_n=5000)
    st.put("byz-centre", at=P(300, 0), facing=90, width=1100, depth=140, label="Centre (Romanos)", strength_n=6000)
    st.put("byz-right", at=P(300, -1150), facing=90, width=1100, depth=120, label="Right wing (Alyates)", strength_n=5000)
    st.put("byz-reserve", at=P(-700, 0), facing=90, width=1600, depth=120, label="Reserve (Doukas)", strength_n=4000)
    st.put("varangians", at=P(100, -250), facing=90, width=250, depth=60, label="Varangian Guard", conjectural=True)
    st.put("seljuk-centre", at=P(4100, 0), facing=270, width=1400, depth=100, shape="crescent", label="Seljuk centre", conjectural=True)
    st.put("seljuk-left", at=P(3700, 1900), facing=250, width=1500, depth=100, label="Seljuk wing (north)", conjectural=True)
    st.put("seljuk-right", at=P(3700, -1900), facing=290, width=1500, depth=100, label="Seljuk wing (south)", conjectural=True)
    st.put("seljuk-camp", at=P(8000, 300), label="Alp Arslan's camp")
    st.put("romanos", at=P(300, 0)); st.pin("romanos", "byz-centre")
    st.put("alp-arslan", at=P(4100, 0)); st.pin("alp-arslan", "seljuk-centre")
    st.step("advance", "Into the arrows", "26 August, midday", """
        The Byzantines marched towards the Seljuk crescent and horse archers shot at them as they closed. The
        crescent's middle kept drawing back while its wings curled round the flanks. Alp Arslan's men would not
        stand and fight, so each advance only carried the Byzantines further from their camp and deeper into the
        arc of fire. The wings, where the arrows fell thickest, were the first to suffer.""")
    for u, x in (("byz-left", 1800), ("byz-centre", 1800), ("byz-right", 1800)):
        st.put(u, at=P(x, st.at(u)[1] if False else {"byz-left": 1150, "byz-centre": 0, "byz-right": -1150}[u]), move="advance")
    st.put("byz-reserve", at=P(800, 0), move="advance")
    st.put("varangians", at=P(1600, -250), move="advance")
    st.put("seljuk-centre", at=P(5200, 0), move="back_water" if False else "retreat")
    st.put("seljuk-left", at=P(2800, 2100), facing=200, move="flank")
    st.put("seljuk-right", at=P(2800, -2100), facing=340, move="flank")
    st.step("camp", "Alp Arslan's camp is taken", "26 August, afternoon", """
        By late afternoon the Byzantine centre had pushed through to Alp Arslan's camp and captured it. It was an
        empty prize. Along the wings, units that tried to force the Seljuks into a close fight found the enemy
        simply riding off, the old steppe habit of giving way and then shooting from a distance. The line was
        stretched and ragged, and the army had no victory to show for a day of marching.""")
    st.put("byz-centre", at=P(6500, 100), move="advance", state="engaged")
    st.put("varangians", at=P(6300, -100), move="advance")
    st.put("seljuk-camp", state="captured", by="byz")
    st.put("byz-left", at=P(3300, 1400), move="advance", state="engaged")
    st.put("byz-right", at=P(3300, -1400), move="advance", state="engaged")
    st.put("seljuk-centre", at=P(7500, 1200), move="retreat", conjectural=True)
    st.put("seljuk-left", state="engaged"); st.put("seljuk-right", state="engaged")
    st.step("withdraw", "A withdrawal order goes wrong", "26 August, dusk", """
        With nothing gained, Romanos ordered a retreat as evening came. The right wing misread the signal, and
        Andronikos Doukas, who was meant to cover the withdrawal, ignored it and marched back to the camp by
        Manzikert, leaving the emperor's force uncovered. Whether this was treachery or confusion is argued, but
        the army was now in disorder and the Seljuks saw their chance.""")
    st.put("byz-reserve", at=P(-1200, -300), move="retreat", facing=270, label="Reserve leaves the field")
    st.put("byz-centre", at=P(5200, 100), move="retreat", facing=270)
    st.put("varangians", at=P(5000, -100), move="retreat", facing=270)
    st.put("byz-right", at=P(2200, -1100), move="retreat", facing=270, state="wavering")
    st.put("byz-left", at=P(2400, 1100), move="retreat", facing=270)
    st.step("rout", "The wings collapse", "26 August, evening", """
        The Seljuks turned and attacked. The right wing, believing it had been betrayed by the Armenians or the
        Turkish auxiliaries, broke almost at once. Accounts disagree about who fled first: some say the Armenians
        ran, others that Armenian foot stood firm and the Turkish auxiliaries stayed loyal. The left wing under
        Bryennios resisted a little longer, then gave way as well.""")
    st.put("seljuk-centre", at=P(4300, 0), facing=270, move="attack", state="engaged", conjectural=True)
    st.put("seljuk-left", at=P(2200, 1500), facing=250, move="attack")
    st.put("seljuk-right", at=P(2000, -1600), facing=290, move="attack")
    st.put("byz-right", at=P(800, -1500), move="rout", state="routed")
    st.put("byz-left", at=P(900, 1500), move="retreat", state="wavering")
    st.step("encircled", "The emperor is surrounded", "26 August, night", """
        What was left of the centre, including Romanos and the Varangian Guard, was ringed by the Seljuks. The
        Armenian infantry and the emperor's own household troops took the heaviest losses. Romanos was wounded
        and captured. Survivors fled in the dark and were chased through the night but not beyond it, and by dawn
        the professional core of the Byzantine army was destroyed, while many levies under Doukas had already gone.""")
    st.put("seljuk-centre", at=P(4900, 0), state="engaged")
    st.put("seljuk-left", at=P(4600, 900), facing=230, move="flank")
    st.put("seljuk-right", at=P(4600, -900), facing=310, move="flank")
    st.put("byz-centre", at=P(4800, 100), state="engaged", width=500, depth=250)
    st.put("varangians", state="engaged")
    st.put("byz-left", at=P(-400, 1600), move="rout", state="routed")
    st.put("byz-right", state="destroyed")
    st.note(P(4800, 100), "Romanos wounded and captured", "capture")
    st.step("captivity", "The emperor before the Sultan", "27 August and the week after", """
        Romanos was brought before Alp Arslan, who at first could not believe the filthy, bloodied prisoner was the
        Roman emperor. After a symbolic humiliation he was treated kindly. During a week of captivity the two
        agreed terms: Antioch, Edessa, Hierapolis and Manzikert were to be given up, with a ransom of 1.5 million
        gold pieces and 360,000 a year after, plus a marriage alliance. Romanos left with an escort. At home the
        Doukas faction defeated him, deposed and blinded him, and he died soon afterwards.""")
    st.put("seljuk-centre", at=P(5000, 0)); st.put("byz-centre", state="captured", by="sel")
    st.put("byz-centre", state="captured", by="sel")
    return st.doc(slug="battle-of-manzikert", kind="battle", schema=3,
        entity={"name": "Battle of Manzikert", "wikidata": "Q200032"},
        title="Battle of Manzikert", date_label="26 August 1071", year=1071,
        intro=("In August 1071 the Byzantine emperor Romanos IV Diogenes led a large, mixed army to the eastern frontier near Lake Van "
               "to settle the question of Turkic raiding and settlement. He met the Seljuk sultan Alp Arslan at Manzikert, in the highlands "
               "north of the lake. The Byzantine force had been halved by a detachment sent towards Khliat, and its Turkic mercenaries "
               "were wavering. Over several days the Seljuk horse archers refused a pitched fight, drew the Byzantines forward, and on "
               "26 August caught them in a disordered retreat. The emperor was captured and the professional core of the army destroyed."),
        outcome="Seljuk victory: Romanos IV was captured and the Byzantine field army broken, opening Anatolia to Turkic settlement.",
        uncertainty=("Sources disagree on army sizes (Byzantine figures range from about 40,000 to over 200,000) and give no compass "
                     "bearings or exact positions. The directions, the line of advance, the Seljuk crescent and the Seljuk camp are "
                     "reconstructed and marked conjectural. The fate of Tarchaniotes' detachment is unclear, and accounts differ on who fled first."),
        sources=[{"title": "Battle of Manzikert - Wikipedia", "url": "https://en.wikipedia.org/wiki/Battle_of_Manzikert", "kind": "web"}],
        sides=[{"id": "byz", "name": "Byzantine Empire", "color": "#7c3aed", "polity": {"name": "Byzantine Empire", "wikidata": "Q12544"},
                "commanders": [{"name": "Romanos IV Diogenes", "wikidata": "Q41834", "role": "emperor"},
                               {"name": "Nikephoros Bryennios the Elder", "wikidata": "Q1246496", "role": "left wing"},
                               {"name": "Theodore Alyates", "wikidata": "Q7781674", "role": "right wing"},
                               {"name": "Andronikos Doukas", "wikidata": "Q513495", "role": "reserve"}],
                "strength": "c. 40,000 (sources vary widely)", "losses": "2,000-8,000 killed; 4,000 captured; many deserted"},
               {"id": "sel", "name": "Seljuk Empire", "color": "#15803d", "polity": {"name": "Seljuk Empire", "wikidata": "Q3708094"},
                "commanders": [{"name": "Alp Arslan", "wikidata": "Q200193", "role": "sultan"}],
                "strength": "35,000-50,000", "losses": "Unknown"}],
        units=[{"id": "byz-army", "side": "byz", "kind": "army", "label": "Byzantine main army"},
               {"id": "tarchaniotes", "side": "byz", "kind": "army", "label": "Tarchaniotes' detachment"},
               {"id": "byz-cav", "side": "byz", "kind": "cavalry", "label": "Basilakes' cavalry"},
               {"id": "byz-left", "side": "byz", "kind": "heavy_cavalry", "label": "Left wing (Bryennios)", "strength": "c. 5,000"},
               {"id": "byz-centre", "side": "byz", "kind": "heavy_infantry", "label": "Centre (Romanos)", "strength": "c. 6,000"},
               {"id": "byz-right", "side": "byz", "kind": "heavy_infantry", "label": "Right wing (Alyates)", "strength": "c. 5,000"},
               {"id": "byz-reserve", "side": "byz", "kind": "infantry", "label": "Reserve (Doukas)", "strength": "c. 4,000"},
               {"id": "varangians", "side": "byz", "kind": "heavy_infantry", "label": "Varangian Guard"},
               {"id": "romanos", "side": "byz", "kind": "commander", "label": "Romanos IV"},
               {"id": "seljuk-host", "side": "sel", "kind": "army", "label": "Seljuk host (hidden)"},
               {"id": "seljuk-skirm", "side": "sel", "kind": "horse_archers", "label": "Seljuk horse archers"},
               {"id": "seljuk-centre", "side": "sel", "kind": "horse_archers", "label": "Seljuk centre"},
               {"id": "seljuk-left", "side": "sel", "kind": "horse_archers", "label": "Seljuk wing (north)"},
               {"id": "seljuk-right", "side": "sel", "kind": "horse_archers", "label": "Seljuk wing (south)"},
               {"id": "seljuk-camp", "side": "sel", "kind": "camp", "label": "Alp Arslan's camp"},
               {"id": "alp-arslan", "side": "sel", "kind": "commander", "label": "Alp Arslan"}],
        terrain=[{"id": "murat", "kind": "river", "label": "Murat river", "line": MURAT},
                 {"id": "manzikert", "kind": "town", "label": "Manzikert", "at": list(ANCHOR)},
                 {"id": "khliat", "kind": "town", "label": "Khliat (Ahlat)", "at": list(P(210, -6945))},
                 {"id": "hills", "kind": "hill", "label": "Hills east of Manzikert", "area": ellipse(P(5000, 800), 2500, 1800), "conjectural": True},
                 {"id": "byz-camp", "kind": "camp", "label": "Byzantine camp", "area": ellipse(P(-900, -200), 500, 350), "conjectural": True}])
