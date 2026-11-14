"""Battle of Marathon, 12 September 490 BC (conventional date) — map story builder.

Anchors: infobox P625 (23.97833, 38.11806) for the plain; Mount Agrieliki (Athenian camp spur, wd:Q25117352) and the
Tumulus (osm) from `places`; Schinias and Brexiza from `places`. The sea is drawn by the base map.
Orientation: the Athenians stand in the west of the plain, facing EAST toward the bay and the Persians (facing WEST).
Plataeans on the Athenian left (north), polemarch Callimachus on the right (south); the two centre tribes (Leontis,
Antiochis) four ranks deep, the rest eight. Persians and Sakae in the centre, levies on the wings. The exact line,
the marsh the Persians fled into (the Great Marsh by Schinias) and the Persian camp are conjectural reconstructions.
Sources: Herodotus (via Wikipedia's Battle of Marathon: Prelude, Opposing forces, The Battle, Aftermath, Conclusions).
"""
from pipeline.map_stories.geo import ellipse, local, offset
from pipeline.map_stories.layout import Story, deploy_line, local_frame, route

ANCHOR = (23.96300, 38.12300)  # plain, shifted inland from the infobox point (which sits at the shore)
P = local_frame(ANCHOR)
PS = local_frame((23.97833, 38.11806))  # shore-side frame for ships, camp and sea-ward features


def L(lon, lat):
    e, n = local((lon, lat), ANCHOR)
    return P(e, n)


AGRIELIKI = L(23.94900, 38.10536)
TUMULUS = L(23.94900, 38.12323)
BREXIZA = L(23.97994, 38.10228)
SCHINIAS = L(24.03074, 38.14447)
NEA_MAKRI = L(23.97907, 38.08305)

GX = -600  # Greek front line x (m east of anchor)
PX = 900  # Persian front line x


def greek(x, **over):
    return deploy_line(P(x, 750), P(x, -750),
                       [("plataeans", 125), ("ath-left", 425), ("ath-centre", 450), ("ath-right", 475)],
                       depth=20, **over)


def persians(x, **over):
    return deploy_line(P(x, -950), P(x, 950),
                       [("pers-wing-s", 8), ("pers-centre", 9), ("pers-wing-n", 8)], depth=40, **over)


