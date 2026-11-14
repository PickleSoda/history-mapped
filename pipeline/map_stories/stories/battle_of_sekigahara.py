"""Battle of Sekigahara, 21 October 1600 — map story builder.

Anchors: Sekigahara village (places), Mount Matsuo (Wikidata Q11529615), Mount Nangu (Q27972356),
Ogaki Castle 14 km east. Orientation: the Western Army stood in the western hills of the basin
facing east; the Eastern Army came along the Nakasendo from Ogaki in the east and faced west.
Kobayakawa on Matsuo (south) overlooked both Otani (south-west) and the Eastern right.
Exact block positions are the mainstream reconstruction and mostly conjectural.
Source: Wikipedia, Battle of Sekigahara (research tool).
"""
from pipeline.map_stories.geo import ellipse
from pipeline.map_stories.layout import Story, local_frame, ent

ANCHOR = (136.46803, 35.36240)
P = local_frame(ANCHOR)

MATSUO = ellipse(P(-1308, -1749), 650, 500, 0)
NANGU = ellipse(P(3789, -1731), 800, 600, 0)
SASAO = ellipse(P(-1700, 1400), 500, 450, 0)
FUJIKAWA = ellipse(P(-2100, -700), 600, 400, 0)
NAKASENDO = [P(4000, 150), P(2000, 80), P(0, 0), P(-1500, 100), P(-3500, 300)]


def blk(st, uid, x, y, facing, w, d, **kw):
    st.put(uid, at=P(x, y), facing=facing, width=w, depth=d, **kw)


