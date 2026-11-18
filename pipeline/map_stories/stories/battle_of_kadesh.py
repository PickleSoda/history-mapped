"""Battle of Kadesh, May 1274 BC — map story builder.

Anchors: Kadesh = Tell Nebi Mend (OSM place, 36.51957, 34.55747); Orontes line from OSM (it runs just east of the tell, flowing north).
Orientation: Egyptians come from the south marching north on the west bank; Hittites wait east of the river behind Old Kadesh, cross at a
ford south of the town and strike west into Re's flank; the Egyptian camp lies north-west of Kadesh. All field positions are mainstream
reconstruction (Wikipedia, Egyptian Poem and Bulletin), conjectural. Strengths from the infobox; per-division sizes are not in the sources.
"""
from pipeline.map_stories.geo import ellipse
from pipeline.map_stories.layout import Story, local_frame

ANCHOR = (36.51957, 34.55747)
P = local_frame(ANCHOR)

ORONTES = [[36.46975, 34.42861], [36.47086, 34.44019], [36.48358, 34.4527], [36.50541, 34.45947], [36.53091, 34.45245], [36.55183, 34.4677], [36.55004, 34.48658], [36.53728, 34.49673], [36.53929, 34.50823], [36.52951, 34.52597], [36.53497, 34.53219], [36.52897, 34.53256], [36.52285, 34.55725]]
ORONTES_N = [[36.52319, 34.55967], [36.52446, 34.56703], [36.52936, 34.56656], [36.52718, 34.58568], [36.53187, 34.58548], [36.53359, 34.59911], [36.52874, 34.59805], [36.52404, 34.61024], [36.53224, 34.6246], [36.60507, 34.65729], [36.61299, 34.66804]]

CAMP = (-1900, 1500)
FORD = (700, -2300)


