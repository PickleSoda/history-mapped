"""Reconcile (C3 over QID-less rows) against an offline client: no network, no DB."""
from pipeline.audit.reconcile import (Context, build_contexts, date_signal, decide, name_match, reconcile_rows,
                                      score, settle, split_qualifier)
from pipeline.audit.tests.conftest import CLOSURE, make_row, rec

CL = {**CLOSURE, "Q188055": {"Q188055"}, "Q198": {"Q198"}, "Q99": {"Q56061"}}


def _closure_fn(classes):
    return CL


def _names(client):
    def names_of(q):
        r = client.entities.get(q)
        return [r["label"], *r.get("aliases", [])] if r else []
    return names_of


def _ctx(**kw):
    base = {"anchors": [], "related_qids": set(), "hay": []}
    base.update(kw)
    return Context(**base)


def test_name_match_label_alias_enwiki_and_qualifier():
    r = rec("Cattedrale di Monreale", p31=["Q16970"])
    r["enwiki"] = "Monreale Cathedral"
    assert name_match("Monreale Cathedral", r) == ("enwiki", "", "")
    assert name_match("Tu Duc", rec("Tự Đức")) == ("label", "", "")
    assert name_match("Emperor Tu Duc", rec("Tự Đức", aliases=["Emperor Tự Đức"])) == ("alias", "", "")
    assert name_match("Siege of Rhodes", rec("Siege of Rhodes (1522)")) == ("label", "1522", "")
    assert name_match("Capture of Sofia (1385)", rec("Capture of Sofia")) == ("label", "", "1385")
    assert name_match("Siege of Rhodes", rec("Siege of Rhodes and Kos")) is None  # no partial names
    assert split_qualifier("Gaur (city)") == ("Gaur", "city")


def test_qualifiers_must_not_say_something_else(client):
    town = make_row("Harfleur (settlement)", "city", summary="Port on the Seine estuary in Normandy.")
    samian = rec("Harfleur (Samian Ware Discovery Site)", p31=["Q515"], description="Harfleur as discovery site")
    assert score(town, "Q1", samian, _ctx(hay=[" port on the seine estuary in normandy "]), CL,
                 _names(client))["name"] == ""
    commune = rec("Harfleur", p31=["Q515"], description="commune in Seine-Maritime, Normandy, France")
    assert score(town, "Q2", commune, _ctx(hay=[" port on the seine estuary in normandy "]), CL,
                 _names(client))["name"] == "label(settlement)"   # 'settlement' is generic for a city
    son = make_row("Antiochus (son of Seleucus IV)", start=-175, end=-170)
    assert score(son, "Q3", rec("Antiochus", dates={"P569": [-175, 9], "P570": [-170, 9]},
                                description="son of Seleucus IV Philopator"), _ctx(), CL, _names(client))["name"]
    assert not score(son, "Q4", rec("Antiochus", dates={"P569": [-175, 9], "P570": [-170, 9]},
                                    description="Greek sculptor"), _ctx(), CL, _names(client))["name"]


def test_a_place_matched_only_through_an_alias_needs_a_link(client):
    row = make_row("Tlalancaleca", "city", start=-200, summary="Formative-period centre in the Puebla valley.")
    ctx = build_contexts([row], {row.id: row}, [])[row.id]
    seat = rec("San Matías Tlalancaleca", p31=["Q515"], aliases=["Tlalancaleca"],
               description="municipal seat of Tlalancaleca, State of Puebla, Mexico")
    s = score(row, "Q1", seat, ctx, CL, _names(client))
    assert s["place"] and not s["ok"] and "alias" in s["need"]


def test_c2_recheck_tolerates_only_what_reconcile_weighed():
    from pipeline.audit.reconcile import c2_passes
    enwiki = {"name": "enwiki", "dates": "own", "date_detail": ""}
    assert c2_passes({"verdict": "ok", "rule": ""}, enwiki)
    assert c2_passes({"verdict": "suspect", "rule": "S8 names share nothing"}, enwiki)
    assert not c2_passes({"verdict": "suspect", "rule": "S8 names share nothing"}, {**enwiki, "name": "alias"})
    reign = {"name": "label", "dates": "anchors", "date_detail": "row span -911..-870 inside the life (reign dates?)"}
    assert c2_passes({"verdict": "suspect", "rule": "S6 dates outside tolerance"}, reign)
    assert not c2_passes({"verdict": "suspect", "rule": "S1 class contradicts type"}, enwiki)
    assert not c2_passes({"verdict": "wrong", "rule": "W8 far era"}, enwiki)


