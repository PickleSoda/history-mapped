"""Battle of Agincourt, 25 October 1415 - map story builder.

Anchors: villages Azincourt (W), Tramecourt (E), Maisoncelle (S) and Ruisseauville (NW) from `places`; the
field origin is the midpoint between Azincourt and Tramecourt. Wikipedia: the English stood across ~690 m of
a defile between the woods of Tramecourt and Azincourt; in the usual reconstruction the English faced north
(towards the road to Calais blocked by the French) and the French faced south. Orientation: English facing 0 (north), left wing = west (Camoys), right = east (York).
French facing 180; their left (as they face south) is east. Wood outlines, exact line positions and the
site itself are conjectural (the real site is disputed). Sources: Wikipedia, Battle of Agincourt (Setting, Fighting).
"""
from pipeline.map_stories.geo import ellipse, offset
from pipeline.map_stories.layout import Story, facing_off, local_frame

ANCHOR = (2.13952, 50.46330)
P = local_frame(ANCHOR)
ROAD = [[2.15041, 50.46371], [2.1496, 50.46232], [2.14792, 50.46154]]
AZINCOURT = [2.12845, 50.46329]
TRAMECOURT = [2.15058, 50.46351]
MAISONCELLE = [2.14242, 50.44730]
RUISSEAUVILLE = [2.12332, 50.48079]

WEST_WOOD = ellipse(P(-570, 0), 190, 800)
EAST_WOOD = ellipse(P(570, 0), 190, 800)
FIELD = [P(-380, -900), P(380, -900), P(380, 900), P(-380, 900)]


