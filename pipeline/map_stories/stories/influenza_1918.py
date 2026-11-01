"""The 1918 influenza pandemic, 1918–1919 — map story builder (schema 3, epidemic, global, ambient).

Anchors: city coordinates (well-known city centres; Camp Funston from its
Wikidata P625 area at Fort Riley, Haskell County from P625). Dates, waves and
death tolls from the Wikipedia article "Spanish flu" (Potential origins, First
wave, Second wave, Third wave, Devastated communities), read through
`research`. Continental regions are schematic hulls around the cities the
sources name, shaded by how hard each wave hit; they are `conjectural`. Nothing
crosses the antimeridian: the Pacific islands are points.
"""

from pipeline.map_stories.geo import hull_region, offset
from pipeline.map_stories.layout import Story, ent, when

C = {
    "haskell": (-100.87, 37.57), "funston": (-96.79, 39.07), "new-york": (-73.94, 40.73), "boston": (-71.06, 42.36),
    "devens": (-71.61, 42.55), "philadelphia": (-75.17, 39.95), "chicago": (-87.63, 41.88), "st-louis": (-90.20, 38.63),
    "memphis": (-90.05, 35.15), "los-angeles": (-118.24, 34.05), "san-francisco": (-122.42, 37.77), "seattle": (-122.33, 47.61),
    "brest": (-4.486, 48.390), "etaples": (1.641, 50.518), "london": (-0.128, 51.507), "paris": (2.349, 48.853),
    "madrid": (-3.704, 40.417), "lisbon": (-9.139, 38.722), "rome": (12.496, 41.903), "berlin": (13.405, 52.520),
    "vienna": (16.373, 48.208), "wroclaw": (17.038, 51.108), "odessa": (30.723, 46.482), "stockholm": (18.071, 59.325),
    "oslo": (10.752, 59.913), "istanbul": (28.976, 41.006),
    "moscow": (37.617, 55.756), "arkhangelsk": (40.516, 64.540), "yekaterinburg": (60.605, 56.838), "omsk": (73.368, 54.989),
    "irkutsk": (104.281, 52.287),
    "freetown": (-13.234, 8.484), "accra": (-0.187, 5.604), "lagos": (3.379, 6.524),
    "cape-town": (18.424, -33.925), "kimberley": (24.763, -28.738), "johannesburg": (28.047, -26.204), "durban": (31.022, -29.859),
    "bulawayo": (28.583, -20.150), "nairobi": (36.817, -1.286), "addis-ababa": (38.747, 9.030),
    "bombay": (72.877, 19.076), "karachi": (67.001, 24.861), "delhi": (77.209, 28.614), "calcutta": (88.364, 22.573),
    "madras": (80.270, 13.083), "mashhad": (59.606, 36.297), "tehran": (51.389, 35.689), "tabriz": (46.292, 38.080),
    "shiraz": (52.531, 29.592), "guangzhou": (113.264, 23.129), "shanghai": (121.474, 31.230), "peking": (116.407, 39.904),
    "tokyo": (139.692, 35.690), "osaka": (135.502, 34.694), "hong-kong": (114.169, 22.319),
    "rio": (-43.173, -22.907), "sao-paulo": (-46.633, -23.551), "montevideo": (-56.165, -34.901), "buenos-aires": (-58.382, -34.604),
    "santiago": (-70.649, -33.449), "lima": (-77.043, -12.046),
    "melbourne": (144.963, -37.814), "sydney": (151.209, -33.869), "adelaide": (138.601, -34.929), "brisbane": (153.026, -27.470),
    "apia": (-171.760, -13.833), "suva": (178.441, -18.141), "nukualofa": (-175.198, -21.139), "antananarivo": (47.508, -18.879),
}