def test_year_qualifier_must_fit_the_row(client):
    row = make_row("Siege of Rhodes", "event_battle", start=1522, end=1522)
    good = rec("Siege of Rhodes (1522)", p31=["Q188055"], dates={"P580": [1522, 11], "P582": [1522, 11]})
    bad = rec("Siege of Rhodes (1480)", p31=["Q188055"], dates={"P580": [1522, 11], "P582": [1522, 11]})
    ctx = _ctx(hay=[" knights of rhodes "])
    assert score(row, "Q1", good, ctx, CL, _names(client))["name"] == "label(1522)"
    assert score(row, "Q2", bad, ctx, CL, _names(client))["name"] == ""


def test_dates_own_anchors_and_conflict():
    person = make_row("Solomon of Hungary")
    life = rec("Solomon of Hungary", dates={"P569": [1053, 11], "P570": [1087, 11]})
    assert date_signal(person, life, [1063, 1074])[0] == "anchors"
    assert date_signal(person, life, [1074, 1120])[0] == "conflict"   # a relation after his death
    coarse = rec("Solomon", dates={"P569": [1000, 7], "P570": [1100, 7]})
    assert date_signal(person, coarse, [1074])[0] == "unknown"        # century dates confirm nothing
    assert date_signal(person, life, [])[0] == "none"
    dated = make_row("Muhammad ibn al-Qasim", start=695, end=715)
    assert date_signal(dated, rec("x", dates={"P569": [695, 9], "P570": [715, 9]}), [])[0] == "own"
    reign = make_row("Muawiya I", start=661, end=680)
    assert date_signal(reign, rec("x", dates={"P569": [602, 9], "P570": [680, 9]}), [])[0] == "anchors"
    battle = make_row("Battle of X", "event_battle", start=1260, end=1260)
    assert date_signal(battle, rec("x", dates={"P585": [1263, 11]}), [])[0] == "conflict"
    work = make_row("Divina Commedia", "cultural_work", start=1320)
    assert date_signal(work, rec("x", dates={"P577": [1321, 9]}), [])[0] == "own"
    assert date_signal(work, rec("x", dates={"P577": [1500, 9]}), [])[0] == "conflict"


def test_battle_needs_place_or_war_context(client):
    row = make_row("Siege of Bajaur", "event_battle", start=1519, end=1519,
                   summary="Babur's capture of the frontier town of Bajaur in 1519.")
    item = rec("Siege of Bajaur", p31=["Q188055"], dates={"P585": [1519, 11]}, description="1519 siege")
    bare = score(row, "Q1", item, _ctx(hay=[]), CL, _names(client))
    assert not bare["ok"] and "context" in bare["need"]
    client.entities["Q50"] = rec("Bajaur", p31=["Q515"])
    item["links"] = {"P276": ["Q50"]}
    ctx = build_contexts([row], {row.id: row}, [])[row.id]
    placed = score(row, "Q1", item, ctx, CL, _names(client))
    assert placed["ok"] and placed["place"] == "text:Bajaur"
    # war context through a related war row's QID
    item["links"] = {"P361": ["Q777"]}
    war = score(row, "Q1", item, _ctx(related_qids={"Q777"}), CL, _names(client))
    assert war["ok"] and war["war"] == "related:Q777"


def test_a_same_named_same_era_rival_blocks_the_match(client):
    row = make_row("Henry of Bavaria", start=1100, end=1150)
    a = score(row, "Q1", rec("Henry of Bavaria", dates={"P569": [1100, 9], "P570": [1150, 9]}),
              _ctx(), CL, _names(client))
    b = score(row, "Q2", rec("Henry of Bavaria", dates={"P569": [1102, 9], "P570": [1149, 9]}),
              _ctx(), CL, _names(client))
    far = score(row, "Q3", rec("Henry of Bavaria", dates={"P569": [1900, 9], "P570": [1960, 9]}),
                _ctx(), CL, _names(client))
    undated = score(row, "Q4", rec("Henry of Bavaria"), _ctx(), CL, _names(client))
    assert decide(row, [a, far])["outcome"] == "accepted"          # another era is no rival
    assert decide(row, [a, b])["outcome"] == "ambiguous"
    assert decide(row, [a, undated])["outcome"] == "ambiguous"     # an undated namesake may be him