def build() -> dict:
    st = Story()
    st.step("west-deploy", "The Western Army takes the hills", "Night of 20 to 21 October",
        """After losing Gifu Castle and failing to hold Ogaki as a choke point, Ishida Mitsunari marched his coalition west to the basin of Sekigahara. He wanted to fight with the surrounding hills at his back. Ishida stood on the north-west slope, Konishi and Shimazu and Ukita lined the centre, and Otani Yoshitsugu held the south-west end of the line. Kobayakawa Hideaki sat above them all on Mount Matsuo, with the Mori contingent of Kikkawa Hiroie far to the south-east on Mount Nangu. On paper the Western Army was strong. In practice Kobayakawa had been in contact with Kuroda Nagamasa, and Kikkawa had secretly promised that the Mori would not fight.""")
    blk(st, "w-ishida", -1700, 1250, 90, 450, 60, state="ready", conjectural=True)
    blk(st, "w-shimazu", -1350, 650, 90, 350, 50, conjectural=True)
    blk(st, "w-konishi", -1250, 250, 90, 350, 50, conjectural=True)
    blk(st, "w-ukita", -1000, -250, 90, 600, 60, conjectural=True)
    blk(st, "w-otani", -1900, -750, 90, 300, 50, conjectural=True)
    blk(st, "w-kobayakawa", -1308, -1700, 90, 500, 70, conjectural=True)
    blk(st, "w-wakisaka", -1750, -1150, 90, 400, 40, conjectural=True)
    blk(st, "w-mori", 3600, -1500, 270, 500, 60, conjectural=True)

    st.step("east-deploy", "The Eastern Army arrives in fog", "Night to dawn, 21 October",
        """Tokugawa Ieyasu came along the Nakasendo from Ogaki and drew up to the east of the Western line. Fukushima Masanori faced Ukita Hideie, the Ii and Matsudaira troops and Honda Tadakatsu stood nearer the road, and Todo Takatora, Kyogoku Takatomo and others took the south side opposite Otani. Heavy fog from the earlier rain hid both armies, and the Tokugawa vanguard stumbled into Ishida's men before either side saw the other. Both recoiled, but each now knew exactly where the enemy stood. Ieyasu himself stayed behind his lines.""")
    blk(st, "e-fukushima", -100, -300, 270, 600, 60, state="ready")
    blk(st, "e-ii", 100, 150, 270, 400, 50)
    blk(st, "e-kuroda", -250, 700, 270, 500, 50, conjectural=True)
    blk(st, "e-todo", -600, -900, 270, 450, 50, conjectural=True)
    blk(st, "e-honda", 600, 50, 270, 300, 50, conjectural=True)
    st.put("e-ieyasu", at=P(2300, 0), facing=270, conjectural=True)

    st.step("ii-opens", "Ii Naomasa begins the fight", "Morning, c. 08:00 or 10:00",
        """The Ii no Akazonae, the 3,600 crimson-armoured men of Ii Naomasa, opened the battle by striking at the Western centre, led forward by a small party of spearmen. Fukushima Masanori followed and engaged Ukita Hideie's troops. Older accounts date the start to about 08:00, while recent Japanese research prefers nearer 10:00. Naomasa had been named supreme field commander, and he was the first to meet the enemy.""")
    blk(st, "e-ii", -750, 250, 270, 400, 50, state="engaged", move="attack")
    blk(st, "w-shimazu", -1350, 650, 90, 350, 50, state="engaged")
    blk(st, "w-konishi", -1250, 250, 90, 350, 50, state="engaged")

    st.step("fukushima-ukita", "Deadlock in the centre", "Morning",
        """Fukushima Masanori's regulars pressed into Ukita Hideie's front while gunfire and arrows filled the air. Ota Gyuichi wrote that friend and foe pushed against each other. Ukita outnumbered Fukushima, but he had been forced to fill his ranks with ronin after senior vassals defected to the Tokugawa, so his army was weaker than its numbers. Spanish accounts add that guns from the Dutch ship De Liefde may have been used as field pieces by the Eastern side.""")
    blk(st, "e-fukushima", -600, -250, 270, 600, 60, state="engaged", move="attack")
    blk(st, "w-ukita", -1000, -250, 90, 600, 60, state="engaged")
    st.note(P(-800, -250), "Ukita holds, but strained", "clash")

    st.step("otani-front", "Otani on the southern flank", "Late morning",
        """On the south-west, Otani Yoshitsugu's small force faced Todo Takatora and Kyogoku Takatomo. Otani had placed his men facing Kobayakawa's hill, showing he suspected betrayal. He held for a time, with Hiratsuka Tamehiro and the Oda brothers leading a vanguard of 360 on the Fujikawa plateau.""")
    blk(st, "e-todo", -1500, -800, 270, 450, 50, state="engaged", move="attack")
    blk(st, "w-otani", -1900, -750, 90, 300, 50, state="engaged")

    st.step("kobayakawa", "Kobayakawa Hideaki changes sides", "Around noon (disputed)",
        """Kobayakawa Hideaki's roughly 15,000 men came down from Mount Matsuo and hit Otani Yoshitsugu from behind. The old story says Ieyasu fired guns at Matsuo to force his hand. Modern historians doubt this, citing the distance and the lack of contemporary evidence, and some argue that Kobayakawa had already agreed to defect before the battle began.""")
    blk(st, "w-kobayakawa", -1650, -1330, 90, 500, 70, state="engaged", move="attack")

    st.step("otani-falls", "Otani's wing is destroyed", "Early afternoon",
        """Pressed by Kobayakawa, Wakisaka Yasuharu and other pre-arranged defectors, together with Todo and Kyogoku, the Otani force gave way. Hiratsuka Tamehiro was killed and Otani Yoshitsugu took his own life. The Western right flank now stood open.""")
    blk(st, "w-wakisaka", -1850, -950, 90, 400, 40, state="engaged", move="attack")
    blk(st, "w-otani", -1900, -750, 90, 300, 50, state="destroyed")
    blk(st, "w-konishi", -1250, 250, 90, 350, 50, state="wavering")

    st.step("mori-held", "The Mori hold back", "Afternoon",
        """On Mount Nangu the Mori troops under Kikkawa Hiroie never came down. Kikkawa pretended to be eating a meal and blocked Mori Hidemoto, who wanted to relieve Mitsunari, and also stopped Chosokabe Morichika from marching. Mori Terumoto himself stayed in Osaka Castle. About two thirds of the Western army never did any real fighting.""")
    st.put("w-mori", state="hidden")
    blk(st, "w-mori", 3600, -1500, 270, 500, 60, state="ready")

    st.step("collapse", "The Western line collapses", "Mid-afternoon",
        """With Otani gone, Fukushima and Kobayakawa rolled up the Western flank. Ukita's troops, fighting the better-trained men of Fukushima, broke at last, and Ishida Mitsunari, seeing the position was hopeless, began to pull his men back. Honda Tadakatsu and Oda Nagamasu had meanwhile intercepted Toda's flanking attack. The Western Army dissolved into flight.""")
    blk(st, "w-ukita", -1400, -250, 90, 600, 60, state="routed", move="rout")
    blk(st, "w-ishida", -2400, 1500, 90, 450, 60, state="routed", move="retreat")
    blk(st, "e-fukushima", -1000, -250, 270, 600, 60, state="engaged", move="pursuit")
    blk(st, "w-shimazu", -1350, 650, 90, 350, 50, state="wavering")

    st.step("aftermath", "Tokugawa victory", "Evening, 21 October",
        """By evening the Western Army had been broken. Estimates of the dead vary hugely by source, from 8,000 to over 35,000 heads collected. Ishida Mitsunari was captured soon after and executed. The Mori lost lands for their ambiguous conduct. Tokugawa Ieyasu was now master of Japan in practice, and the Tokugawa shogunate would rule for two and a half centuries.""")
    blk(st, "e-ieyasu", -800, 100, 270, 100, 100, conjectural=True, move="advance")

    return st.doc(slug="battle-of-sekigahara", kind="battle",
        entity={"name": "Battle of Sekigahara", "wikidata": "Q234188"},
        title="Battle of Sekigahara", date_label="21 October 1600", year=1600,
        intro="""On 21 October 1600, in a narrow basin in what is now Gifu Prefecture, two coalitions fought for control of Japan after the death of Toyotomi Hideyoshi. Tokugawa Ieyasu led the Eastern Army, while Ishida Mitsunari led a Western coalition ostensibly loyal to Hideyoshi's infant son Hideyori. The Western side had planned to hold Gifu and Ogaki, but those plans collapsed and Ishida chose to fight at Sekigahara instead. Fog, secret deals and the last-minute defection of Kobayakawa Hideaki and others decided the day. Many troops on both sides, including Tokugawa Hidetada's 38,000 held at Ueda, never reached the field.""",
        outcome="Eastern Army victory; Tokugawa Ieyasu became master of Japan and founded the shogunate that ruled until 1868.",
        uncertainty="""Start time (08:00 traditional versus about 10:00 in recent research), the timing of Kobayakawa's defection, and the story of Ieyasu firing on Mount Matsuo are all disputed. All block positions are reconstructed from the mainstream layout, marked conjectural, and the sources do not give exact frontages. Casualty figures vary enormously between chronicles.""",
        sources=[{"title": "Battle of Sekigahara — Wikipedia", "url": "https://en.wikipedia.org/wiki/Battle_of_Sekigahara", "kind": "web"}],
        sides=[
            {"id": "w", "name": "Western Army", "color": "#1d4ed8",
             "commanders": [{"name": "Ishida Mitsunari", "wikidata": "Q334107", "role": "Coalition leader"},
                            {"name": "Ukita Hideie", "wikidata": "Q1329792"},
                            {"name": "Otani Yoshitsugu", "wikidata": "Q386265"},
                            {"name": "Shimazu Yoshihiro", "wikidata": "Q1156288"}],
             "strength": "81,890 at the battle (per the infobox)", "losses": "8,000 to 35,270 killed, by source"},
            {"id": "e", "name": "Eastern Army", "color": "#b91c1c",
             "commanders": [{"name": "Tokugawa Ieyasu", "wikidata": "Q171977", "role": "Overall commander"},
                            {"name": "Ii Naomasa", "wikidata": "Q1334437", "role": "Field commander"},
                            {"name": "Fukushima Masanori", "wikidata": "Q1194995"}],
             "strength": "88,888 at the battle (per the infobox)", "losses": "4,000 to 10,000 killed, by source"}],
        units=[
            {"id": "w-ishida", "side": "w", "kind": "infantry", "label": "Ishida Mitsunari"},
            {"id": "w-shimazu", "side": "w", "kind": "infantry", "label": "Shimazu"},
            {"id": "w-konishi", "side": "w", "kind": "infantry", "label": "Konishi"},
            {"id": "w-ukita", "side": "w", "kind": "infantry", "label": "Ukita Hideie"},
            {"id": "w-otani", "side": "w", "kind": "infantry", "label": "Otani Yoshitsugu"},
            {"id": "w-kobayakawa", "side": "w", "kind": "infantry", "label": "Kobayakawa Hideaki"},
            {"id": "w-wakisaka", "side": "w", "kind": "infantry", "label": "Wakisaka and defectors"},
            {"id": "w-mori", "side": "w", "kind": "infantry", "label": "Mori, Kikkawa (held back)"},
            {"id": "e-fukushima", "side": "e", "kind": "infantry", "label": "Fukushima Masanori"},
            {"id": "e-ii", "side": "e", "kind": "infantry", "label": "Ii Naomasa", "strength": "3,600", "strength_n": 3600},
            {"id": "e-kuroda", "side": "e", "kind": "infantry", "label": "Kuroda, Hosokawa"},
            {"id": "e-todo", "side": "e", "kind": "infantry", "label": "Todo, Kyogoku"},
            {"id": "e-honda", "side": "e", "kind": "infantry", "label": "Honda Tadakatsu"},
            {"id": "e-ieyasu", "side": "e", "kind": "commander", "label": "Tokugawa Ieyasu"}],
        terrain=[
            {"id": "matsuo", "kind": "hill", "label": "Mount Matsuo", "area": MATSUO},
            {"id": "nangu", "kind": "hill", "label": "Mount Nangu", "area": NANGU},
            {"id": "sasao", "kind": "hill", "label": "Sasao hill", "area": SASAO, "conjectural": True},
            {"id": "fujikawa", "kind": "hill", "label": "Fujikawa plateau", "area": FUJIKAWA, "conjectural": True},
            {"id": "nakasendo", "kind": "road", "label": "Nakasendo", "line": NAKASENDO, "conjectural": True},
            {"id": "sekigahara", "kind": "village", "label": "Sekigahara", "at": P(0, 0)}])
