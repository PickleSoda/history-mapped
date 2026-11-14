"""Battle of Ain Jalut, 3 September 1260 - map story builder.

Anchors: the spring of Ain Jalut (Ein Harod spring, OSM natural=spring) is the origin; Gidona village, Jezreel
village, Givat HaMoreh peak and the Nahal Harod stream line come from `places`. Mount Gilboa rises SE of the spring.
Orientation: the Mongols camped first at the spring and faced west, toward the Mamluk approach up the Jezreel
valley; the Mamluk main body hid in the Gilboa foothills to the south/south-east (positions conjectural, per Wikipedia's
prose and the mainstream reconstruction). The Mongol rout ran east toward Beisan (Beit She'an), 14 km away.
Source: Wikipedia, Battle of Ain Jalut (Prelude, Battlefield, Battle, Aftermath).
"""
from pipeline.map_stories.geo import ellipse, offset
from pipeline.map_stories.layout import Story, local_frame

ANCHOR = (35.3559, 32.54959)
P = local_frame(ANCHOR)
NAHAL_HAROD = [[35.3379, 32.56658], [35.3509, 32.55965], [35.36877, 32.55503], [35.37525, 32.55023], [35.38314, 32.54717],
               [35.39372, 32.54581], [35.39872, 32.54373], [35.40486, 32.54285], [35.42256, 32.53221], [35.43129, 32.52999],
               [35.44214, 32.53], [35.45398, 32.5223], [35.46018, 32.51354]]
GIDONA = (35.35925, 32.54875)
JEZREEL = (35.32134, 32.56235)
MOREH = (35.34894, 32.61768)
GILBOA = ellipse(P(2600, -2600), 4200, 1500, rotate=45)
MOREH_HILL = ellipse(MOREH, 1500, 1200)