def build() -> dict:
    st = Story()

    # 1 landing
    st.step("landing", "The Persians land at Marathon", "Early September 490 BC", """
        Datis and Artaphernes bring the fleet down the Attic coast on the advice of the exiled tyrant Hippias and beach
        it on the bay of Marathon, about 27 kilometres from Athens. The plain is a good place to land: open ground for
        horses, a long shore for the ships. Under Miltiades the Athenian army marches out fast and takes the
        high ground at the plain's south-western edge, on a spur of Mount Agrieliki, blocking the exits toward Athens.""")
    st.put("pers-fleet", at=PS(2900, 100), facing=90, state="ready", label="Persian fleet")
    st.put("pers-cav", at=PS(2000, -300), facing=270, width=300, depth=40, state="ready",
           label="Persian cavalry", conjectural=True, strength_n=1000)
    st.put("pers-camp", at=PS(1900, 200), label="Persian camp", conjectural=True)
    st.put("ath-army", at=AGRIELIKI, facing=45, label="Athenian army (camp)", conjectural=True)
    st.side_move("a", "march", route(P(-9000, -9000), P(-5000, -5000), AGRIELIKI), label="from Athens")

    # 2 stalemate
    st.step("stalemate", "Five days of stalemate", "c. 7–11 September", """
        The runner Pheidippides has gone to Sparta, but the Spartans cannot march before the full moon because of a
        religious festival. Athens must hold on. A full muster of 1,000 Plataean hoplites arrives, which steadies
        Athenian nerves. Ten generals share command, with the war archon Callimachus in overall charge. For about five
        days the armies sit facing each other across the plain: the Athenians gain by waiting for the Spartans, the
        Persians hesitate to attack hoplites head on.""")
    st.put("plat-camp", at=offset(AGRIELIKI, 300, 250), label="Plataeans arrive", strength_n=1000,
           conjectural=True, move="march", start=P(-3000, 600))
    st.note(AGRIELIKI, "Athenian camp on the Agrieliki spur", "label")

    # 3 deployment
    st.step("deploy", "The armies form their lines", "Morning of the battle", """
        Roughly a mile and a half apart, the two armies deploy. Miltiades thins the centre of the Athenian line, the
        Leontis and Antiochis tribes under Themistocles and Aristides drawn up four ranks deep, the other tribes eight,
        so that the Athenians match the length of the Persian line and cannot be outflanked. The Plataeans hold the
        left. The Persians put their own troops and the Sakae in the centre and weaker levies on the wings.""")
    st.hide("ath-army")
    st.hide("plat-camp")
    st.hide("pers-camp")
    st.hide("pers-cav")  # the cavalry are not mentioned in the battle; one theory has them re-embarking
    st.place(greek(GX), facing=90, state="ready")
    st.place(persians(PX), facing=270, state="ready")

    # 4 advance
    st.step("advance", "The Athenians run at the arrows", "Morning", """
        At the signal the Athenians advance. They march until they reach the zone of the Persian arrows, roughly 200
        metres out, and then break into a run, the first Greek army to charge a missile-armed enemy this way. Their
        armour carries most of them through the volleys. The Persians, who had never seen Greeks attack at the run
        without horse or archers, took it for madness.""")
    st.place(greek(PX - 330), move="advance")
    st.fire("pers-centre", st.at("ath-centre"), "arrows")

    # 5 contact
    st.step("contact", "The lines meet", "Mid-morning", """
        The phalanx crashes into the Persian line along its whole length. Hoplites with long spears and heavy shields
        have the advantage in a close melee, and the Persian infantry, lightly armoured and armed with short spears,
        cannot match them. The fight lasts a long time. The thin Athenian centre faces the best troops the Persians
        have.""")
    st.place(greek(PX - 24), move="attack", state="engaged")
    for uid in ("pers-wing-s", "pers-centre", "pers-wing-n"):
        st.put(uid, state="engaged")

    # 6 centre pushed back
    st.step("centre-back", "The Athenian centre gives way", "Midday", """
        In the middle the Persians and Sakae prevail. The four-deep Athenian centre is forced back and the Persian
        troops pursue it inland, toward the Athenian camp and the road to Athens. On both wings, meanwhile, the
        Athenians and Plataeans are winning, and the levies facing them begin to waver.""")
    st.put("ath-centre", at=P(PX - 800, 0), move="retreat", state="wavering")
    st.put("pers-centre", at=P(PX - 380, 0), move="advance", state="engaged")
    st.put("pers-wing-n", state="wavering")
    st.put("pers-wing-s", state="wavering")

    # 7 wings win
    st.step("wings-win", "The Persian wings break", "Early afternoon", """
        The wings break first. The Athenian right and the Plataeans on the left shatter the levies in front of them
        and, instead of chasing the fugitives toward the sea, stop. They let the wings run and turn inward to help
        the hard-pressed centre. This disciplined decision turns a local success into a double envelopment.""")
    st.put("pers-wing-n", at=P(1900, 1300), move="rout", state="routed", facing=90)
    st.put("pers-wing-s", at=P(1500, -1100), move="rout", state="routed", facing=90)
    st.put("plataeans", at=P(PX - 250, 780), facing=215, move="flank", state="engaged", width=150)
    st.put("ath-left", at=P(PX - 420, 460), facing=215, move="flank", state="engaged", width=420)
    st.put("ath-right", at=P(PX - 420, -480), facing=325, move="flank", state="engaged", width=470)

    # 8 envelopment
    st.step("envelop", "The Persian centre is enclosed", "Afternoon", """
        With both wings closing like jaws, the Persian centre, which had advanced inland, is attacked from either
        flank while the Athenian centre, rallied, still holds its front. Caught away from its ships and its supports,
        it is now in a pocket. Some modern writers suspect that the Persians turned back once they saw their wings
        fail.""")
    st.put("ath-left", at=P(PX - 780, 300), facing=190, move="flank", state="engaged", width=420)
    st.put("ath-right", at=P(PX - 780, -300), facing=350, move="flank", state="engaged", width=470)
    st.put("plataeans", at=P(PX - 700, 560), facing=195, move="flank", state="engaged")
    st.put("ath-centre", at=P(PX - 1010, 0), facing=90, state="engaged")
    st.put("pers-centre", at=P(PX - 560, 0), facing=270, state="engaged")
    st.note(P(PX - 560, 420), "Wings turn inward", "event")

    # 9 rout and pursuit
    st.step("pursuit", "Rout toward the ships and the marsh", "Late afternoon", """
        The Persian centre breaks and runs for the shore with the Athenians behind it. Some fugitives, ignorant of the
        ground, run into the marsh and drown in unknown numbers. The Greeks chase the survivors to the beach, call for
        fire and seize seven ships; the rest of the fleet pushes off. Cynaegirus, brother of the playwright Aeschylus,
        has his hand cut off as he grasps a ship's stern and dies.""")
    st.put("pers-centre", at=P(2200, -300), move="rout", state="routed", facing=90)
    st.put("pers-wing-n", at=P(2800, 1200), move="rout", state="routed", facing=45, conjectural=True)
    st.put("pers-wing-s", at=P(1900, -900), move="rout", state="routed", facing=90)
    st.put("ath-left", at=P(2000, 500), facing=100, move="pursuit", state="engaged")
    st.put("ath-right", at=P(1900, -700), facing=80, move="pursuit", state="engaged")
    st.put("plataeans", at=P(2500, 1000), facing=60, move="pursuit", state="engaged")
    st.put("ath-centre", at=P(1300, 0), facing=90, move="advance", state="ready")
    st.put("pers-fleet", at=PS(3000, 100), move="sail", facing=130)
    st.note(PS(2500, -400), "Seven ships taken", "capture")
    st.note(PS(1900, 1950), "Fugitives drown in the marsh", "death", conjectural=True)

    # 10 aftermath
    st.step("aftermath", "Dead counted, Athens defended", "Evening and next days", """
        Herodotus counts 6,400 Persian dead against 192 Athenians; among the Athenian dead are Callimachus and the
        general Stesilaus. The fleet sails around Cape Sounion to strike Athens directly, whether after the battle
        or, as some think, as its cause. The army marches home as fast as it can, leaving the two centre tribes under
        Aristides to guard the field, and arrives first. The Persians turn back toward Asia. The next day the
        Spartans reach Marathon.""")
    st.put("pers-fleet", at=PS(3900, -2600), move="sail", facing=200)
    st.put("ath-left", at=P(-1500, -1000), facing=225, move="march", state="ready")
    st.put("ath-right", at=P(-2100, -1500), facing=225, move="march", state="ready")
    st.put("plataeans", at=P(-900, -700), facing=225, move="march", state="ready")
    st.put("ath-centre", at=P(300, 0), facing=90, move="retreat", state="ready")
    st.note(TUMULUS, "Athenian dead buried in a tumulus", "label")

    return st.doc(
        slug="battle-of-marathon", kind="battle",
        entity={"name": "Battle of Marathon", "wikidata": "Q31900"},
        title="Battle of Marathon", date_label="12 September 490 BC", year=-490,
        intro="""In the summer of 490 BC a Persian expedition under Datis and Artaphernes, sent by Darius I to punish
        Athens and Eretria for helping the Ionian revolt, landed at the bay of Marathon on the Attic coast. Hippias,
        the exiled Athenian tyrant, was with it. About 10,000 Athenians and Plataeans marched out, took a position on
        the spur of Agrieliki above the plain and waited for the Spartans, who were held back by a festival. After about
        five days of stalemate the Athenians attacked. They thinned their centre to match the longer Persian line,
        crossed the Persian bowshot at a run, broke both Persian wings, and then turned in to destroy the centre. It
        was the first great Greek victory over the Persians.""",
        outcome="Athenian and Plataean victory: Persian expedition repulsed, Athens saved from attack by sea.",
        uncertainty="""Herodotus gives 6,400 Persian and 192 Athenian dead but no army sizes; the 10,000 Greeks and the
        c. 25,000 Persian infantry with about 1,000 horse are the figures usually accepted. The exact date (12
        September or a month earlier), why the Athenians attacked before the Spartans came, and whether the Persian
        cavalry were absent are debated. Positions are reconstructed: the line, the Persian camp, the marsh into which
        the Persians fled, the flank movements and the placement of the wings are conjectural.""",
        sources=[{"title": "Battle of Marathon — Wikipedia", "url": "https://en.wikipedia.org/wiki/Battle_of_Marathon",
                  "kind": "web"}],
        sides=[
            {"id": "a", "name": "Athens and Plataea", "color": "#1d4ed8",
             "polity": {"name": "Classical Athens", "wikidata": "Q844930"},
             "commanders": [{"name": "Miltiades", "wikidata": "Q210350", "role": "strategos"},
                            {"name": "Callimachus", "wikidata": "Q364492", "role": "polemarch, killed"},
                            {"name": "Aristides", "wikidata": "Q294942", "role": "Antiochis tribe"},
                            {"name": "Themistocles", "wikidata": "Q179552", "role": "Leontis tribe"}],
             "strength": "c. 10,000–11,000", "losses": "192 Athenians (Herodotus)"},
            {"id": "b", "name": "Persians", "color": "#b91c1c",
             "polity": {"name": "Achaemenid Empire", "wikidata": "Q389688"},
             "commanders": [{"name": "Datis", "wikidata": "Q41328"},
                            {"name": "Artaphernes", "wikidata": "Q2428648"},
                            {"name": "Hippias", "wikidata": "Q313467", "role": "exiled Athenian tyrant"}],
             "strength": "c. 25,000 infantry, c. 1,000 cavalry (modern estimates)",
             "losses": "6,400 (Herodotus); 7 ships"},
        ],
        units=[
            {"id": "plataeans", "side": "a", "kind": "heavy_infantry", "label": "Plataeans", "strength": "c. 1,000"},
            {"id": "ath-left", "side": "a", "kind": "heavy_infantry", "label": "Athenian left wing tribes"},
            {"id": "ath-centre", "side": "a", "kind": "heavy_infantry", "label": "Leontis and Antiochis (4 ranks)"},
            {"id": "ath-right", "side": "a", "kind": "heavy_infantry", "label": "Athenian right wing tribes"},
            {"id": "ath-army", "side": "a", "kind": "army", "label": "Athenian army"},
            {"id": "plat-camp", "side": "a", "kind": "group", "label": "Plataean contingent", "strength": "1,000"},
            {"id": "pers-wing-s", "side": "b", "kind": "infantry", "label": "Persian levies (south)"},
            {"id": "pers-centre", "side": "b", "kind": "infantry", "label": "Persians and Sakae"},
            {"id": "pers-wing-n", "side": "b", "kind": "infantry", "label": "Persian levies (north)"},
            {"id": "pers-cav", "side": "b", "kind": "cavalry", "label": "Persian cavalry", "strength": "c. 1,000"},
            {"id": "pers-fleet", "side": "b", "kind": "fleet", "label": "Persian fleet", "strength": "600 triremes"},
            {"id": "pers-camp", "side": "b", "kind": "camp", "label": "Persian camp"},
        ],
        terrain=[
            {"id": "agrieliki", "kind": "hill", "label": "Mount Agrieliki", "area": ellipse(AGRIELIKI, 700, 500, 30)},
            {"id": "tumulus", "kind": "site", "label": "Tumulus (Soros)", "at": TUMULUS},
            {"id": "brexiza", "kind": "village", "label": "Brexiza", "at": BREXIZA},
            {"id": "schinias", "kind": "village", "label": "Schinias", "at": SCHINIAS},
            {"id": "marsh", "kind": "marsh", "label": "Great Marsh", "area": ellipse(PS(1900, 1900), 800, 450, 20),
             "conjectural": True},
            {"id": "road", "kind": "road", "label": "Road to Athens",
             "line": [P(-1000, -900), AGRIELIKI, P(-3600, -2600), P(-5000, -5000)], "conjectural": True},
            {"id": "grove", "kind": "woods", "label": "Grove or stakes on the flank",
             "area": ellipse(P(-1700, 900), 250, 150, 0), "conjectural": True},
        ],
    )
