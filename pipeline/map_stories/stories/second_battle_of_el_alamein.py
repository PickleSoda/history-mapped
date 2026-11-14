"""Second Battle of El Alamein, 23 Oct - 4 Nov 1942 - map story builder.

Anchor: El Alamein railway halt (places: OSM, 28.949E 30.834N). The `places` tool found no OSM
points for Tel el Eisa, Miteirya, the Kidney feature or Tel el Aqqaqir, so every ridge, hill and
belt position is a conjectural placement from the mainstream reconstruction (Wikipedia battle text:
Axis mine belts about 5 km apart, Kidney ~4.8 km SE of Tel el Aqqaqir, Rahman track behind it).
The coast is drawn by the base map and lies about 3 km north of the anchor.
Orientation: the Eighth Army starts east of the Axis lines and attacks WEST (facing 270); the Axis
face EAST (90). The northern sector is shown: coast and Tel el Eisa to the north, Miteirya Ridge
to the south. Sources: Wikipedia, Second Battle of El Alamein (Prelude, Battle, Aftermath).
"""
from pipeline.map_stories.geo import offset
from pipeline.map_stories.layout import Story, deploy_line, local_frame

ANCHOR = (28.94927, 30.83394)
P = local_frame(ANCHOR)


def ring(x0, x1, y0, y1):
    return [P(x0, y0), P(x1, y0), P(x1, y1), P(x0, y1)]