def build() -> dict:
    st = Story()

    st.step("mongol-camp", "The Mongols hold the spring", "Early September 1260", """
        Hulegu has taken most of his army back east, and Kitbuqa is left in Syria with a single tumen, Georgian and
        Armenian vassals, and the levies of two Ayyubid princes. Learning that the Mamluks are marching north, he gathers
        his scattered men and takes up a position at the spring of Ain Jalut, where Mount Gilboa shelters his flank and
        the stream gives water and grazing for the horses. His camp is already pitched when the Mamluk vanguard arrives.""")
    st.put("mongol-left", at=P(-250, -750), facing=270, width=700, depth=50, shape="block")
    st.put("mongol-centre", at=P(-250, 0), facing=270, width=700, depth=50, shape="block")
    st.put("mongol-right", at=P(-250, 750), facing=270, width=700, depth=50, shape="block")
    st.put("mongol-camp", at=P(700, 150), conjectural=True)
    st.put("kitbuqa", at=P(300, 0), conjectural=True)
    st.pin("kitbuqa", "mongol-centre")
    st.put("mamluk-army", at=P(-9000, 600), frame=False)

    st.step("mamluk-march", "Qutuz marches north", "July - September 1260", """
        Qutuz leaves Cairo on 26 July and pushes Baybars ahead with the vanguard. Baybars takes Gaza, a Mongol outpost, and
        the sultan follows. The Frankish rulers of Acre, who distrust the Mongols, stay neutral but let the Egyptians pass
        and supply them on the plain of Acre. With his rear secure, Qutuz turns inland toward the Jezreel valley.""")
    st.put("mamluk-army", at=P(-6000, 500), frame=False, move="march")
    st.put("baybars-vanguard", at=P(-3800, 200), facing=90, width=400, depth=40, shape="block")
    st.note(P(-3000, 1450), "Jezreel", "label")

    st.step("baybars-height", "Baybars sees the camp", "Early morning, 3 September", """
        Baybars, leading the vanguard, climbs a nearby height and finds the Mongol camp already in place. Qutuz has the
        advantage of the ground, which Baybars knows from his years as a fugitive. The sultan keeps the bulk of his army out
        of sight in the highlands and leaves only a small force to bait the Mongols.""")
    st.put("baybars-vanguard", at=P(-2300, 150), move="advance")
    st.put("mamluk-army", at=P(-3500, -900), move="march")

    st.step("hidden-force", "The main army hides in the hills", "Dawn", """
        Qutuz settles the greater part of his force in the folds of the Gilboa foothills south of the valley. The trees
        and broken ground conceal them from the Mongol scouts. The exact positions of the left, centre and right are not
        recorded, so they are placed where the mainstream reconstruction puts them. His own guard stays further back.""")
    st.hide("mamluk-army")
    st.put("mamluk-left", at=P(-100, -1900), facing=0, width=600, depth=50, shape="block", conjectural=True)
    st.put("mamluk-centre", at=P(800, -2300), facing=0, width=600, depth=50, shape="block", conjectural=True)
    st.put("mamluk-right", at=P(1900, -1900), facing=0, width=600, depth=50, shape="block", conjectural=True)
    st.put("qutuz-guard", at=P(-300, -3200), facing=0, width=300, depth=40, shape="block", conjectural=True)
    st.put("qutuz", at=P(-300, -3350), conjectural=True)
    st.pin("qutuz", "qutuz-guard")

    st.step("first-clash", "Mongols advance on the vanguard", "Morning", """
        The Mongols are the first to move, with their Georgian and Armenian vassals. Their horse archers sweep forward and
        meet Baybars' small force in the open valley west of the spring. The fighting is hard, and Baybars keeps his men
        in order rather than let them be ridden down.""")
    st.put("mongol-centre", at=P(-1050, 0), move="advance", state="engaged")
    st.put("mongol-left", at=P(-1050, -700), move="advance", state="engaged")
    st.put("mongol-right", at=P(-1050, 700), move="advance", state="engaged")
    st.put("baybars-vanguard", at=P(-1700, 100), state="engaged", move="retreat")
    st.note(P(-1400, 350), "Vanguard met by Mongol charge", "clash")

    st.step("hit-and-run", "Hours of hit and run", "Late morning to midday", """
        For many hours Baybars strikes, falls back, and strikes again, provoking the Mongols and sparing his own troops.
        Each Mongol assault pushes him a little farther toward the broken country on the south side of the valley. The
        constant skirmishing draws the Mongol line forward and thins its order.""")
    st.put("baybars-vanguard", at=P(-300, -700), move="retreat", state="engaged")
    st.put("mongol-centre", at=P(-700, -300), facing=250, move="advance")
    st.put("mongol-left", at=P(-700, -900), facing=240, move="advance")
    st.put("mongol-right", at=P(-700, 400), facing=250, move="advance")

    st.step("feigned-retreat", "The feigned flight", "Afternoon", """
        After a final heavy Mongol assault Baybars and his men pretend to break and flee into the highlands. Kitbuqa, angered
        by the repeated retreats, does not suspect a trap and throws almost all his troops after them. The Mongol line
        loses its shape as it climbs into rough, wooded ground where its archers cannot manoeuvre freely.""")
    st.put("baybars-vanguard", at=P(500, -1500), move="retreat", state="ready")
    st.put("mongol-centre", at=P(100, -1000), facing=160, move="pursuit")
    st.put("mongol-left", at=P(-500, -1500), facing=160, move="pursuit")
    st.put("mongol-right", at=P(500, -300), facing=160, move="pursuit")

    st.step("ambush", "The trap springs", "Afternoon", """
        As the Mongols reach the foothills the hidden Mamluk wings and centre rise from cover. Arrows fall on the
        pursuers and cavalry hit them on several sides at once. Timothy May suggests that the defection of the Mongols'
        Syrian allies was a turning point, though the sources do not agree on this. The Mongols suddenly find themselves
        surrounded.""")
    st.put("mamluk-left", at=P(-700, -1500), facing=45, move="charge", state="engaged", conjectural=True)
    st.put("mamluk-centre", at=P(700, -1800), facing=0, move="charge", state="engaged")
    st.put("mamluk-right", at=P(1900, -1300), facing=315, move="charge", state="engaged")
    st.put("mongol-centre", state="engaged")
    st.put("mongol-left", state="engaged")
    st.put("mongol-right", state="engaged")
    st.put("baybars-vanguard", at=P(-100, -1800), facing=45, state="engaged", move="attack")
    st.put("ayyubid-allies", at=P(1400, -600), facing=270, width=250, depth=40, shape="block", state="wavering", conjectural=True)
    st.note(P(1400, -250), "Allied levies waver (May's view)", "event", conjectural=True)

    st.step("mongol-breakout", "The Mongols fight to break out", "Afternoon", """
        The Mongols fight fiercely to cut their way out of the ring. Their desperate pressure nearly destroys the Mamluk
        left wing, which gives way as they hunt for an escape. The battle is at its most dangerous moment for Qutuz, who has
        been watching from a distance with his own guard.""")
    st.put("mongol-left", at=P(-900, -1300), facing=300, move="attack", state="engaged")
    st.put("mamluk-left", at=P(-500, -1900), state="wavering", move="retreat", conjectural=True)

    st.step("qutuz-charge", "Qutuz throws away his helmet", "Afternoon", """
        Seeing his left wing nearly broken, Qutuz tears off his helmet so that his men can recognise him. He is said to
        have cried out to God three times for victory over the Mongols, and then he rides into the fight shouting
        wa islamah. His guard follows him toward the weakened side, and the wing steadies.""")
    st.put("qutuz-guard", at=P(-600, -2000), facing=330, move="charge", state="engaged", conjectural=True)
    st.put("mamluk-left", state="engaged", conjectural=True)
    st.note(P(-800, -2400), "Qutuz: \"O Islam!\"", "event")

    st.step("mongol-retreat", "Mongols driven toward Beisan", "Late afternoon", """
        Pressed by the renewed Mamluk attack, the Mongols are pushed back and flee east toward the Beisan road. They
        regroup there and counterattack, a last effort that briefly checks their pursuers. But the Mamluks now hold both
        the high ground and the initiative, and part of the Mongol force can only retreat.""")
    st.put("mongol-centre", at=P(2800, -300), facing=90, state="wavering", move="retreat")
    st.put("mongol-left", at=P(2000, -800), facing=90, state="wavering", move="retreat")
    st.put("mongol-right", at=P(3000, 400), facing=90, state="wavering", move="retreat")
    st.put("mamluk-centre", at=P(1600, -1200), facing=60, move="pursuit")
    st.put("mamluk-right", at=P(2500, -1200), facing=70, move="pursuit")
    st.put("mamluk-left", at=P(900, -1000), facing=70, move="pursuit")
    st.put("baybars-vanguard", at=P(1500, -300), facing=70, move="pursuit")
    st.put("qutuz-guard", at=P(700, -1500), facing=70, move="pursuit")
    st.hide("ayyubid-allies")
    st.hide("mongol-camp")

    st.step("kitbuqa-falls", "Kitbuqa dies with his army", "Evening", """
        The counterattack fails to turn the day. Kitbuqa and nearly all of the Mongol force that remained in the Levant
        are killed in the fighting, and the survivors are scattered. The Mamluks retake Damascus within five days and
        Aleppo within a month. Qutuz is murdered by his emirs on the road back to Cairo, and Baybars takes his place.""")
    st.put("mongol-centre", at=P(4300, -500), state="destroyed", move="rout")
    st.put("mongol-left", at=P(3600, -1000), state="routed", move="rout")
    st.put("mongol-right", at=P(4500, 500), state="routed", move="rout")
    st.put("kitbuqa", state="killed")
    st.put("mamluk-centre", at=P(3300, -900), facing=75, move="pursuit")
    st.put("mamluk-right", at=P(3900, -1000), facing=75, move="pursuit")
    st.put("mamluk-left", at=P(2400, -700), facing=75, move="pursuit")
    st.note(P(4500, -500), "Beisan lies 14 km further east", "label")

    return st.doc(
        slug="battle-of-ain-jalut", kind="battle", entity={"name": "Battle of Ain Jalut", "wikidata": "Q244356"},
        title="Battle of Ain Jalut", date_label="3 September 1260", year=1260,
        intro="""In September 1260 a Mamluk army from Egypt met a Mongol force left in Syria at the spring of Ain Jalut, at
        the foot of Mount Gilboa in the Jezreel valley. Hulegu had taken most of his army away after the sack of Baghdad
        and Aleppo, leaving Kitbuqa with about one tumen and Georgian, Armenian and Ayyubid vassals. Sultan Qutuz of Egypt
        killed Hulegu's envoys, marched north and secured the neutrality of the Franks of Acre. The Mongols took the
        ground first. Qutuz hid most of his men in the foothills and sent Baybars with a small force to draw the enemy in.
        After hours of skirmishing, a feigned retreat brought the Mongols into the hills, where they were surrounded and
        broken. Kitbuqa died, and Syria passed to the Mamluks.""",
        outcome="Mamluk victory: Kitbuqa was killed, the Mongols left Syria, and Damascus and Aleppo fell to the Mamluks.",
        uncertainty="""The sources do not fix where the hidden Mamluk wings, centre and guard stood, nor the exact paths of
        the feigned retreat and the Mongol breakout; these are conjectural placements. Army sizes are uncertain: the
        Mongol side is given as 10,000 to 12,000 in one reconstruction, while al-Yunini claims 100,000, which is
        probably exaggerated. Timothy May's suggestion that the Syrian allies defected is a hypothesis, and the timing of
        the Mongol counterattack toward Beisan is vague.""",
        sources=[{"title": "Battle of Ain Jalut - Wikipedia", "url": "https://en.wikipedia.org/wiki/Battle_of_Ain_Jalut", "kind": "web"}],
        sides=[
            {"id": "mamluk", "name": "Mamluk Sultanate", "color": "#15803d",
             "polity": {"name": "Mamluk Sultanate of Egypt", "wikidata": "Q282428"},
             "commanders": [{"name": "Qutuz", "wikidata": "Q336471", "role": "Sultan"},
                            {"name": "Baibars", "wikidata": "Q192960", "role": "Vanguard commander"}],
             "strength": "15,000-20,000", "losses": "Unknown"},
            {"id": "mongol", "name": "Mongols and vassals", "color": "#b91c1c",
             "polity": {"name": "Ilkhanate", "wikidata": "Q178084"},
             "commanders": [{"name": "Kitbuqa", "wikidata": "Q602993", "role": "Mongol general"}],
             "strength": "10,000-20,000", "losses": "Heavy"},
        ],
        units=[
            {"id": "mamluk-army", "side": "mamluk", "kind": "army", "label": "Mamluk army on the march"},
            {"id": "baybars-vanguard", "side": "mamluk", "kind": "light_cavalry", "label": "Baybars' vanguard"},
            {"id": "mamluk-left", "side": "mamluk", "kind": "cavalry", "label": "Mamluk left"},
            {"id": "mamluk-centre", "side": "mamluk", "kind": "cavalry", "label": "Mamluk centre"},
            {"id": "mamluk-right", "side": "mamluk", "kind": "cavalry", "label": "Mamluk right"},
            {"id": "qutuz-guard", "side": "mamluk", "kind": "heavy_cavalry", "label": "Qutuz's guard"},
            {"id": "qutuz", "side": "mamluk", "kind": "commander", "label": "Qutuz"},
            {"id": "mongol-left", "side": "mongol", "kind": "horse_archers", "label": "Mongol left"},
            {"id": "mongol-centre", "side": "mongol", "kind": "horse_archers", "label": "Mongol centre"},
            {"id": "mongol-right", "side": "mongol", "kind": "cavalry", "label": "Georgians and Armenians"},
            {"id": "ayyubid-allies", "side": "mongol", "kind": "cavalry", "label": "Syrian Ayyubid levies"},
            {"id": "kitbuqa", "side": "mongol", "kind": "commander", "label": "Kitbuqa"},
            {"id": "mongol-camp", "side": "mongol", "kind": "camp", "label": "Mongol camp"},
        ],
        terrain=[
            {"id": "ain-jalut", "kind": "site", "label": "Ain Jalut spring", "at": list(ANCHOR)},
            {"id": "gidona", "kind": "village", "label": "Gidona", "at": list(GIDONA)},
            {"id": "jezreel", "kind": "village", "label": "Jezreel", "at": list(JEZREEL)},
            {"id": "harod", "kind": "stream", "label": "Wadi Jalut (Nahal Harod)", "line": NAHAL_HAROD},
            {"id": "gilboa", "kind": "hill", "label": "Mount Gilboa", "area": GILBOA},
            {"id": "moreh", "kind": "hill", "label": "Hill of Moreh", "area": MOREH_HILL},
        ],
    )
