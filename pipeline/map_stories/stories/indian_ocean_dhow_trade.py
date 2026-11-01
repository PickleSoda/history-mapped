"""Indian Ocean dhow trade, c. 500–977 — the map layer of a chronicle (schema 3, trade_route, ambient).

Chronicle: "Indian Ocean Dhow Trade, Ports and Monsoon Commerce (c. 500-1000 CE)"
(slug below, 59 entries, sequence_order 0–58). Each step is keyed to the entry it
illustrates by that entry's sequence_order as stored (0-based); entries without a
step keep the chronicle's default map. Facts from the chronicle's entries and the
Wikipedia article "Bandar Siraf" (Sasanian era, Islamic era), read through
`research`. Port coordinates are the towns' Wikidata P625 or well-known city
centres; sea lanes run through named capes and straits (`route`), and show which
ports traded with which, not ships' courses. Monsoon `wind` is set on the steps
whose voyage it drove.
"""

from pipeline.map_stories.geo import offset
from pipeline.map_stories.layout import Story, ent, route, when

CHRONICLE = "indian-ocean-dhow-trade-ports-and-monsoon-commerce-c-500-1000-ce"

SIRAF = (52.3461, 27.6658)
BASRA = (47.81, 30.515)
HORMUZ = (56.45, 26.45)
MUSCAT = (58.59, 23.61)
SOHAR = (56.7299, 24.342)
KHAMBHAT = (72.62, 22.31)
ADULIS = (39.6606, 15.2636)
YEMEN_COAST = (43.25, 13.32)
BAB = (43.40, 12.62)
ADEN = (45.0333, 12.80)
JEDDAH = (39.19, 21.49)
QUILON = (76.5864, 8.8853)
KODUNGALLUR = (76.22, 10.22)
COMORIN = (77.55, 7.85)
SRI_LANKA = (80.2, 5.7)
NICOBAR = (93.2, 7.4)
KEDAH = (100.36, 5.65)
MALACCA = (101.6, 2.3)
SINGAPORE = (104.0, 1.15)
PALEMBANG = (104.75, -2.99)
JAMBI = (103.60, -1.60)
CHAMPA = (109.4, 12.6)
GUANGZHOU = (113.26, 23.13)
TAMRALIPTI = (87.92, 22.30)
BELITUNG = (107.5952, -2.7608)
CIREBON_WRECK = (108.75, -6.20)
ZANZIBAR = (39.19, -6.16)
QANBALU = (39.6537, -5.1955)

LANES = {
    "gulf-gujarat": route(SIRAF, HORMUZ, (58.9, 24.4), (63.0, 24.6), (68.5, 22.6), KHAMBHAT, sea=True),
    "red-sea-india": route(ADULIS, BAB, (50.0, 12.8), (60.0, 12.5), (70.0, 10.8), KODUNGALLUR, (76.3, 9.0), COMORIN, SRI_LANKA, sea=True),
    "gulf-kollam": route(BASRA, (49.4, 29.0), SIRAF, HORMUZ, (57.4, 25.3), MUSCAT, (62.0, 20.5), (70.0, 12.0), QUILON, sea=True),
    "kollam-china": route(QUILON, COMORIN, SRI_LANKA, NICOBAR, KEDAH, MALACCA, SINGAPORE, (106.3, 6.0), CHAMPA, (111.6, 17.8),
                          (113.4, 21.9), GUANGZHOU, sea=True),
    "yijing": route(GUANGZHOU, (113.4, 21.9), (111.6, 17.8), CHAMPA, (106.3, 6.0), SINGAPORE, (104.9, -1.5), PALEMBANG, JAMBI,
                    MALACCA, KEDAH, NICOBAR, (90.5, 15.5), TAMRALIPTI, sea=True),
    "siraf-jeddah": route(SIRAF, HORMUZ, (57.4, 25.3), MUSCAT, (59.0, 21.0), (54.0, 15.5), ADEN, BAB, (41.0, 16.5), JEDDAH, sea=True),
    "siraf-east-africa": route(SIRAF, HORMUZ, (57.4, 25.3), MUSCAT, (59.0, 21.0), (54.0, 15.5), (51.6, 11.6), (49.0, 5.5),
                               (44.0, -0.5), (40.6, -4.4), QANBALU, ZANZIBAR, sea=True),
}

