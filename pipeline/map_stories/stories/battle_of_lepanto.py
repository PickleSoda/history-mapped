"""Battle of Lepanto, 7 October 1571 - map story builder.

Anchors: ANCHOR is the mouth of the Gulf of Patras, a little east of Oxia island (OSM, 21.1097 E 38.3012 N) and
west of Cape Papas; Wikidata P625 (21.3, 38.2) is the general sea area. The exact lines at sea are reconstructed
(conjectural). Orientation: the Holy League came from the west (Sami, Kefalonia) and faced east, its Left
(Barbarigo) to the north next to the Aetolian shore, Centre (John of Austria) in the middle, Right (Doria) to
the south, reserve (Bazan) behind to the west. The Ottomans came from the east (Lepanto) facing west: Sirocco on
their right (north), Ali Pasha in the centre, Uluc Ali on their left (south, offshore). Source: Wikipedia
"Battle of Lepanto" (deployment, formation and battle sections).
"""
from pipeline.map_stories.geo import ellipse
from pipeline.map_stories.layout import Story, facing_off, local_frame

ANCHOR = (21.17, 38.27)
P = local_frame(ANCHOR)

OXIA = (21.10973, 38.30120)
MESOLONGI = (21.42835, 38.36864)
PAPAS = (21.37723, 38.21836)