REGIONS = {
    "north-america": ("North America", ["seattle", "san-francisco", "los-angeles", "haskell", "funston", "memphis", "chicago", "st-louis", "philadelphia", "new-york", "boston"]),
    "europe": ("Europe", ["brest", "lisbon", "madrid", "london", "paris", "rome", "berlin", "vienna", "wroclaw", "odessa", "stockholm", "oslo"]),
    "russia": ("Russia and Siberia", ["moscow", "arkhangelsk", "yekaterinburg", "omsk", "irkutsk", "odessa"]),
    "west-africa": ("West Africa", ["freetown", "accra", "lagos"]),
    "southern-africa": ("Southern Africa", ["cape-town", "kimberley", "johannesburg", "durban", "bulawayo"]),
    "east-africa": ("East Africa", ["nairobi", "addis-ababa"]),
    "south-asia": ("India", ["karachi", "bombay", "madras", "calcutta", "delhi"]),
    "iran": ("Iran", ["tabriz", "tehran", "mashhad", "shiraz"]),
    "east-asia": ("China and Japan", ["guangzhou", "shanghai", "peking", "osaka", "tokyo"]),
    "south-america": ("South America", ["rio", "sao-paulo", "buenos-aires", "montevideo", "santiago", "lima"]),
    "australia": ("Australia", ["adelaide", "melbourne", "sydney", "brisbane"]),
}
#: Intensity (0–1) of each region at each of the 8 steps; 0 = not drawn.
WAVE = {
    "north-america": [0.2, 0.3, 0.1, 0.55, 1.0, 0.5, 0.5, 0.1],
    "europe": [0, 0.35, 0.2, 0.45, 0.9, 0.5, 0.6, 0.2],
    "russia": [0, 0, 0.1, 0.3, 0.75, 0.5, 0.3, 0.1],
    "west-africa": [0, 0, 0, 0.55, 0.8, 0.3, 0.1, 0],
    "southern-africa": [0, 0, 0, 0.4, 1.0, 0.3, 0.2, 0.35],
    "east-africa": [0, 0, 0, 0, 0.3, 0.6, 0.2, 0],
    "south-asia": [0, 0.15, 0.1, 0.5, 1.0, 0.6, 0.2, 0.1],
    "iran": [0, 0, 0, 0.2, 0.8, 0.7, 0.3, 0],
    "east-asia": [0, 0.1, 0.15, 0.1, 0.5, 0.4, 0.2, 0.2],
    "south-america": [0, 0, 0, 0, 0.5, 0.7, 0.5, 0.6],
    "australia": [0, 0, 0, 0, 0, 0, 0.7, 0.4],
}
#: Death tolls the sources give, as region labels: region → {step: label}.
REGION_LABELS = {
    "north-america": {1: "≈75,000 US flu deaths, Jan–Jun 1918", 4: "≈292,000 US deaths, Sep–Dec 1918", 6: "≈160,000 US deaths, Jan–Jun 1919"},
    "south-asia": {4: "at least 12 million dead (≈5%)"},
    "iran": {4: "0.9–2.4 million dead (8–22%)"},
    "southern-africa": {4: "≈300,000 dead in six weeks (6%)"},
}


def _area(key: str, places: list[str] | None = None, km: float = 350) -> list[list[float]]:
    return hull_region([C[p] for p in places or REGIONS[key][1]], km, max_points=24)