def build() -> dict:
    st = Story()

    st.step("approach", "Two armies on the road to Calais", "24 October",
            """After taking Harfleur, Henry marched his sick and hungry army towards Calais. At the Somme crossings
            and on the road north the French host, under the Constable d'Albret, finally got ahead of him and
            blocked the way near Azincourt. The English settled for the night in and around Maisoncelle on rain-soaked
            ground, while the French camped in the villages to the north. Henry ordered silence in the English camp
            on pain of losing an ear.""")
    st.put("eng-army", at=P(200, -1500), facing=0, width=300, depth=120)
    st.put("fr-army", at=P(-100, 1500), facing=180, width=500, depth=200)
    st.note(P(200, -1250), "English night in silence", "label")

    st.step("french-deploy", "The French draw up their battle", "Morning, 25 October",
            """At daybreak the French formed in a crowded order. A dense vanguard of about 4,800 men-at-arms
            dismounted stood in front, with the main battle of about 3,000 a bowshot behind. Some 600 dismounted
            men stood on each wing. Picked cavalry, 800 to 1,200 strong, waited on both flanks of the vanguard like
            horns, and a leaderless rear body of mounted valets filled the surplus. Archers and crossbowmen, unwanted
            in the front, were crammed behind.""")
    st.hide("fr-army")
    st.put("fr-van", at=P(0, 520), facing=180, width=300, depth=30, strength_n=4800)
    st.put("fr-main", at=P(0, 800), facing=180, width=250, depth=25, strength_n=3000)
    st.put("fr-wing-w", at=P(-210, 500), facing=180, width=90, depth=20, strength_n=600)
    st.put("fr-wing-e", at=P(210, 500), facing=180, width=90, depth=20, strength_n=600)
    st.put("fr-cav-w", at=P(-310, 580), facing=180, width=100, depth=14)
    st.put("fr-cav-e", at=P(310, 580), facing=180, width=100, depth=14)
    st.put("fr-shot", at=P(0, 1000), facing=180, width=300, depth=15)
    st.put("fr-rear", at=P(0, 1250), facing=180, width=320, depth=20)
    st.put("fr-albret", at=P(0, 520))
    st.pin("fr-albret", "fr-van")
    st.put("fr-alencon", at=P(0, 800))
    st.pin("fr-alencon", "fr-main")
    st.put("fr-raid", at=P(-800, 400), facing=180, width=40, depth=15, conjectural=True)
    st.hide("fr-raid")

    st.step("english-deploy", "The English line between the woods", "Morning, 25 October",
            """Henry placed his army across a front of about 690 metres, with the woods pressing in on either side.
            About 1,500 men-at-arms stood four deep in three battles, under Camoys on the left, the king in the
            centre and York on the right. Some 7,000 archers under Erpingham filled the flanks, and each drove a
            sharpened stake into the soft ground. The exact line is reconstructed; the sources give only the width and
            the order.""")
    st.hide("eng-army")
    st.put("eng-left", at=P(-125, -450), facing=0, width=120, depth=14, strength_n=500, conjectural=True)
    st.put("eng-centre", at=P(0, -450), facing=0, width=120, depth=14, strength_n=500, conjectural=True)
    st.put("eng-right", at=P(125, -450), facing=0, width=120, depth=14, strength_n=500, conjectural=True)
    st.put("eng-ar-w", at=P(-265, -450), facing=0, width=160, depth=30, strength_n=3500, conjectural=True)
    st.put("eng-ar-e", at=P(265, -450), facing=0, width=160, depth=30, strength_n=3500, conjectural=True)
    st.put("eng-henry", at=P(0, -450))
    st.pin("eng-henry", "eng-centre")
    st.put("eng-york", at=P(125, -450))
    st.pin("eng-york", "eng-right")
    st.put("eng-camoys", at=P(-125, -450))
    st.pin("eng-camoys", "eng-left")
    st.put("eng-erpingham", at=P(-265, -450))
    st.pin("eng-erpingham", "eng-ar-w")
    st.put("eng-baggage", at=P(150, -900), conjectural=True)

    st.step("standoff", "Three hours of waiting", "Dawn to mid-morning",
            """Nothing happened for about three hours after sunrise. Contemporary doctrine held that the side that
            marched against a firm foe lost, and the French expected reinforcements from Brabant, Anjou and Brittany.
            They were also astride Henry's road. The English, short of food and worn by illness, could not wait. Henry
            had to provoke the French into action, and that meant giving up his prepared ground.""")
    st.note(P(0, 150), "No move for three hours", "label")

    st.step("advance", "The English pull up stakes and advance", "Mid-morning",
            """Henry ordered the whole line forward. The archers tore up their stakes, carried them across the
            mud and drove them in again about 270 metres from the French, at the limit of a longbow's reach. The
            French could have struck while the stakes were out of the ground, but did not move. Erpingham is said to
            have given the signal, and the archers opened a high-angle volley.""")
    for u, x in (("eng-left", -125), ("eng-centre", 0), ("eng-right", 125)):
        st.put(u, at=P(x, 220), move="advance")
    st.put("eng-ar-w", at=P(-265, 220), move="advance")
    st.put("eng-ar-e", at=P(265, 220), move="advance")
    st.put("eng-baggage", at=P(150, -300), move="advance", conjectural=True)
    st.fire("eng-ar-e", P(310, 520), "arrow volley")
    st.fire("eng-ar-w", P(-310, 520), "arrow volley")

    st.step("cavalry", "The mounted charge breaks", "Late morning",
            """The French cavalry rode at the archers, short of men and ragged in order. Woods hemmed in
            the flanks and the stakes barred the front, and arrows struck unarmoured horses, which bolted. The wounded
            horses ran back through the French vanguard, trampling the foot soldiers and churning up the already
            ploughed, rain-sodden field.""")
    st.put("fr-cav-w", at=P(-310, 260), move="charge", state="engaged", facing=180)
    st.put("fr-cav-e", at=P(310, 260), move="charge", state="engaged", facing=180)
    st.put("eng-ar-w", state="engaged")
    st.put("eng-ar-e", state="engaged")
    st.note(P(0, 400), "Horses bolt into the vanguard", "event")

    st.step("cav-rout", "Horses run back through their own foot", "Late morning",
            """The survivors of the charge fled, and their wounded mounts scattered the advancing French infantry
            and cut up the ground still further. The vanguard, now disordered, pressed on through the mud under
            continued arrow fire. Men in plate were slow and had to keep their heads down, which limited breathing and
            sight.""")
    st.put("fr-cav-w", at=P(-300, 700), move="rout", state="routed")
    st.put("fr-cav-e", at=P(300, 700), move="rout", state="routed")
    st.put("eng-ar-w", state="ready")
    st.put("eng-ar-e", state="ready")
    st.put("fr-van", at=P(0, 400), move="advance", state="ready")
    st.put("fr-wing-w", at=P(-210, 380), move="advance")
    st.put("fr-wing-e", at=P(210, 380), move="advance")

    st.step("assault", "The men-at-arms trudge into the arrows", "Around noon",
            """On foot, the French vanguard crossed several hundred metres of mud in full plate while arrows
            fell on them. Most reached the English line and drove it back a short distance. The densely packed French
            ranks, pressed from behind, could scarcely use their weapons. The English men-at-arms and the archers
            on the flanks, now at close range, began to engage them.""")
    st.put("fr-van", **facing_off(st.pl("eng-centre"), depth=30), move="attack", state="engaged")
    st.put("eng-centre", state="engaged")
    st.put("fr-wing-w", **facing_off(st.pl("eng-ar-w"), depth=20, width=90), move="attack", state="engaged")
    st.put("fr-wing-e", **facing_off(st.pl("eng-ar-e"), depth=20, width=90), move="attack", state="engaged")
    st.put("eng-ar-w", state="engaged")
    st.put("eng-ar-e", state="engaged")

    st.step("melee", "The press and the archers' mallets", "Midday to afternoon",
            """The English line bent and then held. When the arrows ran out, archers dropped their bows and went in
            with swords, hatchets and mallets against exhausted, crowded Frenchmen who could not get up once felled.
            The French main battle, led by the dukes of Alencon and Bar, joined the press, but the narrow ground
            gave it no room. The fighting lasted about three hours, and the Gesta Henrici describes three heaps
            of dead around the three English standards.""")
    st.put("fr-main", at=P(0, 350), move="advance", state="engaged")
    st.put("eng-left", state="engaged")
    st.put("eng-right", state="engaged")
    st.note(P(0, 260), "Heaps of dead at the standards", "clash")
    st.note(P(-300, 120), "Henry shields Gloucester", "event", conjectural=True)

    st.step("baggage", "Raid on the English baggage", "During the fighting",
            """A local knight, Ysembart d'Azincourt, took a small party of men-at-arms and varlets and about 600
            peasants round to the English rear. They plundered Henry's baggage and took some of his treasure,
            including a crown. Sources disagree about timing: Barker follows the Gesta Henrici and puts it at the
            start; others place it at the end, when it alarmed the English. It was the French side's only real
            success.""")
    st.put("fr-raid", at=P(-760, 150), facing=90, width=60, depth=20, conjectural=True)
    st.put("fr-raid", at=P(150, -300), move="attack", state="engaged", conjectural=True)
    st.put("eng-baggage", state="captured", by="fr")

    st.step("prisoners", "The prisoners and the rearguard", "Late afternoon",
            """With the French vanguard and main battle destroyed, Henry feared that the large rearguard was
            regrouping and that the prisoners, who outnumbered their guards, might seize weapons. He ordered most of
            them killed, sparing the great lords. English knights refused to do it, and archers were detailed
            instead. Keegan suggests the aim was mostly to terrorise, and that few died before the French rear
            left the field.""")
    st.put("fr-rear", at=P(0, 1500), move="retreat", state="wavering")
    st.put("fr-shot", at=P(0, 1350), move="retreat", state="wavering")
    st.put("fr-van", state="destroyed")
    st.put("fr-main", state="destroyed")
    st.put("fr-wing-w", state="destroyed")
    st.put("fr-wing-e", state="destroyed")
    st.put("fr-raid", state="routed")
    st.note(P(0, 150), "Prisoners put to the sword", "death")

    st.step("aftermath", "A field of dead nobility", "Evening",
            """The French fled and the field was Henry's. Several thousand French were killed, including
            d'Albret, Alencon and Bar, with 700 to 2,200 captured. English losses are put at up to 600, among them
            the Duke of York. Henry went on to Calais and then home, a hero, and the victory fed into the treaty
            of Troyes five years later.""")
    st.put("fr-rear", state="routed")
    st.put("fr-shot", state="routed")
    st.put("eng-york", state="killed")
    st.put("fr-albret", state="killed")
    st.put("fr-alencon", state="killed")

    return st.doc(
        slug="battle-of-agincourt", kind="battle",
        entity={"name": "Battle of Agincourt", "wikidata": "Q188495"},
        title="Battle of Agincourt", date_label="25 October 1415", year=1415,
        intro="""On 25 October 1415, Saint Crispin's Day, Henry V's small and exhausted English army met a far larger
        French host in a muddy defile between woods near Azincourt in Artois. Henry had invaded France in August,
        taken Harfleur after a long siege that cost him many men to disease, and was marching towards Calais when the
        French finally blocked his path. Outnumbered perhaps three to one, the English stood on the defensive behind
        stakes, with archers on both flanks. The French, packed into a narrow field, waded through ploughed mud in
        heavy armour and were slaughtered in great numbers. It became one of the most celebrated English victories of
        the Hundred Years' War.""",
        outcome="English victory: thousands of French nobles killed or captured; Henry reached Calais.",
        uncertainty="""The exact site is disputed: the traditional ground lies between the woods of Azincourt and
        Tramecourt, but Michael Livingston argues for a field west of Azincourt. The wood outlines, the line positions
        and the spacing of the units are therefore conjectural, built from the stated width of about 690 m and the
        unit sizes. Numbers are debated (the English roughly 6,000 to 8,500, the French 12,000 to 25,000), as is the
        timing of the baggage raid and the scale of the prisoner killing.""",
        sources=[{"title": "Battle of Agincourt - Wikipedia", "url": "https://en.wikipedia.org/wiki/Battle_of_Agincourt", "kind": "web"}],
        sides=[
            {"id": "en", "name": "England", "color": "#b91c1c", "polity": {"name": "Kingdom of England", "wikidata": "Q179876"},
             "commanders": [
                 {"name": "Henry V", "wikidata": "Q131581", "role": "King"},
                 {"name": "Edward, Duke of York", "wikidata": "Q452639", "role": "Right wing"},
                 {"name": "Thomas Camoys", "wikidata": "Q2893387", "role": "Left wing"},
                 {"name": "Thomas Erpingham", "wikidata": "Q446018", "role": "Archers"}],
             "strength": "c. 6,000-8,500", "losses": "up to 600"},
            {"id": "fr", "name": "France", "color": "#1d4ed8", "polity": {"name": "Kingdom of France", "wikidata": "Q70972"},
             "commanders": [
                 {"name": "Charles d'Albret", "wikidata": "Q626829", "role": "Constable"},
                 {"name": "Jean Le Maingre", "wikidata": "Q930796", "role": "Marshal"},
                 {"name": "John, Duke of Alencon", "wikidata": "Q1377908", "role": "Main battle"},
                 {"name": "Edward III, Duke of Bar", "wikidata": "Q571406", "role": "Main battle"}],
             "strength": "c. 14,000-15,000", "losses": "c. 6,000 killed; 700-2,200 captured"},
        ],
        units=[
            {"id": "eng-army", "side": "en", "kind": "army", "label": "English army"},
            {"id": "eng-left", "side": "en", "kind": "heavy_infantry", "label": "Camoys' men-at-arms", "strength": "c. 500"},
            {"id": "eng-centre", "side": "en", "kind": "heavy_infantry", "label": "King's men-at-arms", "strength": "c. 500"},
            {"id": "eng-right", "side": "en", "kind": "heavy_infantry", "label": "York's men-at-arms", "strength": "c. 500"},
            {"id": "eng-ar-w", "side": "en", "kind": "archers", "label": "Archers, west flank", "strength": "c. 3,500"},
            {"id": "eng-ar-e", "side": "en", "kind": "archers", "label": "Archers, east flank", "strength": "c. 3,500"},
            {"id": "eng-henry", "side": "en", "kind": "commander", "label": "Henry V"},
            {"id": "eng-york", "side": "en", "kind": "commander", "label": "Duke of York"},
            {"id": "eng-camoys", "side": "en", "kind": "commander", "label": "Camoys"},
            {"id": "eng-erpingham", "side": "en", "kind": "commander", "label": "Erpingham"},
            {"id": "eng-baggage", "side": "en", "kind": "baggage", "label": "English baggage"},
            {"id": "fr-army", "side": "fr", "kind": "army", "label": "French army"},
            {"id": "fr-van", "side": "fr", "kind": "heavy_infantry", "label": "French vanguard", "strength": "c. 4,800"},
            {"id": "fr-main", "side": "fr", "kind": "heavy_infantry", "label": "French main battle", "strength": "c. 3,000"},
            {"id": "fr-wing-w", "side": "fr", "kind": "heavy_infantry", "label": "Wing, Vendome", "strength": "c. 600"},
            {"id": "fr-wing-e", "side": "fr", "kind": "heavy_infantry", "label": "Wing, Richemont", "strength": "c. 600"},
            {"id": "fr-cav-w", "side": "fr", "kind": "heavy_cavalry", "label": "Cavalry, west horn"},
            {"id": "fr-cav-e", "side": "fr", "kind": "heavy_cavalry", "label": "Cavalry, east horn"},
            {"id": "fr-shot", "side": "fr", "kind": "crossbowmen", "label": "Archers and crossbows"},
            {"id": "fr-rear", "side": "fr", "kind": "cavalry", "label": "Mounted rearguard"},
            {"id": "fr-albret", "side": "fr", "kind": "commander", "label": "d'Albret"},
            {"id": "fr-alencon", "side": "fr", "kind": "commander", "label": "Alencon and Bar"},
            {"id": "fr-raid", "side": "fr", "kind": "light_infantry", "label": "Raid on the baggage", "strength": "c. 600 peasants"},
        ],
        terrain=[
            {"id": "wood-w", "kind": "woods", "label": "Wood of Azincourt", "area": WEST_WOOD, "conjectural": True},
            {"id": "wood-e", "kind": "woods", "label": "Wood of Tramecourt", "area": EAST_WOOD, "conjectural": True},
            {"id": "field", "kind": "field", "label": "Ploughed, muddy field", "area": FIELD, "conjectural": True},
            {"id": "azincourt", "kind": "village", "label": "Azincourt", "at": AZINCOURT},
            {"id": "tramecourt", "kind": "village", "label": "Tramecourt", "at": TRAMECOURT},
            {"id": "maisoncelle", "kind": "village", "label": "Maisoncelle", "at": MAISONCELLE},
            {"id": "ruisseauville", "kind": "village", "label": "Ruisseauville", "at": RUISSEAUVILLE},
            {"id": "road", "kind": "road", "label": "Rue de Maisoncelle", "line": ROAD},
        ],
    )
