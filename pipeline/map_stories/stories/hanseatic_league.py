"""The Hanseatic League, 1241–1598 — map story builder (schema 3, trade_route, ambient).

Anchors: town coordinates from `places` (OSM). Sea lanes are drawn with
`route` through named straits and capes (the Sound, the Skagerrak, the Gulf of
Finland, the Neva–Ladoga–Volkhov waterway); they show which towns traded with
which, not the courses ships steered. Facts from the Wikipedia articles
"Hanseatic League" (Foundation, Commercial expansion, Major trade goods,
Zenith, Rise of rival powers, End of the Hansa, Kontors), "Danish–Hanseatic
War (1361–1370)" and "Battle of Helsingborg (1362)", read through `research`.
"""

from pipeline.map_stories.geo import offset
from pipeline.map_stories.layout import Story, ent, route, when

LUBECK = (10.6847, 53.8664)
HAMBURG = (10.0013, 53.5502)
COLOGNE = (6.9600, 50.9384)
VISBY = (18.2980, 57.6379)
NOVGOROD = (31.2758, 58.5210)
BRUGES = (3.2268, 51.2086)
BERGEN = (5.3233, 60.3975)
LONDON = (-0.0906, 51.5114)
DANZIG = (18.6540, 54.3483)
RIGA = (24.1052, 56.9494)
REVAL = (24.7450, 59.4370)
STRALSUND = (13.0821, 54.3096)
COPENHAGEN = (12.5701, 55.6867)
HELSINGBORG = (12.7037, 56.0442)
THORN = (18.5966, 53.0145)
LUNEBURG = (10.4079, 53.2487)
LAUENBURG = (10.5514, 53.3790)
AMSTERDAM = (4.8925, 52.3731)
ANTWERP = (4.3997, 51.2211)
SKANOR = (12.8518, 55.4146)

# Sea lanes, waypoints in sailing order (all bidirectional trades).
SOUND = (12.68, 55.95)
SKAGEN = (10.75, 57.85)
LANES = {
    "lubeck-hamburg": route(LUBECK, (10.3734, 53.8097), HAMBURG),
    "baltic-novgorod": route(LUBECK, (11.3, 54.45), (14.6, 54.95), (17.2, 56.6), VISBY, (21.6, 58.9), (23.5, 59.55),
                             (27.0, 60.05), (29.9, 59.95), (31.1, 60.25), (32.3, 60.0), (32.3, 59.6), (31.6, 58.9), NOVGOROD, sea=True),
    "prussia-livonia": route(LUBECK, (11.3, 54.45), (14.6, 54.95), (18.2, 54.75), DANZIG, (19.5, 54.95), (20.9, 56.4),
                             (21.9, 57.75), (23.4, 57.4), RIGA, sea=True),
    "north-sea": route(HAMBURG, (9.4, 53.85), (8.4, 53.95), (6.6, 53.75), (4.8, 53.15), (3.6, 51.75), BRUGES, (2.1, 51.35),
                       (0.9, 51.47), LONDON, sea=True),
    "bergen": route(LUBECK, (11.3, 54.45), (12.3, 55.3), SOUND, (11.6, 56.9), SKAGEN, (8.6, 58.1), (5.8, 58.9), (5.0, 60.0),
                    BERGEN, sea=True),
    "vistula": route(THORN, (18.75, 53.45), (18.82, 53.95), DANZIG),
    "stecknitz": route(LUBECK, (10.69, 53.63), LAUENBURG, LUNEBURG),
    "dutch-baltic": route(AMSTERDAM, (5.1, 53.35), (7.4, 55.2), (8.3, 57.2), SKAGEN, (11.6, 56.9), SOUND, (12.9, 55.2),
                          (15.5, 55.1), DANZIG, sea=True),
}


