"""The Black Death, 1346–1353 — map story builder (schema 3, epidemic, ambient).

Anchors: town coordinates from `places` (OSM) or, where OSM matched a namesake
(Gaza, Damascus, Cairo, Mecca, Tunis), the city's Wikidata P625. Dates and
mortality figures from the Wikipedia "Black Death" article (Europe; West Asia
and North Africa; Deaths; Persecutions), researched through the cached
`research` command. The shaded regions are schematic hulls around the towns
with documented outbreaks, not mapped extents, so they are `conjectural`.
"""

from pipeline.map_stories.geo import hull_region, merge_rings, offset
from pipeline.map_stories.layout import Story, ent, when

# ── places: (lon, lat), cluster for the spread hulls ─────────────────────────
PLACES = {
    "caffa": ((35.3754, 45.0337), "steppe", "Caffa"),
    "astrakhan": ((48.0326, 46.3498), "steppe", "Hajji Tarkhan"),
    "constantinople": ((28.9759, 41.0064), "aegean", "Constantinople"),
    "messina": ((15.5542, 38.1938), "sicily", "Messina"),
    "alexandria": ((29.8952, 31.1992), "egypt", "Alexandria"),
    "cairo": ((31.2357, 30.0444), "egypt", "Cairo"),
    "genoa": ((8.9339, 44.4073), "italy", "Genoa"),
    "venice": ((12.3346, 45.4372), "italy", "Venice"),
    "pisa": ((10.4017, 43.7228), "italy", "Pisa"),
    "florence": ((11.2556, 43.7698), "italy", "Florence"),
    "siena": ((11.3308, 43.3188), "italy", "Siena"),
    "marseille": ((5.3778, 43.2964), "france", "Marseille"),
    "avignon": ((4.8059, 43.9493), "france", "Avignon"),
    "paris": ((2.3488, 48.8534), "france", "Paris"),
    "bordeaux": ((-0.5800, 44.8412), "france", "Bordeaux"),
    "tunis": ((10.1815, 36.8065), "maghreb", "Tunis"),
    "gaza": ((34.4668, 31.5017), "levant", "Gaza"),
    "damascus": ((36.2765, 33.5138), "levant", "Damascus"),
    "aleppo": ((37.1637, 36.1992), "levant", "Aleppo"),
    "mecca": ((39.8262, 21.4225), "hejaz", "Mecca"),
    "barcelona": ((2.1771, 41.3826), "iberia", "Barcelona"),
    "valencia": ((-0.3763, 39.4697), "iberia", "Valencia"),
    "melcombe": ((-2.4543, 50.6096), "england", "Melcombe"),
    "london": ((-0.1278, 51.5074), "england", "London"),
    "dublin": ((-6.2606, 53.3494), "ireland", "Dublin"),
    "strasbourg": ((7.7507, 48.5846), "germany", "Strasbourg"),
    "cologne": ((6.9600, 50.9384), "germany", "Cologne"),
    "vienna": ((16.3725, 48.2084), "germany", "Vienna"),
    "bergen": ((5.3259, 60.3943), "norway", "Bergen"),
    "hamburg": ((10.0013, 53.5502), "north", "Hamburg"),
    "lubeck": ((10.6847, 53.8664), "north", "Lübeck"),
    "copenhagen": ((12.5701, 55.6867), "north", "Copenhagen"),
    "stockholm": ((18.0711, 59.3251), "north", "Stockholm"),
    "pskov": ((28.3344, 57.8174), "russia", "Pskov"),
    "novgorod": ((31.2758, 58.5210), "russia", "Novgorod"),
    "moscow": ((37.6173, 55.7558), "russia", "Moscow"),
}
P = {k: v[0] for k, v in PLACES.items()}
#: Where each place's town is linked in the atlas (Wikidata, confirmed with `research --qids`).
TOWN_QID = {
    "caffa": ("Caffa", "Q4135566"), "constantinople": ("Constantinople", "Q16869"), "messina": ("Messina", "Q13666"),
    "alexandria": ("Alexandria", "Q87"), "cairo": ("Cairo", "Q85"), "genoa": ("Genoa", "Q1449"), "venice": ("Venice", "Q641"),
    "pisa": ("Pisa", "Q13375"), "florence": ("Florence", "Q2044"), "siena": ("Siena", "Q2751"), "marseille": ("Marseille", "Q23482"),
    "avignon": ("Avignon", "Q6397"), "paris": ("Paris", "Q90"), "tunis": ("Tunis", "Q3572"), "gaza": ("Gaza", "Q47492"),
    "damascus": ("Damascus", "Q3766"), "aleppo": ("Aleppo", "Q41183"), "mecca": ("Mecca", "Q5806"), "london": ("London", "Q84"),
    "strasbourg": ("Strasbourg", "Q6602"), "bergen": ("Bergen", "Q26793"), "hamburg": ("Hamburg", "Q1055"), "lubeck": ("Lübeck", "Q2843"),
    "pskov": ("Pskov", "Q2214"), "novgorod": ("Novgorod", "Q2235"), "moscow": ("Moscow", "Q649"),
}

