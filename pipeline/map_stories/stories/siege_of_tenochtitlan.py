"""Siege of Tenochtitlan, 26 May - 13 August 1521 - map story builder.

Anchors: Templo Mayor (osm, -99.13143, 19.43506) as the city centre; Tlatelolco, Chapultepec, Tacuba,
Coyoacan, Iztapalapa, Tepeyac and Texcoco from `places`. Causeway lines, the Chapultepec aqueduct and the
island outline are conjectural (the lake is drained today); the base map draws no 1521 water.
Orientation: the Spanish divisions converge on the island city from W (Alvarado, Tacuba causeway, facing east),
S (Olid at Coyoacan, then Sandoval from Iztapalapa, facing north); brigantines operate on the lake between.
The Mexica hold the island, fighting outward; Tlatelolco lies north of Tenochtitlan.
Sources: Wikipedia, Fall of Tenochtitlan (sections on preparations, first battles, advance, last stand).
"""
from pipeline.map_stories.geo import ellipse
from pipeline.map_stories.layout import Story, ent, local_frame, when

ANCHOR = (-99.13143, 19.43506)
P = local_frame(ANCHOR)

TACUBA = P(-6220, 2260)
CHAPUL = P(-4770, -1590)
TEXCOCO = P(7800 - 1000, 1400)  # conjectural, lakeshore east of the island
ISLAND = ellipse(P(-200, 600), 1700, 1900, 0, 28)
TACUBA_CW = [P(-1300, 300), P(-3000, 900), P(-4800, 1800), TACUBA]
SOUTH_CW = [P(0, -1100), P(-200, -3000), P(-300, -4500), P(-1700, -7000), P(-3200, -9400)]
IZTA_CW = [P(-300, -4500), P(1500, -6500), P(4080, -8460)]
NORTH_CW = [P(-400, 2300), P(600, 4000), P(1650, 5970)]
AQUEDUCT = [CHAPUL, P(-3000, -900), P(-1300, -300)]