def build() -> dict:
    st = Story()

    def conjectural() -> None:
        st.s["moves"][-1]["conjectural"] = True

    # 1 ── 1241
    st.step("lubeck-hamburg", "Lübeck and Hamburg join hands", "1241", """
        By the early thirteenth century German merchants sailing from Lübeck had joined the Gotlanders of
        Visby in the trade to Novgorod, the great market of the Russian north, where they kept a trading
        yard of their own, the Peterhof. In 1241 Lübeck, with its harbour on the Baltic and its fishing
        grounds, allied with Hamburg, which commanded the routes carrying salt from Lüneburg. The short land
        link between the two towns let goods pass from one sea to the other without sailing round Denmark.""",
        date=when(1241), camera={"center": [20.0, 56.5], "zoom": 4.4},
        entities=[ent("Lübeck", "Q2843", role="leading Baltic port"), ent("Hamburg", "Q1055", role="North Sea port, ally from 1241"),
                  ent("Visby", "Q54757", role="Gotland hub of the earlier trade"), ent("Peterhof", "Q875560", role="German yard in Novgorod")])
    for fid in ("lubeck", "hamburg", "visby", "novgorod", "lubeck-hamburg", "baltic-novgorod"):
        st.state(fid, active=True)
    st.put("cog-east", start=offset(LUBECK, east=40_000, north=40_000), move="trade", via=LANES["baltic-novgorod"][3:12],
           at=offset(VISBY, east=-20_000, north=0), mlabel="cloth and salt east, furs and wax west")

    # 2 ── 1266–1282
    st.step("london", "A charter in London", "1266–1282", """
        In the west the merchants of Cologne already held privileges in England. In 1266 King Henry III
        granted the Hansa of Lübeck and Hamburg a charter of their own, and in 1282 the Cologne and Baltic
        groups joined to form a single Hanseatic colony in London, later known as the Steelyard, beside
        London Bridge. Bruges in Flanders became the other western pole of the trade. In the east the
        merchants twice blockaded Novgorod, in 1268 and 1277–1278, to defend their privileges there.""",
        date=when(1266, end=(1282,)), camera={"center": [6.0, 53.5], "zoom": 5.0},
        entities=[ent("Henry III of England", "Q160311", role="granted the 1266 charter"), ent("Steelyard", "Q445923", role="Hanseatic yard in London"),
                  ent("Cologne", "Q365", role="Rhineland Hansa town"), ent("Bruges", "Q12994", role="Flemish market")])
    for fid in ("cologne", "london", "bruges", "north-sea"):
        st.state(fid, active=True)
    st.hide("cog-east")
    st.put("cog-west", start=offset(HAMBURG, east=-60_000, north=40_000), move="trade", via=LANES["north-sea"][3:-4],
           at=offset(LONDON, east=40_000, north=-6_000), mlabel="grain, furs and wax west; wool and cloth east")

    # 3 ── 1347–1356
    st.step("kontore", "Kontore and a diet", "1347–1356", """
        By the middle of the fourteenth century the four great foreign trading houses, the Kontore at
        Novgorod, Bergen, Bruges and London, were organised corporations with their own treasuries, courts and
        seals. At Bergen the Germans traded grain for dried stockfish, and in Scania their seasonal stations
        salted the herring of the Sound. In 1347 the Bruges Kontor divided its members into three regional
        thirds, and in 1356 a diet of the towns met at Lübeck. The Black Death had just struck many of the
        towns in 1349 and 1350.""",
        date=when(1347, end=(1356,)), camera={"center": [12.0, 56.5], "zoom": 4.4},
        entities=[ent("Bryggen", "Q153430", role="Hanseatic Kontor in Bergen"), ent("Bruges", "Q12994", role="Kontor; statute of 1347"),
                  ent("Gdańsk", "Q1792", role="Prussian Hansa town"), ent("Riga", "Q1773", role="Livonian Hansa town"),
                  ent("Black Death", "Q42005", role="struck the towns in 1349–1350")])
    for fid in ("bergen", "bergen-lane", "scania", "danzig", "riga", "reval", "prussia-livonia"):
        st.state(fid, active=True)
    st.hide("cog-west")
    st.put("cog-bergen", start=offset(LUBECK, east=50_000, north=50_000), move="trade", via=LANES["bergen"][4:-3],
           at=offset(BERGEN, east=-25_000, north=-15_000), mlabel="grain north, stockfish south")

    # 4 ── 1361–1362
    st.step("visby-falls", "Valdemar IV takes Gotland", "1361–1362", """
        In July 1361 King Valdemar IV of Denmark landed on Gotland and took Visby, opening a war with the
        Hanseatic towns over Gotland, Scania and the Sound. The Baltic towns struck back, but on 8 July 1362
        the Danish fleet beat theirs off Helsingborg, and the Lübeck mayor Johann Wittenborg who had led it
        was later tried and executed at home. With the Sound contested, the herring fair in Scania and the
        voyages to Bergen were disrupted, and a truce in 1365 favoured Denmark.""",
        date=when(1361, 7, end=(1362, 7)), camera={"center": [15.0, 56.3], "zoom": 5.3},
        entities=[ent("Valdemar IV of Denmark", "Q216630", role="took Visby, 1361"), ent("Denmark", "Q35", show=True),
                  ent("Danish–Hanseatic War", "Q317210", role="1361–1370"), ent("Battle of Helsingborg", "Q3503678", role="Danish victory, 8 July 1362"),
                  ent("Johann Wittenborg", "Q102185", role="defeated Hanseatic commander")])
    st.state("visby", state="captured", held_by="denmark", label="Visby (Danish from 1361)")
    st.state("bergen-lane", state="disrupted")
    st.state("scania", state="contested")
    st.hide("cog-bergen")
    st.put("danish-fleet", at=offset(HELSINGBORG, east=-12_000, north=-4_000))
    st.put("hansa-fleet", start=offset(LUBECK, east=50_000, north=50_000), move="sail", via=[(12.3, 55.3)],
           at=offset(HELSINGBORG, east=-16_000, north=-22_000), mlabel="Hanseatic fleet", state="routed")
    st.note(offset(HELSINGBORG, east=-30_000, north=8_000), "Danish victory, 8 July 1362", "clash")

    # 5 ── 1367–1369
    st.step("confederation", "The Confederation of Cologne", "1367–1369", """
        Angered by the truce, the Prussian towns, Holland and Zeeland, and in the end the Wendish towns around
        Lübeck, bound themselves together at Cologne in November 1367. In 1368 their ships sacked Copenhagen
        and raided the Danish and Norwegian coasts, Valdemar left his kingdom, and in 1369 Helsingborg castle
        fell. Control of the Sound passed to the allied towns.""",
        date=when(1367, 11, end=(1369,)), camera={"center": [11.5, 55.0], "zoom": 5.4},
        entities=[ent("Confederation of Cologne", "Q883978", role="alliance of November 1367"), ent("Copenhagen", "Q1748", role="sacked 1368"),
                  ent("Helsingborg", "Q25411", role="castle taken 1369"), ent("Denmark", "Q35", show=True)])
    st.hide("danish-fleet")
    st.put("hansa-fleet", state="ready", move="attack", via=[(12.2, 55.2)], at=offset(COPENHAGEN, east=9_000, north=-3_000))
    st.put("dutch-ships", start=(4.4, 53.4), move="sail", via=[(7.4, 55.2), (8.3, 57.2), SKAGEN, (11.6, 56.9)],
           at=offset(HELSINGBORG, east=-14_000, north=8_000), mlabel="Holland and Zeeland")
    st.state("copenhagen", active=True, state="burning")
    st.state("helsingborg", active=True, state="captured", held_by="hansa")

    # 6 ── 24 May 1370
    st.step("stralsund", "The Peace of Stralsund", "24 May 1370", """
        At Stralsund on 24 May 1370 Denmark made peace on the towns' terms. For fifteen years they held the
        fortresses on the Scanian shore of the Sound and a share of their revenues, their privileges in the
        Scanian herring trade were confirmed, and they gained a say over the next Danish king. The treaty
        marked the height of Hanseatic power; the lanes through the Sound reopened, and Gotland stayed
        Danish.""",
        date=when(1370, 5, 24), camera={"center": [12.5, 55.5], "zoom": 5.4},
        entities=[ent("Treaty of Stralsund", "Q524952", role="signed 24 May 1370"), ent("Stralsund", "Q4065", role="where the peace was made")])
    st.hide("dutch-ships")
    st.put("hansa-fleet", move="sail", via=[(12.6, 55.0)], at=offset(STRALSUND, east=12_000, north=22_000))
    st.state("stralsund", active=True)
    st.state("copenhagen", state=None)
    st.state("bergen-lane", state=None)
    st.state("scania", state="held", held_by="hansa", label="Scania (Hanseatic for 15 years)")

    # 7 ── 1398
    st.step("canal-and-pirates", "A canal, pirates and Gotland", "1391–1398", """
        Between 1391 and 1398 Lübeck dug the Stecknitz Canal toward Lauenburg on the Elbe, giving Lüneburg salt a
        water route to its harbour. The Baltic had become unsafe: the Victual Brothers, privateers first hired
        in a war over the Swedish crown, seized Visby and preyed on shipping. In 1398 the Teutonic Order, backed
        by the Prussian towns, drove them out of Gotland, and that year a consortium of Hanseatic towns handed
        back Stockholm, which it had governed since 1395.""",
        date=when(1391, end=(1398,)), camera={"center": [14.5, 55.5], "zoom": 4.9},
        entities=[ent("Stecknitz Canal", "Q452461", role="opened 1398"), ent("Victual Brothers", "Q509392", role="privateers"),
                  ent("State of the Teutonic Order", "Q156020", role="took Gotland, 1398", show=True), ent("Lüneburg", "Q3920", role="salt town")])
    st.hide("hansa-fleet")
    st.state("stecknitz", active=True, state="new")
    st.state("luneburg", active=True)
    st.state("visby", state="captured", held_by=None, label="Visby (Teutonic Order, 1398)")

    # 8 ── 1438–1441
    st.step("dutch-rivals", "The Dutch break in", "1438–1441", """
        In the fifteenth century the Dutch and English pressed into Baltic trade. Lübeck took over the Sound
        toll in 1438, and in the Dutch–Hanseatic War of 1438–1441, fought mostly by privateers of the Wendish
        towns, the merchants of Amsterdam won free access to the Baltic. Prussian towns such as Danzig, which
        lived by shipping grain and timber west, gained from the Dutch carriers, whose freight was cheaper
        than the Hansa's.""",
        date=when(1438, end=(1441,)), camera={"center": [11.0, 55.0], "zoom": 4.6},
        entities=[ent("Amsterdam", "Q727", role="won access to the Baltic"), ent("Gdańsk", "Q1792", role="Prussian grain port")])
    st.state("stecknitz", state=None)
    st.state("amsterdam", active=True)
    st.state("dutch-baltic", active=True, state="new")
    st.put("dutch-ships", state="ready", start=offset(AMSTERDAM, east=20_000, north=60_000), move="trade",
           via=LANES["dutch-baltic"][6:-6], at=offset(DANZIG, east=-20_000, north=30_000), mlabel="Dutch grain ships")

    # 9 ── 1494
    st.step("novgorod-closed", "Ivan III closes the Peterhof", "1494", """
        In 1494 Ivan III of Moscow, master of Novgorod since 1478, closed the Peterhof and sent its merchants,
        only 49 by then, to Moscow. The fur trade turned toward Leipzig and the Russian business moved to Riga,
        Reval and Pskov; when the yard reopened in 1514, Novgorod was no longer a great market. In the south
        Baltic, grain from Poland now came down the Vistula to Danzig, about 10,000 short tons a year by the
        late fifteenth century.""",
        date=when(1494), camera={"center": [22.5, 56.5], "zoom": 4.6},
        entities=[ent("Ivan III of Russia", "Q171185", role="closed the Kontor"), ent("Peterhof", "Q875560", role="closed 1494"),
                  ent("Toruń", "Q47554", role="Vistula grain town"), ent("Gdańsk", "Q1792", role="grain port")])
    st.hide("dutch-ships")
    st.state("dutch-baltic", state=None)
    st.state("novgorod", state="abandoned", label="Peterhof (closed 1494)")
    st.state("baltic-novgorod", state="disrupted")
    st.state("thorn", active=True)
    st.state("vistula", active=True, value_n=9100, value_label="≈10,000 short tons of grain a year")

    # 10 ── 1520–1598
    st.step("steelyard-closes", "The Kontore close", "1520–1598", """
        As Atlantic trade grew, the western Kontore withered. The Bruges house moved to Antwerp in 1520, as the
        Zwin inlet that served Bruges silted up, and the Antwerp house closed in 1593. In 1597 Elizabeth I
        expelled the Hansa from London and the Steelyard was shut the next year. Only the Bergen Kontor lived
        on, until 1754, while the princes of Denmark, Sweden and the German lands reined in the towns.""",
        date=when(1520, end=(1598,)), camera={"center": [6.0, 55.0], "zoom": 4.5},
        entities=[ent("Elizabeth I of England", "Q7207", role="expelled the Hansa, 1597"), ent("Antwerp", "Q12892", role="Kontor 1520–1593"),
                  ent("Steelyard", "Q445923", role="closed 1598"), ent("Bryggen", "Q153430", role="lasted until 1754")])
    st.state("bruges", state="abandoned", label="Bruges (moved to Antwerp, 1520)")
    st.state("antwerp", active=True, state="abandoned", label="Antwerp Kontor (1520–1593)")
    st.state("london", state="abandoned", label="Steelyard (closed 1598)")
    st.state("north-sea", state="disrupted")

    def town(fid: str, kind: str, at, label: str, name: str, qid: str, **extra) -> dict:  # noqa: ANN001
        return {"id": fid, "kind": kind, "label": label, "at": list(at), "entity": ent(name, qid), "side": "hansa", "active": False, **extra}

    features = [
        town("lubeck", "city", LUBECK, "Lübeck", "Lübeck", "Q2843"),
        town("hamburg", "city", HAMBURG, "Hamburg", "Hamburg", "Q1055"),
        town("cologne", "city", COLOGNE, "Cologne", "Cologne", "Q365"),
        town("visby", "market", VISBY, "Visby", "Visby", "Q54757", goods=["furs", "wax"]),
        town("novgorod", "market", NOVGOROD, "Peterhof, Novgorod", "Peterhof", "Q875560", goods=["furs", "wax", "cloth", "salt"]),
        town("bruges", "market", BRUGES, "Bruges Kontor", "Bruges", "Q12994", goods=["cloth"]),
        town("london", "market", LONDON, "Steelyard, London", "Steelyard", "Q445923", goods=["wool", "cloth"]),
        town("bergen", "market", BERGEN, "Bryggen, Bergen", "Bryggen", "Q153430", goods=["stockfish", "grain"]),
        town("danzig", "port", DANZIG, "Danzig", "Gdańsk", "Q1792", goods=["grain", "timber"]),
        town("riga", "port", RIGA, "Riga", "Riga", "Q1773", goods=["flax", "wax", "timber"]),
        town("reval", "port", REVAL, "Reval", "Tallinn", "Q1770"),
        town("stralsund", "city", STRALSUND, "Stralsund", "Stralsund", "Q4065"),
        town("thorn", "city", THORN, "Thorn", "Toruń", "Q47554", goods=["grain", "copper", "iron"]),
        town("luneburg", "mine", LUNEBURG, "Lüneburg salt", "Lüneburg", "Q3920", goods=["salt"]),
        {"id": "scania", "kind": "market", "label": "Scania herring fair", "at": list(SKANOR), "goods": ["herring", "salt"], "active": False},
        {"id": "copenhagen", "kind": "city", "label": "Copenhagen", "at": list(COPENHAGEN), "entity": ent("Copenhagen", "Q1748"), "side": "denmark", "active": False},
        {"id": "helsingborg", "kind": "site", "label": "Helsingborg castle", "at": list(HELSINGBORG), "entity": ent("Helsingborg", "Q25411"), "side": "denmark", "active": False},
        {"id": "amsterdam", "kind": "port", "label": "Amsterdam", "at": list(AMSTERDAM), "entity": ent("Amsterdam", "Q727"), "side": "dutch", "active": False},
        {"id": "antwerp", "kind": "market", "label": "Antwerp Kontor", "at": list(ANTWERP), "entity": ent("Antwerp", "Q12892"), "side": "hansa", "active": False},
        {"id": "lubeck-hamburg", "kind": "route", "route_kind": "road", "label": "Lübeck–Hamburg land link", "line": LANES["lubeck-hamburg"],
         "goods": ["salt", "cloth", "furs", "wax"], "bidirectional": True, "side": "hansa", "active": False},
        {"id": "baltic-novgorod", "kind": "route", "route_kind": "trade", "label": "Lübeck–Visby–Novgorod", "line": LANES["baltic-novgorod"],
         "goods": ["furs", "wax", "cloth", "salt"], "bidirectional": True, "active": False},
        {"id": "prussia-livonia", "kind": "route", "route_kind": "trade", "label": "To Prussia and Livonia", "line": LANES["prussia-livonia"],
         "goods": ["grain", "timber", "flax", "wax"], "bidirectional": True, "active": False},
        {"id": "north-sea", "kind": "route", "route_kind": "trade", "label": "Hamburg–Bruges–London", "line": LANES["north-sea"],
         "goods": ["cloth", "wool", "grain", "furs", "wax"], "bidirectional": True, "active": False},
        {"id": "bergen-lane", "kind": "route", "route_kind": "trade", "label": "Through the Sound to Bergen", "line": LANES["bergen"],
         "goods": ["grain", "stockfish"], "bidirectional": True, "active": False},
        {"id": "vistula", "kind": "route", "route_kind": "trade", "label": "Vistula grain", "line": LANES["vistula"], "goods": ["grain"], "active": False},
        {"id": "stecknitz", "kind": "route", "route_kind": "trade", "label": "Stecknitz Canal", "line": LANES["stecknitz"],
         "entity": ent("Stecknitz Canal", "Q452461"), "goods": ["salt"], "active": False},
        {"id": "dutch-baltic", "kind": "route", "route_kind": "trade", "label": "Dutch Baltic trade", "line": LANES["dutch-baltic"],
         "goods": ["grain", "timber"], "bidirectional": True, "side": "dutch", "active": False},
    ]

    return st.doc(
        schema=3,
        slug="hanseatic-league",
        kind="trade_route",
        entity={"name": "Hanseatic League", "wikidata": "Q42908"},
        title="The Hanseatic League, 1241–1598",
        date_label="13th–16th century",
        year=1241,
        period={"start": {"year": 1241}, "end": {"year": 1598}},
        ambient=True,
        camera={"center": [14.0, 56.0], "zoom": 4.2},
        intro=(
            "The Hanseatic League, or Hansa, was a network of German merchant guilds and trading towns that dominated "
            "the sea trade of the Baltic and the North Sea from the thirteenth to the fifteenth century. Led by Lübeck, "
            "it carried furs, wax, grain, timber and fish west and cloth and salt east, and kept privileged trading houses, "
            "the Kontore, at Novgorod, Bergen, Bruges and London. It never had a standing army, a treasury or a permanent "
            "government, yet in 1370 it forced the king of Denmark to terms. This map follows its main lanes from the "
            "alliance of Lübeck and Hamburg to the closing of the London Steelyard."
        ),
        outcome="The Hansa peaked after the Peace of Stralsund in 1370, then lost ground to Dutch shipping and territorial princes; its last diet met in 1669.",
        uncertainty=(
            "The sea lanes are drawn through named straits and capes to show which towns traded with which, not the courses "
            "ships steered, and goods are listed only where the sources name them. The Hansa had no fixed membership, so the "
            "towns shown are a selection. Grain volumes are given only for the Vistula, the one route with a figure in the "
            "sources used. The founding date is a convention: the word Hanse appears in 1267, and a general diet first met "
            "around 1356, though some place the first diets around 1300."
        ),
        legend=[
            {"swatch": "#b45309", "label": "Hanseatic town, Kontor or lane", "style": "dot"},
            {"swatch": "#b91c1c", "label": "Denmark", "style": "dot"},
            {"swatch": "#ea580c", "label": "Holland and Zeeland", "style": "line"},
        ],
        sources=[
            {"title": "Hanseatic League — Wikipedia", "url": "https://en.wikipedia.org/wiki/Hanseatic_League", "kind": "web"},
            {"title": "Danish–Hanseatic War (1361–1370) — Wikipedia", "url": "https://en.wikipedia.org/wiki/Danish%E2%80%93Hanseatic_War_(1361%E2%80%931370)", "kind": "web"},
            {"title": "Battle of Helsingborg (1362) — Wikipedia", "url": "https://en.wikipedia.org/wiki/Battle_of_Helsingborg_(1362)", "kind": "web"},
        ],
        sides=[
            {"id": "hansa", "name": "Hanseatic towns", "color": "#b45309", "polity": {"name": "Hanseatic League", "wikidata": "Q42908"}},
            {"id": "denmark", "name": "Denmark", "color": "#b91c1c", "polity": {"name": "Denmark", "wikidata": "Q35"},
             "commanders": [{"name": "Valdemar IV", "wikidata": "Q216630", "role": "King of Denmark"}]},
            {"id": "dutch", "name": "Holland and Zeeland", "color": "#ea580c"},
        ],
        units=[
            {"id": "cog-east", "side": "hansa", "kind": "merchant_ship", "label": "Cogs bound for Visby"},
            {"id": "cog-west", "side": "hansa", "kind": "merchant_ship", "label": "Cogs bound for London"},
            {"id": "cog-bergen", "side": "hansa", "kind": "merchant_ship", "label": "Cogs bound for Bergen"},
            {"id": "hansa-fleet", "side": "hansa", "kind": "fleet", "label": "Hanseatic fleet"},
            {"id": "danish-fleet", "side": "denmark", "kind": "fleet", "label": "Danish fleet"},
            {"id": "dutch-ships", "side": "dutch", "kind": "fleet", "label": "Dutch ships"},
        ],
        features=features,
    )