def build() -> dict:
    st = Story()
    W, E = 270, 90

    # ---- 1 Axis defences
    st.step("defences", "Rommel's mine belts", "Before 23 Oct 1942",
            """Panzerarmee Afrika sat behind two belts of mines about five kilometres apart, joined into boxes the
            British called devil's gardens. Forward outposts, with German and Italian infantry alternated, were
            thinly held and the real defence lay behind. Rommel, short of fuel, split his tanks into a northern
            group around the Kidney feature and a southern group, and kept the 90th Light Division back. The
            Eighth Army massed east of the line with four infantry divisions in the north.""",
            light="day")
    st.put("b-outposts", at=P(-11000, -1000), facing=E, width=7000, depth=60, shape="line", state="ready")
    st.put("b-15pz", at=P(-12700, -1300), facing=E, width=1200, depth=60, conjectural=True)
    st.put("b-littorio", at=P(-12700, 600), facing=E, width=1100, depth=60, conjectural=True)
    st.put("b-164", at=P(-9000, 2500), facing=E, width=1200, depth=50, conjectural=True)
    st.put("b-south", at=P(-10800, -7000), facing=E, width=2200, depth=60, conjectural=True)
    st.put("b-90light", at=P(-20500, 1500), facing=E, width=1000, depth=50, frame=False, conjectural=True)
    st.put("b-rommel-hq", at=P(-18000, 500), conjectural=True)
    st.place(deploy_line(P(-7300, -4500), P(-7300, 2500),
                         [("a-sa", 2), ("a-nz", 2), ("a-hld", 2), ("a-aus", 2)], depth=30), state="ready")
    st.put("a-x10", at=P(-4800, -2400), facing=W, width=1500, depth=60)
    st.put("a-x1", at=P(-4800, 0), facing=W, width=1500, depth=60)
    st.put("a-xiii", at=P(-6000, -7000), facing=W, width=2200, depth=60)
    st.put("a-9armd", at=P(-3500, -1200), facing=W, width=800, depth=50, conjectural=True)
    st.put("a-monty", at=P(-2500, -1000), conjectural=True)
    st.put("a-x7", at=P(-5500, -5200), facing=W, width=1500, depth=60, conjectural=True)
    st.put("b-guns", at=P(-15500, -1500), facing=E, width=2200, depth=40, state="hidden", conjectural=True)

    # ---- 2 night 23 Oct
    st.step("lightfoot", "Operation Lightfoot: the break-in", "Night, 23-24 Oct",
            """At 21:40 on 23 October about nine hundred guns opened up, and XXX Corps infantry walked west on a
            front of some twenty-six kilometres toward the Oxalic Line. Montgomery wanted two corridors cut
            through the mines in the north so that X Corps tanks could pass through. The infantry got into the
            outpost zone, but clearing lanes in the dark took far longer than planned, and in the south the
            diversion by XIII Corps made little headway.""", light="night")
    for u, y in (("a-sa", -3800), ("a-nz", -2200), ("a-hld", -300), ("a-aus", 1700)):
        st.put(u, at=P(-10200, y), move="advance", state="engaged")
    st.put("b-outposts", state="engaged")
    st.put("a-xiii", at=P(-9000, -7000), move="advance", state="engaged")
    st.put("b-south", state="engaged")
    st.note(P(-9500, -5500), "Southern diversion stalls in mines", "event", conjectural=True)

    # ---- 3 24 Oct: Stumme dies, armour stuck
    st.step("stuck", "The armour is held at the minefields", "24 Oct",
            """Dawn showed the Axis line bent but unbroken. General Stumme, driving forward to see for himself,
            died of a heart attack, and von Thoma took temporary command. Allied armour stayed bottled up at the
            Oxalic Line while engineers lifted mines. At dusk the 15th Panzer and Littorio divisions came out of
            the Kidney depression, and the first big tank action of the battle began. Over a hundred tanks were
            involved and about half were lost by nightfall, without changing the line.""", light="dusk")
    st.put("a-x1", at=P(-9900, -300), move="advance", state="engaged")
    st.put("a-x10", at=P(-9400, -2300), move="advance")
    st.put("b-15pz", at=P(-11600, -900), move="attack", state="engaged")
    st.put("b-littorio", at=P(-11600, 700), move="attack", state="engaged")
    st.note(P(-11000, -100), "First big tank clash near the Kidney", "clash", conjectural=True)

    # ---- 4 25 Oct: Aus thrust north
    st.step("northern-thrust", "Montgomery turns north", "25 Oct",
            """Montgomery judged a southward push from Miteirya Ridge too costly and shifted his weight to the
            north. At midnight the 26th Australian Brigade, with Valentine tanks, took Point 29 and 240
            prisoners, trying to cut off the German 164th Light Division and the Italian infantry in the coastal
            salient. Rommel, back from sick leave that evening, found the 15th Panzer Division down to 31 tanks
            and fuel for about three days.""", light="night")
    st.put("a-aus", at=P(-9600, 1700), width=1500, move="attack", state="engaged", conjectural=True)
    st.put("b-164", state="engaged")
    st.put("b-rommel-hq", at=P(-17500, 0), conjectural=True)
    st.note(P(-9800, 1200), "Point 29 taken, 240 prisoners", "capture", conjectural=True)

    # ---- 5 26-28 Oct: Rommel concentrates
    st.step("rommel-shifts", "Rommel pulls his armour north", "26-28 Oct",
            """Convinced the main blow would fall in the north, Rommel ordered counter-attacks on Point 29 and
            Hill 28, and moved the 21st Panzer Division, part of the Ariete and half the southern artillery up
            to join the 15th Panzer and Littorio. With so little petrol, the move could not be reversed. On 28
            October the two panzer divisions struck X Corps, but artillery and air attack broke up the
            assembly. It was Rommel's last attempt to seize the initiative.""", light="day")
    st.put("b-south", at=P(-12300, -3300), move="march", width=1800, conjectural=True)
    st.put("b-90light", at=P(-11200, 2300), move="march", frame=True, conjectural=True)
    st.put("b-15pz", at=P(-10500, 1000), move="attack", conjectural=True)
    st.put("a-x1", at=P(-9300, -300), state="engaged")
    st.put("a-nz", at=P(-8500, -2200), move="retreat", state="ready")
    st.note(P(-12500, -1800), "Tank strength drains; fuel short", "event", conjectural=True)

    # ---- 6 28 Oct - 1 Nov: Australians to the coast road
    st.step("crumbling", "The Australians press the coastal salient", "28 Oct - 1 Nov",
            """Further Australian attacks aimed at the paved coast road, around Thompson's Post south of the
            railway. The third attempt, on the night of 30 October, put the 9th Australian Division astride road and
            railway and left the Axis salient exposed, though a 21st Panzer battle group made four attacks on
            Thompson's Post on 31 October, all repulsed. Sergeant Kibby won a posthumous Victoria Cross. Tankers bound for
            Rommel were sunk, and he began planning a retreat to Fuka.""", light="night")
    st.put("a-aus", at=P(-8900, 2500), facing=0, width=1600, move="attack", state="engaged", conjectural=True)
    st.put("b-164", state="engaged")
    st.put("b-90light", state="engaged")
    st.put("a-nz", state="ready")
    st.note(P(-8700, 3000), "Axis attacks on Thompson's Post fail", "clash", conjectural=True)

    # ---- 7 2 Nov: Supercharge
    st.step("supercharge", "Operation Supercharge opens", "01:05, 2 Nov",
            """After a seven-hour air bombardment, 360 guns fired 15,000 shells and two infantry brigades, the
            151st and 152nd with tank regiments, advanced about 4,000 yards toward Tel el Aqqaqir on the Rahman
            track. Maori and lorried infantry guarded the flanks, and New Zealand engineers cleared five lanes
            through the mines. Only one Bersaglieri battalion still held the front line by 04:45.""", light="night")
    st.put("a-9armd", at=P(-12000, -1500), move="march", conjectural=True)
    st.put("a-nz", at=P(-13400, -1500), width=2500, facing=W, move="attack", state="engaged", conjectural=True)
    st.put("b-outposts", at=P(-14600, -1000), width=3500, move="retreat", state="wavering", conjectural=True)
    st.put("b-guns", state="ready")

    # ---- 8 9th Armoured
    st.step("ninth-armoured", "The 9th Armoured Brigade charges the guns", "06:15, 2 Nov",
            """At 06:15, half an hour before dawn, the brigade set off behind a creeping barrage with 94 of
            its 132 tanks still running. German and Italian anti-tank guns, among them 24 of the 88 mm flak
            guns, fired at tanks outlined by the rising sun. About 35 guns were destroyed in thirty minutes,
            but only 24 tanks were left running and 230 of 400 men were killed, wounded or captured. The gap
            for 1st Armoured was not yet open.""", light="dawn")
    st.put("a-9armd", at=P(-15300, -1500), width=1500, move="charge", state="wavering", conjectural=True)
    st.put("b-guns", state="engaged")
    st.put("a-x1", at=P(-14000, -200), width=1500, move="advance", conjectural=True)
    st.put("b-15pz", at=P(-14000, -1200), move="attack", state="engaged", conjectural=True)
    st.note(P(-15300, -2200), "Sacrificed on the gun line", "death", conjectural=True)

    # ---- 9 Break-out 4 Nov
    st.step("breakout", "The Axis front collapses", "4 Nov",
            """On 4 November 1st and 7th Armoured Divisions swung north and the New Zealanders headed west
            along desert tracks. The Ariete fought to the end against British tanks that had come round its open
            flank, while the Littorio and Trieste were also destroyed, and the unmotorised Italian infantry
            were left behind. By early afternoon Rommel judged his front broken, with a hole 19 kilometres
            wide, and radioed Hitler for leave to fall back on Fuka.""", light="day")
    st.put("a-x7", at=P(-14500, -5000), facing=W, width=1800, depth=60, move="flank", state="engaged", conjectural=True)
    st.put("a-x1", at=P(-17500, -300), facing=W, move="advance")
    st.put("a-nz", at=P(-18500, -1800), move="advance", state="ready")
    st.put("b-south", at=P(-16500, -4600), facing=E, move="rout", state="destroyed", conjectural=True)
    st.put("b-littorio", at=P(-15000, 700), move="rout", state="destroyed", conjectural=True)
    st.put("b-outposts", at=P(-14600, -1000), state="captured", by="a")
    st.note(P(-16300, -4300), "Ariete encircled", "death", conjectural=True)

    # ---- 10 Retreat
    st.step("retreat", "The retreat to Fuka", "4-11 Nov",
            """What remained of the German-Italian Panzer Army, with few trucks and no petrol to spare, pulled
            west toward Fuka and on beyond, to the borders of Tunisia. Axis losses were disputed, running from
            over 40,000 to some 73,000, with about 30,000 prisoners counted by 11 November. The Eighth Army lost
            13,560 men. Operation Torch landed in French North Africa on 8 November.""", light="day")
    st.put("b-15pz", at=P(-23000, 700), facing=W, move="retreat", state="wavering", frame=False, conjectural=True)
    st.put("b-90light", at=P(-23500, 2300), facing=W, move="retreat", state="wavering", frame=False, conjectural=True)
    st.put("a-x1", at=P(-19500, 0), move="pursuit")
    st.put("a-nz", at=P(-20000, -1800), move="pursuit")
    st.put("b-rommel-hq", at=P(-24000, 800), move="retreat", conjectural=True)

    return st.doc(
        slug="second-battle-of-el-alamein", kind="battle",
        entity={"name": "Second Battle of El Alamein", "wikidata": "Q153376"},
        title="Second Battle of El Alamein", date_label="23 October - 4 November 1942", year=1942,
        intro="""In October 1942 the Eighth Army under Bernard Montgomery attacked the German-Italian Panzer Army
        of Erwin Rommel at El Alamein, the Egyptian railway halt where the two armies had halted after the
        failed Axis advance. Rommel was away ill for the opening, and the army was laid out behind roughly half a
        million mines in two belts and on boxes called devil's gardens. Montgomery planned a twelve-day battle in
        three stages: the break-in, the dogfight and the final breaking of the enemy. It lasted thirteen days and
        ended with the Axis front torn open and the army in headlong retreat.""",
        outcome="Allied victory: the Axis army was broken and driven back from Egypt and Libya to the Tunisian border.",
        uncertainty="""Boundaries of minefields, the Kidney feature, Miteirya Ridge, Point 29, Tel el Aqqaqir and the
        Rahman track are not in the geodata. They are conjectural placements from the mainstream reconstruction,
        and the unit positions near them are reconstructed too. The southern sector is shown only schematically.
        Axis casualty totals vary widely between sources.""",
        sources=[{"title": "Second Battle of El Alamein - Wikipedia",
                  "url": "https://en.wikipedia.org/wiki/Second_Battle_of_El_Alamein", "kind": "web"}],
        sides=[
            {"id": "a", "name": "Eighth Army (Allies)", "color": "#2563eb",
             "polity": {"name": "United Kingdom", "wikidata": "Q145"},
             "commanders": [{"name": "Bernard Montgomery", "wikidata": "Q152025", "role": "Eighth Army"},
                            {"name": "Harold Alexander", "wikidata": "Q39168", "role": "Commander-in-chief Middle East"}],
             "strength": "195,000; 1,029 tanks", "losses": "13,560 casualties"},
            {"id": "b", "name": "Panzer Army Africa (Axis)", "color": "#b91c1c",
             "commanders": [{"name": "Erwin Rommel", "wikidata": "Q14060", "role": "Panzer Army"},
                            {"name": "Curio Barbasetti di Prun", "wikidata": "Q3699615", "role": "Italian chief of staff"}],
             "strength": "116,000; 547 tanks", "losses": "41,800-73,000 casualties"},
        ],
        units=[
            {"id": "a-sa", "side": "a", "kind": "infantry", "label": "1st South African Div."},
            {"id": "a-nz", "side": "a", "kind": "infantry", "label": "2nd New Zealand Div."},
            {"id": "a-hld", "side": "a", "kind": "infantry", "label": "51st Highland Div."},
            {"id": "a-aus", "side": "a", "kind": "infantry", "label": "9th Australian Div."},
            {"id": "a-x10", "side": "a", "kind": "heavy_cavalry", "label": "10th Armoured Div."},
            {"id": "a-x1", "side": "a", "kind": "heavy_cavalry", "label": "1st Armoured Div."},
            {"id": "a-x7", "side": "a", "kind": "heavy_cavalry", "label": "7th Armoured Div."},
            {"id": "a-xiii", "side": "a", "kind": "heavy_cavalry", "label": "XIII Corps (south)"},
            {"id": "a-9armd", "side": "a", "kind": "heavy_cavalry", "label": "9th Armoured Brigade", "strength": "132 tanks"},
            {"id": "a-monty", "side": "a", "kind": "commander", "label": "Montgomery"},
            {"id": "b-outposts", "side": "b", "kind": "infantry", "label": "Axis forward infantry"},
            {"id": "b-15pz", "side": "b", "kind": "heavy_cavalry", "label": "15th Panzer Div.", "strength": "125 tanks"},
            {"id": "b-littorio", "side": "b", "kind": "heavy_cavalry", "label": "Littorio Armoured Div."},
            {"id": "b-164", "side": "b", "kind": "infantry", "label": "164th Light Div."},
            {"id": "b-south", "side": "b", "kind": "heavy_cavalry", "label": "21st Panzer + Ariete"},
            {"id": "b-90light", "side": "b", "kind": "infantry", "label": "90th Light Div."},
            {"id": "b-guns", "side": "b", "kind": "artillery", "label": "Aqqaqir gun line"},
            {"id": "b-rommel-hq", "side": "b", "kind": "commander", "label": "Rommel"},
        ],
        terrain=[
            {"id": "belt-1", "kind": "fortification", "label": "First mine belt", "area": ring(-11600, -10200, -5500, 2600), "conjectural": True},
            {"id": "belt-2", "kind": "fortification", "label": "Second mine belt", "area": ring(-16200, -14700, -5500, 2600), "conjectural": True},
            {"id": "miteirya", "kind": "ridge", "label": "Miteirya Ridge", "line": [P(-10200, -4800), P(-9300, -3600), P(-8600, -2500)], "conjectural": True},
            {"id": "kidney", "kind": "hill", "label": "Kidney feature", "area": [offset(P(-12500, -1000), dx, dy) for dx, dy in ((-700, 0), (0, 500), (700, 0), (0, -500))], "conjectural": True},
            {"id": "eisa", "kind": "hill", "label": "Tel el Eisa", "area": [offset(P(-8000, 2300), dx, dy) for dx, dy in ((-500, 0), (0, 400), (500, 0), (0, -400))], "conjectural": True},
            {"id": "aqqaqir", "kind": "hill", "label": "Tel el Aqqaqir", "area": [offset(P(-15500, -2200), dx, dy) for dx, dy in ((-500, 0), (0, 400), (500, 0), (0, -400))], "conjectural": True},
            {"id": "rahman", "kind": "road", "label": "Rahman track", "line": [P(-16800, -5000), P(-16800, 2800)], "conjectural": True},
            {"id": "coast-road", "kind": "road", "label": "Coast road and railway", "line": [P(-22000, 3300), P(-12000, 3200), P(-4000, 3000)], "conjectural": True},
            {"id": "alamein", "kind": "village", "label": "El Alamein", "at": list(ANCHOR)},
        ],
    )
