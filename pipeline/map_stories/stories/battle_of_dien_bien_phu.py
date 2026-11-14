"""Battle of Dien Bien Phu, 13 March - 7 May 1954 - map story builder.

Anchors: Muong Thanh valley centre (places, OSM) and the Nam Rom river line (places --geometry).
Strongpoint positions are reconstructed from the usual mainstream layout: Beatrice (Him Lam hill, found by
places) NE, Gabrielle (Doc Lap hill) N, Anne-Marie NW, Dominique and Eliane east of the river, Huguette west,
Claudine south, headquarters on the west bank, Isabelle about 6 km south. All are conjectural to a few hundred m.
Orientation: the French garrison sits in the valley floor facing outward; the Viet Minh hold the hills all
round, the main assaults coming from east and north-east. Nam Rom flows north to south through the valley.
Sources: Wikipedia, Battle of Dien Bien Phu (Prelude, Battle sections).
"""
from pipeline.map_stories.geo import ellipse
from pipeline.map_stories.layout import Story, local_frame

ANCHOR = (103.0125, 21.39)
P = local_frame(ANCHOR)

NAM_ROM = [[103.01458, 21.4171], [103.01258, 21.41491], [103.01414, 21.41289], [103.01404, 21.40726], [103.01096, 21.40443], [103.01351, 21.39802], [103.01163, 21.38707], [103.01183, 21.38269], [103.01341, 21.38142], [103.01095, 21.37341], [103.00546, 21.36915], [103.00488, 21.36245], [103.00159, 21.36109], [103.00091, 21.35826], [103.00317, 21.35381], [102.99973, 21.35298], [103.0031, 21.34944], [103.00548, 21.34976], [103.00435, 21.34716], [103.00714, 21.34715], [103.00465, 21.34381], [103.00538, 21.33624]]

POS = {
    "beatrice": P(1700, 1700), "gabrielle": P(-400, 3500), "anne": P(-1800, 1900),
    "dominique": P(1300, 500), "eliane": P(550, -700), "huguette": P(-1300, 300),
    "hq": P(-450, -500), "claudine": P(-600, -1900), "isabelle": P(-800, -5600),
}