def test_one_word_person_needs_the_primary_article(client):
    row = make_row("Draco", start=-650, end=-600)
    item = rec("Draco", dates={"P569": [-650, 9], "P570": [-600, 9]})
    assert score(row, "Q1", item, _ctx(), CL, _names(client))["ok"]          # both own dates agree
    undated = make_row("Draco")
    other = rec("Draco", dates={"P569": [-650, 9], "P570": [-600, 9]}, enwiki=False)
    assert not score(undated, "Q1", other, _ctx(anchors=[-621]), CL, _names(client))["ok"]
    assert score(undated, "Q1", item, _ctx(anchors=[-621]), CL, _names(client))["ok"]  # enwiki 'Draco'


def test_city_needs_place_agreement_and_a_settlement(client):
    row = make_row("Gaur", "city", summary="Capital of the Bengal Sultanate from 1433 CE.")
    ctx = build_contexts([row], {row.id: row}, [])[row.id]
    india = rec("Gaur", p31=["Q515"], description="ruined city in Malda district, West Bengal, India")
    nepal = rec("Gaur", p31=["Q515"], description="municipality in Rautahat District, Nepal")
    district = rec("Gaur", p31=["Q99"], description="district of Bengal")
    s = [score(row, q, r, ctx, CL, _names(client)) for q, r in (("Q1", india), ("Q2", nepal), ("Q3", district))]
    assert s[0]["ok"] and s[0]["place"] == "description:bengal"
    assert not s[2]["class"]           # an administrative district is not the town
    # a place word in the text does not outweigh a same-named town elsewhere ...
    assert s[1]["rival"] and decide(row, s)["outcome"] == "ambiguous"
    # ... a graph link does: the item is the capital of a related row (the Bengal Sultanate)
    india["links"] = {"P1376": ["Q2088"]}
    linked = score(row, "Q1", india, _ctx(related_qids={"Q2088"}, related_types={"Q2088": "political_entity"},
                                          hay=ctx.hay), CL, _names(client))
    assert linked["link"] and decide(row, [linked, s[1], s[2]])["outcome"] == "accepted"


def test_a_place_named_like_the_row_confirms_nothing(client):
    # Salò on Lake Garda; the Indonesian village 'Salo' sits in a district also called 'Salo'
    row = make_row("Salo", "city", summary="Town on Lake Garda that gave its name to the Italian Social Republic.")
    ctx = _ctx(hay=[" town on lake garda that gave its name to the italian social republic ", " republic of salo "])
    client.entities["Q77"] = rec("Salo", p31=["Q515"])
    village = {**rec("Salo", p31=["Q515"], description="village in Kampar Regency, Riau, Indonesia"),
               "links": {"P131": ["Q77"]}}
    assert score(row, "Q1", village, ctx, CL, _names(client))["place"] == ""


def test_one_word_person_needs_birth_and_death_not_one_of_them(client):
    row = make_row("Theodore", start=590, end=650, summary="Brother of Heraclius.")
    pope = rec("Theodore I", aliases=["Theodore"], dates={"P570": [649, 11]}, enwiki=False)
    s = score(row, "Q104244", pope, _ctx(), CL, _names(client))
    assert s["dates"] == "own" and not s["ok"] and "one-word" in s["need"]


def test_loose_dates_alone_do_not_identify_a_movement(client):
    row = make_row("Movement to Protect the Constitution", "intellectual_movement", start=1912, end=1913)
    china = rec("Constitutional Protection Movement", p31=["Q99999"], aliases=["Movement to Protect the Constitution"],
                dates={"P580": [1917, 11], "P582": [1922, 11]}, description="Chinese political movements")
    s = score(row, "Q2641005", china, _ctx(hay=[" diet cabinet clan oligarchy "]), CL, _names(client))
    assert s["dates"] == "own" and not s["ok"]
    china["enwiki"] = "Movement to Protect the Constitution"   # the article of that exact name would do
    assert score(row, "Q2641005", china, _ctx(), CL, _names(client))["ok"]


