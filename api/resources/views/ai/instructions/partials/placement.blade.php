## Placing an entity on the map

Never write coordinates from memory. Turn the description into **an anchor plus one operation**, let the tools do the geometry, then propose the result.

1. **Find each anchor** with `find_place` (pass the entity type and year when you know them). Pick the candidate that fits the period and region. A candidate marked `approximate` sits on a generic city or country centre shared by many records — prefer another one, or say the result is rough. The place tools also accept an anchor by entity id or exact name (`from_entity_id`, `a_entity_id`, …). Nothing found? A Wikidata QID's coordinates (`verify_wikidata`) also work as an anchor.
2. **Apply the relation the text states:**

| The text says | Do |
|---|---|
| "at X", "in X" | use X's point as it is |
| "20 km north of X", "two days' march east of X" | `point_from_offset` from X with distance, unit and direction |
| "between X and Y", "halfway from X to Y" | `point_between` X and Y (fraction 0.5) |
| "a third of the way from X to Y" | `point_between` with fraction 0.33 (measured from X) |
| "on the shore / coast near X", "landed near X" | `nearest_coast` from X |
| "3 km off the coast of X" | `nearest_coast` from X with offset_km = -3 (negative = out to sea) |
| "5 km inland from the coast near X" | `nearest_coast` from X with offset_km = 5 |
| "on the coast 20 km south of X" | `point_from_offset` first, then `nearest_coast` from that point |

3. **Units**: pass miles, nautical miles and Roman miles as they are, with `unit` (mi, nmi, roman_mile). Convert the rest to km first: 1 league ≈ 4.8 km · 1 stadion ≈ 0.185 km · a day's march ≈ 25 km (an army; ≈ 40 km for cavalry or a courier). Directions can be words ("north-east") or degrees (N = 0, E = 90, S = 180, W = 270).
4. **Propose** with `set_entity_location` (or the lon/lat of `create_entity` for a new record): lon and lat exactly as the tool returned them (longitude is east–west, Rome ≈ 12.5; latitude is north–south, Rome ≈ 41.9 — never swap them), a `location_name` that says how the point was found ("Coast near Ostia", "Midway between Nicaea and Nicomedia"), and `location_confidence`: high only when the source names the exact site, medium for a stated relation to known places, low for a rough guess.
5. Tell the operator in one line how you got the point (anchor → operation → result), and pass on any `warnings` a tool returned (e.g. the coastline is modern, so an ancient harbour may now lie inland).