def build() -> dict:
    st = Story()
    mx = lambda t: t  # noqa: E731

    st.step("preparations", "Cortes builds a fleet at Texcoco", "Dec 1520 - May 1521", """
        After the flight of the Noche Triste, Cortes regrouped in Tlaxcala and chose a plan of encirclement
        rather than assault. Martin Lopez had thirteen brigantines built in pieces and carried to Texcoco, where
        they were assembled and launched into the lake. Texcoco's rulers were replaced by Cortes's ally
        Ixtlilxochitl, and Chalco and other lakeshore towns came over. The Spaniards counted about 84 horsemen,
        some 194 crossbowmen and gunners and 650 foot, with Tlaxcalan and other allies in the tens of thousands.""",
        date=when(1520, 12, end=(1521, 5)), light="day")
    st.put("cortes-base", at=TEXCOCO, label="Cortes at Texcoco", frame=False)
    st.put("brigs", at=P(5600, 1100), label="13 brigantines", frame=False, strength_n=13)
    st.put("mx-main", at=P(0, 0), facing=0, width=1000, depth=700, label="Tenochtitlan garrison", strength_n=80000)
    st.put("mx-tlat", at=P(-590, 1810), facing=0, width=500, depth=400, label="Tlatelolco")
    st.put("mx-canoes", at=P(1800, 300), facing=90, width=900, depth=200, label="War canoes", strength_n=400)

    st.step("camps", "Three causeway camps", "22 May 1521", """
        On 22 May Cortes divided his land forces into three. Alvarado took 30 horse, 18 shot, 150 foot and some
        8,000 Tlaxcalans to Tacuba; Olid took 30 horse, 20 shot, 175 foot and 8,000 allies to Coyoacan;
        Sandoval took 24 horse, 14 shot, 150 foot and 8,000 men of Chalco and Huejotzingo to Iztapalapa. Cortes
        himself kept command of the brigantines. The island city, linked to the shore only by its causeways, was
        about to be shut in.""", date=when(1521, 5, 22), light="day")
    st.put("alv", at=P(-6000, 2200), facing=90, width=90, depth=40, label="Alvarado (c. 200)", strength_n=200)
    st.put("alv-al", at=P(-6200, 2330), facing=90, width=250, depth=60, label="Tlaxcalan allies", strength_n=8000)
    st.put("olid", at=P(-3200, -9250), facing=0, width=100, depth=40, label="Olid (c. 225)", strength_n=225)
    st.put("olid-al", at=P(-3100, -9550), facing=0, width=250, depth=60, label="Olid's allies", strength_n=8000)
    st.put("sand", at=P(4080, -8300), facing=315, width=90, depth=40, label="Sandoval (c. 190)", strength_n=190)
    st.put("sand-al", at=P(4250, -8500), facing=315, width=250, depth=60, label="Chalca, Huejotzinca", strength_n=8000)

    st.step("chapultepec", "The aqueduct is cut", "late May 1521", """
        Alvarado and Olid first marched to Chapultepec, where springs fed the city by aqueduct, and broke the
        supply. They then tried to push onto the Tlacopan causeway, but a hard counterattack from both causeway
        and lake threw them back. The first assault showed what the causeways meant: narrow, broken by gaps and
        bridges, with canoes free to strike either flank.""", date=when(1521, 5, 26), light="day")
    st.put("olid", at=P(-4400, -1800), facing=90, move="march", conjectural=True)
    st.put("olid-al", at=P(-4600, -1900), facing=90, move="march", conjectural=True)
    st.put("alv", at=P(-4600, 1800), move="advance", state="engaged")
    st.put("alv-al", at=P(-4850, 1750), move="advance", state="engaged")
    st.put("mx-canoes", at=P(-3500, 1500), facing=270, move="attack", state="engaged", width=600)
    st.note(CHAPUL, "Springs cut off", "event")
    st.note(P(-3800, 1400), "Tlacopan assault thrown back", "clash")

    st.step("lake", "The first battle on the lake", "late May 1521", """
        Cortes launched the brigantines against more than a thousand canoes. A favourable breeze rose and his
        sloops overturned and scattered the paddlers, breaking the Mexica command of the water. He then cut an
        opening in the causeway so the vessels could pass, and shared them out: four to Alvarado, six to Olid, two
        to Sandoval. With ships on one side of each causeway, canoes could no longer pincer the troops.""",
        date=when(1521, 5, 28), light="day")
    st.put("brigs", at=P(-2300, 700), facing=270, move="sail", frame=True, state="engaged")
    st.put("mx-canoes", at=P(-3000, 200), move="retreat", state="wavering", facing=270)
    st.put("olid", at=P(-300, -4900), facing=0, move="march", state="ready", conjectural=True)
    st.put("olid-al", at=P(-300, -5200), facing=0, move="march", state="ready", conjectural=True)
    st.put("sand", at=P(-600, -4950), facing=0, move="march", conjectural=True)
    st.put("sand-al", at=P(-500, -5250), facing=0, move="march", conjectural=True)
    st.put("alv", state="ready")
    st.put("alv-al", state="ready")
    st.note(P(-2300, 1000), "Causeway breached for ships", "event")

    st.step("causeways", "Fighting along the causeways", "June 1521", """
        The Spaniards tried to attack by day and withdraw at night, but the Mexica reoccupied abandoned bridges at
        once. Cortes therefore ordered his troops to sleep on the causeway with horses saddled. The Mexica dug
        pits in the shallows and planted hidden stakes, and caught two launches in an ambush, killing their
        captains. Cortes answered with a counter-ambush and learned to break the stakes. Supplies by canoe dried
        up, and several lakeside towns made peace.""", date=when(1521, 6), light="day")
    st.put("alv", at=P(-3200, 1050), move="advance", state="engaged", width=100, depth=45)
    st.put("alv-al", at=P(-3500, 1100), move="advance", state="engaged")
    st.put("olid", at=P(-300, -3600), move="advance", state="engaged", width=100, depth=45)
    st.put("olid-al", at=P(-300, -3900), move="advance", state="engaged")
    st.put("sand", at=P(-300, -3150), facing=0, move="advance", state="engaged")
    st.put("sand-al", at=P(-300, -3400), facing=0, move="advance", state="engaged")
    st.put("brigs", at=P(-2000, -1200), facing=0, move="blockade", state="ready")
    st.put("mx-canoes", at=P(-1200, -1700), facing=180, state="ready", width=400, move="sail")
    st.note(P(-1600, -1500), "Stake ambush takes two launches", "death")

    st.step("stjohn", "The day of St John", "24 June 1521", """
        On the feast of St John Cuauhtemoc struck all three camps together. At the Tacuba causeway Alvarado
        charged his horse across a gap; canoes filled it behind him, and he was wounded, with five men dragged
        to the temple. Cortes meanwhile drove for the market square, but left a canal unfilled; a Mexica
        counterattack wounded him, nearly took him, killed Olea and Guzman who covered him, and seized sixty-five
        Spaniards. Their sacrifice was watched from the camps.""", date=when(1521, 6, 24), light="day")
    st.put("mx-main", at=P(-200, -1000), width=700, depth=500, move="attack", state="engaged")
    st.put("olid", state="engaged")
    st.put("alv", state="engaged")
    st.put("olid", at=P(-300, -3250), move="retreat", state="engaged")
    st.put("olid-al", at=P(-300, -3550), move="retreat", state="wavering")
    st.note(P(-3200, 1050), "Alvarado wounded at the gap", "death")
    st.note(P(-300, -2500), "Cortes wounded; 65 captured", "capture")

    st.step("attrition", "Allies depart, famine begins", "late June - July 1521", """
        After the defeat, many Spanish allies went home, leaving only a few hundred in the three camps. When the
        prophecy that the Spaniards would die in ten days failed, many returned. Cortes changed method: each
        district captured was razed and its rubble used to fill canals and gaps, letting foot and horse fight in
        formation instead of in the alleys. Water became brackish, food ran out, and smallpox and dysentery
        spread within the city.""", date=when(1521, 7), light="day")
    st.put("alv", at=P(-2300, 700), move="advance", state="engaged", width=100, depth=45)
    st.put("alv-al", at=P(-2600, 750), move="advance", state="engaged")
    st.put("olid", at=P(-300, -2200), move="advance", state="engaged")
    st.put("olid-al", at=P(-300, -2500), move="advance", state="engaged")
    st.put("mx-main", at=P(-100, -300), width=800, depth=500, state="engaged", move="retreat")
    st.put("sand", at=P(-250, -2000), move="advance", facing=0)
    st.put("sand-al", at=P(-250, -2300), facing=0, move="advance")
    st.note(P(-200, -400), "Famine and disease in the city", "event")

    st.step("closing", "Into the city", "July 1521", """
        With the brigantines free on the lake and all three causeways held, the Spaniards advanced into the main
        quarters. Sandoval's division, moved up to the northern side, helped seal the last roads. Cortes
        also sent columns against tributaries trying to relieve the city. Cuauhtemoc retained the support of
        Tlatelolco, but no outside help reached him.""", date=when(1521, 7, 20), light="day")
    st.put("alv", at=P(-1500, 450), move="advance")
    st.put("alv-al", at=P(-1800, 500), move="advance")
    st.put("olid", at=P(-300, -1200), move="advance")
    st.put("olid-al", at=P(-300, -1500), move="advance")
    st.put("sand", at=P(500, 3500), facing=180, move="march", conjectural=True)
    st.put("sand-al", at=P(650, 3800), facing=180, move="march", conjectural=True)
    st.put("mx-main", at=P(-100, 100), width=700, depth=500)
    st.put("brigs", at=P(1800, 800), facing=0, move="sail")

    st.step("tlatelolco", "Advance on the Tlatelolco market", "early August 1521", """
        Cortes ordered all three camps toward the great market at Tlatelolco. Alvarado's men reached it first,
        and Gutierrez de Badajoz climbed the temple, set it alight and planted Spanish banners. Cortes and
        Sandoval joined them after four more days of fighting. Tlatelolco refused to switch sides, and the
        Mexica still performed their rites, including a sacrifice of seventy captives.""", date=when(1521, 8, 3), light="day")
    st.put("alv", at=P(-900, 1500), move="attack", facing=45)
    st.put("alv-al", at=P(-1200, 1450), move="attack", facing=45)
    st.put("olid", at=P(-300, -200), move="advance", state="engaged")
    st.put("olid-al", at=P(-300, -500), move="advance", state="engaged")
    st.put("sand", at=P(0, 2400), move="attack", facing=180)
    st.put("sand-al", at=P(150, 2700), move="attack", facing=180)
    st.put("mx-tlat", state="engaged")
    st.put("mx-main", at=P(-300, 800), width=500, depth=400, state="wavering", move="retreat")
    st.note(P(-590, 1810), "Temple burned, banners raised", "event")

    st.step("laststand", "The last stand and the flight", "c. 12-13 August 1521", """
        Cuauhtemoc and the nobles judged resistance hopeless after several failed offers of peace. Cortes
        ordered Sandoval to attack the last pocket where the ruler had withdrawn. Hundreds of canoes crowded
        the lake in flight, and the brigantines closed in. Cuauhtemoc tried to escape with family and
        valuables in fifty canoes, but was taken by Sandoval's launches and brought to Cortes.""", date=when(1521, 8, 13), light="day")
    st.put("mx-main", state="routed", move="retreat", at=P(-100, 300), width=500)
    st.put("mx-tlat", state="routed")
    st.put("mx-canoes", at=P(1200, 2000), facing=90, move="rout", state="routed", width=700)
    st.put("brigs", at=P(1000, 2300), facing=0, move="attack", state="engaged")
    st.put("cuauh", at=P(-200, 1700), label="Cuauhtemoc", frame=True)
    st.put("cuauh", at=P(1000, 2100), move="flee" if False else "rout")
    st.note(P(1000, 2100), "Cuauhtemoc captured on the lake", "capture")

    st.step("surrender", "The surrender and its cost", "13 August 1521", """
        The city fell on 13 August. Cortes pressed for the gold lost on the Noche Triste, and little was found.
        Perhaps forty thousand inhabitants were dead or captive, and the survivors streamed out for three days.
        The Spanish allies, especially Tlaxcalans, killed and plundered even after the surrender, to the dismay
        of Cortes. Almost all the nobility were dead; the empire was gone, and New Spain rose on its ruins.""",
        date=when(1521, 8, 13), light="dusk")
    st.put("alv", at=P(-700, 1300), state="ready", facing=90)
    st.put("sand", at=P(500, 1800), state="ready", move="advance")
    st.put("olid", at=P(-300, 300), state="ready", facing=0)
    st.put("mx-main", state="destroyed")
    st.put("mx-tlat", state="destroyed")
    st.put("cuauh", at=P(1000, 2100), state="captured", by="sp")
    st.note(P(-100, 600), "City destroyed; c. 40,000 dead or captive", "event")

    return st.doc(slug="siege-of-tenochtitlan", kind="siege",
        entity={"name": "Siege of Tenochtitlan", "wikidata": "Q593267"},
        title="Siege of Tenochtitlan", date_label="26 May - 13 August 1521", year=1520,
        intro="""In 1521 Hernan Cortes and his native allies besieged Tenochtitlan, the capital of the Mexica, an island
            city in Lake Texcoco joined to the shore by three causeways. After the disaster of the Noche Triste, Cortes
            rebuilt his force around Tlaxcala, won over lakeshore peoples, and had thirteen brigantines built to
            contest the water. The siege opened in late May with three land divisions at Tacuba, Coyoacan and
            Iztapalapa. It lasted roughly eighty days, through desperate fights on the causeways, a near disaster
            on St John's day, famine and smallpox in the city, and a final push to Tlatelolco. It ended with the
            capture of Cuauhtemoc on 13 August.""",
        outcome="Spanish and Tlaxcalan victory: Tenochtitlan fell, the Aztec Empire ended and New Spain began.",
        uncertainty="""Causeway routes, the island outline, the Chapultepec aqueduct and all intermediate positions of
            the three divisions are reconstructed from the narrative sources and marked conjectural; the sources give no
            exact days for most phases. Strengths are contested: allied totals range from 50,000 to 200,000, and
            the death toll from 100,000 to 240,000. The sources are largely Spanish, with Cortes and Diaz at their head.""",
        sources=[{"title": "Fall of Tenochtitlan - Wikipedia", "url": "https://en.wikipedia.org/wiki/Fall_of_Tenochtitlan", "kind": "web"}],
        sides=[
            {"id": "sp", "name": "Spanish and allies", "color": "#b91c1c",
             "polity": {"name": "Spanish Empire", "wikidata": "Q80702"},
             "commanders": [{"name": "Hernan Cortes", "wikidata": "Q7326", "role": "commander"},
                            {"name": "Pedro de Alvarado", "wikidata": "Q210900", "role": "Tacuba division"},
                            {"name": "Cristobal de Olid", "wikidata": "Q550491", "role": "Coyoacan division"},
                            {"name": "Gonzalo de Sandoval", "wikidata": "Q1374269", "role": "Iztapalapa division"}],
             "strength": "900-1,300 Spaniards, 86 horse, 13 brigantines, 50,000-200,000 allies",
             "losses": "450-860 Spaniards, c. 20,000 allies"},
            {"id": "mx", "name": "Mexica", "color": "#0f766e",
             "polity": {"name": "Aztec Empire", "wikidata": "Q2608489"},
             "commanders": [{"name": "Cuauhtemoc", "wikidata": "Q297050", "role": "tlatoani"}],
             "strength": "c. 80,000 warriors, 400 canoes",
             "losses": "100,000+ killed, 300 canoes sunk"}],
        units=[
            {"id": "cortes-base", "side": "sp", "kind": "army", "label": "Cortes at Texcoco"},
            {"id": "brigs", "side": "sp", "kind": "fleet", "label": "13 brigantines", "strength": "13 vessels"},
            {"id": "alv", "side": "sp", "kind": "infantry", "label": "Alvarado's Spaniards", "strength": "c. 200"},
            {"id": "alv-al", "side": "sp", "kind": "light_infantry", "label": "Tlaxcalan allies", "strength": "c. 8,000"},
            {"id": "olid", "side": "sp", "kind": "infantry", "label": "Olid's Spaniards", "strength": "c. 225"},
            {"id": "olid-al", "side": "sp", "kind": "light_infantry", "label": "Olid's allies", "strength": "c. 8,000"},
            {"id": "sand", "side": "sp", "kind": "infantry", "label": "Sandoval's Spaniards", "strength": "c. 190"},
            {"id": "sand-al", "side": "sp", "kind": "light_infantry", "label": "Chalca, Huejotzinca", "strength": "c. 8,000"},
            {"id": "mx-main", "side": "mx", "kind": "light_infantry", "label": "Tenochtitlan garrison", "strength": "c. 80,000"},
            {"id": "mx-tlat", "side": "mx", "kind": "light_infantry", "label": "Tlatelolco"},
            {"id": "mx-canoes", "side": "mx", "kind": "fleet", "label": "War canoes", "strength": "400"},
            {"id": "cuauh", "side": "mx", "kind": "commander", "label": "Cuauhtemoc"}],
        terrain=[
            {"id": "island", "kind": "island", "label": "Island city (outline)", "area": ISLAND, "conjectural": True},
            {"id": "cw-tacuba", "kind": "road", "label": "Tacuba causeway", "line": TACUBA_CW, "conjectural": True},
            {"id": "cw-south", "kind": "road", "label": "Coyoacan causeway", "line": SOUTH_CW, "conjectural": True},
            {"id": "cw-izta", "kind": "road", "label": "Iztapalapa causeway", "line": IZTA_CW, "conjectural": True},
            {"id": "cw-north", "kind": "road", "label": "Tepeyac causeway", "line": NORTH_CW, "conjectural": True},
            {"id": "aqueduct", "kind": "road", "label": "Chapultepec aqueduct", "line": AQUEDUCT, "conjectural": True},
            {"id": "templo", "kind": "site", "label": "Templo Mayor", "at": P(0, 0)},
            {"id": "tlat", "kind": "site", "label": "Tlatelolco market", "at": P(-590, 1810)},
            {"id": "chap", "kind": "site", "label": "Chapultepec", "at": CHAPUL},
            {"id": "tacuba", "kind": "town", "label": "Tacuba", "at": TACUBA}])