def build() -> dict:
    st = Story()
    E = 90    # Holy League faces east
    W = 270   # Ottomans face west

    st.step("sighted", "Two fleets in the gulf approaches", "Dawn, 7 October", """
        After weeks of quarrels and a stormy crossing from Messina, the Holy League fleet left its anchorage on
        Kefalonia before dawn and rowed east toward the Gulf of Patras. The Ottoman fleet, which had left Lepanto
        to meet it, came out of the gulf from the opposite side. Both commanders held councils. Doria and others
        urged caution, but John of Austria wanted a battle to keep the alliance together. Ali Pasha, against the
        advice of Mehmed Sirocco, chose to fight on his sultan's orders. Positions at sea are reconstructed.
        """)
    st.put("c-left", at=P(-3800, 2000), facing=E, width=1900, depth=140, shape="line", state="ready", conjectural=True)
    st.put("c-centre", at=P(-3800, 0), facing=E, width=2000, depth=140, shape="line", state="ready", conjectural=True)
    st.put("c-right", at=P(-3800, -2000), facing=E, width=1900, depth=140, shape="line", state="ready", conjectural=True)
    st.put("c-reserve", at=P(-4600, 0), facing=E, width=1300, depth=140, shape="line", state="ready", conjectural=True)
    st.put("o-right", at=P(3600, 2100), facing=W, width=1700, depth=140, shape="line", state="ready", conjectural=True)
    st.put("o-centre", at=P(3600, 0), facing=W, width=2300, depth=140, shape="line", state="ready", conjectural=True)
    st.put("o-left", at=P(3600, -3400), facing=W, width=2400, depth=200, shape="line", state="ready", conjectural=True)
    st.put("o-reserve", at=P(4400, 0), facing=W, width=800, depth=120, shape="line", state="ready", conjectural=True)

    st.step("league-forms", "The Holy League forms its line", "Morning", """
        The League sailed already arranged in four divisions, with galleys of every nation mixed together and
        Spanish and Italian infantry in each, a lesson drawn from the failure at Preveza in 1538. The Left, of 53
        galleys mostly Venetian, lay in the north under Agostino Barbarigo. John of Austria held the Centre with 62
        galleys, and Giovanni Andrea Doria commanded the Right of 53 to the south. Alvaro de Bazan's 38 galleys
        followed as a reserve. A contrary wind slowed the deployment, but around noon it shifted in the
        Christians' favour.
        """)
    st.put("c-left", at=P(-1900, 2000), move="advance")
    st.put("c-centre", at=P(-1900, 0), move="advance")
    st.put("c-right", at=P(-1900, -2000), move="advance")
    st.put("c-reserve", at=P(-2700, 0), move="advance")
    st.put("john", at=P(-1900, 0), kind="commander")
    st.pin("john", "c-centre")
    st.note(P(-1900, 3400), "Wind shifts in the League's favour", "event", conjectural=True)

    st.step("ottomans-form", "The Ottoman crescent", "Around 11:00", """
        The Ottomans came on in a broad crescent. Mehmed Sirocco commanded 54 galleys on the right, hugging the
        northern shore. Ali Pasha led 88 galleys and eight galliots in the centre aboard the Sultana. Uluc Ali, with
        61 galleys and 32 galliots, took the left to the south and out to sea. A small reserve of eight galleys and
        21 galliots stayed behind the centre. The Ottomans had many more soldiers aboard but fewer of the elite
        janissaries, and their rowers were nearly all slaves.
        """)
    st.put("o-right", at=P(1500, 2100), move="advance")
    st.put("o-centre", at=P(1300, 0), move="advance")
    st.put("o-left", at=P(1500, -3400), move="advance")
    st.put("o-reserve", at=P(2200, 0), move="advance")
    st.put("ali", at=P(1300, 0), kind="commander")
    st.pin("ali", "o-centre")
    st.put("sirocco", at=P(1500, 2100), kind="commander")
    st.pin("sirocco", "o-right")
    st.put("uluc", at=P(1500, -3400), kind="commander")
    st.pin("uluc", "o-left")

    st.step("galleasses", "The galleasses open fire", "Around noon", """
        The six Venetian galleasses, heavy oared gun platforms, were towed ahead of the League's line. Four of them
        reached their stations in time and fired at point-blank range into the leading Ottoman galleys, breaking up
        their formation just as the fleets closed. Their exact placement is reconstructed, because the sources only
        say that four were in front of the line.
        """)
    st.put("c-galleasses-n", at=P(-1000, 1900), facing=E, width=260, depth=120, shape="line", state="ready", conjectural=True)
    st.put("c-galleasses-c", at=P(-1000, 0), facing=E, width=260, depth=120, shape="line", state="ready", conjectural=True)
    st.put("c-galleasses-s", at=P(-1000, -1900), facing=E, width=260, depth=120, shape="line", state="ready", conjectural=True)
    st.put("c-left", at=P(-1500, 2000), move="advance")
    st.put("c-centre", at=P(-1500, 0), move="advance")
    st.put("c-right", at=P(-1500, -2000), move="advance")
    st.put("c-reserve", at=P(-2300, 0), move="advance")
    st.put("o-right", at=P(800, 2100), move="advance")
    st.put("o-centre", at=P(600, 0), move="advance")
    st.put("o-left", at=P(900, -3400), move="advance")
    st.put("o-reserve", at=P(1500, 0), move="advance")
    st.fire("c-galleasses-c", st.at("o-centre"), "galleass guns")
    st.fire("c-galleasses-n", st.at("o-right"), "galleass guns")

    st.step("north-clash", "Barbarigo meets Sirocco", "Around noon", """
        First contact came in the north, between Barbarigo's Left and Sirocco's right wing. Barbarigo tried to
        stay close to the shore so that he could not be outflanked, but Sirocco knew the shallows and slipped
        galleys between the League line and the coast. The ships locked together so tightly that the fighting
        became an almost continuous platform of hand-to-hand combat. The slip of Ottoman galleys inshore is
        reconstructed from the account of the manoeuvre.
        """)
    st.put("c-left", at=P(-90, 2000), move="attack", state="engaged")
    st.put("o-right", facing_off(st.pl("c-left"), depth=140), move="attack", state="engaged")
    st.put("o-inshore", at=P(150, 3300), facing=W, width=450, depth=100, shape="line", state="engaged", conjectural=True)
    st.put("c-galleasses-n", at=P(-400, 2300), move="advance")
    st.hide("c-galleasses-c")
    st.hide("c-galleasses-s")
    st.note(P(150, 3750), "Sirocco slips between Barbarigo and the shore", "clash", conjectural=True)

    st.step("centre-clash", "The flagships collide", "Shortly after noon", """
        In the centre the lines met with such force that Ali Pasha's Sultana drove into John of Austria's Real as
        far as the fourth rowing bench. Spanish tercio infantry and Turkish janissaries fought across the two decks
        while the galleys of Colonna, Venier and the Knights of Malta joined the melee around them. Aboard the
        League ships the galley slaves had been unchained and given a chance to fight.
        """)
    st.put("c-centre", at=P(-90, 0), move="attack", state="engaged")
    st.put("o-centre", facing_off(st.pl("c-centre"), depth=140), move="attack", state="engaged")
    st.put("c-reserve", at=P(-1700, 0), move="advance")
    st.note(P(0, 600), "Sultana rams into the Real", "clash")

    st.step("north-decided", "Barbarigo falls, Sirocco is beaten", "Around 13:00", """
        Barbarigo was killed by an arrow in the eye, yet his captains held on, and Bazan's reserve came up in time
        to restore the balance in the north. Sirocco was killed and beheaded, and Christian slaves freed from the
        captured Turkish ships took up weapons and fought for the League. The Ottoman right broke and survivors ran
        for the shore. Which part of the reserve went north is not stated; the split of the reserve here is
        reconstructed.
        """)
    st.put("c-reserve-n", at=P(-1300, 1500), facing=E, width=650, depth=140, shape="line", state="ready", conjectural=True)
    st.put("c-reserve", width=650, at=P(-1700, -700))
    st.put("c-reserve-n", at=P(-250, 2800), move="advance", state="engaged")
    st.put("c-left", state="engaged")
    st.put("o-right", state="wavering")
    st.put("o-inshore", state="wavering")
    st.put("sirocco", state="killed")
    st.put("barbarigo", at=P(-90, 2000), kind="commander", state="killed")
    st.pin("barbarigo", "c-left")
    st.note(P(-90, 1500), "Barbarigo dies of an arrow wound", "death")
    st.note(P(150, 2600), "Sirocco killed", "death")

    st.step("centre-decided", "Ali Pasha is killed", "Around 14:00", """
        As the Real was close to being taken, Marcantonio Colonna brought his galley alongside and a
        counter-attack drove the Turks off. The Sultana was boarded and cleared, and Ali Pasha died with his crew.
        The banner of the Holy League was raised on the captured flagship, which broke the heart of the Ottoman
        galleys nearby. After about two hours the Turkish right and centre had been beaten, though fighting went
        on for two more.
        """)
    st.put("o-centre", state="wavering")
    st.put("c-centre", state="engaged")
    st.put("ali", state="killed")
    st.put("o-reserve", at=P(1200, 0), move="advance", state="wavering")
    st.note(P(500, 0), "Sultana taken; Ali Pasha dead", "capture")

    st.step("doria-gap", "Doria drifts south, Uluc Ali strikes", "Afternoon", """
        On the south wing Doria kept sailing southward instead of closing on the centre, later explaining that he
        wished to stop the Ottoman left from outflanking him. His own captains suspected treachery. A wide gap
        opened between Doria and the centre, and Uluc Ali wheeled his squadron around and fell on the southern
        flank of Colonna's centre, attacking a group of about fifteen galleys round the Maltese flagship. The strike
        group and its route are reconstructed.
        """)
    st.put("c-right", at=P(-1500, -4400), move="advance", state="ready")
    st.put("o-left", width=1500, at=P(-300, -3900), move="advance", state="engaged")
    st.put("o-uluc-strike", at=P(-500, -1800), facing=315, width=800, depth=120, shape="line", state="engaged", conjectural=True)
    st.put("c-centre", at=P(-90, -300), state="engaged")
    st.note(P(-1700, -2800), "Gap between Doria and the centre", "event")

    st.step("uluc-repulsed", "Bazan's reserve closes the gap", "Late afternoon", """
        Uluc Ali threatened to break into the Christian centre and turn the battle, but Bazan's reserve squadron
        arrived in time to stop him. Seeing the rest of the Ottoman fleet beaten, Uluc Ali withdrew with the
        captured standard of the Knights of Malta and made his escape. Doria's wing finally came into action
        against the stragglers.
        """)
    st.put("c-reserve", at=P(-700, -1900), move="attack", state="engaged", width=650)
    st.put("o-uluc-strike", state="wavering")
    st.put("o-left", at=P(1800, -3500), move="retreat", state="wavering", width=1500)
    st.put("o-uluc-strike", at=P(1500, -2500), move="retreat")
    st.put("c-right", at=P(-300, -4000), move="advance", state="engaged")
    st.put("uluc", at=P(1800, -3500), kind="commander")
    st.pin("uluc", "o-left")
    st.note(P(1200, -3200), "Uluc Ali escapes with Maltese standard", "event")

    st.step("aftermath", "Evening over a wrecked fleet", "Evening", """
        Isolated fighting went on until dusk, and some janissary groups fought to the last, reportedly throwing
        fruit once their weapons ran out. Many Greek rowers seized galleys from within. The League took 117 Ottoman
        galleys and sank or destroyed about 83 more, and freed thousands of Christian slaves. Ottoman dead are put
        at about 30,000, and the Christians lost around 7,500, though some sources go higher on both sides. The
        victory halted no Ottoman conquests for long, but it ended the myth of Turkish invincibility at sea.
        """)
    for uid in ("o-right", "o-inshore", "o-centre", "o-reserve"):
        st.put(uid, state="destroyed")
    st.put("c-left", state="ready")
    st.put("c-centre", state="ready")
    st.put("c-reserve-n", state="ready")
    st.put("c-reserve", state="ready")
    st.put("c-right", state="ready")
    st.put("o-left", state="routed")
    st.put("o-uluc-strike", state="routed")
    st.note(P(0, 0), "117 galleys captured, c. 83 sunk or destroyed", "label")

    return st.doc(
        slug="battle-of-lepanto", kind="naval_battle",
        entity={"name": "Battle of Lepanto", "wikidata": "Q165425"},
        title="Battle of Lepanto", date_label="7 October 1571", year=1571,
        intro="""On 7 October 1571 the fleet of the Holy League, an alliance of Spain, Venice, the Papal States, Genoa and
        smaller Christian powers, met the Ottoman navy at the mouth of the Gulf of Patras in western Greece. The
        League's commander, the young John of Austria, half-brother of Philip II, had gathered more than two hundred
        galleys to relieve Venice after the Ottoman conquest of Cyprus. The Ottoman admiral Ali Pasha led a fleet of
        similar size and more men, drawn up in a crescent. In about four hours of close fighting between galleys,
        which was the last great clash of oared warships, the Christian fleet destroyed or captured most of its
        enemy, killed Ali Pasha and freed thousands of galley slaves.""",
        outcome="Decisive Holy League victory: about 200 Ottoman galleys lost and Ali Pasha killed, but no lasting territorial gain.",
        uncertainty="""Ship positions, the lines' exact distance from the coast, the placement of the six galleasses,
        the Ottoman inshore squadron, the split of Bazan's reserve and Uluc Ali's strike group are reconstructed
        from the prose accounts and marked conjectural. Casualty numbers vary widely: 7,500 to 10,000 Christian dead
        and 20,000 to 40,000 Ottoman dead. The traditional site is near Oxia island and Cape Papas; Wikidata gives a
        point at the gulf mouth.""",
        sources=[{"title": "Battle of Lepanto - Wikipedia", "url": "https://en.wikipedia.org/wiki/Battle_of_Lepanto", "kind": "web"}],
        sides=[
            {"id": "c", "name": "Holy League", "color": "#1d4ed8", "polity": {"name": "Holy League", "wikidata": "Q698215"},
             "commanders": [
                 {"name": "John of Austria", "wikidata": "Q157107", "role": "overall commander"},
                 {"name": "Agostino Barbarigo", "wikidata": "Q4693618", "role": "left division, killed"},
                 {"name": "Giovanni Andrea Doria", "wikidata": "Q1525723", "role": "right division"},
                 {"name": "Alvaro de Bazan", "wikidata": "Q251441", "role": "reserve"},
                 {"name": "Marcantonio Colonna", "wikidata": "Q878288", "role": "papal squadron"},
                 {"name": "Sebastiano Venier", "wikidata": "Q729088", "role": "Venetian squadron"}],
             "strength": "c. 212 ships, 85,900 men", "losses": "7,500-10,000 dead, 13 galleys lost"},
            {"id": "o", "name": "Ottoman Empire", "color": "#b91c1c", "polity": {"name": "Ottoman Empire", "wikidata": "Q12560"},
             "commanders": [
                 {"name": "Ali Pasha", "wikidata": "Q953171", "role": "admiral, killed"},
                 {"name": "Mehmed Sirocco", "wikidata": "Q3853988", "role": "right wing, killed"},
                 {"name": "Uluc Ali", "wikidata": "Q465269", "role": "left wing"}],
             "strength": "c. 274 ships, 88,000 men", "losses": "20,000-40,000 dead, 200 galleys lost"},
        ],
        units=[
            {"id": "c-left", "side": "c", "kind": "warship", "label": "League Left (Barbarigo)", "strength": "53 galleys"},
            {"id": "c-centre", "side": "c", "kind": "warship", "label": "League Centre (John)", "strength": "62 galleys"},
            {"id": "c-right", "side": "c", "kind": "warship", "label": "League Right (Doria)", "strength": "53 galleys"},
            {"id": "c-reserve", "side": "c", "kind": "warship", "label": "Reserve (Bazan)", "strength": "38 galleys"},
            {"id": "c-reserve-n", "side": "c", "kind": "warship", "label": "Reserve, northern part"},
            {"id": "c-galleasses-n", "side": "c", "kind": "warship", "label": "Galleasses, north"},
            {"id": "c-galleasses-c", "side": "c", "kind": "warship", "label": "Galleasses, centre"},
            {"id": "c-galleasses-s", "side": "c", "kind": "warship", "label": "Galleasses, south"},
            {"id": "john", "side": "c", "kind": "commander", "label": "John of Austria"},
            {"id": "barbarigo", "side": "c", "kind": "commander", "label": "Barbarigo"},
            {"id": "o-right", "side": "o", "kind": "warship", "label": "Ottoman Right (Sirocco)", "strength": "54 galleys"},
            {"id": "o-inshore", "side": "o", "kind": "warship", "label": "Sirocco's inshore galleys"},
            {"id": "o-centre", "side": "o", "kind": "warship", "label": "Ottoman Centre (Ali)", "strength": "88 galleys"},
            {"id": "o-left", "side": "o", "kind": "warship", "label": "Ottoman Left (Uluc Ali)", "strength": "61 galleys"},
            {"id": "o-uluc-strike", "side": "o", "kind": "warship", "label": "Uluc Ali's strike group"},
            {"id": "o-reserve", "side": "o", "kind": "warship", "label": "Ottoman reserve", "strength": "8 galleys"},
            {"id": "ali", "side": "o", "kind": "commander", "label": "Ali Pasha"},
            {"id": "sirocco", "side": "o", "kind": "commander", "label": "Sirocco"},
            {"id": "uluc", "side": "o", "kind": "commander", "label": "Uluc Ali"},
        ],
        terrain=[
            {"id": "oxia", "kind": "island", "label": "Oxia", "area": ellipse(OXIA, 1800, 1200), "conjectural": True},
            {"id": "aetolia", "kind": "label", "label": "Aetolian shore", "at": P(-600, 6300), "conjectural": True},
            {"id": "morea", "kind": "label", "label": "Morea (Peloponnese) coast", "at": P(2000, -7500), "conjectural": True},
            {"id": "shallows", "kind": "label", "label": "Northern shallows", "at": P(300, 4300), "conjectural": True},
            {"id": "gulf", "kind": "label", "label": "Gulf of Patras", "at": P(1000, -6200), "conjectural": True},
        ],
    )
