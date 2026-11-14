"""Battle of Gettysburg, 1-3 July 1863 - map story builder.

Anchors: town, Cemetery Hill, Culp's Hill, the Angle, Little Round Top, Peach Orchard, Wheatfield, Devil's Den,
McPherson/Herr Ridge, Oak Hill (OSM via `places`). Rock Creek line from OSM (northern course drawn conjecturally).
Orientation: day 1 the Confederates come from the west facing east (Union I Corps faces west, XI Corps north).
Days 2-3 the Union fishhook (Culp's Hill - Cemetery Hill - Cemetery Ridge - Round Tops) faces west/north; the
Confederate line on Seminary Ridge faces east, its left curls through the town. Exact regimental spots are conjectural.
Sources: Wikipedia, Battle of Gettysburg (Background, Opposing forces, the three days).
"""
from pipeline.map_stories.geo import offset
from pipeline.map_stories.layout import Story, ent, when

TOWN = (-77.2310, 39.8309)
CEM_HILL = (-77.2295, 39.8218)
CULP = (-77.2239, 39.8259)
ANGLE = (-77.2364, 39.8134)
LRT = (-77.2357, 39.7911)
PEACH = (-77.2496, 39.8010)
WHEAT = (-77.2445, 39.7994)
DEN = (-77.2426, 39.7914)
MCP = (-77.2497, 39.8305)
HERR = (-77.2632, 39.8357)
OAK = (-77.2426, 39.8499)
SEM_S = (-77.2553, 39.8070)

ROCK_CREEK = [[-77.2140, 39.8400], [-77.2150, 39.8320], [-77.2160, 39.8250], [-77.2144, 39.81748],
              [-77.21365, 39.8088], [-77.2079, 39.79946], [-77.20929, 39.79355]]
EMMITSBURG_ROAD = [[-77.25006, 39.80168], [-77.24654, 39.80617], [-77.24001, 39.81166], [-77.2330, 39.8205]]
CHAMBERSBURG_PIKE = [[-77.2750, 39.8385], [-77.2632, 39.8350], [-77.2497, 39.8315], [-77.2400, 39.8320], [-77.2310, 39.8309]]