def test_settle_never_gives_one_qid_to_two_rows():
    rows = {"a": make_row("Battle of A", "event_battle", id="a"), "b": make_row("Battle of A", "event_battle", id="b"),
            "c": make_row("Battle of C", "event_battle", id="c"),
            "h": make_row("Battle of C", "event_battle", id="h", qid="Q3"),
            "d": make_row("Battle of D", "event_battle", id="d")}
    recs = [{"entity_id": i, "outcome": "accepted", "qid": q, "action": "", "held_by": ""}
            for i, q in (("a", "Q1"), ("b", "Q1"), ("c", "Q3"), ("d", "Q4"))]
    settle(recs, rows)
    act = {r["entity_id"]: r["action"] for r in recs}
    assert act == {"a": "duplicate_of:b", "b": "duplicate_of:a", "c": "duplicate_of:h", "d": "set_qid"}


def test_reconcile_rows_end_to_end(client):
    war = make_row("Ottoman–Hospitaller wars", "event_war", qid="Q900", id="w", start=1480, end=1565)
    battle = make_row("Capture of Tripoli", "event_battle", id="b", start=1551, end=1551,
                      summary="Capture of Tripoli from the Knights Hospitaller in 1551 CE by Dragut.")
    person = make_row("Dragut", id="p")
    person.attributes = {"_rejected_wikidata_id": "Q10"}
    rows = {r.id: r for r in (war, battle, person)}
    rels = [{"id": "r1", "source": "b", "target": "w", "type": "part_of", "start": None, "end": None,
             "description": ""},
            {"id": "r2", "source": "p", "target": "b", "type": "commanded", "start": None, "end": None,
             "description": ""}]
    client.titles.update({"Capture of Tripoli": None, "Dragut": "Q10"})
    client.searches["Capture of Tripoli␟20"] = [{"qid": "Q20", "match_text": ""}, {"qid": "Q21", "match_text": ""}]
    client.searches["Dragut␟20"] = [{"qid": "Q10", "match_text": ""}, {"qid": "Q11", "match_text": ""}]
    client.entities["Q20"] = {**rec("Siege of Tripoli (1551)", p31=["Q188055"], dates={"P585": [1551, 11]},
                                    aliases=["Capture of Tripoli"]), "links": {"P361": ["Q900"]}}
    client.entities["Q21"] = {**rec("Capture of Tripoli", p31=["Q188055"], dates={"P585": [1289, 11]}),
                              "links": {}}
    client.entities["Q10"] = {**rec("Dragut", dates={"P569": [1485, 9], "P570": [1565, 9]}), "links": {}}
    client.entities["Q11"] = {**rec("Dragut", dates={"P569": [1485, 9], "P570": [1565, 9]}), "links": {}}
    client.entities["Q900"] = {**rec("Ottoman–Hospitaller wars", p31=["Q198"],
                                     dates={"P580": [1480, 9], "P582": [1565, 9]}), "links": {}}
    out = {r["entity_id"]: r for r in reconcile_rows([battle, person], rows, rels, client, _closure_fn,
                                                     log=lambda m: None)}
    assert out["b"]["outcome"] == "accepted" and out["b"]["qid"] == "Q20" and out["b"]["c2"] == "ok"
    assert out["b"]["war_check"] == "related:Q900"
    # the rejected Q10 never wins, but it still fits: it blocks its namesake Q11
    assert out["p"]["outcome"] == "ambiguous" and out["p"]["qid"] == ""
    # with the rejected item out of the era, Q11 is the one item, matched by the battle's year
    client.entities["Q10"] = {**rec("Dragut", dates={"P569": [1185, 9], "P570": [1265, 9]}), "links": {}}
    out = {r["entity_id"]: r for r in reconcile_rows([person], rows, rels, client, _closure_fn, log=lambda m: None)}
    assert out["p"]["qid"] == "Q11" and out["p"]["date_check"].startswith("anchors")


def test_rows_that_cannot_be_reconciled_are_skipped(client):
    rows = {"e": make_row("Some Event", "event_battle", id="e"), "p": make_row("Nobody", id="p")}
    out = reconcile_rows(list(rows.values()), rows, [], client, _closure_fn, log=lambda m: None)
    assert {r["outcome"] for r in out} == {"skipped"}


