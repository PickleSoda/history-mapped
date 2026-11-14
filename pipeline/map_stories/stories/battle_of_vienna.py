"""Battle of Vienna, 12 September 1683 — map story builder.

Anchor: the Türkenschanze (Türkenschanzpark, 16.3338 E 48.2355 N, places). Villages Nussdorf, Heiligenstadt,
Unter-/Oberdöbling, Gersthof, Währing and the Kahlenberg from `places`; Wien river from OSM; the old city
walls and the Ottoman main camp are placed where the mainstream reconstruction puts them (conjectural).
Orientation: the relief army came down from the Kahlenberg and Vienna Woods in the north and north-west and
faced south-east (about 155 deg): Imperials on the left by the Danube (Nussdorf), Saxons and Bavarians in the
centre, Poles on the right (west). The Ottomans faced north-west (about 335 deg) with Vienna and their camp behind.
Sources: Wikipedia, Battle of Vienna (Prelude, Staging the battle, Battle).
"""
from pipeline.map_stories.geo import bearing, ellipse, local, offset
from pipeline.map_stories.layout import Story, facing_off, local_frame, when

ANCHOR = (16.3338, 48.2355)
P = local_frame(ANCHOR)


def L(lon, lat):
    return P(*local((lon, lat), ANCHOR))


WIENFLUSS = [[16.30448, 48.18779], [16.31297, 48.18751], [16.32654, 48.18406], [16.33131, 48.18391], [16.33426, 48.18471],
             [16.33879, 48.18832], [16.35202, 48.19014], [16.355, 48.19581], [16.36711, 48.20061], [16.37352, 48.19984],
             [16.37635, 48.20054], [16.38129, 48.20504], [16.38478, 48.2122]]
KAHLENBERG_RIDGE = [[16.2750, 48.2600], [16.3050, 48.2700], [16.3331, 48.2763], [16.3452, 48.2782]]
VIENNA = (16.3731, 48.2086)
VIENNA_AT = L(*VIENNA)

AL, OT = 155, 335


