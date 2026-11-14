"""Battle of Plassey, 23 June 1757 — map story builder.

Anchors: Palashi town / Plassey station (OSM, ~4 km SE of the Wikidata point); Bhagirathi-Hooghly line from OSM
(the modern course, the river has since shifted west). Layout from the Wikipedia account: the Laksha Bagh grove
(730 x 270 m, diagonal to the river) with Clive's hunting lodge just north of it at the bank; the Nawab's earth
entrenchment ran at right angles to the river for 180 m, then north-east for 4.8 km, with a redoubt at the turn,
a wooded hill 270 m east of it, and two tanks about a mile from the grove. Orientation: the British face north
(river on their left/west), the Nawab's host faces south and south-west toward the grove.
Exact tank, redoubt and unit positions are reconstructed (conjectural).
"""
from pipeline.map_stories.geo import ellipse, offset
from pipeline.map_stories.layout import Story, deploy_line, local_frame

ANCHOR = (88.2480, 23.7850)
P = local_frame(ANCHOR)

RIVER = [[88.23348, 23.78919], [88.24511, 23.8192], [88.2053, 23.84477]]
RIVER_S = [[88.23381, 23.78564], [88.22099, 23.75566], [88.18958, 23.75975]]


def build() -> dict:
    st = Story()
    G = P(-400, 0)

    # ---------------- step 1: night march into the grove
    st.step("grove", "Into the mango grove", "1:00, 23 June",
            """After crossing the Bhagirathi on 22 June, Clive's little army marched through the wet night and reached Plassey
            about one in the morning. It took the Laksha Bagh, a walled and ditched mango grove roughly 730 metres long, and
            Clive made his quarters in the hunting lodge on the river bank just north of it. A mile off, behind earthworks
            that ran from the river and then swung north-east, the Nawab's huge army had been camped for more than a day.""")
    st.put("br-army", at=P(-400, -50), facing=0, width=360, depth=90, state="ready")
    st.put("br-clive", at=P(-1100, 480), facing=0)
    st.put("na-durlabh", at=P(-150, 1950), facing=180, width=500, depth=100)
    st.put("na-madan", at=P(500, 1800), facing=180, width=500, depth=70)
    st.put("na-lutuf", at=P(1200, 1950), facing=180, width=450, depth=100)
    st.put("na-jafar", at=P(1800, 2100), facing=180, width=450, depth=100)
    st.put("na-french", at=P(-450, 1700), facing=180, width=110, depth=40)
    st.put("na-siraj", at=P(100, 2150), facing=180)
    st.side_move("a", "march", [P(-1500, -1900), P(-1000, -900), P(-400, -150)], "Clive's march")

    # ---------------- step 2: Nawab sorties
    st.step("sortie", "The Nawab's army comes out", "Dawn",
            """At daybreak the Nawab's army left its camp and spread toward the grove. Sources count some 50,000 men and a very
            large park of heavy guns. Fifty French gunners under St. Frais took post at the larger tank with a few light
            pieces, within a mile of the British. Behind them stood the loyal general Mir Madan and the diwan Mohanlal with
            about 12,000 men. The rest formed a long arc: Rai Durlabh on the right, Yar Lutuf Khan in the centre and Mir Jafar,
            the secret ally of the British, on the left nearest Clive.""")
    st.put("na-french", at=P(-500, 800), facing=180, width=120, depth=40, move="advance")
    st.put("na-madan", at=P(-150, 1000), facing=190, width=650, depth=60, move="advance")
    st.put("na-durlabh", at=P(-800, 1350), facing=210, width=500, depth=100, move="advance", conjectural=True)
    st.put("na-lutuf", at=P(750, 800), facing=240, width=500, depth=100, move="advance", conjectural=True)
    st.put("na-jafar", at=P(1050, 150), facing=270, width=500, depth=100, move="advance", conjectural=True)
    st.put("na-siraj", at=P(-250, 1650), facing=180, move="advance")

    # ---------------- step 3: British form line, first shots
    st.step("line", "The British line and the first shots", "8:00",
            """Clive watched from the roof of the lodge and ordered his men out of the grove to face the larger tank. The
            Europeans and topasses stood in the centre in four divisions with three six-pounders on each side, and the
            sepoys held the two wings. Two six-pounders and two howitzers were set behind brick kilns north of the left. At
            eight the French guns fired the first shot, killing a grenadier, and the whole Nawab's artillery opened a heavy
            and steady fire.""")
    st.hide("br-army")
    st.place(deploy_line(P(-800, 320), P(100, 320), [("br-sepoy-l", 1050), ("br-euro", 850), ("br-sepoy-r", 1050)], depth=14),
             move="advance")
    st.put("br-guns", at=P(-350, 345), facing=0, width=160, depth=12)
    st.put("br-kilns", at=P(-780, 520), facing=0, width=70, depth=12)
    st.pin("br-clive", "br-euro")
    for u in ("br-euro", "br-kilns", "na-french"):
        st.put(u, state="engaged")
    st.note(P(-500, 700), "First shot from the French guns", "clash")

    # ---------------- step 4: withdraw
    st.step("withdraw", "Back behind the grove bank", "8:30",
            """Round shot from the Nawab's batteries mostly flew into his own cavalry and infantry, yet by half past eight the
            British had lost 10 Europeans and 20 sepoys. Clive pulled the main body back into the shelter of the grove, whose
            earth bank and ditch cut the casualty rate sharply. Only the advanced guns at the brick kilns stayed out to
            answer the French. For about three hours neither side changed position, and Clive's officers resolved to hold the
            grove until dark and attempt a night attack at midnight.""")
    st.put("br-sepoy-l", at=P(-620, 120), facing=0, width=240, depth=30, move="retreat", state="ready")
    st.put("br-euro", at=P(-400, 80), facing=0, width=260, depth=20, move="retreat", state="ready")
    st.put("br-sepoy-r", at=P(-130, 80), facing=0, width=240, depth=30, move="retreat", state="ready")
    st.put("br-guns", at=P(-400, 200), facing=0, move="retreat")
    st.pin("br-clive", "br-euro")
    st.put("br-clive", at=P(-1100, 480))

    # ---------------- step 5: rain and Mir Madan
    st.step("rain", "Rain and the death of Mir Madan", "c. 11:00-12:00",
            """A heavy rainstorm broke over the field. Clive's gunners covered their powder with tarpaulins, but the Nawab's
            army took no such care and its powder was soaked. Supposing the British guns were dead too, Mir Madan led his
            cavalry in a charge as the rain eased. Grapeshot stopped it and mortally wounded him. The loss shook Siraj
            ud-Daulah, who in panic sought Mir Jafar's help, and Mir Jafar quietly passed the news to Clive and urged him to
            press forward.""")
    st.put("na-madan", at=P(-250, 600), facing=190, width=650, depth=60, move="charge", state="engaged")
    st.put("br-sepoy-l", state="engaged")
    st.put("br-guns", state="engaged")
    st.note(P(-300, 520), "Mir Madan mortally wounded", "death")

    # ---------------- step 6: Siraj leaves
    st.step("siraj-leaves", "Siraj ud-Daulah leaves the field", "c. 12:00-14:00",
            """Rai Durlabh, the commander on the Nawab's right, advised Siraj to withdraw behind the entrenchment and to leave
            the fighting to his generals. The Nawab agreed. He ordered Mohanlal to pull back and then rode a camel toward
            Murshidabad with 2,000 horsemen. About two o'clock the army stopped its cannonade and began to turn north toward
            its camp, leaving St. Frais and his guns at the tank without support.""")
    st.put("na-siraj", at=P(-250, 2500), facing=0, move="retreat")
    st.put("na-madan", at=P(-150, 1150), facing=0, move="retreat", state="wavering")
    st.put("na-durlabh", at=P(-700, 1550), facing=0, move="retreat")
    st.put("na-lutuf", at=P(600, 1200), facing=0, move="retreat")
    st.put("br-sepoy-l", state="ready")
    st.put("br-guns", state="ready")
    st.put("br-kilns", state="ready")
    st.put("na-french", state="ready")

    # ---------------- step 7: Kilpatrick
    st.step("kilpatrick", "Kilpatrick moves on the French guns", "c. 14:00",
            """Major Kilpatrick, left in command while Clive rested in the lodge, saw the Nawab's troops going away and saw
            that St. Frais was now alone. Without orders he took two companies of the 39th Foot and two field pieces toward the
            tank. Clive heard of it, hurried up, scolded him, and then brought out the rest of the army from the grove. Mir
            Jafar's division, trailing behind the Nawab's retiring columns, began to angle toward the grove.""")
    st.put("br-kilpatrick", at=P(-420, 450), facing=0, width=130, depth=14, move="advance", start=P(-420, 150))
    st.put("br-euro", at=P(-400, 300), facing=0, width=260, depth=20, move="advance")
    st.put("br-sepoy-l", at=P(-680, 280), facing=0, width=240, depth=30, move="advance")
    st.put("br-sepoy-r", at=P(-120, 280), facing=0, width=240, depth=30, move="advance")
    st.put("na-jafar", at=P(850, 700), facing=300, move="advance", conjectural=True)

    # ---------------- step 8: tank taken, Jafar checked
    st.step("tank", "The larger tank falls", "c. 15:00",
            """Clive led the army forward and by about three o'clock the French artillery had been forced out of the larger
            tank and back to the redoubt of the entrenchment. Meanwhile the Nawab's left division, which had lagged behind,
            turned toward the grove. Clive took it for an attack on his baggage and sent Captain Grant with three platoons and
            a field piece under Johnstone to stop it. The gun's fire halted the division, which then stood apart from the rest
            of the Nawab's army.""")
    st.put("br-kilpatrick", at=P(-500, 760), facing=0, state="engaged")
    st.put("na-french", at=P(-1100, 1450), facing=180, width=100, depth=40, move="retreat", state="ready")
    st.put("br-euro", at=P(-450, 650), facing=0, move="advance")
    st.put("br-sepoy-l", at=P(-750, 620), facing=0, move="advance")
    st.put("br-sepoy-r", at=P(-170, 620), facing=0, move="advance")
    st.put("br-grant", at=P(300, 350), facing=90, width=100, depth=14, move="flank", start=P(-300, 500), conjectural=True)
    st.put("na-jafar", at=P(700, 450), facing=300, state="ready")
    st.put("br-clive", at=P(-450, 650))
    st.pin("br-clive", "br-euro")

    # ---------------- step 9: cannonade of the camp
    st.step("cannonade", "Bombarding the entrenchment", "c. 15:00-16:00",
            """From the mound of the larger tank the British guns fired into the Nawab's camp, and troops and guns that tried to
            come out were thrown into confusion. Clive sent half his force and guns to the smaller tank and the rest to a rise
            about 200 yards to its left. Matchlockmen fired from holes, ditches and bushes on the hill east of the redoubt, St.
            Frais kept his guns in the redoubt and the Nawab's horse charged more than once. This phase cost the British most
            of their casualties. Clive finally understood that the lingering division was Mir Jafar's.""")
    st.put("br-euro", at=P(-700, 1000), facing=0, width=260, depth=20, move="advance", state="engaged")
    st.put("br-sepoy-l", at=P(-1000, 980), facing=0, width=240, depth=30, move="advance", state="engaged")
    st.put("br-sepoy-r", at=P(-430, 980), facing=0, width=240, depth=30, move="advance", state="engaged")
    st.put("br-kilpatrick", at=P(-800, 1050), facing=0, state="engaged")
    st.put("na-durlabh", at=P(-100, 1550), facing=225, state="engaged")
    st.put("na-lutuf", at=P(600, 1500), facing=225, move="advance", state="ready", conjectural=True)
    st.put("na-french", at=P(-1180, 1500), facing=180, width=90, depth=40, state="engaged")
    st.note(P(-930, 1500), "Wooded hill (conjectural)", "label")

    # ---------------- step 10: three-pronged
    st.step("assault", "Three-pronged assault", "16:30",
            """Clive ordered two detachments to storm the redoubt and the hill east of it while the main force pressed in the
            centre. Major Coote with two grenadier companies of the 39th took the hill at half past four, when the defenders
            ran without firing. The redoubt fell after St. Frais withdrew. The army inside, with its general gone and its
            commander Mir Jafar standing aside, had no one to hold it together.""")
    st.put("br-coote", at=P(-930, 1450), facing=0, width=130, depth=14, move="charge", start=P(-800, 1150), state="engaged", conjectural=True)
    st.put("br-euro", at=P(-600, 1350), facing=45, move="attack", state="engaged")
    st.put("br-sepoy-l", at=P(-1100, 1380), facing=0, move="attack", state="engaged")
    st.put("na-french", at=P(-1050, 1900), facing=180, move="retreat", state="routed")
    st.put("na-durlabh", state="wavering")

    # ---------------- step 11: camp taken
    st.step("rout", "The camp is taken", "17:00",
            """By five the British held the entrenchment and the camp the Nawab's army had abandoned as it scattered. Clive's
            losses came to 22 killed and 50 wounded by the usual accounting, against an estimated 500 on the other side. His
            troops marched on that evening and halted six miles beyond Daudpur. The next morning Mir Jafar met him there and
            was saluted as Nawab of Bengal, Bihar and Orissa.""")
    st.put("br-euro", at=P(-300, 1800), facing=45, move="advance", state="ready")
    st.put("br-sepoy-l", at=P(-900, 1800), facing=45, move="advance", state="ready")
    st.put("br-sepoy-r", at=P(-100, 1550), facing=45, move="advance", state="ready")
    st.put("br-coote", at=P(-700, 2100), facing=0, move="pursuit", state="ready")
    for u in ("na-durlabh", "na-lutuf", "na-madan", "na-jafar"):
        st.put(u, state="routed" if u != "na-jafar" else "ready")
    st.put("na-durlabh", at=P(900, 2800), facing=45, move="rout", state="routed")
    st.put("na-lutuf", at=P(1500, 2600), facing=45, move="rout", state="routed")
    st.put("na-madan", at=P(700, 2900), facing=45, move="rout", state="routed")

    return st.doc(
        slug="battle-of-plassey", kind="battle",
        entity={"name": "Battle of Plassey", "wikidata": "Q203233"},
        title="Battle of Plassey", date_label="23 June 1757", year=1757,
        intro="""On 23 June 1757 a small East India Company army under Robert Clive faced the vast host of Siraj ud-Daulah,
        Nawab of Bengal, on a mango-grove plain beside the Bhagirathi, a branch of the Hooghly, near Palashi. Clive had about
        3,100 men and eight guns; the Nawab fielded perhaps 50,000, with heavy artillery and a handful of French gunners
        under St. Frais. The real contest had been settled in advance by a conspiracy: Mir Jafar, who held a wing of the
        Nawab's army, and other powerful men at court had promised to hold back. After a day of cannonade, a rainstorm, the
        death of the Nawab's most loyal general and a British advance in the afternoon, the camp fell. Mir Jafar was made
        Nawab, and Bengal's revenue passed into Company hands.""",
        outcome="British victory: Siraj ud-Daulah fled and was killed, Mir Jafar became Nawab, and Bengal fell under Company control.",
        uncertainty="""The sources fix the grove, the entrenchment, the redoubt, the hill and the two tanks only by distance
        from one another and the Bhagirathi has moved since 1757, so every position here is a reconstruction. The Nawab's
        troop numbers and the split between Rai Durlabh, Yar Lutuf Khan and Mir Jafar are round estimates, and the exact
        timings of the afternoon phases differ between accounts. Positions of detachments under Kilpatrick, Grant and Coote
        are approximate.""",
        sources=[{"title": "Battle of Plassey - Wikipedia", "url": "https://en.wikipedia.org/wiki/Battle_of_Plassey", "kind": "web"}],
        sides=[
            {"id": "a", "name": "East India Company", "color": "#b91c1c",
             "polity": {"name": "East India Company", "wikidata": "Q83164"},
             "commanders": [{"name": "Robert Clive", "wikidata": "Q162296", "role": "commander"},
                            {"name": "Eyre Coote", "wikidata": "Q2613325", "role": "major, 39th Foot"}],
             "strength": "c. 3,100", "losses": "22-27 killed, 50 wounded"},
            {"id": "b", "name": "Nawab of Bengal", "color": "#15803d",
             "polity": {"name": "Bengal Subah", "wikidata": "Q4083684"},
             "commanders": [{"name": "Siraj ud-Daulah", "wikidata": "Q1998495", "role": "Nawab"},
                            {"name": "Mir Jafar", "wikidata": "Q3241725", "role": "left wing, secretly allied to Clive"},
                            {"name": "Mir Madan", "wikidata": "Q28861765", "role": "artillery chief, killed"},
                            {"name": "Diwan Mohanlal", "wikidata": "Q5284739", "role": "diwan"},
                            {"name": "St. Frais", "wikidata": "Q16842433", "role": "French artillery"}],
             "strength": "c. 50,000", "losses": "c. 500 killed and wounded"},
        ],
        units=[
            {"id": "br-army", "side": "a", "kind": "army", "label": "Clive's army", "strength": "c. 3,100"},
            {"id": "br-clive", "side": "a", "kind": "commander", "label": "Clive"},
            {"id": "br-euro", "side": "a", "kind": "infantry", "label": "Europeans and topasses", "strength": "c. 850", "strength_n": 850},
            {"id": "br-sepoy-l", "side": "a", "kind": "infantry", "label": "Sepoys, left", "strength": "c. 1,050", "strength_n": 1050},
            {"id": "br-sepoy-r", "side": "a", "kind": "infantry", "label": "Sepoys, right", "strength": "c. 1,050", "strength_n": 1050},
            {"id": "br-guns", "side": "a", "kind": "artillery", "label": "Six-pounders"},
            {"id": "br-kilns", "side": "a", "kind": "artillery", "label": "Guns at the kilns"},
            {"id": "br-kilpatrick", "side": "a", "kind": "infantry", "label": "Kilpatrick's detachment"},
            {"id": "br-grant", "side": "a", "kind": "infantry", "label": "Grant's platoons"},
            {"id": "br-coote", "side": "a", "kind": "infantry", "label": "Coote's grenadiers"},
            {"id": "na-french", "side": "b", "kind": "artillery", "label": "St. Frais and French guns"},
            {"id": "na-madan", "side": "b", "kind": "cavalry", "label": "Mir Madan and Mohanlal", "strength": "5,000 horse, 7,000 foot"},
            {"id": "na-durlabh", "side": "b", "kind": "infantry", "label": "Rai Durlabh, right"},
            {"id": "na-lutuf", "side": "b", "kind": "infantry", "label": "Yar Lutuf Khan, centre"},
            {"id": "na-jafar", "side": "b", "kind": "infantry", "label": "Mir Jafar, left"},
            {"id": "na-siraj", "side": "b", "kind": "commander", "label": "Siraj ud-Daulah"},
        ],
        terrain=[
            {"id": "river", "kind": "river", "label": "Bhagirathi", "line": RIVER},
            {"id": "river-s", "kind": "river", "label": "Bhagirathi", "line": RIVER_S},
            {"id": "grove", "kind": "woods", "label": "Laksha Bagh grove", "area": ellipse(P(-400, 0), 135, 365, rotate=45), "conjectural": True},
            {"id": "lodge", "kind": "building", "label": "Hunting lodge", "at": P(-1100, 480), "conjectural": True},
            {"id": "entrench", "kind": "wall", "label": "Nawab's entrenchment",
             "line": [P(-1350, 1500), P(-1170, 1500), P(0, 2650), P(900, 3550)], "conjectural": True},
            {"id": "redoubt", "kind": "fortification", "label": "Redoubt", "area": ellipse(P(-1180, 1500), 60, 60), "conjectural": True},
            {"id": "tank-l", "kind": "field", "label": "Larger tank", "area": ellipse(P(-500, 780), 60, 45), "conjectural": True},
            {"id": "tank-s", "kind": "field", "label": "Smaller tank", "area": ellipse(P(-500, 960), 50, 40), "conjectural": True},
            {"id": "hill", "kind": "hill", "label": "Wooded hill", "area": ellipse(P(-930, 1500), 80, 80), "conjectural": True},
        ],
    )