def build() -> dict:
    st = Story()

    st.step("march", "Four divisions march on Kadesh", "Spring, year 5 of Ramesses II",
        """Ramesses II leaves Egypt in the spring of his fifth year and moves up the Canaanite coast and inland toward the Orontes valley. His army marches in four divisions named for Amun, Re, Ptah and Seth, with the Amun division and the king at the head and the others strung out behind. A further contingent, the Ne'arin, has been left in Amurru to guard the port of Sumur. The king's goal is the Hittite-aligned town of Kadesh, which blocks the road into Syria.""")
    st.put("amun", at=P(-1800, -9500), facing=0, width=260, depth=90, shape="column", state="ready", strength_n=5000, frame=True)
    st.put("pharaoh", at=P(-1800, -9200), facing=0, width=40, depth=40, frame=True)
    st.put("re", at=P(-1800, -11500), facing=0, width=260, depth=90, shape="column", strength_n=5000)
    st.put("ptah", at=P(-2400, -17000), facing=0, width=260, depth=90, shape="column", strength_n=5000, frame=False)
    st.put("set", at=P(-2600, -18000), facing=0, width=260, depth=90, shape="column", strength_n=5000, frame=False)
    st.put("nearin", at=P(-8000, -9000), facing=90, width=120, depth=60, frame=False)
    st.pin("pharaoh", "amun")

    st.step("spies", "The false report", "Day 9, third month of Shemu",
        """About eleven kilometres short of Kadesh, south of Shabtuna, Ramesses meets two Shasu nomads who say the Hittite king is far away near Aleppo, too afraid to come south. The report is a plant. Reassured, the king hurries on with the Amun division and pitches camp north-west of Kadesh. Soon after, Egyptian scouts bring in two Hittite prisoners who confess that Muwatalli II and his whole army are waiting behind the old city.""")
    st.put("amun", at=P(*CAMP), facing=0, width=360, depth=140, shape="block", move="advance")
    st.put("re", at=P(-1200, -5500), facing=0, move="march")
    st.put("hitt-chariots", at=P(2200, 1400), facing=270, width=700, depth=120, shape="block", state="hidden", strength_n=2500, frame=False)
    st.put("hitt-infantry", at=P(2400, 400), facing=270, width=600, depth=150, shape="block", state="hidden", frame=False)
    st.put("muwatalli", at=P(2700, 1200), facing=270, width=40, depth=40, frame=False)
    st.note(P(1400, 1900), "Hittites hidden behind old Kadesh", "label", conjectural=True)

    st.step("ambush", "Hittite chariots strike the Re division", "Midday",
        """Ramesses calls his officers and rages at the scouts who failed to find the enemy, and sends the vizier to hurry the Ptah and Seth divisions. The Re division is still marching in column toward the camp when Muwatalli sends his chariots across the Orontes at the ford south of Kadesh. They hit its flank while the men are strung out on the road. The division collapses before it can form a line.""")
    st.put("hitt-chariots", at=P(*FORD), facing=250, state="ready", conjectural=True, frame=True)
    st.put("re", at=P(-900, -3300), state="engaged", move="march")
    st.put("hitt-infantry", state="ready", at=P(2000, 300), frame=True)
    st.put("hitt-chariots", at=P(-300, -3200), facing=250, state="engaged", move="charge")
    st.note(P(500, -2600), "Ford south of Kadesh", "clash", conjectural=True)

    st.step("camp", "The camp is overrun", "Afternoon",
        """The broken Re division flees north toward the Amun camp with the chariots on its heels. The Hittites swing round north of the camp and drive through the shield wall that the Amun troops have set up. Panic runs through the camp. The Hittite attack loses momentum as the chariots tangle with tents, baggage and the barrier itself. In the king's own account he is left alone, without officer, charioteer or shield-bearer, while the enemy surrounds him.""")
    st.put("re", at=P(-1500, -200), state="routed", move="rout")
    st.put("hitt-chariots", at=P(-1500, 800), facing=300, state="engaged", move="charge")
    st.put("amun", state="wavering")
    st.put("pharaoh", state="wounded")

    st.step("counter", "Ramesses rallies and counterattacks", "Afternoon",
        """Ramesses drives back the first attackers and leads several charges with his bodyguard, some Amun chariots and the survivors of Re. The Hittites, thinking the Egyptians beaten, have stopped to plunder the camp, which costs them their momentum. The Egyptian counterattack drives them back toward the river, and the lighter Egyptian chariots catch the Hittite vehicles and cut them down.""")
    st.put("hitt-chariots", at=P(-200, 200), facing=90, state="wavering", move="retreat")
    st.put("amun", at=P(-1900, 1500), state="engaged", facing=90)
    st.put("pharaoh", state="engaged")
    st.put("egypt-chariots", at=P(-1700, 1300), facing=90, width=300, depth=60, shape="block", state="engaged", strength_n=500, conjectural=True)
    st.put("egypt-chariots", at=P(-1000, 800), move="charge")
    st.note(P(-900, 700), "The king's counter-charges", "clash")

    st.step("second-wave", "A second Hittite wave", "Late afternoon",
        """Muwatalli still has chariots and infantry in reserve and the walls of Kadesh behind him. As his beaten chariots reach the river, he sends in about a thousand more, led by nobles close to the throne, to hit the same camp again. His infantry stands unengaged across the river. This is the Hittite king's chance to turn the day, and the Egyptian camp is again in danger.""")
    st.put("hitt-reserve", at=P(1200, 400), facing=270, width=500, depth=100, shape="block", state="ready", strength_n=1000, conjectural=True)
    st.put("hitt-chariots", at=P(500, 100), facing=90)
    st.put("hitt-reserve", at=P(-700, 700), facing=270, state="engaged", move="charge")
    st.put("egypt-chariots", at=P(-1200, 700), facing=90, state="engaged")

    st.step("relief", "Ne'arin and Ptah arrive", "Evening",
        """Two bodies reach the field at the critical moment. The Ne'arin troops from Amurru arrive and surprise the Hittites, and the Ptah division comes up from the south and threatens their rear. After six Hittite charges in all, the survivors are almost surrounded and pinned against the Orontes.""")
    st.put("nearin", at=P(-3500, 2400), facing=90, frame=True, move="march", conjectural=True)
    st.put("ptah", at=P(-300, -3200), facing=0, width=300, depth=100, shape="block", state="engaged", frame=True, move="march", conjectural=True)

    st.step("river", "The river rout", "Dusk",
        """Hemmed in on the bank, the remaining Hittites abandon their chariots and swim for the far side. Egyptian accounts say they went in as fast as crocodiles, and many drowned. The Hittites are routed in the field, yet Muwatalli's infantry remain intact across the river and Kadesh itself is untouched. The king of Aleppo is among those named as pulled out of the water.""")
    st.put("hitt-chariots", at=P(400, 300), state="routed", move="rout", facing=90)
    st.put("hitt-reserve", at=P(600, 500), state="routed", move="rout", facing=90)
    st.put("nearin", state="engaged")
    st.put("ptah", at=P(-200, -600), state="engaged", move="advance", facing=0)
    st.note(P(550, 300), "Hittites flee into the Orontes", "death")

    st.step("next-day", "Stalemate the next day", "Following morning",
        """The following day the armies face each other again in a clash that ends without a result. Ramesses has no means to besiege the walled city of Kadesh. Muwatalli's infantry never fought in the main action, and he still holds the town. Both kings choose to withdraw.""")
    st.put("hitt-infantry", at=P(1400, 600), facing=270, state="ready", move="advance")
    st.put("amun", at=P(-1000, 1100), facing=90, state="ready", move="advance")
    st.put("hitt-chariots", state="destroyed")
    st.put("hitt-reserve", state="destroyed")

    st.step("aftermath", "Both sides claim victory", "After the battle",
        """Ramesses marches south toward Damascus and Egypt, proclaiming a triumph that he carved on temple walls. Hittite records read the outcome differently, and modern historians treat it as a draw. Muwatalli kept Kadesh and pushed on south into the Egyptian province of Upi. A treaty between Ramesses and Hattusili III followed about fifteen years later, in 1258 BC, a copy of which survives from the Hittite capital.""")
    st.put("amun", at=P(-1800, -9000), facing=180, move="retreat", frame=True)
    st.put("re", at=P(-1700, -9500), facing=180, state="ready", move="retreat")
    st.put("ptah", at=P(-1900, -9800), facing=180, state="ready", move="retreat")
    st.put("hitt-infantry", at=P(500, 600), facing=270, state="ready")
    st.note(P(0, 100), "Kadesh remains Hittite", "event")

    return st.doc(slug="battle-of-kadesh", kind="battle", entity={"name": "Battle of Kadesh", "wikidata": "Q203729"},
        title="Battle of Kadesh", date_label="May 1274 BC", year=-1274,
        intro="""In the fifth year of his reign Ramesses II led an Egyptian army north to challenge Hittite power in Syria, aiming at the strongly held town of Kadesh on the Orontes. It was one of the largest chariot battles of the ancient world, and it is unusually well documented because both sides left records. Misled by two planted informants, the pharaoh pushed ahead of most of his army and was struck by the Hittite chariots of Muwatalli II while his divisions were spread out along the road. The Egyptians rallied, and the battle ended undecided.""",
        outcome="Inconclusive: Ramesses rallied and held the field, but Kadesh stayed Hittite; both kings claimed victory.",
        uncertainty="Unit sizes and every field position are reconstructed from the Egyptian Poem and Bulletin, whose account is partisan. The ford, camp, hidden Hittite lines and the timing of arrivals are placed conjecturally. Army strengths are infobox figures with wide ranges.",
        sources=[{"title": "Battle of Kadesh - Wikipedia", "url": "https://en.wikipedia.org/wiki/Battle_of_Kadesh", "kind": "web"}],
        sides=[
            {"id": "egypt", "name": "Egyptian army", "color": "#b45309", "polity": {"name": "Egyptian Empire", "wikidata": "Q180568"},
             "commanders": [{"name": "Ramesses II", "wikidata": "Q1523", "role": "pharaoh"}], "strength": "16,000 infantry, 2,000 chariots", "losses": "Unknown, presumed heavy"},
            {"id": "hatti", "name": "Hittite coalition", "color": "#1d4ed8", "polity": {"name": "Hatti", "wikidata": "Q4496560"},
             "commanders": [{"name": "Muwatalli II", "wikidata": "Q311650", "role": "king of Hatti"}], "strength": "2,500 chariots, 15,000-40,000 infantry (not engaged)", "losses": "Unknown; about 2,000 chariots destroyed"},
        ],
        units=[
            {"id": "amun", "side": "egypt", "kind": "infantry", "label": "Division of Amun", "strength": "c. 5,000"},
            {"id": "pharaoh", "side": "egypt", "kind": "commander", "label": "Ramesses II"},
            {"id": "re", "side": "egypt", "kind": "infantry", "label": "Division of Re"},
            {"id": "ptah", "side": "egypt", "kind": "infantry", "label": "Division of Ptah"},
            {"id": "set", "side": "egypt", "kind": "infantry", "label": "Division of Seth"},
            {"id": "nearin", "side": "egypt", "kind": "chariots", "label": "Ne'arin contingent"},
            {"id": "egypt-chariots", "side": "egypt", "kind": "chariots", "label": "Pharaoh's rallied chariots"},
            {"id": "hitt-chariots", "side": "hatti", "kind": "chariots", "label": "Hittite chariot corps", "strength": "c. 2,500"},
            {"id": "hitt-reserve", "side": "hatti", "kind": "chariots", "label": "Second chariot wave", "strength": "c. 1,000"},
            {"id": "hitt-infantry", "side": "hatti", "kind": "infantry", "label": "Hittite infantry"},
            {"id": "muwatalli", "side": "hatti", "kind": "commander", "label": "Muwatalli II"},
        ],
        terrain=[
            {"id": "orontes", "kind": "river", "label": "Orontes", "line": ORONTES},
            {"id": "orontes-n", "kind": "river", "label": "Orontes", "line": ORONTES_N},
            {"id": "kadesh", "kind": "town", "label": "Kadesh", "at": list(ANCHOR)},
            {"id": "ford", "kind": "site", "label": "Ford", "at": list(P(*FORD)), "conjectural": True},
            {"id": "camp-area", "kind": "camp", "label": "Egyptian camp", "area": ellipse(P(*CAMP), 500, 350), "conjectural": True},
            {"id": "shabtuna", "kind": "village", "label": "Shabtuna (approx.)", "at": list(P(-1800, -10000)), "conjectural": True},
            {"id": "road", "kind": "road", "label": "Road from Egypt", "line": [list(P(-2600, -18000)), list(P(-1800, -10000)), list(P(-1200, -3500)), list(P(-1400, 1000))], "conjectural": True},
        ])