NE = {"from": 45, "strength": "strong", "label": "North-east monsoon (about Nov–Mar): carries ships south and west"}
SW = {"from": 225, "strength": "strong", "label": "South-west monsoon (about Jun–Sep): carries ships east and north"}


def build() -> dict:
    st = Story()

    def conjectural() -> None:
        st.s["moves"][-1]["conjectural"] = True

    # entry 0 ── c. 500
    st.step("gujarat-ware", "Gujarati pottery at Siraf", "c. 500", """
        Fragments of red polished ware made in Gujarat in the fifth and sixth centuries turn up along the
        northern shore of the Persian Gulf, and above all at Siraf. They show that under the Sasanian kings
        Gulf ships already traded with the harbours of the Gulf of Cambay. Siraf, whose story reaches back to
        Parthian times, probably served as the port of the inland city of Gor, and excavations there have found
        East African ivory and Indian stone.""",
        entry=0, date=when(500, end=(599,)), camera={"center": [62.0, 25.0], "zoom": 4.0},
        entities=[ent("Siraf", "Q1790789", role="Sasanian Gulf port"), ent("Sasanian Empire", "Q83891", show=True)])
    st.state("siraf", active=True)
    st.state("khambhat", active=True)
    st.state("gulf-gujarat", active=True)

    # entry 2 ── c. 525
    st.step("adulis", "Cosmas at Adulis", "c. 525", """
        Around 525 the Alexandrian merchant Cosmas was at Adulis, the Red Sea port of the kingdom of Aksum,
        while its king prepared a seaborne expedition against Dhu Nuwas, ruler of Himyar across the strait in
        Yemen. In his Christian Topography Cosmas later described the pepper ports of the Malabar coast and the
        island of Sri Lanka, where ships from India, Persia and Ethiopia met, though whether he sailed that far
        himself is uncertain.""",
        entry=2, date=when(525), camera={"center": [58.0, 12.0], "zoom": 3.7},
        entities=[ent("Cosmas Indicopleustes", "Q355633", role="merchant and writer"), ent("Adulis", "Q378940", role="Aksum's port"),
                  ent("Kingdom of Aksum", "Q139377", show=True), ent("Kaleb of Axum", "Q705378", role="King of Aksum"),
                  ent("Dhu Nuwas", "Q878766", role="King of Himyar"), ent("Himyarite Kingdom", "Q289577", show=True)])
    for fid in ("adulis", "kodungallur", "red-sea-india"):
        st.state(fid, active=True)
    st.put("aksum-fleet", start=offset(ADULIS, east=15_000, north=10_000), move="sail", via=[(41.6, 14.4)],
           at=offset(YEMEN_COAST, east=-20_000, north=0), mlabel="Aksum's expedition")
    conjectural()

    # entry 5 ── 636
    st.step("basra", "Basra is founded", "636", """
        In 636 (some accounts say 638) the caliph Umar founded Basra as a garrison camp for the Arab armies near
        the head of the Persian Gulf, and three years later it was laid out as a city of five districts. It grew
        into the great port of Iraq: in the ninth century goods bound for India and China were first shipped
        from Basra down to Siraf. Ibadi Islam, which arose at Basra, later became the creed of Oman's
        merchants.""",
        entry=5, date=when(636, end=(639,)), camera={"center": [52.0, 27.5], "zoom": 4.8},
        entities=[ent("Basra", "Q48195", role="founded 636"), ent("Umar", "Q8467", role="caliph"), ent("Rashidun Caliphate", "Q12490507", show=True)])
    st.hide("aksum-fleet")
    st.state("basra", active=True, state="founded")
    st.state("red-sea-india", active=False)

    # entry 8 ── 671
    st.step("yijing", "Yijing sails for India", "671–695", """
        In the winter of 671 the Tang monk Yijing left Guangzhou on a Persian ship and ran south before the
        north-east monsoon to Srivijaya on Sumatra, where he stayed months learning Sanskrit grammar. He went on
        by way of Kedah and the Nicobar Islands to Tamralipti near the mouth of the Ganges, and studied for
        years in India. On his way home he settled at Srivijaya to copy and translate Buddhist texts, and in
        695 he was welcomed back at Luoyang by Empress Wu Zetian.""",
        entry=8, date=when(671, end=(695,)), camera={"center": [101.0, 9.0], "zoom": 3.6}, wind=NE,
        entities=[ent("Yijing", "Q457629", role="pilgrim monk"), ent("Tang dynasty", "Q9683", show=True),
                  ent("Srivijaya", "Q234197", role="Buddhist centre on Sumatra", show=True)])
    st.state("basra", state=None)
    for fid in ("guangzhou", "palembang", "tamralipti", "yijing"):
        st.state(fid, active=True)
    st.put("yijing-ship", start=offset(GUANGZHOU, east=10_000, north=-60_000), move="sail", via=LANES["yijing"][2:-12],
           at=offset(PALEMBANG, east=30_000, north=40_000), mlabel="Yijing, 671")

    # entry 17 ── 30 October 758
    st.step("guangzhou-758", "Raiders sack Guangzhou", "30 October 758", """
        While the An Lushan rebellion tore the Tang empire apart, Arab and Persian raiders sacked Guangzhou on 30
        October 758 and left by sea. Two years later, rebels at Yangzhou on the Grand Canal killed thousands of
        Arab and Persian merchants in revenge. The foreign communities of the China ports lived at the mercy of
        Chinese politics, and Guangzhou would see far worse in 878.""",
        entry=17, date=when(758, 10, 30), camera={"center": [112.0, 21.0], "zoom": 4.6},
        entities=[ent("Guangzhou", "Q16572", role="sacked 758"), ent("An Lushan Rebellion", "Q253774", role="civil war in China")])
    st.hide("yijing-ship")
    st.state("yijing", active=False)
    st.state("palembang", active=False)
    st.state("tamralipti", active=False)
    st.state("guangzhou", state="burning")
    st.put("raiders", start=(114.6, 20.4), move="attack", via=[(113.9, 21.9)], at=offset(GUANGZHOU, east=12_000, north=-20_000),
           mlabel="Arab and Persian raiders")
    conjectural()

    # entry 19 ── 793–893
    st.step("oman", "The Ibadi imamate of Oman", "793–893", """
        From 793 to 893 the second Ibadi imamate ruled the coast of Oman, whose ports included Sohar, one of the
        richest harbours in the Gulf. Omani ships and sailors were found from East Africa to China, and Muscat on
        the same coast became the last watering place before ships bound for India struck out across the open
        Arabian Sea.""",
        entry=19, date=when(793, end=(893,)), camera={"center": [57.0, 24.0], "zoom": 5.2},
        entities=[ent("Sohar", "Q943270", role="Omani port"), ent("Ibadi Islam", "Q243551", role="creed of the imamate")])
    st.hide("raiders")
    st.state("guangzhou", state=None)
    st.state("sohar", active=True)
    st.state("muscat", active=True)

    # entry 22 ── 825–849
    st.step("quilon", "Quilon is founded", "825–849", """
        By the tradition of the Kerala Christians, the East Syriac bishops Mar Sabor and Mar Proth settled at
        Quilon (Kollam) with their followers, and in 825 the town was founded with the sanction of the ruler of
        Venad; the Kollam era calendar counts its years from then. In 849 the Quilon copper plates granted
        privileges to the Christian merchant Maruvan Sapir Iso and his church. Quilon became the Indian landfall
        of ships sailing from Muscat to China.""",
        entry=22, date=when(825, end=(849,)), camera={"center": [76.0, 10.0], "zoom": 5.0},
        entities=[ent("Kollam", "Q321475", role="founded 825"), ent("Mar Sabor", "Q18936000", role="East Syriac bishop"),
                  ent("Mar Proth", "Q18936002", role="East Syriac bishop")])
    st.state("quilon", active=True, state="founded")

    # entry 25 ── c. 830
    st.step("belitung", "The Belitung wreck", "c. 830", """
        Around 830 a dhow built of planks sewn together with cord sank off Belitung island in the Gelasa Strait,
        between Sumatra and Borneo. It was carrying a cargo of Tang ceramics from China toward the Strait of
        Malacca; one Changsha bowl aboard bears a date equal to 826. Found in 1998, the wreck shows the kind of
        Arab ship that carried the China trade, and a cargo much of which was made for buyers in the Islamic
        world.""",
        entry=25, date=when(830), camera={"center": [108.5, 8.0], "zoom": 4.0}, wind=NE,
        entities=[ent("Belitung shipwreck", "Q3589078", role="sank c. 830"), ent("Dhow", "Q171799", role="sewn-plank ship")])
    st.state("quilon", state=None)
    st.state("belitung", active=True)
    st.put("dhow", start=offset(GUANGZHOU, east=10_000, north=-60_000), move="sail", via=[(111.6, 17.8), CHAMPA, (106.3, 2.5)],
           at=offset(BELITUNG, east=8_000, north=8_000), mlabel="from China, c. 830", state="sunk")
    conjectural()

    # entry 30 ── 851
    st.step("sulaiman", "Sulaiman the Merchant sails to China", "851", """
        In 851 the Siraf merchant Sulaiman made the voyage to Guangzhou, which the Arabs called Khanfu, and
        marvelled at its porcelain. The account of China and India attributed to him sets out the route: goods
        went from Basra to Siraf, on to Muscat, across the open sea to Kollam, round Sri Lanka and through the
        Strait of Malacca to China. Siraf had just been rebuilt and enlarged into the leading entrepôt of the
        Gulf, with one of the earliest congregational mosques in Iran.""",
        entry=30, date=when(851), camera={"center": [82.0, 15.0], "zoom": 2.7}, wind=SW,
        entities=[ent("Sulaiman al-Tajir", "Q9347981", role="Siraf merchant"), ent("Siraf", "Q1790789", role="leading Gulf entrepôt"),
                  ent("Guangzhou", "Q16572", role="Khanfu"), ent("Tang dynasty", "Q9683", show=True)])
    st.state("belitung", active=False)
    st.hide("dhow")
    st.state("siraf", state="new", label="Siraf (rebuilt in the 9th century)")
    st.state("gulf-kollam", active=True)
    st.state("kollam-china", active=True)
    st.state("gulf-gujarat", active=False)
    st.put("sulaiman-ship", start=offset(SIRAF, east=40_000, north=-30_000), move="trade",
           via=LANES["gulf-kollam"][4:-1] + LANES["kollam-china"][1:-2], at=offset(GUANGZHOU, east=10_000, north=-60_000),
           mlabel="Sulaiman, 851")

    # entry 35 ── 878–879
    st.step("huang-chao", "Huang Chao takes Guangzhou", "878–879", """
        In 878 the rebel army of Huang Chao, which had been ravaging the Tang lands since the mid-870s, took
        Guangzhou after a siege and massacred its inhabitants, ending the foreign merchant communities there.
        Arab writers looked back on it as the moment the direct trade between the Gulf and China broke down;
        the Tang dynasty itself fell in 907.""",
        entry=35, date=when(878, end=(879,)), camera={"center": [112.5, 22.0], "zoom": 4.8},
        entities=[ent("Huang Chao", "Q714113", role="rebel leader"), ent("Huang Chao Rebellion", "Q620621", role="874–884"),
                  ent("Guangzhou", "Q16572", role="massacre of 878")])
    st.hide("sulaiman-ship")
    st.state("siraf", state=None, label=None)
    st.state("guangzhou", state="destroyed")
    st.state("kollam-china", state="disrupted")

    # entry 39 ── c. 900
    st.step("abu-zayd", "To Jeddah and Zanzibar", "c. 900", """
        Around 900 Abu Zayd, himself a merchant of Siraf, wrote that Sirafi ships now traded with Jeddah on the
        Red Sea and with Zanzibar in East Africa. The trade with China had shrunk since the massacre at
        Guangzhou, he said, though Chinese coins still passed from hand to hand in Siraf. Ships bound for East
        Africa ran south-west before the north-east monsoon and came home on the south-west.""",
        entry=39, date=when(900), camera={"center": [50.0, 10.0], "zoom": 3.3}, wind=NE,
        entities=[ent("Abu Zayd Hasan al-Sirafi", "Q12178010", role="Siraf merchant and writer"), ent("Jeddah", "Q374365", role="Red Sea port"),
                  ent("Zanzibar", "Q2222874", role="East African port")])
    for fid in ("jeddah", "zanzibar", "siraf-jeddah", "siraf-east-africa"):
        st.state(fid, active=True, state="new")
    st.state("guangzhou", state="recovered", label="Guangzhou (trade reduced)")

    # entry 43 ── 908–932
    st.step("siraf-wealth", "The wealth of Siraf", "908–932", """
        According to the later historian Ibn al-Balkhi, goods worth 2.53 million dinars a year passed through
        Siraf between 908 and 932. Istakhri, writing shortly before 950, listed its trade in ebony, ivory,
        sandalwood and other aromatics, bamboo, spices, paper, aloes, camphor, ambergris and precious stones,
        besides the pearls of the nearby fisheries. Its merchants lived in tall houses of teak from East Africa
        and fired brick, on which one might spend 30,000 dinars.""",
        entry=43, date=when(908, end=(932,)), camera={"center": [52.5, 27.0], "zoom": 5.0},
        entities=[ent("Siraf", "Q1790789", role="2.53 million dinars a year"), ent("Ibn al-Balkhi", "Q3648073", role="historian")])
    for fid in ("jeddah", "zanzibar", "siraf-jeddah", "siraf-east-africa"):
        st.state(fid, state=None)
    st.state("siraf", state="peak", value_n=2_530_000, value_label="2.53 million dinars of goods a year")

    # entry 45 ── 916–926
    st.step("masudi", "Al-Masudi in East Africa", "916–926", """
        Between 916 and 926 the historian and traveller al-Masudi sailed to Qanbalu, an island off East Africa,
        and found ships of Siraf and Oman trading there, at the far south-western end of the Gulf merchants'
        world. Qanbalu is usually identified with Pemba, though the chronicle and some writers place it on
        Madagascar.""",
        entry=45, date=when(916, end=(926,)), camera={"center": [46.0, 5.0], "zoom": 3.6}, wind=NE,
        entities=[ent("al-Masudi", "Q168705", role="historian and traveller")])
    st.state("qanbalu", active=True)
    st.state("siraf", state=None, value_n=None, value_label=None)
    st.put("masudi-ship", start=offset(MUSCAT, east=40_000, north=-30_000), move="sail", via=LANES["siraf-east-africa"][-14:-3],
           at=offset(QANBALU, east=30_000, north=10_000), mlabel="al-Masudi")
    conjectural()

    # entry 52 ── c. 970
    st.step("cirebon", "The Cirebon wreck", "c. 970", """
        Around 970 a ship sank in the Java Sea off Cirebon with a cargo of Chinese ceramics, glassware and metal
        ingots. Like the Belitung ship a century and a half earlier, it shows the Southeast Asian sea lanes busy
        with mixed cargoes moving between China, the Malay world and the ports further west, a century after the
        direct Gulf–China run had broken down.""",
        entry=52, date=when(970), camera={"center": [108.0, 0.0], "zoom": 4.4},
        entities=[ent("Cirebon shipwreck", "Q3589079", role="sank c. 970")])
    st.hide("masudi-ship")
    st.state("cirebon", active=True)

    # entry 54 ── 971
    st.step("sohar-sacked", "The Buyids sack Sohar", "971", """
        In 971 the Buyids, the Iranian dynasty that controlled Baghdad and Fars, sacked Sohar, one of the richest
        ports of the Gulf, and its trade went into decline. According to al-Maqdisi, many people of Siraf also
        moved to Oman once the Buyids took power in Fars.""",
        entry=54, date=when(971), camera={"center": [55.0, 25.5], "zoom": 5.0},
        entities=[ent("Sohar", "Q943270", role="sacked 971"), ent("Buyid dynasty", "Q273874", role="sacked Sohar", show=True)])
    st.state("cirebon", active=False)
    st.state("sohar", state="burning")

    # entry 56 ── 977
    st.step("siraf-earthquake", "Earthquake at Siraf", "977", """
        In 977 an earthquake badly damaged Siraf. The geographer al-Maqdisi, who disapproved of the town's luxury,
        called it a fitting punishment from God. Siraf survived as a port for centuries more, but its great days
        were passing: in the following century pirates from Qays preyed on its ships and Gulf traffic began to
        bypass it for Basra.""",
        entry=56, date=when(977), camera={"center": [52.5, 27.5], "zoom": 5.2},
        entities=[ent("Siraf", "Q1790789", role="earthquake of 977")])
    st.state("sohar", state="destroyed")
    st.state("siraf", state="disrupted", label="Siraf (earthquake, 977)")

    def port(fid: str, at, label: str, kind: str = "port", name: str | None = None, qid: str | None = None, **extra) -> dict:  # noqa: ANN001
        f = {"id": fid, "kind": kind, "label": label, "at": list(at), "active": False, **extra}
        if qid:
            f["entity"] = ent(name or label, qid)
        return f

    features = [
        port("siraf", SIRAF, "Siraf", name="Siraf", qid="Q1790789",
             goods=["pearls", "ebony", "ivory", "sandalwood", "spices", "aloes", "camphor", "ambergris", "precious stones"]),
        port("basra", BASRA, "Basra", qid="Q48195"),
        port("muscat", MUSCAT, "Muscat"),
        port("sohar", SOHAR, "Sohar", qid="Q943270"),
        port("khambhat", KHAMBHAT, "Gulf of Cambay", goods=["red polished ware"]),
        port("adulis", ADULIS, "Adulis", qid="Q378940"),
        port("kodungallur", KODUNGALLUR, "Malabar ports", name="Malabar Coast", qid="Q473181", goods=["pepper"]),
        port("quilon", QUILON, "Quilon (Kollam)", name="Kollam", qid="Q321475"),
        port("guangzhou", GUANGZHOU, "Guangzhou (Khanfu)", name="Guangzhou", qid="Q16572", goods=["porcelain", "ceramics"]),
        port("palembang", PALEMBANG, "Srivijaya (Palembang)", name="Srivijaya", qid="Q234197"),
        port("tamralipti", TAMRALIPTI, "Tamralipti"),
        port("jeddah", JEDDAH, "Jeddah", qid="Q374365"),
        port("zanzibar", ZANZIBAR, "Zanzibar", qid="Q2222874"),
        port("qanbalu", QANBALU, "Qanbalu (Pemba?)", conjectural=True),
        port("belitung", BELITUNG, "Belitung wreck", kind="site", name="Belitung shipwreck", qid="Q3589078", goods=["Tang ceramics"]),
        port("cirebon", CIREBON_WRECK, "Cirebon wreck", kind="site", name="Cirebon shipwreck", qid="Q3589079",
             goods=["Chinese ceramics", "glassware", "ingots"], conjectural=True),
        {"id": "gulf-gujarat", "kind": "route", "route_kind": "trade", "label": "Gulf–Cambay trade", "line": LANES["gulf-gujarat"],
         "goods": ["red polished ware"], "bidirectional": True, "active": False},
        {"id": "red-sea-india", "kind": "route", "route_kind": "trade", "label": "Red Sea to Malabar and Sri Lanka", "line": LANES["red-sea-india"],
         "goods": ["pepper"], "bidirectional": True, "active": False, "conjectural": True},
        {"id": "yijing", "kind": "route", "route_kind": "pilgrimage", "label": "Yijing's voyage", "line": LANES["yijing"],
         "entity": ent("Yijing", "Q457629"), "active": False},
        {"id": "gulf-kollam", "kind": "route", "route_kind": "trade", "label": "Basra–Siraf–Muscat–Kollam", "line": LANES["gulf-kollam"],
         "bidirectional": True, "active": False},
        {"id": "kollam-china", "kind": "route", "route_kind": "trade", "label": "Kollam–Malacca Strait–Guangzhou", "line": LANES["kollam-china"],
         "goods": ["porcelain", "ceramics"], "bidirectional": True, "active": False},
        {"id": "siraf-jeddah", "kind": "route", "route_kind": "trade", "label": "Siraf–Jeddah", "line": LANES["siraf-jeddah"],
         "bidirectional": True, "active": False},
        {"id": "siraf-east-africa", "kind": "route", "route_kind": "trade", "label": "Siraf–East Africa", "line": LANES["siraf-east-africa"],
         "goods": ["ivory", "ebony", "teak"], "bidirectional": True, "active": False},
    ]

    return st.doc(
        schema=3,
        slug="indian-ocean-dhow-trade",
        kind="trade_route",
        chronicle={"slug": CHRONICLE},
        title="Indian Ocean dhow trade, c. 500–977",
        date_label="c. 500–977",
        year=500,
        period={"start": {"year": 500}, "end": {"year": 988}},
        ambient=True,
        camera={"center": [78.0, 12.0], "zoom": 2.6},
        intro=(
            "Between the late Sasanian period and the end of the tenth century, ships of sewn planks, the dhows of "
            "the Persian Gulf, Oman and India, tied the ports of the Gulf and the Red Sea to India, Southeast Asia, China "
            "and East Africa. They sailed with the monsoons, the seasonal winds that blow from the south-west in summer and "
            "from the north-east in winter, so a voyage to China and back took the better part of two years. This layer "
            "maps the chronicle's entries that the map can show: the rise of Basra, Siraf, Sohar and Quilon, the pilgrim "
            "Yijing's voyage, the route described by Sulaiman the Merchant, the wrecks that preserve the cargoes, and the "
            "blows that fell on Guangzhou, Sohar and Siraf."
        ),
        outcome="By the late tenth century the direct Gulf–China run had broken up into shorter legs, and the Gulf's trade was shifting from Siraf and Sohar.",
        uncertainty=(
            "Sea lanes are drawn through named capes and straits to show which ports traded with which, not the courses "
            "ships steered; the Red Sea–Malabar lane rests on Cosmas's description, and he may not have sailed it himself. "
            "Qanbalu is placed on Pemba, its usual identification, though the chronicle follows writers who put it on "
            "Madagascar; the Cirebon wreck is placed approximately. Some dates are traditional: the founding of Quilon in "
            "825 and of Basra in 636 (or 638). The monsoon arrows show the season that drove each step's voyage, not the "
            "weather on a given day."
        ),
        legend=[
            {"swatch": "#b45309", "label": "Trade lane", "style": "line"},
            {"swatch": "#047857", "label": "Pilgrim's voyage", "style": "line"},
            {"swatch": "#0e7490", "label": "Port", "style": "dot"},
        ],
        sources=[
            {"title": "Indian Ocean Dhow Trade, Ports and Monsoon Commerce (c. 500-1000 CE) — atlas chronicle", "kind": "secondary"},
            {"title": "Bandar Siraf — Wikipedia", "url": "https://en.wikipedia.org/wiki/Bandar_Siraf", "kind": "web"},
        ],
        sides=[],
        units=[
            {"id": "aksum-fleet", "kind": "fleet", "label": "Aksumite expedition"},
            {"id": "yijing-ship", "kind": "merchant_ship", "label": "Yijing's ship"},
            {"id": "raiders", "kind": "fleet", "label": "Arab and Persian raiders"},
            {"id": "dhow", "kind": "merchant_ship", "label": "Belitung dhow"},
            {"id": "sulaiman-ship", "kind": "merchant_ship", "label": "Sulaiman's ship"},
            {"id": "masudi-ship", "kind": "merchant_ship", "label": "Al-Masudi's ship"},
        ],
        features=features,
    )