def test_parse_entity_keeps_links_and_coordinates():
    from pipeline.audit.wd import parse_entity
    ent = {"labels": {"en": {"value": "Siege of Tripoli"}},
           "claims": {"P361": [{"mainsnak": {"datavalue": {"value": {"id": "Q900"}}}}],
                      "P625": [{"mainsnak": {"datavalue": {"value": {"latitude": 32.9, "longitude": 13.18}}}}]}}
    out = parse_entity(ent)
    assert out["links"] == {"P361": ["Q900"]} and out["coord"] == [32.9, 13.18]


def test_cached_records_without_links_are_refetched_on_demand(client):
    client.entities["Q1"] = rec("Old")  # an older cache line: no 'links'
    calls = []
    client._fetch_batch = lambda batch: calls.append(batch) or {q: {**rec("New"), "links": {}} for q in batch}
    client.get_entities(["Q1"])
    assert calls == []
    client.get_entities(["Q1"], need_links=True)
    assert calls == [["Q1"]] and client.entities["Q1"]["label"] == "New"


def test_a_place_far_from_every_related_place_is_out_and_no_rival(client):
    # Wikidata gives the Wari Empire's capital as Huari village in Ancash; Wari is near Ayacucho
    row = make_row("Wari", "city", start=400, summary="Settlement near Quinua, northeast of Ayacucho in Peru.")
    ctx = _ctx(related_qids={"Q923516"}, reverse={"Q3322143"}, points=[(-13.06, -74.13)],  # Conchopata
               hay=[" settlement near quinua northeast of ayacucho in peru "])
    huari = {**rec("Huari", p31=["Q515"], aliases=["Wari"], description="village in Ancash, Peru"),
             "coord": [-9.347, -77.171], "links": {}}
    s = score(row, "Q3322143", huari, ctx, CL, _names(client))
    assert s["link"] == "reverse" and not s["ok"] and not s["rival"] and "km" in s["need"]
    site = {**rec("Wari", p31=["Q515"], description="archaeological site near Ayacucho, Peru"),
            "coord": [-13.06, -74.2], "links": {}}
    assert score(row, "Q1", site, ctx, CL, _names(client))["ok"]


def test_a_country_alone_places_only_the_article_of_that_name(client):
    client.entities["Q30"] = rec("United States", p31=["Q3024240"])
    row = make_row("Pony Express", "infrastructure_monument", start=1860, summary="Mail service across the West.")
    ctx = _ctx(related_qids={"Q30"})
    coaster = {**rec("Pony Express", p31=["Q16970"], description="roller coaster at Knott's Berry Farm"),
               "links": {"P17": ["Q30"]}}
    coaster["enwiki"] = "Pony Express (roller coaster)"
    s = score(row, "Q3397820", coaster, ctx, CL, _names(client))
    assert s["place"] == "country:related:Q30" and not s["ok"]
    coaster["enwiki"] = "Pony Express"   # the article of exactly that name would do
    assert score(row, "Q3397820", coaster, ctx, CL, _names(client))["ok"]


def test_an_alias_match_on_a_person_needs_place_or_link(client):
    row = make_row("Charles Dawes", start=1865, end=1951, summary="American banker who drew up the Dawes Plan.")
    photographer = rec("Charles Peet Dawes", aliases=["Charles Dawes"], dates={"P569": [1867, 11], "P570": [1947, 11]},
                       description="New Zealand photographer")
    s = score(row, "Q1", photographer, _ctx(hay=[" american banker who drew up the dawes plan "]), CL, _names(client))
    assert s["dates"] == "own" and not s["ok"] and "alias" in s["need"]


def test_located_in_a_country_sized_row_is_place_not_identity(client):
    row = make_row("Lothian", "political_entity", summary="Region secured by Malcolm II at Carham in 1018.")
    board = {**rec("Lothian", p31=["Q3024240"], description="Health board area in Scotland"),
             "links": {"P131": ["Q22"]}}
    scot = _ctx(anchors=[1018], related_qids={"Q22"}, related_types={"Q22": "political_entity"})
    s = score(row, "Q104635192", board, scot, CL, _names(client))
    assert s["place"] == "related:Q22" and s["link"] == "" and not s["ok"]
    city = _ctx(related_qids={"Q956"}, related_types={"Q956": "city"})
    square = {**rec("Tiananmen Square", p31=["Q16970"]), "links": {"P131": ["Q956"]}}
    assert score(make_row("Tiananmen Square", "infrastructure_monument"), "Q1", square, city, CL,
                 _names(client))["link"] == "P131:Q956"