def build() -> dict:
    st = Story()

    st.step("first-shots", "Buford holds the western ridges", "Wed 1 July, c. 7:30",
            """Lee's army was scattered across Pennsylvania, and neither commander meant to fight at Gettysburg. On the
            morning of 1 July two brigades of Heth's division came east along the Chambersburg Pike. Just west of the town they met
            the vedettes of John Buford's cavalry. Buford had chosen to delay on Herr, McPherson and Seminary Ridges. His
            dismounted troopers fired breech-loading carbines from fences and trees. They bought the hours the Union infantry
            needed to reach the stronger hills south of town.""",
            date=when(1863, 7, 1), light="day")
    st.put("cs-heth", at=offset(HERR, -900, -60), facing=90, width=700, depth=40, state="ready")
    st.put("us-buford", at=offset(HERR, 150, -40), facing=270, width=900, depth=25, state="ready")
    st.put("us-cav-horses", at=offset(MCP, 500, -250), facing=270, width=200, depth=40, frame=False)
    st.note(offset(HERR, -300, 120), "First shots, c. 7:30 am", "clash")

    st.step("mcpherson", "Reynolds and the Iron Brigade", "Wed 1 July, 10:20 am - 12:30",
            """By 10:20 Heth's men had driven the troopers back to McPherson Ridge, just as the head of Reynolds's I Corps
            arrived. North of the pike Davis's brigade broke into Cutler's line but was thrown back near the unfinished
            railroad cut. South of it the Iron Brigade captured Archer and hundreds of his men in Herbst Woods. Reynolds
            was shot dead near the woods, and Doubleday took over. The fight in this sector then paused until about 2:30.""",
            date=when(1863, 7, 1))
    st.put("us-i-corps", at=offset(MCP, 150, -120), facing=270, width=1500, depth=40, state="engaged",
           conjectural=True)
    st.put("cs-heth", at=offset(MCP, -350, -60), move="attack", state="engaged", width=1100)
    st.put("us-buford", at=offset(MCP, 700, -450), facing=250, width=500, move="retreat")
    st.note(offset(MCP, 80, -250), "Reynolds killed", "death")
    st.note(offset(MCP, 120, 20), "Railroad cut: Davis repelled", "clash")

    st.step("north-collapse", "Ewell hits from the north", "Wed 1 July, 2:00 - 4:00 pm",
            """Heth, now with Pettigrew and Brockenbrough, renewed the attack at 2:30. The 26th North Carolina, the army's
            largest regiment at 839 men, left the day with about 212. Pender's division then drove the I Corps through the
            seminary grounds. Meanwhile two of Ewell's divisions, Rodes and Early, arrived from the north. Barlow had
            advanced the XI Corps to a knoll that stuck out of the line. Early overran him and the Union right folded up.""",
            date=when(1863, 7, 1))
    st.put("cs-heth", at=offset(MCP, -150, -80), move="attack", width=1100)
    st.put("cs-pender", at=offset(HERR, 100, -80), facing=90, width=900, depth=40, frame=True, state="engaged")
    st.put("cs-pender", at=offset(MCP, 20, -150), move="attack")
    st.put("us-i-corps", at=offset(MCP, 520, -300), facing=250, width=1100, state="wavering", move="retreat")
    st.put("cs-rodes", at=offset(OAK, -250, -400), facing=180, width=900, depth=40, state="engaged",
           conjectural=True)
    st.put("cs-early", at=offset(TOWN, 650, 1250), facing=225, width=900, depth=40, state="engaged",
           conjectural=True)
    st.put("us-xi-corps", at=offset(TOWN, 250, 900), facing=0, width=1200, depth=40, state="routed",
           conjectural=True)
    st.note(offset(TOWN, 500, 1050), "Barlow's Knoll overrun", "clash")

    st.step("cemetery-hill", "Hancock chooses the ground", "Wed 1 July, evening",
            """Howard pulled the broken I and XI Corps back through the streets to Cemetery Hill, where von Steinwehr's
            division was waiting. Meade sent Hancock forward to take command. Hancock judged it the strongest natural
            position he had ever seen and declared it the battlefield. Lee sent Ewell an order to take the hill "if
            practicable". Ewell decided it was not, and historians regard that as a lost chance.""",
            date=when(1863, 7, 1))
    st.put("us-i-corps", at=offset(CEM_HILL, -300, -150), facing=300, width=500, depth=40, move="retreat", state="ready")
    st.put("us-xi-corps", at=offset(CEM_HILL, 100, 120), facing=0, width=500, depth=40, move="retreat", state="ready")
    st.put("cs-early", at=offset(TOWN, 250, 250), facing=180, width=700, state="ready", move="advance")
    st.put("cs-rodes", at=offset(TOWN, -350, 350), facing=135, width=600, state="ready", move="advance")
    st.put("cs-heth", at=offset(SEM_S, 0, 1500), facing=90, width=500, state="ready", move="advance")
    st.put("cs-pender", at=offset(SEM_S, 0, 900), facing=90, width=500, state="ready", move="advance")
    st.put("us-hancock", at=offset(CEM_HILL, -60, 40))
    st.note(offset(CEM_HILL, 0, 300), "Ewell declines to attack", "event")

    st.step("fishhook", "The fishhook and the long Confederate arc", "Thu 2 July, morning",
            """Through the night and morning most of the remaining infantry arrived. The Union line took the shape of a
            fishhook. It ran from Culp's Hill to Cemetery Hill and then south along Cemetery Ridge toward Little Round Top.
            The XII Corps held Culp's Hill and the II Corps the northern ridge. Because the Union army held interior lines, Meade
            could shift troops. Lee's line was nearly five miles long, running along Seminary Ridge and curving through the
            town. Lee ordered Longstreet to attack the Union left, up the Emmitsburg Road.""",
            date=when(1863, 7, 2), light="day")
    st.hide("us-buford")
    st.hide("us-cav-horses")
    st.hide("cs-rodes")
    st.hide("us-hancock")
    st.hide("cs-heth")
    st.hide("cs-pender")
    st.put("us-xii-corps", at=offset(CULP, -80, 20), facing=60, width=600, depth=40, state="ready")
    st.put("us-xi-corps", at=offset(CEM_HILL, 100, 20), facing=0, width=500, state="ready")
    st.put("us-i-corps", at=offset(CEM_HILL, -250, -100), facing=270, width=400, state="ready")
    st.put("us-ii-corps", at=offset(ANGLE, 100, 400), facing=270, width=1100, depth=40, state="ready")
    st.put("cs-johnson", at=offset(CULP, 900, 350), facing=270, width=700, state="ready", conjectural=True,
           frame=True)
    st.put("cs-hood", at=offset(SEM_S, -300, -700), facing=90, width=900, depth=40, state="ready", conjectural=True)
    st.put("cs-mclaws", at=offset(SEM_S, -250, -250), facing=90, width=900, depth=40, state="ready", conjectural=True)
    st.put("cs-anderson", at=offset(SEM_S, -200, 450), facing=90, width=900, depth=40, state="ready", conjectural=True)
    st.put("us-meade", at=offset(ANGLE, 700, 500))
    st.put("cs-lee", at=offset(SEM_S, -450, 700))

    st.step("sickles-salient", "Sickles advances to the Peach Orchard", "Thu 2 July, c. 3:00 - 4:00 pm",
            """Dissatisfied with his low ground at the south end of Cemetery Ridge, Sickles moved the III Corps half a mile
            west, to the slightly higher Emmitsburg Road. His new line ran from Devil's Den to the Peach Orchard and then
            along the road. It formed a salient that could be hit from two sides and was too long for his small corps. The
            Confederate guns opened about 3:00. Meade rode out and saw the problem, but it was too late to withdraw.""",
            date=when(1863, 7, 2))
    st.put("us-iii-corps", at=offset(PEACH, 100, 380), facing=250, width=2100, depth=40, state="ready", conjectural=True)
    st.put("cs-mclaws", at=offset(PEACH, -700, -50), facing=90, width=900, state="ready", move="advance")
    st.put("cs-hood", at=offset(DEN, -900, -250), facing=90, width=900, state="ready", move="advance")
    st.note(PEACH, "Peach Orchard salient", "label")

    st.step("round-tops", "Hood strikes Devil's Den and Little Round Top", "Thu 2 July, c. 4:00 - 6:00 pm",
            """Hood's division, after a long march, attacked just after 4:00. It drifted east and lost touch with the
            Emmitsburg Road, so the blow fell on Devil's Den and Little Round Top. Warren saw how vital the hill was.
            He sent Vincent's brigade, a battery and the 140th New York to it a few minutes before Law's brigade arrived. Vincent's four
            small regiments beat off repeated assaults. At the far left the 20th Maine under Chamberlain made a bayonet
            charge downhill that became one of the war's best-known episodes.""",
            date=when(1863, 7, 2))
    st.put("cs-hood", at=offset(DEN, -50, -150), facing=70, width=600, move="attack", state="engaged")
    st.put("us-vincent", at=offset(LRT, -30, -20), facing=250, width=300, depth=30, state="engaged", frame=True)
    st.put("us-v-corps", at=offset(LRT, 250, 400), facing=270, width=500, state="ready", frame=True)
    st.put("us-iii-corps", state="engaged")
    st.note(LRT, "20th Maine bayonet charge", "clash")

    st.step("wheatfield-peach", "The Wheatfield and the Peach Orchard", "Thu 2 July, c. 5:00 - 7:00 pm",
            """McLaws attacked about 5:00 and overwhelmed the III Corps in the Wheatfield and the Peach Orchard. His
            men pushed down into Plum Run valley before the Pennsylvania Reserves of the V Corps stopped them. Meade fed in
            some 20,000 reinforcements: the V Corps, Caldwell's II Corps division, most of the XII Corps and part of the VI
            Corps. The III Corps was nearly destroyed, and Sickles lost a leg. At about 6:00 Anderson's division reached
            Cemetery Ridge, where Hancock threw in the 1st Minnesota to buy time.""",
            date=when(1863, 7, 2))
    st.put("cs-mclaws", at=offset(WHEAT, 100, 200), facing=60, width=900, move="attack", state="engaged")
    st.put("us-iii-corps", at=offset(WHEAT, 450, 450), facing=250, width=1200, state="routed", move="retreat")
    st.put("us-v-corps", at=offset(WHEAT, 550, -50), facing=250, width=700, move="attack", state="engaged")
    st.put("cs-anderson", at=offset(ANGLE, -350, -150), facing=70, width=900, move="attack", state="engaged")
    st.put("us-ii-corps", state="engaged")
    st.note(WHEAT, "Wheatfield: Caldwell's division breaks", "clash")
    st.note(offset(ANGLE, -80, -200), "1st Minnesota charge", "event")

    st.step("culp-east-cem", "Evening attacks on the Union right", "Thu 2 July, c. 6:00 - 10:00 pm",
            """Ewell had understood his orders to mean a cannonade, and only around 6:00 did he order his divisions
            forward. Johnson had to cross Rock Creek, and only three of his four brigades attacked Culp's Hill. The XII Corps
            had gone south, so Greene's New Yorkers held the new works alone until I and XI Corps reinforcements came.
            Johnson's men took a few lower earthworks. On East Cemetery Hill, Hays and Avery's brigades reached the
            guns and the crest. Without support on their right they withdrew.""",
            date=when(1863, 7, 2), light="dusk")
    st.put("cs-johnson", at=offset(CULP, 350, 120), facing=250, width=500, depth=40, move="attack", state="engaged")
    st.put("us-greene", at=offset(CULP, -30, 10), facing=70, width=350, depth=30, state="engaged", frame=True)
    st.put("us-xii-corps", at=offset(ANGLE, -100, -600), facing=270, width=500, state="ready", move="retreat")
    st.put("cs-early", at=offset(CEM_HILL, 250, 70), facing=225, width=450, move="attack", state="engaged")
    st.put("us-xi-corps", state="engaged")
    st.note(offset(CEM_HILL, 160, 40), "Hays and Avery reach the crest", "clash")

    st.step("culp-dawn", "The second fight for Culp's Hill", "Fri 3 July, dawn - 11:00 am",
            """Lee meant to repeat the plan of the previous day, with Longstreet on the left and Ewell on Culp's Hill. The Union XII
            Corps struck first, opening an artillery bombardment at dawn to win back its lost works. Johnson's men attacked
            again, and the fight lasted about seven hours. Harry Pfanz judged that the Union line ended the morning intact and
            held more strongly than before. Lee had to change his plan and look to the centre.""",
            date=when(1863, 7, 3), light="dawn")
    st.put("us-xii-corps", at=offset(CULP, -60, -150), facing=70, width=700, state="engaged", move="attack")
    st.put("cs-johnson", at=offset(CULP, 280, -60), facing=250, width=550, state="wavering", move="retreat")
    st.put("us-greene", state="engaged")
    st.put("us-hancock", at=offset(ANGLE, 100, 80))
    st.note(CULP, "Culp's Hill held", "event")

    st.step("bombardment", "The great cannonade", "Fri 3 July, c. 1:00 - 3:00 pm",
            """Lee now planned an attack on the Union II Corps on Cemetery Ridge. Pickett's division and six
            brigades from Hill's corps would make it under Longstreet. Longstreet argued that it would fail, but obeyed. Around
            1:00 pm between 150 and 170 Confederate guns opened what was probably the largest bombardment of the war. Hunt
            saved the Union ammunition, then about 15 minutes later about 80 Union guns replied. The Confederates were short of
            shells, and the Union line was little hurt.""",
            date=when(1863, 7, 3), light="day")
    st.hide("cs-hood")
    st.hide("cs-mclaws")
    st.hide("cs-anderson")
    st.hide("us-iii-corps")
    st.hide("us-v-corps")
    st.hide("us-vincent")
    st.hide("cs-early")
    st.hide("us-xi-corps")
    st.hide("us-i-corps")
    st.hide("us-xii-corps")
    st.hide("us-greene")
    st.hide("cs-johnson")
    st.put("cs-pickett", at=offset(ANGLE, -1300, 20), facing=90, width=800, depth=60, state="ready", frame=True, strength_n=5800)
    st.put("cs-pettigrew", at=offset(ANGLE, -1300, 1000), facing=90, width=800, depth=60, state="ready", frame=True)
    st.put("cs-artillery", at=offset(ANGLE, -1700, 200), facing=90, width=2200, depth=30, state="engaged")
    st.put("us-artillery", at=offset(ANGLE, -80, 30), facing=270, width=1300, depth=25, state="engaged")
    st.fire("cs-artillery", st.pl("us-ii-corps")["at"], mlabel="150-170 guns")
    st.put("us-ii-corps", at=offset(ANGLE, 20, 300), facing=270, width=1000, state="ready")

    st.step("pickett-charge", "Pickett's Charge", "Fri 3 July, c. 3:00 - 4:00 pm",
            """When the guns went quiet, between 10,500 and 12,500 Confederates stepped out of the trees and crossed
            three-quarters of a mile of open ground toward Cemetery Ridge. Union guns on Cemetery Hill and Little Round Top
            raked their flank, and musket and canister fire came from Hancock's line. At a bend in a low stone wall known as the
            Angle the Union line broke, and Armistead's brigade got in to the guns. Reinforcements sealed the breach. Nearly
            half of the attackers did not come back, and Pickett's division lost about two thirds of its men.""",
            date=when(1863, 7, 3), light="day")
    st.put("cs-pickett", at=offset(ANGLE, -150, -20), facing=75, width=700, depth=50, state="engaged", move="charge")
    st.put("cs-pettigrew", at=offset(ANGLE, -250, 950), facing=80, width=700, depth=50, state="wavering", move="charge")
    st.put("us-ii-corps", state="engaged")
    st.note(ANGLE, "Angle: high-water mark", "clash")
    st.note(offset(ANGLE, 450, -330), "Armistead mortally wounded", "death")

    st.step("cavalry-and-retreat", "Cavalry fights and the end of the battle", "Fri 3 July, afternoon - evening",
            """Two cavalry fights ran alongside the infantry assault. About three miles northeast of the town Stuart tried to get behind
            the Union line, but Gregg and Custer stopped him in a sabre melee. South of Big Round Top, after Pickett failed, Kilpatrick
            sent Farnsworth's brigade against entrenched infantry over rough ground. Farnsworth was killed in the fourth of five
            failed charges. Lee withdrew to Seminary Ridge, and on 4 July he began his retreat toward the Potomac.""",
            date=when(1863, 7, 3, end=(1863, 7, 4)), light="dusk")
    st.put("cs-pickett", at=offset(ANGLE, -900, -20), facing=270, width=500, state="routed", move="retreat")
    st.put("cs-pettigrew", at=offset(ANGLE, -900, 950), facing=270, width=600, state="routed", move="retreat")
    st.put("cs-stuart", at=offset(TOWN, 4400, 500), facing=270, width=400, state="engaged", frame=True)
    st.put("us-gregg", at=offset(TOWN, 3900, 400), facing=90, width=400, state="engaged", frame=True)
    st.put("us-kilpatrick", at=offset(LRT, -150, -1300), facing=280, width=400, state="engaged", move="charge", start=offset(LRT, 700, -1100), frame=True)
    st.note(offset(TOWN, 4150, 450), "East Cavalry Field", "clash")
    st.note(offset(LRT, -500, -900), "Farnsworth killed", "death")

    return st.doc(
        slug="battle-of-gettysburg", kind="battle",
        entity={"name": "Battle of Gettysburg", "wikidata": "Q33132"},
        title="Battle of Gettysburg", date_label="1-3 July 1863", year=1863,
        intro="""For three days in the summer of 1863 the Army of the Potomac under George Meade and Robert E. Lee's Army of
        Northern Virginia fought around a small Pennsylvania road junction, in the largest battle of the American Civil
        War. Lee had carried the war north to take pressure off Virginia and to hurt Northern morale. His cavalry, under
        Stuart, was away on a raid, and Lee stumbled into a fight he had not chosen. On 1 July Union cavalry and I Corps
        fought a delaying action west and north of the town until they were driven back to Cemetery Hill. On 2 July Lee
        attacked both ends of the Union fishhook. On 3 July he sent about 12,000 men across open fields at the centre. They
        were beaten back with enormous loss, and Lee retreated to Virginia.""",
        outcome="Union victory: Pickett's Charge failed and Lee's army retreated to Virginia on 4 July.",
        uncertainty="""Coordinates for the ridges, hills and farms come from OpenStreetMap. Brigade-level positions,
        unit widths, the northern course of Rock Creek and the Chambersburg Pike are reconstructions (marked conjectural
        where drawn). Strength and loss figures are ranges from the sources. The timing of Ewell's attacks on 2 July and
        the claim that Lee ordered only a diversion there are disputed, as is how decisive a victory this was.""",
        sources=[{"title": "Battle of Gettysburg - Wikipedia", "url": "https://en.wikipedia.org/wiki/Battle_of_Gettysburg", "kind": "web"}],
        sides=[
            {"id": "us", "name": "Union Army of the Potomac", "color": "#1d4ed8",
             "polity": {"name": "Union (American Civil War)", "wikidata": "Q214102"},
             "commanders": [{"name": "George G. Meade", "wikidata": "Q297121", "role": "army commander"}],
             "strength": "93,500-104,256 soldiers; 360 guns", "losses": "23,049"},
            {"id": "cs", "name": "Confederate Army of Northern Virginia", "color": "#b91c1c",
             "polity": {"name": "Confederate States of America", "wikidata": "Q81931"},
             "commanders": [{"name": "Robert E. Lee", "wikidata": "Q165557", "role": "army commander"}],
             "strength": "65,000-75,000 men; 270 guns", "losses": "23,000-28,000"},
        ],
        units=[
            {"id": "us-buford", "side": "us", "kind": "light_cavalry", "label": "Buford's cavalry"},
            {"id": "us-cav-horses", "side": "us", "kind": "baggage", "label": "Horse-holders"},
            {"id": "us-i-corps", "side": "us", "kind": "infantry", "label": "I Corps (Reynolds)"},
            {"id": "us-xi-corps", "side": "us", "kind": "infantry", "label": "XI Corps (Howard)"},
            {"id": "us-hancock", "side": "us", "kind": "commander", "label": "Hancock"},
            {"id": "us-xii-corps", "side": "us", "kind": "infantry", "label": "XII Corps"},
            {"id": "us-ii-corps", "side": "us", "kind": "infantry", "label": "II Corps"},
            {"id": "us-iii-corps", "side": "us", "kind": "infantry", "label": "III Corps (Sickles)"},
            {"id": "us-v-corps", "side": "us", "kind": "infantry", "label": "V Corps"},
            {"id": "us-vincent", "side": "us", "kind": "infantry", "label": "Vincent's brigade"},
            {"id": "us-greene", "side": "us", "kind": "infantry", "label": "Greene's brigade"},
            {"id": "us-artillery", "side": "us", "kind": "artillery", "label": "Union artillery"},
            {"id": "us-gregg", "side": "us", "kind": "cavalry", "label": "Gregg and Custer"},
            {"id": "us-kilpatrick", "side": "us", "kind": "cavalry", "label": "Farnsworth's brigade"},
            {"id": "us-meade", "side": "us", "kind": "commander", "label": "Meade"},
            {"id": "cs-heth", "side": "cs", "kind": "infantry", "label": "Heth's division"},
            {"id": "cs-pender", "side": "cs", "kind": "infantry", "label": "Pender's division"},
            {"id": "cs-rodes", "side": "cs", "kind": "infantry", "label": "Rodes's division"},
            {"id": "cs-early", "side": "cs", "kind": "infantry", "label": "Early's division"},
            {"id": "cs-johnson", "side": "cs", "kind": "infantry", "label": "Johnson's division"},
            {"id": "cs-hood", "side": "cs", "kind": "infantry", "label": "Hood's division"},
            {"id": "cs-mclaws", "side": "cs", "kind": "infantry", "label": "McLaws's division"},
            {"id": "cs-anderson", "side": "cs", "kind": "infantry", "label": "Anderson's division"},
            {"id": "cs-pickett", "side": "cs", "kind": "infantry", "label": "Pickett's division"},
            {"id": "cs-pettigrew", "side": "cs", "kind": "infantry", "label": "Pettigrew's command"},
            {"id": "cs-artillery", "side": "cs", "kind": "artillery", "label": "Confederate guns"},
            {"id": "cs-stuart", "side": "cs", "kind": "cavalry", "label": "Stuart's cavalry"},
            {"id": "cs-lee", "side": "cs", "kind": "commander", "label": "Lee"},
        ],
        terrain=[
            {"id": "cemetery-hill", "kind": "hill", "label": "Cemetery Hill", "area": _hill(CEM_HILL, 300, 250)},
            {"id": "culps-hill", "kind": "hill", "label": "Culp's Hill", "area": _hill(CULP, 300, 300)},
            {"id": "cemetery-ridge", "kind": "ridge", "label": "Cemetery Ridge",
             "line": [list(offset(ANGLE, 0, 700)), list(ANGLE), list(offset(LRT, 100, 450))], "conjectural": True},
            {"id": "seminary-ridge", "kind": "ridge", "label": "Seminary Ridge",
             "line": [list(offset(SEM_S, -50, 1400)), list(offset(SEM_S, 0, 700)), list(SEM_S)], "conjectural": True},
            {"id": "mcpherson-ridge", "kind": "ridge", "label": "McPherson Ridge",
             "line": [list(offset(MCP, 0, 500)), list(MCP), list(offset(MCP, 60, -500))], "conjectural": True},
            {"id": "round-top", "kind": "hill", "label": "Little Round Top", "area": _hill(LRT, 200, 250)},
            {"id": "big-round-top", "kind": "hill", "label": "Big Round Top", "area": _hill((-77.2394, 39.78675), 250, 250)},
            {"id": "peach", "kind": "farm", "label": "Peach Orchard", "at": list(PEACH)},
            {"id": "wheatfield", "kind": "field", "label": "Wheatfield", "area": _hill(WHEAT, 200, 200)},
            {"id": "devils-den", "kind": "site", "label": "Devil's Den", "at": list(DEN)},
            {"id": "town", "kind": "town", "label": "Gettysburg", "at": list(TOWN)},
            {"id": "rock-creek", "kind": "stream", "label": "Rock Creek", "line": ROCK_CREEK},
            {"id": "emmitsburg-road", "kind": "road", "label": "Emmitsburg Road", "line": EMMITSBURG_ROAD},
            {"id": "pike", "kind": "road", "label": "Chambersburg Pike", "line": CHAMBERSBURG_PIKE, "conjectural": True},
        ],
    )


def _hill(c, rx, ry):
    from pipeline.map_stories.geo import ellipse
    return ellipse(c, rx, ry)