#: Places with documented outbreaks, by step (the step where each first appears).
REACHED = [
    ["caffa", "astrakhan"],
    ["constantinople"],
    ["messina", "alexandria"],
    ["genoa", "venice", "pisa", "marseille", "avignon"],
    ["florence", "siena", "tunis", "gaza", "barcelona", "valencia", "paris", "melcombe"],
    ["damascus", "aleppo", "cairo", "mecca", "bordeaux", "london", "dublin"],
    ["strasbourg", "vienna", "cologne"],
    ["bergen"],
    ["hamburg", "lubeck", "copenhagen", "stockholm"],
    [],
    ["pskov", "novgorod"],
    ["moscow"],
]
#: How hard the plague was raging across the reached area, step by step (0–1).
INTENSITY = [0.35, 0.45, 0.55, 0.7, 0.85, 0.9, 0.8, 0.7, 0.6, 0.35, 0.4, 0.35]

#: Mortality where the sources give it: step index → place → (value_n, label).
MORTALITY = {
    4: {"florence": (60_000, "≈110,000 → 50,000 by 1351")},
    5: {"cairo": (200_000, "⅓–40% of ≈600,000 died"), "paris": (50_000, "about half of ≈100,000 died"),
        "london": (None, "perhaps 60% died")},
    8: {"hamburg": (None, "at least 60% died")},
}


def _hulls(places: list[str], buffer_km: float) -> list[list[list[float]]]:
    clusters: dict[str, list] = {}
    for p in places:
        clusters.setdefault(PLACES[p][1], []).append(P[p])
    return merge_rings(*[hull_region(pts, buffer_km if len(pts) > 1 else buffer_km * 0.8, max_points=20) for pts in clusters.values()])