def build() -> dict:
    st = Story()

    st.step("siege", "Two months under siege", "14 July – 11 September", """
        Since 14 July the Ottoman army of Grand Vizier Kara Mustafa has sat before Vienna, where Count Starhemberg
        commands a garrison and militia. Ottoman sappers have dug toward the north-western bastions and laid ten
        mines under them; the Ottoman camp lies south-west of the city, and janissaries hold the fortified post at
        the Türkenschanze and the villages Nussdorf and Heiligenstadt to the north. The city is close to falling.
        """, date=when(1683, 7, 14, end=(1683, 9, 11)))
    st.put("garrison", at=P(2850, -2950), facing=315, width=500, depth=60, state="engaged")
    st.put("ot-assault", at=P(2500, -2400), facing=135, width=450, depth=50, state="engaged")
    st.put("ot-camp", at=P(-200, -2700), width=500, depth=300)
    st.put("kara", at=P(250, -400))
    st.put("ot-centre", at=P(150, 120), facing=OT, width=600, depth=60)
    st.put("ot-right", at=P(2600, 2250), facing=OT, width=800, depth=50)
    st.put("ot-left", at=P(-1300, -100), facing=OT, width=700, depth=60)
    st.put("wallachians", at=P(3280, 900), facing=OT, width=300, depth=40)
    st.note(P(2400, -2000), "Ten mines laid under the bastions", "event")

    st.step("bonfires", "Bonfires on the Kahlenberg", "11 September evening", """
        The relief army arrives over the Vienna Woods after crossing the Danube upstream. Poles under King John III
        Sobieski, Imperial troops under Charles of Lorraine, and Saxon, Bavarian and other German contingents gather
        on the Kahlenberg slopes and light bonfires to tell the city help is near. Jerzy Kulczycki, a Polish-born
        Turkish speaker, had slipped through the Ottoman lines with word of the plan. The Crimean Tatars under the
        khan, charged with guarding the rear, had refused to contest the crossing.
        """, date=when(1683, 9, 11))
    st.put("imp-left", at=P(2300, 3300), facing=AL, width=900, depth=50)
    st.put("sax-bav", at=P(700, 3500), facing=AL, width=800, depth=50)
    st.put("pol-inf", at=P(-900, 3200), facing=AL, width=900, depth=50)
    st.put("pol-hussars", at=P(-2300, 3300), facing=AL, width=450, depth=40)
    st.put("pol-cav", at=P(-1700, 3800), facing=AL, width=600, depth=40)
    st.put("imp-cav", at=P(1400, 3950), facing=AL, width=500, depth=40)
    st.put("sobieski", at=P(-2200, 3500))
    st.put("charles", at=P(2000, 3500))
    st.pin("sobieski", "pol-hussars")
    st.note(P(0, 4500), "Kahlenberg", "label")

    st.step("attack", "The Ottomans strike first", "12 September, 04:00", """
        Before the allied columns have fully formed, Kara Mustafa tries to disrupt them by attacking at four in
        the morning. His right, holding the Danube-side villages, pushes up the slope against the Imperial left.
        The German troops are the first to answer, and the fighting there is hard and goes back and forth.
        """, date=when(1683, 9, 12), light="dawn")
    st.put("ot-right", at=P(2350, 2800), move="attack", state="engaged")
    st.put("imp-left", facing_off(st.pl("ot-right"), depth=50, gap=5), state="engaged")

    st.step("nussdorf", "The Imperial left takes the villages", "Morning to midday", """
        Charles of Lorraine commits the Imperial army on the left and the centre. After several Ottoman
        counter-attacks the fortified villages of Nussdorf and Heiligenstadt fall to him, and by noon the Ottoman
        right is badly mauled and the Imperials are close to a breakthrough along the Danube.
        """)
    st.put("ot-right", at=P(2650, 1500), move="retreat", state="wavering")
    st.put("imp-left", facing_off(st.pl("ot-right"), depth=50, gap=30), move="attack", state="engaged")
    st.put("sax-bav", at=P(800, 2700), move="advance")
    st.note(P(2900, 2000), "Nussdorf and Heiligenstadt taken", "capture")

    st.step("walls", "The last assault on the walls fails", "Midday", """
        Kara Mustafa throws counter-attacks at the Imperials but holds back his best janissaries and sipahis for a
        final push on the city. His sappers' great charge under the Löbelbastei is found and the ten mines are
        disarmed by the defenders. On the Danube flank the Wallachians of Șerban Cantacuzino, who secretly favour
        the allies, abandon the bridge on Brigittenau island that covered the Ottoman left.
        """)
    st.put("wallachians", at=P(3700, 300), move="retreat", state="wavering")
    st.put("ot-assault", at=P(2400, -2300), state="wavering")
    st.put("garrison", state="ready")
    st.note(P(2250, -2000), "Mines found and disarmed", "event")

    st.step("poles", "The Polish infantry advance", "Early afternoon to 16:00", """
        On the other side of the field Polish infantry move down from the woods against the Ottoman right
        flank, which is distracted by the siege works. By four o'clock they hold the village of Gersthof,
        which becomes the jumping-off point for the cavalry. The Polish horse, under cover of the woods and
        the infantry, form up behind them.
        """, light="day")
    st.put("ot-left", at=P(-1250, -500), move="retreat", state="engaged")
    st.put("pol-inf", facing_off(st.pl("ot-left"), depth=50, gap=5), move="attack", state="engaged")
    st.put("pol-hussars", at=P(-1900, 1000), move="march")
    st.put("pol-cav", at=P(-1450, 1200), move="march")
    st.note(P(-900, -150), "Gersthof taken by the Poles", "capture")

    st.step("doblings", "The Türkenschanze is threatened", "15:30–17:00", """
        The Germans resume their advance at 15:30, meeting stiff resistance, but by five they have taken
        Unterdöbling and Oberdöbling. The Ottoman strongpoint on the Türkenschanze is now threatened from the
        west by Poles, from the north-west by Saxons and Bavarians, and from the north by Austrians. At about four
        a detachment of 120 hussars makes a probing charge: it shows the Ottoman line is brittle but takes heavy
        losses. Kara Mustafa leaves the post and rides back to the main camp.
        """)
    st.put("imp-left", at=P(1150, 800), facing=bearing(P(1150, 800), P(300, 100)), move="advance", state="engaged", width=700)
    st.put("sax-bav", facing_off(st.pl("ot-centre"), depth=50, gap=5), move="attack", state="engaged")
    st.put("ot-centre", state="engaged")
    st.put("pol-probe", at=P(-900, 650), facing=AL, width=120, depth=20, state="ready")
    st.put("pol-probe", at=P(-350, 150), move="charge", state="wavering")
    st.put("kara", at=P(-200, -2500), move="retreat")
    st.note(P(1000, 1250), "Döbling villages taken", "capture")

    st.step("charge-form", "The cavalry forms on the slope", "c. 17:00–18:00", """
        Sobieski and Charles of Lorraine each decide, without consulting the other, to press on. The Polish king
        draws his cavalry into four contingents: three Polish and one Imperial. Some 3,000 Winged Hussars, the
        heavy lancers, are under his own command. Allied Lipka Tatars wear straw in their helmets so that they
        are not mistaken for the Tatars on the Ottoman side.
        """, light="dusk")
    st.put("pol-hussars", at=P(-1450, 900), facing=150, width=500, depth=40, strength_n=3000, state="ready")
    st.put("pol-cav", at=P(-2000, 1000), facing=150, width=600, depth=40)
    st.put("imp-cav", at=P(-600, 1450), facing=150, width=500, depth=40, move="march")
    st.put("pol-probe", at=P(-350, 150))
    st.hide("pol-probe")

    st.step("charge", "The great cavalry charge", "c. 18:00", """
        About 18,000 horsemen sweep down the hills, the largest cavalry charge on record. The tired and
        disheartened Ottoman line, shaken by the failed mine assault and the loss of the Türkenschanze,
        breaks almost at once. Cantacuzino's Wallachians also join the retreat, and the cavalry heads for
        Kara Mustafa's camp.
        """)
    st.put("pol-hussars", at=P(-700, -400), move="charge", state="engaged")
    st.put("pol-cav", at=P(-1300, -300), move="charge", state="engaged")
    st.put("imp-cav", at=P(100, 400), move="charge", state="engaged")
    st.put("ot-left", at=P(-1000, -1300), move="rout", state="routed")
    st.put("ot-centre", at=P(300, -1300), move="rout", state="routed")
    st.put("pol-inf", at=P(-1000, -250), move="advance", state="ready")
    st.put("sax-bav", at=P(500, 1000), move="advance", state="ready")
    st.put("imp-left", at=P(1000, 600), move="advance", state="ready")
    st.put("ot-right", at=P(2000, 400), move="retreat", state="routed")

    st.step("camp", "The camp falls and the garrison sallies", "Evening", """
        The horsemen ride straight on to the Ottoman camp and the vizier's headquarters while the remaining
        Viennese garrison sallies from the walls to join in. Less than three hours after the charge began, the
        battle is over and the siege lifted. Ottoman troops flee southward and eastward, leaving the camp,
        baggage and guns.
        """, light="dusk")
    st.put("pol-hussars", at=P(-250, -2300), move="pursuit", state="ready")
    st.put("imp-cav", at=P(700, -2000), move="pursuit", state="ready")
    st.put("pol-cav", at=P(-900, -2000), move="pursuit", state="ready")
    st.put("ot-camp", state="captured", by="allies")
    st.put("kara", at=P(900, -3800), move="retreat")
    st.put("ot-assault", at=P(1900, -3600), move="rout", state="routed")
    st.put("garrison", at=P(2400, -2000), move="attack", state="ready")
    st.note(P(-200, -2800), "Ottoman camp and baggage taken", "capture")

    st.step("aftermath", "Vienna is saved", "13 September onward", """
        The Ottoman army, its commander and most of its guns beaten, retreats toward Hungary. Sobieski sums up
        the day with a line adapted from Caesar: we came, we saw, God conquered. The Viennese cheer the
        deliverers, and the Habsburg alliance with Poland, Venice and the pope presses the war into Hungary, a
        long conflict that ends in Ottoman losses of Hungarian lands. Kara Mustafa is executed on his sultan's
        orders at the end of the year.
        """, light="day")
    st.put("sobieski", at=P(300, -2400))
    st.note(P(300, -2200), "Sobieski enters the camp", "event")

    return st.doc(
        slug="battle-of-vienna", kind="battle", entity={"name": "Battle of Vienna", "wikidata": "Q200855"},
        title="Battle of Vienna", date_label="12 September 1683", year=1683,
        intro="""In the summer of 1683 the Ottoman army of Grand Vizier Kara Mustafa Pasha besieged Vienna, the Habsburg
        capital, after the emperor and his court had fled. The siege began on 14 July and by September the walls were
        undermined and the garrison under Count Starhemberg was close to collapse. A relief army of Poles under King
        John III Sobieski, Imperial troops under Charles of Lorraine and German contingents from Saxony, Bavaria and
        elsewhere came over the Vienna Woods. On 12 September the Ottomans attacked first at dawn, the Imperial left
        took the villages by the Danube, Polish infantry took Gersthof, and at about six in the evening some 18,000
        horsemen, led by Sobieski's Winged Hussars, charged down the hills and broke the Ottoman army.""",
        outcome="Decisive victory for the Christian coalition: the siege of Vienna is lifted and the Ottoman army flees.",
        uncertainty="""Times in the sources are approximate and sometimes disagree. Exact unit positions, frontages and
        the orientation of the lines are reconstructed from the villages named in the accounts (conjectural), as are the
        city walls, the Ottoman camp and the bridge on Brigittenau. The sizes of both armies are disputed: the
        relief force is given as 70,000 to 80,000 and the Ottoman field force as 28,400 to 50,000. Historians also
        doubt how far the Crimean Tatars took part in the final battle.""",
        sources=[{"title": "Battle of Vienna - Wikipedia", "url": "https://en.wikipedia.org/wiki/Battle_of_Vienna", "kind": "web"}],
        sides=[
            {"id": "allies", "name": "Christian coalition", "color": "#1d4ed8",
             "polity": {"name": "Habsburg monarchy", "wikidata": "Q153136"},
             "commanders": [{"name": "John III Sobieski", "wikidata": "Q53454", "role": "King of Poland, relief army"},
                            {"name": "Charles V, Duke of Lorraine", "wikidata": "Q156949", "role": "Imperial army"},
                            {"name": "Ernst Rüdiger von Starhemberg", "wikidata": "Q551615", "role": "Vienna garrison"}],
             "strength": "70,000-80,000 relief force; 16,000 in the city", "losses": "c. 4,500 in the battle"},
            {"id": "ottomans", "name": "Ottoman army", "color": "#b91c1c",
             "polity": {"name": "Ottoman Empire", "wikidata": "Q12560"},
             "commanders": [{"name": "Kara Mustafa Pasha", "wikidata": "Q334140", "role": "Grand Vizier"},
                            {"name": "Murad Giray", "wikidata": "Q2977282", "role": "Khan of Crimea"},
                            {"name": "Șerban Cantacuzino", "wikidata": "Q127436", "role": "Prince of Wallachia"}],
             "strength": "28,400-50,000 in the field, c. 60 guns", "losses": "8,000-20,000 in the battle"},
        ],
        units=[
            {"id": "imp-left", "side": "allies", "kind": "infantry", "label": "Imperial army (left)"},
            {"id": "sax-bav", "side": "allies", "kind": "infantry", "label": "Saxons and Bavarians"},
            {"id": "pol-inf", "side": "allies", "kind": "infantry", "label": "Polish infantry"},
            {"id": "pol-hussars", "side": "allies", "kind": "heavy_cavalry", "label": "Winged Hussars", "strength": "c. 3,000"},
            {"id": "pol-cav", "side": "allies", "kind": "cavalry", "label": "Polish cavalry"},
            {"id": "imp-cav", "side": "allies", "kind": "cavalry", "label": "Imperial cavalry"},
            {"id": "pol-probe", "side": "allies", "kind": "heavy_cavalry", "label": "Probing hussars", "strength": "120"},
            {"id": "garrison", "side": "allies", "kind": "infantry", "label": "Vienna garrison"},
            {"id": "sobieski", "side": "allies", "kind": "commander", "label": "Sobieski"},
            {"id": "charles", "side": "allies", "kind": "commander", "label": "Charles of Lorraine"},
            {"id": "ot-right", "side": "ottomans", "kind": "infantry", "label": "Ottoman right at Nussdorf"},
            {"id": "ot-centre", "side": "ottomans", "kind": "infantry", "label": "Janissaries, Türkenschanze"},
            {"id": "ot-left", "side": "ottomans", "kind": "light_cavalry", "label": "Sipahis and Tatars"},
            {"id": "wallachians", "side": "ottomans", "kind": "infantry", "label": "Wallachians at the bridge"},
            {"id": "ot-assault", "side": "ottomans", "kind": "infantry", "label": "Sappers at the walls"},
            {"id": "ot-camp", "side": "ottomans", "kind": "camp", "label": "Ottoman camp"},
            {"id": "kara", "side": "ottomans", "kind": "commander", "label": "Kara Mustafa"},
        ],
        terrain=[
            {"id": "wien", "kind": "river", "label": "Wien river", "line": WIENFLUSS},
            {"id": "ridge", "kind": "ridge", "label": "Kahlenberg ridge", "line": [list(p) for p in KAHLENBERG_RIDGE], "conjectural": True},
            {"id": "woods", "kind": "woods", "label": "Vienna Woods", "area": ellipse(P(-3200, 3200), 1800, 1300), "conjectural": True},
            {"id": "walls", "kind": "fortification", "label": "Vienna walls", "area": ellipse(VIENNA_AT, 900, 700), "conjectural": True},
            {"id": "schanze", "kind": "fortification", "label": "Türkenschanze", "area": ellipse(P(0, 0), 250, 200), "conjectural": True},
            {"id": "nussdorf", "kind": "village", "label": "Nussdorf", "at": L(16.36455, 48.25905)},
            {"id": "heiligenstadt", "kind": "village", "label": "Heiligenstadt", "at": L(16.36554, 48.24805)},
            {"id": "gersthof", "kind": "village", "label": "Gersthof", "at": L(16.32374, 48.23414)},
            {"id": "oberdobling", "kind": "village", "label": "Oberdöbling", "at": L(16.34402, 48.24405)},
            {"id": "unterdobling", "kind": "village", "label": "Unterdöbling", "at": L(16.34862, 48.24779)},
            {"id": "bridge", "kind": "bridge", "label": "Brigittenau bridge", "at": L(16.37814, 48.24382), "conjectural": True},
        ],
    )