def build() -> dict:
    st = Story()

    def conjectural() -> None:
        st.s["moves"][-1]["conjectural"] = True

    def wave(i: int) -> None:
        for key in REGIONS:
            k, was = WAVE[key][i], WAVE[key][i - 1] if i else 0
            label = REGION_LABELS.get(key, {}).get(i)
            if k:
                st.state(key, active=True, intensity=k, **({"value_label": label} if label else {}))
            elif was:
                st.state(key, active=False)

    def city(fid: str, state: str = "infected", **extra) -> None:
        st.state(fid, active=True, state=state, **extra)

    # 1 ── January–March 1918
    st.step("kansas", "Kansas, early 1918", "January–March 1918", """
        The first cases that can be pinned down came from rural Haskell County in Kansas, where a local doctor
        reported a severe influenza in January and February 1918. On 4 March an army cook at Camp Funston, a
        huge training camp at Fort Riley some 320 km away, reported sick, and within days 522 men at the camp
        had followed. By 11 March the virus was in Queens, New York. The United States was at war, and its
        camps were filling with recruits bound for France.""",
        date=when(1918, 1, end=(1918, 3)), camera={"center": [-88.0, 39.5], "zoom": 3.6},
        entities=[ent("Haskell County", "Q374663", role="earliest reported cases"), ent("Camp Funston", "Q1029832", role="outbreak from 4 March 1918"),
                  ent("New York City", "Q60", role="cases by 11 March")])
    st.state("north-america", area=_area("north-america", ["haskell", "funston", "new-york"], 250))
    wave(0)
    city("haskell")
    city("funston", value_label="522 sick within days")
    city("new-york")

    # 2 ── April–May 1918
    st.step("across-the-atlantic", "Across the Atlantic", "April–May 1918", """
        Troops of the American Expeditionary Forces carried the disease from the training camps to the French
        ports, and by mid-April it was on the Western Front. It ran through France, Britain, Italy and Spain and
        in May reached Wrocław and Odessa, North Africa, India and Japan. This first wave was mild: in Madrid
        fewer than a thousand people died of it in May and June. But neutral Spain's uncensored newspapers
        reported it freely while the warring countries kept quiet, and so it became known as the Spanish flu.""",
        date=when(1918, 4, end=(1918, 5)), camera={"center": [-30.0, 42.0], "zoom": 2.2},
        entities=[ent("Brest", "Q12193", role="main landing port of US troops"), ent("Western Front", "Q152989", role="reached by mid-April"),
                  ent("Madrid", "Q2807", role="gave the pandemic its name")])
    st.state("north-america", area=_area("north-america"))
    wave(1)
    city("brest", state="infected")
    city("madrid", value_label="<1,000 deaths, May–June")
    st.put("aef-convoys", start=offset(C["new-york"], east=150_000, north=-60_000), move="spread", via=[(-50.0, 44.5), (-25.0, 47.5)],
           at=offset(C["brest"], east=-60_000, north=-20_000), mlabel="US troopships")

    # 3 ── June–July 1918
    st.step("first-wave-ebbs", "The first wave ebbs", "June–July 1918", """
        By June an outbreak was reported in China, and in July the Ottoman army recorded its first cases. The
        first wave had disrupted the war more than it had killed: three-quarters of the French troops, half
        the British forces and over 900,000 German soldiers fell sick. In the United States about 75,000
        influenza deaths were reported in the first half of 1918, against some 63,000 in the same months of
        1915. Through July the wave receded.""",
        date=when(1918, 6, end=(1918, 7)), camera={"center": [40.0, 35.0], "zoom": 1.6},
        entities=[ent("Ottoman Empire", "Q12560", role="first cases in July", show=True)])
    wave(2)
    st.hide("aef-convoys")
    city("istanbul")
    for fid in ("haskell", "funston", "new-york", "madrid"):
        st.state(fid, state="recovered")

    # 4 ── August–September 1918
    st.step("second-wave", "Brest, Boston and Freetown", "August–September 1918", """
        In the second half of August a far deadlier wave began. It probably reached Boston and Freetown in
        Sierra Leone on ships from Brest, where American troops or French naval recruits had likely brought it.
        From the Boston Navy Yard and Camp Devens it moved to other army camps and onto troopships bound for
        Europe; from Freetown it spread along the West African coast, rivers and railways. In September ships
        bringing men of the South African Native Labour Corps home from France landed it in South Africa. The
        Allied force in North Russia brought it to Arkhangelsk, and from the east it entered Iran at Mashhad.""",
        date=when(1918, 8, end=(1918, 9)), camera={"center": [-25.0, 15.0], "zoom": 1.7},
        entities=[ent("Brest", "Q12193", role="probable source of the second wave"), ent("Boston", "Q100", role="outbreak late August"),
                  ent("Fort Devens", "Q1413867", role="Camp Devens outbreak"), ent("Freetown", "Q3780", role="outbreak late August"),
                  ent("Cape Town", "Q5465", role="landing, September"), ent("Arkhangelsk", "Q1851", role="via the North Russia intervention"),
                  ent("Mashhad", "Q121157", role="entry into Iran")])
    wave(3)
    city("brest", state="peak")
    city("boston")
    city("freetown")
    city("cape-town")
    city("arkhangelsk")
    city("mashhad")
    st.put("brest-boston", start=offset(C["brest"], east=-60_000, north=-20_000), move="spread", via=[(-30.0, 46.5), (-55.0, 43.5)],
           at=offset(C["boston"], east=90_000, north=-50_000), mlabel="ships from Brest")
    conjectural()
    st.put("brest-freetown", start=offset(C["brest"], east=-70_000, north=-40_000), move="spread", via=[(-12.0, 40.0), (-20.0, 20.0)],
           at=offset(C["freetown"], east=-80_000, north=-30_000), mlabel="ships from Brest")
    conjectural()
    st.put("labour-corps", start=(-1.5, 48.0), move="spread", via=[(-12.0, 40.0), (-20.0, 10.0), (-2.0, -15.0), (12.0, -30.0)],
           at=offset(C["cape-town"], east=-60_000, north=-30_000), mlabel="Labour Corps ships")
    conjectural()
    st.put("north-russia", start=(-1.2, 55.5), move="spread", via=[(4.0, 62.5), (18.0, 70.5), (33.0, 69.8), (39.0, 66.0)],
           at=offset(C["arkhangelsk"], east=-40_000, north=30_000), mlabel="Allied intervention")
    conjectural()

    # 5 ── October 1918
    st.step("october", "October 1918, the deadliest month", "October 1918", """
        October 1918 was the worst month of the whole pandemic. The United States reported about 292,000
        deaths between September and December; a war-bond parade in Philadelphia on 28 September was followed
        by an outbreak that killed some 12,000. Bombay counted about 15,000 dead out of 1.1 million, and India
        as a whole lost at least 12 million people. South Africa lost about 300,000 in six weeks, among them
        almost a quarter of the diamond-mine workforce of Kimberley. The wave swept across Russia and reached
        China, Japan and Brazil.""",
        date=when(1918, 10), camera={"center": [20.0, 20.0], "zoom": 1.3},
        entities=[ent("Philadelphia", "Q1345", role="≈12,000 dead after the 28 September parade"), ent("Mumbai", "Q1156", role="≈15,000 dead"),
                  ent("British Raj", "Q129286", role="at least 12 million dead", show=True), ent("Union of South Africa", "Q193619", role="≈300,000 dead", show=True),
                  ent("Kimberley", "Q125905", role="a quarter of the mine workers died")])
    wave(4)
    for uid in ("brest-boston", "brest-freetown", "labour-corps", "north-russia"):
        st.hide(uid)
    st.state("south-america", area=_area("south-america", ["rio", "sao-paulo", "santiago"], 350))
    city("philadelphia", state="peak", value_n=12_000, value_label="≈12,000 dead")
    city("bombay", state="peak", value_n=15_000, value_label="≈15,000 of 1.1 million died")
    city("kimberley", state="peak", value_label="≈¼ of mine workers died")
    city("boston", state="peak")

    # 6 ── November–December 1918
    st.step("armistice", "Armistice and the Pacific", "November–December 1918", """
        Crowds celebrating the armistice of 11 November set off fresh outbreaks in places such as Lima and
        Nairobi, and the disease reached Ethiopia. Ships from New Zealand, which was slow to stop infected
        vessels leaving its ports, carried it to the Pacific islands: Tonga lost 8% of its people and Fiji 5%,
        about 9,000. In Western Samoa, under New Zealand occupation, nine in ten people were infected and
        three in ten adult men died. Iran, already in famine, lost between 8% and 22% of its population. By
        December the second wave was largely over.""",
        date=when(1918, 11, end=(1918, 12)), camera={"center": [10.0, 0.0], "zoom": 1.3},
        entities=[ent("Armistice of 11 November 1918", "Q253224", role="celebrations spread the flu"), ent("Lima", "Q2868", role="armistice outbreak"),
                  ent("Nairobi", "Q3870", role="armistice outbreak"), ent("Apia", "Q36260", role="Western Samoa, the worst hit"),
                  ent("Tonga", "Q678", role="8% died"), ent("Fiji", "Q712", role="≈9,000 died (5%)")])
    wave(5)
    st.state("south-america", area=_area("south-america"))
    city("lima")
    city("nairobi")
    city("apia", state="peak", value_label="90% infected; 30% of adult men died")
    city("nukualofa", state="peak", value_label="8% died")
    city("suva", state="peak", value_n=9_000, value_label="≈9,000 died (5%)")
    for fid in ("brest", "freetown", "cape-town", "arkhangelsk", "istanbul"):
        st.state(fid, state="recovered")
    for fid in ("philadelphia", "bombay", "kimberley", "boston"):
        st.state(fid, state="recovered")

    # 7 ── January–April 1919
    st.step("third-wave", "A third wave", "January–April 1919", """
        In January 1919 death rates jumped again in most American cities, from New York to San Francisco,
        before falling from mid-February; nearly 160,000 Americans died of influenza and pneumonia in the first
        half of the year. England and Wales peaked in early March, France and the Netherlands in February, and
        Spain suffered a strong recurrence from January to April. Australia, shielded through 1918 by a strict
        maritime quarantine, saw its first epidemic in Melbourne in January, peaking in mid-February before
        spreading to New South Wales and South Australia. Madagascar had its first cases in April.""",
        date=when(1919, 1, end=(1919, 4)), camera={"center": [40.0, 10.0], "zoom": 1.3},
        entities=[ent("Melbourne", "Q3141", role="Australia's first epidemic"), ent("Madagascar", "Q1019", role="first cases in April 1919")])
    wave(6)
    for fid in ("lima", "nairobi", "apia", "nukualofa", "suva", "mashhad"):
        st.state(fid, state="recovered")
    city("melbourne", state="peak")
    city("antananarivo")

    # 8 ── May–December 1919
    st.step("last-outbreaks", "The last outbreaks of 1919", "May–December 1919", """
        Through the rest of 1919 the pandemic flared on in pieces. Hong Kong had another outbreak in June and
        South Africa a third wave in its winter; Portugal suffered from March to September. Chile, first struck
        in October 1918, had a severe second wave that peaked in August 1919, and Montevideo had another
        outbreak from July to September. Tasmania stayed free until mid-August. Smaller recurrences followed
        in 1920, after which the virus settled into ordinary seasonal influenza.""",
        date=when(1919, 5, end=(1919, 12)), camera={"center": [30.0, 0.0], "zoom": 1.3},
        entities=[ent("Hong Kong", "Q8646", role="outbreak in June 1919"), ent("Chile", "Q298", role="second wave peaking August 1919", show=True),
                  ent("Montevideo", "Q1335", role="outbreak July–September 1919")])
    wave(7)
    st.state("melbourne", state="recovered")
    st.state("antananarivo", state="recovered")
    city("hong-kong")
    city("santiago", state="peak", value_label="second wave peaked August 1919")
    city("montevideo")

    labels = {
        "haskell": "Haskell County", "funston": "Camp Funston", "new-york": "New York", "brest": "Brest", "madrid": "Madrid",
        "istanbul": "Constantinople", "boston": "Boston", "freetown": "Freetown", "cape-town": "Cape Town", "arkhangelsk": "Arkhangelsk",
        "philadelphia": "Philadelphia", "bombay": "Bombay", "kimberley": "Kimberley", "mashhad": "Mashhad", "lima": "Lima",
        "nairobi": "Nairobi", "apia": "Apia, Western Samoa", "nukualofa": "Nuku'alofa, Tonga", "suva": "Suva, Fiji",
        "melbourne": "Melbourne", "antananarivo": "Antananarivo", "hong-kong": "Hong Kong", "santiago": "Santiago", "montevideo": "Montevideo",
    }
    qids = {
        "haskell": ("Haskell County", "Q374663"), "funston": ("Camp Funston", "Q1029832"), "new-york": ("New York City", "Q60"),
        "brest": ("Brest", "Q12193"), "madrid": ("Madrid", "Q2807"), "boston": ("Boston", "Q100"), "freetown": ("Freetown", "Q3780"),
        "cape-town": ("Cape Town", "Q5465"), "arkhangelsk": ("Arkhangelsk", "Q1851"), "philadelphia": ("Philadelphia", "Q1345"),
        "bombay": ("Mumbai", "Q1156"), "kimberley": ("Kimberley", "Q125905"), "mashhad": ("Mashhad", "Q121157"), "lima": ("Lima", "Q2868"),
        "nairobi": ("Nairobi", "Q3870"), "apia": ("Apia", "Q36260"), "melbourne": ("Melbourne", "Q3141"), "hong-kong": ("Hong Kong", "Q8646"),
        "montevideo": ("Montevideo", "Q1335"),
    }
    features = []
    for key, (label, _places) in REGIONS.items():
        features.append({"id": key, "kind": "region", "region_kind": "affected", "label": label, "area": _area(key), "active": False, "conjectural": True})
    for fid, label in labels.items():
        f = {"id": fid, "kind": "outbreak", "label": label, "at": list(C[fid]), "active": False}
        if fid in qids:
            f["entity"] = ent(*qids[fid])
        if fid in ("brest", "freetown", "cape-town", "boston"):
            f["kind"] = "port"
        features.append(f)

    return st.doc(
        schema=3,
        slug="1918-influenza",
        kind="epidemic",
        entity={"name": "1918 influenza pandemic", "wikidata": "Q178275"},
        title="The 1918 influenza pandemic",
        date_label="1918–1919",
        year=1918,
        period={"start": {"year": 1918, "month": 1}, "end": {"year": 1919, "month": 12}},
        ambient=True,
        camera={"center": [20.0, 20.0], "zoom": 1.3},
        intro=(
            "The influenza pandemic of 1918–1920, caused by an H1N1 influenza A virus and misleadingly called the "
            "Spanish flu, infected perhaps a third of the world's people and killed somewhere between 17 and 50 million, "
            "possibly more. It came in waves: a mild one in the spring of 1918, a devastating one from late August to "
            "December that by most accounts struck young adults unusually hard, and a third through 1919. The last year of the First "
            "World War spread it: troopships, training camps and crowded hospitals carried it from port to port and then "
            "along rivers and railways inland. This map follows the three waves, shading each region by how hard it was hit "
            "and marking the cities where the sources record its arrival or its dead."
        ),
        outcome="Between 17 and 50 million died, possibly 100 million; smaller waves followed in 1920 before the virus became a seasonal flu.",
        uncertainty=(
            "Where the pandemic began is unknown. The first confirmed cases were in the United States: Haskell County, Kansas "
            "in early 1918 (Barry), though a 2018 study found the Kansas cases milder than those in New York and leaned only "
            "towards a North American origin. Others propose the British army camp at Étaples in France, hit by a similar "
            "illness in late 1916; Austria in early 1917; or northern China, where a respiratory illness in November 1917 "
            "preceded the dispatch of the Chinese Labour Corps to France. The alternative sites are marked. Regional shading "
            "is schematic and the intensities are relative, read from the dates and tolls the sources give; China's toll in "
            "particular is poorly known. The ships' tracks are inferred from the ports they linked."
        ),
        alt_sites=[
            {"at": [-100.87, 37.57], "label": "Haskell County, Kansas", "note": "severe influenza reported Jan–Feb 1918"},
            {"at": [-73.94, 40.73], "label": "New York", "note": "2018 study: deadlier early cases than Kansas"},
            {"at": [1.641, 50.518], "label": "Étaples", "note": "British army camp; similar illness in late 1916"},
            {"at": [16.373, 48.208], "label": "Austria", "note": "Austrian archives suggest early 1917"},
            {"at": [117.0, 36.65], "label": "Northern China", "note": "respiratory illness, November 1917 (place schematic)"},
        ],
        legend=[
            {"swatch": "#c2410c", "label": "Region hit, shaded by severity (schematic)", "style": "fill"},
            {"swatch": "#991b1b", "label": "City with a recorded outbreak", "style": "dot"},
        ],
        sources=[
            {"title": "Spanish flu — Wikipedia", "url": "https://en.wikipedia.org/wiki/Spanish_flu", "kind": "web"},
            {"title": "1918 influenza pandemic (Q178275) — Wikidata", "url": "https://www.wikidata.org/wiki/Q178275", "kind": "web"},
        ],
        sides=[],
        units=[
            {"id": "aef-convoys", "kind": "fleet", "label": "US troopships"},
            {"id": "brest-boston", "kind": "fleet", "label": "Ships from Brest to Boston"},
            {"id": "brest-freetown", "kind": "fleet", "label": "Ships from Brest to Freetown"},
            {"id": "labour-corps", "kind": "fleet", "label": "Labour Corps ships"},
            {"id": "north-russia", "kind": "fleet", "label": "North Russia intervention"},
        ],
        features=features,
    )