def build() -> dict:
    st = Story()
    seen: list[str] = []

    def conjectural() -> None:
        """Mark the arrow just drawn as inferred."""
        st.s["moves"][-1]["conjectural"] = True

    def spread(i: int) -> None:
        """Feature state for step i: newly reached towns, older ones, both regions."""
        new = REACHED[i]
        for p in new:
            st.state(f"o-{p}", active=True, state="infected")
        for p in REACHED[i - 2] if i >= 2 else []:
            st.state(f"o-{p}", state="recovered")
        for p, (n, label) in MORTALITY.get(i, {}).items():
            st.state(f"o-{p}", state="peak", value_label=label, **({"value_n": n} if n else {}))
        seen.extend(new)
        st.state("reached", active=True, area=_hulls(seen, 160), intensity=INTENSITY[i])
        if new:
            st.state("raging", active=True, area=_hulls(new, 110), intensity=min(1.0, INTENSITY[i] + 0.1))
        else:
            st.state("raging", active=False)

    def towns(i: int, roles: dict[str, str] | None = None) -> list[dict]:
        roles = roles or {}
        return [ent(*TOWN_QID[p], role=roles.get(p, "outbreak")) for p in REACHED[i] if p in TOWN_QID]

    # 1 ── 1346
    st.step("horde-and-caffa", "Plague in the Horde and at Caffa", "1346", """
        Russian chronicles record a great pestilence in 1346 among the Tatars and the other peoples of the
        Golden Horde, in its towns on the lower Volga. That year Khan Jani Beg's army was besieging Caffa,
        the walled Genoese trading colony on the Crimean coast, and the disease broke out among the
        besiegers. The Piacenza notary Gabriele de' Mussi, writing soon afterwards, claimed the Tatars
        catapulted their dead over the walls; whether or not they did, rats and fleas could cross siege
        lines on their own, and the town was infected.""",
        date=when(1346), camera={"center": [40.5, 45.2], "zoom": 4.6},
        entities=[ent("Golden Horde", "Q79965", role="its army besieged Caffa", show=True), ent("Jani Beg", "Q735288", role="khan"),
                  ent("Caffa", "Q4135566", role="besieged Genoese colony"), ent("Republic of Genoa", "Q174306", role="Caffa's mother city")])
    st.put("horde-army", at=offset(P["caffa"], east=-30_000, north=35_000))
    st.put("galleys", at=offset(P["caffa"], east=6_000, north=-8_000))
    spread(0)

    # 2 ── summer 1347
    st.step("constantinople", "Ships carry it to Constantinople", "Summer 1347", """
        Genoese merchants escaping the Black Sea took the infection with them, and by the summer of 1347 it
        had reached Constantinople. The co-emperor John VI Kantakouzenos lost his thirteen-year-old son
        Andronikos to it and later wrote an account modelled on Thucydides' plague of Athens, remarking that
        it travelled by ship from one sea city to the next. The first outbreak in the capital went on for
        about a year.""",
        date=when(1347, 5, end=(1347, 8)), camera={"center": [32.0, 43.0], "zoom": 4.7},
        entities=[ent("Constantinople", "Q16869", role="outbreak"), ent("John VI Kantakouzenos", "Q37084", role="emperor; lost his son"),
                  ent("Byzantine Empire", "Q12544", show=True)])
    st.hide("horde-army")
    st.put("galleys", move="spread", via=[(31.5, 42.4)], at=offset(P["constantinople"], east=4_000, north=-6_000), mlabel="Genoese ships")
    spread(1)

    # 3 ── autumn 1347
    st.step("messina-alexandria", "Messina and Alexandria", "Autumn 1347", """
        In October 1347 twelve Genoese galleys put in at Messina in Sicily with sick and dying crews. The
        Messinese drove them out of the harbour, but too late: within weeks the disease was all over the
        island. That same autumn a merchant ship carrying slaves from Constantinople brought it to
        Alexandria, the great port of Mamluk Egypt. From these two footholds it would move into Italy,
        North Africa and the Levant.""",
        date=when(1347, 9, end=(1347, 12)), camera={"center": [24.0, 39.0], "zoom": 4.2},
        entities=[ent("Messina", "Q13666", role="first Sicilian outbreak"), ent("Alexandria", "Q87", role="first Egyptian outbreak"),
                  ent("Mamluk Sultanate", "Q282428", show=True)])
    st.put("galleys", move="spread", via=[(23.0, 36.2), (17.0, 37.6)], at=offset(P["messina"], east=6_000, north=-4_000), mlabel="twelve galleys")
    conjectural()
    st.put("slave-ship", start=offset(P["constantinople"], east=4_000, north=-6_000), move="spread", via=[(26.3, 39.6), (27.5, 34.0)],
           at=offset(P["alexandria"], east=0, north=12_000), mlabel="slave ship")
    spread(2)

    # 4 ── January–March 1348
    st.step("italy-and-provence", "Into Italy and up the Rhône", "January–March 1348", """
        Galleys from the east reached Genoa and Venice in January 1348, but it was Pisa, struck a few weeks
        later, that opened the way into inland Tuscany. Towards the end of January a galley turned away
        from Italy brought the plague to Marseille, and it moved up the Rhône to Avignon, then the seat of
        the papacy. Pope Clement VI stayed in the city, and his physician Guy de Chauliac described two
        forms of the disease: a fever with coughing of blood, and the swellings in the armpit and groin.""",
        date=when(1348, 1, end=(1348, 3)), camera={"center": [10.0, 42.5], "zoom": 4.9},
        entities=towns(3) + [ent("Pope Clement VI", "Q170863", role="stayed in Avignon"), ent("Guy de Chauliac", "Q469362", role="papal physician")])
    st.hide("slave-ship")
    st.put("galleys", move="spread", via=[(12.0, 39.6)], at=offset(P["genoa"], east=0, north=-15_000), mlabel="galleys from the east")
    conjectural()
    st.put("marseille-galley", start=offset(P["genoa"], east=0, north=-15_000), move="spread", via=[(7.3, 43.4)],
           at=offset(P["marseille"], east=0, north=-12_000), mlabel="galley turned away")
    conjectural()
    spread(3)

    # 5 ── April–June 1348
    st.step("spring-1348", "Tuscany, Tunis and the road to Paris", "April–June 1348", """
        Through the spring of 1348 the plague swept Tuscany. Florence, home to perhaps 110,000 to 120,000
        people a decade earlier, had about 50,000 by 1351, and Boccaccio set the storytellers of the
        Decameron in this year. In Siena the chronicler Agnolo di Tura wrote that he buried his five children
        himself. A ship from Sicily infected Tunis in April. By June the disease had crossed France to Paris
        and reached the ports of Aragon, and a ship had landed it at Melcombe in Dorset, its first foothold
        in England.""",
        date=when(1348, 4, end=(1348, 6)), camera={"center": [10.0, 42.0], "zoom": 3.9},
        entities=towns(4) + [ent("Giovanni Boccaccio", "Q1402", role="set the Decameron in this plague"), ent("Agnolo di Tura", "Q3606673", role="Sienese chronicler")])
    st.hide("marseille-galley")
    st.put("sicily-ship", start=offset(P["messina"], east=-8_000, north=-10_000), move="spread", via=[(12.6, 37.6)],
           at=offset(P["tunis"], east=10_000, north=12_000), mlabel="ship from Sicily")
    spread(4)

    # 6 ── July–December 1348
    st.step("autumn-1348", "Cairo, Syria, Paris and London", "July–December 1348", """
        In the second half of 1348 the plague reached Cairo, the largest city of the Mediterranean world.
        The boy sultan an-Nasir Hasan left the city, and between a third and two-fifths of its people died
        within eight months. Damascus was struck in July and Aleppo in October, and pilgrims carried it to
        Mecca. In the west Paris lost about half of its inhabitants, London was reached by the end of the
        year and Dublin earlier in the autumn. From Avignon, Clement VI condemned those who blamed the Jews,
        pointing out that Jews were dying too.""",
        date=when(1348, 7, end=(1348, 12)), camera={"center": [16.0, 40.0], "zoom": 3.2},
        entities=towns(5, {"cairo": "a third or more died", "mecca": "carried by pilgrims"}) + [ent("Mamluk Sultanate", "Q282428", show=True), ent("Pope Clement VI", "Q170863", role="protected the Jews")])
    st.hide("sicily-ship")
    st.hide("galleys")
    spread(5)

    # 7 ── January–June 1349
    st.step("german-lands", "The German lands and the pogroms", "January–June 1349", """
        In 1349 the epidemic spread across the German lands. Fear turned on the Jews, who were accused of
        poisoning wells: in Strasbourg about 2,000 were murdered in February, before the plague had even
        reached the town. Bands of flagellants went from town to town, whipping themselves in public
        penance. Vienna and the Rhineland were struck, and in England the disease worked north from the
        southern ports.""",
        date=when(1349, 1, end=(1349, 6)), camera={"center": [6.0, 50.0], "zoom": 4.0},
        entities=towns(6) + [ent("Strasbourg massacre", "Q476345", role="pogrom, 14 February 1349"), ent("Holy Roman Empire", "Q12548", show=True)])
    st.note(offset(P["strasbourg"], east=0, north=25_000), "c. 2,000 Jews murdered, Feb 1349", "death")
    spread(6)

    # 8 ── July–December 1349
    st.step("norway", "A ship to Norway", "July–December 1349", """
        In 1349 a ship arriving at Askøy, outside Bergen, brought the plague to Norway, and it spread from
        there into the country. In August the Jewish communities of Mainz and Cologne were destroyed. By
        the end of the year the disease was in Scotland, carried north from England, and it was moving on
        through the German and Low Countries towns.""",
        date=when(1349, 7, end=(1349, 12)), camera={"center": [5.0, 54.5], "zoom": 4.0},
        entities=towns(7, {"bergen": "first Norwegian outbreak"}) + [ent("Kingdom of Norway", "Q2196956", show=True)])
    st.put("bergen-ship", start=offset(P["london"], east=60_000, north=-20_000), move="spread", via=[(2.5, 53.4), (3.5, 58.5)],
           at=offset(P["bergen"], east=-14_000, north=8_000), mlabel="a ship, perhaps from England")
    conjectural()
    spread(7)

    # 9 ── 1350
    st.step("baltic", "The North Sea and the Baltic", "1350", """
        In 1350 the plague swept the North Sea and Baltic coasts. At least three in five people may have
        died in Hamburg and Bremen, and Lübeck, Denmark and Sweden were struck in turn. Some regions were
        hit far less hard: the evidence of pollen from farmland suggests that farming in parts of central
        and eastern Europe carried on almost undisturbed, while Scandinavia, France, western Germany and
        central Italy show signs of heavy loss.""",
        date=when(1350), camera={"center": [11.0, 56.5], "zoom": 4.2},
        entities=towns(8) + [ent("Hanseatic League", "Q42908", role="its towns were hit hard")])
    st.hide("bergen-ship")
    spread(8)

    # 10 ── 1351
    st.step("counting", "Counting the dead", "1351", """
        By 1351 the first wave had passed through most of western Europe. Agents of Clement VI were said to
        have counted 23,840,000 dead in Christian Europe, about a third of its people, though modern
        estimates run from a quarter to well over half. Sixty large and 150 smaller Jewish communities had
        been destroyed, and many survivors moved east to Poland, where King Casimir the Great received them.""",
        date=when(1351), camera={"center": [16.0, 46.0], "zoom": 3.4},
        entities=[ent("Pope Clement VI", "Q170863", role="his agents counted the dead")])
    spread(9)

    # 11 ── 1352
    st.step("pskov-novgorod", "Pskov and Novgorod", "1352", """
        In 1352 the plague reached the Russian lands from the west, striking Pskov and then Novgorod, the
        great trading republic whose market linked the Baltic to the Russian interior. Contemporary
        accounts describe a toll in the Russian towns much like that in western Europe.""",
        date=when(1352), camera={"center": [31.0, 57.0], "zoom": 4.9},
        entities=towns(10) + [ent("Novgorod Republic", "Q151536", show=True)])
    spread(10)

    # 12 ── 1353
    st.step("moscow", "Moscow", "1353", """
        In 1353 the epidemic reached Moscow. Grand Prince Simeon the Proud died of it in April, and his young
        sons and his brother Andrei died in the same outbreak. With Moscow the first great wave of the second
        plague pandemic had run its course across Europe, though the disease would return every few years
        for generations.""",
        date=when(1353), camera={"center": [33.0, 56.5], "zoom": 4.7},
        entities=towns(11) + [ent("Simeon of Moscow", "Q297102", role="grand prince; died of plague")])
    spread(11)

    features = [
        {"id": "reached", "kind": "region", "region_kind": "spread", "label": "Plague had reached", "area": _hulls(REACHED[0], 160),
         "active": False, "conjectural": True},
        {"id": "raging", "kind": "region", "region_kind": "affected", "label": "Newly struck", "area": _hulls(REACHED[0], 110),
         "active": False, "conjectural": True},
    ]
    for key, (at, _cluster, label) in PLACES.items():
        f = {"id": f"o-{key}", "kind": "outbreak", "label": label, "at": list(at), "active": False}
        if key in TOWN_QID:
            f["entity"] = ent(*TOWN_QID[key])
        features.append(f)

    return st.doc(
        schema=3,
        slug="black-death",
        kind="epidemic",
        entity={"name": "Black Death", "wikidata": "Q42005"},
        title="The Black Death, 1346–1353",
        date_label="1346–1353",
        year=1346,
        period={"start": {"year": 1346}, "end": {"year": 1353}},
        ambient=True,
        camera={"center": [16.0, 45.0], "zoom": 3.0},
        intro=(
            "The Black Death was the plague pandemic that crossed western Eurasia and North Africa between 1346 and "
            "1353, the deadliest in recorded history. It was caused by the bacterium Yersinia pestis, spread by the "
            "fleas of rats and other animals and, in its pneumonic form, from person to person. First reported among "
            "the Golden Horde and at the besieged Genoese port of Caffa in the Crimea, it moved along the sea lanes of "
            "Italian merchants to Constantinople, Sicily and Egypt, then inland along roads and rivers until it had "
            "reached Scandinavia and Russia. This map follows it half a year at a time, marking the towns where the "
            "sources date an outbreak; the shaded areas are schematic outlines drawn around those towns."
        ),
        outcome="Between a quarter and well over half of Europe's people died, and about a third of the Middle East's; the plague returned every few years for centuries.",
        uncertainty=(
            "Where the pandemic began is disputed. Tombstones near Lake Issyk-Kul record a 'pestilence' in 1338–1339 "
            "and ancient DNA from them carries the ancestral strain, but others place the source on the steppe north-west "
            "of the Caspian or further west. The story of corpses catapulted into Caffa rests on one writer who was not "
            "there. The ships' tracks drawn here are inferred from the ports they linked, and the shaded regions are hulls "
            "around documented outbreaks, not the true extent: some areas inside them were spared or lightly hit, and "
            "regional mortality varied widely. Dates for the Levant differ between accounts (some give 1347), and death "
            "tolls for single cities are estimates."
        ),
        alt_sites=[
            {"at": [75.2, 42.6], "label": "Issyk-Kul (Chüy valley)", "note": "1338–1339 'pestilence' graves with Y. pestis DNA"},
            {"at": [47.0, 45.5], "label": "North-west Caspian shore", "note": "Benedictow's suggested plague focus"},
        ],
        legend=[
            {"swatch": "#991b1b", "label": "Plague had reached (schematic)", "style": "fill"},
            {"swatch": "#c2410c", "label": "Newly struck this period", "style": "fill"},
            {"swatch": "#7f1d1d", "label": "Town with a dated outbreak", "style": "dot"},
        ],
        sources=[
            {"title": "Black Death — Wikipedia", "url": "https://en.wikipedia.org/wiki/Black_Death", "kind": "web"},
            {"title": "Black Death (Q42005) — Wikidata", "url": "https://www.wikidata.org/wiki/Q42005", "kind": "web"},
        ],
        sides=[],
        units=[
            {"id": "horde-army", "kind": "army", "label": "Jani Beg's army"},
            {"id": "galleys", "kind": "merchant_ship", "label": "Genoese galleys"},
            {"id": "slave-ship", "kind": "merchant_ship", "label": "Slave ship to Alexandria"},
            {"id": "marseille-galley", "kind": "merchant_ship", "label": "Galley to Marseille"},
            {"id": "sicily-ship", "kind": "merchant_ship", "label": "Ship from Sicily"},
            {"id": "bergen-ship", "kind": "merchant_ship", "label": "Ship to Bergen"},
        ],
        features=features,
    )