def build() -> dict:
    st = Story()

    st.step("fortress", "The hedgehog in the valley", "Dec 1953 - Mar 1954", """
        After the November 1953 parachute drop, de Castries' garrison turned the Muong Thanh valley into a ring of
        fortified hills named for women: Beatrice, Gabrielle and Anne-Marie on the north, Dominique and Eliane east
        of the Nam Rom, Huguette and Claudine west and south, and Isabelle six kilometres away at the reserve strip.
        The French relied on air supply and artillery to beat any assault. The Viet Minh, however, hauled guns
        by hand up the wooded hills and dug in around the valley.""")
    st.put("fr-hq", at=POS["hq"], facing=0, width=500, depth=300, shape="block", label="HQ and airstrip (de Castries)")
    st.put("fr-beatrice", at=POS["beatrice"], facing=45, width=300, depth=250, label="Beatrice (Legion)")
    st.put("fr-gabrielle", at=POS["gabrielle"], facing=0, width=300, depth=250, label="Gabrielle (Algerians)")
    st.put("fr-anne", at=POS["anne"], facing=315, width=250, depth=200, label="Anne-Marie (Tai)")
    st.put("fr-east", at=P(900, -100), facing=90, width=600, depth=250, label="Dominique and Eliane")
    st.put("fr-west", at=P(-1300, -300), facing=270, width=500, depth=250, label="Huguette and Claudine")
    st.put("fr-isabelle", at=POS["isabelle"], facing=180, width=500, depth=300, label="Isabelle", strength_n=1800)
    st.put("vm-312", at=P(3300, 2400), facing=225, width=700, depth=400, label="312th Division", frame=False)
    st.put("vm-308", at=P(-600, 5500), facing=180, width=700, depth=400, label="308th Division", frame=False)
    st.put("vm-316", at=P(3200, -600), facing=270, width=700, depth=400, label="316th Division", frame=False)
    st.put("vm-guns", at=P(3500, 900), facing=270, width=500, depth=300, label="Artillery in the hills", frame=False)


    st.step("beatrice", "Beatrice falls", "13 March 1954", """
        On the evening of 13 March the Viet Minh guns opened up without warning. A shell struck the Beatrice command
        post and killed the Legion battalion commander and most of his staff, and Colonel Gaucher, who commanded the
        central sector, died a few minutes later. The 312th Division then sent in the 141st and 209th Regiments, and
        sappers cut the wire. By morning the Foreign Legion had lost the hill, and the French learned that their
        counter-battery fire could not find the enemy guns.""")
    st.put("vm-312", at=P(2000, 1900), facing=225, move="attack", state="engaged", frame=True)
    st.put("fr-beatrice", state="engaged")
    st.note(POS["beatrice"], "Gaucher and Pegot killed by shellfire", "death")

    st.step("gabrielle", "Gabrielle and the guns", "14-15 March", """
        The next night the 308th Division attacked Gabrielle, held by an Algerian battalion. Artillery fell for hours
        before the infantry advanced at 20:00, and a shell wounded the battalion commander at 04:00. A relief
        thrust by an exhausted Vietnamese paratroop battalion was pinned by shellfire. The Algerians withdrew
        at 08:00 on 15 March. The airstrip had already been closed by the bombardment, so every ration and shell
        now had to come down by parachute.""")
    st.put("vm-308", at=P(-500, 4300), facing=180, move="attack", state="engaged", frame=True)
    st.put("fr-gabrielle", state="engaged")
    st.put("fr-beatrice", state="destroyed")
    st.note(POS["gabrielle"], "Fell 08:00 on 15 March", "clash")

    st.step("anne-marie", "Anne-Marie dissolves", "17 March", """
        Anne-Marie in the north-west was held by Tai auxiliaries. Giap had spent weeks leaflet-dropping them with
        the argument that this was not their war, and the loss of Beatrice and Gabrielle broke their morale. Under
        morning fog on 17 March most of them walked away, leaving the French and a few remaining Tai to pull back.
        The garrison was now confined to the central ring and to distant Isabelle.""")
    st.put("fr-anne", state="routed", move="retreat", at=P(-1300, 1100))
    st.put("fr-gabrielle", state="destroyed")
    st.put("vm-308", at=P(-900, 3000), move="advance", state="ready")

    st.step("lull", "Two weeks of quiet", "17-30 March", """
        The Viet Minh used the lull to tighten the ring and cut Isabelle off. Inside the camp the command cracked:
        de Castries withdrew to his bunker, and Colonel Langlais is often said to have taken effective control on
        24 March, though that confrontation is disputed. Chief gunner Piroth, who had promised to out-shoot the
        enemy, died on 15 March. Supply flights were forced above 2,000 m, and a sortie on 28 March destroyed
        seventeen anti-aircraft machine guns near the strip.""")
    st.put("vm-312", at=P(2200, 1000), facing=270, state="ready", move="advance")
    st.put("vm-316", at=P(2000, -400), facing=270, move="advance")
    st.put("fr-isabelle", state="ready")
    st.note(P(-3300, -3000), "Isabelle cut off from the centre", "label")

    st.step("eastern-assaults", "Dominique and Eliane", "30 March - 5 April", """
        On 30 March the Viet Minh went for the two hill groups east of the river. The 312th took Dominique 1 and 2
        at dusk, while the 316th captured Eliane 1 and half of Eliane 2. French 105 mm howitzers fired at zero
        elevation into the attackers, and counterattacks led by Langlais and Bigeard won back part of the
        ground. For several nights Eliane 2 and 4 changed hands under tanks and bayonets. The French held,
        but there were few reinforcements and the losses could not be replaced.""")
    st.put("vm-312", at=P(1700, 700), facing=270, move="attack", state="engaged")
    st.put("vm-316", at=P(1100, -400), facing=270, move="attack", state="engaged")
    st.put("fr-east", state="engaged", at=P(700, -100))
    st.note(P(600, -700), "Bigeard: not giving up Eliane 4", "clash")

    st.step("trench-war", "Trenches and starvation", "5-22 April", """
        After a Viet Minh regiment was caught in the open on 5 April, Giap gave up massed night charges and began
        digging. Trenches crept toward each strongpoint, cutting the French from their water and ammunition.
        On 10 April the French recaptured Eliane 1, and Huguette 6 was abandoned after a failed break-out on
        18 April. Huguette 1 was overrun on 22 April, and with more than 90 percent of the airfield in Viet Minh
        hands the landing zone shrank to a few hundred metres, so parachute drops went astray.""")
    st.put("vm-312", at=P(1500, 600), state="ready")
    st.put("vm-308", at=P(-1500, 700), move="advance", state="engaged")
    st.put("fr-west", state="wavering", at=P(-1000, -250), move="retreat")
    st.note(P(-1500, 500), "Huguette 1 falls on 22 April", "capture")

    st.step("final", "The last offensive", "1-6 May", """
        On the night of 1 May the Viet Minh overran Eliane 1, Dominique 3 and Huguette 5 in a combined assault.
        Isabelle, short of water and ammunition since the end of April, was by then all but alone. On 6 May the
        first Katyusha rockets of the battle struck Eliane 2; the French answered with a time-on-target barrage, but
        a mine placed under the hill shattered the defenders. Within hours Eliane 2 was lost, and the central
        garrison had nowhere left to give ground.""")
    st.put("vm-312", at=P(900, 300), facing=270, move="attack", state="engaged")
    st.put("vm-316", at=P(500, -500), facing=270, move="attack", state="engaged")
    st.put("fr-east", state="destroyed")
    st.put("vm-308", at=P(-900, 100), move="attack")
    st.put("fr-west", state="destroyed")
    st.note(P(550, -700), "Mine under Eliane 2, 6 May", "death")

    st.step("surrender", "The fall of the camp", "7 May 1954", """
        Giap ordered an all-out attack on 7 May with more than 25,000 men. At 17:00 de Castries told Hanoi that the
        end was near and was ordered to fight on; soon afterward the radio went silent as the headquarters bunker
        was overrun. Roughly 18:20 saw only Lily, held by Moroccans, still resisting, and it surrendered that night.
        That night a break-out from the main camp failed, while at Isabelle about seventy of
        1,700 men reached Laos. About 11,700 Frenchmen went into captivity.""")
    st.put("vm-308", at=P(-1000, -100), move="attack", state="engaged")
    st.put("vm-312", at=P(700, 500), move="attack")
    st.put("vm-316", at=P(300, -1300), move="attack")
    st.put("fr-hq", state="captured", by="vm")
    st.put("fr-isabelle", state="destroyed", at=POS["isabelle"])
    st.note(POS["hq"], "De Castries surrenders", "capture")
    st.note(POS["isabelle"], "About 70 of 1,700 escape", "event")

    return st.doc(
        slug="battle-of-dien-bien-phu", kind="siege",
        entity={"name": "Battle of Dien Bien Phu", "wikidata": "Q604897"},
        title="Battle of Dien Bien Phu", date_label="13 March - 7 May 1954", year=1954,
        intro="""In November 1953 French commander Navarre parachuted troops into the remote Muong Thanh valley in
            north-west Vietnam, planning a fortified base that would lure the Viet Minh into a pitched battle and
            shield Laos. The garrison grew to roughly 10,800 men and was supplied only by air. General Vo Nguyen Giap
            encircled it with about 50,000 troops and hauled artillery, including anti-aircraft guns and howitzers,
            over the forested hills. After abandoning an early quick-strike plan, he opened the assault on 13 March
            1954 and, step by step, took the outlying strongpoints, then closed in with trenches until the last
            positions fell on 7 May. The surrender ended the French war in Indochina.""",
        outcome="Viet Minh victory: the French garrison surrendered, about 11,700 were captured, and the First Indochina War ended in French withdrawal.",
        uncertainty="""Exact strongpoint and headquarters positions, the artillery sites, and the paths of the Viet Minh divisions are reconstructed from the usual maps and marked conjectural. Casualty figures vary widely between Western, Asian and Vietnamese sources. The alleged confrontation of de Castries by Langlais on 24 March is disputed by some historians. Unit sizes are schematic and not drawn to strength.""",
        sources=[{"title": "Battle of Dien Bien Phu - Wikipedia", "url": "https://en.wikipedia.org/wiki/Battle_of_Dien_Bien_Phu", "kind": "web"}],
        sides=[
            {"id": "fr", "name": "French Union", "color": "#1d4ed8",
             "polity": {"name": "French Union", "wikidata": "Q848478"},
             "commanders": [{"name": "Henri Navarre", "wikidata": "Q1354290", "role": "Commander in Indochina"},
                            {"name": "Christian de Castries", "wikidata": "Q710667", "role": "Garrison commander"},
                            {"name": "Pierre Langlais", "wikidata": "Q3385771", "role": "Paratroop commander"}],
             "strength": "c. 10,800 at start, c. 14,000 by 7 May",
             "losses": "1,142-2,293 killed, 11,721 captured"},
            {"id": "vm", "name": "Viet Minh", "color": "#b91c1c",
             "polity": {"name": "Viet Minh", "wikidata": "Q190949"},
             "commanders": [{"name": "Vo Nguyen Giap", "wikidata": "Q179910", "role": "Commander"}],
             "strength": "c. 49,500 combat troops at start",
             "losses": "Estimates from 8,000 dead to 23,000-25,000 casualties"},
        ],
        units=[
            {"id": "fr-hq", "side": "fr", "kind": "camp", "label": "HQ and airstrip"},
            {"id": "fr-beatrice", "side": "fr", "kind": "heavy_infantry", "label": "Beatrice (Legion)"},
            {"id": "fr-gabrielle", "side": "fr", "kind": "infantry", "label": "Gabrielle (Algerians)"},
            {"id": "fr-anne", "side": "fr", "kind": "light_infantry", "label": "Anne-Marie (Tai)"},
            {"id": "fr-east", "side": "fr", "kind": "infantry", "label": "Dominique and Eliane"},
            {"id": "fr-west", "side": "fr", "kind": "infantry", "label": "Huguette and Claudine"},
            {"id": "fr-isabelle", "side": "fr", "kind": "infantry", "label": "Isabelle", "strength": "1,809"},
            {"id": "vm-312", "side": "vm", "kind": "infantry", "label": "312th Division"},
            {"id": "vm-308", "side": "vm", "kind": "infantry", "label": "308th Division"},
            {"id": "vm-316", "side": "vm", "kind": "infantry", "label": "316th Division"},
            {"id": "vm-guns", "side": "vm", "kind": "artillery", "label": "Artillery in the hills"},
        ],
        terrain=[
            {"id": "nam-rom", "kind": "river", "label": "Nam Rom", "line": NAM_ROM},
            {"id": "strip", "kind": "road", "label": "Airstrip", "line": [list(P(-500, -1200)), list(P(-450, 600))], "conjectural": True},
            {"id": "muong-thanh", "kind": "village", "label": "Muong Thanh", "at": [103.01687, 21.38728]},
            {"id": "him-lam", "kind": "hill", "label": "Him Lam hill", "area": ellipse(POS["beatrice"], 350, 300), "conjectural": True},
            {"id": "doc-lap", "kind": "hill", "label": "Doc Lap hill", "area": ellipse(POS["gabrielle"], 350, 300), "conjectural": True},
            {"id": "eliane-hills", "kind": "hill", "label": "Eliane hills", "area": ellipse(POS["eliane"], 400, 250), "conjectural": True},
            {"id": "east-woods", "kind": "woods", "label": "Forested hills", "area": ellipse(P(3300, 800), 1100, 2400), "conjectural": True},
        ],
    )
